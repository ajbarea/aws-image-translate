"""Synchronous Reddit scraper for Lambda environment.

This module provides a completely synchronous Reddit scraper designed for AWS Lambda's concurrency model. Uses requests-based HTTP calls to fetch image URLs from Reddit subreddits.
"""

import io
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, cast

import praw
import requests
from dotenv import load_dotenv
from reddit_config import get_default_subreddit, get_subreddits_from_env

logger = logging.getLogger(__name__)

SupportedMediaFormats = List[str]

REDDIT_SCRAPING_CONFIG = {
    "DEFAULT_SUBREDDIT": get_default_subreddit(),
    "SUBREDDITS": get_subreddits_from_env(),
    "REDDIT_FETCH_LIMIT": 25,
    "SUPPORTED_MEDIA_FORMATS": ["jpg", "jpeg", "png", "gif", "webp"],
}

IMAGE_URL_PATTERN = re.compile(
    r"https?://(?:i\.redd\.it|i\.imgur\.com|preview\.redd\.it)/[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png|gif|webp)"
    r"|https?://imgur\.com/(?:gallery|a)/[a-zA-Z0-9_-]+"
    r"|https?://reddit\.com/gallery/[a-zA-Z0-9_-]+"
)

IMAGE_DOMAINS = [
    "i.redd.it",
    "i.imgur.com",
    "imgur.com",
    "preview.redd.it",
    "reddit.com",
]


def create_reddit_credentials() -> Dict[str, str]:
    """
    Load Reddit API credentials from environment variables.

    Checks environment variables first, then attempts to load from a .env.local
    file if running locally.

    Returns:
        A dictionary containing client_id, client_secret, and user_agent.

    Raises:
        ValueError: If any required credentials are not found.
    """
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT")

    if not all([client_id, client_secret, user_agent]):
        env_path = Path(__file__).parent.parent / ".env.local"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            client_id = os.environ.get("REDDIT_CLIENT_ID")
            client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
            user_agent = os.environ.get("REDDIT_USER_AGENT")

    logger.info(
        f"Reddit credentials check: ID={'OK' if client_id else 'MISSING'}, Secret={'OK' if client_secret else 'MISSING'}, Agent={'OK' if user_agent else 'MISSING'}"
    )

    if not all([client_id, client_secret, user_agent]):
        missing = [
            cred
            for cred, var in [
                ("REDDIT_CLIENT_ID", client_id),
                ("REDDIT_CLIENT_SECRET", client_secret),
                ("REDDIT_USER_AGENT", user_agent),
            ]
            if not var
        ]
        raise ValueError(f"Missing Reddit API credentials: {', '.join(missing)}")

    assert client_id is not None
    assert client_secret is not None
    assert user_agent is not None

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "user_agent": user_agent,
    }


def init_reddit_client() -> Optional[praw.Reddit]:
    """
    Initialize and return a PRAW Reddit client.

    Creates a read-only Reddit client instance using credentials from environment
    variables and tests the connection.

    Returns:
        A configured Reddit client if successful, otherwise None.
    """
    try:
        creds = create_reddit_credentials()
        reddit = praw.Reddit(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            user_agent=creds["user_agent"],
            check_for_async=False,
        )
        reddit.read_only = True
        _ = reddit.subreddit("test").display_name
        logger.info("[SUCCESS] Reddit client initialized successfully")
        return reddit
    except Exception as e:
        logger.error(f"[ERROR] Error initializing Reddit client: {e}")
        return None


def is_supported_media_url(url: str) -> bool:
    """
    Check if a URL points to a supported media format.

    Args:
        url: The URL to validate.

    Returns:
        True if the URL has a supported media format extension, False otherwise.
    """
    url_lower = url.lower()
    supported_formats = cast(
        SupportedMediaFormats, REDDIT_SCRAPING_CONFIG["SUPPORTED_MEDIA_FORMATS"]
    )
    return any(url_lower.endswith(f".{fmt}") for fmt in supported_formats)


def extract_urls_from_text(text: str) -> Set[str]:
    """
    Extract image URLs from text using pattern matching.

    Args:
        text: The text content to search for image URLs.

    Returns:
        A set of image URLs found in the text.
    """
    return {
        match.group(0)
        for match in IMAGE_URL_PATTERN.finditer(text)
        if is_supported_media_url(match.group(0))
    }


def extract_image_urls_from_submission(submission: Any) -> Set[str]:
    """
    Extract all image URLs from a Reddit submission.

    Args:
        submission: A Reddit submission object from PRAW.

    Returns:
        A set of image URLs found in the submission's URL and selftext.
    """
    urls = set()
    if any(domain in submission.url for domain in IMAGE_DOMAINS):
        urls.update(extract_urls_from_text(submission.url))
    if hasattr(submission, "selftext") and submission.selftext:
        urls.update(extract_urls_from_text(submission.selftext))
    return urls


def get_image_urls_from_subreddits(
    reddit: Optional[praw.Reddit],
    subreddits: Optional[List[str]] = None,
    limit: int = 25,
    use_stream: bool = False,
    return_post_ids: bool = False,
) -> Dict[str, Any]:
    """
    Fetch image URLs from multiple subreddits synchronously.

    Args:
        reddit: An initialized Reddit client instance.
        subreddits: A list of subreddit names to fetch from.
        limit: The maximum number of posts to fetch per subreddit.
        use_stream: If True, use streaming to get the absolute newest posts.
        return_post_ids: If True, return post IDs along with URLs.

    Returns:
        A dictionary mapping subreddit names to lists of image URLs, or
        to dicts with 'urls' and 'post_ids' if return_post_ids is True.
    """
    if not reddit:
        logger.warning("Reddit client not initialized.")
        return {}

    if subreddits is None:
        subreddits = cast(List[str], REDDIT_SCRAPING_CONFIG["SUBREDDITS"])

    assert subreddits is not None

    results = {}
    for subreddit_name in subreddits:
        try:
            subreddit = reddit.subreddit(subreddit_name)
            urls = set()
            post_ids = []

            if use_stream:
                logger.info(
                    f"[FETCH] Streaming newest posts from r/{subreddit_name}..."
                )
                # Use stream to get the absolute newest posts
                submissions_checked = 0
                images_found = 0
                max_submissions_to_check = (
                    limit * 3
                )  # Check more submissions to find images
                start_time = time.time()
                timeout_seconds = 30  # Maximum 30 seconds for streaming

                try:
                    for submission in subreddit.stream.submissions(skip_existing=True):
                        submissions_checked += 1

                        # Stop if we've exceeded time limit
                        if time.time() - start_time > timeout_seconds:
                            logger.info(
                                f"[STREAM] Timeout reached after {timeout_seconds}s"
                            )
                            break

                        # Stop if we've checked too many submissions or found enough images
                        if (
                            submissions_checked >= max_submissions_to_check
                            or images_found >= limit
                        ):
                            break

                        submission_urls = extract_image_urls_from_submission(submission)
                        if submission_urls:
                            urls.update(submission_urls)
                            if return_post_ids:
                                post_ids.extend([submission.id] * len(submission_urls))
                            images_found += len(submission_urls)
                            logger.info(
                                f"[STREAM] Found {len(submission_urls)} images in post: {submission.title[:50]}..."
                            )

                except Exception as stream_error:
                    logger.warning(
                        f"[STREAM] Stream error: {stream_error}, falling back to regular mode"
                    )
                    # Fall back to regular mode if streaming fails
                    for submission in subreddit.new(limit=limit):
                        submission_urls = extract_image_urls_from_submission(submission)
                        urls.update(submission_urls)
                        if return_post_ids:
                            post_ids.extend([submission.id] * len(submission_urls))

                elapsed = time.time() - start_time
                logger.info(
                    f"[STREAM] Completed in {elapsed:.2f}s: checked {submissions_checked} submissions, found {len(urls)} images"
                )
            else:
                logger.info(f"[FETCH] Fetching newest posts from r/{subreddit_name}...")
                # Use .new() to get the newest posts (more efficient for Lambda)
                for submission in subreddit.new(limit=limit):
                    submission_urls = extract_image_urls_from_submission(submission)
                    urls.update(submission_urls)
                    if return_post_ids:
                        post_ids.extend([submission.id] * len(submission_urls))

            if return_post_ids:
                results[subreddit_name] = {
                    "urls": list(urls),
                    "post_ids": post_ids[: len(urls)],  # Ensure same length
                }
            else:
                results[subreddit_name] = list(urls)
            logger.info(f"[SUCCESS] Found {len(urls)} image URLs in r/{subreddit_name}")
        except Exception as e:
            logger.error(f"[ERROR] Error fetching posts from r/{subreddit_name}: {e}")
            if return_post_ids:
                results[subreddit_name] = {"urls": [], "post_ids": []}
            else:
                results[subreddit_name] = []
    return results


def download_and_store_image_sync(
    url: str,
    post_id: str,
    subreddit: str,
    s3_bucket: str,
    upload_function: Any,
    retries: int = 3,
) -> bool:
    """
    Download an image synchronously and store it in S3.

    Args:
        url: The image URL to download.
        post_id: The Reddit post ID for S3 key generation.
        subreddit: The subreddit name for S3 organization.
        s3_bucket: The target S3 bucket name.
        upload_function: The function to handle the S3 upload.
        retries: The number of retry attempts on failure.

    Returns:
        True if the download and upload are successful, False otherwise.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Reddit-Image-Collector/1.0)"}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    extension = "jpg"
                elif "png" in content_type:
                    extension = "png"
                elif "gif" in content_type:
                    extension = "gif"
                elif "webp" in content_type:
                    extension = "webp"
                else:
                    extension = "jpg"

                timestamp = int(time.time())
                s3_key = f"reddit/{subreddit}/{timestamp}-{post_id}.{extension}"
                image_data = io.BytesIO(response.content)
                success = upload_function(image_data, s3_bucket, s3_key)

                if success:
                    logger.info(f"[SUCCESS] Successfully stored: {s3_key}")
                    return True
                else:
                    logger.error(f"[ERROR] Failed to upload: {s3_key}")
                    return False
            else:
                logger.warning(f"[WARNING] HTTP {response.status_code} for URL: {url}")
        except Exception as e:
            logger.error(
                f"[ERROR] Error downloading {url} (attempt {attempt + 1}/{retries}): {e}"
            )
            if attempt < retries - 1:
                time.sleep(2**attempt)
    logger.error(f"[ERROR] Failed to download {url} after {retries} attempts")
    return False


if __name__ == "__main__":
    reddit = init_reddit_client()
    if reddit:
        results = get_image_urls_from_subreddits(reddit, get_subreddits_from_env(), 5)
        print(f"Found URLs: {results}")
    else:
        print("Failed to initialize Reddit client")
