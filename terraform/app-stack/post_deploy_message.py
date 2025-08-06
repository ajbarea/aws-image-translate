#!/usr/bin/env python3
"""
Post-deployment message script for Google OAuth configuration.
This script provides consistent output across Windows, Mac, and Linux.
"""

import sys


def main():
    # Get URLs from command line arguments
    if len(sys.argv) != 3:
        print("Usage: python post_deploy_message.py <cloudfront_url> <cognito_url>")
        sys.exit(1)

    cloudfront_url = sys.argv[1]
    cognito_url = sys.argv[2]

    # Print the post-deployment message
    print()
    print("Google OAuth configuration files updated!")
    print("Configuration saved to: google-oauth-config.txt")
    print(
        "Scripts generated: update-google-oauth.sh (Unix/Mac) and update-google-oauth.bat (Windows)"
    )
    print("Current URLs:")
    print(f"    CloudFront: {cloudfront_url}")
    print(f"    Cognito: {cognito_url}")
    print()
    print("To configure Google OAuth: python update-google-oauth.py")
    print()


if __name__ == "__main__":
    main()
