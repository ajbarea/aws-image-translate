from unittest.mock import MagicMock, patch

from src.amazon_translate import detect_language, translate_text


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


@patch("src.amazon_translate.boto3")
def test_detect_language_success(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    # Simulate detect_dominant_language returning a list of languages
    mock_client.detect_dominant_language.return_value = {
        "Languages": [{"LanguageCode": "es"}]
    }
    result = detect_language("Hola mundo!")
    assert result == "es"


@patch("src.amazon_translate.boto3")
def test_detect_language_no_languages(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    # Simulate no languages detected
    mock_client.detect_dominant_language.return_value = {"Languages": []}
    result = detect_language("Hello world!")
    assert result == "en"


@patch("src.amazon_translate.boto3")
def test_detect_language_error(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client
    # Simulate an exception during detection
    mock_client.detect_dominant_language.side_effect = Exception("Comprehend error")
    result = detect_language("Test error")
    assert result == "en"
