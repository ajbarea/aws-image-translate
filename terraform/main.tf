# Root Terraform configuration for AWS Image Translation Pipeline

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Uncomment and configure for remote state storage
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "aws-image-translate/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# DynamoDB Table for Reddit state tracking
module "dynamodb" {
  source = "./modules/dynamodb"
  
  table_name           = var.dynamodb_table_name
  enable_backup_table  = false  # Set to true if you want backup table
  billing_mode        = "PAY_PER_REQUEST"  # or "PROVISIONED"
}

# S3 Bucket for image storage
module "s3" {
  source = "./modules/s3"
  
  bucket_name        = var.s3_bucket_name
  enable_lifecycle   = true   # Enable cost optimization
  enable_versioning  = true   # Enable object versioning
}

# IAM roles and policies for the application
resource "aws_iam_role" "app_role" {
  name = "image-translate-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "app_policy" {
  name = "image-translate-policy"
  role = aws_iam_role.app_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:Query"
        ]
        Resource = module.dynamodb.table_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          module.s3.bucket_arn,
          "${module.s3.bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "rekognition:DetectText"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "comprehend:DetectDominantLanguage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "translate:TranslateText"
        ]
        Resource = "*"
      }
    ]
  })
}
