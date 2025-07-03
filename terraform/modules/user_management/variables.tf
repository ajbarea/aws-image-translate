# Variables for Cognito module

variable "project_name" {
  description = "Name of the project for resource naming"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket to grant access to"
  type        = string
}

variable "enable_auth" {
  description = "Whether to enable Cognito authentication"
  type        = bool
  default     = true
}

variable "cognito_triggers_file_path" {
  description = "The absolute path to the cognito triggers lambda file."
  type        = string
}