# AWS Image Translation Pipeline - Terraform Infrastructure

> **Infrastructure as Code for AWS AI/ML Translation Services**
> Automated provisioning and management of AWS resources for image text extraction, language detection, and translation pipeline using Terraform.

This directory contains the Terraform configuration for deploying the AWS infrastructure for the image translation pipeline.

## 🏗️ Architecture Overview (Feature-Driven)

The infrastructure is organized into feature-specific modules, encapsulating all resources related to a particular application domain.

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

## 📋 Prerequisites

1. **AWS CLI configured** with appropriate credentials (`aws configure`).
2. **Terraform installed** (>= 1.0) - Available at [terraform.io](https://terraform.io).
3. **Python 3.8+** for Lambda function packaging.

## 🚀 Quick Start (Development Environment)

All Terraform commands should be executed from the `terraform/envs/dev` directory.

1. **Navigate to the development environment directory:**

    ```bash
    cd terraform/envs/dev
    ```

2. **Edit the variables file:**
    Create `terraform.tfvars` in `terraform/envs/dev` if it doesn't exist, and update `project_name` and `s3_bucket_name` to be globally unique.

    ```hcl
    # terraform/envs/dev/terraform.tfvars
    project_name = "your-unique-project-name-dev"
    s3_bucket_name = "your-globally-unique-image-bucket"
    frontend_path = "../../frontend" # Path to your frontend build directory
    ```

3. **Initialize Terraform:**

    ```bash
    terraform init
    ```

4. **Plan the deployment:**

    ```bash
    terraform plan
    ```

5. **Apply the infrastructure:**

    ```bash
    terraform apply
    ```

## 🛠️ Useful Commands (run from `terraform/envs/dev`)

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

## ⚙️ Configuration

The primary configuration for the development environment is in `terraform/envs/dev/variables.tf` and `terraform/envs/dev/terraform.tfvars`.

## Security Features

Security features like S3 public access blocks, server-side encryption, versioning, lifecycle rules, DynamoDB encryption, and IAM least privilege access are configured within their respective feature modules (`image_translation`, `user_management`, `frontend_hosting`).

## Cleanup

To destroy all resources for the development environment and avoid ongoing costs:

```bash
cd terraform/envs/dev
terraform destroy
```
