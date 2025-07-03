# Variables for S3 module

variable "bucket_name" {
  description = "Name of the S3 bucket (must be globally unique)"
  type        = string
}

variable "enable_lifecycle" {
  description = "Whether to enable lifecycle management for cost optimization"
  type        = bool
  default     = true
}

variable "enable_versioning" {
  description = "Whether to enable S3 bucket versioning"
  type        = bool
  default     = true
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

variable "force_destroy" {
  description = "Whether to allow Terraform to destroy the bucket even if it contains objects"
  type        = bool
  default     = true
}
