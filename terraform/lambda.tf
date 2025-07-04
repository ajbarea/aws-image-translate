# terraform/lambda.tf

# Image Processor Lambda
data "archive_file" "image_processor_zip" {
  type        = "zip"
  source_dir  = "../lambda"
  output_path = "${path.module}/image_processor.zip"
}

resource "aws_lambda_function" "image_processor" {
  filename         = data.archive_file.image_processor_zip.output_path
  function_name    = "${var.project_name}-image-processor"
  role             = aws_iam_role.image_processor_role.arn
  handler          = "image_processor.lambda_handler"
  runtime          = "python3.11"
  timeout          = 90
  memory_size      = 512
  source_code_hash = data.archive_file.image_processor_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET = aws_s3_bucket.image_storage.bucket
    }
  }

  tags = {
    Name = "${var.project_name}-image-processor"
  }
}

resource "aws_iam_role" "image_processor_role" {
  name = "${var.project_name}-image-processor-role"

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

resource "aws_iam_policy" "image_processor_policy" {
  name        = "${var.project_name}-image-processor-policy"
  description = "Policy for the image processor Lambda function"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${aws_lambda_function.image_processor.function_name}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = [aws_s3_bucket.image_storage.arn, "${aws_s3_bucket.image_storage.arn}/*"]
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

resource "aws_iam_role_policy_attachment" "image_processor_attachment" {
  role       = aws_iam_role.image_processor_role.name
  policy_arn = aws_iam_policy.image_processor_policy.arn
}

# Cognito Triggers Lambda
data "archive_file" "cognito_triggers_zip" {
  type        = "zip"
  source_file = "../lambda/cognito_triggers.py"
  output_path = "${path.module}/cognito_triggers.zip"
}

resource "aws_lambda_function" "cognito_triggers" {
  filename         = data.archive_file.cognito_triggers_zip.output_path
  function_name    = "${var.project_name}-cognito-triggers"
  role             = aws_iam_role.cognito_triggers_role.arn
  handler          = "cognito_triggers.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  source_code_hash = data.archive_file.cognito_triggers_zip.output_base64sha256
}

resource "aws_iam_role" "cognito_triggers_role" {
  name = "${var.project_name}-cognito-triggers-role"

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

resource "aws_iam_role_policy" "cognito_triggers_policy" {
  name = "${var.project_name}-cognito-triggers-policy"
  role = aws_iam_role.cognito_triggers_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_permission" "cognito_triggers_permission" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cognito_triggers.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.pool.arn
}
