from unittest.mock import patch, MagicMock
from src.amazon_s3 import list_images_in_bucket


@patch("src.amazon_s3.boto3")
def test_list_images_in_bucket_returns_images(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "img1.png"},
            {"Key": "img2.jpg"},
            {"Key": "doc.txt"},
            {"Key": "img3.jpeg"},
        ]
    }
    result = list_images_in_bucket("bucket")
    assert result == ["img1.png", "img2.jpg", "img3.jpeg"]


@patch("src.amazon_s3.boto3")
def test_list_images_in_bucket_empty(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mock_client.list_objects_v2.return_value = {}
    result = list_images_in_bucket("bucket")
    assert result == []
