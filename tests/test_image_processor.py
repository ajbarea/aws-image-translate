import asyncio
import io
import logging
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

from config import DYNAMODB_TABLE_NAME, S3_IMAGE_BUCKET
from src.image_processor import (
    _infer_content_type_from_url,
    download_image_async,
    generate_s3_object_name,
    lambda_handler,
    process_new_images_from_reddit_async,
)

# Test data
TEST_URL_JPG = "https://example.com/image.jpg"
TEST_URL_PNG = "https://example.com/image.png"
TEST_URL_GIF = "https://example.com/image.gif"
TEST_URL_UNSUPPORTED = "https://example.com/document.pdf"
TEST_URL_NO_EXT = "https://example.com/image"
TEST_POST_ID_1 = "t3_post1"
TEST_POST_ID_2 = "t3_post2"


class TestInferContentType:
    """Test content type inference logic."""

    @pytest.mark.parametrize(
        "url,original_content_type,expected",
        [
            ("https://example.com/image.jpg", "image/jpeg", "image/jpeg"),
            ("https://example.com/image.png", "application/octet-stream", "image/png"),
            ("https://example.com/image.gif", "image/gif", "image/gif"),
            ("https://example.com/document.pdf", "application/pdf", None),
            ("https://example.com/unknown", "unknown/type", None),
        ],
    )
    def test_infer_content_type_from_url(self, url, original_content_type, expected):
        """Test content type inference from URL and original type."""
        result = _infer_content_type_from_url(url, original_content_type)
        assert (
            result == expected
        ), f"Expected {expected} for URL {url} with type {original_content_type}"


class TestDownloadImageAsync:
    """Test async image downloading functionality."""

    @pytest.mark.asyncio
    async def test_download_image_success_jpg(self):
        """Test successful download of JPEG image."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.read = AsyncMock(return_value=b"jpeg_data")
        mock_response.raise_for_status = Mock()

        # Create a proper async context manager mock
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = Mock(return_value=mock_context_manager)

        image_bytes, content_type = await download_image_async(
            mock_session, TEST_URL_JPG, retries=1
        )

        mock_session.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        assert image_bytes is not None, "Expected image bytes to be returned"
        assert (
            image_bytes.read() == b"jpeg_data"
        ), "Image content should match expected data"
        assert content_type == "image/jpeg", "Content type should be image/jpeg"

    @pytest.mark.asyncio
    async def test_download_image_success_png_infer_from_url(self):
        """Test successful download with content type inferred from URL extension."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/octet-stream"}
        mock_response.read = AsyncMock(return_value=b"png_data")
        mock_response.raise_for_status = Mock()

        # Create a proper async context manager mock
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = Mock(return_value=mock_context_manager)

        image_bytes, content_type = await download_image_async(
            mock_session, TEST_URL_PNG, retries=1
        )

        assert image_bytes is not None, "Expected image bytes to be returned"
        assert (
            image_bytes.read() == b"png_data"
        ), "Image content should match expected data"
        assert (
            content_type == "image/png"
        ), "Content type should be inferred as image/png"

    @pytest.mark.asyncio
    async def test_download_image_unsupported_content_type(self, caplog):
        """Test handling of unsupported content types."""
        caplog.set_level(logging.WARNING)
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.raise_for_status = Mock()

        # Create a proper async context manager mock
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = Mock(return_value=mock_context_manager)

        image_bytes, content_type = await download_image_async(
            mock_session, TEST_URL_UNSUPPORTED, retries=1
        )

        assert image_bytes is None, "Expected None for unsupported content type"
        assert content_type is None, "Expected None for unsupported content type"
        assert "Skipping unsupported content type" in caplog.text

    @pytest.mark.asyncio
    async def test_download_image_client_error_with_retry(self, caplog):
        """Test download failure with retry mechanism."""
        caplog.set_level(logging.WARNING)
        mock_session = AsyncMock()
        # Mock the session.get to raise aiohttp.ClientError
        mock_session.get = Mock(side_effect=aiohttp.ClientError("Connection error"))

        image_bytes, content_type = await download_image_async(
            mock_session, TEST_URL_JPG, retries=2
        )

        assert image_bytes is None, "Expected None on connection error"
        assert content_type is None, "Expected None on connection error"
        assert "All download attempts failed" in caplog.text

    @pytest.mark.asyncio
    async def test_download_image_unexpected_error(self, caplog):
        """Test handling of unexpected errors during download."""
        caplog.set_level(logging.ERROR)
        mock_session = AsyncMock()
        # Mock the session.get to raise a generic Exception
        mock_session.get = Mock(side_effect=Exception("Unexpected error"))

        image_bytes, content_type = await download_image_async(
            mock_session, TEST_URL_JPG, retries=1
        )

        assert image_bytes is None, "Expected None on unexpected error"
        assert content_type is None, "Expected None on unexpected error"
        assert "An unexpected error occurred" in caplog.text
        assert content_type is None, "Expected None on unexpected error"
        assert "An unexpected error occurred" in caplog.text


class TestGenerateS3ObjectName:
    """Test S3 object name generation."""

    @pytest.mark.parametrize(
        "post_id,url,content_type,subreddit,expected_pattern",
        [
            (
                TEST_POST_ID_1,
                "https://i.redd.it/abc123xyz.jpg",
                "image/jpeg",
                "translator",
                "r_translator/t3_post1/i_redd_it_abc123xyz_jpg.jpg",
            ),
            (
                TEST_POST_ID_2,
                "https://example.com/path/to/image.png?query=param",
                "image/png",
                "translator",
                "r_translator/t3_post2/example_com_image_png.png",
            ),
            (
                "t3_post/with/slash",
                "https://i.redd.it/img.jpg",
                "image/jpeg",
                "translator",
                "r_translator/t3_post_with_slash/i_redd_it_img_jpg.jpg",
            ),
        ],
    )
    def test_generate_s3_object_name_patterns(
        self, post_id, url, content_type, subreddit, expected_pattern
    ):
        """Test S3 object name generation with various inputs."""
        result = generate_s3_object_name(post_id, url, content_type, subreddit)
        assert result == expected_pattern, f"Expected {expected_pattern}, got {result}"

    def test_generate_s3_object_name_special_characters(self):
        """Test handling of special characters in URLs and post IDs."""
        result = generate_s3_object_name(
            TEST_POST_ID_1,
            "https://site.com/image-name(1).gif",
            "image/gif",
            "translator",
        )
        expected = "r_translator/t3_post1/site_com_image_name1_gif.gif"
        assert result == expected, f"Expected {expected}, got {result}"

    def test_generate_s3_object_name_error_handling(self, caplog):
        """Test error handling in S3 object name generation."""
        caplog.set_level(logging.ERROR)

        # Test with invalid URL that might cause parsing errors
        result = generate_s3_object_name(
            "test_post", "not_a_valid_url", "image/jpeg", "translator"
        )

        # Should still return a valid object name even with errors
        assert result.startswith(
            "r_translator/"
        ), "Should still generate valid object name"
        assert "test_post" in result, "Should include post ID in fallback name"


class TestProcessNewImagesFromRedditAsync:
    """Test async image processing from Reddit."""

    @pytest.mark.asyncio
    @patch("src.image_processor.init_reddit_client")
    @patch("src.image_processor.get_last_processed_post_id")
    @patch("src.image_processor.get_new_image_posts_since")
    @patch("src.image_processor.upload_fileobj_to_s3")
    @patch("src.image_processor.update_last_processed_post_id")
    async def test_process_new_images_full_flow(
        self,
        mock_update_ddb,
        mock_upload_s3,
        mock_get_new_posts,
        mock_get_last_id,
        mock_init_reddit,
        caplog,
    ):
        """Test complete flow of processing new images from Reddit."""
        caplog.set_level(logging.INFO)

        # Setup mocks
        mock_reddit_client = MagicMock()
        mock_init_reddit.return_value = mock_reddit_client
        mock_get_last_id.return_value = "t3_olderpost"
        new_posts = [
            (TEST_POST_ID_1, TEST_URL_JPG),
            (TEST_POST_ID_2, TEST_URL_PNG),
        ]
        mock_get_new_posts.return_value = new_posts
        mock_upload_s3.return_value = True
        mock_update_ddb.return_value = True

        # Mock aiohttp session and responses
        with patch("src.image_processor.aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock responses for each URL
            mock_responses = []
            test_data = [
                (b"jpg_data_content", "image/jpeg"),
                (b"png_data_content", "image/png"),
            ]

            for data, content_type in test_data:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"Content-Type": content_type}
                mock_response.read = AsyncMock(return_value=data)
                mock_response.raise_for_status = Mock()
                mock_responses.append(mock_response)

            # Create async context managers for each response
            async_context_managers = []
            for response in mock_responses:
                context_manager = AsyncMock()
                context_manager.__aenter__ = AsyncMock(return_value=response)
                context_manager.__aexit__ = AsyncMock(return_value=None)
                async_context_managers.append(context_manager)

            mock_session.get = Mock(side_effect=async_context_managers)

            # Execute the function
            result = await process_new_images_from_reddit_async(
                S3_IMAGE_BUCKET, DYNAMODB_TABLE_NAME, "translator", reddit_fetch_limit=5
            )

        # Verify interactions
        mock_init_reddit.assert_called_once()
        mock_get_last_id.assert_called_once_with(DYNAMODB_TABLE_NAME, "r/translator")
        mock_get_new_posts.assert_called_once_with(
            mock_reddit_client,
            subreddit_name="translator",
            limit=5,
            after_fullname="t3_olderpost",
        )
        assert mock_upload_s3.call_count == len(new_posts), "Should upload all images"
        mock_update_ddb.assert_called_once_with(
            DYNAMODB_TABLE_NAME, "r/translator", TEST_POST_ID_2
        )

        # Verify result
        assert result["status"] == "success", "Processing should succeed"
        assert result["processed_count"] == len(
            new_posts
        ), f"Should process {len(new_posts)} images"
        assert result["failed_count"] == 0, "Should have no failures"
        assert (
            result["newest_id_processed"] == TEST_POST_ID_2
        ), "Should track newest processed ID"

    @pytest.mark.asyncio
    @patch("src.image_processor.init_reddit_client")
    async def test_process_new_images_reddit_init_fails(self, mock_init_reddit):
        """Test handling of Reddit client initialization failure."""
        mock_init_reddit.return_value = None

        result = await process_new_images_from_reddit_async(
            S3_IMAGE_BUCKET, DYNAMODB_TABLE_NAME
        )

        assert result["status"] == "error", "Should return error status"
        assert (
            result["message"] == "Reddit client initialization failed."
        ), "Should have error message"

    @pytest.mark.asyncio
    @patch("src.image_processor.init_reddit_client")
    @patch("src.image_processor.get_last_processed_post_id")
    @patch("src.image_processor.get_new_image_posts_since")
    async def test_process_new_images_no_new_posts(
        self, mock_get_new_posts, mock_get_last_id, mock_init_reddit
    ):
        """Test handling when no new posts are found."""
        mock_init_reddit.return_value = MagicMock()
        mock_get_last_id.return_value = "t3_someid"
        mock_get_new_posts.return_value = []

        result = await process_new_images_from_reddit_async(
            S3_IMAGE_BUCKET, DYNAMODB_TABLE_NAME
        )

        assert result["status"] == "success", "Should succeed with no posts"
        assert result["processed_count"] == 0, "Should process zero images"
        assert (
            result["newest_id_processed"] == "t3_someid"
        ), "Should maintain last processed ID"


class TestLambdaHandler:
    """Test Lambda handler functionality."""

    @pytest.mark.parametrize(
        "event,expected_subreddit,expected_limit",
        [
            ({"subreddit_name": "customsub", "fetch_limit": 10}, "customsub", 10),
            (
                {"subreddits": ["sub1", "sub2"], "fetch_limit": 15},
                "sub2",
                15,
            ),  # Last subreddit processed
            ({}, "translator", 25),  # Default values
        ],
    )
    @patch("src.image_processor.process_new_images_from_reddit_async")
    def test_lambda_handler_parameter_handling(
        self, mock_process_images, event, expected_subreddit, expected_limit
    ):
        """Test Lambda handler parameter processing."""
        mock_process_images.return_value = {
            "status": "success",
            "message": "Processed 5 images.",
            "processed_count": 5,
            "failed_count": 0,
            "newest_id_processed": "t3_new123",
        }

        response = lambda_handler(event, {})

        # For multiple subreddits, check that the function was called multiple times
        if "subreddits" in event:
            assert mock_process_images.call_count == len(
                event["subreddits"]
            ), "Should call once per subreddit"
            # Check the last call (which determines the expected_subreddit)
            last_call_args = mock_process_images.call_args_list[-1]
            assert last_call_args[1]["subreddit_name"] == expected_subreddit
            assert last_call_args[1]["reddit_fetch_limit"] == expected_limit
        else:
            # Single subreddit case
            call_args = mock_process_images.call_args
            assert call_args[1]["subreddit_name"] == expected_subreddit
            assert call_args[1]["reddit_fetch_limit"] == expected_limit

        assert response["statusCode"] == 200

    @patch("src.image_processor.process_new_images_from_reddit_async")
    def test_lambda_handler_processing_error(self, mock_process_images):
        """Test Lambda handler error response."""
        mock_process_images.return_value = {
            "status": "error",
            "message": "Something went wrong.",
        }

        response = lambda_handler({}, {})

        assert response["statusCode"] == 500, "Should return 500 on processing error"
        assert (
            response["body"]["message"] == "Something went wrong."
        ), "Should include error message"

    @patch("src.image_processor.S3_IMAGE_BUCKET", None)
    @patch("src.image_processor.DYNAMODB_TABLE_NAME", None)
    def test_lambda_handler_config_error(self):
        """Test Lambda handler configuration error handling."""
        response = lambda_handler({}, {})

        assert response["statusCode"] == 500, "Should return 500 on config error"
        assert (
            "Configuration error" in response["body"]
        ), "Should indicate configuration error"

    @patch("src.image_processor.process_new_images_from_reddit_async")
    def test_lambda_handler_multiple_subreddits(self, mock_process_images):
        """Test Lambda handler with multiple subreddits."""
        mock_process_images.return_value = {
            "status": "success",
            "message": "Processed images.",
            "processed_count": 3,
            "failed_count": 1,
        }

        event = {"subreddits": ["translator", "learnpython"]}
        response = lambda_handler(event, {})

        # Should be called twice, once for each subreddit
        assert mock_process_images.call_count == 2, "Should process both subreddits"
        assert response["statusCode"] == 200, "Should succeed"
        assert response["body"]["total_processed"] == 6, "Should sum processed counts"
        assert response["body"]["total_failed"] == 2, "Should sum failed counts"
