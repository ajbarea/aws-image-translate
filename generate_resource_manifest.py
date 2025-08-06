#!/usr/bin/env python3
"""
Generate resource manifest for deployed resources.
Run this after deployment to create tracking files for easy cleanup.
"""

import subprocess
import sys
from pathlib import Path

from deployment_logic.progress_indicator import ProgressIndicator
from deployment_logic.resource_naming import ResourceNameGenerator
from deployment_logic.resource_tracker import ResourceTracker


def get_aws_info():
    """Get AWS account ID and region from AWS CLI"""
    try:
        # Get AWS account ID
        result = subprocess.run(
            [
                "aws",
                "sts",
                "get-caller-identity",
                "--query",
                "Account",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print("❌ Failed to get AWS account ID. Make sure AWS CLI is configured.")
            return None, None

        account_id = result.stdout.strip()

        # Get AWS region
        result = subprocess.run(
            ["aws", "configure", "get", "region"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print("❌ Failed to get AWS region. Make sure AWS CLI is configured.")
            return None, None

        region = result.stdout.strip()

        return account_id, region

    except Exception as e:
        print(f"❌ Error getting AWS info: {e}")
        return None, None


def main():
    print("🔍 Generating resource manifest for deployed resources...")

    # Get AWS info
    account_id, region = get_aws_info()
    if not account_id or not region:
        print("❌ Cannot proceed without AWS account information")
        return False

    print(f"📋 AWS Account: {account_id}")
    print(f"🌍 AWS Region: {region}")

    # Initialize components
    root_dir = Path(__file__).parent
    progress = ProgressIndicator(5)

    # Create resource name generator
    resource_name_generator = ResourceNameGenerator(account_id, region, progress)

    # Create resource tracker
    tracker = ResourceTracker(root_dir, account_id, region)

    print("\n📝 Tracking predicted resources...")

    # Track all predicted resources based on naming patterns
    tracker.track_predicted_resources(resource_name_generator)

    # Save the manifest
    print("💾 Saving resource manifest...")
    if tracker.save_manifest():
        print(f"✅ Resource manifest saved to: {tracker.manifest_file}")
    else:
        print("❌ Failed to save resource manifest")
        return False

    # Generate cleanup script
    print("🧹 Generating cleanup script...")
    cleanup_script = tracker.generate_cleanup_script()
    cleanup_file = root_dir / "cleanup_resources.py"

    try:
        with open(cleanup_file, "w", encoding="utf-8") as f:
            f.write(cleanup_script)
        print(f"✅ Cleanup script saved to: {cleanup_file}")
    except Exception as e:
        print(f"❌ Failed to save cleanup script: {e}")
        return False

    # Generate human-readable summary
    print("📄 Generating resource summary...")
    summary = tracker.create_human_readable_summary()
    summary_file = root_dir / "deployed_resources.md"

    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary)
        print(f"✅ Resource summary saved to: {summary_file}")
    except Exception as e:
        print(f"❌ Failed to save resource summary: {e}")
        return False

    print("\n🎉 Resource tracking files generated successfully!")
    print("\nFiles created:")
    print(f"  📋 {tracker.manifest_file} - JSON manifest of all resources")
    print(f"  🧹 {cleanup_file} - Python script to clean up resources")
    print(f"  📄 {summary_file} - Human-readable summary")

    print("\n💡 Usage:")
    print("  • Review deployed_resources.md to see what was created")
    print("  • Run 'python cleanup_resources.py' to delete all resources")
    print("  • Keep these files safe for future cleanup operations")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
