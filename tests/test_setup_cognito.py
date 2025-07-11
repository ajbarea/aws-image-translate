#!/usr/bin/env python3
"""
Tests for the Cognito Setup Script
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from setup_cognito import main, run_cmd


# Tests for run_cmd
@patch("subprocess.run")
def test_run_cmd_success(mock_subprocess_run):
    """Test run_cmd with a successful command execution."""
    mock_result = MagicMock()
    mock_result.stdout = "  some output  \n"
    mock_subprocess_run.return_value = mock_result

    result = run_cmd("echo 'hello'")
    assert result == "some output"
    mock_subprocess_run.assert_called_once_with(
        "echo 'hello'", shell=True, capture_output=True, text=True, check=True
    )


@patch("subprocess.run")
@patch("sys.exit")
def test_run_cmd_failure(mock_sys_exit, mock_subprocess_run, capsys):
    """Test run_cmd with a failed command execution."""
    error = subprocess.CalledProcessError(
        returncode=1, cmd="failed command", stderr="error message"
    )
    mock_subprocess_run.side_effect = error
    mock_sys_exit.side_effect = SystemExit(1)

    # The script calls sys.exit(1), which pytest will catch as a SystemExit exception.
    with pytest.raises(SystemExit) as excinfo:
        run_cmd("failed command")

    # Check that the exit code is 1
    assert excinfo.value.code == 1

    # Check that the error message was printed
    captured = capsys.readouterr()
    assert "❌ Command failed" in captured.out
    assert "Error: error message" in captured.out

    # Check that sys.exit was called with 1
    mock_sys_exit.assert_called_once_with(1)


# Tests for main
@patch("setup_cognito.run_cmd")
def test_main_success(mock_run_cmd, capsys):
    """Test the main function for a successful Cognito setup."""
    # Mock outputs for the three aws commands
    user_pool_output = {"UserPool": {"Id": "us-east-1_testpoolid", "Name": "test-pool"}}
    client_output = {
        "UserPoolClient": {
            "ClientId": "testclientid",
            "UserPoolId": "us-east-1_testpoolid",
        }
    }
    identity_pool_output = {"IdentityPoolId": "us-east-1:testidentitypoolid"}

    mock_run_cmd.side_effect = [
        json.dumps(user_pool_output),
        json.dumps(client_output),
        json.dumps(identity_pool_output),
    ]

    main()

    captured = capsys.readouterr()

    # Check that the correct commands were called
    assert mock_run_cmd.call_count == 3

    cmd1 = mock_run_cmd.call_args_list[0].args[0]
    assert "aws cognito-idp create-user-pool" in cmd1
    assert '--pool-name "aws-image-translate-dev-pool"' in cmd1

    cmd2 = mock_run_cmd.call_args_list[1].args[0]
    assert (
        "aws cognito-idp create-user-pool-client --user-pool-id us-east-1_testpoolid"
        in cmd2
    )
    assert '--client-name "dev-client"' in cmd2

    cmd3 = mock_run_cmd.call_args_list[2].args[0]
    assert "aws cognito-identity create-identity-pool" in cmd3
    assert (
        "ProviderName=cognito-idp.us-east-1.amazonaws.com/us-east-1_testpoolid" in cmd3
    )
    assert "ClientId=testclientid" in cmd3

    # Check that the output contains the expected IDs and config snippets
    assert "✅ User Pool: us-east-1_testpoolid" in captured.out
    assert "✅ Client: testclientid" in captured.out
    assert "✅ Identity Pool: us-east-1:testidentitypoolid" in captured.out

    assert "COGNITO_USER_POOL_ID=us-east-1_testpoolid" in captured.out
    assert "COGNITO_APP_CLIENT_ID=testclientid" in captured.out
    assert "COGNITO_IDENTITY_POOL_ID=us-east-1:testidentitypoolid" in captured.out

    assert 'userPoolId: "us-east-1_testpoolid"' in captured.out
    assert 'userPoolWebClientId: "testclientid"' in captured.out
    assert 'identityPoolId: "us-east-1:testidentitypoolid"' in captured.out


@patch("setup_cognito.run_cmd")
def test_main_stops_on_run_cmd_failure(mock_run_cmd):
    """Test that main stops if any run_cmd call fails."""
    # Simulate a failure on the first command by having it raise SystemExit,
    # which is what happens when run_cmd fails and calls sys.exit().
    mock_run_cmd.side_effect = SystemExit(1)

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    # The first call to run_cmd should have been made, but not subsequent ones.
    mock_run_cmd.assert_called_once()
