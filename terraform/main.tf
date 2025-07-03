# Root Terraform configuration for AWS Image Translation Pipeline

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
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

provider "local" {}

# Frontend deployment with S3 and CloudFront
module "frontend" {
  count  = var.skip_frontend ? 0 : 1
  source = "./modules/frontend"

  bucket_name   = var.frontend_bucket_name
  environment   = var.environment
  frontend_path = var.frontend_path
}

# DynamoDB Table for Reddit state tracking
module "dynamodb" {
  source = "./modules/dynamodb"

  table_name          = var.dynamodb_table_name
  enable_backup_table = false             # Set to true if you want backup table
  billing_mode        = "PAY_PER_REQUEST" # or "PROVISIONED"
}

# S3 Bucket for image storage
module "s3" {
  source = "./modules/s3"

  bucket_name       = var.s3_bucket_name
  enable_lifecycle  = true # Enable cost optimization
  enable_versioning = true # Enable object versioning
  force_destroy     = true # Allow Terraform to delete bucket even if not empty
  allowed_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
  ]
}

# Cognito for frontend authentication
module "cognito" {
  source = "./modules/cognito"

  project_name  = var.project_name
  s3_bucket_arn = module.s3.bucket_arn
}

# Lambda for serverless image processing
module "lambda" {
  source = "./modules/lambda"

  project_name   = var.project_name
  s3_bucket_name = module.s3.bucket_name
  s3_bucket_arn  = module.s3.bucket_arn
  allowed_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
  ]
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

resource "aws_iam_policy" "app_policy" {
  name        = "image-translate-policy"
  description = "Policy for the main application to access AWS services"

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

resource "aws_iam_role_policy_attachment" "app_policy_attachment" {
  role       = aws_iam_role.app_role.name
  policy_arn = aws_iam_policy.app_policy.arn
}

resource "local_file" "frontend_config" {
  content = templatefile("${path.module}/config.js.tpl", {
    aws_region           = var.aws_region
    user_pool_id         = module.cognito.user_pool_id
    user_pool_web_client = module.cognito.user_pool_client_id
    identity_pool_id     = module.cognito.identity_pool_id
    bucket_name          = module.s3.bucket_name
    api_gateway_url      = module.lambda.api_gateway_invoke_url
    lambda_function_name = module.lambda.lambda_function_name
  })
  filename = "${path.root}/../frontend/js/config.js"
}
