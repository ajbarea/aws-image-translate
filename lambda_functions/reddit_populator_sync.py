"""Reddit image populator for AWS Lambda.

This module provides an implementation for fetching and storing Reddit images in S3, with concurrent processing, rate limiting, and batch operations for maximum efficiency.
"""

import concurrent.futures
import hashlib
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urlparse

import boto3
import requests
from aws_clients import get_s3_client, performance_monitor
from botocore.exceptions import ClientError
from image_processor import detect_text_from_image
from reddit_config import get_default_subreddit, get_subreddits_from_env

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

S3_IMAGE_BUCKET = os.environ.get("S3_BUCKET", "lenslate-image-storage")
PROCESSED_POSTS_TABLE = os.environ.get(
    "REDDIT_PROCESSED_POSTS_TABLE", "lenslate-reddit-processed-posts-dev"
)
TRANSLATIONS_TABLE = os.environ.get("TRANSLATIONS_TABLE", "lenslate-translations")

REDDIT_SCRAPING_CONFIG = {
    "DEFAULT_SUBREDDIT": get_default_subreddit(),
    "SUBREDDITS": get_subreddits_from_env(),
    "REDDIT_FETCH_LIMIT": 50,
}

try:
    from reddit_scraper_sync import get_image_urls_from_subreddits, init_reddit_client

    logger.info("[SUCCESS] Successfully imported synchronous reddit scraper")
except ImportError as e:
    logger.error(f"[ERROR] Import failed: {e}")

    def init_reddit_client() -> Optional[Any]:
        return None

    def get_image_urls_from_subreddits(
        reddit: Optional[Any],
        subreddits: Optional[List[str]] = None,
        limit: int = 25,
    ) -> Dict[str, List[str]]:
        return {}


def get_dynamodb_client():
    """Get DynamoDB client."""
    return boto3.client("dynamodb")


def check_content_hash_in_existing_translations(content_hash: str) -> bool:
    """Check if content hash exists in existing translations table (reuse existing infrastructure)."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TRANSLATIONS_TABLE)

        # Query the existing text-language-index to see if this content hash exists
        response = table.query(
            IndexName="text-language-index",
            KeyConditionExpression="text_hash = :hash",
            ExpressionAttributeValues={":hash": content_hash},
            Limit=1,
        )

        return len(response["Items"]) > 0

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "ResourceNotFoundException":
            logger.warning(
                f"DynamoDB table {TRANSLATIONS_TABLE} not found. Will process all images."
            )
            return False
        logger.error(f"Error checking content hash in translations: {e}")
        return False
    except Exception as e:
        logger.error(f"Error checking content hash: {e}")
        return False


# Simple in-memory cache for this Lambda execution to avoid repeated URL checks
_processed_urls_cache = set()


def is_url_already_processed(url: str) -> bool:
    """Check if URL was already processed in this execution (simple cache approach)."""
    return url in _processed_urls_cache


def mark_url_as_processed_in_cache(url: str):
    """Mark URL as processed in local cache."""
    _processed_urls_cache.add(url)


def upload_to_s3(file_data: io.BytesIO, bucket: str, key: str) -> bool:
    """Upload file data to S3 bucket."""
    start_time = time.time()
    try:
        file_data.seek(0)
        s3_client = get_s3_client()
        s3_client.upload_fileobj(file_data, bucket, key)
        duration = time.time() - start_time
        performance_monitor.record_operation("s3_upload", duration, True)
        return True
    except Exception as e:
        duration = time.time() - start_time
        performance_monitor.record_operation("s3_upload", duration, False)
        logger.error(f"[ERROR] Failed to upload {key} to S3: {e}")
        return False


def process_image_batch(
    image_urls: List[str],
    subreddit_name: str,
    images_to_get: int,
    post_ids: Optional[List[str]] = None,
) -> int:
    """Process a batch of images concurrently until enough are found."""
    successful_uploads = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(
                download_and_upload_image,
                url,
                subreddit_name,
                i,
                post_ids[i] if post_ids and i < len(post_ids) else None,
            ): url
            for i, url in enumerate(image_urls)
        }

        for future in concurrent.futures.as_completed(future_to_url):
            if successful_uploads >= images_to_get:
                # Cancel remaining futures
                for f in future_to_url:
                    f.cancel()
                break

            url = future_to_url[future]
            try:
                success = future.result()
                if success:
                    successful_uploads += 1
                    logger.info(
                        f"[SUCCESS] Successfully processed and stored image with text from: {url}"
                    )
            except Exception as e:
                if not isinstance(e, concurrent.futures.CancelledError):
                    logger.error(f"[ERROR] Exception processing {url}: {e}")

    return successful_uploads


def check_image_duplicate(
    image_data: bytes, s3_client, url: Optional[str] = None
) -> Tuple[bool, str]:
    """Check if an image with the same content already exists using existing infrastructure.

    Returns:
        Tuple of (is_duplicate, content_hash)
    """
    try:
        # Create content hash
        content_hash = hashlib.sha256(image_data).hexdigest()

        # First check if we have this URL in our processed URLs cache (this execution only)
        if url and is_url_already_processed(url):
            logger.info(f"URL already processed in this execution: {url}")
            return True, content_hash

        # Check existing translations table for this content hash (reuse existing infrastructure!)
        if check_content_hash_in_existing_translations(content_hash):
            logger.info(
                f"Duplicate image detected with hash {content_hash[:12]}... (found in translations)"
            )
            return True, content_hash

        return False, content_hash

    except Exception as e:
        logger.error(f"Error checking for duplicates: {e}")
        return False, hashlib.sha256(image_data).hexdigest()


def download_and_upload_image(
    url: str, subreddit_name: str, index: int, post_id: Optional[str] = None
) -> bool:
    """Download, check for text, check for duplicates, and upload a single image."""
    try:
        image_data, content_type = download_image_sync(url)
        if not image_data:
            mark_url_as_processed_in_cache(url)  # Mark failed downloads
            return False

        s3_client = get_s3_client()

        # Check for duplicate content BEFORE processing
        is_duplicate, content_hash = check_image_duplicate(image_data, s3_client, url)
        if is_duplicate:
            logger.info(f"Skipping duplicate image from {url}")
            mark_url_as_processed_in_cache(url)
            return False

        extension = get_file_extension(url, content_type or "")
        staging_prefix = "staging/reddit/"
        final_prefix = "reddit/"

        # Use content hash for staging filename to avoid URL-based conflicts
        staging_filename = f"{content_hash[:16]}.{extension}"
        staging_key = f"{staging_prefix}{staging_filename}"

        try:
            # 1. Upload to staging with content hash in metadata
            s3_client.put_object(
                Bucket=S3_IMAGE_BUCKET,
                Key=staging_key,
                Body=image_data,
                ContentType=content_type or "image/jpeg",
                Metadata={
                    "content-hash": content_hash,
                    "source-url": url,
                    "subreddit": subreddit_name,
                },
            )

            # 2. Detect text
            detected_text = detect_text_from_image(S3_IMAGE_BUCKET, staging_key)

            if detected_text and detected_text.strip():
                logger.info(f"Text found in {url}. Moving to final location.")
                # 3a. Move to final location with content hash in metadata
                timestamp = int(time.time())
                final_filename = f"{timestamp}-{content_hash[:8]}.{extension}"
                final_key = f"{final_prefix}{subreddit_name}/{final_filename}"

                s3_client.copy_object(
                    Bucket=S3_IMAGE_BUCKET,
                    CopySource={"Bucket": S3_IMAGE_BUCKET, "Key": staging_key},
                    Key=final_key,
                    MetadataDirective="REPLACE",
                    Metadata={
                        "content-hash": content_hash,
                        "source-url": url,
                        "subreddit": subreddit_name,
                        "processed-at": str(timestamp),
                        "post-id": post_id or "unknown",
                    },
                    ContentType=content_type or "image/jpeg",
                )

                # Mark URL as processed in local cache (no new tables needed!)
                mark_url_as_processed_in_cache(url)

                # If we have a post_id, mark it as processed in DynamoDB too
                if post_id:
                    try:
                        from reddit_realtime_scraper import mark_post_as_processed

                        mark_post_as_processed(subreddit_name, post_id, True)
                    except ImportError:
                        pass  # Real-time scraper not available

                logger.info(f"Saved unique image with hash {content_hash[:12]}...")
                return True
            else:
                logger.info(f"No text found in {url}.")
                mark_url_as_processed_in_cache(url)
                return False
        finally:
            # 4. Delete from staging
            try:
                s3_client.delete_object(Bucket=S3_IMAGE_BUCKET, Key=staging_key)
            except Exception as e:
                logger.error(f"Failed to delete staging file {staging_key}: {e}")

    except Exception as e:
        logger.error(f"[ERROR] Error processing {url}: {e}")
        # Still mark as processed to avoid retrying failed URLs in this execution
        mark_url_as_processed_in_cache(url)
        return False


def download_image_sync(
    url: str, timeout: int = 30
) -> Tuple[Optional[bytes], Optional[str]]:
    """Download image from URL synchronously."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "image" not in content_type:
            logger.warning(
                f"[WARNING] Non-image content type for {url}: {content_type}"
            )
            return None, None
        return response.content, content_type
    except Exception as e:
        logger.error(f"[ERROR] Failed to download {url}: {e}")
        return None, None


def get_file_extension(url: str, content_type: str) -> str:
    """Determine appropriate file extension."""
    mime_map = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    if content_type in mime_map:
        return mime_map[content_type]

    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    for ext in ["jpg", "jpeg", "png", "gif", "webp"]:
        if path.endswith(f".{ext}"):
            return ext
    return "jpg"


def process_single_subreddit(
    subreddit_name: str, images_per_subreddit: int = 5, use_stream: bool = False
) -> int:
    """Process and download images from a single subreddit."""
    logger.info(f"[PROCESS] Processing r/{subreddit_name}...")
    reddit = init_reddit_client()
    if not reddit:
        logger.error("[ERROR] Failed to initialize Reddit client")
        return 0

    # Get image URLs and post IDs together
    results = get_image_urls_from_subreddits(
        reddit,
        subreddits=[subreddit_name],
        limit=REDDIT_SCRAPING_CONFIG["REDDIT_FETCH_LIMIT"],
    )

    subreddit_result = results.get(subreddit_name, [])
    if isinstance(subreddit_result, dict):
        # New format with post IDs
        image_urls = subreddit_result.get("urls", [])
        post_ids = subreddit_result.get("post_ids", [])
    else:
        # Fallback to old format (list of URLs)
        image_urls = subreddit_result
        post_ids = []

    if not image_urls:
        logger.warning(f"[WARNING] No images found in r/{subreddit_name}")
        return 0

    logger.info(
        f"[FOUND] Found {len(image_urls)} candidate images to process from r/{subreddit_name}"
    )

    successful_downloads = process_image_batch(
        image_urls, subreddit_name, images_per_subreddit, post_ids
    )

    logger.info(
        f"[COMPLETE] Completed r/{subreddit_name}: {successful_downloads}/{images_per_subreddit} images with text uploaded"
    )
    return successful_downloads


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler for Reddit image population."""
    real_time_mode = event.get("real_time_mode", False)
    use_stream = event.get("use_stream", False)

    if real_time_mode:
        # Use the real-time scraper for EventBridge triggers
        try:
            from reddit_realtime_scraper import process_new_reddit_posts

            return process_new_reddit_posts(event, context)
        except ImportError:
            logger.warning(
                "Real-time scraper not available, falling back to regular mode"
            )

    # Original bulk population logic for initial setup
    logger.info("[START] Starting synchronous Reddit image population...")

    images_per_subreddit = event.get("images_per_subreddit", 30)
    subreddits = event.get("subreddits") or cast(
        List[str], REDDIT_SCRAPING_CONFIG["SUBREDDITS"]
    )
    max_images_per_lambda = event.get("max_images_per_lambda", 30)
    actual_per_subreddit = min(
        images_per_subreddit,
        max_images_per_lambda // len(subreddits) if subreddits else 0,
    )

    logger.info("[CONFIG] Configuration:")
    logger.info(f"   - Target images per subreddit: {actual_per_subreddit}")
    logger.info(f"   - Subreddits: {subreddits}")

    results = {}
    total_images = 0

    try:
        for subreddit_name in subreddits:
            count = process_single_subreddit(
                subreddit_name, actual_per_subreddit, use_stream
            )
            results[subreddit_name] = count
            total_images += count

        logger.info("[SUCCESS] Population completed successfully!")
        logger.info(f"[RESULTS] Results: {results}")
        logger.info(f"[TOTAL] Total images stored: {total_images}")

        performance_monitor.persist_metrics()
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "success": True,
                    "total_images": total_images,
                    "results_per_subreddit": results,
                    "message": f"Successfully populated {total_images} images with text",
                    "performanceMetrics": performance_monitor.get_metrics(),
                }
            ),
        }

    except Exception as e:
        error_msg = f"Error during Reddit image population: {str(e)}"
        logger.error(f"[ERROR] {error_msg}", exc_info=True)
        performance_monitor.persist_metrics()
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"success": False, "error": error_msg, "partial_results": results}
            ),
        }


if __name__ == "__main__":
    test_event = {
        "images_per_subreddit": 5,
        "subreddits": get_subreddits_from_env(),
        "max_images_per_lambda": 10,
    }
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
