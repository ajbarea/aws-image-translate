# Reddit AWS Processing Pipeline

> **Comprehensive AWS-Based Reddit Content Analysis System**
> Advanced pipeline for automated Reddit image processing, text extraction, language detection, and multi-language translation using AWS AI/ML services.

## 🌟 Overview

This project provides a scalable solution for collecting Reddit posts containing images, extracting text from those images using AWS Rekognition OCR, and translating the extracted text using AWS Translate. The pipeline maintains stateful processing through DynamoDB and stores processed images in S3 with enterprise-grade security.

### 🏗️ Architecture Components

- **Amazon DynamoDB**: State management and tracking of processed Reddit posts
- **Amazon S3**: Secure storage for downloaded images and processed content
- **Amazon Rekognition**: AI-powered text detection and extraction from images (OCR)
- **Amazon Comprehend**: Natural language processing for intelligent language detection
- **Amazon Translate**: Multi-language text translation supporting 75+ languages
- **AWS Lambda**: Serverless execution environment for scalable pipeline processing
- **Reddit API Integration**: Automated content discovery and image extraction from subreddits

## 🚀 Quick Start

### Prerequisites

- **AWS Account** with appropriate IAM permissions for AI/ML services (Rekognition, Translate, Comprehend, S3, DynamoDB)
- **Python 3.8+** runtime environment (actively tested with Python 3.13.2)
- **AWS CLI** configured with programmatic access credentials
- **Reddit API** credentials for content access (client ID, secret, user agent)
- **Required Python packages** (see Installation section)

### Installation

```bash
# Create and activate virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Linux/Mac
source venv/bin/activate

# Install core dependencies
pip install -r requirements.txt

# Install development dependencies (testing, linting, etc.)
pip install -r requirements-dev.txt
```

**Core Dependencies (`requirements.txt`):**

- `boto3` - AWS SDK for Python (AWS service integration)
- `praw` - Python Reddit API Wrapper (Reddit content access)
- `requests` - HTTP library for web requests
- `python-dotenv` - Environment variable management
- `beautifulsoup4` - HTML parsing utilities

**Development Dependencies (`requirements-dev.txt`):**

- `pytest>=8.0.0` - Testing framework for comprehensive unit tests
- `pytest-cov>=4.0.0` - Coverage plugin for test metrics and reporting
- `moto>=4.2.0` - AWS services mocking for testing without real AWS resources
- `black>=23.0.0` - Code formatting with modern Python support
- `flake8>=6.0.0` - Code linting with customizable rules (configured in setup.cfg)
- `isort>=5.12.0` - Import sorting for clean code organization
- `mypy>=1.0.0` - Type checking for better code quality and error detection
- `pre-commit>=3.0.0` - Git hooks for automated code quality checks

### Environment Configuration

Create a `.env.local` file in the project root with your credentials:

```bash
# Reddit API credentials
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=python:translate-images-bot:1.0 (by u/yourusername)

# Optional: Override default AWS settings
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
DYNAMODB_TABLE_NAME=reddit_ingest_state
```

**Alternative AWS credential methods:**

- AWS CLI: `aws configure`
- IAM roles (recommended for EC2/Lambda)
- AWS credential files in `~/.aws/`

### Basic Usage

```python
from src.image_processor import process_new_images_from_reddit

# Process images from a subreddit
result = process_new_images_from_reddit(
    s3_bucket_name="ajbarea-aws-translate",  # Your S3 bucket
    dynamodb_table_name="reddit_ingest_state",
    subreddit_name="translator",
    reddit_fetch_limit=25
)

print(f"Processed: {result['processed_count']} images")
print(f"Failed: {result['failed_count']} images")
```

**Using the CLI:**

```bash
# Process images with default settings
python main.py

# Process with custom parameters
python main.py --bucket my-bucket --source-lang es --target-lang en
```

## 📚 Module Documentation

### DynamoDB Utilities (`amazon_dynamodb.py`)

**Purpose**: Manages state persistence for tracking processing progress across subreddits.

#### Core Functions

**`get_dynamodb_resource()`**

- Initializes DynamoDB resource for the configured AWS region
- **Returns**: `boto3.resource` object for DynamoDB operations
- **Use Case**: Foundation for all DynamoDB operations

**`get_last_processed_post_id(table_name, subreddit_key)`**

- Retrieves the most recently processed post ID for a subreddit
- **Parameters:**
  - `table_name` (str): DynamoDB table name for state tracking
  - `subreddit_key` (str): Subreddit identifier (e.g., "r/translator")
- **Returns**: Post ID string or `None` if not found
- **Use Case**: Resume processing from last checkpoint

**`update_last_processed_post_id(table_name, subreddit_key, post_id)`**

- Updates the last processed post ID for tracking progress
- **Parameters:**
  - `table_name` (str): DynamoDB table name
  - `subreddit_key` (str): Subreddit identifier
  - `post_id` (str): Reddit post ID to record
- **Returns**: `True` on success, `False` on error
- **Use Case**: Checkpoint progress to avoid reprocessing

#### Usage Example

```python
from amazon_dynamodb import get_last_processed_post_id, update_last_processed_post_id

# Retrieve processing state
last_id = get_last_processed_post_id("reddit_ingest_state", "r/translator")

# Update processing state
success = update_last_processed_post_id("reddit_ingest_state", "r/translator", "t3_abc123")
```

#### Table Setup

For testing purposes, create a DynamoDB table manually:

```python
import boto3

client = boto3.client("dynamodb", region_name="us-east-1")
client.create_table(
    TableName="reddit_ingest_state_test",
    KeySchema=[{'AttributeName': 'subreddit_key', 'KeyType': 'HASH'}],
    AttributeDefinitions=[{'AttributeName': 'subreddit_key', 'AttributeType': 'S'}],
    BillingMode='PAY_PER_REQUEST'  # No need for ProvisionedThroughput
)

# Wait for table creation
waiter = client.get_waiter('table_exists')
waiter.wait(TableName="reddit_ingest_state_test")
```

### S3 Utilities (`amazon_s3.py`)

**Purpose**: Handles secure file storage and retrieval operations in Amazon S3.

#### S3 Core Functions

**`list_images_in_bucket(bucket)`**

- Lists all image files (PNG, JPG, JPEG) in the specified bucket
- **Parameters**: `bucket` (str): S3 bucket name
- **Returns**: List of image file names
- **Use Case**: Inventory existing processed images

**`upload_file_to_s3(file_path, bucket_name, object_name=None)`**

- Uploads a local file to S3 with automatic error handling
- **Parameters:**
  - `file_path` (str): Local file path
  - `bucket_name` (str): Target S3 bucket
  - `object_name` (str, optional): S3 object key (defaults to filename)
- **Returns**: `True` on success, `False` on error
- **Use Case**: Store Reddit images for processing

**`upload_fileobj_to_s3(fileobj, bucket_name, object_name)`**

- Uploads a file-like object directly to S3 (memory efficient)
- **Parameters:**
  - `fileobj`: File-like object (BytesIO, file handle, etc.)
  - `bucket_name` (str): Target S3 bucket
  - `object_name` (str): S3 object key
- **Returns**: `True` on success, `False` on error
- **Use Case**: Stream images directly from Reddit URLs

#### S3 Usage Example

```python
from amazon_s3 import upload_file_to_s3, list_images_in_bucket

# Upload a local image
success = upload_file_to_s3("./image.jpg", "my-bucket", "images/image.jpg")

# List existing images
images = list_images_in_bucket("my-bucket")
print(f"Found {len(images)} images")
```

### Rekognition Utilities (`amazon_rekognition.py`)

**Purpose**: Provides AI-powered text detection and extraction from images using AWS Rekognition OCR.

#### Rekognition Core Functions

**`detect_text_from_s3(photo, bucket)`**

- Detects and extracts text from an image stored in S3 using computer vision
- **Parameters:**
  - `photo` (str): S3 object key for the image
  - `bucket` (str): S3 bucket name
- **Returns**: String containing all detected text lines (space-separated)
- **Raises:**
  - `botocore.exceptions.BotoCoreError`: Low-level AWS SDK errors
  - `botocore.exceptions.ClientError`: Rekognition API errors
- **Use Case**: Extract text from memes, screenshots, documents

#### Rekognition Usage Example

```python
from amazon_rekognition import detect_text_from_s3

# Extract text from an image
text = detect_text_from_s3("images/sample.jpg", "my-bucket")
print(f"Extracted text: {text}")
```

### Translate Utilities (`amazon_translate.py`)

**Purpose**: Handles intelligent text translation between different languages using AWS Translate.

#### Translate Core Functions

**`translate_text(text, source_lang, target_lang)`**

- Translates text between specified languages with high accuracy
- **Parameters:**
  - `text` (str): Text to translate
  - `source_lang` (str): Source language code (e.g., 'en', 'es', 'fr')
  - `target_lang` (str): Target language code
- **Returns**: Translated text string
- **Raises:**
  - `botocore.exceptions.BotoCoreError`: Low-level AWS SDK errors
  - `botocore.exceptions.ClientError`: Translate API errors
- **Use Case**: Translate extracted text to desired language

#### Translate Usage Example

```python
from amazon_translate import translate_text

# Translate English to Spanish
spanish_text = translate_text("Hello world", "en", "es")
print(f"Translation: {spanish_text}")  # Output: "Hola mundo"
```

### Image Processor (`image_processor.py`)

**Purpose**: Main pipeline orchestration module handling end-to-end image processing workflow.

#### Image Processor Core Functions

**`download_image(url)`**

- Downloads an image from a URL into memory with error handling
- **Parameters**: `url` (str): Image URL to download
- **Returns**: Tuple of `(BytesIO object, content_type)` or `(None, None)` on error
- **Supported formats**: JPEG, PNG, GIF
- **Use Case**: Fetch images from Reddit posts

**`generate_s3_object_name(post_id, image_url, content_type)`**

- Creates a unique S3 object key for storing images
- **Parameters:**
  - `post_id` (str): Reddit post identifier
  - `image_url` (str): Original image URL
  - `content_type` (str): MIME type of the image
- **Returns**: Generated S3 object key string
- **Use Case**: Organize images with meaningful names

**`process_new_images_from_reddit(s3_bucket_name, dynamodb_table_name, subreddit_name="translator", reddit_fetch_limit=25)`**

- Main processing function that orchestrates the entire pipeline
- **Parameters:**
  - `s3_bucket_name` (str): Target S3 bucket for images
  - `dynamodb_table_name` (str): DynamoDB table for state tracking
  - `subreddit_name` (str, optional): Target subreddit name (default: "translator")
  - `reddit_fetch_limit` (int, optional): Maximum posts to process (default: 25)
- **Returns**: Dictionary with processing results:

  ```python
  {
      "status": "success|error",
      "message": "Status description",
      "processed_count": int,
      "failed_count": int,
      "newest_processed_id": str
  }
  ```

**`lambda_handler(event, context)`**

- AWS Lambda entry point for serverless execution
- **Parameters:**
  - `event` (dict): Lambda event payload
  - `context`: Lambda context object
- **Returns**: HTTP response dictionary with status code and body
- **Use Case**: Scheduled processing in Lambda

#### Pipeline Workflow

1. **Fetch Reddit Posts**: Retrieve new posts from specified subreddit using Reddit API
2. **State Check**: Compare against last processed post ID from DynamoDB
3. **Image Download**: Download images from Reddit posts to memory
4. **S3 Upload**: Store images in S3 with generated object keys
5. **Text Extraction**: Use Rekognition OCR to detect text in images
6. **Language Detection**: Use Comprehend to identify source language
7. **Translation**: Translate extracted text using AWS Translate
8. **State Update**: Update DynamoDB with latest processed post ID

#### Image Processor Usage Example

```python
from image_processor import process_new_images_from_reddit

# Process images from r/translator subreddit
result = process_new_images_from_reddit(
    s3_bucket_name="reddit-translation-images",
    dynamodb_table_name="reddit_processing_state",
    subreddit_name="translator",
    reddit_fetch_limit=25
)

if result["status"] == "success":
    print(f"Successfully processed {result['processed_count']} images")
    print(f"Failed to process {result['failed_count']} images")
else:
    print(f"Processing failed: {result['message']}")
```

## ☁️ AWS Lambda Deployment

### Lambda Configuration

- **Runtime**: Python 3.9+ (recommended for compatibility)
- **Memory**: 512 MB (adjust based on image sizes)
- **Timeout**: 5 minutes (for processing multiple images)
- **Environment Variables**:
  - `S3_BUCKET_NAME`: Target S3 bucket
  - `DYNAMODB_TABLE_NAME`: State tracking table
  - `SUBREDDIT_NAME`: Target subreddit
  - `REDDIT_FETCH_LIMIT`: Post processing limit

### IAM Permissions

Required AWS permissions for the Lambda execution role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/reddit_*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "rekognition:DetectText"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "translate:TranslateText"
            ],
            "Resource": "*"
        }
    ]
}
```

### Lambda Event Trigger

Example CloudWatch Events rule for scheduled execution:

```json
{
    "source": ["aws.events"],
    "detail-type": ["Scheduled Event"],
    "detail": {}
}
```

## 🛠️ Error Handling and Monitoring

### Error Handling Strategy

- All functions implement comprehensive exception handling
- Errors are logged using Python's logging module
- Functions return appropriate error indicators (`None`, `False`, error status)
- Processing continues when individual items fail (fail-safe approach)

### Monitoring Recommendations

- **CloudWatch Logs**: Monitor Lambda function logs for errors
- **CloudWatch Metrics**: Track processing success/failure rates
- **DynamoDB Metrics**: Monitor read/write capacity utilization
- **S3 Metrics**: Track storage usage and request patterns

## 🔧 Common Issues and Solutions

### Reddit API Rate Limiting

- Implement exponential backoff for Reddit requests
- Consider using multiple Reddit API credentials

### Large Image Processing

- Increase Lambda memory allocation for large images
- Implement image resizing before S3 upload

### DynamoDB Throttling

- Monitor and adjust read/write capacity units
- Implement retry logic with exponential backoff

## ✅ Best Practices

### Performance Optimization

- Use concurrent processing for multiple images where possible
- Implement caching for frequently accessed DynamoDB items
- Optimize S3 object naming for better performance patterns

### Cost Management

- Use S3 Intelligent Tiering for long-term storage cost optimization
- Monitor AWS usage through Cost Explorer
- Set up billing alerts for unexpected usage spikes

### Security Considerations

- Use IAM roles with minimal required permissions
- Enable S3 bucket encryption at rest
- Consider VPC endpoints for internal AWS service communication
- Regularly rotate AWS access keys if using programmatic access

## 🤝 Contributing

When contributing to this project:

1. Follow PEP 8 style guidelines for Python code
2. Add comprehensive docstrings to all functions
3. Include unit tests for new functionality
4. Update documentation for any API changes
5. Test with actual AWS resources before submitting PRs

## 📄 License

This project is provided as-is for educational and development purposes. Ensure compliance with Reddit's API terms of service and AWS acceptable use policies.

## 🔧 Current Project Configuration

This project is pre-configured with the following default settings (from `config.py`):

### AWS Configuration

- **S3 Bucket**: `ajbarea-aws-translate`
- **AWS Region**: `us-east-1`
- **DynamoDB Table**: `reddit_ingest_state`

### Language Settings

- **Source Language**: Spanish (`es`)
- **Target Language**: English (`en`)
- **Supported Languages**: English, Spanish, French, German, Italian, Portuguese, Chinese, Japanese, Korean

### Reddit Configuration

- **Default Subreddit**: `translator`
- **Additional Subreddits**: `food`
- **Post Fetch Limit**: 25 posts per run
- **Supported Formats**: JPG, JPEG, PNG, GIF, WebP

### Media Processing

- **Download Timeout**: 10 seconds
- **Max Retries**: 3 attempts

**To customize these settings:**

1. Edit `config.py` for application defaults
2. Use environment variables in `.env.local` to override
3. Pass parameters to CLI or functions directly

## 🧪 Testing and Quality Assurance

### Test Suite Overview

The project includes 64 comprehensive unit tests covering all major components with full AWS service mocking:

- **Amazon DynamoDB** (6 tests): State management, table operations, error handling
- **Amazon Rekognition** (2 tests): Text detection functionality, API response handling
- **Amazon S3** (6 tests): File upload/download, listing operations, error conditions
- **Amazon Translate** (2 tests): Multi-language translation services, API integration
- **Enhanced Media Utils** (10 tests): Media processing utilities, error handling
- **Image Processor** (7 tests): End-to-end Reddit image processing pipeline
- **Main CLI** (6 tests): Command-line interface functionality and argument parsing
- **Reddit Scraper** (13 tests): Reddit API integration, subreddit processing
- **Additional Integration Tests** (12 tests): Cross-module functionality testing

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src --cov-report=html

# Run specific test modules
pytest tests/test_amazon_rekognition.py
pytest tests/test_reddit_scraper.py

# Run tests with verbose output
pytest -v
```

### Test Configuration

Tests are configured via `pyproject.toml`:

```toml
[tool.pytest.ini_options]
filterwarnings = [
    "ignore::DeprecationWarning:botocore.*",
    "ignore::DeprecationWarning:boto3.*",
]
addopts = "-v --tb=short"
testpaths = ["tests"]
```

### Mocking Strategy

- **AWS Services**: Uses `moto` library to mock AWS API calls
- **Reddit API**: Uses custom mocks to simulate Reddit responses
- **HTTP Requests**: Uses `responses` library for HTTP request mocking

### Quality Tools

- **Code Formatting**: `black` for consistent code style
- **Linting**: `flake8` with custom configuration in `setup.cfg`
- **Import Sorting**: `isort` for organized imports
- **Type Checking**: `mypy` for static type analysis
- **Pre-commit Hooks**: Automated quality checks before commits
