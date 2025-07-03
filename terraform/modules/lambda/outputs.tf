# Outputs for Lambda module

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.image_processor.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.image_processor.function_name
}

output "api_gateway_invoke_url" {
  description = "Invoke URL of the API Gateway"
  value       = aws_apigatewayv2_api.image_api.api_endpoint
}
