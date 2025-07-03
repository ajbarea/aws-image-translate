variable "bucket_name" {
  description = "Name of the S3 bucket for website hosting"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "frontend_path" {
  description = "Local path to frontend files"
  type        = string
}
