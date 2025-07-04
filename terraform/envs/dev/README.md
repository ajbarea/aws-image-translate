# AWS Image Translation Pipeline - Development Environment

> **Infrastructure as Code for AWS AI/ML Translation Services**
> Automated provisioning and management of AWS resources for image text extraction, language detection, and translation pipeline using Terraform.

This directory contains the **development environment** configuration for the AWS image translation pipeline infrastructure.

## 🏗️ Architecture Overview

The infrastructure is organized into feature-specific modules:

```text
terraform/
├─ modules/
│   ├─ api/                 # API Gateway resources for the application API
│   ├─ frontend_hosting/    # S3 bucket and CloudFront for static frontend hosting
│   ├─ image_translation/   # Lambda, S3 (image storage), DynamoDB (state tracking) for image processing
│   └─ user_management/     # Cognito User Pool, Identity Pool, and related Lambda triggers
└─ envs/
    └─ dev/                 # Development environment configuration (main entry point)
        ├─ main.tf          # Wires together feature modules for the dev environment
        ├─ variables.tf
        ├─ outputs.tf
        └─ terraform.tfvars
```

## � Terraform Cloud Deployment

This environment is configured for **automated deployment via Terraform Cloud**:

- **Working Directory**: `terraform/envs/dev`
- **Auto-apply**: Enabled (changes are automatically applied after successful plans)
- **VCS Integration**: Connected to GitHub repository
- **Execution Mode**: Remote

### Required Variables in Terraform Cloud

**Environment Variables:**

- `AWS_ACCESS_KEY_ID` (sensitive)
- `AWS_SECRET_ACCESS_KEY` (sensitive)  
- `AWS_DEFAULT_REGION` (e.g., "us-east-1")

**Terraform Variables:**

- `project_name` (default: "aws-image-translate-dev")
- `region` (default: "us-east-1")
- `allowed_origins` (default: ["http://localhost:8080"])
- `additional_origins` (default: [])

## 📋 Local Development Prerequisites

1. **AWS CLI configured** with appropriate credentials (`aws configure`)
2. **Terraform installed** (>= 1.0) - Available at [terraform.io](https://terraform.io)
3. **Python 3.8+** for Lambda function packaging

## 🛠️ Local Development Commands

For local development and testing (run from this directory):

```bash
# Initialize Terraform
terraform init

# Check what will be created/changed
terraform plan

# Apply changes locally (not recommended - use Terraform Cloud)
terraform apply

# View outputs after deployment
terraform output

# Validate configuration
terraform validate

# Check current state
terraform show
terraform state list
```

## 🔄 Deployment Process

1. **Push changes** to the main branch
2. **Terraform Cloud automatically**:
   - Detects changes via GitHub webhook
   - Runs `terraform plan`
   - Auto-applies if plan succeeds (auto-apply enabled)
   - Updates infrastructure in AWS

## 🛡️ Security Features

- S3 public access blocks and server-side encryption
- IAM least privilege access policies
- DynamoDB encryption at rest
- CloudFront security headers
- VPC security groups (when applicable)

## 🗑️ Cleanup

To destroy all resources and avoid ongoing costs:

```bash
# Via Terraform Cloud: Queue a destroy run
# Via CLI (emergency only):
terraform destroy
```

## 📊 Monitoring

- Check Terraform Cloud workspace for run status
- Monitor AWS CloudWatch for application metrics
- Review AWS Cost Explorer for resource costs
