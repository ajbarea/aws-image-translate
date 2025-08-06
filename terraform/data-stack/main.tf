terraform {
  required_version = ">= 1.8.0"

  backend "s3" {
    # Configuration is passed via -backend-config flag in deploy.py
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "lenslate"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

# Data sources for unique resource naming
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Generate unique suffix for all resources
resource "random_id" "this" {
  byte_length = 4
}
