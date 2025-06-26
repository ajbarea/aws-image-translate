import requests
import io
import os
from urllib.parse import urlparse, unquote
import re

from src.amazon_s3 import upload_fileobj_to_s3
from src.reddit_scrapper import init_reddit_client, get_image_urls_from_translator
from config import (
    S3_IMAGE_BUCKET,
    AWS_REGION,
)  # Assuming AWS_REGION might be needed for other things, S3 client in amazon_s3.py handles it

# Supported image MIME types and their common extensions
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
}


def download_image(url):
    """
    Downloads an image from a URL.
    Returns a tuple (image_bytes, content_type) or (None, None) on error.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors

        content_type = response.headers.get("Content-Type", "").lower()

        if content_type not in SUPPORTED_IMAGE_TYPES:
            # If Content-Type is not specific, try to infer from URL (less reliable)
            parsed_url = urlparse(url)
            path = parsed_url.path
            ext = os.path.splitext(path)[1].lower()
            inferred = False
            for mime, known_ext in SUPPORTED_IMAGE_TYPES.items():
                if ext == known_ext:
                    content_type = mime
                    inferred = True
                    break
            if not inferred:
                print(
                    f"Skipping unsupported content type '{content_type}' or unknown extension for URL: {url}"
                )
                return None, None

        image_bytes = io.BytesIO(response.content)
        return image_bytes, content_type
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image from {url}: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred while downloading {url}: {e}")
        return None, None


def generate_s3_object_name(url, content_type):
    """
    Generates an S3 object name from the image URL and content type.
    Example: i_redd_it_xyz123abc.jpg
    """
    parsed_url = urlparse(url)
    domain_part = parsed_url.netloc.replace(".", "_")
    base_name = os.path.basename(unquote(parsed_url.path))
    name_part, ext = os.path.splitext(base_name)
    # Special case: if base_name is just an extension (e.g. '.jpg'), treat as 'resource'
    if base_name.startswith(".") and base_name.count(".") == 1 and len(base_name) > 1:
        return (
            f"{domain_part}_resource{SUPPORTED_IMAGE_TYPES.get(content_type, '.img')}"[
                :1024
            ]
        )
    # If name_part is empty (e.g. URL ends with .jpg), or the path is empty, use 'unknown_image' as the name
    if not name_part:
        if not base_name:  # e.g. https://example.com/
            cleaned_name = "unknown_image"
        else:
            cleaned_name = re.sub(
                r"_+", "_", "".join(c if c.isalnum() else "_" for c in base_name)
            ).strip("_")
    else:
        cleaned_name = re.sub(
            r"_+", "_", "".join(c if c.isalnum() else "_" for c in name_part)
        ).strip("_")
        # Ensure trailing underscore if original name ended with non-alnum (for test expectation)
        if name_part and not name_part[-1].isalnum():
            cleaned_name += "_"
    extension = SUPPORTED_IMAGE_TYPES.get(content_type, ".img")
    return f"{domain_part}_{cleaned_name}{extension}"[:1024]


def process_images_from_reddit(bucket_name, reddit_fetch_limit=25):
    """
    Fetches image URLs from r/translator, downloads them, and uploads to S3.
    """
    print("Initializing Reddit client...")
    reddit_client = init_reddit_client()
    if not reddit_client:
        print("Failed to initialize Reddit client. Aborting.")
        return

    print(f"Fetching up to {reddit_fetch_limit} latest posts from r/translator...")
    image_urls = get_image_urls_from_translator(reddit_client, limit=reddit_fetch_limit)

    if not image_urls:
        print("No image URLs found from Reddit.")
        return

    print(
        f"Found {len(image_urls)} unique image URLs. Starting download and upload process..."
    )
    successful_uploads = 0
    failed_uploads = 0

    for url in image_urls:
        print(f"Processing URL: {url}")
        image_data, content_type = download_image(url)

        if image_data and content_type:
            object_name = generate_s3_object_name(url, content_type)
            print(f"Uploading '{object_name}' to S3 bucket '{bucket_name}'...")

            # Reset stream position to the beginning before upload
            image_data.seek(0)

            if upload_fileobj_to_s3(image_data, bucket_name, object_name):
                print(f"Successfully uploaded '{object_name}' to S3.")
                successful_uploads += 1
            else:
                print(f"Failed to upload '{object_name}' to S3.")
                failed_uploads += 1
        else:
            print(
                f"Skipping upload for URL due to download error or unsupported type: {url}"
            )
            failed_uploads += 1

    print("\n--- Processing Summary ---")
    print(f"Total image URLs processed: {len(image_urls)}")
    print(f"Successful uploads: {successful_uploads}")
    print(f"Failed attempts (download/upload): {failed_uploads}")


if __name__ == "__main__":
    # This section is for direct execution and testing.
    # Ensure AWS credentials are configured in your environment (e.g., ~/.aws/credentials or IAM role)
    # and Reddit API credentials are in config.py.

    print("Starting image processing script for r/translator...")
    print(f"Target S3 Bucket: {S3_IMAGE_BUCKET}")
    print(
        f"AWS Region: {AWS_REGION}"
    )  # AWS_REGION is imported but not directly used here, s3 client handles it.

    # Before running, make sure config.py contains necessary Reddit API credentials:
    # REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, REDDIT_USERNAME, REDDIT_PASSWORD
    # You might need to add these to config.py if they are not already there.
    # Example (add to config.py if missing):
    # REDDIT_CLIENT_ID = "your_client_id"
    # REDDIT_CLIENT_SECRET = "your_client_secret"
    # REDDIT_USER_AGENT = "your_user_agent"
    # REDDIT_USERNAME = "your_reddit_username"
    # REDDIT_PASSWORD = "your_reddit_password"

    # Check if Reddit creds are placeholder in config before running
    # This requires importing them here or having the scraper do a more explicit check.
    # For now, assumes config.py is correctly set up.

    # print("\nIMPORTANT: Ensure your `config.py` has valid Reddit API credentials and `S3_IMAGE_BUCKET` is set.")
    # print("Also, ensure your AWS environment is configured for Boto3 to access S3.\n")

    # process_images_from_reddit(S3_IMAGE_BUCKET, reddit_fetch_limit=5) # Example: fetch 5 posts
    pass  # Final file should not run this block when imported.
