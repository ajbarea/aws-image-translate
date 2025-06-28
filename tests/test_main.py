import pytest
from unittest.mock import patch, MagicMock
from main import process_image, process_all_images


def test_process_image_detects_and_translates(monkeypatch):
    mock_detect = MagicMock(return_value="Hola Mundo")
    mock_translate = MagicMock(return_value="Hello World")
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    monkeypatch.setattr("main.translate_text", mock_translate)
    result = process_image("photo.jpg", "bucket", "es", "en")
    assert result == "Hello World"
    mock_detect.assert_called_once_with("photo.jpg", "bucket")
    mock_translate.assert_called_once_with(
        "Hola Mundo", source_lang="es", target_lang="en"
    )


def test_process_image_no_text(monkeypatch):
    mock_detect = MagicMock(return_value="")
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    result = process_image("photo.jpg", "bucket", "es", "en")
    assert result is None


def test_process_image_detect_error(monkeypatch):
    mock_detect = MagicMock(side_effect=Exception("AWS error"))
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    result = process_image("photo.jpg", "bucket", "es", "en")
    assert result is None


def test_process_image_translate_error(monkeypatch):
    mock_detect = MagicMock(return_value="Hola Mundo")
    mock_translate = MagicMock(side_effect=Exception("Translate error"))
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    monkeypatch.setattr("main.translate_text", mock_translate)
    result = process_image("photo.jpg", "bucket", "es", "en")
    assert result is None


def test_process_all_images(monkeypatch):
    mock_list = MagicMock(return_value=["img1.png", "img2.jpg"])
    mock_process = MagicMock(side_effect=["Hello", "World"])
    monkeypatch.setattr("main.list_images_in_bucket", mock_list)
    monkeypatch.setattr("main.process_image", mock_process)
    results = process_all_images("bucket", "es", "en")
    assert results == ["Hello", "World"]
    mock_list.assert_called_once_with("bucket")
    assert mock_process.call_count == 2


def test_process_all_images_list_error(monkeypatch):
    mock_list = MagicMock(side_effect=Exception("S3 error"))
    monkeypatch.setattr("main.list_images_in_bucket", mock_list)
    results = process_all_images("bucket", "es", "en")
    assert results == []


def test_main_function(monkeypatch):
    mock_s3_exists = MagicMock(return_value=True)
    mock_process = MagicMock(return_value="Hello")
    monkeypatch.setattr("main.s3_object_exists", mock_s3_exists)
    monkeypatch.setattr("main.process_image", mock_process)
    from main import main as main_func

    main_func("bucket", "es", "en")

    mock_s3_exists.assert_called_once_with("bucket", "es1.png")
    mock_process.assert_called_once_with("es1.png", "bucket", "es", "en")


def test_main_function_uploads_missing_image(monkeypatch):
    mock_s3_exists = MagicMock(return_value=False)
    mock_upload = MagicMock(return_value=True)
    mock_process = MagicMock(return_value="Hello")
    monkeypatch.setattr("main.s3_object_exists", mock_s3_exists)
    monkeypatch.setattr("main.upload_file_to_s3", mock_upload)
    monkeypatch.setattr("main.process_image", mock_process)
    from main import main as main_func

    main_func("bucket", "es", "en")

    mock_upload.assert_called_once_with(
        "C:/ajsoftworks/aws-image-translate/spanish_images/es1.png", "bucket", "es1.png"
    )
    mock_process.assert_called_once_with("es1.png", "bucket", "es", "en")


def test_cli_invokes_main(monkeypatch, capsys):
    mock_main = MagicMock()
    monkeypatch.setattr("main.main", mock_main)
    test_args = [
        "prog",
        "--bucket",
        "mybucket",
        "--source-lang",
        "fr",
        "--target-lang",
        "de",
    ]
    monkeypatch.setattr("sys.argv", test_args)
    from main import cli

    cli()

    mock_main.assert_called_once_with("mybucket", "fr", "de")


def test_cli_default_args(monkeypatch):
    mock_main = MagicMock()
    monkeypatch.setattr("main.main", mock_main)
    test_args = ["prog"]
    monkeypatch.setattr("sys.argv", test_args)
    from main import cli
    from config import S3_IMAGE_BUCKET, SOURCE_LANGUAGE_CODE, TARGET_LANGUAGE_CODE

    cli()

    mock_main.assert_called_once_with(
        S3_IMAGE_BUCKET, SOURCE_LANGUAGE_CODE, TARGET_LANGUAGE_CODE
    )
