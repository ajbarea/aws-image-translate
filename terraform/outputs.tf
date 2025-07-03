# Output values from the AWS Image Translation infrastructure

# Resource Identifiers
output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for Reddit state tracking"
  value       = module.dynamodb.table_name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = module.dynamodb.table_arn
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for image storage"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

# Configuration Information
output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "project_name" {
  description = "Project name used for tagging"
  value       = var.project_name
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

# Lambda outputs
output "lambda_function_arn" {
  description = "ARN of the Lambda function for image processing"
  value       = module.lambda.lambda_function_arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.lambda.lambda_function_name
}

output "api_gateway_url" {
  description = "API Gateway URL for image processing"
  value       = module.lambda.api_gateway_invoke_url
}

output "api_gateway_invoke_url" {
  description = "API Gateway invoke URL for image processing"
  value       = module.lambda.api_gateway_invoke_url
}

# Integration Information
output "integration_config" {
  description = "Configuration values for Python application and frontend integration"
  value = {
    DYNAMODB_TABLE_NAME = module.dynamodb.table_name
    S3_IMAGE_BUCKET     = module.s3.bucket_name
    AWS_REGION          = var.aws_region
    USER_POOL_ID        = module.cognito.user_pool_id
    USER_POOL_CLIENT_ID = module.cognito.user_pool_client_id
    IDENTITY_POOL_ID    = module.cognito.identity_pool_id
    LAMBDA_FUNCTION_ARN = module.lambda.lambda_function_arn
    API_GATEWAY_URL     = module.lambda.api_gateway_invoke_url
  }
}

# Frontend URLs
output "frontend_website_url" {
  description = "S3 website URL for the frontend"
  value       = module.frontend.website_url
}

output "frontend_cloudfront_url" {
  description = "CloudFront distribution URL for the frontend"
  value       = module.frontend.cloudfront_url
}
