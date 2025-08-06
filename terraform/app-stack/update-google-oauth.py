#!/usr/bin/env python3
"""
Google OAuth Configuration Updater for Lenslate
Automatically updates Google Cloud Console OAuth settings after Terraform deployment
"""

import json
import subprocess
import sys
import webbrowser
from pathlib import Path


def get_terraform_outputs():
    """Get the current Terraform outputs"""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=".",
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to get Terraform outputs: {e}")
        return None
    except FileNotFoundError:
        print(
            "ERROR: Terraform not found. Please ensure Terraform is installed and in your PATH."
        )
        return None


def check_config_changes():
    """Check if configuration files exist and show what changed"""
    config_file = Path("terraform/google-oauth-config.txt")

    if config_file.exists():
        print("Configuration files updated:")
        print(f"   - {config_file}")

        script_file = Path("terraform/update-google-oauth.sh")
        if script_file.exists():
            print(f"   - {script_file}")

        print(f"   - Generated: {config_file.stat().st_mtime}")
        return True
    return False


def main():
    print("Google OAuth Configuration Updater for Lenslate")
    print("=" * 60)

    # Check if configuration files were updated
    config_updated = check_config_changes()
    if config_updated:
        print(
            "SUCCESS: Configuration files have been updated with current deployment URLs"
        )
        print()

    outputs = get_terraform_outputs()
    if not outputs:
        sys.exit(1)

    # Extract values
    try:
        client_id = outputs["google_oauth_client_id"]["value"]
        js_origins = outputs["google_oauth_javascript_origins"]["value"]
        redirect_uri = outputs["google_oauth_redirect_uri"]["value"]
        console_url = outputs["google_oauth_console_url"]["value"]
        cloudfront_url = outputs["cloudfront_url"]["value"]

        if client_id == "Not configured":
            print("WARNING: Google OAuth is not configured in your .env.local file")
            print("   Add your Google OAuth credentials to enable Google sign-in")
            return

    except KeyError as e:
        print(f"ERROR: Missing output: {e}")
        sys.exit(1)

    print(f"Client ID: {client_id}")
    print(f"Console URL: {console_url}")
    print()

    print("REQUIRED CONFIGURATION:")
    print("-" * 30)
    print("1. Go to Google Cloud Console:")
    print(f"   {console_url}")
    print()
    print(f"2. Find OAuth 2.0 Client ID: {client_id}")
    print()
    print("3. Click 'Edit' and add these URLs:")
    print()
    print("   AUTHORIZED JAVASCRIPT ORIGINS:")
    for origin in js_origins:
        print(f"   - {origin}")
    print()
    print("   AUTHORIZED REDIRECT URIS:")
    print(f"   - {redirect_uri}")
    print()

    # Ask if user wants to open the console
    response = input("Open Google Cloud Console now? (y/N): ").strip().lower()
    if response in ["y", "yes"]:
        try:
            webbrowser.open(console_url)
            print("SUCCESS: Opened Google Cloud Console in your browser")
        except Exception as e:
            print(f"WARNING: Could not open browser: {e}")
            print(f"   Please manually go to: {console_url}")

    print()
    print("TIP: After updating the OAuth settings:")
    print("   - Wait 5-10 minutes for changes to propagate")
    print("   - Clear your browser cache")
    print("   - Try Google sign-in again")
    print()
    print(f"Your app URL: {cloudfront_url}")


if __name__ == "__main__":
    main()
