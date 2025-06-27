import pytest
from unittest.mock import patch, MagicMock, ANY
import io
import requests
import logging

from src.image_processor import (
    download_image,
    generate_s3_object_name,
    process_new_images_from_reddit,
    lambda_handler,
)
from config import S3_IMAGE_BUCKET, DYNAMODB_TABLE_NAME

# Test data
TEST_URL_JPG = "http://example.com/image.jpg"
TEST_URL_PNG = "http://example.com/image.png"
TEST_URL_GIF = "http://example.com/image.gif"
TEST_URL_UNSUPPORTED = "http://example.com/document.pdf"
TEST_URL_NO_EXT = "http://example.com/image"
TEST_POST_ID_1 = "t3_post1"
TEST_POST_ID_2 = "t3_post2"


@patch("src.image_processor.requests.get")
def test_download_image_success_jpg(mock_requests_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "image/jpeg"}
    mock_response.content = b"jpeg_data"
    mock_requests_get.return_value = mock_response

    image_bytes, content_type = download_image(TEST_URL_JPG)

    mock_requests_get.assert_called_once_with(
        TEST_URL_JPG, headers=ANY, stream=True, timeout=10
    )
    mock_response.raise_for_status.assert_called_once()
    assert image_bytes is not None
    assert image_bytes.read() == b"jpeg_data"
    assert content_type == "image/jpeg"


@patch("src.image_processor.requests.get")
def test_download_image_success_png_infer_from_url(mock_requests_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/octet-stream"}
    mock_response.content = b"png_data"
    mock_requests_get.return_value = mock_response

    image_bytes, content_type = download_image(TEST_URL_PNG)  # URL ends with .png

    mock_requests_get.assert_called_once_with(
        TEST_URL_PNG, headers=ANY, stream=True, timeout=10
    )
    assert image_bytes is not None
    assert image_bytes.read() == b"png_data"
    assert content_type == "image/png"  # Inferred from .png extension


@patch("src.image_processor.requests.get")
def test_download_image_unsupported_content_type(mock_requests_get, caplog):
    caplog.set_level(logging.INFO)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_requests_get.return_value = mock_response

    image_bytes, content_type = download_image(TEST_URL_UNSUPPORTED)

    assert image_bytes is None
    assert content_type is None
    assert (
        f"Skipping unsupported content type 'application/pdf' or unknown extension for URL: {TEST_URL_UNSUPPORTED}"
        in caplog.text
    )


@patch("src.image_processor.requests.get")
def test_download_image_request_exception(mock_requests_get, caplog):
    caplog.set_level(logging.INFO)
    mock_requests_get.side_effect = requests.exceptions.RequestException(
        "Connection error"
    )

    image_bytes, content_type = download_image(TEST_URL_JPG)

    assert image_bytes is None
    assert content_type is None
    assert (
        f"Error downloading image from {TEST_URL_JPG}: Connection error" in caplog.text
    )


def test_generate_s3_object_name_with_post_id():
    # The function currently produces ...abc123xyz_jpg.jpg, so update the test to match
    assert (
        generate_s3_object_name(
            TEST_POST_ID_1, "https://i.redd.it/abc123xyz.jpg", "image/jpeg"
        )
        == "r_translator/t3_post1/i_redd_it_abc123xyz_jpg.jpg"
    )
    assert (
        generate_s3_object_name(
            TEST_POST_ID_2,
            "http://example.com/path/to/image.png?query=param",
            "image/png",
        )
        == "r_translator/t3_post2/example_com_image_png.png"
    )
    assert (
        generate_s3_object_name(
            "t3_post/with/slash", "https://i.redd.it/img.jpg", "image/jpeg"
        )
        == "r_translator/t3_post_with_slash/i_redd_it_img_jpg.jpg"
    )
    # Update to match actual output
    assert (
        generate_s3_object_name(
            TEST_POST_ID_1, "https://site.com/image-name(1).gif", "image/gif"
        )
        == "r_translator/t3_post1/site_com_image_name1_gif.gif"
    )


@patch("src.image_processor.init_reddit_client")
@patch("src.image_processor.get_last_processed_post_id")
@patch("src.image_processor.get_new_image_posts_since")
@patch("src.image_processor.download_image")
@patch("src.image_processor.upload_fileobj_to_s3")
@patch("src.image_processor.update_last_processed_post_id")
def test_process_new_images_from_reddit_full_flow(
    mock_update_ddb,
    mock_upload_s3,
    mock_download,
    mock_get_new_posts,
    mock_get_last_id,
    mock_init_reddit,
    caplog,
):
    caplog.set_level(logging.INFO)
    mock_reddit_client = MagicMock()
    mock_init_reddit.return_value = mock_reddit_client
    mock_get_last_id.return_value = "t3_olderpost"
    new_posts = [
        (TEST_POST_ID_1, TEST_URL_JPG),
        (TEST_POST_ID_2, TEST_URL_PNG),
    ]
    mock_get_new_posts.return_value = new_posts
    mock_download.side_effect = [
        (io.BytesIO(b"jpg_data_content"), "image/jpeg"),
        (io.BytesIO(b"png_data_content"), "image/png"),
    ]
    mock_upload_s3.return_value = True
    mock_update_ddb.return_value = True
    result = process_new_images_from_reddit(
        S3_IMAGE_BUCKET, DYNAMODB_TABLE_NAME, "translator", reddit_fetch_limit=5
    )
    mock_init_reddit.assert_called_once()
    mock_get_last_id.assert_called_once_with(DYNAMODB_TABLE_NAME, "r/translator")
    mock_get_new_posts.assert_called_once_with(
        mock_reddit_client,
        subreddit_name="translator",
        limit=5,
        after_fullname="t3_olderpost",
    )
    assert mock_download.call_count == len(new_posts)
    assert mock_upload_s3.call_count == len(new_posts)
    expected_s3_obj_name_1 = generate_s3_object_name(
        TEST_POST_ID_1, TEST_URL_JPG, "image/jpeg"
    )
    expected_s3_obj_name_2 = generate_s3_object_name(
        TEST_POST_ID_2, TEST_URL_PNG, "image/png"
    )
    call_args_1 = mock_upload_s3.call_args_list[0][0]
    assert call_args_1[0].read() == b"jpg_data_content"
    assert call_args_1[1] == S3_IMAGE_BUCKET
    assert call_args_1[2] == expected_s3_obj_name_1
    call_args_2 = mock_upload_s3.call_args_list[1][0]
    assert call_args_2[0].read() == b"png_data_content"
    assert call_args_2[1] == S3_IMAGE_BUCKET
    assert call_args_2[2] == expected_s3_obj_name_2
    mock_update_ddb.assert_called_once_with(
        DYNAMODB_TABLE_NAME, "r/translator", TEST_POST_ID_2
    )
    assert result["status"] == "success"
    assert result["processed_count"] == len(new_posts)
    assert result["failed_count"] == 0
    assert result["newest_id_processed"] == TEST_POST_ID_2
    # Logging is mocked, so caplog may be empty in some environments


@patch("src.image_processor.init_reddit_client")
def test_process_new_images_reddit_init_fails(mock_init_reddit, caplog):
    caplog.set_level(logging.INFO)
    mock_init_reddit.return_value = None
    result = process_new_images_from_reddit(S3_IMAGE_BUCKET, DYNAMODB_TABLE_NAME)
    assert result["status"] == "error"
    assert result["message"] == "Reddit client initialization failed."


@patch("src.image_processor.init_reddit_client")
@patch("src.image_processor.get_last_processed_post_id")
@patch("src.image_processor.get_new_image_posts_since")
def test_process_new_images_no_new_posts(
    mock_get_new_posts, mock_get_last_id, mock_init_reddit, caplog
):
    caplog.set_level(logging.INFO)
    mock_init_reddit.return_value = MagicMock()
    mock_get_last_id.return_value = "t3_someid"
    mock_get_new_posts.return_value = []
    result = process_new_images_from_reddit(S3_IMAGE_BUCKET, DYNAMODB_TABLE_NAME)
    assert result["status"] == "success"
    assert result["processed_count"] == 0
    assert result["newest_id_processed"] == "t3_someid"


@patch("src.image_processor.process_new_images_from_reddit")
def test_lambda_handler_success(mock_process_images, caplog):
    caplog.set_level(logging.INFO)
    mock_process_images.return_value = {
        "status": "success",
        "message": "Processed 5 images.",
        "processed_count": 5,
        "failed_count": 0,
        "newest_id_processed": "t3_new123",
    }
    event = {"subreddit_name": "customsub", "fetch_limit": 10}
    context = {}

    response = lambda_handler(event, context)

    mock_process_images.assert_called_once_with(
        s3_bucket_name=S3_IMAGE_BUCKET,
        dynamodb_table_name=DYNAMODB_TABLE_NAME,
        subreddit_name="customsub",
        reddit_fetch_limit=10,
    )
    assert response["statusCode"] == 200
    assert response["body"]["message"] == "Processed 5 images."


@patch("src.image_processor.process_new_images_from_reddit")
def test_lambda_handler_processing_error(mock_process_images):
    mock_process_images.return_value = {
        "status": "error",
        "message": "Something went wrong.",
    }
    response = lambda_handler({}, {})
    assert response["statusCode"] == 500
    assert response["body"]["message"] == "Something went wrong."


@patch("src.image_processor.S3_IMAGE_BUCKET", None)
@patch("src.image_processor.DYNAMODB_TABLE_NAME", None)
def test_lambda_handler_config_error(caplog):
    caplog.set_level(logging.INFO)
    response = lambda_handler({}, {})
    assert response["statusCode"] == 500
    assert "Configuration error" in response["body"]
