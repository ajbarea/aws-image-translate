#!/usr/bin/env python3
"""
Reddit Gallery Management Script

This script helps you manage your Reddit gallery population and streaming.
Use this to:
1. Do a one-time bulk population of your gallery
2. Enable/disable the real-time streaming
3. Clear duplicates if needed
"""

import json
import sys

import boto3


def get_lambda_client():
    """Get AWS Lambda client."""
    return boto3.client("lambda")


def get_eventbridge_client():
    """Get AWS EventBridge client."""
    return boto3.client("events")


def get_terraform_outputs():
    """Get Terraform outputs to find resource names."""
    import os
    import subprocess

    terraform_dir = "terraform/app-stack"
    if not os.path.exists(terraform_dir):
        print(f"❌ Terraform directory not found: {terraform_dir}")
        return {}

    try:
        result = subprocess.run(
            "terraform output -json",
            shell=True,
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        outputs = json.loads(result.stdout)
        return {
            "lambda_function_name": outputs.get(
                "reddit_populator_function_name", {}
            ).get("value"),
            "eventbridge_rule_name": outputs.get("reddit_scraper_rule_name", {}).get(
                "value"
            ),
        }
    except Exception as e:
        print(f"❌ Error getting Terraform outputs: {e}")
        return {}


def invoke_reddit_populator(
    images_per_subreddit: int = 30, real_time_mode: bool = False
):
    """Invoke the Reddit populator Lambda function."""
    lambda_client = get_lambda_client()

    # Get function name from Terraform outputs
    resources = get_terraform_outputs()
    function_name = resources.get("lambda_function_name")

    if not function_name:
        print(
            "[ERROR] Could not find Lambda function name. Make sure Terraform is deployed."
        )
        return None

    payload = {
        "images_per_subreddit": images_per_subreddit,
        "real_time_mode": real_time_mode,
        "use_stream": False if not real_time_mode else True,
    }

    print(f"Invoking {function_name} with payload: {json.dumps(payload, indent=2)}")

    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())
        print("Response:", json.dumps(result, indent=2))
        return result

    except Exception as e:
        print(f"Error invoking Lambda: {e}")
        return None


def enable_real_time_streaming():
    """Enable the EventBridge rule for real-time streaming."""
    eventbridge = get_eventbridge_client()

    # Get rule name from Terraform outputs
    resources = get_terraform_outputs()
    rule_name = resources.get("eventbridge_rule_name")

    if not rule_name:
        print(
            "[ERROR] Could not find EventBridge rule name. Make sure Terraform is deployed."
        )
        return

    try:
        eventbridge.enable_rule(Name=rule_name)
        print(f"[SUCCESS] Enabled real-time streaming rule: {rule_name}")
    except Exception as e:
        print(f"[ERROR] Error enabling rule: {e}")


def disable_real_time_streaming():
    """Disable the EventBridge rule for real-time streaming."""
    eventbridge = get_eventbridge_client()

    # Get rule name from Terraform outputs
    resources = get_terraform_outputs()
    rule_name = resources.get("eventbridge_rule_name")

    if not rule_name:
        print(
            "[ERROR] Could not find EventBridge rule name. Make sure Terraform is deployed."
        )
        return

    try:
        eventbridge.disable_rule(Name=rule_name)
        print(f"[SUCCESS] Disabled real-time streaming rule: {rule_name}")
    except Exception as e:
        print(f"[ERROR] Error disabling rule: {e}")


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print(
            """
Usage: python manage_reddit_gallery.py <command>

Commands:
  populate [count]    - Do initial bulk population (default: 30 images per subreddit)
  enable-stream      - Enable real-time streaming (every 5 minutes)
  disable-stream     - Disable real-time streaming
  test-stream        - Test real-time mode once

Examples:
  python manage_reddit_gallery.py populate 50
  python manage_reddit_gallery.py enable-stream
  python manage_reddit_gallery.py disable-stream
        """
        )
        return

    command = sys.argv[1].lower()

    if command == "populate":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        print(f"[START] Starting bulk population with {count} images per subreddit...")
        print("[WARNING] Make sure real-time streaming is disabled first!")
        result = invoke_reddit_populator(
            images_per_subreddit=count, real_time_mode=False
        )
        if result:
            print("[SUCCESS] Bulk population completed!")
            print(
                "[INFO] You can now enable real-time streaming with: python manage_reddit_gallery.py enable-stream"
            )

    elif command == "enable-stream":
        print("[START] Enabling real-time streaming...")
        enable_real_time_streaming()
        print("[SUCCESS] Real-time streaming is now active (runs every 5 minutes)")

    elif command == "disable-stream":
        print("[START] Disabling real-time streaming...")
        disable_real_time_streaming()
        print("[SUCCESS] Real-time streaming is now disabled")

    elif command == "test-stream":
        print("[START] Testing real-time mode once...")
        result = invoke_reddit_populator(images_per_subreddit=3, real_time_mode=True)
        if result:
            print("[SUCCESS] Real-time test completed!")

    else:
        print(f"[ERROR] Unknown command: {command}")
        print("Run without arguments to see usage.")


if __name__ == "__main__":
    main()
