from unittest.mock import patch, MagicMock
from src.amazon_translate import translate_text


@patch("src.amazon_translate.boto3")
def test_translate_text_returns_translation(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mock_client.translate_text.return_value = {"TranslatedText": "Hello world!"}
    result = translate_text("Hola mundo!", "es", "en")
    assert result == "Hello world!"


@patch("src.amazon_translate.boto3")
def test_translate_text_returns_none_if_missing(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    mock_client.translate_text.return_value = {}
    result = translate_text("Hola mundo!", "es", "en")
    assert result is None
