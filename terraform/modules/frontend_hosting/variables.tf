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

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "user_pool_id" {
  description = "Cognito User Pool ID"
  type        = string
}

variable "user_pool_web_client" {
  description = "Cognito User Pool Web Client ID"
  type        = string
}

variable "identity_pool_id" {
  description = "Cognito Identity Pool ID"
  type        = string
}

variable "api_gateway_url" {
  description = "API Gateway URL"
  type        = string
}

variable "lambda_function_name" {
  description = "Lambda Function Name"
  type        = string
}
