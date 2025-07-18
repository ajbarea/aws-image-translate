from unittest.mock import MagicMock, patch

import pytest

from main import process_all_images, process_image


def test_process_image_detects_and_translates(monkeypatch):
    mock_detect = MagicMock(return_value="Hola Mundo")
    mock_detect_language = MagicMock(return_value="es")
    mock_translate = MagicMock(return_value="Hello World")
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    monkeypatch.setattr("main.detect_language", mock_detect_language)
    monkeypatch.setattr("main.translate_text", mock_translate)
    result = process_image("photo.jpg", "bucket", "en")
    assert result == "Hello World"
    mock_detect.assert_called_once_with("photo.jpg", "bucket")
    mock_detect_language.assert_called_once_with("Hola Mundo")
    mock_translate.assert_called_once_with(
        "Hola Mundo", source_lang="es", target_lang="en"
    )


def test_process_image_no_text(monkeypatch):
    mock_detect = MagicMock(return_value="")
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    result = process_image("photo.jpg", "bucket", "en")
    assert result is None


def test_process_image_detect_error(monkeypatch):
    mock_detect = MagicMock(side_effect=Exception("AWS error"))
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    result = process_image("photo.jpg", "bucket", "en")
    assert result is None


def test_process_image_translate_error(monkeypatch):
    mock_detect = MagicMock(return_value="Hola Mundo")
    mock_detect_language = MagicMock(return_value="es")
    mock_translate = MagicMock(side_effect=Exception("Translate error"))
    monkeypatch.setattr("main.detect_text_from_s3", mock_detect)
    monkeypatch.setattr("main.detect_language", mock_detect_language)
    monkeypatch.setattr("main.translate_text", mock_translate)
    result = process_image("photo.jpg", "bucket", "en")
    assert result is None


def test_process_all_images(monkeypatch):
    mock_list = MagicMock(return_value=["img1.png", "img2.jpg"])
    mock_process = MagicMock(side_effect=["Hello", "World"])
    monkeypatch.setattr("main.list_images_in_bucket", mock_list)
    monkeypatch.setattr("main.process_image", mock_process)
    results = process_all_images("bucket", "en")
    assert results == ["Hello", "World"]
    mock_list.assert_called_once_with("bucket")
    assert mock_process.call_count == 2


def test_process_all_images_list_error(monkeypatch):
    mock_list = MagicMock(side_effect=Exception("S3 error"))
    monkeypatch.setattr("main.list_images_in_bucket", mock_list)
    results = process_all_images("bucket", "en")
    assert results == []


def test_process_all_images_with_none_results(monkeypatch):
    """Test process_all_images when some images return None (no text detected)."""
    mock_list = MagicMock(return_value=["img1.png", "img2.jpg", "img3.png"])
    mock_process = MagicMock(side_effect=["Hello", None, "World"])  # img2 returns None
    monkeypatch.setattr("main.list_images_in_bucket", mock_list)
    monkeypatch.setattr("main.process_image", mock_process)
    results = process_all_images("bucket", "en")
    assert results == ["Hello", "World"]  # None result is filtered out
    mock_list.assert_called_once_with("bucket")
    assert mock_process.call_count == 3


def test_main_function(monkeypatch):
    mock_s3_exists = MagicMock(return_value=True)
    mock_process = MagicMock(return_value="Hello")
    monkeypatch.setattr("main.s3_object_exists", mock_s3_exists)
    monkeypatch.setattr("main.process_image", mock_process)
    from main import main as main_func

    main_func("bucket", "en")

    mock_s3_exists.assert_called_once_with("bucket", "es1.png")
    mock_process.assert_called_once_with("es1.png", "bucket", "en")


def test_main_function_uploads_missing_image(monkeypatch):
    mock_s3_exists = MagicMock(return_value=False)
    mock_upload = MagicMock(return_value=True)
    mock_process = MagicMock(return_value="Hello")
    monkeypatch.setattr("main.s3_object_exists", mock_s3_exists)
    monkeypatch.setattr("main.upload_file_to_s3", mock_upload)
    monkeypatch.setattr("main.process_image", mock_process)
    from main import main as main_func

    main_func("bucket", "en")

    mock_upload.assert_called_once_with(
        "C:/ajsoftworks/aws-image-translate/tests/resources/spanish_images/es1.png",
        "bucket",
        "es1.png",
    )
    mock_process.assert_called_once_with("es1.png", "bucket", "en")


# Test main upload failure skips processing
def test_main_upload_failure_skips_processing(monkeypatch):
    mock_s3_exists = MagicMock(return_value=False)
    mock_upload = MagicMock(return_value=False)
    mock_process = MagicMock()
    monkeypatch.setattr("main.s3_object_exists", mock_s3_exists)
    monkeypatch.setattr("main.upload_file_to_s3", mock_upload)
    monkeypatch.setattr("main.process_image", mock_process)
    from main import main as main_func

    main_func("bucket", "en")

    mock_upload.assert_called_once_with(
        "C:/ajsoftworks/aws-image-translate/tests/resources/spanish_images/es1.png",
        "bucket",
        "es1.png",
    )
    mock_process.assert_not_called()


def test_cli_invokes_main(monkeypatch, capsys):
    mock_main = MagicMock()
    monkeypatch.setattr("main.main", mock_main)
    test_args = [
        "prog",
        "--bucket",
        "mybucket",
        "--target-lang",
        "de",
    ]
    monkeypatch.setattr("sys.argv", test_args)
    from main import cli

    cli()

    mock_main.assert_called_once_with("mybucket", "de")


def test_cli_default_args(monkeypatch):
    mock_main = MagicMock()
    monkeypatch.setattr("main.main", mock_main)
    test_args = ["prog"]
    monkeypatch.setattr("sys.argv", test_args)
    from config import S3_IMAGE_BUCKET, TARGET_LANGUAGE_CODE
    from main import cli

    cli()

    mock_main.assert_called_once_with(S3_IMAGE_BUCKET, TARGET_LANGUAGE_CODE)


# Tests for s3_object_exists
@patch("main.boto3")
def test_s3_object_exists_true(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    mock_s3_client.head_object.return_value = {}

    from main import s3_object_exists

    assert s3_object_exists("bucket", "key") is True
    mock_boto3.client.assert_called_once_with("s3")
    mock_s3_client.head_object.assert_called_once_with(Bucket="bucket", Key="key")


@patch("main.boto3")
def test_s3_object_exists_false_404(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    # Mock ClientError for 404 (object not found)
    from botocore.exceptions import ClientError

    error_404 = ClientError(
        error_response={"Error": {"Code": "404", "Message": "Not Found"}},
        operation_name="HeadObject",
    )
    mock_s3_client.head_object.side_effect = error_404

    from main import s3_object_exists

    assert s3_object_exists("bucket", "key") is False
    mock_boto3.client.assert_called_once_with("s3")
    mock_s3_client.head_object.assert_called_once_with(Bucket="bucket", Key="key")


@patch("main.boto3")
def test_s3_object_exists_reraises_non_404_errors(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    # Mock ClientError for non-404 error (should be re-raised)
    from botocore.exceptions import ClientError

    error_500 = ClientError(
        error_response={"Error": {"Code": "500", "Message": "Internal Server Error"}},
        operation_name="HeadObject",
    )
    mock_s3_client.head_object.side_effect = error_500

    from main import s3_object_exists

    with pytest.raises(ClientError) as exc_info:
        s3_object_exists("bucket", "key")

    assert exc_info.value.response.get("Error", {}).get("Code") == "500"
    mock_boto3.client.assert_called_once_with("s3")
    mock_s3_client.head_object.assert_called_once_with(Bucket="bucket", Key="key")


# Tests for upload_file_to_s3
@patch("main.boto3")
def test_upload_file_to_s3_success(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    from main import upload_file_to_s3

    result = upload_file_to_s3("file.txt", "bucket", "key")
    assert result is True
    mock_boto3.client.assert_called_once_with("s3")
    mock_s3_client.upload_file.assert_called_once_with("file.txt", "bucket", "key")


@patch("main.boto3")
def test_upload_file_to_s3_failure(mock_boto3):
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    mock_s3_client.upload_file.side_effect = Exception("Upload error")

    from main import upload_file_to_s3

    result = upload_file_to_s3("file.txt", "bucket", "key")
    assert result is False
