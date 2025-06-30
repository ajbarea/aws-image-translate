# Input variables for the AWS Image Translation infrastructure

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.aws_region))
    error_message = "AWS region must be a valid region identifier."
  }
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for Reddit state tracking"
  type        = string
  default     = "reddit-ingest-state"

  validation {
    condition     = can(regex("^[a-zA-Z0-9_.-]+$", var.dynamodb_table_name))
    error_message = "DynamoDB table name must contain only alphanumeric characters, hyphens, periods, and underscores."
  }
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for image storage (must be globally unique)"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9.-]+$", var.s3_bucket_name)) && length(var.s3_bucket_name) >= 3 && length(var.s3_bucket_name) <= 63
    error_message = "S3 bucket name must be 3-63 characters, contain only lowercase letters, numbers, hyphens, and periods."
  }
}

# Optional: Project tagging
variable "project_name" {
  description = "Name of the project for resource tagging"
  type        = string
  default     = "aws-image-translate"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}
