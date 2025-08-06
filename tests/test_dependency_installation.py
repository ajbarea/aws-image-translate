#!/usr/bin/env python3
"""
Test dependency installation functionality
"""

import sys
from unittest.mock import Mock, patch

import pytest

from deployment_logic.deployment_orchestrator import DeploymentOrchestrator


class TestDependencyInstallation:
    """Test cases for dependency installation functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.orchestrator = DeploymentOrchestrator(ci_mode=True)
        self.orchestrator.python_cmd = sys.executable
        self.orchestrator.platform = (
            "windows"  # or "linux"/"darwin" depending on test needs
        )

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_dependencies_success_with_npm(self, mock_subprocess, mock_which):
        """Test successful dependency installation when npm is available"""
        # Mock npm being available
        mock_which.return_value = "/path/to/npm"

        # Mock successful subprocess calls
        mock_subprocess.return_value = Mock(returncode=0, stderr="", stdout="")

        # Test the method
        result = self.orchestrator._install_dependencies()

        # Assertions
        assert result is True
        assert mock_subprocess.call_count == 2  # npm install + pip install

        # Verify npm install was called
        npm_call = mock_subprocess.call_args_list[0]
        assert npm_call[0][0] == ["npm", "install"]
        assert npm_call[1]["shell"] is True  # Windows shell mode

        # Verify pip install was called
        pip_call = mock_subprocess.call_args_list[1]
        expected_pip_args = [sys.executable, "-m", "pip", "install", "-e", ".[testing]"]
        assert pip_call[0][0] == expected_pip_args

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_dependencies_success_without_npm(
        self, mock_subprocess, mock_which
    ):
        """Test successful dependency installation when npm is not available"""
        # Mock npm not being available
        mock_which.return_value = None

        # Mock successful pip install
        mock_subprocess.return_value = Mock(returncode=0, stderr="", stdout="")

        # Test the method
        result = self.orchestrator._install_dependencies()

        # Assertions
        assert result is True
        assert mock_subprocess.call_count == 1  # Only pip install

        # Verify pip install was called
        pip_call = mock_subprocess.call_args_list[0]
        expected_pip_args = [sys.executable, "-m", "pip", "install", "-e", ".[testing]"]
        assert pip_call[0][0] == expected_pip_args

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_dependencies_npm_failure(self, mock_subprocess, mock_which):
        """Test dependency installation when npm install fails"""
        # Mock npm being available
        mock_which.return_value = "/path/to/npm"

        # Mock npm install failure
        mock_subprocess.return_value = Mock(
            returncode=1, stderr="npm install failed", stdout=""
        )

        # Test the method
        result = self.orchestrator._install_dependencies()

        # Assertions
        assert result is False
        assert mock_subprocess.call_count == 1  # Only npm install attempted

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_dependencies_pip_failure(self, mock_subprocess, mock_which):
        """Test dependency installation when pip install fails"""
        # Mock npm not being available to skip npm install
        mock_which.return_value = None

        # Mock pip install failure
        mock_subprocess.return_value = Mock(
            returncode=1, stderr="pip install failed", stdout=""
        )

        # Test the method
        result = self.orchestrator._install_dependencies()

        # Assertions
        assert result is False
        assert mock_subprocess.call_count == 1  # Only pip install attempted

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_install_dependencies_timeout(self, mock_subprocess, mock_which):
        """Test dependency installation when subprocess times out"""
        # Mock npm being available
        mock_which.return_value = "/path/to/npm"

        # Mock timeout
        from subprocess import TimeoutExpired

        mock_subprocess.side_effect = TimeoutExpired("npm", 300)

        # Test the method
        result = self.orchestrator._install_dependencies()

        # Assertions
        assert result is False

    def test_install_dependencies_no_python_cmd(self):
        """Test dependency installation when python command is not available"""
        # Clear python command
        self.orchestrator.python_cmd = None

        # Test the method
        result = self.orchestrator._install_dependencies()

        # Assertions
        assert result is False

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_platform_specific_shell_usage(self, mock_subprocess, mock_which):
        """Test that shell=True is used on Windows platform"""
        # Mock npm being available
        mock_which.return_value = "/path/to/npm"
        mock_subprocess.return_value = Mock(returncode=0, stderr="", stdout="")

        # Test Windows platform
        self.orchestrator.platform = "windows"
        self.orchestrator._install_dependencies()

        # Check that shell=True was used for npm install
        npm_call = mock_subprocess.call_args_list[0]
        assert npm_call[1]["shell"] is True

        # Reset mocks
        mock_subprocess.reset_mock()

        # Test non-Windows platform
        self.orchestrator.platform = "linux"
        self.orchestrator._install_dependencies()

        # Check that shell=False was used for npm install
        npm_call = mock_subprocess.call_args_list[0]
        assert npm_call[1]["shell"] is False


@pytest.mark.integration
def test_dependency_installation_integration():
    """Integration test for dependency installation (requires actual environment)"""
    # This test runs the actual dependency installation
    # Mark as integration test so it can be skipped in fast test runs

    orchestrator = DeploymentOrchestrator(ci_mode=True)
    orchestrator.python_cmd = sys.executable

    # This will actually run npm install and pip install
    # Only run this if you want to test against the real environment
    result = orchestrator._install_dependencies()

    assert (
        result is True
    ), "Dependency installation should succeed in a properly configured environment"


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
