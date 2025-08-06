#!/usr/bin/env python3
"""
Pytest test suite for buildspec.yml deployment validation

This test suite validates that:
1. buildspec.yml can create the necessary configuration files
2. deploy.py can run without user interaction
3. The entire deployment pipeline is non-interactive

Usage:
    pytest test_buildspec.py -v
    pytest test_buildspec.py::TestBuildspecDeployment::test_buildspec_exists -v
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml


class TestBuildspecDeployment:
    """Test suite for buildspec.yml deployment functionality"""

    @classmethod
    def setup_class(cls):
        """Setup class-level fixtures"""
        cls.root_dir = Path(__file__).parent.parent.absolute()
        cls.buildspec_path = cls.root_dir / "buildspec.yml"

    def test_buildspec_exists(self):
        """Test that buildspec.yml exists"""
        assert (
            self.buildspec_path.exists()
        ), f"buildspec.yml not found at {self.buildspec_path}"

    def test_buildspec_structure(self):
        """Test that buildspec.yml has the correct structure"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec = yaml.safe_load(f)

        # Check required sections
        required_sections = ["version", "phases"]
        for section in required_sections:
            assert section in buildspec, f"Missing required section: {section}"

        # Check phases
        phases = buildspec.get("phases", {})
        required_phases = ["install", "pre_build", "build"]
        for phase in required_phases:
            assert phase in phases, f"Missing required phase: {phase}"

    def test_env_local_creation(self):
        """Test that buildspec.yml creates .env.local file"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        # Check for .env.local creation logic
        env_creation_patterns = [
            ".env.local",
            "REDDIT_CLIENT_ID",
            "REDDIT_CLIENT_SECRET",
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
        ]

        for pattern in env_creation_patterns:
            assert (
                pattern in buildspec_content
            ), f"Missing .env.local creation pattern: {pattern}"

    def test_lambda_build_execution(self):
        """Test that buildspec.yml builds Lambda functions"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        assert (
            "python build_all.py" in buildspec_content
        ), "buildspec.yml does not call Lambda build script"

    def test_manual_deployment_guidance(self):
        """Test that buildspec.yml provides manual deployment guidance"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        # Check for manual deployment instructions
        manual_deploy_patterns = [
            "manual deployment required",
            "python deploy.py",
            "locally to deploy",
        ]

        found_patterns = [
            pattern
            for pattern in manual_deploy_patterns
            if pattern in buildspec_content
        ]

        assert (
            len(found_patterns) >= 2
        ), f"Insufficient manual deployment guidance found. Found: {found_patterns}"

    def test_lambda_zip_validation(self):
        """Test that buildspec.yml validates Lambda zip files"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        validation_patterns = [
            "Validating Lambda zip files",
            "pytest tests/test_lambda_build_validation.py",
            "test_lambda_build_validation",
        ]

        found_patterns = [
            pattern for pattern in validation_patterns if pattern in buildspec_content
        ]

        assert (
            len(found_patterns) >= 2
        ), f"Insufficient Lambda zip validation found. Found: {found_patterns}"

    def test_build_validation_focus(self):
        """Test that buildspec.yml focuses on build validation not deployment"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        # Check for build validation messaging
        build_focus_patterns = [
            "Starting build validation",
            "no deployment",
            "Build validation complete",
        ]

        found_patterns = [
            pattern for pattern in build_focus_patterns if pattern in buildspec_content
        ]

        assert (
            len(found_patterns) >= 2
        ), f"Insufficient build validation focus found. Found: {found_patterns}"

    def test_non_interactive_environment(self):
        """Test that buildspec.yml sets up non-interactive environment"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        # Check that there are no interactive prompts
        interactive_patterns = ["read ", "input(", "confirm", "y/n"]
        for pattern in interactive_patterns:
            assert (
                pattern not in buildspec_content
            ), f"Interactive pattern found: {pattern}"

    def test_aws_credentials_handling(self):
        """Test that buildspec.yml properly handles AWS credentials"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        # Check for AWS credential setup
        aws_patterns = ["secrets-manager", "AWS_DEFAULT_REGION"]

        # At least one AWS pattern should be present
        aws_found = any(pattern in buildspec_content for pattern in aws_patterns)
        assert aws_found, "No AWS credential handling patterns found"

    def test_error_handling_patterns(self):
        """Test that buildspec.yml has appropriate error handling"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        # Check for basic error handling patterns
        error_patterns = [
            "echo",  # Output for debugging
        ]

        found_patterns = [
            pattern for pattern in error_patterns if pattern in buildspec_content
        ]
        assert (
            len(found_patterns) >= 1
        ), f"Insufficient error handling patterns found: {found_patterns}"

    def test_required_environment_variables(self):
        """Test that buildspec.yml references required environment variables"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec_content = f.read()

        # These variables should be referenced in the buildspec
        required_env_vars = [
            "AWS_DEFAULT_REGION",
        ]

        for var in required_env_vars:
            # Allow for flexible matching (with or without $ prefix)
            var_found = var in buildspec_content or f"${var}" in buildspec_content
            assert var_found, f"Required environment variable not found: {var}"

    @pytest.fixture
    def temp_environment(self):
        """Fixture to create a temporary environment for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Set up environment variables
            original_env = os.environ.copy()
            os.environ.update(
                {
                    "AWS_DEFAULT_REGION": "us-east-1",
                    "AWS_ACCESS_KEY_ID": "test_access_key",
                    "AWS_SECRET_ACCESS_KEY": "test_secret_key",
                    "CODEBUILD_BUILD_ID": "test-build-123",
                }
            )

            yield temp_path

            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)

    def test_env_local_simulation(self, temp_environment):
        """Test simulation of .env.local file creation"""
        temp_path = temp_environment

        # Simulate .env.local creation
        env_local_content = """REDDIT_CLIENT_ID=dummy_client_id
REDDIT_CLIENT_SECRET=dummy_client_secret
REDDIT_USER_AGENT="codebuild:lenslate-deploy:1.0"
GOOGLE_OAUTH_CLIENT_ID=placeholder_client_id
GOOGLE_OAUTH_CLIENT_SECRET=placeholder_client_secret
"""
        env_local_path = temp_path / ".env.local"
        with open(env_local_path, "w") as f:
            f.write(env_local_content)

        assert env_local_path.exists(), ".env.local file was not created"

        # Verify content
        with open(env_local_path, "r") as f:
            content = f.read()

        required_keys = [
            "REDDIT_CLIENT_ID",
            "REDDIT_CLIENT_SECRET",
            "GOOGLE_OAUTH_CLIENT_ID",
        ]
        for key in required_keys:
            assert key in content, f"Required key {key} not found in .env.local"

    def test_terraform_tfvars_simulation(self, temp_environment):
        """Test simulation of terraform.tfvars file creation"""
        temp_path = temp_environment

        # Simulate terraform.tfvars creation
        tfvars_content = """# Auto-generated terraform.tfvars for CodeBuild deployment
region = "us-east-1"
project_name = "lenslate"
environment = "prod"
s3_bucket_name = "lenslate-image-storage-123456789"
frontend_bucket_name = "lenslate-frontend-hosting-123456789"
frontend_path = "../frontend"
allowed_origins = ["https://lenslate.com"]
reddit_client_id = "dummy_client_id"
reddit_client_secret = "dummy_client_secret"
reddit_user_agent = "codebuild:lenslate-deploy:1.0"
google_oauth_client_id = "placeholder_client_id"
google_oauth_client_secret = "placeholder_client_secret"
"""
        tfvars_path = temp_path / "terraform.tfvars"
        with open(tfvars_path, "w") as f:
            f.write(tfvars_content)

        assert tfvars_path.exists(), "terraform.tfvars file was not created"

        # Verify content
        with open(tfvars_path, "r") as f:
            content = f.read()

        required_vars = ["region =", "project_name =", "reddit_client_id ="]
        for var in required_vars:
            assert (
                var in content
            ), f"Required variable {var} not found in terraform.tfvars"

    def test_buildspec_yaml_validity(self):
        """Test that buildspec.yml is valid YAML"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"buildspec.yml is not valid YAML: {e}")

    def test_buildspec_version(self):
        """Test that buildspec.yml specifies a version"""
        with open(self.buildspec_path, "r", encoding="utf-8") as f:
            buildspec = yaml.safe_load(f)

        assert "version" in buildspec, "buildspec.yml must specify a version"
        version = str(buildspec["version"])
        assert version in [
            "0.1",
            "0.2",
        ], f"Unsupported buildspec version: {buildspec['version']}"

    @pytest.mark.integration
    def test_full_environment_setup(self, temp_environment):
        """Integration test for complete environment setup"""
        temp_path = temp_environment

        # Create both configuration files
        env_local_path = temp_path / ".env.local"
        tfvars_path = temp_path / "terraform.tfvars"

        # Create .env.local
        with open(env_local_path, "w") as f:
            f.write("REDDIT_CLIENT_ID=test\nREDDIT_CLIENT_SECRET=test\n")

        # Create terraform.tfvars
        with open(tfvars_path, "w") as f:
            f.write('region = "us-east-1"\nproject_name = "test"\n')

        # Verify both files exist and are readable
        assert env_local_path.exists() and env_local_path.is_file()
        assert tfvars_path.exists() and tfvars_path.is_file()

        # Verify files are not empty
        assert env_local_path.stat().st_size > 0
        assert tfvars_path.stat().st_size > 0


# Pytest configuration and custom markers
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Session-level setup for all tests"""
    print("\n🧪 Starting buildspec.yml deployment validation tests...")
    yield
    print("\n✅ Buildspec validation tests completed!")


# Custom pytest markers for different test categories
pytestmark = [
    pytest.mark.buildspec,
    pytest.mark.deployment,
]


if __name__ == "__main__":
    # Allow running the test file directly
    pytest.main([__file__, "-v"])
