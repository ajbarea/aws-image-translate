# AWS Reddit Image Translation Pipeline

> **AI-Powered Image Text Extraction and Translation System**
> Automatically detect, extract, and translate text from Reddit images using AWS AI services including Rekognition, Comprehend, and Translate.

## 📚 Comprehensive Documentation Hub

| Document | Purpose | Key Topics |
|----------|---------|------------|
| **[Reddit Pipeline Documentation](src/README.md)** | Complete technical guide | Reddit API integration, AWS service architecture, module APIs, deployment patterns |
| **[Infrastructure Guide](terraform/README.md)** | Infrastructure automation | Terraform deployment, cost optimization, security best practices |
| **[Frontend Deployment Guide](frontend/README.md)** | Web interface setup | Cognito authentication, S3 integration, deployment options |

## 🏗️ System Architecture Overview

**Core Components:**

- **Reddit Integration**: Automated content discovery and image extraction
- **AWS Rekognition**: OCR text detection and extraction from images
- **AWS Comprehend**: Intelligent language detection and confidence scoring
- **AWS Translate**: Multi-language text translation with 75+ language support
- **DynamoDB**: Stateful processing tracking and Reddit post management
- **S3 Storage**: Secure image storage with encryption and lifecycle management
- **Lambda Functions**: Serverless execution environment for scalable processing

## ⚙️ Prerequisites and Requirements

### System Requirements

- **Python 3.8+** (actively tested with Python 3.13.2)
- **AWS Account** with appropriate permissions for AI/ML services
- **Reddit API credentials** for content access

### AWS Credentials Setup

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

### Virtual Environment Setup

#### Option A: Using setup scripts (Recommended)

```bash
# Windows (PowerShell)
.\setup-env.ps1           # Setup with dev dependencies
.\setup-env.ps1 -Prod     # Production dependencies only
.\setup-env.ps1 -Clean    # Clean install

# Linux/Mac
./setup-env.sh            # Setup with dev dependencies
./setup-env.sh --prod     # Production dependencies only
./setup-env.sh --clean    # Clean install
```

#### Option B: Manual setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
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

# Optional: Override default AWS settings
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=reddit_ingest_state
```

**Key Configuration Settings (config.py):**

- **S3_IMAGE_BUCKET**: `"ajbarea-aws-translate"` - S3 bucket for image storage
- **SOURCE_LANGUAGE_CODE**: `"es"` - Default source language (Spanish)
- **TARGET_LANGUAGE_CODE**: `"en"` - Default target language (English)
- **AWS_REGION**: `"us-east-1"` - AWS region for all services

## Infrastructure Management

This project includes Terraform configuration for managing AWS infrastructure. See [terraform/README.md](terraform/README.md) for detailed instructions.

### Infrastructure Deployment

1. **Initialize and deploy infrastructure:**

   **Option A: Using deployment scripts (Recommended)**

   ```bash
   cd terraform

   # Windows (PowerShell)
   .\deploy.ps1 -Action init
   .\deploy.ps1 -Action plan
   .\deploy.ps1 -Action apply

   # Linux/Mac (Bash)
   ./deploy.sh init
   ./deploy.sh plan
   ./deploy.sh apply
   ```

   **Option B: Direct Terraform commands**

   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

2. **Configure the frontend:**

   ```bash
   # Copy the configuration template
   cd frontend/js
   cp config.js.example config.js

   # Get actual values from Terraform
   cd ../../terraform
   terraform output integration_config

   # Edit frontend/js/config.js with the output values
   ```

3. **Clean up resources (Important - Avoid AWS costs):**

   ```bash
   # Using Terraform destroy
   cd terraform
   terraform destroy

   # Alternative: Use deployment scripts
   .\deploy.ps1 -Action destroy    # Windows PowerShell
   ./deploy.sh destroy             # Linux/Mac

   # Alternative: Use cleanup script
   python cleanup.py --dry-run    # Preview what will be deleted
   python cleanup.py              # Actually delete resources
   ```

## 🧪 Testing & Development

### Running Tests

To run the full test suite, including coverage reporting, use the following command:

```bash
pytest --cov=src
```

### Development Tools and Code Quality

This project uses a suite of modern Python development tools to ensure high code quality and consistency. Code formatting, linting, and type-checking are automated using `pre-commit` hooks.

The primary tools include:

- **`pytest`**: For running the comprehensive test suite.
- **`black`**: For opinionated, consistent code formatting.
- **`isort`**: For automatically sorting imports.
- **`flake8`**: For enforcing style and complexity rules.
- **`mypy`**: For static type checking.

#### Running Quality Checks

To run all code quality checks and formatters across the entire project, use the provided script:

```bash
./lint.sh
```

This script executes all configured `pre-commit` hooks, which include `black`, `isort`, `flake8`, and `mypy`.

For convenience, `pre-commit` is also configured to run on every `git commit`. To enable this feature, run `pre-commit install` once after setting up your environment.

## 🚧 Project Architecture Details

### Technology Stack

**Backend:**

- **Python 3.13.2**: Core application language with modern features
- **AWS SDK (boto3)**: Cloud service integration
- **Reddit API (PRAW)**: Automated content discovery
- **BeautifulSoup4**: HTML parsing for media extraction

**Infrastructure:**

- **Terraform**: Infrastructure as Code for reproducible deployments
- **AWS Services**: S3, DynamoDB, Rekognition, Translate, Comprehend, Lambda
- **GitHub Actions**: CI/CD pipeline with automated testing and quality checks

**Frontend:**

- **Vanilla JavaScript**: Lightweight, fast, no frameworks required
- **AWS SDK for JavaScript**: Direct AWS service integration
- **AWS Cognito**: Secure user authentication and authorization

## 📚 Documentation and Resources

### AWS Service Documentation

- [AWS Rekognition Text Detection](https://docs.aws.amazon.com/rekognition/latest/dg/text-detecting-text-procedure.html)
- [AWS S3 Developer Guide](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/list_objects_v2.html)
- [AWS Translate API Reference](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/translate/client/translate_text.html)
- [AWS Lambda Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/python-programming-model.html)

### Development Resources

- [Python PRAW Documentation](https://praw.readthedocs.io/en/stable/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [pytest Documentation](https://docs.pytest.org/en/stable/)
- [AWS SDK for Python (Boto3)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

### Community Resources

- [Build Your Own Translator App Tutorial](https://community.aws/content/2drbcpmaBORz25L3e74AM6EIcFj/build-your-own-translator-app-in-less-30-min)
