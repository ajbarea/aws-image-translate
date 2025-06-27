# Reddit AWS Processing Pipeline

A comprehensive AWS-based pipeline for ingesting, processing, and analyzing Reddit content with image text extraction and translation capabilities.

## Overview

This project provides a scalable solution for collecting Reddit posts containing images, extracting text from those images using AWS Rekognition, and translating the extracted text using AWS Translate. The pipeline maintains state tracking through DynamoDB and stores processed images in S3.

### Architecture Components

- **Amazon DynamoDB**: State management and tracking of processed posts
- **Amazon S3**: Storage for downloaded images and processed content
- **Amazon Rekognition**: Text detection and extraction from images
- **Amazon Translate**: Multi-language text translation
- **AWS Lambda**: Serverless execution environment for pipeline processing

## Quick Start

### Prerequisites

- AWS Account with appropriate permissions
- Python 3.8+
- AWS CLI configured with credentials
- Required Python packages (see Installation)

### Installation

```bash
pip install boto3 requests python-dotenv
```

### Environment Configuration

Create a `.env` file or configure environment variables:

```bash
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Basic Usage

```python
from image_processor import process_new_images_from_reddit

# Process images from a subreddit
result = process_new_images_from_reddit(
    s3_bucket_name="my-reddit-images",
    dynamodb_table_name="reddit_ingest_state",
    subreddit_name="translator",
    reddit_fetch_limit=50
)

print(f"Processed: {result['processed_count']} images")
```

## Module Documentation

### DynamoDB Utilities (`amazon_dynamodb.py`)

Manages state persistence for tracking processing progress across subreddits.

#### Core Functions

**`get_dynamodb_resource()`**

- Initializes DynamoDB resource for the configured AWS region
- Returns: `boto3.resource` object for DynamoDB operations

**`get_last_processed_post_id(table_name, subreddit_key)`**

- Retrieves the most recently processed post ID for a subreddit
- **Parameters:**
  - `table_name` (str): DynamoDB table name
  - `subreddit_key` (str): Subreddit identifier (e.g., "r/translator")
- **Returns:** Post ID string or `None` if not found

**`update_last_processed_post_id(table_name, subreddit_key, post_id)`**

- Updates the last processed post ID for tracking progress
- **Parameters:**
  - `table_name` (str): DynamoDB table name
  - `subreddit_key` (str): Subreddit identifier
  - `post_id` (str): Reddit post ID to record
- **Returns:** `True` on success, `False` on error

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
    ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
)

# Wait for table creation
waiter = client.get_waiter('table_exists')
waiter.wait(TableName="reddit_ingest_state_test")
```

### S3 Utilities (`amazon_s3.py`)

Handles file storage and retrieval operations in Amazon S3.

#### S3 Core Functions

**`list_images_in_bucket(bucket)`**

- Lists all image files (PNG, JPG, JPEG) in the specified bucket
- **Parameters:** `bucket` (str): S3 bucket name
- **Returns:** List of image file names

**`upload_file_to_s3(file_path, bucket_name, object_name=None)`**

- Uploads a local file to S3
- **Parameters:**
  - `file_path` (str): Local file path
  - `bucket_name` (str): Target S3 bucket
  - `object_name` (str, optional): S3 object key (defaults to filename)
- **Returns:** `True` on success, `False` on error

**`upload_fileobj_to_s3(fileobj, bucket_name, object_name)`**

- Uploads a file-like object directly to S3
- **Parameters:**
  - `fileobj`: File-like object (BytesIO, file handle, etc.)
  - `bucket_name` (str): Target S3 bucket
  - `object_name` (str): S3 object key
- **Returns:** `True` on success, `False` on error

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

Provides text detection and extraction from images using AWS Rekognition.

#### Rekognition Core Functions

**`detect_text_from_s3(photo, bucket)`**

- Detects and extracts text from an image stored in S3
- **Parameters:**
  - `photo` (str): S3 object key for the image
  - `bucket` (str): S3 bucket name
- **Returns:** String containing all detected text lines (space-separated)
- **Raises:**
  - `botocore.exceptions.BotoCoreError`: Low-level AWS SDK errors
  - `botocore.exceptions.ClientError`: Rekognition API errors

#### Rekognition Usage Example

```python
from amazon_rekognition import detect_text_from_s3

# Extract text from an image
text = detect_text_from_s3("images/sample.jpg", "my-bucket")
print(f"Extracted text: {text}")
```

### Translate Utilities (`amazon_translate.py`)

Handles text translation between different languages using AWS Translate.

#### Translate Core Functions

**`translate_text(text, source_lang, target_lang)`**

- Translates text between specified languages
- **Parameters:**
  - `text` (str): Text to translate
  - `source_lang` (str): Source language code (e.g., 'en', 'es', 'fr')
  - `target_lang` (str): Target language code
- **Returns:** Translated text string
- **Raises:**
  - `botocore.exceptions.BotoCoreError`: Low-level AWS SDK errors
  - `botocore.exceptions.ClientError`: Translate API errors

#### Translate Usage Example

```python
from amazon_translate import translate_text

# Translate English to Spanish
spanish_text = translate_text("Hello world", "en", "es")
print(f"Translation: {spanish_text}")  # Output: "Hola mundo"
```

### Image Processor (`image_processor.py`)

Main pipeline orchestration module handling end-to-end image processing workflow.

#### Image Processor Core Functions

**`download_image(url)`**

- Downloads an image from a URL into memory
- **Parameters:** `url` (str): Image URL to download
- **Returns:** Tuple of `(BytesIO object, content_type)` or `(None, None)` on error
- **Supported formats:** JPEG, PNG, GIF

**`generate_s3_object_name(post_id, image_url, content_type)`**

- Creates a unique S3 object key for storing images
- **Parameters:**
  - `post_id` (str): Reddit post identifier
  - `image_url` (str): Original image URL
  - `content_type` (str): MIME type of the image
- **Returns:** Generated S3 object key string

**`process_new_images_from_reddit(s3_bucket_name, dynamodb_table_name, subreddit_name, reddit_fetch_limit)`**

- Main processing function that orchestrates the entire pipeline
- **Parameters:**
  - `s3_bucket_name` (str): Target S3 bucket for images
  - `dynamodb_table_name` (str): DynamoDB table for state tracking
  - `subreddit_name` (str): Target subreddit name
  - `reddit_fetch_limit` (int): Maximum posts to process
- **Returns:** Dictionary with processing results:

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
- **Returns:** HTTP response dictionary with status code and body

#### Pipeline Workflow

1. **Fetch Reddit Posts**: Retrieve new posts from specified subreddit
2. **State Check**: Compare against last processed post ID from DynamoDB
3. **Image Download**: Download images from Reddit posts
4. **S3 Upload**: Store images in S3 with generated object keys
5. **Text Extraction**: Use Rekognition to detect text in images
6. **Translation**: Translate extracted text using AWS Translate
7. **State Update**: Update DynamoDB with latest processed post ID

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

## AWS Lambda Deployment

### Lambda Configuration

- **Runtime**: Python 3.9+
- **Memory**: 512 MB (adjust based on image sizes)
- **Timeout**: 5 minutes
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

## Error Handling and Monitoring

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

## Common Issues and Solutions

### Reddit API Rate Limiting

- Implement exponential backoff for Reddit requests
- Consider using multiple Reddit API credentials

### Large Image Processing

- Increase Lambda memory allocation for large images
- Implement image resizing before S3 upload

### DynamoDB Throttling

- Monitor and adjust read/write capacity units
- Implement retry logic with exponential backoff

## Best Practices

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

## Contributing

When contributing to this project:

1. Follow PEP 8 style guidelines for Python code
2. Add comprehensive docstrings to all functions
3. Include unit tests for new functionality
4. Update documentation for any API changes
5. Test with actual AWS resources before submitting PRs

## License

This project is provided as-is for educational and development purposes. Ensure compliance with Reddit's API terms of service and AWS acceptable use policies.
