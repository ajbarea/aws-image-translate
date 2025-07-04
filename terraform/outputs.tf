# terraform/outputs.tf

output "cognito_user_pool_id" {
  description = "The ID of the Cognito User Pool."
  value       = aws_cognito_user_pool.pool.id
}

output "cognito_user_pool_client_id" {
  description = "The ID of the Cognito User Pool Client."
  value       = aws_cognito_user_pool_client.client.id
}

output "cognito_identity_pool_id" {
  description = "The ID of the Cognito Identity Pool."
  value       = aws_cognito_identity_pool.main.id
}

output "api_invoke_url" {
  description = "The invoke URL of the API Gateway."
  value       = aws_apigatewayv2_api.image_api.api_endpoint
}

output "frontend_s3_bucket_website_url" {
  description = "The S3 website URL for the frontend."
  value       = "http://${aws_s3_bucket_website_configuration.frontend_hosting.website_endpoint}"
}

output "cloudfront_url" {
  description = "The CloudFront distribution URL."
  value       = "https://${aws_cloudfront_distribution.website.domain_name}"
}

output "image_storage_bucket_name" {
  description = "Name of the S3 bucket for image storage"
  value       = aws_s3_bucket.image_storage.bucket
}
