"""Image processing utilities for Reddit image ingestion and AWS S3 upload.

This module provides functions to download images from Reddit posts, generate S3 object names,
process new images from a subreddit, and handle AWS Lambda events for image ingestion pipelines.
"""

import requests
import io
import os
from urllib.parse import urlparse
import logging

from src.amazon_s3 import upload_fileobj_to_s3
from src.reddit_scraper import init_reddit_client, get_new_image_posts_since
from src.amazon_dynamodb import (
    get_last_processed_post_id,
    update_last_processed_post_id,
)
from config import (
    S3_IMAGE_BUCKET,
    DYNAMODB_TABLE_NAME,
    AWS_REGION,
)

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
}


def download_image(url):
    """Download an image from a URL and return its bytes and content type.

    Args:
        url (str): The URL of the image to download.

    Returns:
        tuple: (image_bytes (io.BytesIO), content_type (str)) if successful, otherwise (None, None).

    Raises:
        None: All exceptions are caught and logged; function returns (None, None) on error.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        content_type = (
            response.headers.get("Content-Type", "").lower().split(";")[0].strip()
        )
        if content_type not in SUPPORTED_IMAGE_TYPES:
            parsed_url = urlparse(url)
            ext = os.path.splitext(parsed_url.path)[1].lower()
            for mime, known_ext in SUPPORTED_IMAGE_TYPES.items():
                if ext == known_ext:
                    content_type = mime
                    logging.info(
                        f"Inferred content type '{content_type}' for URL {url} from extension '{ext}'."
                    )
                    break
            else:
                logging.warning(
                    f"Skipping unsupported content type '{content_type}' or unknown extension for URL: {url}"
                )
                return None, None
        image_bytes = io.BytesIO(response.content)
        return image_bytes, content_type
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading image from {url}: {e}")
        return None, None
    except Exception as e:
        logging.error(f"An unexpected error occurred while downloading {url}: {e}")
        return None, None


def generate_s3_object_name(post_id, image_url, content_type):
    """Generate a unique S3 object name for an image based on post ID, URL, and content type.

    Args:
        post_id (str): The Reddit post ID.
        image_url (str): The URL of the image.
        content_type (str): The MIME type of the image.

    Returns:
        str: A unique S3 object name for the image.

    Raises:
        None: All exceptions are caught and logged; function returns a fallback name on error.
    """
    try:
        parsed_url = urlparse(image_url)
        base_name = os.path.basename(parsed_url.path)
        cleaned_post_id = "".join(c if c.isalnum() else "_" for c in post_id)
        domain_part = parsed_url.netloc.replace(".", "_")
        cleaned_base_name = "".join(
            c if c.isalnum() else "_"
            for c in base_name
            if c.isalnum() or c in [".", "_", "-"]
        )
        extension = SUPPORTED_IMAGE_TYPES.get(content_type)
        if not extension:
            url_ext = os.path.splitext(base_name)[1]
            extension = (
                url_ext
                if url_ext and url_ext in SUPPORTED_IMAGE_TYPES.values()
                else ".img"
            )
            logging.warning(
                f"Content type {content_type} unknown, derived extension {extension} for {image_url}"
            )
        if not cleaned_base_name or cleaned_base_name == extension.replace(".", "_"):
            path_segments = [seg for seg in parsed_url.path.split("/") if seg]
            if path_segments:
                cleaned_base_name = "".join(
                    c if c.isalnum() else "_"
                    for c in path_segments[-1]
                    if c.isalnum() or c in ["_", "-"]
                )
            else:
                fallback_name_part = "".join(
                    c if c.isalnum() else "_"
                    for c in parsed_url.query + parsed_url.fragment
                    if c.isalnum()
                )
                cleaned_base_name = (
                    fallback_name_part
                    if fallback_name_part
                    else hex(hash(image_url))[2:]
                )
        object_name = f"r_translator/{cleaned_post_id}/{domain_part}_{cleaned_base_name}{extension}"
        return object_name[:1000]
    except Exception as e:
        logging.error(
            f"Error generating S3 object name for URL {image_url}, post ID {post_id}: {e}"
        )
        return f"r_translator/{post_id}/unknown_image_{hex(hash(image_url))[2:]}{SUPPORTED_IMAGE_TYPES.get(content_type, '.img')}"


def process_new_images_from_reddit(
    s3_bucket_name,
    dynamodb_table_name,
    subreddit_name="translator",
    reddit_fetch_limit=25,
):
    """Fetch new image posts from a subreddit, download, and upload them to S3, updating DynamoDB.

    Args:
        s3_bucket_name (str): Name of the S3 bucket to upload images to.
        dynamodb_table_name (str): Name of the DynamoDB table for tracking state.
        subreddit_name (str, optional): Subreddit to fetch images from. Defaults to "translator".
        reddit_fetch_limit (int, optional): Number of posts to fetch. Defaults to 25.

    Returns:
        dict: Summary of the processing job, including status, message, processed/failed counts, and newest ID.

    Raises:
        None: All exceptions are caught and logged; function returns a summary dict on error.
    """
    logging.info("Starting image processing job.")
    reddit_client = init_reddit_client()
    if not reddit_client:
        logging.error("Failed to initialize Reddit client. Aborting job.")
        return {"status": "error", "message": "Reddit client initialization failed."}
    subreddit_key = f"r/{subreddit_name}"
    last_processed_id = get_last_processed_post_id(dynamodb_table_name, subreddit_key)
    logging.info(
        f"Last processed post ID for {subreddit_key} from DynamoDB: {last_processed_id}"
    )
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
    logging.info(
        f"Found {len(new_posts_data)} new image posts/URLs. Starting download and upload process..."
    )
    successful_uploads = 0
    failed_attempts = 0
    newest_id_in_batch = None
    for post_id, image_url in new_posts_data:
        logging.info(f"Processing Post ID: {post_id}, Image URL: {image_url}")
        image_data, content_type = download_image(image_url)
        if image_data and content_type:
            object_name = generate_s3_object_name(post_id, image_url, content_type)
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
        else:
            logging.warning(
                f"Skipping upload for Post ID: {post_id}, URL: {image_url} due to download error or unsupported type."
            )
            failed_attempts += 1
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
    elif successful_uploads == 0 and new_posts_data:
        logging.warning(
            f"No images were successfully uploaded in this run, DynamoDB state for {subreddit_key} remains {last_processed_id}."
        )
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


def lambda_handler(event, context):
    """AWS Lambda handler for processing new Reddit images and uploading to S3.

    Args:
        event (dict): Lambda event payload, may include 'subreddit_name' and 'fetch_limit'.
        context (object): Lambda context object.

    Returns:
        dict: Lambda-compatible response with statusCode and body.
    """
    logging.info(f"Lambda handler invoked. Event: {event}, Context: {context}")
    s3_bucket = S3_IMAGE_BUCKET
    ddb_table = DYNAMODB_TABLE_NAME
    subreddit = event.get("subreddit_name", "translator")
    limit = event.get("fetch_limit", 25)
    if not s3_bucket or not ddb_table:
        logging.error("S3_IMAGE_BUCKET or DYNAMODB_TABLE_NAME not configured.")
        return {
            "statusCode": 500,
            "body": "Configuration error: S3 bucket or DynamoDB table name missing.",
        }
    result = process_new_images_from_reddit(
        s3_bucket_name=s3_bucket,
        dynamodb_table_name=ddb_table,
        subreddit_name=subreddit,
        reddit_fetch_limit=limit,
    )
    return {
        "statusCode": 200 if result.get("status") == "success" else 500,
        "body": result,
    }


if __name__ == "__main__":
    logging.info("Starting image processing script directly (not as Lambda)...")
    # Example direct invocation (uncomment to use):
    # result = process_new_images_from_reddit(
    #     s3_bucket_name=S3_IMAGE_BUCKET,
    #     dynamodb_table_name=DYNAMODB_TABLE_NAME,
    #     subreddit_name="translator",
    #     reddit_fetch_limit=5
    # )
    # logging.info(f"Direct script execution result: {result}")
