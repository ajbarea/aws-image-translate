# 🖼️➡️🌐 AWS Reddit Image Translation Pipeline

> **AI-Powered Image Text Extraction and Translation System**
> Automatically detect, extract, and translate text from your photos or Reddit images using AWS AI services including Rekognition, Comprehend, and Translate.

## 📚 Documentation Hub

| Document                                               | Purpose                   | Key Topics                                                                         |
| ------------------------------------------------------ | ------------------------- | ---------------------------------------------------------------------------------- |
| **📄 [Reddit Pipeline Documentation](src/README.md)**  | Complete technical guide  | Reddit API integration, AWS service architecture, module APIs, deployment patterns |
| **🏗️ [Infrastructure Guide](terraform/README.md)**    | Infrastructure automation | Terraform deployment, cost optimization, security best practices                   |
| **🌐 [Frontend Deployment Guide](frontend/README.md)** | Web interface setup       | Cognito authentication, S3 integration, deployment options                         |
| **🔄 [Storage Adapter Guide](STORAGE_ADAPTER.md)**     | Storage backend switching | AWS S3 ↔ Google Cloud Storage, free tier optimization                            |

## 🏗️ System Architecture Overview

**Core Components:**

* 🌐 **Reddit Integration**: Automated content discovery and image extraction
* 📸 **AWS Rekognition**: OCR text detection and extraction from images
* 🧠 **AWS Comprehend**: Intelligent language detection and confidence scoring
* 🌍 **AWS Translate**: Multi-language text translation with 75+ language support
* 📊 **DynamoDB**: Stateful processing tracking and Reddit post management
* 🗄️ **S3 Storage**: Secure image storage with encryption and lifecycle management
* 🔧 **Lambda Functions**: Serverless execution environment for scalable processing

## ⚙️ Prerequisites and Requirements

### 🖥️ System Requirements

* 🐍 **Python 3.8+** (actively tested with Python 3.13.2)
* ☁️ **AWS Account** with appropriate permissions for AI/ML services
* 🔑 **Reddit API credentials** for content access

### 🔐 AWS Credentials Setup

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

* ⚙️ AWS CLI: `aws configure`
* 🌱 Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
* 🛡️ IAM roles

## 🚀 Quick Start Guide

### 🛠️ Virtual Environment Setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
python -m pip install --upgrade pip
pip install .[dev]
```

### 🌐 Local Development Setup (Recommended)

Launch frontend with Live Server and use the local FastAPI backend:

```bash
# 1. Create Cognito resources for authentication
python setup-cognito.py

# 2. Add the output to .env.local file

# 3. Start the backend
fastapi dev backend/app.py

# 4. Open frontend/index.html with Live Server
```

### 🏃 Running the CLI

The main entry point is `main.py`, which provides a command-line interface to detect and translate text from images in an S3 bucket.

#### 📋 Usage

```bash
python main.py [--bucket BUCKET] [--target-lang TGT_LANG]
```

**Parameters:**

* 🗃️ `--bucket`: S3 bucket name (default: value from `config.py`)
* 🌐 `--target-lang`: Target language code (default: value from `config.py`)

**Example:**

```bash
python main.py --bucket mybucket --target-lang en
```

If no arguments are provided, the defaults from `config.py` will be used. The source language is automatically detected using AWS Comprehend.

### 🌱 Environment Variables

Before running the application, create a `.env.local` file in the project root with your Reddit API credentials:

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=python:translate-images-bot:1.0 (by u/yourusername)

# Optional: Override default AWS settings
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=reddit_ingest_state
```

**Key Configuration Settings (`config.py`):**

* 🗂️ **S3\_IMAGE\_BUCKET**: `"ajbarea-aws-translate"` - S3 bucket for image storage
* 🌐 **SOURCE\_LANGUAGE\_CODE**: `"es"` - Default source language (Spanish)
* 🌐 **TARGET\_LANGUAGE\_CODE**: `"en"` - Default target language (English)
* 📍 **AWS\_REGION**: `"us-east-1"` - AWS region for all services

## 🔄 Storage Backend Management

### 📦 Switching Between AWS S3 and Google Cloud Storage

This project includes a **Storage Adapter** that allows you to seamlessly switch between AWS S3 and Google Cloud Storage without changing your application code. This is particularly useful when you're hitting AWS free tier limits during development.

#### 🚀 Quick Storage Switch Commands

```bash
# Check current storage backend
python configure_storage.py --status

# Switch to Google Cloud Storage (or your own gcloud image bucket)
python configure_storage.py --backend gcs --bucket-name gcloud-image-bucket

# Switch back to AWS S3
python configure_storage.py --backend aws
```

#### 🔧 Google Cloud Storage Setup

**Prerequisites:**

1. **Install Google Cloud SDK:** Download from [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install)
2. **Install Python dependencies:**

   ```bash
   pip install .[gcs]
   # OR use the automated installer
   python configure_storage.py --install-gcs
   ```

**Authentication Setup:**

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your Google Cloud project
gcloud config set project YOUR_PROJECT_ID

# Verify your bucket exists (`gcloud-image-bucket` is default)
gsutil ls gs://gcloud-image-bucket
```

**Configure the Storage Adapter:**

```bash
# Switch to Google Cloud Storage
python configure_storage.py --backend gcs --bucket-name gcloud-image-bucket

# Verify configuration
python configure_storage.py --status
```

#### 📊 Storage Backend Comparison

| Feature | AWS S3 Free Tier | Google Cloud Storage Always Free |
|---------|------------------|-----------------------------------|
| 📦 Storage | 5 GB for 12 months | 5 GB regional storage |
| 🔄 Operations | 20,000 GET, 2,000 PUT | 5,000 Class A, 50,000 Class B operations |
| 🌐 Transfer | 15 GB out per month | 1 GB network egress |
| 💰 **Total Dev Capacity** | **~10 GB** when using both! | **Perfect for development** |

#### 🔒 Security & Authentication

**AWS S3 Authentication:**

* Uses existing AWS credentials (`~/.aws/credentials`)
* IAM roles
* Environment variables

**Google Cloud Storage Authentication:**

* Application Default Credentials
* Service Account JSON keys

**Production Service Account Setup:**

```bash
# Create service account for production
gcloud iam service-accounts create image-translate-storage

# Grant storage permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member='serviceAccount:image-translate-storage@YOUR_PROJECT_ID.iam.gserviceaccount.com' \
  --role='roles/storage.admin'

# Download credentials
gcloud iam service-accounts keys create gcs-key.json \
  --iam-account=image-translate-storage@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Configure with service account
python configure_storage.py --backend gcs --bucket-name gcloud-image-bucket --credentials gcs-key.json
```

#### 🔍 Troubleshooting Storage Issues

**Common Issues & Solutions:**

1. **"Import Error: google.cloud.storage"**

   ```bash
   python configure_storage.py --install-gcs
   ```

2. **"Your default credentials were not found"**

   ```bash
   # Option 1: Application Default Credentials (recommended)
   gcloud auth application-default login

   # Option 2: If gcloud not found in VS Code terminal
   export PATH="/c/Users/YOUR_USERNAME/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin:$PATH"
   gcloud auth application-default login
   ```

3. **"gcloud: command not found" in VS Code terminal**

   **Quick Fix:**

   ```bash
   # Add Google Cloud SDK to PATH (replace YOUR_USERNAME)
   export PATH="/c/Users/YOUR_USERNAME/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin:$PATH"
   gcloud --version
   ```

   **Permanent Fix:**
   * Add Google Cloud SDK to your system PATH in Windows Environment Variables
   * Or reload VS Code: `Ctrl+Shift+P` → "Developer: Reload Window"

4. **"The billing account for the owning project is disabled" (GCS)**

   Google Cloud Storage requires billing to be enabled, even for free tier usage:

   ```bash
   # Enable billing for your project in Google Cloud Console:
   # 1. Go to: https://console.cloud.google.com/billing
   # 2. Link your project to a billing account
   # 3. Google Cloud has a generous free tier that covers development needs
   ```

5. **"Permission denied" errors**
   * **AWS**: Check IAM permissions (`s3:GetObject`, `s3:PutObject`, `s3:ListBucket`)
   * **GCS**: Verify service account has `storage.admin` or similar permissions

6. **Storage connectivity test failed**

   ```bash
   # Test current configuration
   python configure_storage.py --test

   # Get setup help
   python configure_storage.py --setup-help gcs  # or aws
   ```

#### 📂 Storage Configuration Files

**Environment Configuration (`.env.local`):**

```env
# AWS S3 Configuration (default)
STORAGE_BACKEND=aws

# Google Cloud Storage Configuration
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=gcloud-image-bucket
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json  # Optional
```

**The storage adapter automatically handles:**

* ✅ Function call routing to the correct backend
* ✅ Bucket name management (GCS uses configured bucket, AWS uses function parameter)
* ✅ Error handling and logging
* ✅ File upload/download operations
* ✅ Image listing and filtering

#### 🎯 Development Workflow Example

```bash
# 1. Start with AWS S3 (default)
python main.py  # Uses AWS S3

# 2. Hit AWS free tier limits? Switch to GCS
python configure_storage.py --backend gcs --bucket-name gcloud-image-bucket

# 3. Continue development seamlessly
python main.py  # Now uses Google Cloud Storage - same code!

# 4. Ready for production? Switch back
python configure_storage.py --backend aws

# 5. Deploy to production with AWS
terraform apply
```

## 🛠️ Infrastructure Management

### 🚧 Infrastructure Deployment

1. **Initialize and deploy infrastructure:**

   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

2. **🧹 Clean up resources (Important - Avoid AWS costs):**

   ```bash
   cd terraform
   terraform destroy
   ```

## 🧪 Testing & Development

### ✅ Running Tests

```bash
pytest --cov=src

# Check for branches missing coverage
python -m pytest --cov=src --cov-report=term-missing --cov-branch
```

### 🧰 Development Tools and Code Quality

This project uses a suite of modern Python development tools to ensure high code quality and consistency. Code formatting, linting, and type-checking are automated using `pre-commit` hooks.

The primary tools include:

* 🧪 **`pytest`**: For running the comprehensive test suite.
* 🎨 **`black`**: For opinionated, consistent code formatting.
* ➗ **`isort`**: For automatically sorting imports.
* 🚨 **`flake8`**: For enforcing style and complexity rules.
* 🔍 **`mypy`**: For static type checking.

#### 🔄 Running Quality Checks

To run all code quality checks and formatters across the entire project, use the provided script:

```bash
./lint.sh
```

## 🏛️ Project Architecture Details

### 💻 Technology Stack

**🖥️ Backend:**

* **Python 3.13.2**: Core application language with modern features
* **AWS SDK (boto3)**: Cloud service integration
* **Reddit API (PRAW)**: Automated content discovery
* **BeautifulSoup4**: HTML parsing for media extraction

**🌐 Infrastructure:**

* **Terraform**: Infrastructure as Code for reproducible deployments
* **AWS Services**: S3, DynamoDB, Rekognition, Translate, Comprehend, Lambda
* **GitHub Actions**: CI/CD pipeline with automated testing and quality checks

**🎨 Frontend:**

* **Vanilla JavaScript**: Lightweight, fast, no frameworks required
* **AWS SDK for JavaScript**: Direct AWS service integration
* **AWS Cognito**: Secure user authentication and authorization

## 📚 Documentation and Resources

### ☁️ AWS Service Documentation

* [AWS Rekognition Text Detection](https://docs.aws.amazon.com/rekognition/latest/dg/text-detecting-text-procedure.html)
* [AWS S3 Developer Guide](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/list_objects_v2.html)
* [AWS Translate API Reference](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/translate/client/translate_text.html)
* [AWS Lambda Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/python-programming-model.html)

### 📒 Development Resources

* [Python PRAW Documentation](https://praw.readthedocs.io/en/stable/)
* [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
* [pytest Documentation](https://docs.pytest.org/en/stable/)
* [AWS SDK for Python (Boto3)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

### 🤝 Community Resources

* [Build Your Own Translator App Tutorial](https://community.aws/content/2drbcpmaBORz25L3e74AM6EIcFj/build-your-own-translator-app-in-less-30-min)
