# terraform/api.tf

resource "aws_apigatewayv2_api" "image_api" {
  name          = "${var.project_name}-image-api"
  protocol_type = "HTTP"
  description   = "API for image processing"

  cors_configuration {
    allow_origins = concat(var.allowed_origins, var.additional_origins, ["*"])
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"]
  }
}

resource "aws_apigatewayv2_stage" "api_stage" {
  api_id      = aws_apigatewayv2_api.image_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.image_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.image_processor.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "process_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "POST /process"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}
