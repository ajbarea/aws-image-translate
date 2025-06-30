"""Configuration for AWS Image Translate

This module contains all configurable variables, including AWS services and Reddit API settings.
For sensitive credentials, use .env.local file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.local if it exists
env_path = Path(__file__).parent / ".env.local"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# AWS Configuration
S3_IMAGE_BUCKET = "ajbarea-aws-translate-2025"
SOURCE_LANGUAGE_CODE = "es"  # Spanish
TARGET_LANGUAGE_CODE = "en"  # English
AWS_REGION = "us-east-1"

# Language Configuration
LANGUAGE_CODES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
}

# Enhanced Reddit scraping configuration (merged from subreddit-scraper)
REDDIT_SCRAPING_CONFIG = {
    "POST_SEARCH_AMOUNT": 10,  # Number of media items to download per run
    "SUBREDDIT_LIMIT": 100,  # Maximum posts to check per subreddit
    "SAFETY_LIMIT": 100,  # Maximum posts to check before giving up
    "SUPPORTED_MEDIA_FORMATS": ["jpg", "jpeg", "png", "gif", "webp"],
    "DEFAULT_SUBREDDIT": "translator",  # Default subreddit
    "SUBREDDITS": ["translator", "food"],  # List of subreddits to scrape
    "REDDIT_FETCH_LIMIT": 25,
    "TOKEN_FILE": "token.pickle",  # For OAuth token storage
}

# Media processing settings
MEDIA_PROCESSING_CONFIG = {
    "SUPPORTED_IMAGE_TYPES": {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    },
    "DOWNLOAD_FOLDER": "data/downloads",  # Local storage for downloaded images
    "USER_AGENT_FALLBACK": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "DOWNLOAD_TIMEOUT": 10,  # Seconds
    "MAX_RETRIES": 3,  # Number of download retries
}

# Reddit API Credentials taken from environment variables
# Ensure these are set in your environment or .env.local file
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# DynamoDB Configuration
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "reddit_ingest_state")
