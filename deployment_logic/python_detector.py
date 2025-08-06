""" """

import platform
import re
import shutil
import subprocess
from typing import Optional, Tuple

from .progress_indicator import ProgressIndicator


class PythonDetector:
    """Cross-platform Python executable detection and validation system"""

    def __init__(self, progress_indicator: ProgressIndicator):
        self.progress = progress_indicator
        self.platform = platform.system().lower()
        self.python_cmd = None
        self.python_version = None

    def detect_python_command(self) -> Optional[str]:
        """
        Detect available Python command across platforms.
        Tries python, python3, and py in order.
        Returns the first working command or None if none found.
        """
        # Define command candidates in order of preference
        candidates = ["python", "python3"]

        # On Windows, also try 'py' launcher as last resort
        if self.platform == "windows":
            candidates.append("py")

        for cmd in candidates:
            if self._test_python_command(cmd):
                self.python_cmd = cmd
                return cmd

        return None

    def _test_python_command(self, cmd: str) -> bool:
        """Test if a Python command is available and working"""
        try:
            # Check if command exists in PATH
            if not shutil.which(cmd):
                return False

            # Test if command actually works
            result = subprocess.run(
                [cmd, "--version"], capture_output=True, text=True, timeout=10
            )

            return result.returncode == 0 and "Python" in result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def validate_python_version(self, python_cmd: str) -> bool:
        """
        Validate Python version meets requirements (3.8+).
        Returns True if version is acceptable, False otherwise.
        """
        try:
            result = subprocess.run(
                [python_cmd, "--version"], capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                return False

            # Parse version from output like "Python 3.9.7"
            version_output = result.stdout.strip()
            version_match = re.search(r"Python (\d+)\.(\d+)\.(\d+)", version_output)

            if not version_match:
                self.progress.warning(
                    f"Could not parse Python version from: {version_output}"
                )
                return False

            major, minor, patch = map(int, version_match.groups())
            self.python_version = f"{major}.{minor}.{patch}"

            # Check if version meets minimum requirement (3.8+)
            if major < 3 or (major == 3 and minor < 8):
                self.progress.error(
                    f"Python {self.python_version} is too old (minimum: 3.8.0)"
                )
                return False

            self.progress.success(f"Python {self.python_version} meets requirements")
            return True

        except (
            subprocess.TimeoutExpired,
            ValueError,
            AttributeError,
            FileNotFoundError,
            OSError,
        ) as e:
            self.progress.error(f"Error validating Python version: {e}")
            return False

    def get_python_install_instructions(self) -> str:
        """Get platform-specific Python installation instructions"""
        instructions = {
            "windows": (
                "Install Python from https://python.org/downloads/ or use:\n"
                "  - Windows Store: Search for 'Python' in Microsoft Store\n"
                "  - Winget: winget install Python.Python.3\n"
                "  - Chocolatey: choco install python\n"
                "Make sure to check 'Add Python to PATH' during installation"
            ),
            "darwin": (
                "Install Python using one of these methods:\n"
                "  - Homebrew: brew install python\n"
                "  - Official installer: https://python.org/downloads/\n"
                "  - pyenv: pyenv install 3.11.0 && pyenv global 3.11.0"
            ),
            "linux": (
                "Install Python using your distribution's package manager:\n"
                "  - Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip\n"
                "  - CentOS/RHEL: sudo dnf install python3 python3-pip\n"
                "  - Fedora: sudo dnf install python3 python3-pip\n"
                "  - Arch Linux: sudo pacman -S python python-pip\n"
                "  - Alpine: sudo apk add python3 py3-pip\n"
                "  - Or compile from source: https://python.org/downloads/"
            ),
        }

        return instructions.get(
            self.platform,
            "Please install Python 3.8+ from https://python.org/downloads/",
        )

    def detect_and_validate(self) -> Tuple[bool, Optional[str]]:
        """
        Complete Python detection and validation process.
        Returns (success, python_command) tuple.
        """
        # Try to detect Python command
        python_cmd = self.detect_python_command()

        if not python_cmd:
            self.progress.error("No Python executable found")
            self.progress.info(
                "Tried commands: python, python3"
                + (", py" if self.platform == "windows" else "")
            )
            self.progress.info("Installation instructions:")
            print(self.get_python_install_instructions())
            return False, None

        # Validate version
        if not self.validate_python_version(python_cmd):
            self.progress.info("Installation instructions:")
            print(self.get_python_install_instructions())
            return False, None

        self.progress.success(f"Python executable detected: {python_cmd}")
        return True, python_cmd

    def get_detected_command(self) -> Optional[str]:
        """Get the detected Python command"""
        return self.python_cmd

    def get_detected_version(self) -> Optional[str]:
        """Get the detected Python version"""
        return self.python_version
