"""Tests for storage adapter functionality.

This module tests the storage adapter that provides a unified interface
for both AWS S3 and Google Cloud Storage backends.
"""

import os
from unittest.mock import MagicMock, patch

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

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
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
                {"Key": "IMG4.PNG"},  # Test case sensitivity
            ]
        }

        result = list_images_in_bucket("test_bucket")

        expected = ["img1.png", "img2.jpg", "img3.jpeg", "IMG4.PNG"]
        assert sorted(result) == sorted(expected)
        mock_s3_client.list_objects_v2.assert_called_once_with(Bucket="test_bucket")

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_upload_file_to_s3_aws_success(self, mock_boto3):
        _reset_clients()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        result = upload_file_to_s3("test/path.jpg", "test_bucket", "object.jpg")

        assert result is True
        mock_s3_client.upload_file.assert_called_once_with(
            "test/path.jpg", "test_bucket", "object.jpg"
        )

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_upload_fileobj_to_s3_aws_success(self, mock_boto3):
        _reset_clients()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        mock_fileobj = MagicMock()

        result = upload_fileobj_to_s3(mock_fileobj, "test_bucket", "object.jpg")

        assert result is True
        mock_s3_client.upload_fileobj.assert_called_once_with(
            mock_fileobj, "test_bucket", "object.jpg"
        )

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    def test_get_storage_info_aws(self):
        info = get_storage_info()

        assert info["backend"] == "AWS S3"
        assert info["bucket"] == "Varies by function call"
        assert "region" in info


class TestStorageAdapterGCS:
    """Test storage adapter with Google Cloud Storage backend."""

    @patch.dict(
        os.environ, {"STORAGE_BACKEND": "gcs", "GCS_BUCKET_NAME": "test-bucket"}
    )
    @patch("src.storage_adapter.gcs")
    def test_list_images_in_bucket_gcs(self, mock_gcs):
        # Mock the GCS client and bucket
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_gcs.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket

        # Mock blobs
        mock_blob1 = MagicMock()
        mock_blob1.name = "img1.png"
        mock_blob2 = MagicMock()
        mock_blob2.name = "img2.jpg"
        mock_blob3 = MagicMock()
        mock_blob3.name = "doc.txt"

        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]

        # Import after patching environment
        from src.storage_adapter import list_images_in_bucket

        result = list_images_in_bucket("ignored_bucket")

        expected = ["img1.png", "img2.jpg"]
        assert sorted(result) == sorted(expected)

    @patch.dict(
        os.environ, {"STORAGE_BACKEND": "gcs", "GCS_BUCKET_NAME": "test-bucket"}
    )
    @patch("src.storage_adapter.gcs")
    def test_upload_file_to_s3_gcs_success(self, mock_gcs):
        _reset_clients()
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_gcs.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Import after patching environment
        from src.storage_adapter import upload_file_to_s3

        result = upload_file_to_s3("test/path.jpg", "ignored_bucket", "object.jpg")

        assert result is True
        mock_bucket.blob.assert_called_once_with("object.jpg")
        mock_blob.upload_from_filename.assert_called_once_with("test/path.jpg")


class TestStorageAdapterConfiguration:
    """Test storage adapter configuration and error handling."""

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    def test_connectivity_check_aws_success(self):
        _reset_clients()
        with patch("src.storage_adapter.boto3") as mock_boto3:
            mock_s3_client = MagicMock()
            mock_boto3.client.return_value = mock_s3_client

            result = check_storage_connectivity()

            assert result is True
            mock_s3_client.list_buckets.assert_called_once()

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    def test_connectivity_check_aws_failure(self):
        _reset_clients()
        with patch("src.storage_adapter.boto3") as mock_boto3:
            mock_s3_client = MagicMock()
            mock_s3_client.list_buckets.side_effect = Exception("AWS Error")
            mock_boto3.client.return_value = mock_s3_client

            result = check_storage_connectivity()

            assert result is False

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_upload_error_handling_aws(self, mock_boto3):
        _reset_clients()
        mock_s3_client = MagicMock()
        mock_s3_client.upload_file.side_effect = Exception("Upload failed")
        mock_boto3.client.return_value = mock_s3_client

        result = upload_file_to_s3("test/path.jpg", "test_bucket", "object.jpg")

        assert result is False

    def test_invalid_backend_environment(self):
        """Test that invalid backend values fall back to AWS."""
        with patch.dict(os.environ, {"STORAGE_BACKEND": "invalid"}):
            # Should fall back to AWS
            info = get_storage_info()
            assert info["backend"] == "AWS S3"


# Integration-style tests (these would require actual credentials in real usage)
class TestStorageAdapterIntegration:
    """Integration tests for storage adapter (mocked)."""

    @patch.dict(os.environ, {"STORAGE_BACKEND": "aws"})
    @patch("src.storage_adapter.boto3")
    def test_end_to_end_aws_workflow(self, mock_boto3):
        """Test a complete workflow with AWS backend."""
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        # Mock successful operations
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "test.jpg"}]
        }

        # Test workflow
        images = list_images_in_bucket("test_bucket")
        upload_success = upload_file_to_s3("local.jpg", "test_bucket", "remote.jpg")

        assert len(images) == 1
        assert upload_success is True
        assert mock_s3_client.list_objects_v2.call_count == 1
        assert mock_s3_client.upload_file.call_count == 1
