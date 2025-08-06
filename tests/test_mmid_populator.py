import tarfile
from unittest.mock import MagicMock, patch

import pytest
from botocore import UNSIGNED

from lambda_functions import mmid_populator


@pytest.fixture
def fake_tar_members():
    members = []
    for i in range(5):
        info = tarfile.TarInfo(name=f"dir{i}/01.jpg")
        info.size = 10
        info.type = tarfile.REGTYPE  # Make it a regular file
        members.append(info)
    return members


def test_choose_images(fake_tar_members):
    selected = mmid_populator.choose_images(fake_tar_members, k=3)
    assert len(selected) == 3
    assert all(m.name.endswith("/01.jpg") for m in selected)


def test_get_content_type():
    assert mmid_populator.get_content_type("file.png") == "image/png"
    assert mmid_populator.get_content_type("file.JPG") == "image/jpeg"
    assert mmid_populator.get_content_type("file.unknown") == "application/octet-stream"


@patch("lambda_functions.mmid_populator.boto3.client")
def test_create_s3_clients(mock_boto3_client):
    # Mock the boto3.client calls
    mock_unsigned_client = MagicMock()
    mock_signed_client = MagicMock()
    mock_boto3_client.side_effect = [mock_unsigned_client, mock_signed_client]

    # Clear the cache to ensure fresh test
    mmid_populator.create_s3_clients.cache_clear()

    # Call the function
    unsigned_s3, signed_s3 = mmid_populator.create_s3_clients()

    # Verify the clients are returned correctly
    assert unsigned_s3 == mock_unsigned_client
    assert signed_s3 == mock_signed_client

    # Verify boto3.client was called twice with correct parameters
    assert mock_boto3_client.call_count == 2

    # Check the first call (unsigned client)
    first_call = mock_boto3_client.call_args_list[0]
    assert first_call[0] == ("s3",)
    unsigned_config = first_call[1]["config"]
    assert unsigned_config.signature_version == UNSIGNED
    assert unsigned_config.retries == {"max_attempts": 3, "mode": "adaptive"}
    assert unsigned_config.max_pool_connections == 50

    # Check the second call (signed client)
    second_call = mock_boto3_client.call_args_list[1]
    assert second_call[0] == ("s3",)
    # The signed client uses OPTIMIZED_CONFIG from aws_clients


@patch("lambda_functions.mmid_populator.boto3.client")
def test_create_s3_clients_caching(mock_boto3_client):
    # Mock the boto3.client calls
    mock_unsigned_client = MagicMock()
    mock_signed_client = MagicMock()
    mock_boto3_client.side_effect = [mock_unsigned_client, mock_signed_client]

    # Clear the cache to ensure fresh test
    mmid_populator.create_s3_clients.cache_clear()

    # Call the function twice
    result1 = mmid_populator.create_s3_clients()
    result2 = mmid_populator.create_s3_clients()

    # Verify the same instances are returned (cached)
    assert result1 == result2
    assert result1[0] == result2[0]  # unsigned client
    assert result1[1] == result2[1]  # signed client

    # Verify boto3.client was only called twice total (not four times)
    assert mock_boto3_client.call_count == 2


@patch("lambda_functions.mmid_populator.process_single_language")
def test_lambda_handler(mock_process):
    mock_process.side_effect = lambda lang, bucket, images: (lang, [f"key-{lang}"])

    # Set env vars for test
    with patch("lambda_functions.mmid_populator.DEST_BUCKET", "test-bucket"):
        result = mmid_populator.lambda_handler({}, None)

    assert result["uploaded"] == len(result["all_keys"])
    assert result["bucket"] == "test-bucket"


def test_lambda_handler_missing_dest_bucket():
    with patch("lambda_functions.mmid_populator.DEST_BUCKET", None):
        with pytest.raises(
            RuntimeError, match="DEST_BUCKET environment variable not set"
        ):
            mmid_populator.lambda_handler({}, None)
