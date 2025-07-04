output "api_invoke_url" {
  description = "The invoke URL of the API Gateway"
  value       = aws_apigatewayv2_api.image_api.api_endpoint
}
