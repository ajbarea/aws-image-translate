# Variables for Image Translation module

variable "project_name" {
  description = "Name of the project for resource naming"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "force_destroy" {
  description = "Whether to allow Terraform to destroy the bucket even if it contains objects"
  type        = bool
  default     = true
}

variable "enable_versioning" {
  description = "Whether to enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "enable_lifecycle" {
  description = "Whether to enable lifecycle management for cost optimization"
  type        = bool
  default     = true
}

variable "table_name" {
  description = "Name of the DynamoDB table"
  type        = string
}

variable "enable_backup_table" {
  description = "Whether to create a backup table"
  type        = bool
  default     = false
}

variable "billing_mode" {
  description = "DynamoDB billing mode (PAY_PER_REQUEST or PROVISIONED)"
  type        = string
  default     = "PAY_PER_REQUEST"

  validation {
    condition     = contains(["PAY_PER_REQUEST", "PROVISIONED"], var.billing_mode)
    error_message = "Billing mode must be either PAY_PER_REQUEST or PROVISIONED."
  }
}

variable "allowed_origins" {
  description = "List of allowed origins for CORS"
  type        = list(string)
  default     = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
  ]
}

variable "additional_origins" {
  description = "Additional origins to add to CORS (e.g., CloudFront URL)"
  type        = list(string)
  default     = []
}

variable "skip_default_cors" {
  description = "Whether to skip the default CORS configuration (for when using custom CORS)"
  type        = bool
  default     = false
}