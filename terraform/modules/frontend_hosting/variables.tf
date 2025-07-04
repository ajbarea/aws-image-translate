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

variable "config_file_ready" {
  description = "A dummy variable to ensure config.js is generated before frontend upload."
  type        = string
  default     = ""
}
