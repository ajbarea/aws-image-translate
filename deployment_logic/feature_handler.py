"""
Manages optional features like Reddit and Google OAuth integrations.
"""

import json
import re
import subprocess
from typing import Dict, Tuple

from .progress_indicator import ProgressIndicator


class OptionalFeatureHandler:
    """
    Manage optional integrations (Reddit, Google OAuth, CI/CD).
    Validates optional feature credentials and provides status reporting.
    """

    def __init__(
        self,
        env_vars: Dict[str, str],
        progress_indicator: ProgressIndicator,
        aws_cmd: str,
    ):
        """Initialize with environment variables and dependencies"""
        self.env_vars = env_vars
        self.progress = progress_indicator
        self.aws_cmd = aws_cmd

    def validate_reddit_credentials(self) -> Tuple[str, str]:
        """
        Validate Reddit API credentials with format checking.
        Returns (status, message) where status is 'enabled', 'disabled', or 'invalid'.
        """
        try:
            client_id = self.env_vars.get("REDDIT_CLIENT_ID", "").strip()
            client_secret = self.env_vars.get("REDDIT_CLIENT_SECRET", "").strip()
            user_agent = self.env_vars.get("REDDIT_USER_AGENT", "").strip()

            # Check if Reddit credentials are provided
            if not client_id and not client_secret:
                return "disabled", "Not configured - Reddit scraping will be disabled"

            # Validate Reddit client ID format
            if not client_id:
                return "invalid", "REDDIT_CLIENT_ID is missing"

            if len(client_id) < 14 or len(client_id) > 30:
                return "invalid", "REDDIT_CLIENT_ID length should be 14-30 characters"

            if not re.match(r"^[A-Za-z0-9_-]+$", client_id):
                return (
                    "invalid",
                    "REDDIT_CLIENT_ID contains invalid characters (use only letters, numbers, underscore, hyphen)",
                )

            # Check for placeholder values
            if self._is_placeholder_value(client_id):
                return "invalid", "REDDIT_CLIENT_ID appears to be a placeholder value"

            # Validate Reddit client secret format
            if not client_secret:
                return "invalid", "REDDIT_CLIENT_SECRET is missing"

            if len(client_secret) < 20 or len(client_secret) > 50:
                return (
                    "invalid",
                    "REDDIT_CLIENT_SECRET length should be 20-50 characters",
                )

            if not re.match(r"^[A-Za-z0-9_-]+$", client_secret):
                return "invalid", "REDDIT_CLIENT_SECRET contains invalid characters"

            if self._is_placeholder_value(client_secret):
                return (
                    "invalid",
                    "REDDIT_CLIENT_SECRET appears to be a placeholder value",
                )

            # Validate Reddit user agent format
            if not user_agent:
                return (
                    "invalid",
                    "REDDIT_USER_AGENT is missing (required for Reddit API)",
                )

            # Reddit user agent should follow format: platform:app_name:version (by /u/username)
            user_agent_pattern = r"^[^:]+:[^:]+:v?\d+\.\d+.*"
            if not re.match(user_agent_pattern, user_agent):
                return (
                    "invalid",
                    "REDDIT_USER_AGENT format should be 'platform:app_name:version (by /u/username)'",
                )

            if self._is_placeholder_value(user_agent):
                return "invalid", "REDDIT_USER_AGENT appears to be a placeholder value"

            # All validations passed
            return "enabled", "Valid credentials - Reddit scraping enabled"

        except Exception as e:
            return "invalid", f"Error validating Reddit credentials: {e}"

    def validate_google_oauth_credentials(self) -> Tuple[str, str]:
        """
        Validate Google OAuth credentials with proper domain checking.
        Returns (status, message) where status is 'enabled', 'disabled', or 'invalid'.
        """
        try:
            client_id = self.env_vars.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
            client_secret = self.env_vars.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()

            # Check if Google OAuth credentials are provided
            if not client_id and not client_secret:
                return "disabled", "Not configured - Google sign-in will be disabled"

            # Validate Google OAuth client ID format
            if not client_id:
                return "invalid", "GOOGLE_OAUTH_CLIENT_ID is missing"

            if self._is_placeholder_value(client_id):
                return (
                    "invalid",
                    "GOOGLE_OAUTH_CLIENT_ID appears to be a placeholder value",
                )

            # Google OAuth client IDs should end with .apps.googleusercontent.com
            if not client_id.endswith(".apps.googleusercontent.com"):
                return (
                    "invalid",
                    "GOOGLE_OAUTH_CLIENT_ID must end with '.apps.googleusercontent.com'",
                )

            # Check client ID structure: should be like 123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com
            client_id_pattern = r"^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$"
            if not re.match(client_id_pattern, client_id):
                return (
                    "invalid",
                    "GOOGLE_OAUTH_CLIENT_ID format is invalid (should be numeric-alphanumeric.apps.googleusercontent.com)",
                )

            # Validate Google OAuth client secret format
            if not client_secret:
                return "invalid", "GOOGLE_OAUTH_CLIENT_SECRET is missing"

            # Google OAuth client secrets are typically 24 characters, alphanumeric with some special chars
            if len(client_secret) < 20 or len(client_secret) > 50:
                return (
                    "invalid",
                    "GOOGLE_OAUTH_CLIENT_SECRET length should be 20-50 characters",
                )

            # Google client secrets typically contain letters, numbers, hyphens, and underscores
            if not re.match(r"^[A-Za-z0-9_-]+$", client_secret):
                return (
                    "invalid",
                    "GOOGLE_OAUTH_CLIENT_SECRET contains invalid characters",
                )

            if self._is_placeholder_value(client_secret):
                return (
                    "invalid",
                    "GOOGLE_OAUTH_CLIENT_SECRET appears to be a placeholder value",
                )

            # All validations passed
            return "enabled", "Valid credentials - Google sign-in enabled"

        except Exception as e:
            return "invalid", f"Error validating Google OAuth credentials: {e}"

    def validate_github_connection(self) -> Tuple[str, str]:
        """
        Validate GitHub connection ARN with AWS API calls.
        Returns (status, message) where status is 'enabled', 'disabled', or 'invalid'.
        """
        try:
            github_arn = self.env_vars.get("GITHUB_CONNECTION_ARN", "").strip()

            # Check if GitHub connection ARN is provided
            if not github_arn:
                return "disabled", "Not configured - CI/CD pipeline will be disabled"

            # Validate GitHub connection ARN format
            if not self._validate_github_arn_format(github_arn):
                return "invalid", "GitHub connection ARN format is invalid"

            # Test connection using AWS API calls
            connection_status = self._test_github_connection_access(github_arn)
            if connection_status == "available":
                return "enabled", "Valid connection - CI/CD pipeline enabled"
            elif connection_status == "pending":
                return (
                    "invalid",
                    "GitHub connection is pending authorization - complete setup in AWS Console",
                )
            elif connection_status == "error":
                return (
                    "invalid",
                    "GitHub connection is in error state - check AWS Console",
                )
            else:
                return "invalid", "GitHub connection could not be validated"

        except Exception as e:
            return "invalid", f"Error validating GitHub connection: {e}"

    def _validate_github_arn_format(self, arn: str) -> bool:
        """Validate GitHub connection ARN format"""
        # Expected format: arn:aws:codestar-connections:region:account:connection/connection-id
        # or: arn:aws:codeconnections:region:account:connection/connection-id
        arn_pattern = r"^arn:aws:(codestar-connections|codeconnections):[a-z0-9-]+:\d{12}:connection/[a-f0-9-]+$"
        return re.match(arn_pattern, arn) is not None

    def _test_github_connection_access(self, github_arn: str) -> str:
        """
        Test GitHub connection access using AWS API calls.
        Returns 'available', 'pending', 'error', or 'failed'.
        """
        # Try codestar-connections first (original service)
        status = self._test_connection_with_service("codestar-connections", github_arn)
        if status != "failed":
            return status

        # Try codeconnections (newer service name)
        status = self._test_connection_with_service("codeconnections", github_arn)
        return status

    def _test_connection_with_service(self, service_name: str, github_arn: str) -> str:
        """Test connection access with a specific AWS service name"""
        try:
            result = subprocess.run(
                [
                    self.aws_cmd,
                    service_name,
                    "get-connection",
                    "--connection-arn",
                    github_arn,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                try:
                    connection_info = json.loads(result.stdout)
                    connection_data = connection_info.get("Connection", {})
                    connection_status = connection_data.get(
                        "ConnectionStatus", "UNKNOWN"
                    )

                    if connection_status == "AVAILABLE":
                        return "available"
                    elif connection_status == "PENDING":
                        return "pending"
                    elif connection_status == "ERROR":
                        return "error"
                    else:
                        return "available"  # Assume working if we can access it

                except json.JSONDecodeError:
                    return "available"  # If we can access it, assume it's working
            else:
                return "failed"

        except (subprocess.TimeoutExpired, Exception):
            return "failed"

    def _is_placeholder_value(self, value: str) -> bool:
        """Check if a value appears to be a placeholder"""
        if not value:
            return False

        placeholder_patterns = [
            "your_client_id_here",
            "your_client_secret_here",
            "your_google_client_id",
            "your_reddit_client",
            "YourUsernameHere",
            "YOUR_ACCOUNT_ID",
            "YOUR_CONNECTION_ID",
            "your_",
            "YOUR_",
            "example",
            "placeholder",
            "dummy",
            "test_client",
            "sample_",
        ]

        value_lower = value.lower()
        return any(pattern.lower() in value_lower for pattern in placeholder_patterns)

    def get_reddit_status(self) -> Tuple[bool, str]:
        """Check Reddit integration status"""
        status, message = self.validate_reddit_credentials()
        return status == "enabled", message

    def get_google_oauth_status(self) -> Tuple[bool, str]:
        """Check Google OAuth integration status"""
        status, message = self.validate_google_oauth_credentials()
        return status == "enabled", message

    def get_github_cicd_status(self) -> Tuple[bool, str]:
        """Check GitHub CI/CD integration status"""
        status, message = self.validate_github_connection()
        return status == "enabled", message

    def generate_feature_report(self) -> str:
        """Generate report of enabled/disabled features"""
        reddit_enabled, reddit_msg = self.get_reddit_status()
        google_enabled, google_msg = self.get_google_oauth_status()
        github_enabled, github_msg = self.get_github_cicd_status()

        report_lines = [
            "\n" + "=" * 60,
            "OPTIONAL FEATURES STATUS",
            "=" * 60,
            f"Reddit Integration:  {'ENABLED' if reddit_enabled else 'DISABLED'}",
            f"Google OAuth:        {'ENABLED' if google_enabled else 'DISABLED'}",
            f"GitHub CI/CD:        {'ENABLED' if github_enabled else 'DISABLED'}",
            "=" * 60,
        ]

        if not any([reddit_enabled, google_enabled, github_enabled]):
            report_lines.extend(
                [
                    "All optional features are disabled.",
                    "Your application will deploy with core functionality only.",
                    "To enable features, add credentials to .env.local and redeploy.",
                    "=" * 60,
                ]
            )
        else:
            enabled_features = []
            if reddit_enabled:
                enabled_features.append("Reddit content scraping")
            if google_enabled:
                enabled_features.append("Google sign-in")
            if github_enabled:
                enabled_features.append("CI/CD pipeline")

            report_lines.extend(
                [
                    f"Enabled features: {', '.join(enabled_features)}",
                    "=" * 60,
                ]
            )

        return "\n".join(report_lines)
