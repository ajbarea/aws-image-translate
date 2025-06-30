# AWS Image Translation Pipeline - Terraform Infrastructure

> **Infrastructure as Code for AWS AI/ML Translation Services**  
> Automated provisioning and management of AWS resources for image text extraction, language detection, and translation pipeline using Terraform.

This directory contains simplified Terraform configuration for deploying AWS infrastructure for the image translation pipeline.

## 🏗️ What This Creates

- **DynamoDB Table**: `reddit_ingest_state` for tracking Reddit post processing state
- **S3 Bucket**: Secure storage for images with encryption, versioning, and lifecycle rules
- **IAM Role & Policy**: Application permissions for accessing DynamoDB, S3, Rekognition, and Translate services

## 🔧 Architecture Overview

```text
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Python App   │───▶│  S3 Bucket   │───▶│  AWS Services   │
│                 │    │  (Images)    │    │ - Rekognition   │
└─────────────────┘    └──────────────┘    │ - Translate     │
         │                                  └─────────────────┘
         ▼
┌─────────────────┐
│ DynamoDB Table  │
│ (Reddit State)  │
└─────────────────┘
```

## 📋 Prerequisites

1. **AWS CLI configured** with appropriate credentials (`aws configure`)
2. **Terraform installed** (>= 1.0) - We'll use `C:\terraform\terraform.exe`
3. **Unique S3 bucket name** (S3 bucket names must be globally unique)

## 🚀 Quick Start

1. **Edit the variables file:**

   ```bash
   # Edit terraform/terraform.tfvars
   # Update s3_bucket_name to something globally unique
   # Your Reddit API credentials are already set up
   ```

2. **Initialize Terraform:**

   ```bash
   cd terraform
   terraform init
   ```

3. **Plan the deployment:**

   ```bash
   terraform plan
   ```

4. **Apply the infrastructure:**

   ```bash
   terraform apply
   ```

## 🛠️ Using the Deploy Scripts (Recommended)

Instead of running terraform commands directly, you can use the deployment scripts:

**Windows (PowerShell):**

```powershell
.\deploy.ps1 -Action init
.\deploy.ps1 -Action plan
.\deploy.ps1 -Action apply
```

**Linux/Mac/Windows Bash:**

```bash
./deploy.sh init
./deploy.sh plan  
./deploy.sh apply
```

## ⚙️ Configuration

Your `terraform.tfvars` is already configured with:

```hcl
aws_region = "us-east-1"
dynamodb_table_name = "reddit_ingest_state"
s3_bucket_name = "ajbarea"  # Make sure this is globally unique!

# Reddit API credentials (synchronized with .env.local)
reddit_client_id     = "jn9y3ZKeyvpmYtIa7POWKg"
reddit_client_secret = "So3_AYuHcyOkYugn14TXTvMEp7zYqg"
reddit_user_agent    = "python:translate-images-bot:1.0 (by u/NoNeck4585)"
reddit_username      = "NoNeck4585"
reddit_password      = "YOUR_REDDIT_PASSWORD"
```

## Cost Estimation

**Expected monthly costs for light development usage:**

- **DynamoDB**: ~$1-5/month (pay-per-request)
- **S3**: ~$0.10-1/month (depending on storage)
- **Rekognition**: $1.50 per 1,000 images analyzed
- **Translate**: $15 per million characters translated

Most costs are pay-per-use, so minimal usage = minimal cost.

## Security Features

✅ **S3 Security:**

- Public access blocked
- Server-side encryption (AES256)
- Versioning enabled
- Lifecycle rules for cost optimization

✅ **DynamoDB Security:**

- Server-side encryption enabled
- Point-in-time recovery enabled

✅ **IAM Security:**

- Least privilege access
- Specific resource permissions only

## Cleanup

To destroy all resources and avoid ongoing costs:

```bash
terraform destroy
# or
./deploy.sh destroy
```

## File Structure

```text
terraform/
├── main.tf                # Main infrastructure configuration
├── variables.tf           # Input variables  
├── outputs.tf            # Output values
├── data.tf               # Data sources
├── terraform.tfvars      # Your actual values (configured)
├── terraform.tfvars.example  # Template for new setups
├── deploy.sh             # Bash deployment script
├── deploy.ps1            # PowerShell deployment script
└── modules/              # Reusable modules
    ├── dynamodb/         # DynamoDB table module
    └── s3/               # S3 bucket module
```

## Troubleshooting

### Common Issues

1. **S3 bucket name conflicts**: Choose a globally unique bucket name in `terraform.tfvars`
2. **AWS credentials**: Ensure `aws configure` is set up with proper permissions
3. **Terraform path**: Scripts use `C:\terraform\terraform.exe` (Windows) or system `terraform` (Linux/Mac)

### Useful Commands

```bash
# Check what will be created/changed
terraform plan

# Check current state
terraform show

# View outputs after deployment
terraform output

# Validate configuration
terraform validate

# Check current workspace and state
terraform workspace show
terraform state list
```

## Integration with Python Application

After deploying, your resources will match your Python `config.py`:

```python
# These values are already synchronized:
DYNAMODB_TABLE_NAME = "reddit_ingest_state"
S3_IMAGE_BUCKET = "ajbarea"
AWS_REGION = "us-east-1"
```

The infrastructure is designed to work seamlessly with your existing Python application configuration.
