# Outputs for Cognito module

output "user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.pool.id
}

output "user_pool_client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = aws_cognito_user_pool_client.client.id
}

output "identity_pool_id" {
  description = "ID of the Cognito Identity Pool"
  value       = aws_cognito_identity_pool.main.id
}

output "cognito_domain" {
  description = "Cognito domain"
  value       = aws_cognito_user_pool.pool.endpoint
}

output "cognito_triggers_lambda_arn" {
  description = "ARN of the Cognito triggers Lambda function"
  value       = aws_lambda_function.cognito_triggers.arn
}
