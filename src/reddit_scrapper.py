import praw
import re
from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    REDDIT_USERNAME,
    REDDIT_PASSWORD,
)

# Regular expression to find image URLs (direct links to jpg, png, gif)
# It also tries to identify common image hosting patterns that might not end in .jpg etc directly
# but are known to host images (e.g. imgur.com/gallery/xxxx)
IMAGE_URL_PATTERN = re.compile(
    r"https?://(i\.redd\.it/|i\.imgur\.com/|preview\.redd\.it/)([a-zA-Z0-9]+\.(jpg|jpeg|png|gif))"
    r"|https?://(imgur\.com/gallery/|imgur\.com/a/)([a-zA-Z0-9]+)"
)

# List of domains that typically host images directly or are image galleries
IMAGE_DOMAINS = [
    "i.redd.it",
    "i.imgur.com",
    "imgur.com",
    "preview.redd.it",
    # Add other domains if necessary
]


def init_reddit_client():
    """Initializes and returns a PRAW Reddit instance."""
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            check_for_async=False,  # Added to avoid PRAW warning if used in async context later
        )
        reddit.read_only = True  # Set to read-only mode if we are only fetching data
        return reddit
    except Exception as e:
        print(f"Error initializing Reddit client: {e}")
        return None


def get_image_urls_from_translator(reddit, limit=25):
    """
    Fetches posts from r/translator/new and extracts image URLs.

    :param reddit: Initialized PRAW Reddit instance.
    :param limit: Number of posts to fetch from /new.
    :return: A list of unique image URLs.
    """
    if not reddit:
        print("Reddit client not initialized.")
        return []

    image_urls = set()
    try:
        subreddit = reddit.subreddit("translator")
        for submission in subreddit.new(limit=limit):
            # Check submission URL itself
            if any(domain in submission.url for domain in IMAGE_DOMAINS):
                match = IMAGE_URL_PATTERN.search(submission.url)
                if match:
                    # For imgur gallery links, we might need more sophisticated parsing
                    # to get direct image links. For now, we'll take the link as is
                    # if it's a direct image, or the gallery link.
                    # Prioritize direct i.redd.it or i.imgur.com links
                    if match.group(2) and match.group(3):  # direct image link
                        image_urls.add(f"https://{match.group(1)}{match.group(2)}")
                    elif match.group(4) and match.group(5):  # imgur gallery
                        # Heuristic: try to convert basic imgur page to direct image
                        if (
                            "imgur.com/" in submission.url
                            and not submission.url.startswith("https://i.imgur.com")
                        ):
                            # This is a simplification. True conversion often requires API or more complex scraping.
                            # For now, we'll prefer i.imgur.com if available, else take the page.
                            # A common pattern is imgur.com/imageId -> i.imgur.com/imageId.jpg
                            # However, this is not universally reliable.
                            # For galleries (imgur.com/a/ or imgur.com/gallery/) it's more complex.
                            # We will just add the URL and let the downloader try.
                            pass  # Add logic here if a reliable transformation is found
                    image_urls.add(submission.url)

            # Check selftext for image URLs (less common for r/translator but possible)
            # This can be slow if posts are very long, consider if truly needed.
            if submission.selftext_html:  # PRAW decodes html entities
                for match in IMAGE_URL_PATTERN.finditer(submission.selftext):
                    if match.group(2) and match.group(3):  # direct image link
                        image_urls.add(f"https://{match.group(1)}{match.group(2)}")
                    elif match.group(4) and match.group(5):  # imgur gallery
                        image_urls.add(match.group(0))  # Add the full matched URL

    except Exception as e:
        print(f"Error fetching posts from Reddit: {e}")

    return list(image_urls)


if __name__ == "__main__":
    # Example usage (requires config.py to have Reddit credentials)
    # This part will be commented out or removed in the final version
    # as it's for testing the module directly.
    # print("Attempting to fetch images from r/translator...")
    # print("Please ensure your Reddit API credentials are in config.py:")
    # print("REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, REDDIT_USERNAME, REDDIT_PASSWORD")

    # # Dummy credentials for direct execution if config.py is not set up yet for Reddit
    # # IMPORTANT: Replace these with your actual credentials in config.py
    # class DummyConfig:
    #     REDDIT_CLIENT_ID = "YOUR_CLIENT_ID"  # Replace
    #     REDDIT_CLIENT_SECRET = "YOUR_CLIENT_SECRET"  # Replace
    #     REDDIT_USER_AGENT = "YOUR_USER_AGENT (e.g., python:myRedditScraper:v1.0 by u/YourUsername)"  # Replace
    #     REDDIT_USERNAME = "YOUR_REDDIT_USERNAME" # Replace
    #     REDDIT_PASSWORD = "YOUR_REDDIT_PASSWORD" # Replace

    # # Check if actual config values are placeholders before trying to connect
    # if any(val.startswith("YOUR_") for val in [REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, REDDIT_USERNAME, REDDIT_PASSWORD]):
    #     print("\nERROR: Reddit API credentials in config.py appear to be placeholders.")
    #     print("Please update config.py with your actual Reddit script app credentials.")
    #     print("You can create a script app at: https://www.reddit.com/prefs/apps")
    # else:
    #     reddit_client = init_reddit_client()
    #     if reddit_client:
    #         print(f"Successfully initialized Reddit client (Read-only: {reddit_client.read_only}).")
    #         image_urls = get_image_urls_from_translator(reddit_client, limit=10)
    #         if image_urls:
    #             print(f"\nFound {len(image_urls)} potential image URLs:")
    #             for url in image_urls:
    #                 print(url)
    #         else:
    #             print("\nNo image URLs found or error fetching posts.")
    #     else:
    #         print("Failed to initialize Reddit client.")
    pass  # Final file should not run this block when imported.Tool output for `create_file_with_block`:
