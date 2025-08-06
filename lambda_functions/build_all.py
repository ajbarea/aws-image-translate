#!/usr/bin/env python3
"""
Cross-platform Lambda build system for all functions.
Builds all Lambda functions in the correct order and validates outputs.
"""

import concurrent.futures
import shutil
import subprocess
import sys
import time
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

try:
    from deployment_logic.progress_indicator import ProgressIndicator
    from deployment_logic.python_detector import PythonDetector

    PYTHON_DETECTOR_AVAILABLE = True
except ImportError:
    PYTHON_DETECTOR_AVAILABLE = False

try:
    from .build_lambda import LAMBDA_FUNCTIONS, build_lambda_function
except ImportError:
    from build_lambda import LAMBDA_FUNCTIONS, build_lambda_function


class BuildAllError(Exception):
    """Custom exception for build-all errors."""

    pass


# Thread-safe printing
print_lock = Lock()


def safe_print(*args, **kwargs):
    """Thread-safe print function."""
    with print_lock:
        print(*args, **kwargs)


def build_function_wrapper(
    function_name: str, cleanup: bool = True, python_cmd: Optional[str] = None
) -> Tuple[str, bool, str]:
    """
    Wrapper function for building a single Lambda function in a thread.

    Returns:
        Tuple of (function_name, success, error_message)
    """
    try:
        zip_path = build_lambda_function(
            function_name, cleanup=cleanup, python_cmd=python_cmd
        )
        return function_name, True, str(zip_path)
    except Exception as e:
        return function_name, False, str(e)


def build_functions_parallel(
    function_names: List[str],
    max_workers: int = 3,
    cleanup: bool = True,
    python_cmd: Optional[str] = None,
) -> Dict[str, Tuple[bool, str]]:
    """
    Build multiple Lambda functions in parallel.

    Args:
        function_names: List of function names to build
        max_workers: Maximum number of parallel builds
        cleanup: Whether to clean up build directories after zip creation
        python_cmd: Python executable to use for building

    Returns:
        Dictionary mapping function names to (success, message) tuples
    """
    results = {}

    safe_print(
        f"\nBuilding {len(function_names)} Lambda functions in parallel (max {max_workers} workers)..."
    )
    if python_cmd:
        safe_print(f"Using Python executable: {python_cmd}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all build tasks
        future_to_function = {
            executor.submit(
                build_function_wrapper, func_name, cleanup, python_cmd
            ): func_name
            for func_name in function_names
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_function):
            function_name = future_to_function[future]
            try:
                func_name, success, message = future.result()
                results[func_name] = (success, message)

                if success:
                    safe_print(f"  [OK] {func_name}: {message}")
                else:
                    safe_print(f"  [FAIL] {func_name}: {message}")

            except Exception as e:
                results[function_name] = (False, f"Unexpected error: {e}")
                safe_print(f"  [ERROR] {function_name}: Unexpected error: {e}")

    return results


def build_functions_sequential(
    function_names: List[str], cleanup: bool = True, python_cmd: Optional[str] = None
) -> Dict[str, Tuple[bool, str]]:
    """
    Build Lambda functions sequentially (fallback for parallel build issues).

    Args:
        function_names: List of function names to build
        cleanup: Whether to clean up build directories after zip creation
        python_cmd: Python executable to use for building

    Returns:
        Dictionary mapping function names to (success, message) tuples
    """
    results = {}

    print(f"\nBuilding {len(function_names)} Lambda functions sequentially...")
    if python_cmd:
        print(f"Using Python executable: {python_cmd}")

    for i, function_name in enumerate(function_names, 1):
        print(f"\n[{i}/{len(function_names)}] Building {function_name}...")

        try:
            zip_path = build_lambda_function(
                function_name, cleanup=cleanup, python_cmd=python_cmd
            )
            results[function_name] = (True, str(zip_path))
            print(f"  [OK] {function_name}: {zip_path}")

        except Exception as e:
            results[function_name] = (False, str(e))
            print(f"  [FAIL] {function_name}: {e}")

    return results


def validate_build_outputs() -> List[str]:
    """
    Validate that all required zip files were created successfully.

    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []
    lambda_dir = Path(__file__).parent.resolve()
    terraform_root = lambda_dir.parent / "terraform"
    terraform_app_stack = terraform_root / "app-stack"

    print("\nValidating build outputs...")

    for function_name in LAMBDA_FUNCTIONS.keys():
        # Determine expected location based on function type
        if function_name == "reddit_populator":
            zip_path = terraform_root / f"{function_name}.zip"
            location_desc = "terraform/"
        else:
            zip_path = terraform_app_stack / f"{function_name}.zip"
            location_desc = "terraform/app-stack/"

        print(f"Checking {function_name}.zip in {location_desc}...")

        if not zip_path.exists():
            errors.append(f"Missing zip file: {zip_path}")
            continue

        # Check file size (should not be empty)
        zip_size = zip_path.stat().st_size
        if zip_size == 0:
            errors.append(f"Empty zip file: {zip_path}")
            continue

        # Minimum reasonable size check (1KB)
        if zip_size < 1024:
            errors.append(f"Suspiciously small zip file ({zip_size} bytes): {zip_path}")
            continue

        print(f"  [OK] {function_name}.zip ({zip_size:,} bytes)")

    return errors


def print_build_summary(
    results: Dict[str, Tuple[bool, str]], start_time: float
) -> None:
    """Print a summary of the build results."""
    end_time = time.time()
    duration = end_time - start_time

    successful = [name for name, (success, _) in results.items() if success]
    failed = [name for name, (success, _) in results.items() if not success]

    print(f"\n{'=' * 60}")
    print(f"Build Summary ({duration:.1f}s)")
    print(f"{'=' * 60}")

    if successful:
        print(f"Successful builds ({len(successful)}):")
        for name in successful:
            print(f"  * {name}")

    if failed:
        print(f"\nFailed builds ({len(failed)}):")
        for name in failed:
            _, error_msg = results[name]
            print(f"  * {name}: {error_msg}")

    print(f"\nTotal: {len(successful)}/{len(results)} functions built successfully")


def build_all_lambda_functions(
    parallel: bool = True,
    max_workers: int = 3,
    cleanup: bool = True,
    python_cmd: Optional[str] = None,
) -> bool:
    """
    Build all Lambda functions with error handling.

    Args:
        parallel: Whether to build functions in parallel
        max_workers: Maximum number of parallel workers
        cleanup: Whether to clean up build directories after zip creation
        python_cmd: Python executable to use for building (auto-detected if None)

    Returns:
        True if all builds successful, False otherwise
    """
    start_time = time.time()
    function_names = list(LAMBDA_FUNCTIONS.keys())

    print("Starting Lambda build process...")
    print(f"Functions to build: {', '.join(function_names)}")

    # Auto-detect Python command if not provided
    if python_cmd is None:
        python_cmd = _detect_python_executable()
        print(f"Auto-detected Python executable: {python_cmd}")
    else:
        print(f"Using provided Python executable: {python_cmd}")

    # Validate Python executable before starting builds
    if not _validate_python_executable(python_cmd):
        print(f"ERROR: Python executable '{python_cmd}' is not suitable for building")
        return False

    # Build functions
    if parallel:
        try:
            results = build_functions_parallel(
                function_names, max_workers, cleanup, python_cmd
            )
        except Exception as e:
            print(
                f"WARNING: Parallel build failed ({e}), falling back to sequential..."
            )
            results = build_functions_sequential(function_names, cleanup, python_cmd)
    else:
        results = build_functions_sequential(function_names, cleanup, python_cmd)

    # Validate outputs
    validation_errors = validate_build_outputs()

    # Print summary
    print_build_summary(results, start_time)

    # Check for failures
    failed_builds = [name for name, (success, _) in results.items() if not success]

    if failed_builds:
        print(f"\nBuild failed for: {', '.join(failed_builds)}")
        _provide_build_failure_guidance(failed_builds, results, python_cmd)
        return False

    if validation_errors:
        print("\nValidation errors:")
        for error in validation_errors:
            print(f"  * {error}")
        _provide_validation_failure_guidance(validation_errors, python_cmd)
        return False

    print("\nAll Lambda functions built successfully!")
    return True


def _detect_python_executable() -> str:
    """Detect the best Python executable to use for building."""
    if PYTHON_DETECTOR_AVAILABLE:
        try:
            # Use the Python detector with a simple progress indicator
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
    if sys.platform.startswith("win"):
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


def _validate_python_executable(python_cmd: str) -> bool:
    """Validate that the Python executable is suitable for building."""
    try:
        # Test Python version
        result = subprocess.run(
            [python_cmd, "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(f"ERROR: Python executable '{python_cmd}' is not working")
            return False

        print(f"Python version: {result.stdout.strip()}")

        # Test pip availability
        result = subprocess.run(
            [python_cmd, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print(f"ERROR: pip is not available with Python executable '{python_cmd}'")
            print("Solution: Install pip or use a different Python executable")
            return False

        print(f"pip version: {result.stdout.strip()}")
        return True

    except FileNotFoundError:
        print(f"ERROR: Python executable '{python_cmd}' not found")
        print("Solutions:")
        print("  - Install Python from https://python.org")
        print("  - Ensure Python is in your PATH")
        print("  - Try different executable: python3, py")
        return False
    except Exception as e:
        print(f"ERROR: Cannot validate Python executable '{python_cmd}': {e}")
        return False


def _provide_build_failure_guidance(
    failed_builds: List[str], results: Dict[str, Tuple[bool, str]], python_cmd: str
) -> None:
    """Provide specific guidance for build failures."""
    print(f"\n{'=' * 60}")
    print("BUILD FAILURE GUIDANCE")
    print(f"{'=' * 60}")

    print(f"Failed functions: {', '.join(failed_builds)}")
    print(f"Python executable used: {python_cmd}")

    # Analyze common error patterns
    all_errors = []
    for func_name in failed_builds:
        _, error_msg = results[func_name]
        all_errors.append(error_msg.lower())

    combined_errors = " ".join(all_errors)

    print("\nCommon solutions:")

    if "permission" in combined_errors or "access" in combined_errors:
        print("* PERMISSION ISSUES:")
        print("  - Run with administrator/sudo privileges")
        print("  - Check if files are locked by antivirus or other processes")
        print("  - Use virtual environment to avoid system conflicts")

    if "network" in combined_errors or "connection" in combined_errors:
        print("* NETWORK ISSUES:")
        print("  - Check internet connection")
        print("  - Configure proxy if needed")
        print("  - Try again later if package repositories are down")

    if "module" in combined_errors or "import" in combined_errors:
        print("* DEPENDENCY ISSUES:")
        print(f"  - Update pip: {python_cmd} -m pip install --upgrade pip")
        print(
            f"  - Install requirements: {python_cmd} -m pip install -r lambda_functions/requirements.txt"
        )

    print("\nManual troubleshooting:")
    print("1. Try building individual functions:")
    for func_name in failed_builds:
        print(f"   {python_cmd} lambda_functions/build_lambda.py {func_name}")

    print("2. Check Python environment:")
    print(f"   {python_cmd} --version")
    print(f"   {python_cmd} -m pip --version")

    print("3. Clean and retry:")
    print("   - Delete lambda_functions/build/ directory")
    print("   - Delete existing .zip files in terraform/")
    print("   - Run build again")


def _provide_validation_failure_guidance(
    validation_errors: List[str], python_cmd: str
) -> None:
    """Provide guidance for validation failures."""
    print(f"\n{'=' * 60}")
    print("VALIDATION FAILURE GUIDANCE")
    print(f"{'=' * 60}")

    print("Validation errors indicate that zip files were created but have issues:")
    for error in validation_errors:
        print(f"  • {error}")

    print("\nSolutions:")
    print("1. Clean build and retry:")
    print("   - Delete lambda_functions/build/ directory")
    print("   - Delete problematic .zip files")
    print(f"   - Run: {python_cmd} lambda_functions/build_all.py")

    print("2. Check disk space and permissions")
    print("3. Verify source files are not corrupted")
    print("4. Check antivirus software isn't interfering with zip creation")


def main():
    """Main entry point for building all Lambda functions."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build all Lambda functions with error handling"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Build functions sequentially instead of in parallel",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Maximum number of parallel workers (default: 3)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup of build directories after zip creation",
    )
    parser.add_argument(
        "--python-cmd",
        type=str,
        help="Python executable to use for building (auto-detected if not specified)",
    )

    args = parser.parse_args()

    try:
        success = build_all_lambda_functions(
            parallel=not args.sequential,
            max_workers=args.workers,
            cleanup=not args.no_cleanup,
            python_cmd=args.python_cmd,
        )

        if not success:
            print("\nBuild process failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nBuild interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
