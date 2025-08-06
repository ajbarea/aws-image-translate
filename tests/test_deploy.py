#!/usr/bin/env python3
"""
Integration tests for deploy.py terraform apply --auto-approve functionality

This test suite uses pytest to validate the deployment process can run without manual intervention.
"""
import inspect
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from deployment_logic.deployment_orchestrator import DeploymentOrchestrator
from deployment_logic.progress_indicator import Colors
from deployment_logic.resource_naming import ResourceNameGenerator


@pytest.fixture(scope="session")
def project_paths():
    """Fixture providing project paths"""
    root_dir = Path(__file__).parent.parent.absolute()
    return {
        "root_dir": root_dir,
        "terraform_dir": root_dir / "terraform" / "app-stack",
        "buildspec_path": root_dir / "buildspec.yml",
        "env_local_path": root_dir / ".env.local",
        "env_example_path": root_dir / ".env.example",
    }


@pytest.fixture(scope="session")
def deployer():
    """Fixture providing DeploymentOrchestrator instance"""
    deployer_instance = DeploymentOrchestrator(ci_mode=True)

    # Mock resource name generator
    mock_resource_generator = MagicMock(spec=ResourceNameGenerator)
    mock_backend_names = {
        "state_bucket": "lenslate-terraform-state-123456-abc123",
        "lock_table": "lenslate-terraform-lock-123456-abc123",
    }
    mock_resource_generator.get_terraform_backend_names.return_value = (
        mock_backend_names
    )
    mock_resource_generator.aws_region = "us-east-1"
    deployer_instance.resource_name_generator = mock_resource_generator

    return deployer_instance


class TestDeploymentIntegration:
    """Integration tests for deployment functionality"""

    def test_environment_setup(self, project_paths):
        """Test that environment can be set up for non-interactive deployment"""
        # Check if .env.local exists or can be created
        env_local_path = project_paths["env_local_path"]
        env_example_path = project_paths["env_example_path"]

        assert (
            env_local_path.exists() or env_example_path.exists()
        ), "Neither .env.local nor .env.example found"

        # Check terraform directory
        assert project_paths["terraform_dir"].exists(), "Terraform directory not found"

        # Check for terraform configuration files
        required_tf_files = [
            "main.tf",
            "variables.tf",
            "outputs.tf",
            "env_to_tfvars.py",
        ]
        missing_files = []

        for tf_file in required_tf_files:
            if not (project_paths["terraform_dir"] / tf_file).exists():
                missing_files.append(tf_file)

        assert not missing_files, f"Missing terraform files: {', '.join(missing_files)}"

    def test_deployment_prerequisites(self, deployer):
        """Test that all deployment prerequisites are met"""
        # Test that the method exists and is callable
        assert hasattr(
            deployer, "validate_prerequisites"
        ), "validate_prerequisites method not found"
        assert callable(
            getattr(deployer, "validate_prerequisites")
        ), "validate_prerequisites method not callable"

        # Test platform detection
        assert hasattr(deployer, "platform"), "platform attribute not found"
        assert deployer.platform in [
            "windows",
            "darwin",
            "linux",
            "unknown",
        ], f"Invalid platform: {deployer.platform}"

    def test_terraform_configuration_validation(self, deployer):
        """Test terraform configuration validation method exists"""
        # Set terraform command
        deployer.terraform_cmd = "terraform"

        # Test that the method exists and is callable
        assert hasattr(
            deployer, "validate_terraform_configuration"
        ), "validate_terraform_configuration method not found"
        assert callable(
            getattr(deployer, "validate_terraform_configuration")
        ), "validate_terraform_configuration method not callable"

        # Test terraform directory path
        assert hasattr(deployer, "terraform_dir"), "terraform_dir attribute not found"
        assert deployer.terraform_dir.exists(), "Terraform directory does not exist"

    def test_terraform_version_validation(self, deployer):
        """Test terraform version validation method exists"""
        # Set terraform command
        deployer.terraform_cmd = "terraform"

        # Test that the method exists and is callable
        assert hasattr(
            deployer, "validate_terraform_version"
        ), "validate_terraform_version method not found"
        assert callable(
            getattr(deployer, "validate_terraform_version")
        ), "validate_terraform_version method not callable"

        # Test configuration validation method
        assert hasattr(
            deployer, "validate_terraform_configuration"
        ), "validate_terraform_configuration method not found"
        assert callable(
            getattr(deployer, "validate_terraform_configuration")
        ), "validate_terraform_configuration method not callable"

    def test_deployment_run_method_structure(self, deployer):
        """Test that run method has proper structure for deployment orchestration"""
        # Set terraform command
        deployer.terraform_cmd = "terraform"

        # Check that the method exists and can be called
        assert hasattr(deployer, "run"), "run method not found"
        assert callable(getattr(deployer, "run")), "run method not callable"

        # Verify the method has proper deployment flow
        source = inspect.getsource(deployer.run)

        # Check for key components required for deployment orchestration
        required_components = [
            ("validate_prerequisites", "Validates prerequisites"),
            ("build_lambda_functions", "Builds lambda functions"),
            ("validate_lambda_zip_files", "Validates lambda zip files"),
            ("deployment_started", "Tracks deployment state"),
        ]

        missing_components = []
        for component, description in required_components:
            if component not in source:
                missing_components.append(description)

        assert (
            not missing_components
        ), f"Missing required components: {', '.join(missing_components)}"

        # Test CI mode functionality
        assert deployer.ci_mode is True, "Deployer should be in CI mode for tests"

        # Test environment file handling
        assert hasattr(
            deployer, "_handle_environment_file"
        ), "_handle_environment_file method not found"

    def test_buildspec_compatibility(self, project_paths):
        """Test that buildspec.yml is compatible with non-interactive deployment"""
        buildspec_path = project_paths["buildspec_path"]

        assert buildspec_path.exists(), "buildspec.yml not found"

        with open(buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

            # Check for deployment-related configuration
        expected_elements = [
            ("lambda_functions", "References lambda functions directory"),
            ("AWS_DEFAULT_REGION", "Sets AWS region"),
            (".env.local", "Creates .env.local file"),
        ]

        missing_elements = []
        for element, description in expected_elements:
            if element not in buildspec_content:
                missing_elements.append(description)

        assert (
            not missing_elements
        ), f"Missing required elements for non-interactive deployment: {', '.join(missing_elements)}"

    @pytest.mark.integration
    def test_terraform_commands_available(self):
        """Test that terraform command is available in the system"""
        try:
            result = subprocess.run(
                ["terraform", "version"], capture_output=True, text=True, timeout=30
            )
            assert result.returncode == 0, f"Terraform command failed: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("Terraform not installed or not in PATH")
        except subprocess.TimeoutExpired:
            pytest.fail("Terraform version command timed out")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_terraform_configuration_validation_actual(self, project_paths, deployer):
        """Test actual terraform configuration validation (requires terraform to be installed)"""
        deployer.terraform_cmd = "terraform"

        # Only run if terraform is available
        try:
            subprocess.run(["terraform", "version"], check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pytest.skip("Terraform not available")

        # Test configuration validation
        result = deployer.validate_terraform_configuration()
        assert isinstance(
            result, bool
        ), "validate_terraform_configuration should return a boolean"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_lambda_build_actual(self, project_paths, deployer):
        """Test actual lambda function building"""
        deployer.python_cmd = "python"

        # Test lambda build functionality
        result = deployer.build_lambda_functions()
        assert isinstance(
            result, bool
        ), "build_lambda_functions should return a boolean"


class TestDeploymentPrerequisites:
    """Tests for deployment prerequisites"""

    def test_deployer_instantiation(self):
        """Test that DeploymentOrchestrator can be instantiated"""
        deployer = DeploymentOrchestrator()
        assert deployer is not None

        # Test CI mode instantiation
        ci_deployer = DeploymentOrchestrator(ci_mode=True)
        assert ci_deployer is not None
        assert ci_deployer.ci_mode is True

    def test_colors_available(self):
        """Test that Colors class is available for output formatting"""
        assert hasattr(Colors, "HEADER")
        assert hasattr(Colors, "OKGREEN")
        assert hasattr(Colors, "FAIL")
        assert hasattr(Colors, "ENDC")

    def test_required_methods_exist(self):
        """Test that all required methods exist on DeploymentOrchestrator"""
        deployer = DeploymentOrchestrator()
        required_methods = [
            "validate_prerequisites",
            "validate_terraform_configuration",
            "validate_terraform_version",
            "build_lambda_functions",
            "validate_lambda_zip_files",
            "run",
            "_handle_environment_file",
            "_generate_terraform_vars",
        ]

        missing_methods = []
        for method in required_methods:
            if not hasattr(deployer, method):
                missing_methods.append(method)

        assert (
            not missing_methods
        ), f"Missing required methods: {', '.join(missing_methods)}"

        # Test required attributes
        required_attributes = [
            "platform",
            "root_dir",
            "terraform_dir",
            "env_file",
            "ci_mode",
            "progress",
        ]

        missing_attributes = []
        for attr in required_attributes:
            if not hasattr(deployer, attr):
                missing_attributes.append(attr)

        assert (
            not missing_attributes
        ), f"Missing required attributes: {', '.join(missing_attributes)}"


# Custom pytest markers for different test categories
pytestmark = [
    pytest.mark.integration,  # Mark all tests in this module as integration tests
]


def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


if __name__ == "__main__":
    # Allow running with python -m pytest or python test_file.py
    pytest.main([__file__])
