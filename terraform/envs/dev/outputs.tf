output "cognito_user_pool_id" {
  description = "The ID of the Cognito User Pool."
  value       = module.user_management.user_pool_id
}

output "cognito_user_pool_client_id" {
  description = "The ID of the Cognito User Pool Client."
  value       = module.user_management.user_pool_client_id
}

output "cognito_identity_pool_id" {
  description = "The ID of the Cognito Identity Pool."
  value       = module.user_management.identity_pool_id
}

output "api_invoke_url" {
  description = "The invoke URL of the API Gateway."
  value       = module.api.api_invoke_url
}

output "frontend_s3_bucket_website_url" {
  description = "The S3 website URL for the frontend."
  value       = module.frontend_hosting.website_url
}

output "cloudfront_url" {
  description = "The CloudFront distribution URL."
  value       = module.frontend_hosting.cloudfront_url
}
