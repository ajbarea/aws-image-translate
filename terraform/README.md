# AWS Image Translation Pipeline - Terraform Infrastructure

> **Infrastructure as Code for AWS AI/ML Translation Services**
> Automated provisioning and management of AWS resources for image text extraction, language detection, and translation pipeline using Terraform.

This directory contains the Terraform configuration for deploying the AWS infrastructure for the image translation pipeline.

## 🏗️ Architecture Overview

The infrastructure is defined in a flat structure within this directory, with resources grouped into logical files:

```text
terraform/
├─ main.tf              # Main entry point, provider configuration
├─ api.tf               # API Gateway resources
├─ cognito.tf           # Cognito User Pool and Identity Pool
├─ dynamodb.tf          # DynamoDB table for state tracking
├─ frontend.tf          # S3 bucket and CloudFront for frontend hosting
├─ lambda.tf            # Lambda functions for image processing and Cognito triggers
├─ s3.tf                # S3 bucket for image storage
├─ variables.tf         # All input variables
├─ outputs.tf           # All output values
└─ terraform.tfvars.example # Example variables file
```

## 📋 Prerequisites

1. **AWS CLI configured** with appropriate credentials (`aws configure`).
2. **Terraform installed** (>= 1.0) - Available at [terraform.io](https://terraform.io).
3. **Python 3.8+** for Lambda function packaging.

## 🚀 Quick Start

All Terraform commands should be executed from this `terraform/` directory.

1. **Edit the variables file:**
    Create `terraform.tfvars` in this directory (you can copy `terraform.tfvars.example`), and update the following variables to be globally unique:
    - `s3_bucket_name`
    - `frontend_bucket_name`

2. **Initialize Terraform:**
    ```bash
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

## 🛠️ Useful Commands

```bash
# Check what will be created/changed
terraform plan

# Check current state
terraform show

# View outputs after deployment
terraform output

# Validate configuration
terraform validate
```

## ⚙️ Configuration

All configuration is managed in `variables.tf` and `terraform.tfvars`.

## 🗑️ Cleanup

To destroy all resources and avoid ongoing costs:
```bash
terraform destroy
```