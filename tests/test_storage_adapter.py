import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.storage_adapter import (
    _reset_clients,
    check_storage_connectivity,
    get_storage_info,
    list_images_in_bucket,
    upload_file_to_s3,
    upload_fileobj_to_s3,
)


class TestStorageAdapterAWS:
    """Test storage adapter with AWS S3 backend."""

    def setup_method(self):
        _reset_clients()
        self.patcher = patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        _reset_clients()

    @patch("src.storage_adapter.boto3")
    def test_list_images_in_bucket_aws(self, mock_boto3):
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "img1.png"},
                {"Key": "img2.jpg"},
                {"Key": "doc.txt"},
                {"Key": "img3.jpeg"},
                {"Key": "IMG4.PNG"},
            ]
        }
        result = list_images_in_bucket("test_bucket")
        expected = ["img1.png", "img2.jpg", "img3.jpeg", "IMG4.PNG"]
        assert sorted(result) == sorted(expected)
        mock_s3_client.list_objects_v2.assert_called_once_with(Bucket="test_bucket")

    @patch("src.storage_adapter.boto3")
    def test_upload_file_to_s3_aws_success(self, mock_boto3):
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        result = upload_file_to_s3("test/path.jpg", "test_bucket", "object.jpg")
        assert result is True
        mock_s3_client.upload_file.assert_called_once_with(
            "test/path.jpg", "test_bucket", "object.jpg"
        )

    @patch("src.storage_adapter.boto3")
    def test_upload_fileobj_to_s3_aws_success(self, mock_boto3):
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        mock_fileobj = MagicMock()
        result = upload_fileobj_to_s3(mock_fileobj, "test_bucket", "object.jpg")
        assert result is True
        mock_s3_client.upload_fileobj.assert_called_once_with(
            mock_fileobj, "test_bucket", "object.jpg"
        )

    def test_get_storage_info_aws(self):
        info = get_storage_info()
        assert info["backend"] == "AWS S3"
        assert info["bucket"] == "Varies by function call"
        assert "region" in info


class TestStorageAdapterGCS:
    """Test storage adapter with Google Cloud Storage backend."""

    def setup_method(self):
        _reset_clients()
        self.patcher = patch.dict(
            os.environ, {"STORAGE_BACKEND": "gcs", "GCS_BUCKET_NAME": "test-bucket"}
        )
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        _reset_clients()

    @patch("src.storage_adapter.gcs")
    def test_list_images_in_bucket_gcs(self, mock_gcs):
        mock_client, mock_bucket = MagicMock(), MagicMock()
        mock_gcs.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_blobs = [MagicMock(), MagicMock(), MagicMock()]
        mock_blobs[0].name = "img1.png"
        mock_blobs[1].name = "img2.jpg"
        mock_blobs[2].name = "doc.txt"
        mock_bucket.list_blobs.return_value = mock_blobs
        result = list_images_in_bucket("ignored_bucket")
        assert sorted(result) == sorted(["img1.png", "img2.jpg"])

    @patch("src.storage_adapter.gcs")
    def test_upload_file_to_s3_gcs_success(self, mock_gcs):
        mock_client, mock_bucket, mock_blob = MagicMock(), MagicMock(), MagicMock()
        mock_gcs.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        result = upload_file_to_s3("test/path.jpg", "ignored_bucket", "object.jpg")
        assert result is True
        mock_bucket.blob.assert_called_once_with("object.jpg")
        mock_blob.upload_from_filename.assert_called_once_with("test/path.jpg")

    @patch("src.storage_adapter.gcs")
    def test_upload_fileobj_to_s3_gcs_success(self, mock_gcs):
        mock_client, mock_bucket, mock_blob = MagicMock(), MagicMock(), MagicMock()
        mock_gcs.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_fileobj = BytesIO(b"test data")
        result = upload_fileobj_to_s3(mock_fileobj, "ignored_bucket", "object.jpg")
        assert result is True
        mock_bucket.blob.assert_called_once_with("object.jpg")
        mock_blob.upload_from_file.assert_called_once_with(mock_fileobj)
        assert mock_fileobj.tell() == 0


class TestStorageAdapterConfiguration:
    """Test storage adapter configuration and error handling."""

    def setup_method(self):
        _reset_clients()

    def teardown_method(self):
        _reset_clients()

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_connectivity_check_aws_success(self, mock_boto3):
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        assert check_storage_connectivity() is True
        mock_s3_client.list_buckets.assert_called_once()

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_connectivity_check_aws_failure(self, mock_boto3):
        mock_s3_client = MagicMock()
        mock_s3_client.list_buckets.side_effect = Exception("AWS Error")
        mock_boto3.client.return_value = mock_s3_client
        assert check_storage_connectivity() is False

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_upload_error_handling_aws(self, mock_boto3):
        mock_s3_client = MagicMock()
        mock_s3_client.upload_file.side_effect = Exception("Upload failed")
        mock_boto3.client.return_value = mock_s3_client
        assert upload_file_to_s3("test.jpg", "bucket", "obj.jpg") is False

    @patch.dict(os.environ, {"STORAGE_BACKEND": "gcs"})
    def test_gcs_missing_bucket_name_raises_error(self):
        if "GCS_BUCKET_NAME" in os.environ:
            del os.environ["GCS_BUCKET_NAME"]
        with patch("src.storage_adapter.gcs"), pytest.raises(RuntimeError) as excinfo:
            list_images_in_bucket("any_bucket")
        assert "GCS_BUCKET_NAME environment variable is required" in str(excinfo.value)

    @patch.dict(os.environ, {"STORAGE_BACKEND": "gcs"})
    def test_gcs_import_error(self):
        with patch("src.storage_adapter.gcs", None), pytest.raises(ImportError):
            list_images_in_bucket("any_bucket")

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    def test_aws_import_error(self):
        with patch("src.storage_adapter.boto3", None), pytest.raises(ImportError):
            list_images_in_bucket("any_bucket")

    def test_invalid_backend_falls_back_to_aws(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "invalid"}):
            info = get_storage_info()
            assert info["backend"] == "AWS S3"

    @patch.dict(
        os.environ, {"STORAGE_BACKEND": "gcs", "GCS_BUCKET_NAME": "test-bucket"}
    )
    @patch("src.storage_adapter.gcs")
    def test_gcs_client_reuse(self, mock_gcs):
        """Test that GCS client is reused when already initialized."""
        mock_client, mock_bucket = MagicMock(), MagicMock()
        mock_gcs.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.list_blobs.return_value = []

        # First call initializes the client
        list_images_in_bucket("test_bucket")

        # Second call should reuse the client
        list_images_in_bucket("test_bucket")

        # Client should only be created once
        mock_gcs.Client.assert_called_once()
        assert mock_client.bucket.call_count == 1

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_s3_client_reuse(self, mock_boto3):
        """Test that S3 client is reused when already initialized."""
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        mock_s3_client.list_objects_v2.return_value = {"Contents": []}

        # First call initializes the client
        list_images_in_bucket("test_bucket")

        # Second call should reuse the client
        list_images_in_bucket("test_bucket")

        # Client should only be created once
        mock_boto3.client.assert_called_once()
        assert mock_s3_client.list_objects_v2.call_count == 2
