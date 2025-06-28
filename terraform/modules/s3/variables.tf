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
