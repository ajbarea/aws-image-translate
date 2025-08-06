#!/usr/bin/env python3
"""
Simple linting and testing script for the Lenslate project.

This script runs the following tools in sequence:
1. isort     - Import sorting check
2. flake8    - Python linting
3. pytest    - Python tests
4. npm install - Installs JS dependencies
5. eslint    - JavaScript linting with fixes
6. stylelint - CSS linting
7. npm test  - JavaScript/Node.js tests
"""

import shutil
import subprocess
import sys
from typing import List, Tuple


def check_npm_available() -> bool:
    """Check if npm is available in the system."""
    return shutil.which("npm") is not None


def run_command(command: List[str], description: str) -> Tuple[bool, str]:
    """
    Run a shell command and return success status and output.

    Args:
        command: List of command parts to execute
        description: Human-readable description of what the command does

    Returns:
        Tuple of (success: bool, output: str)
    """
    print(f"\n🔍 {description}...")

    # On Windows, 'npx' might need to be 'npx.cmd'
    if sys.platform == "win32" and command[0] == "npx":
        command[0] = "npx.cmd"

    print(f"   Running: {' '.join(command)}")

    try:
        # Using shell=True for globbing patterns like "**/*.css"
        result = subprocess.run(
            " ".join(command),
            capture_output=True,
            text=True,
            check=False,
            shell=True,
        )

        if result.returncode == 0:
            print(f"✅ {description} completed successfully!")
            if result.stdout.strip():
                print(f"   Output:\n{result.stdout.strip()}")
            return True, result.stdout
        else:
            print(f"❌ {description} failed!")
            # Print both stdout and stderr for better debugging
            output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
            print(f"   Error:\n{output}")
            return False, output

    except FileNotFoundError:
        error_msg = f"Command not found: {command[0]}"
        print(f"❌ {description} failed - {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {description} failed - {error_msg}")
        return False, error_msg


def main():
    """Main function that runs all linting and testing commands."""
    print("🚀 Starting Lenslate linting and testing process...")
    print("=" * 60)

    # Define base commands for Python
    commands = [
        (["isort", "."], "Sorting imports with isort"),
        (["black", "."], "Formatting Python code with black"),
        (
            ["flake8", ".", "--exclude=your_deployment/cleanup_resources.py"],
            "Linting Python code with flake8",
        ),
        (["pytest"], "Running Python tests with pytest"),
    ]

    # Conditionally add JS/CSS commands if npm is available
    if check_npm_available():
        js_commands = [
            (["npm", "install"], "Installing npm dependencies"),
            (
                ["npx", "eslint", ".", "--fix"],
                "Linting JavaScript with ESLint",
            ),
            (["npx", "stylelint", "**/*.css", "--fix"], "Linting CSS with Stylelint"),
            (["npm", "test"], "Running JavaScript tests with npm"),
        ]
        commands.extend(js_commands)
    else:
        print("⚠️  Warning: npm not found in PATH. Skipping all JavaScript/CSS checks.")
        print("   To fix this, install Node.js from https://nodejs.org/")

    # Track results
    results = []
    all_passed = True

    # Run each command
    for command, description in commands:
        success, _ = run_command(command, description)
        results.append((description, success))
        if not success:
            all_passed = False
            # Stop on first failure
            print("\nStopping script due to a failing check.")
            break

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")

    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {status}: {description}")

    if all_passed:
        print("\n🎉 All checks passed! Your code is ready to go!")
        sys.exit(0)
    else:
        print("\n⚠️  Some checks failed. Please review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
