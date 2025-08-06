import shutil
import subprocess
import sys
from pathlib import Path


def main():
    """
    Prepares the build directory for the reddit_populator Lambda function.
    This script is designed to be cross-platform.
    """
    lambda_dir = Path(__file__).parent.resolve()
    build_dir = lambda_dir / "build" / "reddit_populator"
    requirements_file = lambda_dir / "requirements.txt"

    print(f"--- Preparing build directory: {build_dir} ---")

    # 1. Safely remove existing directory
    if build_dir.exists():
        print(f"Removing existing directory: {build_dir}")
        shutil.rmtree(build_dir)

    # 2. Recreate the directory
    print(f"Creating directory: {build_dir}")
    build_dir.mkdir(parents=True, exist_ok=True)

    # 3. Copy source files
    source_files = [
        "reddit_populator_sync.py",
        "reddit_scraper_sync.py",
        "reddit_realtime_scraper.py",
        "reddit_config.py",
        "aws_clients.py",
        "image_processor.py",
        "history_handler.py",
    ]
    print("Copying source files...")
    for file_name in source_files:
        source_path = lambda_dir / file_name
        if source_path.exists():
            shutil.copy(source_path, build_dir / file_name)
            print(f"  - Copied {file_name}")
        else:
            print(f"  - WARNING: Source file not found: {file_name}")

    # 4. Install dependencies
    print(f"Installing dependencies from {requirements_file}...")
    if not requirements_file.exists():
        print(f"--- ERROR: requirements.txt not found at {requirements_file} ---")
        sys.exit(1)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(build_dir),
                "-r",
                str(requirements_file),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print("Dependencies installed successfully.")
        if result.stdout:
            print("PIP STDOUT:", result.stdout)
    except subprocess.CalledProcessError as e:
        print("--- ERROR: Failed to install dependencies ---")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        sys.exit(1)

    # 6. Create zip file
    print("Creating zip file...")
    # The archive will be created in the terraform directory
    shutil.make_archive(
        str(lambda_dir.parent / "terraform" / "reddit_populator"),
        "zip",
        root_dir=str(build_dir),
    )
    print("--- Reddit populator build directory is ready. ---")


if __name__ == "__main__":
    main()
