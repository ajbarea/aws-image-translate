"""
Unit tests for the OptionalFeatureHandler class.
"""

from unittest.mock import MagicMock, patch

import pytest

from deployment_logic.feature_handler import OptionalFeatureHandler
from deployment_logic.progress_indicator import ProgressIndicator


@pytest.fixture
def mock_progress_indicator():
    """Fixture to create a mock ProgressIndicator."""
    return MagicMock(spec=ProgressIndicator)


def create_handler(env_vars, progress_indicator):
    """Helper function to create an OptionalFeatureHandler instance."""
    return OptionalFeatureHandler(
        env_vars=env_vars,
        progress_indicator=progress_indicator,
        aws_cmd="aws",
    )


class TestOptionalFeatureHandler:
    """Tests for the OptionalFeatureHandler class."""

    # --- Reddit Credential Validation Tests ---

    def test_validate_reddit_credentials_enabled(self, mock_progress_indicator):
        """Test valid Reddit credentials."""
        env = {
            "REDDIT_CLIENT_ID": "a" * 14,
            "REDDIT_CLIENT_SECRET": "b" * 27,
            "REDDIT_USER_AGENT": "platform:app:v1.0 (by /u/user)",
        }
        handler = create_handler(env, mock_progress_indicator)
        status, msg = handler.validate_reddit_credentials()
        assert status == "enabled"
        assert "Reddit scraping enabled" in msg

    def test_validate_reddit_credentials_disabled(self, mock_progress_indicator):
        """Test disabled Reddit integration when credentials are not provided."""
        handler = create_handler({}, mock_progress_indicator)
        status, msg = handler.validate_reddit_credentials()
        assert status == "disabled"
        assert "will be disabled" in msg

    @pytest.mark.parametrize(
        "env, expected_msg_part",
        [
            (
                {
                    "REDDIT_CLIENT_SECRET": "b" * 27,
                    "REDDIT_USER_AGENT": "platform:app:v1.0 (by /u/user)",
                },
                "REDDIT_CLIENT_ID is missing",
            ),
            (
                {
                    "REDDIT_CLIENT_ID": "a" * 14,
                    "REDDIT_USER_AGENT": "platform:app:v1.0 (by /u/user)",
                },
                "REDDIT_CLIENT_SECRET is missing",
            ),
            (
                {"REDDIT_CLIENT_ID": "a" * 14, "REDDIT_CLIENT_SECRET": "b" * 27},
                "REDDIT_USER_AGENT is missing",
            ),
            (
                {
                    "REDDIT_CLIENT_ID": "a" * 10,
                    "REDDIT_CLIENT_SECRET": "b" * 27,
                    "REDDIT_USER_AGENT": "platform:app:v1.0 (by /u/user)",
                },
                "length should be 14-30",
            ),
            (
                {
                    "REDDIT_CLIENT_ID": "a" * 14,
                    "REDDIT_CLIENT_SECRET": "b" * 10,
                    "REDDIT_USER_AGENT": "platform:app:v1.0 (by /u/user)",
                },
                "length should be 20-50",
            ),
            (
                {
                    "REDDIT_CLIENT_ID": "a" * 14,
                    "REDDIT_CLIENT_SECRET": "b" * 27,
                    "REDDIT_USER_AGENT": "invalid-agent",
                },
                "format should be",
            ),
            (
                {
                    "REDDIT_CLIENT_ID": "your_client_id_here",
                    "REDDIT_CLIENT_SECRET": "b" * 27,
                    "REDDIT_USER_AGENT": "platform:app:v1.0 (by /u/user)",
                },
                "placeholder value",
            ),
        ],
    )
    def test_validate_reddit_credentials_invalid(
        self, env, expected_msg_part, mock_progress_indicator
    ):
        """Test various invalid Reddit credential scenarios."""
        handler = create_handler(env, mock_progress_indicator)
        status, msg = handler.validate_reddit_credentials()
        assert status == "invalid"
        assert expected_msg_part in msg

    # --- Google OAuth Credential Validation Tests ---

    def test_validate_google_oauth_credentials_enabled(self, mock_progress_indicator):
        """Test valid Google OAuth credentials."""
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "12345-abcdefg.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "h" * 24,
        }
        handler = create_handler(env, mock_progress_indicator)
        status, msg = handler.validate_google_oauth_credentials()
        assert status == "enabled"
        assert "Google sign-in enabled" in msg

    def test_validate_google_oauth_credentials_disabled(self, mock_progress_indicator):
        """Test disabled Google OAuth when credentials are not provided."""
        handler = create_handler({}, mock_progress_indicator)
        status, msg = handler.validate_google_oauth_credentials()
        assert status == "disabled"
        assert "will be disabled" in msg

    @pytest.mark.parametrize(
        "env, expected_msg_part",
        [
            (
                {"GOOGLE_OAUTH_CLIENT_SECRET": "h" * 24},
                "GOOGLE_OAUTH_CLIENT_ID is missing",
            ),
            (
                {"GOOGLE_OAUTH_CLIENT_ID": "12345-abcdefg.apps.googleusercontent.com"},
                "GOOGLE_OAUTH_CLIENT_SECRET is missing",
            ),
            (
                {
                    "GOOGLE_OAUTH_CLIENT_ID": "invalid-id",
                    "GOOGLE_OAUTH_CLIENT_SECRET": "h" * 24,
                },
                "must end with",
            ),
            (
                {
                    "GOOGLE_OAUTH_CLIENT_ID": "123.apps.googleusercontent.com",
                    "GOOGLE_OAUTH_CLIENT_SECRET": "h" * 24,
                },
                "format is invalid",
            ),
            (
                {
                    "GOOGLE_OAUTH_CLIENT_ID": "12345-abcdefg.apps.googleusercontent.com",
                    "GOOGLE_OAUTH_CLIENT_SECRET": "h" * 10,
                },
                "length should be 20-50",
            ),
            (
                {
                    "GOOGLE_OAUTH_CLIENT_ID": "your_google_client_id",
                    "GOOGLE_OAUTH_CLIENT_SECRET": "h" * 24,
                },
                "placeholder value",
            ),
        ],
    )
    def test_validate_google_oauth_credentials_invalid(
        self, env, expected_msg_part, mock_progress_indicator
    ):
        """Test various invalid Google OAuth credential scenarios."""
        handler = create_handler(env, mock_progress_indicator)
        status, msg = handler.validate_google_oauth_credentials()
        assert status == "invalid"
        assert expected_msg_part in msg

    # --- GitHub Connection Validation Tests ---

    @patch("subprocess.run")
    def test_validate_github_connection_enabled(
        self, mock_run, mock_progress_indicator
    ):
        """Test a valid and available GitHub connection."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"Connection": {"ConnectionStatus": "AVAILABLE"}}',
        )
        env = {
            "GITHUB_CONNECTION_ARN": "arn:aws:codestar-connections:us-east-1:123456789012:connection/a1b2c3d4"
        }
        handler = create_handler(env, mock_progress_indicator)
        status, msg = handler.validate_github_connection()
        assert status == "enabled"
        assert "CI/CD pipeline enabled" in msg

    def test_validate_github_connection_disabled(self, mock_progress_indicator):
        """Test disabled GitHub integration when ARN is not provided."""
        handler = create_handler({}, mock_progress_indicator)
        status, msg = handler.validate_github_connection()
        assert status == "disabled"
        assert "will be disabled" in msg

    @patch("subprocess.run")
    @pytest.mark.parametrize(
        "stdout, expected_msg_part",
        [
            (
                '{"Connection": {"ConnectionStatus": "PENDING"}}',
                "pending authorization",
            ),
            ('{"Connection": {"ConnectionStatus": "ERROR"}}', "error state"),
        ],
    )
    def test_validate_github_connection_invalid_states(
        self, mock_run, stdout, expected_msg_part, mock_progress_indicator
    ):
        """Test pending and error states for GitHub connection."""
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout)
        env = {
            "GITHUB_CONNECTION_ARN": "arn:aws:codestar-connections:us-east-1:123456789012:connection/a1b2c3d4"
        }
        handler = create_handler(env, mock_progress_indicator)
        status, msg = handler.validate_github_connection()
        assert status == "invalid"
        assert expected_msg_part in msg

    def test_validate_github_connection_invalid_arn_format(
        self, mock_progress_indicator
    ):
        """Test an invalid GitHub connection ARN format."""
        env = {"GITHUB_CONNECTION_ARN": "invalid-arn"}
        handler = create_handler(env, mock_progress_indicator)
        status, msg = handler.validate_github_connection()
        assert status == "invalid"
        assert "format is invalid" in msg

    # --- Report Generation Tests ---

    @patch.object(OptionalFeatureHandler, "get_reddit_status", return_value=(True, ""))
    @patch.object(
        OptionalFeatureHandler, "get_google_oauth_status", return_value=(True, "")
    )
    @patch.object(
        OptionalFeatureHandler, "get_github_cicd_status", return_value=(True, "")
    )
    def test_generate_feature_report_all_enabled(
        self, mock_github, mock_google, mock_reddit, mock_progress_indicator
    ):
        """Test feature report when all features are enabled."""
        handler = create_handler({}, mock_progress_indicator)
        report = handler.generate_feature_report()
        assert "Reddit Integration:  ENABLED" in report
        assert "Google OAuth:        ENABLED" in report
        assert "GitHub CI/CD:        ENABLED" in report
        assert (
            "Enabled features: Reddit content scraping, Google sign-in, CI/CD pipeline"
            in report
        )

    @patch.object(OptionalFeatureHandler, "get_reddit_status", return_value=(False, ""))
    @patch.object(
        OptionalFeatureHandler, "get_google_oauth_status", return_value=(False, "")
    )
    @patch.object(
        OptionalFeatureHandler, "get_github_cicd_status", return_value=(False, "")
    )
    def test_generate_feature_report_all_disabled(
        self, mock_github, mock_google, mock_reddit, mock_progress_indicator
    ):
        """Test feature report when all features are disabled."""
        handler = create_handler({}, mock_progress_indicator)
        report = handler.generate_feature_report()
        assert "Reddit Integration:  DISABLED" in report
        assert "Google OAuth:        DISABLED" in report
        assert "GitHub CI/CD:        DISABLED" in report
        assert "All optional features are disabled" in report
