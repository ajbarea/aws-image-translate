from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "aws-image-translate-backend",
    }


@patch("backend.app.detect_text_from_s3")
@patch("backend.app.detect_language")
@patch("backend.app.translate_text")
def test_process_image_full_pipeline(
    mock_translate, mock_detect_language, mock_detect_text
):
    """Test the full image processing pipeline (detection and translation)."""
    mock_detect_text.return_value = "Hola Mundo"
    mock_detect_language.return_value = "es"
    mock_translate.return_value = "Hello World"

    response = client.post(
        "/process",
        json={"bucket": "test-bucket", "key": "test.jpg", "targetLanguage": "en"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["detectedText"] == "Hola Mundo"
    assert data["detectedLanguage"] == "es"
    assert data["translatedText"] == "Hello World"
    assert data["targetLanguage"] == "en"

    mock_detect_text.assert_called_once_with("test.jpg", "test-bucket")
    mock_detect_language.assert_called_once_with("Hola Mundo")
    mock_translate.assert_called_once_with(
        "Hola Mundo", source_lang="es", target_lang="en"
    )


@patch("backend.app.detect_text_from_s3")
def test_process_image_no_text_detected(mock_detect_text):
    """Test the case where no text is detected in the image."""
    mock_detect_text.return_value = ""

    response = client.post(
        "/process",
        json={"bucket": "test-bucket", "key": "blank.jpg", "targetLanguage": "en"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["detectedText"] == ""
    assert data["translatedText"] is None


@patch("backend.app.detect_language")
@patch("backend.app.translate_text")
def test_process_image_retranslate(mock_translate, mock_detect_language):
    """Test the re-translation functionality."""
    mock_translate.return_value = "Bonjour le monde"

    response = client.post(
        "/process",
        json={
            "bucket": "test-bucket",
            "key": "test.jpg",
            "targetLanguage": "fr",
            "detectedText": "Hello World",
            "detectedLanguage": "en",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["detectedText"] == "Hello World"
    assert data["translatedText"] == "Bonjour le monde"
    assert data["targetLanguage"] == "fr"

    mock_detect_language.assert_not_called()
    mock_translate.assert_called_once_with(
        "Hello World", source_lang="en", target_lang="fr"
    )


@patch("backend.app.detect_language")
@patch("backend.app.translate_text")
def test_process_image_retranslate_with_language_detection(
    mock_translate, mock_detect_language
):
    """Test re-translation when source language is not provided."""
    mock_detect_language.return_value = "en"
    mock_translate.return_value = "Hallo Welt"

    response = client.post(
        "/process",
        json={
            "bucket": "test-bucket",
            "key": "test.jpg",
            "targetLanguage": "de",
            "detectedText": "Hello World",
            # No detectedLanguage
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["translatedText"] == "Hallo Welt"
    mock_detect_language.assert_called_once_with("Hello World")
    mock_translate.assert_called_once_with(
        "Hello World", source_lang="en", target_lang="de"
    )


@patch(
    "backend.app.detect_text_from_s3", side_effect=Exception("AWS Rekognition Error")
)
def test_process_image_exception_handling(mock_detect_text):
    """Test that exceptions are handled and result in a 500 error."""
    response = client.post(
        "/process",
        json={"bucket": "test-bucket", "key": "test.jpg", "targetLanguage": "en"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "AWS Rekognition Error"}
