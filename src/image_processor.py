"""Image processing and content type handling for media files.

This module provides utilities for processing images, including content type detection,
validation, and S3 upload preparation. It works in conjunction with Reddit scraping
and AWS services to process and store media files.
"""

import asyncio
import io
import logging
import os
from typing import Any, Dict, List, Mapping, Optional, Tuple, cast
from urllib.parse import urlparse

import aiohttp

from config import (
    DYNAMODB_TABLE_NAME,
    MEDIA_PROCESSING_CONFIG,
    REDDIT_SCRAPING_CONFIG,
    S3_IMAGE_BUCKET,
)
from src.amazon_dynamodb import (
    get_last_processed_post_id,
    update_last_processed_post_id,
)
from src.reddit_scraper import get_new_image_posts_since, init_reddit_client
from src.storage_adapter import upload_fileobj_to_s3

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# pull in supported types
SUPPORTED_IMAGE_TYPES: Mapping[str, str] = MEDIA_PROCESSING_CONFIG["SUPPORTED_IMAGE_TYPES"]  # type: ignore


def _infer_content_type_from_url(url: str, original_content_type: str) -> Optional[str]:
    """Infers the content type of a media file from its URL or original content type.

    Attempts to determine the correct MIME type for a media file using either its
    original content type (if supported) or by examining the file extension in the URL.

    Args:
        url (str): The URL of the media file to analyze.
        original_content_type (str): The content type provided in the response headers
            or metadata.

    Returns:
        Optional[str]: The inferred MIME type if successfully determined and supported,
            None otherwise.

    Note:
        Supported image types are defined in MEDIA_PROCESSING_CONFIG["SUPPORTED_IMAGE_TYPES"].
        Logs a warning if the content type cannot be determined or is unsupported.
    """
    supported_types = SUPPORTED_IMAGE_TYPES
    if original_content_type in supported_types:
        return original_content_type

    parsed_url = urlparse(url)
    ext = os.path.splitext(parsed_url.path)[1].lower()

    for mime, known_ext in supported_types.items():
        if ext == known_ext:
            logging.info(
                f"Inferred content type '{mime}' for URL {url} from extension '{ext}'."
            )
            return str(mime)  # Ensure we return str, not Any

    logging.warning(
        f"Skipping unsupported content type '{original_content_type}' or unknown extension for URL: {url}"
    )
    return None


async def _handle_retry_logic_async(
    retry_count: int, retries: int, url: str, error: Exception
) -> Optional[int]:
    """Handle retry logic and logging for failed download attempts."""
    retry_count += 1
    if retry_count < retries:
        wait_time = 2**retry_count  # Exponential backoff
        logging.warning(
            f"Download attempt {retry_count} failed for {url}: {error}. Retrying in {wait_time}s..."
        )
        await asyncio.sleep(wait_time)
        return retry_count
    else:
        logging.error(f"All download attempts failed for {url}: {error}")
        return None


async def download_image_async(
    session: aiohttp.ClientSession, url: str, retries: Optional[int] = None
) -> Tuple[Optional[io.BytesIO], Optional[str]]:
    """Download an image from a URL with retries and enhanced error handling asynchronously.

    Args:
        session (aiohttp.ClientSession): The aiohttp session to use for the request.
        url (str): The URL to download from.
        retries (int): Number of retries for failed downloads.

    Returns:
        Tuple[Optional[io.BytesIO], Optional[str]]: (image_data, content_type) or (None, None) on failure.
    """
    if retries is None:
        retries = cast(int, MEDIA_PROCESSING_CONFIG["MAX_RETRIES"])

    headers: Dict[str, str] = {
        "User-Agent": cast(str, MEDIA_PROCESSING_CONFIG["USER_AGENT_FALLBACK"])
    }
    retry_count = 0

    while retry_count < retries:
        try:
            timeout = aiohttp.ClientTimeout(
                total=cast(float, MEDIA_PROCESSING_CONFIG["DOWNLOAD_TIMEOUT"])
            )
            async with session.get(
                url,
                headers=headers,
                timeout=timeout,
            ) as response:
                response.raise_for_status()

                original_content_type = (
                    response.headers.get("Content-Type", "")
                    .lower()
                    .split(";")[0]
                    .strip()
                )

                content_type = _infer_content_type_from_url(url, original_content_type)
                if not content_type:
                    return (None, None)

                image_bytes = io.BytesIO(await response.read())
                return (image_bytes, content_type)

        except aiohttp.ClientError as e:
            new_retry_count = await _handle_retry_logic_async(
                retry_count, retries, url, e
            )
            if new_retry_count is None:
                return (None, None)
            retry_count = new_retry_count

        except Exception as e:
            logging.error(f"An unexpected error occurred while downloading {url}: {e}")
            return (None, None)

    return (None, None)


def _get_extension(base_name: str, content_type: str, image_url: str) -> str:
    supported_types = SUPPORTED_IMAGE_TYPES
    extension = supported_types.get(content_type)
    if not extension:
        url_ext = os.path.splitext(base_name)[1]
        extension = (
            url_ext if url_ext and url_ext in supported_types.values() else ".img"
        )
        logging.warning(
            f"Content type {content_type} unknown, derived extension {extension} for {image_url}"
        )
    return str(extension)


def _fallback_cleaned_base_name(parsed_url: Any, image_url: str) -> str:
    path_segments = [seg for seg in parsed_url.path.split("/") if seg]
    if path_segments:
        return "".join(
            c if c.isalnum() else "_"
            for c in path_segments[-1]
            if c.isalnum() or c in ["_", "-"]
        )
    fallback_name_part = "".join(
        c if c.isalnum() else "_"
        for c in parsed_url.query + parsed_url.fragment
        if c.isalnum()
    )
    return fallback_name_part if fallback_name_part else hex(hash(image_url))[2:]


def _get_cleaned_base_name(
    parsed_url: Any, base_name: str, extension: str, image_url: str
) -> str:
    cleaned_base_name = "".join(
        c if c.isalnum() else "_"
        for c in base_name
        if c.isalnum() or c in [".", "_", "-"]
    )
    if not cleaned_base_name or cleaned_base_name == extension.replace(".", "_"):
        cleaned_base_name = _fallback_cleaned_base_name(parsed_url, image_url)
    return cleaned_base_name


def generate_s3_object_name(
    post_id: str, image_url: str, content_type: str, subreddit: str = "translator"
) -> str:
    """Generate a unique S3 object name for the image.

    Args:
        post_id (str): Reddit post ID
        image_url (str): Original image URL
        content_type (str): MIME type of the image
        subreddit (str): Subreddit name for organizing files

    Returns:
        str: Generated S3 object key
    """
    try:
        parsed_url = urlparse(image_url)
        base_name = os.path.basename(parsed_url.path)
        cleaned_post_id = "".join(c if c.isalnum() else "_" for c in post_id)
        domain_part = parsed_url.netloc.replace(".", "_")
        extension = _get_extension(base_name, content_type, image_url)
        cleaned_base_name = _get_cleaned_base_name(
            parsed_url, base_name, extension, image_url
        )
        object_name = f"r_{subreddit}/{cleaned_post_id}/{domain_part}_{cleaned_base_name}{extension}"
        return object_name[:1000]
    except Exception as e:
        logging.error(
            f"Error generating S3 object name for URL {image_url}, post ID {post_id}: {e}"
        )
        return f"r_{subreddit}/{post_id}/unknown_image_{hex(hash(image_url))[2:]}{SUPPORTED_IMAGE_TYPES.get(content_type, '.img')}"


async def _process_image_posts_async(
    new_posts_data: List[Tuple[str, str]],
    s3_bucket_name: str,
    subreddit: str = "translator",
) -> Tuple[int, int, Optional[str]]:
    """Process a batch of image posts asynchronously.

    Args:
        new_posts_data (List[Tuple[str, str]]): List of (post_id, image_url) pairs
        s3_bucket_name (str): Target S3 bucket
        subreddit (str): Subreddit name for organizing files

    Returns:
        Tuple[int, int, Optional[str]]: (successful_uploads, failed_attempts, newest_id_in_batch)
    """
    successful_uploads = 0
    failed_attempts = 0
    newest_id_in_batch = None

    async with aiohttp.ClientSession() as session:
        tasks = []
        for post_id, image_url in new_posts_data:
            tasks.append(asyncio.create_task(download_image_async(session, image_url)))

        download_results = await asyncio.gather(*tasks)

        for i, (image_data, content_type) in enumerate(download_results):
            post_id, image_url = new_posts_data[i]
            if image_data and content_type:
                object_name = generate_s3_object_name(
                    post_id, image_url, content_type, subreddit
                )
                logging.info(
                    f"Uploading '{object_name}' to S3 bucket '{s3_bucket_name}'..."
                )

                image_data.seek(0)
                if upload_fileobj_to_s3(image_data, s3_bucket_name, object_name):
                    logging.info(f"Successfully uploaded '{object_name}' to S3.")
                    successful_uploads += 1
                    newest_id_in_batch = post_id
                else:
                    logging.error(
                        f"Failed to upload '{object_name}' (from Post ID: {post_id}, URL: {image_url}) to S3."
                    )
                    failed_attempts += 1
            else:  # pragma: no cover
                logging.warning(  # pragma: no cover
                    f"Skipping upload for Post ID: {post_id}, URL: {image_url} due to download error or unsupported type."
                )
                failed_attempts += 1  # pragma: no cover

    return successful_uploads, failed_attempts, newest_id_in_batch


async def process_new_images_from_reddit_async(
    s3_bucket_name: str,
    dynamodb_table_name: str,
    subreddit_name: str = "translator",
    reddit_fetch_limit: int = 25,
) -> Dict[str, Any]:
    """Process new images from specified subreddit and store in S3 asynchronously.

    Args:
        s3_bucket_name (str): Target S3 bucket
        dynamodb_table_name (str): DynamoDB table for state tracking
        subreddit_name (str): Target subreddit name
        reddit_fetch_limit (int): Maximum posts to process

    Returns:
        Dict[str, Any]: Processing results
    """
    logging.info(f"Starting image processing job for r/{subreddit_name}")

    # Initialize Reddit client
    reddit_client = init_reddit_client()
    if not reddit_client:
        logging.error("Failed to initialize Reddit client. Aborting job.")
        return {"status": "error", "message": "Reddit client initialization failed."}

    # Get last processed state
    subreddit_key = f"r/{subreddit_name}"
    last_processed_id = get_last_processed_post_id(dynamodb_table_name, subreddit_key)
    logging.info(
        f"Last processed post ID for {subreddit_key} from DynamoDB: {last_processed_id}"
    )

    # Fetch new posts
    new_posts_data = get_new_image_posts_since(
        reddit_client,
        subreddit_name=subreddit_name,
        limit=reddit_fetch_limit,
        after_fullname=last_processed_id,
    )

    if not new_posts_data:
        logging.info("No new image posts found since last run.")
        return {
            "status": "success",
            "message": "No new images to process.",
            "processed_count": 0,
            "newest_id_processed": last_processed_id,
        }

    # Process the new posts
    logging.info(
        f"Found {len(new_posts_data)} new image posts/URLs. Starting download and upload process..."
    )
    (
        successful_uploads,
        failed_attempts,
        newest_id_in_batch,
    ) = await _process_image_posts_async(new_posts_data, s3_bucket_name, subreddit_name)

    # Update processing state
    if newest_id_in_batch:
        logging.info(
            f"Updating DynamoDB with newest processed post ID for {subreddit_key}: {newest_id_in_batch}"
        )
        if not update_last_processed_post_id(
            dynamodb_table_name, subreddit_key, newest_id_in_batch
        ):
            logging.error(
                f"Failed to update DynamoDB with newest_id: {newest_id_in_batch} for {subreddit_key}."
            )
    elif successful_uploads == 0 and new_posts_data:  # pragma: no cover
        logging.warning(  # pragma: no cover
            f"No images were successfully uploaded in this run, DynamoDB state for {subreddit_key} remains {last_processed_id}."
        )

    # Generate summary
    summary_message = (
        f"Processing summary for {subreddit_key}: "
        f"Total new posts/URLs fetched: {len(new_posts_data)}. "
        f"Successful uploads: {successful_uploads}. "
        f"Failed attempts: {failed_attempts}. "
        f"Newest post ID processed in this run: {newest_id_in_batch if newest_id_in_batch else 'None'}. "
        f"DynamoDB state for {subreddit_key} is now: {newest_id_in_batch if newest_id_in_batch else last_processed_id}."
    )
    logging.info(summary_message)

    return {
        "status": "success",
        "message": summary_message,
        "processed_count": successful_uploads,
        "failed_count": failed_attempts,
        "newest_id_processed": (
            newest_id_in_batch if newest_id_in_batch else last_processed_id
        ),
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler function.

    Args:
        event (dict): Lambda event containing optional parameters
        context (dict): Lambda context

    Returns:
        dict: Lambda response
    """
    s3_bucket = S3_IMAGE_BUCKET
    ddb_table = DYNAMODB_TABLE_NAME

    if not s3_bucket or not ddb_table:
        logging.error(
            "Missing required configuration: S3 bucket or DynamoDB table name"
        )
        return {
            "statusCode": 500,
            "body": "Configuration error: S3 bucket or DynamoDB table name missing.",
        }

    # Support both single subreddit and list of subreddits
    subreddits = event.get("subreddits", None)
    if not subreddits:
        subreddits = [event.get("subreddit_name", "translator")]

    limit = event.get("fetch_limit", REDDIT_SCRAPING_CONFIG["REDDIT_FETCH_LIMIT"])

    async def process_all_subreddits() -> Dict[str, Any]:
        results = {}
        total_processed = 0
        total_failed = 0

        for subreddit in subreddits:
            logging.info(f"Processing subreddit: r/{subreddit}")
            result = await process_new_images_from_reddit_async(
                s3_bucket_name=s3_bucket,
                dynamodb_table_name=ddb_table,
                subreddit_name=subreddit,
                reddit_fetch_limit=limit,
            )
            results[subreddit] = result

            if result.get("status") == "error":
                return {
                    "statusCode": 500,
                    "body": {
                        "status": "error",
                        "message": result.get("message", "Something went wrong."),
                    },
                }

            processed = int(result.get("processed_count", 0))
            failed = int(result.get("failed_count", 0))
            total_processed += processed
            total_failed += failed

        return {
            "statusCode": 200,
            "body": {
                "status": "success",
                "message": f"Processed {total_processed} images.",
                "total_processed": total_processed,
                "total_failed": total_failed,
                "subreddit_results": results,
            },
        }

    return asyncio.run(process_all_subreddits())


if __name__ == "__main__":
    logging.info("Starting image processing script directly (not as Lambda)...")

    async def main() -> None:
        # Example direct invocation with multiple subreddits:
        result = await asyncio.gather(
            *(
                process_new_images_from_reddit_async(
                    s3_bucket_name=S3_IMAGE_BUCKET,
                    dynamodb_table_name=DYNAMODB_TABLE_NAME,
                    subreddit_name=subreddit,
                    reddit_fetch_limit=cast(
                        int, REDDIT_SCRAPING_CONFIG["POST_SEARCH_AMOUNT"]
                    ),
                )
                for subreddit in cast(List[str], REDDIT_SCRAPING_CONFIG["SUBREDDITS"])
            )
        )
        logging.info(f"Direct script execution result: {result}")

    asyncio.run(main())
