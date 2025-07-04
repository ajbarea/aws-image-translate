# Outputs for Image Translation module

# Lambda Outputs
output "image_processor_lambda_function_arn" {
  description = "ARN of the image processor Lambda function"
  value       = aws_lambda_function.image_processor.arn
}

output "image_processor_lambda_function_name" {
  description = "Name of the image processor Lambda function"
  value       = aws_lambda_function.image_processor.function_name
}

output "image_processor_lambda_invoke_arn" {
  description = "Invoke ARN of the image processor Lambda function"
  value       = aws_lambda_function.image_processor.invoke_arn
}

# DynamoDB Outputs
output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.reddit_state.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.reddit_state.arn
}

# S3 Outputs
output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.images.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.images.arn
}
