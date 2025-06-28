# AWS Reddit Image Translation Pipeline

> **AI-Powered Image Text Extraction and Translation System**  
> Automatically detect, extract, and translate text from Reddit images using AWS AI services including Rekognition, Comprehend, and Translate.

## 📚 Comprehensive Documentation Hub

| Document | Purpose | Key Topics |
|----------|---------|------------|
| **[Reddit Pipeline Documentation](src/reddit-aws-pipeline-docs.md)** | Complete technical guide | Reddit API integration, AWS service architecture, module APIs, deployment patterns |
| **[AWS Translation Demo](aws-demos/README.md)** | Hands-on examples | Live pipeline demonstrations, component testing, troubleshooting guides |
| **[Infrastructure Guide](terraform/README.md)** | Infrastructure automation | Terraform deployment, cost optimization, security best practices |

## 🏗️ System Architecture Overview

**Core Components:**

- **Reddit Integration**: Automated content discovery and image extraction
- **AWS Rekognition**: OCR text detection and extraction from images
- **AWS Comprehend**: Intelligent language detection and confidence scoring
- **AWS Translate**: Multi-language text translation with 75+ language support
- **DynamoDB**: Stateful processing tracking and Reddit post management
- **S3 Storage**: Secure image storage with encryption and lifecycle management
- **Lambda Functions**: Serverless execution environment for scalable processing

## ⚙️ AWS Credentials Setup

### Essential Security Configuration

Before running any AWS operations, configure your AWS credentials securely. Create the following credential files with your AWS access keys and region:

**`~/.aws/credentials`:**

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

**`~/.aws/config`:**

```ini
[default]
region=us-east-1
```

**Alternative Methods:**

- AWS CLI: `aws configure`
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- IAM roles (recommended for EC2/Lambda)

## 🚀 Quick Start Guide

### Setup

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Running the CLI

The main entry point is `main.py`, which provides a command-line interface to detect and translate text from images in an S3 bucket.

#### Usage

```bash
python main.py [--bucket BUCKET] [--source-lang SRC_LANG] [--target-lang TGT_LANG]
```

**Parameters:**

- `--bucket`: S3 bucket name (default: value from `config.py`)
- `--source-lang`: Source language code (default: value from `config.py`)
- `--target-lang`: Target language code (default: value from `config.py`)

**Example:**

```bash
python main.py --bucket mybucket --source-lang es --target-lang en
```

If no arguments are provided, the defaults from `config.py` will be used.

### Environment Variables

Before running the application, create a `.env.local` file in the project root with your Reddit API credentials:

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=python:translate-images-bot:1.0 (by u/yourusername)
```

Replace the values with your own Reddit API credentials. This file is required for the application to access Reddit APIs.

## Infrastructure Management

This project includes Terraform configuration for managing AWS infrastructure. See [terraform/README.md](terraform/README.md) for detailed instructions.

### Quick Infrastructure Setup

1. **Initialize and deploy infrastructure:**

   ```bash
   # Windows (PowerShell)
   .\terraform\deploy.ps1 -Action init
   .\terraform\deploy.ps1 -Action apply
   
   # Linux/Mac (Bash)
   ./terraform/deploy.sh init
   ./terraform/deploy.sh apply
   ```

2. **Clean up resources to avoid costs:**

   ```bash
   # Using Terraform
   .\terraform\deploy.ps1 -Action destroy
   
   # Using cleanup script
   python cleanup.py --dry-run    # Preview what will be deleted
   python cleanup.py              # Actually delete resources
   ```

## Testing & Coverage

Run all tests with coverage:

```bash
pytest --cov=.
```

## References

- <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rekognition.html#>
- <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/list_objects_v2.html>
- <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/translate/client/translate_text.html>
- <https://docs.aws.amazon.com/rekognition/latest/dg/text-detecting-text-procedure.html>
- <https://community.aws/content/2drbcpmaBORz25L3e74AM6EIcFj/build-your-own-translator-app-in-less-30-min>
