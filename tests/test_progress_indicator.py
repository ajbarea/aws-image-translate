"""
Unit tests for the ProgressIndicator class.
"""

import pytest

from deployment_logic.progress_indicator import Colors, ProgressIndicator


@pytest.fixture
def progress_indicator():
    """Fixture to create a ProgressIndicator instance."""
    return ProgressIndicator(total_steps=5)


class TestColors:
    """Tests for the Colors class."""

    def test_color_codes_are_strings(self):
        """Test that all color codes are strings."""
        assert isinstance(Colors.HEADER, str)
        assert isinstance(Colors.OKBLUE, str)
        assert isinstance(Colors.OKCYAN, str)
        assert isinstance(Colors.OKGREEN, str)
        assert isinstance(Colors.WARNING, str)
        assert isinstance(Colors.FAIL, str)
        assert isinstance(Colors.ENDC, str)
        assert isinstance(Colors.BOLD, str)
        assert isinstance(Colors.UNDERLINE, str)


class TestProgressIndicator:
    """Tests for the ProgressIndicator class."""

    def test_initialization(self, progress_indicator):
        """Test that the progress indicator is initialized correctly."""
        assert progress_indicator.total_steps == 5
        assert progress_indicator.current_step == 0

    def test_next_step(self, progress_indicator, capsys):
        """Test the next_step method."""
        progress_indicator.next_step("Testing step 1")
        captured = capsys.readouterr()
        assert "[1/5] Testing step 1" in captured.out
        assert progress_indicator.current_step == 1

        progress_indicator.next_step("Testing step 2")
        captured = capsys.readouterr()
        assert "[2/5] Testing step 2" in captured.out
        assert progress_indicator.current_step == 2

    def test_success_message(self, progress_indicator, capsys):
        """Test the success message output."""
        progress_indicator.success("Operation successful")
        captured = capsys.readouterr()
        assert "[OK] Operation successful" in captured.out
        assert Colors.OKGREEN in captured.out

    def test_warning_message(self, progress_indicator, capsys):
        """Test the warning message output."""
        progress_indicator.warning("This is a warning")
        captured = capsys.readouterr()
        assert "[WARNING] This is a warning" in captured.out
        assert Colors.WARNING in captured.out

    def test_error_message(self, progress_indicator, capsys):
        """Test the error message output."""
        progress_indicator.error("An error occurred")
        captured = capsys.readouterr()
        assert "[ERROR] An error occurred" in captured.out
        assert Colors.FAIL in captured.out

    def test_info_message(self, progress_indicator, capsys):
        """Test the info message output."""
        progress_indicator.info("Some information")
        captured = capsys.readouterr()
        assert "[INFO] Some information" in captured.out
        assert Colors.OKCYAN in captured.out
