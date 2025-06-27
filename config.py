import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.local if it exists
env_path = Path(__file__).parent / ".env.local"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


S3_IMAGE_BUCKET = "ajbarea"
SOURCE_LANGUAGE_CODE = "es"  # Spanish
TARGET_LANGUAGE_CODE = "en"  # English
AWS_REGION = "us-east-1"

# More laguage codes to play with:
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

# Reddit API Credentials taken from environment variables
# Ensure these are set in your environment or .env.local file
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# DynamoDB Configuration
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "reddit_ingest_state")
