"""Reddit scraper utilities for extracting image posts from subreddits.

This module provides functions to initialize a Reddit client, extract image URLs from posts,
and fetch new image posts since a given post ID using the PRAW library.
"""

import re
import logging
import praw
from typing import Optional, Set, List
from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    REDDIT_USERNAME,
    REDDIT_PASSWORD,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

IMAGE_URL_PATTERN = re.compile(
    r"https?://(?:i\.redd\.it|i\.imgur\.com|preview\.redd\.it)/[a-zA-Z0-9]+\.(?:jpg|jpeg|png|gif)"  # direct image links
    r"|https?://imgur\.com/(?:gallery|a)/[a-zA-Z0-9]+"  # imgur galleries
)

IMAGE_DOMAINS = [
    "i.redd.it",
    "i.imgur.com",
    "imgur.com",
    "preview.redd.it",
    # Add other domains if necessary
]


def init_reddit_client() -> "praw.Reddit | None":
    """Initialize and return a PRAW Reddit client using credentials from config.

    Returns:
        praw.Reddit | None: A configured Reddit client instance if successful, otherwise None.
    """
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            check_for_async=False,
        )
        reddit.read_only = True
        return reddit
    except Exception as e:
        logging.error(f"Error initializing Reddit client: {e}")
        return None


def _extract_urls_from_text(text: str) -> Set[str]:
    """Extract image URLs from a block of text using IMAGE_URL_PATTERN.

    Args:
        text (str): The text to search for image URLs.

    Returns:
        Set[str]: A set of matched image URLs.
    """
    return {match.group(0) for match in IMAGE_URL_PATTERN.finditer(text)}


def extract_image_urls_from_submission(submission) -> Set[str]:
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


def get_image_urls_from_translator(
    reddit: Optional["praw.Reddit"], limit: int = 25
) -> List[str]:
    """Fetch image URLs from r/translator/new posts.

    Args:
        reddit (Optional[praw.Reddit]): An initialized Reddit client or None.
        limit (int, optional): The number of posts to fetch. Defaults to 25.

    Returns:
        List[str]: A list of image URLs found in the latest posts.
    """
    if not reddit:
        logging.warning("Reddit client not initialized.")
        return []

    image_urls = set()
    try:
        subreddit = reddit.subreddit("translator")
        for submission in subreddit.new(limit=limit):
            image_urls.update(extract_image_urls_from_submission(submission))
    except Exception as e:
        logging.error(f"Error fetching posts from Reddit: {e}")
    return list(image_urls)


def get_new_image_posts_since(
    reddit: Optional["praw.Reddit"],
    subreddit_name: str = "translator",
    limit: int = 25,
    after_fullname: Optional[str] = None,
) -> List[tuple[str, str]]:
    """Fetch new image posts from a subreddit since a given post ID (fullname).

    Args:
        reddit (Optional[praw.Reddit]): An initialized Reddit client or None.
        subreddit_name (str, optional): The subreddit to fetch from. Defaults to "translator".
        limit (int, optional): The number of posts to fetch. Defaults to 25.
        after_fullname (Optional[str], optional): Only return posts after this fullname. Defaults to None.

    Returns:
        List[tuple[str, str]]: A list of (post_id, image_url) tuples for new image posts.
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
