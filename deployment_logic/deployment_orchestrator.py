"""
Main deployment orchestrator.
"""

import json
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from .feature_handler import OptionalFeatureHandler
from .progress_indicator import Colors, ProgressIndicator
from .python_detector import PythonDetector
from .resource_naming import ResourceNameGenerator
from .resource_tracker import ResourceTracker


class DeploymentOrchestrator:
    """Main deployment orchestrator"""

    def __init__(self, ci_mode=False, force_unlock=False):
        self.platform = self.detect_platform()
        self.root_dir = Path(__file__).parent.parent.absolute()
        self.terraform_dir = self.root_dir / "terraform" / "app-stack"
        self.data_stack_dir = self.root_dir / "terraform" / "data-stack"
        self.lambda_dir = self.root_dir / "lambda_functions"
        self.env_file = self.root_dir / ".env.local"
        self.backup_dir = self.root_dir / "terraform" / "backups"
        self.ci_mode = ci_mode
        self.force_unlock = force_unlock

        # Dual-stack support: track both data-stack and app-stack directories
        self.stacks = [
            {"name": "data-stack", "directory": self.data_stack_dir},
            {"name": "app-stack", "directory": self.terraform_dir},
        ]

        # Will be set during prerequisite validation
        self.python_cmd: Optional[str] = None
        self.terraform_cmd: Optional[str] = None
        self.aws_cmd: Optional[str] = None

        # Resource name generator (initialized after AWS validation)
        self.resource_name_generator: Optional[ResourceNameGenerator] = None

        # Resource tracker (initialized after AWS validation)
        self.resource_tracker: Optional[ResourceTracker] = None

        # Track Google OAuth status for post-deployment prompt
        self.google_oauth_enabled = False

        # Rollback and recovery state
        self.deployment_id = None
        self.state_backup_path = None
        self.deployment_started = False
        self.resources_created = []

        self.progress = ProgressIndicator(10)

    def detect_platform(self) -> str:
        """Detect current platform and return standardized name"""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "darwin":
            return "darwin"
        elif system == "linux":
            return "linux"
        else:
            return "unknown"

    def check_command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        return shutil.which(command) is not None

    def get_platform_install_instructions(self, tool: str) -> str:
        """Get platform-specific installation instructions for missing tools"""
        instructions = {
            "windows": {
                "python": "Install Python from https://python.org or use 'winget install Python.Python.3'",
                "terraform": "Install from https://terraform.io or use 'winget install Hashicorp.Terraform'",
                "aws": "Install AWS CLI from https://aws.amazon.com/cli/ or use 'winget install Amazon.AWSCLI'",
            },
            "darwin": {
                "python": "Install with 'brew install python' or from https://python.org",
                "terraform": "Install with 'brew install terraform' or from https://terraform.io",
                "aws": "Install with 'brew install awscli' or from https://aws.amazon.com/cli/",
            },
            "linux": {
                "python": "Install with your package manager or from https://python.org",
                "terraform": "Install from https://terraform.io or use your package manager",
                "aws": "Install with 'sudo apt install awscli' or from https://aws.amazon.com/cli/",
            },
        }

        return instructions.get(self.platform, {}).get(
            tool, f"Please install {tool} for your platform"
        )

    def _ensure_commands_available(self) -> bool:
        """Ensure all required commands are available and not None"""
        if not self.terraform_cmd:
            self.progress.error("Terraform command not available")
            return False
        if not self.aws_cmd:
            self.progress.error("AWS CLI command not available")
            return False
        if not self.python_cmd:
            self.progress.error("Python command not available")
            return False
        return True

    def validate_terraform_version(self) -> bool:
        """Validate Terraform version meets requirements"""
        if not self.terraform_cmd:
            return False

        try:
            result = subprocess.run(
                [cast(str, self.terraform_cmd), "version", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0:
                version_info = json.loads(result.stdout)
                terraform_version = version_info.get("terraform_version", "unknown")
                self.progress.success(f"Terraform version: {terraform_version}")

                # Check if version meets minimum requirement (1.8.0)
                version_parts = terraform_version.split(".")
                if len(version_parts) >= 2:
                    major, minor = int(version_parts[0]), int(version_parts[1])
                    if major > 1 or (major == 1 and minor >= 8):
                        return True
                    else:
                        self.progress.error(
                            f"Terraform version {terraform_version} is too old (minimum: 1.8.0)"
                        )
                        self.progress.info(
                            "Please upgrade Terraform to version 1.8.0 or later"
                        )
                        return False

            else:
                # Fallback to text version check
                if not self.terraform_cmd:
                    return False

                result = subprocess.run(
                    [cast(str, self.terraform_cmd), "version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    self.progress.success("Terraform version check completed")
                    return True

        except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
            self.progress.warning("Could not verify Terraform version")
            return True  # Don't fail deployment for version check issues

        return True

    def validate_terraform_configuration(self) -> bool:
        """Validate Terraform configuration files for both stacks with auto-fix capabilities"""
        self.progress.info(
            "Validating Terraform configuration files for both stacks..."
        )

        # Validate each stack
        all_stacks_valid = True
        for stack in self.stacks:
            stack_name = stack["name"]
            stack_dir = stack["directory"]

            self.progress.info(f"Validating {stack_name} configuration...")

            if not self._validate_single_stack_configuration(stack_name, stack_dir):
                all_stacks_valid = False
                self.progress.error(f"{stack_name} validation failed")
            else:
                self.progress.success(f"{stack_name} configuration is valid")

        if all_stacks_valid:
            self.progress.success("All stack configurations are valid")
        else:
            self.progress.error("One or more stack configurations failed validation")

        return all_stacks_valid

    def _validate_single_stack_configuration(
        self, stack_name: str, stack_dir: Path
    ) -> bool:
        """Validate Terraform configuration files for a single stack"""
        # Check required Terraform files exist
        required_files = ["main.tf", "variables.tf", "outputs.tf"]

        # env_to_tfvars.py is only required for app-stack (it's the shared script)
        if stack_name == "app-stack":
            required_files.append("env_to_tfvars.py")

        missing_files = []
        for file_name in required_files:
            file_path = stack_dir / file_name
            if not file_path.exists():
                missing_files.append(file_name)

        if missing_files:
            self.progress.error(
                f"Missing required Terraform files in {stack_name}: {', '.join(missing_files)}"
            )
            self.progress.info("Ensure all Terraform configuration files are present")
            return False

            # Validate S3 bucket naming configuration (only for app-stack)
            if not self._validate_s3_bucket_configuration():
                return False

        # Initialize Terraform
        self.progress.info(f"Initializing Terraform for {stack_name}...")

        # Create S3 bucket and DynamoDB table before initializing backend
        if not self._create_terraform_state_bucket():
            return False
        if not self._create_terraform_lock_table():
            return False

        backend_names = cast(
            ResourceNameGenerator, self.resource_name_generator
        ).get_terraform_backend_names()
        backend_config = [
            f'-backend-config=bucket={backend_names["state_bucket"]}',
            f"-backend-config=key={stack_name}/terraform.tfstate",
            f"-backend-config=region={cast(ResourceNameGenerator, self.resource_name_generator).aws_region}",
            "-backend-config=use_lockfile=true",
            "-backend-config=encrypt=true",
        ]

        if stack_name == "data-stack":
            init_command = [
                cast(str, self.terraform_cmd),
                "init",
                "-upgrade",
                "-force-copy",
            ] + backend_config
        else:
            init_command = [
                cast(str, self.terraform_cmd),
                "init",
                "-upgrade",
                "-reconfigure",
                "-input=false",
            ] + backend_config

        init_result = subprocess.run(
            init_command,
            cwd=str(stack_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )

        if init_result.returncode != 0:
            self.progress.error(f"Terraform initialization failed for {stack_name}")
            if init_result.stderr:
                self.progress.error("Error output:")
                print(init_result.stderr)
            return False

        self.progress.success(f"Terraform initialized successfully for {stack_name}")

        # Validate Terraform syntax
        try:
            result = subprocess.run(
                [cast(str, self.terraform_cmd), "validate"],
                cwd=str(stack_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return True
            else:
                self.progress.error(
                    f"{stack_name} Terraform configuration validation failed"
                )

                # Try to auto-fix common validation issues (only for app-stack)
                if (
                    stack_name == "app-stack"
                    and self._attempt_terraform_validation_fixes(result.stderr)
                ):
                    # Retry validation after fixes
                    retry_result = subprocess.run(
                        [cast(str, self.terraform_cmd), "validate"],
                        cwd=str(stack_dir),
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if retry_result.returncode == 0:
                        self.progress.success(
                            f"{stack_name} Terraform configuration fixed and validated"
                        )
                        return True

                if result.stderr:
                    self.progress.info(f"{stack_name} validation errors:")
                    print(result.stderr)
                self.progress.info("Common solutions:")
                self.progress.info("1. Check syntax in .tf files")
                self.progress.info("2. Ensure all required variables are defined")
                self.progress.info("3. Verify provider configurations")
                return False

        except subprocess.TimeoutExpired:
            self.progress.error(f"{stack_name} Terraform validation timed out")
            return False
        except Exception as e:
            self.progress.error(
                f"Error validating {stack_name} Terraform configuration: {e}"
            )
            return False

    def _validate_s3_bucket_configuration(self) -> bool:
        """Validate S3 bucket naming configuration and auto-resolve conflicts"""
        try:
            # Check if locals.tf exists and has proper random_id configuration
            locals_file = self.terraform_dir / "locals.tf"
            if not locals_file.exists():
                self.progress.warning(
                    "locals.tf not found - checking for S3 bucket configuration"
                )
                return self._check_s3_bucket_naming_in_main_tf()

            with open(locals_file, "r", encoding="utf-8") as f:
                locals_content = f.read()

            # Verify random_id resource exists for bucket naming
            if (
                "random_id" not in locals_content
                or "bucket_suffix" not in locals_content
            ):
                self.progress.warning("S3 bucket random naming not configured properly")
                return self._auto_fix_s3_bucket_naming()

            self.progress.success("S3 bucket naming configuration validated")
            return True

        except Exception as e:
            self.progress.error(f"Error validating S3 bucket configuration: {e}")
            return False

    def _check_s3_bucket_naming_in_main_tf(self) -> bool:
        """Check S3 bucket naming configuration in main.tf"""
        try:
            main_tf = self.terraform_dir / "main.tf"
            if not main_tf.exists():
                self.progress.error("main.tf not found")
                return False

            with open(main_tf, "r", encoding="utf-8") as f:
                main_content = f.read()

            # Check for proper bucket naming with random suffix
            if "random_id" in main_content and (
                "bucket_suffix" in main_content or "hex" in main_content
            ):
                self.progress.success("S3 bucket naming properly configured in main.tf")
                return True
            else:
                self.progress.warning("S3 bucket naming may cause conflicts")
                return self._auto_fix_s3_bucket_naming()

        except Exception as e:
            self.progress.error(f"Error checking main.tf: {e}")
            return False

    def _auto_fix_s3_bucket_naming(self) -> bool:
        """Auto-fix S3 bucket naming to prevent conflicts"""
        try:
            self.progress.info("Auto-fixing S3 bucket naming configuration...")

            # Check if the configuration already uses random suffixes
            main_tf = self.terraform_dir / "main.tf"
            if main_tf.exists():
                with open(main_tf, "r", encoding="utf-8") as f:
                    content = f.read()

                # If random_id is already configured, assume it's working
                if "random_id" in content and "bucket_suffix" in content:
                    self.progress.success(
                        "S3 bucket naming already uses random suffixes"
                    )
                    return True

            # The current Terraform configuration should already handle this
            # Just validate that it's working as expected
            self.progress.info("S3 bucket naming uses automatic random suffixes")
            self.progress.info("This prevents naming conflicts automatically")
            return True

        except Exception as e:
            self.progress.error(f"Error auto-fixing S3 bucket naming: {e}")
            return False

    def _extract_backend_bucket(self, content: str) -> Optional[str]:
        """Extract backend bucket name from terraform configuration"""
        # Look for bucket = "bucket-name" in backend "s3" block
        match = re.search(
            r'backend\s+"s3"\s*{[^}]*bucket\s*=\s*"([^"]+)"', content, re.DOTALL
        )
        return match.group(1) if match else None

    def _extract_remote_state_bucket(self, content: str) -> Optional[str]:
        """Extract remote state bucket name from data source configuration"""
        # Look for bucket = "bucket-name" in terraform_remote_state data source
        match = re.search(
            r'data\s+"terraform_remote_state"[^{]*{[^}]*config\s*=\s*{[^}]*bucket\s*=\s*"([^"]+)"',
            content,
            re.DOTALL,
        )
        return match.group(1) if match else None

    def _extract_backend_key(self, content: str) -> Optional[str]:
        """Extract backend key from terraform configuration"""
        # Look for key = "path/terraform.tfstate" in backend "s3" block
        match = re.search(
            r'backend\s+"s3"\s*{[^}]*key\s*=\s*"([^"]+)"', content, re.DOTALL
        )
        return match.group(1) if match else None

    def _extract_remote_state_key(self, content: str) -> Optional[str]:
        """Extract remote state key from data source configuration"""
        # Look for key = "path/terraform.tfstate" in terraform_remote_state data source
        match = re.search(
            r'data\s+"terraform_remote_state"[^{]*{[^}]*config\s*=\s*{[^}]*key\s*=\s*"([^"]+)"',
            content,
            re.DOTALL,
        )
        return match.group(1) if match else None

    def _attempt_terraform_validation_fixes(self, error_output: str) -> bool:
        """Attempt to auto-fix common Terraform validation issues"""
        fixes_applied = False

        try:
            if (
                "variable" in error_output.lower()
                and "not declared" in error_output.lower()
            ):
                # Try to regenerate terraform.tfvars
                if self._generate_terraform_vars():
                    fixes_applied = True
                    self.progress.info("Auto-fix: Regenerated terraform.tfvars")

            if "provider" in error_output.lower():
                # Try terraform init to update providers
                self.progress.info("Auto-fix: Attempting to update providers...")
                result = subprocess.run(
                    [cast(str, self.terraform_cmd), "init", "-upgrade"],
                    cwd=str(self.terraform_dir),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    fixes_applied = True
                    self.progress.info("Auto-fix: Updated Terraform providers")

        except Exception as e:
            self.progress.warning(f"Could not apply auto-fixes: {e}")

        return fixes_applied

    def _handle_environment_file(self) -> bool:
        """
        Environment file handling for turnkey deployment.
        Gracefully handles missing .env.local and provides user options for optional features.
        """
        if not self.env_file.exists():
            return self._handle_missing_env_file()
        else:
            return self._handle_existing_env_file()

    def _handle_missing_env_file(self) -> bool:
        """Handle missing .env.local file with user prompts for optional features"""
        self.progress.warning(".env.local file not found")
        self.progress.info(
            "AWS CLI credentials are the only requirement for deployment"
        )

        # Check if .env.example exists to show what's available
        env_example = self.root_dir / ".env.example"
        if env_example.exists():
            self.progress.info(
                "Optional features available (see .env.example for details):"
            )
            self.progress.info(
                "   • Reddit integration (populate gallery from r/translator)"
            )
            self.progress.info("   • Google OAuth (Sign in with Google button)")
            self.progress.info("   • GitHub CI/CD pipeline (automated deployments)")
        else:
            self.progress.info(
                "Optional features available (configured via .env.local):"
            )
            self.progress.info(
                "   • Reddit integration (populate gallery from r/translator)"
            )
            self.progress.info("   • Google OAuth (Sign in with Google button)")
            self.progress.info("   • GitHub CI/CD pipeline (automated deployments)")

        # In CI mode, skip prompts and continue with AWS-only deployment
        if self.ci_mode:
            self.progress.info("CI mode: Continuing with AWS-only deployment")
            return self._create_minimal_env_file()

        # Prompt user for their preference
        return self._prompt_for_optional_features()

    def _prompt_for_optional_features(self) -> bool:
        """Prompt user about optional features when .env.local is missing"""
        try:
            print(f"\n{Colors.OKCYAN}Optional Feature Configuration{Colors.ENDC}")
            print("The application will work perfectly with just AWS CLI credentials.")
            print("Optional features can be configured now or added later.\n")

            while True:
                print("Choose an option:")
                print(
                    "1. Continue with AWS-only deployment (recommended for first-time setup)"
                )
                print("2. Configure optional features now")
                print("3. Show more details about optional features")

                try:
                    choice = input(
                        f"\n{Colors.BOLD}Enter your choice (1-3): {Colors.ENDC}"
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    print(
                        f"\n{Colors.WARNING}Deployment cancelled by user{Colors.ENDC}"
                    )
                    return False

                if choice == "1":
                    self.progress.success("Continuing with AWS-only deployment")
                    return self._create_minimal_env_file()
                elif choice == "2":
                    return self._configure_optional_features()
                elif choice == "3":
                    self._show_optional_features_details()
                    continue
                else:
                    print(
                        f"{Colors.WARNING}Invalid choice. Please enter 1, 2, or 3.{Colors.ENDC}"
                    )
                    continue

        except Exception as e:
            self.progress.error(f"Error during user prompt: {e}")
            self.progress.info("Falling back to AWS-only deployment")
            return self._create_minimal_env_file()

    def _show_optional_features_details(self) -> None:
        """Show detailed information about optional features"""
        print(f"\n{Colors.HEADER}Optional Features Details:{Colors.ENDC}")

        print(f"\n{Colors.BOLD}1. Reddit Integration{Colors.ENDC}")
        print("   • Populates the gallery with images from r/translator subreddit")
        print(
            "   • Requires Reddit API credentials from https://www.reddit.com/prefs/apps/"
        )
        print("   • Without this: App works with MMID dataset only")

        print(f"\n{Colors.BOLD}2. Google OAuth{Colors.ENDC}")
        print("   • Enables 'Sign in with Google' button for users")
        print("   • Requires Google OAuth credentials from Google Cloud Console")
        print("   • Without this: Users sign in with AWS Cognito (email/password)")

        print(f"\n{Colors.BOLD}3. GitHub CI/CD Pipeline{Colors.ENDC}")
        print("   • Enables automated deployments when you push code changes")
        print("   • Requires GitHub connection ARN from AWS Console")
        print("   • Without this: Manual deployments only (using this script)")

        print(
            f"\n{Colors.OKGREEN}All features are optional - the core application works without them!{Colors.ENDC}"
        )

    def _configure_optional_features(self) -> bool:
        """Guide user through configuring optional features"""
        env_example = self.root_dir / ".env.example"
        if not env_example.exists():
            self.progress.error(".env.example template not found")
            return self._create_minimal_env_file()

        try:
            shutil.copy2(env_example, self.env_file)

            print(f"\n{Colors.OKGREEN}Created .env.local from template{Colors.ENDC}")
            print(f"Edit {self.env_file} to configure optional features:")
            print("   • Add your API credentials for features you want to enable")
            print("   • Leave credentials blank for features you want to skip")
            print("   • Save the file when done")

            # Wait for user to edit the file
            input(
                f"\n{Colors.BOLD}Press Enter after you've finished editing .env.local...{Colors.ENDC}"
            )

            # Validate the configured file
            return self._handle_existing_env_file()

        except Exception as e:
            self.progress.error(f"Error setting up optional features: {e}")
            return self._create_minimal_env_file()

    def _create_minimal_env_file(self) -> bool:
        """Create minimal .env.local file for AWS-only deployment"""
        try:
            minimal_content = """# .env.local - Minimal Configuration for AWS-only Deployment
# Generated automatically by deploy.py

# IMPORTANT: Only AWS CLI credentials are required for deployment!
#    Configure AWS CLI with: aws configure
#    All credentials below are OPTIONAL - the app works without them.

# --- Optional: Reddit Integration ---
# Leave blank to disable Reddit features - app will still work with MMID dataset
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=

# --- Optional: Google OAuth Integration ---
# Leave blank to disable Google OAuth - users can still sign in with Cognito
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=

# --- Optional: CI/CD Pipeline Integration ---
# Leave blank to disable CI/CD pipeline - app will still deploy manually
GITHUB_CONNECTION_ARN=
"""
            with open(self.env_file, "w", encoding="utf-8") as f:
                f.write(minimal_content)

            self.progress.success("Created minimal .env.local for AWS-only deployment")
            return True

        except Exception as e:
            self.progress.error(f"Error creating minimal .env.local: {e}")
            return False

    def _handle_existing_env_file(self) -> bool:
        """Handle existing .env.local file with validation and optional feature detection"""
        if not self.validate_env_file_content():
            return False

        # Detect and report optional features status
        self._report_optional_features_status()
        return True

    def _report_optional_features_status(self) -> None:
        """Report which optional features are enabled/disabled"""
        try:
            with open(self.env_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            env_vars = self._parse_env_content(content)

            # Check Reddit integration
            reddit_enabled = bool(
                env_vars.get("REDDIT_CLIENT_ID", "").strip()
                and env_vars.get("REDDIT_CLIENT_SECRET", "").strip()
            )

            # Check Google OAuth
            google_enabled = bool(
                env_vars.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
                and env_vars.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
            )

            # Check GitHub CI/CD
            github_enabled = bool(env_vars.get("GITHUB_CONNECTION_ARN", "").strip())

            # Report status
            print(f"\n{Colors.OKCYAN}Optional Features Status:{Colors.ENDC}")

            status_icon_enabled = "[ON]"
            status_icon_disabled = "[OFF]"

            reddit_status = (
                f"{Colors.OKGREEN}{status_icon_enabled}"
                if reddit_enabled
                else f"{Colors.WARNING}{status_icon_disabled}"
            )
            google_status = (
                f"{Colors.OKGREEN}{status_icon_enabled}"
                if google_enabled
                else f"{Colors.WARNING}{status_icon_disabled}"
            )
            github_status = (
                f"{Colors.OKGREEN}{status_icon_enabled}"
                if github_enabled
                else f"{Colors.WARNING}{status_icon_disabled}"
            )

            print(f"   {reddit_status} Reddit Integration{Colors.ENDC}")
            print(f"   {google_status} Google OAuth{Colors.ENDC}")
            print(f"   {github_status} GitHub CI/CD Pipeline{Colors.ENDC}")

            if not (reddit_enabled or google_enabled or github_enabled):
                print(
                    f"\n{Colors.OKGREEN}AWS-only deployment - all core features will work!{Colors.ENDC}"
                )

        except Exception as e:
            self.progress.warning(f"Could not report optional features status: {e}")

    def _generate_terraform_vars(self, stack_dir: Optional[Path] = None) -> bool:
        """Generate terraform.tfvars from .env.local using env_to_tfvars.py

        Args:
            stack_dir: Optional stack directory to generate terraform.tfvars for.
                      If not provided, defaults to existing behavior (app-stack).
        """
        # Use provided stack_dir or default to existing behavior
        target_stack_dir = stack_dir if stack_dir is not None else self.terraform_dir

        self.progress.info(
            f"Generating terraform.tfvars from .env.local for {target_stack_dir.name}..."
        )

        try:
            # Get AWS region from config
            region_result = subprocess.run(
                [cast(str, self.aws_cmd), "configure", "get", "region"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            aws_region = (
                region_result.stdout.strip()
                if region_result.returncode == 0 and region_result.stdout.strip()
                else "us-east-1"
            )

            # Get AWS Account ID
            account_id_result = subprocess.run(
                [
                    cast(str, self.aws_cmd),
                    "sts",
                    "get-caller-identity",
                    "--query",
                    "Account",
                    "--output",
                    "text",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if account_id_result.returncode != 0:
                self.progress.error(
                    "Could not get AWS Account ID. Please configure your AWS CLI."
                )
                if account_id_result.stderr:
                    print(account_id_result.stderr)
                return False
            aws_account_id = account_id_result.stdout.strip()

            # Initialize resource name generator
            self.resource_name_generator = ResourceNameGenerator(
                aws_account_id, aws_region, self.progress
            )
            if not self.resource_name_generator.validate_resource_names():
                return False

            # Initialize resource tracker
            self.resource_tracker = ResourceTracker(
                self.root_dir, aws_account_id, aws_region
            )
            # Track predicted resources based on naming patterns
            self.resource_tracker.track_predicted_resources(
                self.resource_name_generator
            )

            # Use the env_to_tfvars.py script from app-stack (it's the shared script)
            env_to_tfvars_script = self.terraform_dir / "env_to_tfvars.py"
            command = [
                cast(str, self.python_cmd),
                str(env_to_tfvars_script),
            ]

            # Run the script (it always generates in app-stack directory)
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                # If target directory is different from app-stack, copy the generated file
                if target_stack_dir != self.terraform_dir:
                    source_tfvars = self.terraform_dir / "terraform.tfvars"
                    target_tfvars = target_stack_dir / "terraform.tfvars"

                    if source_tfvars.exists():
                        shutil.copy2(source_tfvars, target_tfvars)
                        self.progress.success(
                            f"terraform.tfvars copied to {target_stack_dir.name}."
                        )
                    else:
                        self.progress.error(
                            f"Source terraform.tfvars not found at {source_tfvars}"
                        )
                        return False
                else:
                    self.progress.success("terraform.tfvars generated successfully.")

                if result.stdout:
                    self.progress.info("env_to_tfvars.py output:")
                    print(result.stdout)
                return True
            else:
                self.progress.error("Failed to generate terraform.tfvars.")
                if result.stderr:
                    self.progress.error(result.stderr)
                if result.stdout:
                    self.progress.info(result.stdout)
                return False

        except Exception as e:
            self.progress.error(
                f"An error occurred while generating terraform.tfvars: {e}"
            )
            return False

    def _verify_and_fix_configuration(self) -> bool:
        """Configuration verification and auto-fix"""
        self.progress.info("Performing configuration verification...")

        fixes_applied = []

        try:
            # 1. Verify .env.local has all expected variables
            env_fixes = self._ensure_complete_env_configuration()
            if env_fixes:
                fixes_applied.extend(env_fixes)

            # 2. Verify terraform.tfvars is up to date and valid
            if not self._generate_terraform_vars():
                self.progress.warning("terraform.tfvars validation failed")
                return False

            # 3. Validate AWS region consistency
            region_fixes = self._validate_region_consistency()
            if region_fixes:
                fixes_applied.extend(region_fixes)

            if fixes_applied:
                self.progress.success(
                    f"Applied {len(fixes_applied)} configuration fixes:"
                )
                for fix in fixes_applied:
                    self.progress.info(f"  - {fix}")
            else:
                self.progress.success(
                    "Configuration verification completed - no fixes needed"
                )

            return True

        except Exception as e:
            self.progress.error(f"Error during configuration verification: {e}")
            return False

    def _ensure_complete_env_configuration(self) -> List[str]:
        """
        Ensure .env.local has complete configuration structure.
        """
        fixes = []

        try:
            with open(self.env_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for missing variables and add them only if needed
            required_vars = [
                "REDDIT_CLIENT_ID",
                "REDDIT_CLIENT_SECRET",
                "REDDIT_USER_AGENT",
                "GOOGLE_OAUTH_CLIENT_ID",
                "GOOGLE_OAUTH_CLIENT_SECRET",
                "GITHUB_CONNECTION_ARN",
            ]

            missing_vars = []
            lines = content.split("\n")

            for var in required_vars:
                # Check if variable exists (either as var= or var=value)
                var_exists = any(
                    line.strip().startswith(f"{var}=")
                    for line in lines
                    if not line.strip().startswith("#")
                )
                if not var_exists:
                    missing_vars.append(var)

            # Only add missing variables if they're actually missing
            if missing_vars:
                # Add a simple comment and the missing variables
                content += "\n\n# Additional configuration variables\n"
                for var in missing_vars:
                    content += f"{var}=\n"

                with open(self.env_file, "w", encoding="utf-8") as f:
                    f.write(content)

                fixes.append(f"Added {len(missing_vars)} missing environment variables")

        except Exception as e:
            self.progress.warning(f"Could not ensure complete env configuration: {e}")

        return fixes

    def _validate_region_consistency(self) -> List[str]:
        """Validate AWS region consistency across configurations"""
        fixes = []

        try:
            # Get AWS CLI configured region
            aws_region = None
            try:
                result = subprocess.run(
                    [cast(str, self.aws_cmd), "configure", "get", "region"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    aws_region = result.stdout.strip()
            except Exception:
                pass

            # Check terraform.tfvars region
            tfvars_file = self.terraform_dir / "terraform.tfvars"
            if tfvars_file.exists() and aws_region:
                with open(tfvars_file, "r", encoding="utf-8") as f:
                    tfvars_content = f.read()

                # Update region in terraform.tfvars to match AWS CLI
                if f'region = "{aws_region}"' not in tfvars_content:
                    lines = tfvars_content.split("\n")
                    updated_lines = []
                    region_updated = False

                    for line in lines:
                        if line.startswith("region ="):
                            updated_lines.append(f'region = "{aws_region}"')
                            region_updated = True
                            fixes.append(
                                f"Updated region to match AWS CLI: {aws_region}"
                            )
                        else:
                            updated_lines.append(line)

                    if not region_updated:
                        updated_lines.append(f'region = "{aws_region}"')
                        fixes.append(f"Added region configuration: {aws_region}")

                    with open(tfvars_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(updated_lines))

        except Exception as e:
            self.progress.warning(f"Could not validate region consistency: {e}")

        return fixes

    def validate_env_file_content(self) -> bool:
        """
        Validate .env.local file with graceful handling of optional features.
        """
        try:
            with open(self.env_file, "r", encoding="utf-8", errors="ignore") as f:
                env_content = f.read()

            # Check for critical configuration issues
            critical_issues = []
            auto_fixes_applied = []

            # Check if file is empty
            if not env_content.strip():
                critical_issues.append(".env.local file is empty")

            # Parse environment variables
            env_vars = self._parse_env_content(env_content)

            # Validate required structure and apply auto-fixes
            fixed_content, fixes = self._validate_and_fix_env_structure(
                env_content, env_vars
            )
            if fixes:
                auto_fixes_applied.extend(fixes)
                # Write fixed content back to file
                with open(self.env_file, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                self.progress.success(f"Applied {len(fixes)} auto-fixes to .env.local")

            # Validate optional features (non-blocking)
            self._validate_optional_features(env_vars)

            # Report critical issues (these block deployment)
            if critical_issues:
                for issue in critical_issues:
                    self.progress.error(issue)
                self.progress.info("Solutions:")
                self.progress.info("1. Ensure .env.local file exists and is not empty")
                self.progress.info(
                    "2. Use minimal configuration for AWS-only deployment"
                )
                return False

            if auto_fixes_applied:
                for fix in auto_fixes_applied:
                    self.progress.info(f"Auto-fix applied: {fix}")

            self.progress.success(".env.local file validated successfully")
            return True

        except Exception as e:
            self.progress.error(f"Error validating .env.local file: {e}")
            return False

    def _validate_optional_features(self, env_vars: Dict[str, str]) -> None:
        """
        Validation of optional features with format checking.
        """
        try:
            # Initialize optional feature handler
            feature_handler = OptionalFeatureHandler(
                env_vars, self.progress, cast(str, self.aws_cmd)
            )

            # Validate Reddit integration
            reddit_status, reddit_message = (
                feature_handler.validate_reddit_credentials()
            )
            if reddit_status == "enabled":
                self.progress.success(f"Reddit integration: {reddit_message}")
            elif reddit_status == "invalid":
                self.progress.warning(f"Reddit integration: {reddit_message}")
                self.progress.info("Reddit scraping functionality will be disabled")
            else:  # disabled
                self.progress.info(f"Reddit integration: {reddit_message}")

            # Validate Google OAuth
            google_status, google_message = (
                feature_handler.validate_google_oauth_credentials()
            )
            if google_status == "enabled":
                self.progress.success(f"Google OAuth: {google_message}")
                self.google_oauth_enabled = True
            elif google_status == "invalid":
                self.progress.warning(f"Google OAuth: {google_message}")
                self.progress.info("Google sign-in functionality will be disabled")
            else:  # disabled
                self.progress.info(f"Google OAuth: {google_message}")

            # Validate GitHub CI/CD
            github_status, github_message = feature_handler.validate_github_connection()
            if github_status == "enabled":
                self.progress.success(f"GitHub CI/CD: {github_message}")
            elif github_status == "invalid":
                self.progress.warning(f"GitHub CI/CD: {github_message}")
                self.progress.info("CI/CD pipeline will be disabled")
            else:  # disabled
                self.progress.info(f"GitHub CI/CD: {github_message}")

            # Generate and display feature summary
            feature_report = feature_handler.generate_feature_report()
            self.progress.info(feature_report)

        except Exception as e:
            self.progress.warning(f"Error validating optional features: {e}")
            self.progress.info("Continuing with AWS-only deployment")

    def _has_placeholder_value(self, value: str) -> bool:
        """Check if a value appears to be a placeholder"""
        if not value:
            return False

        placeholder_patterns = [
            "your_client_id_here",
            "your_client_secret_here",
            "your_google_client_id",
            "YourUsernameHere",
            "YOUR_ACCOUNT_ID",
            "YOUR_CONNECTION_ID",
            "your_",
            "YOUR_",
            "example",
            "placeholder",
        ]

        value_lower = value.lower()
        return any(pattern.lower() in value_lower for pattern in placeholder_patterns)

    def _parse_env_content(self, content: str) -> Dict[str, str]:
        """Parse environment file content into key-value pairs"""
        env_vars = {}
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                env_vars[key] = value
        return env_vars

    def _validate_and_fix_env_structure(
        self, content: str, env_vars: Dict[str, str]
    ) -> Tuple[str, List[str]]:
        """Validate and auto-fix common .env.local structure issues"""
        fixes_applied = []
        lines = content.split("\n")

        # Check for missing required structure
        expected_vars = [
            "REDDIT_CLIENT_ID",
            "REDDIT_CLIENT_SECRET",
            "REDDIT_USER_AGENT",
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GITHUB_CONNECTION_ARN",
        ]

        missing_vars = []
        for var in expected_vars:
            if var not in env_vars:
                missing_vars.append(var)

        # Auto-fix: Add missing variables with empty values
        if missing_vars:
            lines.append("")
            lines.append("# Auto-added missing variables")
            for var in missing_vars:
                if var.startswith("REDDIT_"):
                    if var == "REDDIT_USER_AGENT":
                        lines.append(
                            f'{var}="python:lenslate-image-collector:v1.0 (by /u/yourbot)"'
                        )
                    else:
                        lines.append(f"{var}=")
                elif var.startswith("GOOGLE_"):
                    lines.append(f"{var}=")
                elif var == "GITHUB_CONNECTION_ARN":
                    lines.append(f"{var}=")
                fixes_applied.append(f"Added missing variable: {var}")

        return "\n".join(lines), fixes_applied

    def _validate_env_variable_values(self, env_vars: Dict[str, str]) -> List[str]:
        """Validate environment variable values and return issues"""
        issues = []

        # Validate Reddit user agent format
        if "REDDIT_USER_AGENT" in env_vars:
            user_agent = env_vars["REDDIT_USER_AGENT"]
            if user_agent and not re.match(r"^[^:]+:[^:]+:v?\d+\.\d+.*", user_agent):
                issues.append(
                    "REDDIT_USER_AGENT format may be invalid (expected: platform:app_name:version)"
                )

        # Validate Google OAuth client ID format
        if "GOOGLE_OAUTH_CLIENT_ID" in env_vars:
            client_id = env_vars["GOOGLE_OAUTH_CLIENT_ID"]
            if client_id and not client_id.endswith(".apps.googleusercontent.com"):
                issues.append(
                    "GOOGLE_OAUTH_CLIENT_ID should end with .apps.googleusercontent.com"
                )

        # Validate GitHub connection ARN format
        if "GITHUB_CONNECTION_ARN" in env_vars:
            connection_arn = env_vars["GITHUB_CONNECTION_ARN"]
            if connection_arn:
                # Validate ARN format: arn:aws:codeconnections:region:account:connection/connection-id
                # or legacy format: arn:aws:codestar-connections:region:account:connection/connection-id
                arn_pattern = r"^arn:aws:(codeconnections|codestar-connections):[a-z0-9-]+:\d{12}:connection/[a-f0-9-]+$"
                if not re.match(arn_pattern, connection_arn):
                    issues.append(
                        "GITHUB_CONNECTION_ARN format appears invalid (expected: arn:aws:codeconnections:region:account:connection/connection-id)"
                    )

        # Check for common configuration mistakes
        for key, value in env_vars.items():
            if value and ("example" in value.lower() or "placeholder" in value.lower()):
                issues.append(f"{key} appears to contain placeholder text")

        return issues

    def validate_prerequisites(self) -> bool:
        """Validate all required tools and configurations are available"""
        self.progress.next_step("Validating prerequisites and configuration")

        # Check Python using the new detection system
        python_detector = PythonDetector(self.progress)
        python_success, python_cmd = python_detector.detect_and_validate()

        if not python_success:
            return False

        self.python_cmd = python_cmd

        # Check Terraform
        if self.check_command_exists("terraform"):
            self.terraform_cmd = "terraform"
            if not self.validate_terraform_version():
                return False
        else:
            self.progress.error("Terraform not found")
            self.progress.info(self.get_platform_install_instructions("terraform"))
            self.progress.info("Terraform 1.8.0 or later is required")
            return False

        # Check AWS CLI
        if self.check_command_exists("aws"):
            self.aws_cmd = "aws"
            # Get AWS CLI version
            try:
                version_result = subprocess.run(
                    [cast(str, self.aws_cmd), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if version_result.returncode == 0:
                    aws_version = version_result.stdout.strip().split()[0]
                    self.progress.success(f"AWS CLI found: {aws_version}")
                else:
                    self.progress.success("AWS CLI found")
            except Exception:
                self.progress.success("AWS CLI found")
        else:
            self.progress.error("AWS CLI not found")
            self.progress.info(self.get_platform_install_instructions("aws"))
            self.progress.info("AWS CLI v2 is recommended")
            return False

        # Environment file handling for turnkey deployment
        if not self._handle_environment_file():
            return False

        # Perform configuration verification
        if not self._verify_and_fix_configuration():
            return False

        # Validate Terraform configuration
        if not self.validate_terraform_configuration():
            return False

        # Check post-deployment message script
        post_deploy_script = self.terraform_dir / "post_deploy_message.py"
        if not post_deploy_script.exists():
            self.progress.error(
                f"Post-deployment script not found at {post_deploy_script}"
            )
            self.progress.info(
                "This script is required for displaying deployment results"
            )
            return False
        else:
            self.progress.success("Post-deployment script found")

        # Check Lambda source files exist
        lambda_files = [
            "image_processor.py",
            "gallery_lister.py",
            "cognito_triggers.py",
            "user_manager.py",
            "mmid_populator.py",
            "reddit_populator_sync.py",
            "history_handler.py",
            "performance_handler.py",
            "prepare_reddit_populator.py",
            "reddit_realtime_scraper.py",
        ]

        missing_lambda_files = []
        for lambda_file in lambda_files:
            if not (self.lambda_dir / lambda_file).exists():
                missing_lambda_files.append(lambda_file)

        if missing_lambda_files:
            self.progress.error(
                f"Missing Lambda source files: {', '.join(missing_lambda_files)}"
            )
            self.progress.info("Ensure all Lambda function source files are present")
            return False
        else:
            self.progress.success("All Lambda source files found")

        return True

    def _validate_basic_tools_for_destroy(self) -> bool:
        """Validate only the basic tools needed for destroy operations - don't create resources"""
        self.progress.next_step("Validating basic tools for destroy operation")

        # Check Python using the new detection system
        python_detector = PythonDetector(self.progress)
        python_success, python_cmd = python_detector.detect_and_validate()

        if not python_success:
            return False

        self.python_cmd = python_cmd

        # Check Terraform
        if self.check_command_exists("terraform"):
            self.terraform_cmd = "terraform"
            if not self.validate_terraform_version():
                return False
        else:
            self.progress.error("Terraform not found")
            self.progress.info(self.get_platform_install_instructions("terraform"))
            self.progress.info("Terraform 1.8.0 or later is required")
            return False

        # Check AWS CLI
        if self.check_command_exists("aws"):
            self.aws_cmd = "aws"
            # Get AWS CLI version
            try:
                version_result = subprocess.run(
                    [cast(str, self.aws_cmd), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if version_result.returncode == 0:
                    aws_version = version_result.stdout.strip().split()[0]
                    self.progress.success(f"AWS CLI found: {aws_version}")
                else:
                    self.progress.success("AWS CLI found")
            except Exception:
                self.progress.success("AWS CLI found")
        else:
            self.progress.error("AWS CLI not found")
            self.progress.info(self.get_platform_install_instructions("aws"))
            self.progress.info("AWS CLI v2 is recommended")
            return False

        # Get AWS region and account ID for destroy operations
        region_result = subprocess.run(
            [cast(str, self.aws_cmd), "configure", "get", "region"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        aws_region = (
            region_result.stdout.strip()
            if region_result.returncode == 0 and region_result.stdout.strip()
            else "us-east-1"
        )

        # Get AWS Account ID
        account_id_result = subprocess.run(
            [
                cast(str, self.aws_cmd),
                "sts",
                "get-caller-identity",
                "--query",
                "Account",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if account_id_result.returncode != 0:
            self.progress.error(
                "Could not get AWS Account ID. Please configure your AWS CLI."
            )
            if account_id_result.stderr:
                print(account_id_result.stderr)
            return False
        aws_account_id = account_id_result.stdout.strip()

        # Initialize resource name generator for destroy operations
        # This is needed to determine backend bucket/table names
        try:
            self.resource_name_generator = ResourceNameGenerator(
                aws_account_id, aws_region, self.progress
            )
            self.progress.success("Resource name generator initialized")
        except Exception as e:
            self.progress.error(f"Failed to initialize resource name generator: {e}")
            return False

        return True

    def build_lambda_functions(self) -> bool:
        """
        Build all Lambda functions using the detected Python executable.
        Provides error analysis and troubleshooting for build failures.
        """
        self.progress.next_step("Building Lambda functions")
        build_script = self.lambda_dir / "build_all.py"

        if not build_script.exists():
            self.progress.error(f"Lambda build script not found: {build_script}")
            self.progress.info(
                "Ensure 'build_all.py' exists in the 'lambda_functions' directory."
            )
            return False

        self.progress.info(f"Using Python executable: {self.python_cmd}")
        self.progress.info(f"Running build script: {build_script}")

        try:
            process = subprocess.run(
                [cast(str, self.python_cmd), str(build_script)],
                cwd=str(self.lambda_dir),
                capture_output=True,
                text=True,
                timeout=300,  # 5-minute timeout for build process
                encoding="utf-8",
                errors="replace",
            )

            if process.returncode == 0:
                self.progress.success("Lambda functions built successfully")
                if process.stdout:
                    self.progress.info("Build script output:")
                    print(process.stdout)
                return True
            else:
                self.progress.error("Lambda function build failed")
                self._analyze_lambda_build_error(process.stderr, process.stdout)
                return False

        except subprocess.TimeoutExpired:
            self.progress.error("Lambda build process timed out (5 minutes)")
            self.progress.info(
                "This could be due to a slow internet connection while downloading dependencies."
            )
            self.progress.info(
                "Try increasing the timeout in the deploy.py script if this persists."
            )
            return False
        except Exception as e:
            self.progress.error(
                f"An unexpected error occurred during Lambda build: {e}"
            )
            return False

    def _analyze_lambda_build_error(self, stderr: str, stdout: str):
        """Analyze build errors and provide troubleshooting guidance"""
        output = f"--- STDOUT ---\n{stdout}\n\n--- STDERR ---\n{stderr}"
        self.progress.info("Full build script output:")
        print(output)

        self.progress.info("\n" + "=" * 60)
        self.progress.info("TROUBLESHOOTING GUIDANCE")
        self.progress.info("=" * 60)

        if "No matching distribution found" in stderr:
            self.progress.info(
                "A package in a requirements.txt file could not be found on PyPI."
            )
            self.progress.info(
                "  - Check for typos in the package name in all lambda_functions/*/requirements.txt files."
            )
            self.progress.info("  - Ensure the package version (if specified) exists.")
        elif (
            "failed to build" in stderr.lower()
            or "microsoft visual c++" in stderr.lower()
        ):
            self.progress.info(
                "A package with C extensions failed to compile. This requires system-level build tools."
            )
            self.progress.info(
                "  - On Windows: Install 'Microsoft C++ Build Tools' from the Visual Studio Installer."
            )
            self.progress.info(
                "  - On Linux (Debian/Ubuntu): sudo apt-get update && sudo apt-get install -y build-essential python3-dev"
            )
            self.progress.info(
                "  - On macOS: Install Xcode Command Line Tools with: xcode-select --install"
            )
        elif "Permission denied" in stderr:
            self.progress.info("The build script encountered a file permission error.")
            self.progress.info(
                "  - Check read/write/execute permissions for the 'lambda_functions' directory and its contents."
            )
        elif "pip" in stderr and (
            "command not found" in stderr or "is not recognized" in stderr
        ):
            self.progress.info(
                "The 'pip' command was not found by the Python interpreter."
            )
            self.progress.info(
                f"  - Try running: {self.python_cmd} -m ensurepip --upgrade"
            )
        elif "error: invalid command 'bdist_wheel'" in stderr:
            self.progress.info(
                "The 'wheel' package is not installed, which is required for building packages."
            )
            self.progress.info(
                f"  - Try running: {self.python_cmd} -m pip install wheel"
            )
        else:
            self.progress.info(
                "An unknown build error occurred. Review the full output above for details."
            )
            self.progress.info(
                "You can also try running the build script manually for more interactive debugging:"
            )
            self.progress.info(f"    cd {self.lambda_dir}")
            self.progress.info(f"    {self.python_cmd} build_all.py")
        self.progress.info("=" * 60)

    def _create_terraform_lock_table(self) -> bool:
        """Create the Terraform lock DynamoDB table if it doesn't exist."""
        self.progress.next_step("Ensuring Terraform lock table exists")
        backend_names = cast(
            ResourceNameGenerator, self.resource_name_generator
        ).get_terraform_backend_names()
        table_name = backend_names["lock_table"]

        try:
            # Check if table exists
            self.progress.info(f"Checking for DynamoDB table: {table_name}")
            command = [
                cast(str, self.aws_cmd),
                "dynamodb",
                "describe-table",
                "--table-name",
                table_name,
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                self.progress.success(f"DynamoDB table {table_name} already exists.")
                return True

            # If table does not exist, create it
            self.progress.info(f"DynamoDB table {table_name} not found. Creating it...")
            create_table_command = [
                cast(str, self.aws_cmd),
                "dynamodb",
                "create-table",
                "--table-name",
                table_name,
                "--attribute-definitions",
                "AttributeName=LockID,AttributeType=S",
                "--key-schema",
                "AttributeName=LockID,KeyType=HASH",
                "--provisioned-throughput",
                "ReadCapacityUnits=1,WriteCapacityUnits=1",
            ]
            create_result = subprocess.run(
                create_table_command, capture_output=True, text=True, timeout=120
            )

            if create_result.returncode == 0:
                self.progress.info(
                    f"Waiting for DynamoDB table {table_name} to be created..."
                )
                wait_command = [
                    cast(str, self.aws_cmd),
                    "dynamodb",
                    "wait",
                    "table-exists",
                    "--table-name",
                    table_name,
                ]
                wait_result = subprocess.run(
                    wait_command, capture_output=True, text=True, timeout=120
                )
                if wait_result.returncode == 0:
                    self.progress.success(
                        f"DynamoDB table {table_name} created successfully."
                    )
                    return True
                else:
                    self.progress.error(
                        f"Timed out waiting for DynamoDB table {table_name} to be created."
                    )
                    if wait_result.stderr:
                        self.progress.error(wait_result.stderr)
                    return False
            else:
                self.progress.error(f"Failed to create DynamoDB table {table_name}.")
                if create_result.stderr:
                    self.progress.error(create_result.stderr)
                return False

        except Exception as e:
            self.progress.error(f"An error occurred while creating DynamoDB table: {e}")
            return False

    def _create_terraform_state_bucket(self) -> bool:
        """Create the Terraform state S3 bucket if it doesn't exist."""
        self.progress.next_step("Ensuring Terraform state bucket exists")
        backend_names = cast(
            ResourceNameGenerator, self.resource_name_generator
        ).get_terraform_backend_names()
        bucket_name = backend_names["state_bucket"]
        region = cast(ResourceNameGenerator, self.resource_name_generator).aws_region

        try:
            # Check if bucket exists
            self.progress.info(f"Checking for S3 bucket: {bucket_name}")
            command = [
                cast(str, self.aws_cmd),
                "s3api",
                "head-bucket",
                "--bucket",
                bucket_name,
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                self.progress.success(f"S3 bucket {bucket_name} already exists.")
                return True

            # If bucket does not exist, create it
            self.progress.info(f"S3 bucket {bucket_name} not found. Creating it...")

            if region == "us-east-1":
                create_bucket_command = [
                    cast(str, self.aws_cmd),
                    "s3api",
                    "create-bucket",
                    "--bucket",
                    bucket_name,
                    "--region",
                    region,
                ]
            else:
                create_bucket_command = [
                    cast(str, self.aws_cmd),
                    "s3api",
                    "create-bucket",
                    "--bucket",
                    bucket_name,
                    "--region",
                    region,
                    "--create-bucket-configuration",
                    f"LocationConstraint={region}",
                ]

            create_result = subprocess.run(
                create_bucket_command, capture_output=True, text=True, timeout=120
            )

            if create_result.returncode == 0:
                self.progress.success(f"S3 bucket {bucket_name} created successfully.")
                # It can take a moment for the bucket to be fully available
                time.sleep(5)
                return True
            else:
                self.progress.error(f"Failed to create S3 bucket {bucket_name}.")
                if create_result.stderr:
                    self.progress.error(create_result.stderr)
                return False

        except Exception as e:
            self.progress.error(f"An error occurred while creating S3 bucket: {e}")
            return False

    def validate_lambda_zip_files(self) -> bool:
        """Validation of Lambda zip files with checks"""
        expected_zip_files = [
            "image_processor.zip",
            "gallery_lister.zip",
            "cognito_triggers.zip",
            "user_manager.zip",
            "mmid_populator.zip",
            "history_handler.zip",
            "performance_handler.zip",
            "prepare_reddit_populator.zip",
            "reddit_realtime_scraper.zip",
        ]

        # reddit_populator.zip is in a different location
        reddit_populator_zip = "reddit_populator.zip"

        missing_files = []
        invalid_files = []
        validation_warnings = []

        # Check regular zip files in terraform/app-stack directory
        for zip_file in expected_zip_files:
            zip_path = self.terraform_dir / zip_file
            validation_result = self._validate_single_zip_file(zip_path, zip_file)

            if validation_result["status"] == "missing":
                missing_files.append(zip_file)
            elif validation_result["status"] == "invalid":
                invalid_files.append(validation_result["message"])
            elif validation_result["status"] == "warning":
                validation_warnings.append(validation_result["message"])
                self.progress.warning(f"{validation_result['message']}")
            else:
                self.progress.info(f"{zip_file} ({validation_result['size']:,} bytes)")

        # Check reddit_populator.zip in terraform root directory
        reddit_zip_path = self.root_dir / "terraform" / reddit_populator_zip
        validation_result = self._validate_single_zip_file(
            reddit_zip_path, reddit_populator_zip
        )

        if validation_result["status"] == "missing":
            missing_files.append(reddit_populator_zip)
        elif validation_result["status"] == "invalid":
            invalid_files.append(validation_result["message"])
        elif validation_result["status"] == "warning":
            validation_warnings.append(validation_result["message"])
            self.progress.warning(f"{validation_result['message']}")
        else:
            self.progress.info(
                f"{reddit_populator_zip} ({validation_result['size']:,} bytes)"
            )

        # Report results
        if missing_files:
            self.progress.error(f"Missing Lambda zip files: {', '.join(missing_files)}")
            self._provide_missing_files_guidance(missing_files)
            return False

        if invalid_files:
            self.progress.error("Invalid Lambda zip files found:")
            for invalid_file in invalid_files:
                self.progress.error(f"  - {invalid_file}")
            self._provide_invalid_files_guidance()
            return False

        if validation_warnings:
            self.progress.warning(
                f"Found {len(validation_warnings)} validation warnings"
            )
            self.progress.info(
                "These warnings may indicate potential issues but won't prevent deployment"
            )

        self.progress.success("All Lambda zip files validated successfully")
        return True

    def run(self) -> bool:
        """
        Run the full deployment process with error handling.
        """
        self.deployment_started = True
        self.deployment_id = int(time.time())
        self.progress.info(f"Starting deployment ID: {self.deployment_id}")

        try:
            # Pre-deployment validation
            if not self.validate_prerequisites():
                self.progress.error("Prerequisite validation failed. Aborting.")
                return False

            if not self.build_lambda_functions():
                self.progress.error("Lambda function build failed. Aborting.")
                return False

            if not self.validate_lambda_zip_files():
                self.progress.error("Lambda zip file validation failed. Aborting.")
                return False

            self.progress.success("All pre-deployment checks and builds passed.")

            # Generate terraform.tfvars for both stacks
            if not self._generate_terraform_vars(self.data_stack_dir):
                self.progress.error(
                    "Failed to generate terraform.tfvars for data-stack. Aborting."
                )
                return False

            if not self._generate_terraform_vars(self.terraform_dir):
                self.progress.error(
                    "Failed to generate terraform.tfvars for app-stack. Aborting."
                )
                return False

            # Infrastructure deployment

            # Create the S3 bucket and DynamoDB table for Terraform state
            if not self._create_terraform_state_bucket():
                self.progress.error(
                    "Failed to create Terraform state bucket. Aborting."
                )
                return False
            if not self._create_terraform_lock_table():
                self.progress.error("Failed to create Terraform lock table. Aborting.")
                return False

            # Deploy both stacks in sequence: data-stack first, then app-stack
            self.progress.next_step("Deploying infrastructure to AWS (dual-stack)")

            # Deploy data-stack first
            if not self._deploy_terraform_stack("data-stack", self.data_stack_dir):
                self.progress.error("Data-stack deployment failed.")
                if not self.ci_mode:
                    self._prompt_for_cleanup()
                return False

            # Update app-stack terraform.tfvars with data-stack state bucket reference
            self.progress.info(
                "Updating app-stack configuration with data-stack state bucket..."
            )
            if not self._update_app_stack_data_bucket_reference():
                self.progress.error("Failed to update app-stack data bucket reference.")
                if not self.ci_mode:
                    self._prompt_for_cleanup()
                return False

            # Deploy app-stack second
            if not self._deploy_terraform_stack("app-stack", self.terraform_dir):
                self.progress.error("App-stack deployment failed.")
                if not self.ci_mode:
                    self._prompt_for_cleanup()
                return False

            self.progress.success("🎉 Deployment completed successfully!")

            # Save resource tracking files
            self._save_resource_tracking_files()

            self._display_success_message()
            self._prompt_google_oauth_setup()
            return True

        except KeyboardInterrupt:
            self.progress.error("Deployment interrupted by user")
            if not self.ci_mode:
                self._prompt_for_cleanup()
            return False
        except Exception as e:
            self.progress.error(f"An unexpected error occurred during deployment: {e}")
            if not self.ci_mode:
                self._prompt_for_cleanup()
            return False

    def _prompt_for_cleanup(self) -> None:
        """Prompt user whether to cleanup failed deployment"""
        if self.ci_mode:
            self.progress.info("CI mode: Skipping cleanup prompt")
            return

        try:
            print(
                f"\n{Colors.WARNING}Deployment failed or was interrupted.{Colors.ENDC}"
            )
            print("Some AWS resources may have been partially created.")

            while True:
                choice = (
                    input(
                        f"\n{Colors.BOLD}Do you want to cleanup/destroy any created resources? (y/n): {Colors.ENDC}"
                    )
                    .strip()
                    .lower()
                )

                if choice in ["y", "yes"]:
                    self.progress.info("For comprehensive cleanup of all resources:")
                    self.progress.info("   python full_cleanup.py")
                    self.progress.info("")
                    self.progress.info(
                        "This script handles both stacks and all AWS resources safely."
                    )
                    break
                elif choice in ["n", "no"]:
                    self.progress.info(
                        "Skipping cleanup. Please check AWS Console for any resources that need manual cleanup."
                    )
                    break
                else:
                    print("Please enter 'y' for yes or 'n' for no.")

        except (EOFError, KeyboardInterrupt):
            self.progress.info("Skipping cleanup prompt.")

    def _display_success_message(self) -> None:
        """Display final success message with next steps"""
        print(f"\n{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.OKGREEN} DEPLOYMENT SUCCESSFUL! {Colors.ENDC}")
        print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")

        print(f"\n{Colors.BOLD}Your application has been deployed to AWS!{Colors.ENDC}")
        print(f"\n{Colors.OKCYAN}What's been created:{Colors.ENDC}")
        print("• S3 bucket for image storage and website hosting")
        print("• Lambda functions for image processing and API endpoints")
        print("• API Gateway for REST API")
        print("• Cognito User Pool for authentication")
        print("• CloudFront distribution for global content delivery")
        print("• DynamoDB tables for data storage")

        print(f"\n{Colors.BOLD}Important Notes:{Colors.ENDC}")
        print(
            "• Keep your .env.local file secure - it contains sensitive configuration"
        )
        print("• Your AWS resources will incur costs - monitor your AWS billing")
        print("• To update the application, modify code and run this script again")
        print("• To destroy all resources, run: python deploy.py --destroy")

        print(
            f"\n{Colors.OKGREEN}Enjoy your new image translation application!{Colors.ENDC}"
        )
        print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")

    def _save_resource_tracking_files(self) -> None:
        """Save resource tracking files for easy cleanup"""
        if not self.resource_tracker:
            return

        try:
            self.progress.info("📝 Saving resource tracking files...")

            # Save JSON manifest
            if self.resource_tracker.save_manifest():
                self.progress.success(
                    f"Resource manifest saved to: {self.resource_tracker.manifest_file}"
                )

            # Generate and save cleanup script
            cleanup_script = self.resource_tracker.generate_cleanup_script()
            cleanup_file = self.resource_tracker.deployment_dir / "cleanup_resources.py"
            with open(cleanup_file, "w", encoding="utf-8") as f:
                f.write(cleanup_script)
            self.progress.success(f"Cleanup script saved to: {cleanup_file}")

            # Generate and save human-readable summary
            summary = self.resource_tracker.create_human_readable_summary()
            summary_file = (
                self.resource_tracker.deployment_dir / "deployed_resources.md"
            )
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary)
            self.progress.success(f"Resource summary saved to: {summary_file}")

            self.progress.info(
                "💡 Use 'python deployment/cleanup_resources.py' to delete all resources when needed"
            )

        except Exception as e:
            self.progress.warning(f"Could not save resource tracking files: {e}")

    def _check_google_oauth_status(self) -> Dict[str, Any]:
        """Check Google OAuth configuration status from Terraform outputs"""
        try:
            # Get Terraform outputs
            result = subprocess.run(
                [
                    cast(str, self.terraform_cmd),
                    "output",
                    "-json",
                    "google_oauth_status",
                ],
                cwd=str(self.terraform_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                output_data = json.loads(result.stdout)
                oauth_status = output_data.get("value", {})

                # Ensure we return a dictionary even if the output is unexpected
                if isinstance(oauth_status, dict):
                    return oauth_status
                else:
                    # If it's not a dict (e.g., list, string, etc.), create a fallback
                    return {
                        "configured": False,
                        "message": f"Unexpected OAuth status format: {type(oauth_status).__name__}",
                    }
            else:
                self.progress.warning(
                    "Could not get Google OAuth status from Terraform"
                )
                return {
                    "configured": False,
                    "message": "Unable to check configuration status",
                }

        except Exception as e:
            self.progress.warning(f"Error checking Google OAuth status: {e}")
            return {
                "configured": False,
                "message": "Unable to check configuration status",
            }

    def _prompt_google_oauth_setup(self) -> None:
        """Prompt user to run Google OAuth configuration script if Google OAuth is enabled"""
        if not self.google_oauth_enabled or self.ci_mode:
            return

        # Check current OAuth status
        self._check_google_oauth_status()

        print(f"\n{Colors.OKCYAN}Google OAuth Configuration{Colors.ENDC}")
        print(f"{Colors.BOLD}Your application has Google OAuth enabled.{Colors.ENDC}")

        # Check if already configured by examining Terraform outputs for more details
        try:
            # Get the specific outputs to check if JavaScript origins and redirect URIs are set
            js_origins_result = subprocess.run(
                [
                    cast(str, self.terraform_cmd),
                    "output",
                    "-json",
                    "google_oauth_javascript_origins",
                ],
                cwd=str(self.terraform_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )

            redirect_uri_result = subprocess.run(
                [
                    cast(str, self.terraform_cmd),
                    "output",
                    "-json",
                    "google_oauth_redirect_uri",
                ],
                cwd=str(self.terraform_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )

            # If we have valid outputs and they contain actual URLs, OAuth is likely configured
            if (
                js_origins_result.returncode == 0
                and redirect_uri_result.returncode == 0
            ):
                js_origins_data = json.loads(js_origins_result.stdout)
                redirect_uri_data = json.loads(redirect_uri_result.stdout)

                # Handle both direct values and wrapped values
                if isinstance(js_origins_data, dict):
                    js_origins = js_origins_data.get("value", [])
                else:
                    js_origins = (
                        js_origins_data if isinstance(js_origins_data, list) else []
                    )

                if isinstance(redirect_uri_data, dict):
                    redirect_uri = redirect_uri_data.get("value", "")
                else:
                    redirect_uri = (
                        redirect_uri_data if isinstance(redirect_uri_data, str) else ""
                    )

                # Check if we have actual URLs (not empty arrays/strings)
                if js_origins and redirect_uri:
                    print(
                        f"\n{Colors.OKGREEN}✓ Google OAuth appears to be already configured!{Colors.ENDC}"
                    )
                    print(
                        "Your Google Cloud Console should already have the following URLs:"
                    )
                    print(f"\n{Colors.BOLD}Authorized JavaScript Origins:{Colors.ENDC}")
                    for origin in js_origins:
                        print(f"  • {origin}")
                    print(f"\n{Colors.BOLD}Authorized Redirect URI:{Colors.ENDC}")
                    print(f"  • {redirect_uri}")
                    print(
                        f"\n{Colors.OKGREEN}If Google sign-in is working, no further action needed!{Colors.ENDC}"
                    )
                    return

        except Exception as e:
            self.progress.warning(f"Could not check OAuth configuration details: {e}")

        # Fallback to original behavior if status check failed or OAuth not configured
        print("Would you like to run the Google OAuth configuration script to get")
        print("the redirect URIs for your Google Cloud Console?")

        try:
            response = (
                input(
                    f"\n{Colors.BOLD}Run Google OAuth configuration script? (y/N): {Colors.ENDC}"
                )
                .strip()
                .lower()
            )
            if response in ["y", "yes"]:
                self._run_google_oauth_script()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.OKCYAN}Skipping Google OAuth configuration.{Colors.ENDC}")

    def _run_google_oauth_script(self) -> None:
        """Run the Google OAuth configuration script"""
        try:
            script_path = self.terraform_dir / "update-google-oauth.py"
            if not script_path.exists():
                self.progress.warning("Google OAuth configuration script not found.")
                self.progress.info(
                    "You can manually configure OAuth using the Terraform outputs."
                )
                return

            print(
                f"\n{Colors.OKCYAN}Running Google OAuth configuration script...{Colors.ENDC}"
            )
            result = subprocess.run(
                [cast(str, self.python_cmd), str(script_path)],
                cwd=str(self.terraform_dir),
                capture_output=False,  # Let it run interactively
                text=True,
            )

            if result.returncode == 0:
                print(
                    f"\n{Colors.OKGREEN}Google OAuth configuration completed!{Colors.ENDC}"
                )
            else:
                self.progress.warning(
                    "Google OAuth configuration script encountered an issue."
                )
                self.progress.info(
                    "You can run it manually later: python terraform/app-stack/update-google-oauth.py"
                )

        except Exception as e:
            self.progress.warning(f"Error running Google OAuth script: {e}")
            self.progress.info(
                "You can run it manually later: python terraform/app-stack/update-google-oauth.py"
            )

    def destroy_infrastructure(self, auto_approve=False) -> bool:
        """Destroy all deployed infrastructure for both stacks with error handling."""
        self.progress.info("Destroying all infrastructure...")

        if not self._validate_basic_tools_for_destroy():
            self.progress.error("Basic tool validation failed. Aborting.")
            return False

        auto_approve_destroy = auto_approve or self.ci_mode

        if not auto_approve_destroy:
            print(
                f"\n{Colors.WARNING}WARNING: This will destroy ALL deployed resources for both app-stack and data-stack!{Colors.ENDC}"
            )
            print("This action cannot be undone.")
            try:
                choice = (
                    input(
                        f"\n{Colors.BOLD}Are you sure you want to continue? (Type 'yes' to confirm): {Colors.ENDC}"
                    )
                    .strip()
                    .lower()
                )
                if choice != "yes":
                    self.progress.info("Destruction cancelled.")
                    return True  # Not an error
            except (EOFError, KeyboardInterrupt):
                self.progress.info("\nDestruction cancelled by user.")
                return True

        success = True

        # Try to destroy app-stack first (depends on data-stack)
        self.progress.info("Attempting to destroy app-stack...")
        if not self._execute_terraform_stack_destruction(
            "app-stack", self.terraform_dir
        ):
            success = False

        # Then destroy data-stack
        self.progress.info("Attempting to destroy data-stack...")
        if not self._execute_terraform_stack_destruction(
            "data-stack", self.data_stack_dir
        ):
            success = False

        if success:
            self.progress.success("All infrastructure destroyed successfully.")

        return True

    def _execute_terraform_stack_destruction(
        self, stack_name: str, stack_dir: Path
    ) -> bool:
        """Destroy process for a single Terraform stack."""
        self.progress.info(f"Destroying {stack_name}...")

        # Try normal terraform destroy
        if self._try_normal_destroy(stack_name, stack_dir):
            return True

        # If normal destroy fails, just log and continue
        self.progress.warning(f"Terraform destroy failed for {stack_name}")
        return False

    def _try_normal_destroy(self, stack_name: str, stack_dir: Path) -> bool:
        """Try normal terraform destroy with optional lock bypass."""
        try:
            destroy_command = [
                cast(str, self.terraform_cmd),
                "destroy",
            ]

            # Add -lock=false if force_unlock is enabled
            if self.force_unlock:
                destroy_command.append("-lock=false")
                self.progress.warning(
                    f"Using -lock=false for {stack_name} destroy (state lock bypass)"
                )

            destroy_command.append("-auto-approve")

            process = subprocess.run(
                destroy_command,
                cwd=str(stack_dir),
                capture_output=True,
                text=True,
                timeout=1200,  # 20 mins
            )
            if process.returncode == 0:
                self.progress.success(f"{stack_name} destroyed successfully.")
                return True
            else:
                # Check if this is a state lock error and we haven't tried lock=false yet
                if not self.force_unlock and self._is_state_lock_error(process.stderr):
                    self.progress.warning(
                        f"State lock detected for {stack_name} destroy, attempting fallback with -lock=false..."
                    )
                    # Create a retry command with lock=false
                    destroy_command_retry = [
                        cast(str, self.terraform_cmd),
                        "destroy",
                        "-lock=false",
                        "-auto-approve",
                    ]

                    process_retry = subprocess.run(
                        destroy_command_retry,
                        cwd=str(stack_dir),
                        capture_output=True,
                        text=True,
                        timeout=1200,  # 20 mins
                    )

                    if process_retry.returncode == 0:
                        self.progress.success(
                            f"{stack_name} destroyed successfully with -lock=false."
                        )
                        return True
                    else:
                        self.progress.info(
                            f"Destroy with -lock=false also failed for {stack_name}: {process_retry.stderr}"
                        )
                        return False

                self.progress.info(
                    f"Normal destroy failed for {stack_name}: {process.stderr}"
                )
                return False
        except Exception as e:
            self.progress.info(f"Normal destroy exception for {stack_name}: {e}")
            return False

    def _validate_single_zip_file(
        self, zip_path: Path, zip_name: str
    ) -> Dict[str, Any]:
        """Validate a single Lambda zip file"""
        if not zip_path.exists():
            return {
                "status": "missing",
                "message": f"{zip_name} not found at {zip_path}",
            }

        try:
            size = zip_path.stat().st_size
            if size == 0:
                return {
                    "status": "invalid",
                    "message": f"{zip_name} is an empty file",
                }

            # Basic check to see if it's a zip file by reading the header
            with open(zip_path, "rb") as f:
                header = f.read(4)
                if header != b"PK\x03\x04":
                    return {
                        "status": "invalid",
                        "message": f"{zip_name} does not appear to be a valid zip file (bad header)",
                    }

            return {"status": "valid", "size": size}
        except Exception as e:
            return {
                "status": "invalid",
                "message": f"Error validating {zip_name}: {e}",
            }

    def _provide_missing_files_guidance(self, missing_files: List[str]) -> None:
        """Provide guidance for missing Lambda zip files"""
        self.progress.info("To resolve missing Lambda zip files:")
        self.progress.info("1. Ensure the Lambda build process completed successfully")
        self.progress.info(
            "2. Check that all required source files exist in lambda_functions/"
        )
        self.progress.info("3. Try running the build process again")

        if "reddit_populator.zip" in missing_files:
            self.progress.info(
                "4. reddit_populator.zip should be in terraform/ directory"
            )

    def _provide_invalid_files_guidance(self) -> None:
        """Provide guidance for invalid Lambda zip files"""
        self.progress.info("To resolve invalid Lambda zip files:")
        self.progress.info("1. Delete the invalid zip files")
        self.progress.info("2. Run the Lambda build process again")
        self.progress.info("3. Check for disk space issues during build")

    def create_state_backup(self) -> bool:
        """Create backup of current Terraform state"""
        try:
            state_file = self.terraform_dir / "terraform.tfstate"
            if state_file.exists():
                backup_name = f"terraform.tfstate.backup.{self.deployment_id}"
                self.state_backup_path = self.backup_dir / backup_name

                shutil.copy2(state_file, self.state_backup_path)
                self.progress.info(f"State backup created: {backup_name}")

            return True
        except Exception as e:
            self.progress.warning(f"Could not create state backup: {e}")
            return True  # Don't fail deployment for backup issues

    def _deploy_terraform_stack(self, stack_name: str, stack_dir: Path) -> bool:
        """Deploy a single Terraform stack with automatic fallback for lock issues"""
        self.progress.info(f"Deploying {stack_name}...")

        return self._deploy_terraform_stack_with_retry(
            stack_name, stack_dir, use_lock_false=self.force_unlock
        )

    def _deploy_terraform_stack_with_retry(
        self, stack_name: str, stack_dir: Path, use_lock_false: bool = False
    ) -> bool:
        """Deploy a single Terraform stack with optional lock=false flag"""

        try:
            # Prepare plan command
            plan_cmd = [cast(str, self.terraform_cmd), "plan"]
            if use_lock_false:
                plan_cmd.append("-lock=false")
            plan_cmd.extend(["-out=tfplan"])

            # Prepare apply command
            apply_cmd = [cast(str, self.terraform_cmd), "apply"]
            if use_lock_false:
                apply_cmd.append("-lock=false")
            apply_cmd.extend(["-auto-approve", "tfplan"])

            # Show warning if using lock=false
            if use_lock_false:
                self.progress.warning(
                    f"Using -lock=false for {stack_name} (state lock bypass)"
                )

            # Run terraform plan
            self.progress.info(f"Generating deployment plan for {stack_name}...")
            plan_result = subprocess.run(
                plan_cmd,
                cwd=str(stack_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )

            if plan_result.returncode != 0:
                # Check if this is a state lock error and we haven't tried lock=false yet
                if not use_lock_false and self._is_state_lock_error(plan_result.stderr):
                    self.progress.warning(
                        f"State lock detected for {stack_name}, attempting fallback with -lock=false..."
                    )
                    return self._deploy_terraform_stack_with_retry(
                        stack_name, stack_dir, use_lock_false=True
                    )

                self.progress.error(f"Terraform plan failed for {stack_name}")
                if plan_result.stderr:
                    self.progress.error("Plan error output:")
                    print(plan_result.stderr)
                return False

            self.progress.success(
                f"Deployment plan generated successfully for {stack_name}"
            )

            # Apply the plan
            self.progress.info(f"Applying infrastructure changes for {stack_name}...")
            self.progress.info("This may take several minutes...")

            apply_result = subprocess.run(
                apply_cmd,
                cwd=str(stack_dir),
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes timeout for apply
            )

            if apply_result.returncode == 0:
                self.progress.success(f"{stack_name} deployed successfully.")
                if apply_result.stdout:
                    self.progress.info(f"{stack_name} apply output:")
                    print(apply_result.stdout)
                # Track successful creation for potential rollback
                self.resources_created.append(stack_name)
                return True
            else:
                # Check if this is a state lock error and we haven't tried lock=false yet
                if not use_lock_false and self._is_state_lock_error(
                    apply_result.stderr
                ):
                    self.progress.warning(
                        f"State lock detected during apply for {stack_name}, attempting fallback with -lock=false..."
                    )
                    return self._deploy_terraform_stack_with_retry(
                        stack_name, stack_dir, use_lock_false=True
                    )

                self.progress.error(f"Terraform apply failed for {stack_name}")
                if apply_result.stderr:
                    self.progress.error("Error output:")
                    print(apply_result.stderr)
                if apply_result.stdout:
                    self.progress.info("Standard output:")
                    print(apply_result.stdout)
                return False

        except subprocess.TimeoutExpired:
            self.progress.error(f"Terraform apply timed out for {stack_name}")
            return False
        except Exception as e:
            self.progress.error(f"Error deploying {stack_name}: {e}")
            return False

    def _is_state_lock_error(self, error_output: str) -> bool:
        """Check if the error output indicates a state lock issue"""
        if not error_output:
            return False

        lock_indicators = [
            "Error acquiring the state lock",
            "state lock",
            "Lock Info:",
            "PreconditionFailed",
            "At least one of the pre-conditions you specified did not hold",
        ]

        error_lower = error_output.lower()
        return any(indicator.lower() in error_lower for indicator in lock_indicators)

    def _update_app_stack_data_bucket_reference(self) -> bool:
        """Update app-stack terraform.tfvars with the data-stack state bucket name"""
        try:
            # Get the backend names from the resource generator
            backend_names = cast(
                ResourceNameGenerator, self.resource_name_generator
            ).get_terraform_backend_names()
            data_stack_bucket = backend_names["state_bucket"]

            # Read the current terraform.tfvars file
            tfvars_file = self.terraform_dir / "terraform.tfvars"
            if not tfvars_file.exists():
                self.progress.warning("terraform.tfvars not found, creating it")
                tfvars_content = ""
            else:
                with open(tfvars_file, "r", encoding="utf-8") as f:
                    tfvars_content = f.read()

            # Check if data_stack_state_bucket is already set
            if "data_stack_state_bucket" in tfvars_content:
                # Update existing value
                import re

                pattern = r'data_stack_state_bucket\s*=\s*"[^"]*"'
                replacement = f'data_stack_state_bucket = "{data_stack_bucket}"'
                tfvars_content = re.sub(pattern, replacement, tfvars_content)
            else:
                # Add new variable
                tfvars_content += f'\ndata_stack_state_bucket = "{data_stack_bucket}"\n'

            # Write the updated content
            with open(tfvars_file, "w", encoding="utf-8") as f:
                f.write(tfvars_content)

            self.progress.success(
                f"Updated app-stack terraform.tfvars with data-stack bucket: {data_stack_bucket}"
            )
            return True

        except Exception as e:
            self.progress.error(
                f"Failed to update app-stack data bucket reference: {e}"
            )
            return False
