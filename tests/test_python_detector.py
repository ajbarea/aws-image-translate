"""
Unit tests for the PythonDetector class.
"""

from unittest.mock import MagicMock, patch

import pytest

from deployment_logic.progress_indicator import ProgressIndicator
from deployment_logic.python_detector import PythonDetector


@pytest.fixture
def mock_progress_indicator():
    """Fixture to create a mock ProgressIndicator."""
    return MagicMock(spec=ProgressIndicator)


@pytest.fixture
def python_detector(mock_progress_indicator):
    """Fixture to create a PythonDetector instance."""
    detector = PythonDetector(progress_indicator=mock_progress_indicator)
    # Mock the platform to have a consistent testing environment
    detector.platform = "linux"
    return detector


class TestPythonDetector:
    """Tests for the PythonDetector class."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_python_command_success(self, mock_run, mock_which, python_detector):
        """Test successful detection of python3."""
        mock_which.side_effect = [True, True]  # python, python3
        mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.9.7")

        command = python_detector.detect_python_command()
        assert command == "python"
        assert python_detector.python_cmd == "python"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_python_command_fallback(
        self, mock_run, mock_which, python_detector
    ):
        """Test fallback to python3 if python is not found."""
        mock_which.side_effect = [False, True]  # python fails, python3 succeeds
        mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.9.7")

        command = python_detector.detect_python_command()
        assert command == "python3"

    @patch("shutil.which")
    def test_detect_python_command_not_found(self, mock_which, python_detector):
        """Test when no python command is found."""
        mock_which.return_value = False
        command = python_detector.detect_python_command()
        assert command is None

    @patch("subprocess.run")
    def test_validate_python_version_success(self, mock_run, python_detector):
        """Test validation of a valid Python version."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.8.10")
        is_valid = python_detector.validate_python_version("python3")
        assert is_valid is True
        assert python_detector.python_version == "3.8.10"

    @patch("subprocess.run")
    def test_validate_python_version_too_old(self, mock_run, python_detector):
        """Test validation of an outdated Python version."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.7.0")
        is_valid = python_detector.validate_python_version("python3")
        assert is_valid is False
        python_detector.progress.error.assert_called_with(
            "Python 3.7.0 is too old (minimum: 3.8.0)"
        )

    @patch("subprocess.run")
    def test_validate_python_version_parse_error(self, mock_run, python_detector):
        """Test validation with unparseable version output."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Invalid Version String")
        is_valid = python_detector.validate_python_version("python3")
        assert is_valid is False
        python_detector.progress.warning.assert_called_with(
            "Could not parse Python version from: Invalid Version String"
        )

    def test_get_python_install_instructions(self, python_detector):
        """Test that installation instructions are returned."""
        python_detector.platform = "windows"
        instructions = python_detector.get_python_install_instructions()
        assert "winget" in instructions

        python_detector.platform = "darwin"
        instructions = python_detector.get_python_install_instructions()
        assert "brew" in instructions

        python_detector.platform = "linux"
        instructions = python_detector.get_python_install_instructions()
        assert "apt" in instructions

    @patch.object(PythonDetector, "detect_python_command", return_value="python3")
    @patch.object(PythonDetector, "validate_python_version", return_value=True)
    def test_detect_and_validate_success(
        self, mock_validate, mock_detect, python_detector
    ):
        """Test the end-to-end detection and validation process (success)."""
        success, command = python_detector.detect_and_validate()
        assert success is True
        assert command == "python3"
        mock_detect.assert_called_once()
        mock_validate.assert_called_once_with("python3")

    @patch.object(PythonDetector, "detect_python_command", return_value=None)
    def test_detect_and_validate_no_command(self, mock_detect, python_detector):
        """Test the end-to-end process when no command is found."""
        success, command = python_detector.detect_and_validate()
        assert success is False
        assert command is None
        mock_detect.assert_called_once()
        python_detector.progress.error.assert_called_with("No Python executable found")

    @patch.object(PythonDetector, "detect_python_command", return_value="python3")
    @patch.object(PythonDetector, "validate_python_version", return_value=False)
    def test_detect_and_validate_invalid_version(
        self, mock_validate, mock_detect, python_detector
    ):
        """Test the end-to-end process with an invalid version."""
        success, command = python_detector.detect_and_validate()
        assert success is False
        assert command is None
        mock_detect.assert_called_once()
        mock_validate.assert_called_once_with("python3")
