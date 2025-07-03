# Lambda module for image processing

# Get current AWS region
data "aws_region" "current" {}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# ZIP the Lambda function code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../lambda"
  output_path = "${path.root}/lambda_function.zip"
}

# Lambda function
resource "aws_lambda_function" "image_processor" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = "${var.project_name}-image-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "image_processor.lambda_handler"
  runtime       = "python3.11"
  timeout       = 90
  memory_size   = 512

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET = var.s3_bucket_name
    }
  }

  tags = {
    Name = "${var.project_name}-image-processor"
  }
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Lambda execution policy
resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.project_name}-lambda-policy"
  description = "Policy for the image processor Lambda function"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${aws_lambda_function.image_processor.function_name}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${var.s3_bucket_arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "rekognition:DetectText"
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "comprehend:DetectDominantLanguage"
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "translate:TranslateText"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# S3 bucket notification to trigger Lambda
resource "aws_s3_bucket_notification" "lambda_trigger" {
  bucket = var.s3_bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.image_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ""
  }

  depends_on = [aws_lambda_permission.allow_s3]
}

# Permission for S3 to invoke Lambda
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.s3_bucket_arn
}

# API Gateway (HTTP API) for direct Lambda invocation from frontend
resource "aws_apigatewayv2_api" "image_api" {
  name          = "${var.project_name}-image-api"
  protocol_type = "HTTP"
  description   = "API for image processing"

  cors_configuration {
    allow_origins = var.allowed_origins
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
  api_id           = aws_apigatewayv2_api.image_api.id
  integration_type = "AWS_PROXY"

  integration_uri    = aws_lambda_function.image_processor.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "process_route" {
  api_id    = aws_apigatewayv2_api.image_api.id
  route_key = "POST /process"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# Permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.image_api.execution_arn}/*/*"
}
