# AWS Image Translation Pipeline - Terraform Infrastructure

This directory contains the Terraform configuration for deploying AWS infrastructure for the image translation pipeline.

## Architecture

The infrastructure includes:

- **DynamoDB**: Table for tracking Reddit post processing state
- **S3**: Bucket for storing images
- **IAM**: Roles and policies for application permissions
- **AWS Services**: Rekognition (text detection) and Translate (text translation)

## Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **Terraform installed** (>= 1.0)
3. **Unique S3 bucket name** (S3 bucket names are globally unique)

## Quick Start

1. **Copy the example variables file:**

   ```bash
   cp environments/dev/terraform.tfvars.example environments/dev/terraform.tfvars
   ```

2. **Edit the variables file:**

   ```bash
   # Edit environments/dev/terraform.tfvars
   # Update s3_bucket_name to something globally unique
   # Add your Reddit API credentials
   ```

3. **Initialize Terraform:**

   ```bash
   cd terraform
   terraform init
   ```

4. **Plan the deployment:**

   ```bash
   terraform plan -var-file="environments/dev/terraform.tfvars"
   ```

5. **Apply the infrastructure:**

   ```bash
   terraform apply -var-file="environments/dev/terraform.tfvars"
   ```

## Cost Management

### Expected Monthly Costs (Development Usage)

- **DynamoDB**: ~$0.65/month (1 RCU/WCU) or $0.25 per million requests (on-demand)
- **S3**: ~$0.023 per GB stored + request costs
- **Rekognition**: $1.50 per 1,000 images analyzed
- **Translate**: $15 per million characters

### Cost Optimization Features

- **S3 Lifecycle**: Automatically transitions objects to cheaper storage classes
- **DynamoDB On-Demand**: Pay only for what you use
- **TTL on backup tables**: Automatically delete old data

## Environment Management

### Development

```bash
terraform workspace select dev  # or create if it doesn't exist
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### Production

```bash
terraform workspace select prod
terraform apply -var-file="environments/prod/terraform.tfvars"
```

## Cleanup

To destroy all resources and avoid ongoing costs:

```bash
# Destroy development environment
terraform destroy -var-file="environments/dev/terraform.tfvars"

# Or destroy specific resources
terraform destroy -target=module.dynamodb -var-file="environments/dev/terraform.tfvars"
```

## File Structure

```text
terraform/
├── main.tf                    # Root module configuration
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── data.tf                    # Data sources
├── modules/                   # Reusable modules
│   ├── dynamodb/             # DynamoDB table module
│   └── s3/                   # S3 bucket module
└── environments/             # Environment-specific configs
    └── dev/
        └── terraform.tfvars  # Development variables
```

## Security Best Practices

1. **Never commit sensitive variables** to version control
2. **Use AWS IAM roles** instead of hardcoded credentials
3. **Enable encryption** for all data at rest and in transit
4. **Use least privilege** IAM policies
5. **Store Terraform state remotely** in S3 with state locking

## Remote State Setup (Recommended)

For production use, store Terraform state in S3:

1. Create an S3 bucket for Terraform state
2. Create a DynamoDB table for state locking
3. Uncomment and configure the backend in `main.tf`

## Troubleshooting

### Common Issues

1. **S3 bucket name conflicts**: Choose a globally unique bucket name
2. **AWS credentials**: Ensure AWS CLI is configured with proper permissions
3. **Region availability**: Some services may not be available in all regions

### Useful Commands

```bash
# Check current state
terraform show

# Import existing resources
terraform import aws_s3_bucket.images your-existing-bucket-name

# Refresh state
terraform refresh

# View outputs
terraform output
```

## Integration with Python Application

After deploying, update your `config.py` file with the output values:

```python
# Use terraform output to get these values
DYNAMODB_TABLE_NAME = "reddit-ingest-state-dev"  # from terraform output
S3_IMAGE_BUCKET = "your-unique-bucket-name-dev"  # from terraform output
```

Or use the Terraform outputs directly in your CI/CD pipeline.
