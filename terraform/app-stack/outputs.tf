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

output "cognito_domain_url" {
  description = "The Cognito User Pool Domain URL for OAuth endpoints."
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
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

output "frontend_s3_bucket_name" {
  description = "Name of the S3 bucket for frontend hosting"
  value       = aws_s3_bucket.frontend_hosting.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidation"
  value       = aws_cloudfront_distribution.website.id
}

output "cloudfront_invalidations_console_url" {
  description = "AWS Console URL to view CloudFront invalidations"
  value       = "https://us-east-1.console.aws.amazon.com/cloudfront/v4/home?region=us-east-1#/distributions/${aws_cloudfront_distribution.website.id}/invalidations"
}

output "google_oauth_javascript_origins" {
  description = "JavaScript origins to add to Google OAuth client"
  sensitive   = true
  value = local.google_oauth_enabled ? [
    "https://${aws_cloudfront_distribution.website.domain_name}",
    "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
  ] : []
}

output "google_oauth_redirect_uri" {
  description = "Redirect URI to add to Google OAuth client"
  sensitive   = true
  value       = local.google_oauth_enabled ? "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com/oauth2/idpresponse" : ""
}

output "google_oauth_client_id" {
  description = "Google OAuth Client ID being used"
  sensitive   = true
  value       = local.google_oauth_enabled ? local.oauth_client_id : "Not configured"
}

output "google_oauth_console_url" {
  description = "Direct link to Google Cloud Console OAuth configuration"
  sensitive   = true
  value       = local.google_oauth_enabled ? "https://console.cloud.google.com/apis/credentials" : "Not configured"
}

output "google_oauth_status" {
  description = "Google OAuth configuration status and next steps"
  sensitive   = true
  value = local.google_oauth_enabled ? {
    configured  = true
    message     = var.use_secrets_manager_oauth ? "Google OAuth is configured via AWS Secrets Manager. Run 'python update-google-oauth.py' to update Google Cloud Console with current URLs." : "Google OAuth is configured. Run 'python update-google-oauth.py' to update Google Cloud Console with current URLs."
    config_file = "terraform/google-oauth-config.txt"
    method      = var.use_secrets_manager_oauth ? "AWS Secrets Manager" : "Environment Variables"
    } : {
    configured  = false
    message     = var.use_secrets_manager_oauth ? "Google OAuth not configured. Set up AWS Secrets Manager with OAuth credentials to enable Google sign-in." : "Google OAuth not configured. Add GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET to .env.local to enable Google sign-in."
    config_file = null
    method      = var.use_secrets_manager_oauth ? "AWS Secrets Manager" : "Environment Variables"
  }
}

# Reddit Gallery Management Outputs
output "reddit_populator_function_name" {
  description = "Name of the Reddit populator Lambda function"
  value       = aws_lambda_function.reddit_populator.function_name
}

output "reddit_scraper_rule_name" {
  description = "Name of the EventBridge rule for Reddit scraping"
  value       = aws_cloudwatch_event_rule.reddit_scraper_schedule.name
}
