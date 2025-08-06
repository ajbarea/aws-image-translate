#!/usr/bin/env python3
"""
Cross-platform Lambda function builder for individual functions.
Handles dependency installation, source file packaging, and zip creation.
"""

import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    from deployment_logic.progress_indicator import ProgressIndicator
    from deployment_logic.python_detector import PythonDetector

    PYTHON_DETECTOR_AVAILABLE = True
except ImportError:
    PYTHON_DETECTOR_AVAILABLE = False


@dataclass
class LambdaFunction:
    """Metadata for a Lambda function."""

    name: str
    handler_file: str
    handler_function: str
    source_files: List[str]
    has_dependencies: bool = False
    runtime: str = "python3.11"


# Lambda function definitions
LAMBDA_FUNCTIONS = {
    "image_processor": LambdaFunction(
        name="image_processor",
        handler_file="image_processor.py",
        handler_function="lambda_handler",
        source_files=["image_processor.py", "aws_clients.py"],
    ),
    "gallery_lister": LambdaFunction(
        name="gallery_lister",
        handler_file="gallery_lister.py",
        handler_function="lambda_handler",
        source_files=["gallery_lister.py", "aws_clients.py"],
    ),
    "cognito_triggers": LambdaFunction(
        name="cognito_triggers",
        handler_file="cognito_triggers.py",
        handler_function="lambda_handler",
        source_files=["cognito_triggers.py", "aws_clients.py"],
    ),
    "user_manager": LambdaFunction(
        name="user_manager",
        handler_file="user_manager.py",
        handler_function="lambda_handler",
        source_files=["user_manager.py", "aws_clients.py"],
    ),
    "mmid_populator": LambdaFunction(
        name="mmid_populator",
        handler_file="mmid_populator.py",
        handler_function="lambda_handler",
        source_files=["mmid_populator.py", "aws_clients.py"],
    ),
    "reddit_populator": LambdaFunction(
        name="reddit_populator",
        handler_file="reddit_populator_sync.py",
        handler_function="lambda_handler",
        source_files=[
            "reddit_populator_sync.py",
            "reddit_scraper_sync.py",
            "aws_clients.py",
        ],
        has_dependencies=True,
    ),
    "history_handler": LambdaFunction(
        name="history_handler",
        handler_file="history_handler.py",
        handler_function="lambda_handler",
        source_files=["history_handler.py", "aws_clients.py"],
    ),
    "performance_handler": LambdaFunction(
        name="performance_handler",
        handler_file="performance_handler.py",
        handler_function="lambda_handler",
        source_files=["performance_handler.py", "aws_clients.py"],
    ),
    "prepare_reddit_populator": LambdaFunction(
        name="prepare_reddit_populator",
        handler_file="prepare_reddit_populator.py",
        handler_function="main",
        source_files=["prepare_reddit_populator.py"],
    ),
    "reddit_realtime_scraper": LambdaFunction(
        name="reddit_realtime_scraper",
        handler_file="reddit_realtime_scraper.py",
        handler_function="process_new_reddit_posts",
        source_files=[
            "reddit_realtime_scraper.py",
            "reddit_config.py",
            "reddit_populator_sync.py",
            "reddit_scraper_sync.py",
            "aws_clients.py",
        ],
        has_dependencies=True,
    ),
}


class LambdaBuildError(Exception):
    """Custom exception for Lambda build errors."""

    pass


def validate_source_files(lambda_dir: Path, source_files: List[str]) -> None:
    """Validate that all required source files exist."""
    missing_files = []
    for file_name in source_files:
        source_path = lambda_dir / file_name
        if not source_path.exists():
            missing_files.append(file_name)

    if missing_files:
        raise LambdaBuildError(f"Missing source files: {', '.join(missing_files)}")


def copy_source_files(
    lambda_dir: Path, build_dir: Path, source_files: List[str]
) -> None:
    """Copy source files to the build directory."""
    print("Copying source files...")
    for file_name in source_files:
        source_path = lambda_dir / file_name
        dest_path = build_dir / file_name
        shutil.copy2(source_path, dest_path)
        print(f"  * Copied {file_name}")


def install_dependencies(python_cmd: str, lambda_dir: Path, build_dir: Path) -> None:
    """Install Python dependencies to the build directory with error handling."""
    requirements_file = lambda_dir / "requirements.txt"

    if not requirements_file.exists():
        raise LambdaBuildError(f"requirements.txt not found at {requirements_file}")

    print(f"Installing dependencies from {requirements_file}...")
    print(f"Using Python executable: {python_cmd}")

    try:
        # First, validate pip is available
        pip_check = subprocess.run(
            [python_cmd, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if pip_check.returncode != 0:
            raise LambdaBuildError(
                f"pip is not available with Python executable '{python_cmd}'\n"
                f"Error: {pip_check.stderr}\n"
                f"Solution: Install pip or use a different Python executable"
            )

        print(f"  * Using pip: {pip_check.stdout.strip()}")

        # Install dependencies with error handling
        result = subprocess.run(
            [
                python_cmd,
                "-m",
                "pip",
                "install",
                "--target",
                str(build_dir),
                "-r",
                str(requirements_file),
                "--no-deps",  # Avoid conflicts with system packages
                "--upgrade",
                "--no-cache-dir",  # Avoid cache issues
            ],
            capture_output=True,
            text=True,
            cwd=str(lambda_dir),
            timeout=300,  # 5 minute timeout
        )

        if result.returncode == 0:
            print("  * Dependencies installed successfully")

            # Show installed packages
            if result.stdout and "Successfully installed" in result.stdout:
                installed_packages = [
                    line
                    for line in result.stdout.split("\n")
                    if "Successfully installed" in line
                ]
                for line in installed_packages:
                    print(f"  {line}")
        else:
            # Error analysis
            error_msg = _analyze_pip_error(result, python_cmd, requirements_file)
            raise LambdaBuildError(error_msg)

    except subprocess.TimeoutExpired:
        raise LambdaBuildError(
            f"Dependency installation timed out after 5 minutes.\n"
            f"This may be due to slow internet connection or large packages.\n"
            f"Solutions:\n"
            f"  - Check internet connection\n"
            f"  - Try running manually: {python_cmd} -m pip install -r {requirements_file}\n"
            f"  - Consider using a faster internet connection"
        )
    except subprocess.CalledProcessError as e:
        error_msg = _analyze_pip_error(e, python_cmd, requirements_file)
        raise LambdaBuildError(error_msg)
    except Exception as e:
        raise LambdaBuildError(
            f"Unexpected error during dependency installation: {e}\n"
            f"Python command: {python_cmd}\n"
            f"Requirements file: {requirements_file}"
        )


def _analyze_pip_error(result, python_cmd: str, requirements_file: Path) -> str:
    """Analyze pip installation errors and provide specific guidance."""
    error_output = (
        result.stderr.lower() if hasattr(result, "stderr") and result.stderr else ""
    )
    stdout_output = (
        result.stdout.lower() if hasattr(result, "stdout") and result.stdout else ""
    )
    combined_output = f"{error_output} {stdout_output}"

    error_msg = f"Failed to install dependencies from {requirements_file}\n"

    # Add raw output for debugging
    if hasattr(result, "stderr") and result.stderr:
        error_msg += f"\nSTDERR:\n{result.stderr}\n"
    if hasattr(result, "stdout") and result.stdout:
        error_msg += f"\nSTDOUT:\n{result.stdout}\n"

    # Analyze specific error patterns and provide solutions
    error_msg += "\nERROR ANALYSIS AND SOLUTIONS:\n"

    if "permission denied" in combined_output or "access is denied" in combined_output:
        error_msg += (
            "• PERMISSION ERROR: Insufficient permissions to install packages\n"
            "  Solutions:\n"
            "  - Run with administrator/sudo privileges\n"
            "  - Use virtual environment: python -m venv venv && source venv/bin/activate\n"
            "  - Install to user directory: pip install --user\n"
        )

    if "externally-managed-environment" in combined_output:
        error_msg += (
            "• EXTERNALLY MANAGED ENVIRONMENT: System Python is protected\n"
            "  Solutions:\n"
            "  - Use virtual environment: python -m venv venv && source venv/bin/activate\n"
            "  - Use --break-system-packages flag (not recommended)\n"
            "  - Install Python from python.org instead of system package manager\n"
        )

    if any(
        term in combined_output
        for term in ["network", "connection", "timeout", "unreachable"]
    ):
        error_msg += (
            "• NETWORK ERROR: Cannot connect to package repositories\n"
            "  Solutions:\n"
            "  - Check internet connection\n"
            "  - Configure proxy if needed: pip config set global.proxy http://proxy:port\n"
            "  - Try alternative index: pip install -i https://pypi.org/simple/\n"
            "  - Retry installation after network issues are resolved\n"
        )

    if "no space left" in combined_output or "disk" in combined_output:
        error_msg += (
            "• DISK SPACE ERROR: Insufficient disk space\n"
            "  Solutions:\n"
            "  - Free up disk space\n"
            "  - Clean pip cache: pip cache purge\n"
            "  - Use different temporary directory\n"
        )

    if any(
        term in combined_output
        for term in ["compiler", "gcc", "visual studio", "build tools"]
    ):
        error_msg += (
            "• COMPILATION ERROR: Missing build tools for native extensions\n"
            "  Solutions:\n"
            "  - Windows: Install Microsoft C++ Build Tools\n"
            "  - macOS: Install Xcode command line tools: xcode-select --install\n"
            "  - Linux: Install build-essential package\n"
            "  - Try pre-compiled wheels: pip install --only-binary=all\n"
        )

    if "no module named" in combined_output:
        error_msg += (
            "• MODULE ERROR: Missing Python modules\n"
            "  Solutions:\n"
            "  - Ensure pip is up to date: python -m pip install --upgrade pip\n"
            "  - Check Python installation integrity\n"
            "  - Reinstall Python if necessary\n"
        )

    # Add general troubleshooting steps
    error_msg += (
        f"\nGENERAL TROUBLESHOOTING:\n"
        f"1. Try manual installation: {python_cmd} -m pip install -r {requirements_file}\n"
        f"2. Update pip: {python_cmd} -m pip install --upgrade pip\n"
        f"3. Clear pip cache: {python_cmd} -m pip cache purge\n"
        f"4. Check Python version: {python_cmd} --version\n"
        f"5. Verify requirements file exists and is readable: cat {requirements_file}\n"
    )

    return error_msg


def create_zip_file(build_dir: Path, zip_path: Path) -> None:
    """Create a zip file from the build directory with validation."""
    print(f"Creating zip file: {zip_path}")

    # Ensure the parent directory exists
    try:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise LambdaBuildError(f"Cannot create parent directory for zip file: {e}")

    # Validate build directory exists and has content
    if not build_dir.exists():
        raise LambdaBuildError(f"Build directory does not exist: {build_dir}")

    # Count files to be zipped
    files_to_zip = []
    for root, dirs, files in os.walk(build_dir):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            # Skip .pyc files and other unnecessary files
            if file.endswith((".pyc", ".pyo", ".DS_Store", ".gitignore")):
                continue

            file_path = Path(root) / file
            files_to_zip.append(file_path)

    if not files_to_zip:
        raise LambdaBuildError(f"No files found to zip in build directory: {build_dir}")

    print(f"  * Found {len(files_to_zip)} files to zip")

    try:
        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zipf:
            for file_path in files_to_zip:
                try:
                    arcname = file_path.relative_to(build_dir)
                    zipf.write(file_path, arcname)
                except Exception as e:
                    raise LambdaBuildError(
                        f"Failed to add file {file_path} to zip: {e}"
                    )

    except zipfile.BadZipFile as e:
        raise LambdaBuildError(f"Failed to create valid zip file: {e}")
    except Exception as e:
        raise LambdaBuildError(f"Unexpected error creating zip file: {e}")

    # zip file validation
    _validate_created_zip_file(zip_path, len(files_to_zip))


def _validate_created_zip_file(zip_path: Path, expected_file_count: int) -> None:
    """Validate the created zip file with checks."""
    # Check if file exists
    if not zip_path.exists():
        raise LambdaBuildError(f"Zip file was not created: {zip_path}")

    # Check file size
    zip_size = zip_path.stat().st_size
    if zip_size == 0:
        raise LambdaBuildError(f"Created zip file is empty: {zip_path}")

    # Minimum reasonable size check (should be at least 1KB for Lambda functions)
    if zip_size < 1024:
        raise LambdaBuildError(
            f"Created zip file is suspiciously small ({zip_size} bytes): {zip_path}\n"
            f"This may indicate missing files or compression issues."
        )

    # Validate zip file structure
    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            # Test zip file integrity
            bad_file = zipf.testzip()
            if bad_file:
                raise LambdaBuildError(
                    f"Created zip file is corrupted (bad file: {bad_file}): {zip_path}"
                )

            # Check file count
            zip_file_list = zipf.namelist()
            if len(zip_file_list) == 0:
                raise LambdaBuildError(
                    f"Created zip file contains no files: {zip_path}"
                )

            # Warn if file count doesn't match expected
            if len(zip_file_list) != expected_file_count:
                print(
                    f"  * Warning: Expected {expected_file_count} files, zip contains {len(zip_file_list)}"
                )

            # Check for essential Python files
            python_files = [f for f in zip_file_list if f.endswith(".py")]
            if not python_files:
                raise LambdaBuildError(
                    f"Created zip file contains no Python files: {zip_path}\n"
                    f"Files in zip: {', '.join(zip_file_list[:10])}{'...' if len(zip_file_list) > 10 else ''}"
                )

            print(
                f"  * Zip validation passed: {len(zip_file_list)} files, {len(python_files)} Python files"
            )

            # Check for suspiciously large files (>50MB)
            if zip_size > 50 * 1024 * 1024:
                print(
                    f"  * Warning: Zip file is large ({zip_size:,} bytes) - may contain unnecessary files"
                )
                # List largest files for debugging
                file_sizes = []
                for info in zipf.infolist():
                    if info.file_size > 1024 * 1024:  # Files larger than 1MB
                        file_sizes.append((info.filename, info.file_size))

                if file_sizes:
                    print("  * Large files in zip:")
                    for filename, size in sorted(
                        file_sizes, key=lambda x: x[1], reverse=True
                    )[:5]:
                        print(f"    - {filename}: {size:,} bytes")

    except zipfile.BadZipFile:
        raise LambdaBuildError(f"Created file is not a valid zip file: {zip_path}")
    except Exception as e:
        raise LambdaBuildError(f"Error validating created zip file: {e}")

    print(f"  * Created zip file ({zip_size:,} bytes)")


def cleanup_build_directory(build_dir: Path) -> None:
    """Clean up the build directory after successful zip creation."""
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print(f"  * Cleaned up build directory: {build_dir}")


def build_lambda_function(
    function_name: str, cleanup: bool = True, python_cmd: Optional[str] = None
) -> Path:
    """
    Build a single Lambda function with error handling.

    Args:
        function_name: Name of the Lambda function to build
        cleanup: Whether to clean up build directory after zip creation
        python_cmd: Python executable to use (auto-detected if None)

    Returns:
        Path to the created zip file

    Raises:
        LambdaBuildError: If build fails
    """
    if function_name not in LAMBDA_FUNCTIONS:
        available = ", ".join(LAMBDA_FUNCTIONS.keys())
        raise LambdaBuildError(
            f"Unknown function '{function_name}'. Available: {available}"
        )

    func = LAMBDA_FUNCTIONS[function_name]
    lambda_dir = Path(__file__).parent.resolve()
    build_dir = lambda_dir / "build" / function_name

    # Auto-detect Python command if not provided
    if python_cmd is None:
        python_cmd = _detect_python_executable()

    # Determine output location based on function type
    if function_name == "reddit_populator":
        # reddit_populator goes in terraform/ root directory
        terraform_dir = lambda_dir.parent / "terraform"
    else:
        # Other functions go in terraform/app-stack/ directory
        terraform_dir = lambda_dir.parent / "terraform" / "app-stack"

    zip_path = terraform_dir / f"{function_name}.zip"

    print(f"\n=== Building Lambda function: {function_name} ===")
    print(f"Source directory: {lambda_dir}")
    print(f"Build directory: {build_dir}")
    print(f"Output zip: {zip_path}")
    print(f"Python executable: {python_cmd}")

    try:
        # 1. Validate build prerequisites
        _validate_build_prerequisites(lambda_dir, python_cmd, func)

        # 2. Validate source files exist
        validate_source_files(lambda_dir, func.source_files)

        # 3. Clean and create build directory
        _prepare_build_directory(build_dir)

        # 4. Copy source files
        copy_source_files(lambda_dir, build_dir, func.source_files)

        # 5. Install dependencies if needed
        if func.has_dependencies:
            install_dependencies(python_cmd, lambda_dir, build_dir)

        # 6. Create zip file
        create_zip_file(build_dir, zip_path)

        # 7. Cleanup build directory
        if cleanup:
            cleanup_build_directory(build_dir)

        print(f"Successfully built {function_name}")
        return zip_path

    except LambdaBuildError:
        # Re-raise LambdaBuildError as-is (already has good error messages)
        _cleanup_on_failure(build_dir)
        raise
    except Exception as e:
        # Wrap unexpected errors with context
        _cleanup_on_failure(build_dir)
        raise LambdaBuildError(
            f"Unexpected error building {function_name}: {str(e)}\n"
            f"Build directory: {build_dir}\n"
            f"Output path: {zip_path}\n"
            f"Python command: {python_cmd}"
        )


def _detect_python_executable() -> str:
    """Detect the best Python executable to use for building."""
    if PYTHON_DETECTOR_AVAILABLE:
        try:
            # Use the centralized Python detector with a simple progress indicator
            class SimpleProgress(ProgressIndicator):
                def __init__(self):
                    super().__init__(1)  # Single step for Python detection

                def success(self, msg):
                    pass

                def error(self, msg):
                    print(f"Error: {msg}")

                def warning(self, msg):
                    print(f"Warning: {msg}")

                def info(self, msg):
                    pass

            detector = PythonDetector(SimpleProgress())
            success, python_cmd = detector.detect_and_validate()
            if success and python_cmd:
                return python_cmd
        except Exception:
            pass

    # Fallback to original detection logic if detector unavailable or fails
    candidates = ["python", "python3"]

    # On Windows, also try 'py' launcher
    if os.name == "nt":
        candidates.append("py")

    for cmd in candidates:
        try:
            if shutil.which(cmd):
                # Test if command works and has pip
                result = subprocess.run(
                    [cmd, "-m", "pip", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return cmd
        except Exception:
            continue

    # Fallback to 'python' if nothing else works
    return "python"


def _validate_build_prerequisites(
    lambda_dir: Path, python_cmd: str, func: LambdaFunction
) -> None:
    """Validate all prerequisites for building a Lambda function."""
    # Check Python executable
    try:
        result = subprocess.run(
            [python_cmd, "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise LambdaBuildError(
                f"Python executable '{python_cmd}' is not working\n"
                f"Error: {result.stderr}\n"
                f"Try using a different Python executable or reinstalling Python"
            )
        print(f"  * Python version: {result.stdout.strip()}")
    except FileNotFoundError:
        raise LambdaBuildError(
            f"Python executable '{python_cmd}' not found\n"
            f"Solutions:\n"
            f"  - Install Python from https://python.org\n"
            f"  - Ensure Python is in your PATH\n"
            f"  - Try different executable: python3, py"
        )
    except subprocess.TimeoutExpired:
        raise LambdaBuildError(
            f"Python executable '{python_cmd}' timed out - may be broken"
        )

    # Check pip availability if dependencies are needed
    if func.has_dependencies:
        try:
            result = subprocess.run(
                [python_cmd, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise LambdaBuildError(
                    f"pip is not available with Python executable '{python_cmd}'\n"
                    f"Error: {result.stderr}\n"
                    f"Solution: Install pip or use a different Python executable"
                )
            print(f"  * pip version: {result.stdout.strip()}")
        except Exception as e:
            raise LambdaBuildError(f"Cannot validate pip availability: {e}")

    # Check requirements.txt if dependencies are needed
    if func.has_dependencies:
        requirements_file = lambda_dir / "requirements.txt"
        if not requirements_file.exists():
            raise LambdaBuildError(
                f"requirements.txt not found at {requirements_file}\n"
                f"This file is required for {func.name} dependencies"
            )

        # Validate requirements.txt is readable and not empty
        try:
            content = requirements_file.read_text().strip()
            if not content:
                raise LambdaBuildError(
                    f"requirements.txt is empty: {requirements_file}\n"
                    f"Expected to contain package dependencies for {func.name}"
                )
            print(
                f"  * Found requirements.txt with {len(content.splitlines())} dependencies"
            )
        except Exception as e:
            raise LambdaBuildError(f"Cannot read requirements.txt: {e}")


def _prepare_build_directory(build_dir: Path) -> None:
    """Prepare the build directory with proper error handling."""
    try:
        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)
        print(f"  * Prepared build directory: {build_dir}")
    except PermissionError:
        raise LambdaBuildError(
            f"Permission denied creating build directory: {build_dir}\n"
            f"Solutions:\n"
            f"  - Run with administrator/sudo privileges\n"
            f"  - Check if files are locked by another process\n"
            f"  - Ensure you have write permissions to the project directory"
        )
    except Exception as e:
        raise LambdaBuildError(f"Cannot prepare build directory {build_dir}: {e}")


def _cleanup_on_failure(build_dir: Path) -> None:
    """Clean up build directory on failure."""
    try:
        if build_dir.exists():
            shutil.rmtree(build_dir)
    except Exception:
        # Don't raise errors during cleanup
        pass


def main():
    """Main entry point for building a single Lambda function."""
    if len(sys.argv) != 2:
        print("Usage: python build_lambda.py <function_name>")
        print(f"Available functions: {', '.join(LAMBDA_FUNCTIONS.keys())}")
        sys.exit(1)

    function_name = sys.argv[1]

    try:
        zip_path = build_lambda_function(function_name)
        print("\nBuild completed successfully!")
        print(f"Output: {zip_path}")

    except LambdaBuildError as e:
        print(f"\nBuild failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBuild interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
