#!/usr/bin/env python3
"""
Sync frontend files to S3 and invalidate CloudFront cache
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import boto3


# ANSI color codes
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def colorize(text, color):
    """Add color to text if stdout supports it"""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


def print_info(message):
    """Print info message with blue color"""
    print(colorize(f"[INFO] {message}", Colors.BLUE))


def print_success(message):
    """Print success message with green color"""
    print(colorize(f"[SUCCESS] {message}", Colors.GREEN))


def print_error(message):
    """Print error message with red color"""
    print(colorize(f"[ERROR] {message}", Colors.RED))


def print_warning(message):
    """Print warning message with yellow color"""
    print(colorize(f"[WARNING] {message}", Colors.YELLOW))


def format_url(url):
    """Format URL with cyan color and underline"""
    return colorize(url, Colors.CYAN + Colors.UNDERLINE)


def format_id(id_value):
    """Format ID with bold yellow color"""
    return colorize(id_value, Colors.YELLOW + Colors.BOLD)


def get_cloudfront_distribution_id():
    """Get CloudFront distribution ID from environment or terraform state"""
    try:
        dist_id = os.environ.get("CLOUDFRONT_DISTRIBUTION_ID")
        if dist_id:
            return dist_id

        result = subprocess.run(
            ["terraform", "output", "-raw", "cloudfront_distribution_id"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print_error(f"Failed to get CloudFront distribution ID: {e}")

    return None


def get_cloudfront_url():
    """Get CloudFront distribution URL from environment or terraform state"""
    try:
        url = os.environ.get("CLOUDFRONT_URL")
        if url:
            return url

        result = subprocess.run(
            ["terraform", "output", "-raw", "cloudfront_url"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # Construct URL from distribution ID if available
    dist_id = get_cloudfront_distribution_id()
    if dist_id:
        return f"https://{dist_id}.cloudfront.net"

    return None


def get_cloudfront_invalidations_console_url():
    """Get CloudFront invalidations console URL from environment or terraform state"""
    try:
        url = os.environ.get("CLOUDFRONT_INVALIDATIONS_CONSOLE_URL")
        if url:
            return url

        result = subprocess.run(
            ["terraform", "output", "-raw", "cloudfront_invalidations_console_url"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # Fallback to constructing URL from distribution ID if available
    dist_id = get_cloudfront_distribution_id()
    if dist_id:
        return f"https://us-east-1.console.aws.amazon.com/cloudfront/v4/home?region=us-east-1#/distributions/{dist_id}/invalidations"

    return None


def get_s3_bucket_name():
    """Get S3 bucket name from environment or terraform state"""
    try:
        bucket = os.environ.get("S3_FRONTEND_BUCKET")
        if bucket:
            return bucket
        result = subprocess.run(
            ["terraform", "output", "-raw", "frontend_s3_bucket_name"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def sync_frontend_files():
    """Sync frontend files to S3 using AWS CLI"""
    print_info("Syncing frontend files to S3...")

    bucket_name = get_s3_bucket_name()
    if not bucket_name:
        print_error("Could not determine S3 bucket name")
        return False

    frontend_dir = Path("../../frontend")
    if not frontend_dir.exists():
        print_error("Frontend directory not found")
        return False

    try:
        # AWS CLI sync command with exclusions
        sync_command = [
            "aws",
            "s3",
            "sync",
            "../../frontend/",
            f"s3://{bucket_name}/",
            "--delete",
            "--cache-control",
            "max-age=300",
            "--exclude",
            ".DS_Store",
            "--exclude",
            "*.tmp",
            "--exclude",
            "Thumbs.db",
        ]

        print(f"   {colorize('[INFO]', Colors.BLUE)} Running: {' '.join(sync_command)}")

        result = subprocess.run(sync_command, capture_output=True, text=True, cwd=".")

        if result.returncode == 0:
            if result.stdout.strip():
                print(f"   {colorize('[INFO]', Colors.BLUE)} Files synced:")
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        print(f"      {line}")
            else:
                print(
                    f"   {colorize('[INFO]', Colors.BLUE)} No files needed syncing (all up to date)"
                )

            print_success("Successfully synced frontend files to S3")
            return True
        else:
            print_error("AWS S3 sync failed:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False

    except FileNotFoundError:
        print_error("AWS CLI not found. Please install AWS CLI:")
        print(
            f"   {format_url('https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html')}"
        )
        return False
    except Exception as e:
        print_error(f"Failed to sync files to S3: {e}")
        return False


def invalidate_cloudfront():
    """Invalidate CloudFront cache"""
    print_info("Invalidating CloudFront cache...")

    dist_id = get_cloudfront_distribution_id()
    if not dist_id:
        print_error("Could not determine CloudFront distribution ID")
        return False

    try:
        cloudfront = boto3.client("cloudfront")

        response = cloudfront.create_invalidation(
            DistributionId=dist_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": f"frontend-sync-{int(time.time())}",
            },
        )

        invalidation_id = response["Invalidation"]["Id"]
        print_success(f"CloudFront invalidation created: {format_id(invalidation_id)}")
        print(
            f"   {colorize('[INFO]', Colors.BLUE)} Cache invalidation may take a few minutes to complete"
        )

        console_url = get_cloudfront_invalidations_console_url()
        if console_url:
            print(
                f"   {colorize('[INFO]', Colors.BLUE)} View invalidation status: {format_url(console_url)}"
            )
        return True

    except Exception as e:
        print_error(f"Failed to invalidate CloudFront: {e}")
        return False


def main():
    """Main function"""
    print(colorize("Frontend Sync Tool", Colors.BOLD + Colors.BLUE))
    print(colorize("=" * 40, Colors.BLUE))

    sync_result = sync_frontend_files()

    if sync_result is False:
        sys.exit(1)

    # Always invalidate CloudFront cache regardless of file changes
    if not invalidate_cloudfront():
        print_warning("Cache invalidation failed")
        print("   Try refreshing your browser with Ctrl+F5")
        sys.exit(1)

    if sync_result == "no_change":
        print(
            f"\n{colorize('[SUCCESS]', Colors.GREEN)} Frontend is already up to date, but cache has been invalidated."
        )
    else:
        print(
            f"\n{colorize('[SUCCESS]', Colors.GREEN)} Frontend sync completed successfully!"
        )

    cloudfront_url = get_cloudfront_url()
    if cloudfront_url:
        print(
            f"{colorize('[INFO]', Colors.BLUE)} Your site is available at: {format_url(cloudfront_url)}"
        )
    else:
        print_warning("Could not determine CloudFront URL")

    print(colorize("   Your updated files should be available shortly", Colors.WHITE))


if __name__ == "__main__":
    main()
