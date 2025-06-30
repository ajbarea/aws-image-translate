from unittest.mock import MagicMock, patch

from src.amazon_rekognition import detect_text_from_s3


@patch("src.amazon_rekognition.boto3")
def test_detect_text_from_s3_returns_detected_lines(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client
    mock_client.detect_text.return_value = {
        "TextDetections": [
            {"DetectedText": "Hola", "Type": "LINE"},
            {"DetectedText": "Mundo", "Type": "LINE"},
            {"DetectedText": "word", "Type": "WORD"},
        ]
    }
    result = detect_text_from_s3("photo.jpg", "bucket")
    assert result == "Hola Mundo"


@patch("src.amazon_rekognition.boto3")
def test_detect_text_from_s3_no_lines(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.Session.return_value.client.return_value = mock_client
    mock_client.detect_text.return_value = {
        "TextDetections": [{"DetectedText": "word", "Type": "WORD"}]
    }
    result = detect_text_from_s3("photo.jpg", "bucket")
    assert result == ""
