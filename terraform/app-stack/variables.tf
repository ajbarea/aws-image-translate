variable "region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name of the project for resource tagging"
  type        = string
  default     = "lenslate"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "frontend_path" {
  description = "Local path to frontend files"
  type        = string
  default     = "../../frontend"
}

variable "allowed_origins" {
  description = "List of allowed origins for CORS"
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://localhost:5500",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080"
  ]
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

variable "reddit_client_id" {
  description = "Reddit API client ID for accessing Reddit data"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reddit_client_secret" {
  description = "Reddit API client secret for accessing Reddit data"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reddit_user_agent" {
  description = "User agent string for Reddit API requests"
  type        = string
  default     = "python:lenslate-image-collector:v1.0 (by /u/yourbot)"
}

variable "mmid_languages" {
  description = "Comma-separated list of language codes to sample images from in the MMID dataset"
  type        = string
  default     = "chinese,hindi,spanish,arabic,french"
}

variable "mmid_images_per_language" {
  description = "Number of MMID images to sample per language"
  type        = number
  default     = 2
}

variable "google_oauth_client_id" {
  description = "Google OAuth 2.0 client ID for SSO integration"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_oauth_client_secret" {
  description = "Google OAuth 2.0 client secret for SSO integration"
  type        = string
  sensitive   = true
  default     = ""
}

variable "use_secrets_manager_oauth" {
  description = "Use AWS Secrets Manager for OAuth credentials instead of .env.local (recommended for teams)"
  type        = bool
  default     = false
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "lenslate"
}

variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
  default     = "RIT-SWEN-514-00"
}

variable "github_connection_arn" {
  description = "ARN of the CodeStar connection to GitHub (optional - leave empty to skip CI/CD pipeline)"
  type        = string
  default     = ""
}

variable "pipeline_branches" {
  description = "List of branches to create pipelines for"
  type        = list(string)
  default     = ["master", "develop", "aj-reddit-stream"]
}

variable "data_stack_state_bucket" {
  description = "S3 bucket name for data-stack Terraform state"
  type        = string
  default     = ""
}
