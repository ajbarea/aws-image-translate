# terraform/variables.tf

variable "region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name of the project for resource tagging"
  type        = string
  default     = "aws-image-translate"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for image storage (must be globally unique)"
  type        = string
  default     = "aj-aws-image-translate-terraform"
}

variable "frontend_bucket_name" {
  description = "Name of S3 bucket for website hosting"
  type        = string
  default     = "aj-aws-image-translate-dev-frontend-hosting"
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state tracking"
  type        = string
  default     = "image-translation-state"
}

variable "frontend_path" {
  description = "Local path to frontend files"
  type        = string
  default     = "../frontend"
}

variable "allowed_origins" {
  description = "List of allowed origins for CORS"
  type        = list(string)
  default     = ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5500", "http://127.0.0.1:5500"]
}

variable "additional_origins" {
  description = "Additional allowed origins for CORS configuration, typically for dynamic environments."
  type        = list(string)
  default     = []
}

variable "cognito_access_token_validity" {
  description = "Validity period for Cognito access tokens (in hours, 1-24)"
  type        = number
  default     = 1
  validation {
    condition     = var.cognito_access_token_validity >= 1 && var.cognito_access_token_validity <= 24
    error_message = "Access token validity must be between 1 and 24 hours."
  }
}

variable "cognito_id_token_validity" {
  description = "Validity period for Cognito ID tokens (in hours, 1-24)"
  type        = number
  default     = 1
  validation {
    condition     = var.cognito_id_token_validity >= 1 && var.cognito_id_token_validity <= 24
    error_message = "ID token validity must be between 1 and 24 hours."
  }
}

variable "cognito_refresh_token_validity" {
  description = "Validity period for Cognito refresh tokens (in days, 1-3650)"
  type        = number
  default     = 30
  validation {
    condition     = var.cognito_refresh_token_validity >= 1 && var.cognito_refresh_token_validity <= 3650
    error_message = "Refresh token validity must be between 1 and 3650 days (10 years)."
  }
}
