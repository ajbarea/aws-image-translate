# Terraform configuration for AWS API Gateway v2
resource "aws_apigatewayv2_api" "image_api" {
  name          = "${var.project_name}-image-api-${var.environment}-${local.random_suffix}"
  protocol_type = "HTTP"
  description   = "API for image processing"

  cors_configuration {
    allow_origins = concat(
      var.allowed_origins,
      var.additional_origins,
      ["https://${aws_cloudfront_distribution.website.domain_name}"]
    )
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"]
  }

  tags = local.common_tags

  depends_on = [aws_cloudfront_distribution.website]
}

resource "aws_apigatewayv2_stage" "api_stage" {
  api_id      = aws_apigatewayv2_api.image_api.id
  name        = "$default"
  auto_deploy = true
}

# JWT Authorizer for Cognito authentication
resource "aws_apigatewayv2_authorizer" "cognito_authorizer" {
  api_id           = aws_apigatewayv2_api.image_api.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.project_name}-cognito-authorizer-${var.environment}-${local.random_suffix}"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.client.id]
    issuer   = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.pool.id}"
  }
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.image_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.image_processor.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "gallery_integration" {
  api_id                 = aws_apigatewayv2_api.image_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.gallery_lister.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "user_manager_integration" {
  api_id                 = aws_apigatewayv2_api.image_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.user_manager.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "history_handler_integration" {
  api_id                 = aws_apigatewayv2_api.image_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.history_handler.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "history_detail_integration" {
  api_id                 = aws_apigatewayv2_api.image_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.history_detail_handler.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "performance_handler_integration" {
  api_id                 = aws_apigatewayv2_api.image_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.performance_handler.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "process_route" {
  api_id             = aws_apigatewayv2_api.image_api.id
  route_key          = "POST /process"
  target             = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_authorizer.id
}

resource "aws_apigatewayv2_route" "gallery_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "GET /gallery"
  target    = "integrations/${aws_apigatewayv2_integration.gallery_integration.id}"
}

resource "aws_apigatewayv2_route" "user_unlink_google_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "DELETE /user/unlink-google"
  target    = "integrations/${aws_apigatewayv2_integration.user_manager_integration.id}"
}

resource "aws_apigatewayv2_route" "user_set_password_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "POST /user/set-password"
  target    = "integrations/${aws_apigatewayv2_integration.user_manager_integration.id}"
}

resource "aws_apigatewayv2_route" "user_link_google_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "POST /user/link-google"
  target    = "integrations/${aws_apigatewayv2_integration.user_manager_integration.id}"
}

resource "aws_apigatewayv2_route" "history_list_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "GET /history"
  target    = "integrations/${aws_apigatewayv2_integration.history_handler_integration.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_authorizer.id
}

resource "aws_apigatewayv2_route" "history_detail_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "GET /history/{history_id}"
  target    = "integrations/${aws_apigatewayv2_integration.history_detail_integration.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_authorizer.id
}

resource "aws_apigatewayv2_route" "performance_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "GET /performance"
  target    = "integrations/${aws_apigatewayv2_integration.performance_handler_integration.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_authorizer.id
}

resource "aws_apigatewayv2_route" "performance_services_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "GET /performance/services"
  target    = "integrations/${aws_apigatewayv2_integration.performance_handler_integration.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_authorizer.id
}

resource "aws_apigatewayv2_route" "performance_current_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "GET /performance/current"
  target    = "integrations/${aws_apigatewayv2_integration.performance_handler_integration.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_authorizer.id
}

resource "aws_apigatewayv2_route" "performance_frontend_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "POST /performance/frontend"
  target    = "integrations/${aws_apigatewayv2_integration.performance_handler_integration.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_authorizer.id
}

resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_gallery_api_gateway" {
  statement_id  = "AllowGalleryExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gallery_lister.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_user_manager_api_gateway" {
  statement_id  = "AllowUserManagerExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.user_manager.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_history_handler_api_gateway" {
  statement_id  = "AllowHistoryHandlerExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.history_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_history_detail_api_gateway" {
  statement_id  = "AllowHistoryDetailExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.history_detail_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_performance_handler_api_gateway" {
  statement_id  = "AllowPerformanceHandlerExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.performance_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}
