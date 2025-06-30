import io
from unittest.mock import MagicMock, mock_open, patch

from config import AWS_REGION
from src.amazon_s3 import list_images_in_bucket, upload_file_to_s3, upload_fileobj_to_s3


# Existing tests for list_images_in_bucket
@patch("src.amazon_s3.boto3")
def test_list_images_in_bucket_returns_images(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    mock_s3_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "img1.png"},
            {"Key": "img2.jpg"},
            {"Key": "doc.txt"},
            {"Key": "img3.jpeg"},
            {"Key": "IMG4.PNG"},  # Test case sensitivity for extension
        ]
    }
    result = list_images_in_bucket("test_bucket")
    assert sorted(result) == sorted(["img1.png", "img2.jpg", "img3.jpeg", "IMG4.PNG"])
    mock_boto3.client.assert_called_once_with("s3", region_name=AWS_REGION)
    mock_s3_client.list_objects_v2.assert_called_once_with(Bucket="test_bucket")


@patch("src.amazon_s3.boto3")
def test_list_images_in_bucket_empty_contents(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    mock_s3_client.list_objects_v2.return_value = {"Contents": []}  # Empty contents
    result = list_images_in_bucket("test_bucket")
    assert result == []
    mock_boto3.client.assert_called_once_with("s3", region_name=AWS_REGION)
    mock_s3_client.list_objects_v2.assert_called_once_with(Bucket="test_bucket")


@patch("src.amazon_s3.boto3")
def test_list_images_in_bucket_no_contents_key(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    mock_s3_client.list_objects_v2.return_value = {}  # No 'Contents' key
    result = list_images_in_bucket("test_bucket")
    assert result == []
    mock_boto3.client.assert_called_once_with("s3", region_name=AWS_REGION)
    mock_s3_client.list_objects_v2.assert_called_once_with(Bucket="test_bucket")


# Tests for upload_file_to_s3
@patch("src.amazon_s3.boto3")
@patch(
    "builtins.open", new_callable=mock_open, read_data="test data"
)  # Mock open for file operations
def test_upload_file_to_s3_success(mock_file_open, mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    file_path = "dummy/path/to/file.txt"
    bucket_name = "test_bucket"
    object_name = "s3_object.txt"

    result = upload_file_to_s3(file_path, bucket_name, object_name)

    assert result is True
    mock_boto3.client.assert_called_once_with("s3", region_name=AWS_REGION)
    mock_s3_client.upload_file.assert_called_once_with(
        file_path, bucket_name, object_name
    )


@patch("src.amazon_s3.boto3")
@patch("builtins.open", new_callable=mock_open, read_data="test data")
def test_upload_file_to_s3_uses_filename_as_object_name(mock_file_open, mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    file_path = "another/dummy/file_to_upload.jpg"
    bucket_name = "test_bucket"
    expected_object_name = "file_to_upload.jpg"  # Derived from file_path

    result = upload_file_to_s3(file_path, bucket_name)  # object_name is None

    assert result is True
    mock_s3_client.upload_file.assert_called_once_with(
        file_path, bucket_name, expected_object_name
    )


@patch("src.amazon_s3.boto3")
@patch("builtins.open", new_callable=mock_open, read_data="test data")
def test_upload_file_to_s3_failure(mock_file_open, mock_boto3, capsys):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    mock_s3_client.upload_file.side_effect = Exception("S3 Upload Error")

    result = upload_file_to_s3("dummy/path.txt", "test_bucket", "s3_object.txt")

    assert result is False
    captured = capsys.readouterr()
    assert "Error uploading file to S3: S3 Upload Error" in captured.out


# Tests for upload_fileobj_to_s3
@patch("src.amazon_s3.boto3")
def test_upload_fileobj_to_s3_success(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    fileobj = io.BytesIO(b"some file data")
    bucket_name = "test_bucket"
    object_name = "s3_object_from_fileobj.bin"

    result = upload_fileobj_to_s3(fileobj, bucket_name, object_name)

    assert result is True
    mock_boto3.client.assert_called_once_with("s3", region_name=AWS_REGION)
    mock_s3_client.upload_fileobj.assert_called_once_with(
        fileobj, bucket_name, object_name
    )


@patch("src.amazon_s3.boto3")
def test_upload_fileobj_to_s3_failure(mock_boto3, capsys):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    mock_s3_client.upload_fileobj.side_effect = Exception("S3 FileObj Upload Error")

    fileobj = io.BytesIO(b"some file data")
    result = upload_fileobj_to_s3(fileobj, "test_bucket", "s3_object.bin")

    assert result is False
    captured = capsys.readouterr()  # To check the print statement
    assert "Error uploading file object to S3: S3 FileObj Upload Error" in captured.out
