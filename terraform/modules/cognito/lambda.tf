# Lambda function for Cognito triggers
resource "aws_lambda_function" "cognito_triggers" {
  filename         = data.archive_file.cognito_triggers_zip.output_path
  function_name    = "${var.project_name}-cognito-triggers"
  role            = aws_iam_role.cognito_triggers_role.arn
  handler         = "cognito_triggers.lambda_handler"
  runtime         = "python3.11"
  timeout         = 30
  source_code_hash = data.archive_file.cognito_triggers_zip.output_base64sha256
}

# Archive the Lambda function code
data "archive_file" "cognito_triggers_zip" {
  type        = "zip"
  source_file = "${path.root}/../lambda/cognito_triggers.py"
  output_path = "${path.module}/cognito_triggers.zip"
}

# IAM role for the Lambda function
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

# IAM policy for Lambda function
resource "aws_iam_role_policy" "cognito_triggers_policy" {
  name = "${var.project_name}-cognito-triggers-policy"
  role = aws_iam_role.cognito_triggers_role.id

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
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Permission for Cognito to invoke the Lambda function
resource "aws_lambda_permission" "cognito_triggers_permission" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cognito_triggers.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.pool.arn
}
