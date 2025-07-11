import sys
from typing import List
from unittest.mock import MagicMock, patch

import configure_storage


def run_main_with_args(args: List[str]) -> None:
    with patch.object(sys, "argv", ["configure_storage.py"] + args):
        configure_storage.main()


def test_setup_aws_prints_instructions(capsys):
    configure_storage.setup_aws()
    captured = capsys.readouterr()
    assert "AWS S3 Setup:" in captured.out
    assert "Ensure your AWS credentials are configured" in captured.out


def test_setup_gcs_prints_instructions(capsys):
    configure_storage.setup_gcs()
    captured = capsys.readouterr()
    assert "Google Cloud Storage Setup:" in captured.out
    assert "Install Google Cloud SDK" in captured.out


@patch("subprocess.run")
def test_install_gcs_dependencies_success(mock_run, capsys):
    # Simulate successful installation
    mock_proc = MagicMock(returncode=0, stderr="")
    mock_run.return_value = mock_proc
    result = configure_storage.install_gcs_dependencies()
    captured = capsys.readouterr()
    assert "Installing Google Cloud Storage dependencies..." in captured.out
    assert "✓ Successfully installed google-cloud-storage" in captured.out
    assert result is True


@patch("subprocess.run")
def test_install_gcs_dependencies_failure(mock_run, capsys):
    # Simulate failed installation
    mock_proc = MagicMock(returncode=1, stderr="error occurred")
    mock_run.return_value = mock_proc
    result = configure_storage.install_gcs_dependencies()
    captured = capsys.readouterr()
    assert "✗ Failed to install dependencies: error occurred" in captured.out
    assert result is False


@patch("configure_storage.install_gcs_dependencies")
def test_main_install_gcs(mock_install, capsys):
    run_main_with_args(["--install-gcs"])
    mock_install.assert_called_once()


@patch("configure_storage.show_status")
def test_main_status_calls_show(mock_show, capsys):
    run_main_with_args(["--status"])
    mock_show.assert_called_once()


@patch("configure_storage.show_status")
def test_main_status_exception(mock_show, capsys):
    mock_show.side_effect = Exception("fail")
    run_main_with_args(["--status"])
    captured = capsys.readouterr()
    assert "Error checking status: fail" in captured.out
    assert "Run with --setup-help to see configuration instructions" in captured.out


@patch("configure_storage.create_env_file")
def test_main_backend_aws(mock_create, capsys):
    run_main_with_args(["--backend", "aws"])
    mock_create.assert_called_once_with("aws", None, None)
    captured = capsys.readouterr()
    assert "✓ Configured storage backend: AWS" in captured.out


@patch("configure_storage.create_env_file")
def test_main_backend_gcs_missing_bucket(mock_create, capsys):
    run_main_with_args(["--backend", "gcs"])
    captured = capsys.readouterr()
    assert (
        "Error: --bucket-name is required when configuring GCS backend" in captured.out
    )


@patch("configure_storage.create_env_file")
def test_main_backend_gcs(mock_create, capsys):
    run_main_with_args(["--backend", "gcs", "--bucket-name", "my-bucket"])
    mock_create.assert_called_once_with("gcs", "my-bucket", None)
    captured = capsys.readouterr()
    assert "✓ Configured storage backend: GCS" in captured.out
    assert "Next steps for Google Cloud Storage:" in captured.out


# Tests for CLI setup-help and error handling
@patch("configure_storage.setup_aws")
def test_main_setup_help_aws(mock_setup):
    run_main_with_args(["--setup-help", "aws"])
    mock_setup.assert_called_once()


@patch("configure_storage.setup_gcs")
def test_main_setup_help_gcs(mock_setup):
    run_main_with_args(["--setup-help", "gcs"])
    mock_setup.assert_called_once()


@patch("configure_storage.create_env_file", side_effect=Exception("oops"))
def test_main_backend_error(mock_create, capsys):
    run_main_with_args(["--backend", "aws"])
    captured = capsys.readouterr()
    assert "Error configuring storage: oops" in captured.out
