"""Real-time Reddit scraper that tracks processed posts to avoid duplicates."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Set

import boto3
from botocore.exceptions import ClientError
from reddit_config import get_subreddits_from_env
from reddit_populator_sync import download_and_upload_image
from reddit_scraper_sync import extract_image_urls_from_submission, init_reddit_client

logger = logging.getLogger(__name__)

# DynamoDB table to track processed posts
PROCESSED_POSTS_TABLE = os.environ.get(
    "REDDIT_PROCESSED_POSTS_TABLE", "lenslate-reddit-processed-posts-dev"
)
S3_BUCKET = os.environ.get("S3_BUCKET", "lenslate-image-storage")


def get_dynamodb_client():
    """Get DynamoDB client."""
    return boto3.client("dynamodb")


def get_processed_post_ids(subreddit: str, hours_back: int = 48) -> Set[str]:
    """Get list of post IDs processed in the last N hours."""
    try:
        dynamodb = get_dynamodb_client()

        # Calculate timestamp for N hours ago
        cutoff_time = int(time.time()) - (hours_back * 3600)

        response = dynamodb.query(
            TableName=PROCESSED_POSTS_TABLE,
            KeyConditionExpression="subreddit = :subreddit AND processed_at > :cutoff",
            ExpressionAttributeValues={
                ":subreddit": {"S": subreddit},
                ":cutoff": {"N": str(cutoff_time)},
            },
        )

        return {item["post_id"]["S"] for item in response.get("Items", [])}
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            logger.warning(
                f"DynamoDB table {PROCESSED_POSTS_TABLE} not found. Will process all posts."
            )
            return set()
        logger.error(f"Error querying processed posts: {e}")
        return set()


def mark_post_as_processed(subreddit: str, post_id: str, had_images: bool = False):
    """Mark a post as processed in DynamoDB."""
    try:
        dynamodb = get_dynamodb_client()

        dynamodb.put_item(
            TableName=PROCESSED_POSTS_TABLE,
            Item={
                "subreddit": {"S": subreddit},
                "post_id": {"S": post_id},
                "processed_at": {"N": str(int(time.time()))},
                "had_images": {"BOOL": had_images},
            },
        )
    except Exception as e:
        logger.error(f"Error marking post {post_id} as processed: {e}")


def get_new_posts_with_images(
    subreddit_name: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Get new posts that haven't been processed yet and contain images."""
    reddit = init_reddit_client()
    if not reddit:
        logger.error("Failed to initialize Reddit client")
        return []

    # Get posts we've already processed
    processed_ids = get_processed_post_ids(subreddit_name)
    logger.info(
        f"Found {len(processed_ids)} already processed posts in r/{subreddit_name}"
    )

    subreddit = reddit.subreddit(subreddit_name)
    new_posts = []

    try:
        # Get the newest posts
        for submission in subreddit.new(limit=limit):
            # Skip if we've already processed this post
            if submission.id in processed_ids:
                continue

            # Extract image URLs from this submission
            image_urls = extract_image_urls_from_submission(submission)

            if image_urls:
                new_posts.append(
                    {
                        "post_id": submission.id,
                        "title": submission.title,
                        "created_utc": submission.created_utc,
                        "url": submission.url,
                        "image_urls": list(image_urls),
                        "score": submission.score,
                    }
                )
                logger.info(
                    f"Found new post with {len(image_urls)} images: {submission.title[:50]}..."
                )

            # Mark post as processed regardless of whether it had new images
            mark_post_as_processed(subreddit_name, submission.id, bool(image_urls))

    except Exception as e:
        logger.error(f"Error fetching new posts from r/{subreddit_name}: {e}")

    return new_posts


def process_new_reddit_posts(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for processing new Reddit posts in real-time."""
    logger.info("[START] Processing new Reddit posts...")

    subreddits = event.get("subreddits", get_subreddits_from_env())
    images_per_subreddit = event.get("images_per_subreddit", 10)

    results = {}
    total_new_images = 0

    for subreddit_name in subreddits:
        logger.info(f"[PROCESS] Checking for new posts in r/{subreddit_name}...")

        # Get new posts that haven't been processed
        new_posts = get_new_posts_with_images(subreddit_name, limit=100)

        if not new_posts:
            logger.info(f"[INFO] No new posts with images in r/{subreddit_name}")
            results[subreddit_name] = {"new_posts": 0, "images_processed": 0}
            continue

        logger.info(
            f"[FOUND] {len(new_posts)} new posts with images in r/{subreddit_name}"
        )

        # Process images from new posts
        images_processed = 0
        for post in new_posts[:images_per_subreddit]:  # Limit posts processed
            for i, image_url in enumerate(post["image_urls"]):
                try:
                    success = download_and_upload_image(image_url, subreddit_name, i)
                    if success:
                        images_processed += 1
                        logger.info(
                            f"[SUCCESS] Processed image from post: {post['title'][:30]}..."
                        )
                except Exception as e:
                    logger.error(f"[ERROR] Failed to process image {image_url}: {e}")

        results[subreddit_name] = {
            "new_posts": len(new_posts),
            "images_processed": images_processed,
        }
        total_new_images += images_processed

    logger.info(f"[COMPLETE] Processed {total_new_images} new images total")

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "success": True,
                "total_new_images": total_new_images,
                "results_per_subreddit": results,
                "message": f"Processed {total_new_images} new images from Reddit",
            }
        ),
    }


if __name__ == "__main__":
    test_event = {
        "subreddits": get_subreddits_from_env(),
        "images_per_subreddit": 5,
        "real_time_mode": True,
    }
    result = process_new_reddit_posts(test_event, None)
    print(json.dumps(result, indent=2))
