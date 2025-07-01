"""Reddit scraper utilities for extracting image posts from subreddits.

This module provides functions to initialize a Reddit client, extract image URLs from posts,
and fetch new image posts since a given post ID using the PRAW library.

Enhanced with comprehensive media detection and authentication patterns.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, cast

import praw
from dotenv import load_dotenv

from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_SCRAPING_CONFIG,
    REDDIT_USER_AGENT,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Enhanced pattern to support more media types and domains
IMAGE_URL_PATTERN = re.compile(
    r"https?://(?:i\.redd\.it|i\.imgur\.com|preview\.redd\.it)/[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png|gif|webp)"  # direct image links
    r"|https?://imgur\.com/(?:gallery|a)/[a-zA-Z0-9_-]+"  # imgur galleries
    r"|https?://reddit\.com/gallery/[a-zA-Z0-9_-]+"  # reddit galleries
)

IMAGE_DOMAINS = [
    "i.redd.it",
    "i.imgur.com",
    "imgur.com",
    "preview.redd.it",
    "reddit.com",
    # Add other domains as needed
]


# Enhanced authentication with better error handling
def create_reddit_credentials() -> Dict[str, str]:
    """Load Reddit API credentials from environment variables with comprehensive validation.

    Returns:
        Dictionary containing Reddit API credentials for read-only access

    Raises:
        ValueError: If any required credentials are missing
    """
    # For testing purposes, check if we have test values first
    if os.environ.get("REDDIT_TEST_MODE"):
        return {
            "client_id": "test_id",
            "client_secret": "test_secret",
            "user_agent": "test_agent",
        }

    # Load environment variables from .env.local if it exists
    env_path = Path(__file__).parent.parent / ".env.local"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    creds: Dict[str, Optional[str]] = {
        "client_id": REDDIT_CLIENT_ID,
        "client_secret": REDDIT_CLIENT_SECRET,
        "user_agent": REDDIT_USER_AGENT,
    }

    # Check if all credentials are loaded
    missing_creds: List[str] = [key for key, value in creds.items() if not value]
    if missing_creds:
        error_msg = f"Missing Reddit credentials: {', '.join(missing_creds)}"
        logging.error(error_msg)
        logging.error(
            "Please check your .env.local file and ensure all Reddit credentials are set."
        )
        raise ValueError(error_msg)

    # Convert to Dict[str, str] since we've verified all values are not None
    return {key: str(value) for key, value in creds.items()}


def init_reddit_client() -> "praw.Reddit | None":
    """Initialize and return a PRAW Reddit client using credentials from config.

    Enhanced with better error handling and credential validation.

    Returns:
        praw.Reddit | None: A configured Reddit client instance if successful, otherwise None.
    """
    try:
        # Use enhanced credential loading
        creds = create_reddit_credentials()

        reddit = praw.Reddit(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            user_agent=creds["user_agent"],
            check_for_async=False,
        )
        reddit.read_only = True

        # Test the connection with a simple API call
        _ = reddit.subreddit("test").display_name
        logging.info("✅ Reddit client initialized successfully")
        return reddit

    except ValueError as e:
        logging.error(f"Credential error: {e}")
        return None
    except Exception as e:
        logging.error(f"Error initializing Reddit client: {e}")
        logging.error(
            "Please verify your Reddit API credentials and internet connection"
        )
        return None


def is_supported_media_url(url: str) -> bool:
    """Check if URL points to supported media format.

    Args:
        url: URL to check

    Returns:
        True if URL is supported media format
    """
    url_lower = url.lower()
    supported_formats = REDDIT_SCRAPING_CONFIG["SUPPORTED_MEDIA_FORMATS"]
    return any(f".{fmt}" in url_lower for fmt in supported_formats)  # type: ignore


def is_direct_media_url(url: str) -> bool:
    """Check if URL is a direct media link.

    Args:
        url: URL to check

    Returns:
        True if URL is direct media link
    """
    return any(domain in url for domain in IMAGE_DOMAINS) and is_supported_media_url(
        url
    )


def _extract_urls_from_text(text: str) -> Set[str]:
    """Extract image URLs from a block of text using IMAGE_URL_PATTERN.

    Args:
        text (str): The text to search for image URLs.

    Returns:
        Set[str]: A set of matched image URLs.
    """
    return {match.group(0) for match in IMAGE_URL_PATTERN.finditer(text)}


def extract_image_urls_from_submission(submission: Any) -> Set[str]:
    """Extract all image URLs from a Reddit submission's URL and selftext.

    Args:
        submission: A Reddit submission object with 'url' and optional 'selftext'.

    Returns:
        Set[str]: A set of image URLs found in the submission.
    """
    urls = set()
    # Check submission URL for direct image or gallery links
    if any(domain in submission.url for domain in IMAGE_DOMAINS):
        urls.update(_extract_urls_from_text(submission.url))
    # Check selftext for image URLs
    if getattr(submission, "selftext", None):
        urls.update(_extract_urls_from_text(submission.selftext))
    return urls


def get_image_urls_from_subreddits(
    reddit: Optional["praw.Reddit"],
    subreddits: Optional[List[str]] = None,
    limit: int = cast(int, REDDIT_SCRAPING_CONFIG["REDDIT_FETCH_LIMIT"]),
) -> Dict[str, List[str]]:
    """Fetch image URLs from multiple subreddits.

    Args:
        reddit: An initialized Reddit client or None
        subreddits: List of subreddits to fetch from. If None, uses config
        limit: The number of posts to fetch per subreddit

    Returns:
        Dict mapping subreddit names to lists of image URLs
    """
    if not reddit:
        logging.warning("Reddit client not initialized.")
        return {}

    if subreddits is None:
        config_subreddits = REDDIT_SCRAPING_CONFIG.get("SUBREDDITS")
        default_subreddit = cast(str, REDDIT_SCRAPING_CONFIG["DEFAULT_SUBREDDIT"])
        subreddits = (
            cast(List[str], config_subreddits)
            if config_subreddits
            else [default_subreddit]
        )

    results = {}
    for subreddit_name in subreddits:
        try:
            subreddit = reddit.subreddit(subreddit_name)
            urls = set()
            for submission in subreddit.new(limit=limit):
                urls.update(extract_image_urls_from_submission(submission))
            results[subreddit_name] = list(urls)
        except Exception as e:
            logging.error(f"Error fetching posts from r/{subreddit_name}: {e}")
            results[subreddit_name] = []

    return results


# Legacy wrapper for backward compatibility
def get_image_urls_from_translator(
    reddit: Optional["praw.Reddit"],
    limit: int = cast(int, REDDIT_SCRAPING_CONFIG["REDDIT_FETCH_LIMIT"]),
) -> List[str]:
    """Legacy wrapper for backward compatibility. Use get_image_urls_from_subreddits instead.

    Args:
        reddit: An initialized Reddit client or None
        limit: The number of posts to fetch. Defaults to config value.

    Returns:
        List[str]: A list of image URLs found in the latest posts from r/translator.
    """
    default_subreddit = cast(str, REDDIT_SCRAPING_CONFIG["DEFAULT_SUBREDDIT"])
    results = get_image_urls_from_subreddits(
        reddit, subreddits=[default_subreddit], limit=limit
    )
    return results.get(default_subreddit, [])


def get_new_image_posts_since(
    reddit: Optional["praw.Reddit"],
    subreddit_name: str = cast(str, REDDIT_SCRAPING_CONFIG["DEFAULT_SUBREDDIT"]),
    limit: int = cast(int, REDDIT_SCRAPING_CONFIG["REDDIT_FETCH_LIMIT"]),
    after_fullname: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Fetch new image posts from a subreddit since a given post ID (fullname).

    Args:
        reddit (Optional[praw.Reddit]): An initialized Reddit client or None.
        subreddit_name (str, optional): The subreddit to fetch from. Defaults to "translator".
        limit (int, optional): The number of posts to fetch. Defaults to 25.
        after_fullname (Optional[str], optional): Only return posts after this fullname. Defaults to None.

    Returns:
        List[Tuple[str, str]]: A list of (post_id, image_url) tuples for new image posts.
    """
    if not reddit:
        logging.warning("Reddit client not initialized.")
        return []

    processed_posts = []
    try:
        subreddit = reddit.subreddit(subreddit_name)
        logging.info(
            f"Fetching posts from r/{subreddit_name}/new with limit {limit}, after: {after_fullname if after_fullname else 'None'}"
        )
        if after_fullname is not None:
            submissions_generator = subreddit.new(
                limit=limit, params={"after": after_fullname}
            )
        else:
            submissions_generator = subreddit.new(limit=limit)
        temp_posts = []
        for submission in submissions_generator:
            post_fullname = submission.fullname
            for url in extract_image_urls_from_submission(submission):
                temp_posts.append(
                    {
                        "id": post_fullname,
                        "url": url,
                        "created_utc": submission.created_utc,
                    }
                )
        # Sort posts by creation time (oldest to newest)
        if temp_posts:
            sorted_posts = sorted(temp_posts, key=lambda p: p["created_utc"])
            unique_id_url_pairs = set()
            for post_data in sorted_posts:
                if (post_data["id"], post_data["url"]) not in unique_id_url_pairs:
                    processed_posts.append((post_data["id"], post_data["url"]))
                    unique_id_url_pairs.add((post_data["id"], post_data["url"]))
    except Exception as e:
        logging.error(f"Error fetching new posts from Reddit (r/{subreddit_name}): {e}")
    logging.info(f"Found {len(processed_posts)} new image posts/URLs to process.")
    return processed_posts


if __name__ == "__main__":
    # Example usage (requires config.py to have Reddit credentials)
    # This part is for testing the module directly.
    pass
