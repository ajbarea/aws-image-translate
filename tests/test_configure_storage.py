from unittest.mock import mock_open, patch
import argparse


from configure_storage import (
    create_env_file,
    handle_backend_configuration,
    handle_setup_help,
    show_status,
)


# Tests for create_env_file
@patch("pathlib.Path.exists", return_value=False)
@patch("builtins.open", new_callable=mock_open)
def test_create_env_file_aws_new(mock_file_open, mock_exists):
    """Test creating a new .env.local file for AWS."""
    create_env_file("aws")
    handle = mock_file_open()
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    assert "STORAGE_BACKEND=aws" in written_content
    assert "GCS_BUCKET_NAME" not in written_content


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="GCS_BUCKET_NAME=old\nOTHER=val",
)
@patch("pathlib.Path.exists", return_value=True)
def test_create_env_file_aws_existing(mock_exists, mock_file_open):
    """Test updating an existing .env.local file for AWS, removing GCS vars."""
    create_env_file("aws")
    handle = mock_file_open()
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    assert "STORAGE_BACKEND=aws" in written_content
    assert "OTHER=val" in written_content
    assert "GCS_BUCKET_NAME" not in written_content


@patch("pathlib.Path.exists", return_value=False)
@patch("builtins.open", new_callable=mock_open)
def test_create_env_file_gcs_new(mock_file_open, mock_exists):
    """Test creating a new .env.local file for GCS."""
    create_env_file("gcs", "my-bucket", "key.json")
    handle = mock_file_open()
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    assert "STORAGE_BACKEND=gcs" in written_content
    assert "GCS_BUCKET_NAME=my-bucket" in written_content
    assert "GOOGLE_APPLICATION_CREDENTIALS=key.json" in written_content


# Tests for show_status
@patch("src.storage_adapter.get_storage_info")
@patch("src.storage_adapter.check_storage_connectivity")
def test_show_status_success(mock_check_conn, mock_get_info, capsys):
    """Test show_status with successful connectivity."""
    mock_get_info.return_value = {
        "backend": "AWS S3",
        "bucket": "test-bucket",
        "region": "us-east-1",
    }
    mock_check_conn.return_value = True
    show_status()
    captured = capsys.readouterr()
    assert "Current Storage Configuration:" in captured.out
    assert "Backend: AWS S3" in captured.out
    assert "✓ Storage backend is accessible" in captured.out


@patch("src.storage_adapter.get_storage_info")
@patch("src.storage_adapter.check_storage_connectivity")
def test_show_status_failure(mock_check_conn, mock_get_info, capsys):
    """Test show_status with failed connectivity."""
    mock_get_info.return_value = {
        "backend": "GCS",
        "bucket": "gcs-bucket",
        "region": "N/A",
    }
    mock_check_conn.return_value = False
    show_status()
    captured = capsys.readouterr()
    assert "Current Storage Configuration:" in captured.out
    assert "Backend: GCS" in captured.out
    assert "✗ Storage backend is not accessible" in captured.out


@patch("pathlib.Path.exists", return_value=False)
@patch("builtins.open", new_callable=mock_open)
def test_create_env_file_gcs_without_credentials(mock_file_open, mock_exists):
    """Test creating GCS config without credentials (tests the else branch for gcs_credentials)."""
    create_env_file("gcs", "my-bucket")  # No credentials provided
    handle = mock_file_open()
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    assert "STORAGE_BACKEND=gcs" in written_content
    assert "GCS_BUCKET_NAME=my-bucket" in written_content
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in written_content


@patch("pathlib.Path.exists", return_value=False)
@patch("builtins.open", new_callable=mock_open)
def test_create_env_file_unknown_backend(mock_file_open, mock_exists):
    """Test creating config with unknown backend (tests the implicit else branch)."""
    create_env_file("unknown")
    handle = mock_file_open()
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    # Should only contain the header comments, no backend configuration
    assert "# Storage Configuration" in written_content
    assert "STORAGE_BACKEND" not in written_content


@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="# Comment line\n\n=invalid_line\nVALID=value\n",
)
@patch("pathlib.Path.exists", return_value=True)
def test_create_env_file_with_invalid_lines(mock_exists, mock_file_open):
    """Test parsing env file with various line formats (comments, empty, invalid)."""
    create_env_file("aws")
    handle = mock_file_open()
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    assert "STORAGE_BACKEND=aws" in written_content
    assert "VALID=value" in written_content
    # Should ignore comment lines and invalid format lines


# Tests for handle_setup_help
@patch("configure_storage.setup_aws")
def test_handle_setup_help_aws(mock_setup_aws):
    """Test handle_setup_help with AWS backend."""
    args = argparse.Namespace()
    args.setup_help = "aws"
    handle_setup_help(args)
    mock_setup_aws.assert_called_once()


@patch("configure_storage.setup_gcs")
def test_handle_setup_help_gcs(mock_setup_gcs):
    """Test handle_setup_help with GCS backend."""
    args = argparse.Namespace()
    args.setup_help = "gcs"
    handle_setup_help(args)
    mock_setup_gcs.assert_called_once()


def test_handle_setup_help_unknown():
    """Test handle_setup_help with unknown backend (tests else branch)."""
    args = argparse.Namespace()
    args.setup_help = "unknown"
    # Should not raise an exception, just do nothing
    handle_setup_help(args)


# Tests for handle_backend_configuration
@patch("configure_storage.create_env_file")
@patch("builtins.print")
def test_handle_backend_configuration_aws(mock_print, mock_create_env):
    """Test handle_backend_configuration with AWS backend."""
    args = argparse.Namespace()
    args.backend = "aws"
    args.bucket_name = "test-bucket"
    args.credentials = None

    handle_backend_configuration(args)

    mock_create_env.assert_called_once_with("aws", "test-bucket", None)
    mock_print.assert_called_with("✓ Configured storage backend: AWS")


@patch("configure_storage.create_env_file")
@patch("builtins.print")
def test_handle_backend_configuration_gcs_with_bucket(mock_print, mock_create_env):
    """Test handle_backend_configuration with GCS backend and bucket name."""
    args = argparse.Namespace()
    args.backend = "gcs"
    args.bucket_name = "test-bucket"
    args.credentials = "path/to/key.json"

    handle_backend_configuration(args)

    mock_create_env.assert_called_once_with("gcs", "test-bucket", "path/to/key.json")
    # Verify GCS-specific output is printed
    assert any(
        "Next steps for Google Cloud Storage:" in str(call)
        for call in mock_print.call_args_list
    )


@patch("builtins.print")
def test_handle_backend_configuration_gcs_no_bucket(mock_print):
    """Test handle_backend_configuration with GCS backend but no bucket name."""
    args = argparse.Namespace()
    args.backend = "gcs"
    args.bucket_name = None
    args.credentials = None

    handle_backend_configuration(args)

    mock_print.assert_any_call(
        "Error: --bucket-name is required when configuring GCS backend"
    )
    mock_print.assert_any_call(
        "Example: python configure_storage.py --backend gcs --bucket-name my-bucket"
    )


@patch("configure_storage.create_env_file", side_effect=Exception("Test error"))
@patch("builtins.print")
def test_handle_backend_configuration_exception(mock_print, mock_create_env):
    """Test handle_backend_configuration when create_env_file raises an exception."""
    args = argparse.Namespace()
    args.backend = "aws"
    args.bucket_name = "test-bucket"
    args.credentials = None

    handle_backend_configuration(args)

    mock_print.assert_called_with("Error configuring storage: Test error")
