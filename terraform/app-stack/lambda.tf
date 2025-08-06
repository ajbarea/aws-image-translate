# Lambda Functions Configuration
# Reddit Populator Package Preparation
resource "null_resource" "prepare_reddit_populator_package" {
  triggers = {
    # Triggers rebuild when any source files or requirements change
    requirements_hash     = filemd5("../../lambda_functions/requirements.txt")
    populator_hash        = filemd5("../../lambda_functions/reddit_populator_sync.py")
    scraper_hash          = filemd5("../../lambda_functions/reddit_scraper_sync.py")
    realtime_scraper_hash = filemd5("../../lambda_functions/reddit_realtime_scraper.py")
    aws_clients_hash      = filemd5("../../lambda_functions/aws_clients.py")
    prep_script_hash      = filemd5("../../lambda_functions/prepare_reddit_populator.py")
  }

  provisioner "local-exec" {
    command = "python ../../lambda_functions/prepare_reddit_populator.py"
  }
}

# Lambda Function Packaging
data "archive_file" "image_processor_zip" {
  type        = "zip"
  output_path = "${path.module}/image_processor.zip"

  source {
    content  = file("../../lambda_functions/image_processor.py")
    filename = "image_processor.py"
  }
  source {
    content  = file("../../lambda_functions/aws_clients.py")
    filename = "aws_clients.py"
  }
  source {
    content  = file("../../lambda_functions/history_handler.py")
    filename = "history_handler.py"
  }
}

data "archive_file" "gallery_lister_zip" {
  type        = "zip"
  output_path = "${path.module}/gallery_lister.zip"

  source {
    content  = file("../../lambda_functions/gallery_lister.py")
    filename = "gallery_lister.py"
  }
  source {
    content  = file("../../lambda_functions/aws_clients.py")
    filename = "aws_clients.py"
  }
}

data "archive_file" "cognito_triggers_zip" {
  type        = "zip"
  output_path = "${path.module}/cognito_triggers.zip"

  source {
    content  = file("../../lambda_functions/cognito_triggers.py")
    filename = "cognito_triggers.py"
  }
  source {
    content  = file("../../lambda_functions/aws_clients.py")
    filename = "aws_clients.py"
  }
}

data "archive_file" "mmid_populator_zip" {
  type        = "zip"
  output_path = "${path.module}/mmid_populator.zip"

  source {
    content  = file("../../lambda_functions/mmid_populator.py")
    filename = "mmid_populator.py"
  }
  source {
    content  = file("../../lambda_functions/aws_clients.py")
    filename = "aws_clients.py"
  }
  source {
    content  = file("../../lambda_functions/image_processor.py")
    filename = "image_processor.py"
  }
  source {
    content  = file("../../lambda_functions/history_handler.py")
    filename = "history_handler.py"
  }
}

data "archive_file" "user_manager_zip" {
  type        = "zip"
  output_path = "${path.module}/user_manager.zip"

  source {
    content  = file("../../lambda_functions/user_manager.py")
    filename = "user_manager.py"
  }
  source {
    content  = file("../../lambda_functions/aws_clients.py")
    filename = "aws_clients.py"
  }
}

data "archive_file" "history_handler_zip" {
  type        = "zip"
  output_path = "${path.module}/history_handler.zip"

  source {
    content  = file("../../lambda_functions/history_handler.py")
    filename = "history_handler.py"
  }
  source {
    content  = file("../../lambda_functions/aws_clients.py")
    filename = "aws_clients.py"
  }
}

data "archive_file" "performance_handler_zip" {
  type        = "zip"
  output_path = "${path.module}/performance_handler.zip"

  source {
    content  = file("../../lambda_functions/performance_handler.py")
    filename = "performance_handler.py"
  }
  source {
    content  = file("../../lambda_functions/aws_clients.py")
    filename = "aws_clients.py"
  }
}

# Reddit Populator Lambda - requires special packaging with dependencies
resource "aws_lambda_function" "reddit_populator" {
  filename      = "../reddit_populator.zip"
  function_name = "${var.project_name}-reddit-populator-${var.environment}-${local.random_suffix}"
  role          = aws_iam_role.reddit_populator_role.arn
  handler       = "reddit_populator_sync.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512
  source_code_hash = base64sha256(format("%s%s%s%s%s%s",
    null_resource.prepare_reddit_populator_package.triggers.requirements_hash,
    null_resource.prepare_reddit_populator_package.triggers.populator_hash,
    null_resource.prepare_reddit_populator_package.triggers.scraper_hash,
    null_resource.prepare_reddit_populator_package.triggers.realtime_scraper_hash,
    null_resource.prepare_reddit_populator_package.triggers.aws_clients_hash,
    null_resource.prepare_reddit_populator_package.triggers.prep_script_hash
  ))

  depends_on = [null_resource.prepare_reddit_populator_package]

  environment {
    variables = {
      S3_BUCKET                    = aws_s3_bucket.image_storage.bucket
      REDDIT_CLIENT_ID             = local.reddit_client_id
      REDDIT_CLIENT_SECRET         = local.reddit_client_secret
      REDDIT_USER_AGENT            = local.reddit_user_agent
      REDDIT_SUBREDDITS            = join(",", local.reddit_subreddits)
      REDDIT_PROCESSED_POSTS_TABLE = aws_dynamodb_table.reddit_processed_posts.name
      TRANSLATIONS_TABLE           = data.terraform_remote_state.data.outputs.translations_table_name
      PERFORMANCE_TABLE            = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}

# Lambda Function Definitions
resource "aws_lambda_function" "image_processor" {
  filename         = data.archive_file.image_processor_zip.output_path
  function_name    = "${var.project_name}-image-processor-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.image_processor_role.arn
  handler          = "image_processor.lambda_handler"
  runtime          = "python3.11"
  timeout          = 90
  memory_size      = 512
  source_code_hash = data.archive_file.image_processor_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET                 = aws_s3_bucket.image_storage.bucket
      REKOGNITION_ROLE          = aws_iam_role.image_processor_role.arn
      TRANSLATION_HISTORY_TABLE = data.terraform_remote_state.data.outputs.translation_history_table_name
      TRANSLATIONS_TABLE        = data.terraform_remote_state.data.outputs.translations_table_name
      PERFORMANCE_TABLE         = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "cognito_triggers" {
  filename         = data.archive_file.cognito_triggers_zip.output_path
  function_name    = "${var.project_name}-cognito-triggers-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.cognito_triggers_role.arn
  handler          = "cognito_triggers.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  source_code_hash = data.archive_file.cognito_triggers_zip.output_base64sha256

  environment {
    variables = {
      PERFORMANCE_TABLE = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}


resource "aws_lambda_function" "gallery_lister" {
  filename         = data.archive_file.gallery_lister_zip.output_path
  function_name    = "${var.project_name}-gallery-lister-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.gallery_lister_role.arn
  handler          = "gallery_lister.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256
  source_code_hash = data.archive_file.gallery_lister_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET         = aws_s3_bucket.image_storage.bucket
      PERFORMANCE_TABLE = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "mmid_populator" {
  filename         = data.archive_file.mmid_populator_zip.output_path
  function_name    = "${var.project_name}-mmid-populator-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.mmid_populator_role.arn
  handler          = "mmid_populator.lambda_handler"
  runtime          = "python3.11"
  timeout          = 600
  memory_size      = 2048
  source_code_hash = data.archive_file.mmid_populator_zip.output_base64sha256

  environment {
    variables = {
      DEST_BUCKET         = aws_s3_bucket.image_storage.bucket
      LANGUAGES           = var.mmid_languages
      IMAGES_PER_LANGUAGE = var.mmid_images_per_language
      PERFORMANCE_TABLE   = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "user_manager" {
  filename         = data.archive_file.user_manager_zip.output_path
  function_name    = "${var.project_name}-user-manager-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.user_manager_role.arn
  handler          = "user_manager.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256
  source_code_hash = data.archive_file.user_manager_zip.output_base64sha256

  environment {
    variables = {
      USER_POOL_ID      = aws_cognito_user_pool.pool.id
      PERFORMANCE_TABLE = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "history_handler" {
  filename         = data.archive_file.history_handler_zip.output_path
  function_name    = "${var.project_name}-history-handler-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.history_handler_role.arn
  handler          = "history_handler.list_history"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256
  source_code_hash = data.archive_file.history_handler_zip.output_base64sha256

  environment {
    variables = {
      TRANSLATION_HISTORY_TABLE = data.terraform_remote_state.data.outputs.translation_history_table_name
      TRANSLATIONS_TABLE        = data.terraform_remote_state.data.outputs.translations_table_name
      PERFORMANCE_TABLE         = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "history_detail_handler" {
  filename         = data.archive_file.history_handler_zip.output_path
  function_name    = "${var.project_name}-history-detail-handler-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.history_handler_role.arn
  handler          = "history_handler.get_history_item"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256
  source_code_hash = data.archive_file.history_handler_zip.output_base64sha256

  environment {
    variables = {
      TRANSLATION_HISTORY_TABLE = data.terraform_remote_state.data.outputs.translation_history_table_name
      TRANSLATIONS_TABLE        = data.terraform_remote_state.data.outputs.translations_table_name
      PERFORMANCE_TABLE         = aws_dynamodb_table.performance_metrics.name
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "performance_handler" {
  filename         = data.archive_file.performance_handler_zip.output_path
  function_name    = "${var.project_name}-performance-handler-${var.environment}-${local.random_suffix}"
  role             = aws_iam_role.performance_handler_role.arn
  handler          = "performance_handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256
  source_code_hash = data.archive_file.performance_handler_zip.output_base64sha256

  environment {
    variables = {
      PERFORMANCE_TABLE    = aws_dynamodb_table.performance_metrics.name
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.pool.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.client.id
    }
  }
  tags = local.common_tags
}

# Lambda Invocations for Initial Data Population
# Initial gallery population with Reddit data (bulk mode)
resource "aws_lambda_invocation" "reddit_populator_initial" {
  function_name = aws_lambda_function.reddit_populator.function_name
  input = jsonencode({
    images_per_subreddit = 30
    subreddits           = local.reddit_subreddits
    real_time_mode       = false # Use bulk mode for initial population
    use_stream           = false # Don't use streaming for initial population
  })
  depends_on = [aws_lambda_function.reddit_populator]
}

resource "aws_lambda_invocation" "mmid_populator_invoke" {
  function_name = aws_lambda_function.mmid_populator.function_name
  input         = jsonencode({})
  depends_on    = [aws_lambda_function.mmid_populator]
}

# IAM Roles and Policies
resource "aws_iam_role" "image_processor_role" {
  name = "${var.project_name}-image-processor-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "image_processor_policy" {
  name = "${var.project_name}-image-processor-policy-${var.environment}-${local.random_suffix}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${aws_s3_bucket.image_storage.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["rekognition:DetectText", "rekognition:DetectLabels"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["comprehend:DetectDominantLanguage"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["translate:TranslateText"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:Query"]
        Resource = [
          data.terraform_remote_state.data.outputs.translation_history_table_arn,
          data.terraform_remote_state.data.outputs.translations_table_arn,
          "${data.terraform_remote_state.data.outputs.translations_table_arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "image_processor_attachment" {
  role       = aws_iam_role.image_processor_role.name
  policy_arn = aws_iam_policy.image_processor_policy.arn
}

resource "aws_iam_role" "cognito_triggers_role" {
  name = "${var.project_name}-cognito-triggers-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "cognito_triggers_policy" {
  name = "${var.project_name}-cognito-triggers-policy-${var.environment}-${local.random_suffix}"
  role = aws_iam_role.cognito_triggers_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-cognito-triggers:*"
      },
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:AdminGetUser", "cognito-idp:AdminInitiateAuth", "cognito-idp:ListUsers"]
        Resource = aws_cognito_user_pool.pool.arn
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

resource "aws_iam_role" "reddit_populator_role" {
  name = "${var.project_name}-reddit-populator-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "reddit_populator_policy" {
  name = "${var.project_name}-reddit-populator-policy-${var.environment}-${local.random_suffix}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:CopyObject", "s3:ListBucket"]
        Resource = ["${aws_s3_bucket.image_storage.arn}/*", aws_s3_bucket.image_storage.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["rekognition:DetectText"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "reddit_populator_attachment" {
  role       = aws_iam_role.reddit_populator_role.name
  policy_arn = aws_iam_policy.reddit_populator_policy.arn
}

# Reddit Populator DynamoDB permissions
resource "aws_iam_role_policy_attachment" "reddit_populator_dynamodb_attachment" {
  role       = aws_iam_role.reddit_populator_role.name
  policy_arn = aws_iam_policy.reddit_dynamodb_policy.arn
}

resource "aws_iam_role" "gallery_lister_role" {
  name = "${var.project_name}-gallery-lister-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "gallery_lister_policy" {
  name = "${var.project_name}-gallery-lister-policy-${var.environment}-${local.random_suffix}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetObject"]
        Resource = ["${aws_s3_bucket.image_storage.arn}/*", aws_s3_bucket.image_storage.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "gallery_lister_attachment" {
  role       = aws_iam_role.gallery_lister_role.name
  policy_arn = aws_iam_policy.gallery_lister_policy.arn
}

resource "aws_iam_role" "mmid_populator_role" {
  name = "${var.project_name}-mmid-populator-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "mmid_populator_policy" {
  name = "${var.project_name}-mmid-populator-policy-${var.environment}-${local.random_suffix}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["arn:aws:s3:::mmid-pds/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:CopyObject"]
        Resource = ["${aws_s3_bucket.image_storage.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["rekognition:DetectText"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mmid_populator_attachment" {
  role       = aws_iam_role.mmid_populator_role.name
  policy_arn = aws_iam_policy.mmid_populator_policy.arn
}

resource "aws_iam_role" "user_manager_role" {
  name = "${var.project_name}-user-manager-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "user_manager_policy" {
  name = "${var.project_name}-user-manager-policy-${var.environment}-${local.random_suffix}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      },
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminUpdateUserAttributes",
          "cognito-idp:AdminDeleteUserAttributes",
          "cognito-idp:AdminSetUserPassword",
          "cognito-idp:AdminInitiateAuth"
        ]
        Resource = aws_cognito_user_pool.pool.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "user_manager_attachment" {
  role       = aws_iam_role.user_manager_role.name
  policy_arn = aws_iam_policy.user_manager_policy.arn
}

resource "aws_iam_role" "history_handler_role" {
  name = "${var.project_name}-history-handler-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "history_handler_policy" {
  name = "${var.project_name}-history-handler-policy-${var.environment}-${local.random_suffix}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem"
        ]
        Resource = [
          data.terraform_remote_state.data.outputs.translation_history_table_arn,
          data.terraform_remote_state.data.outputs.translations_table_arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "history_handler_attachment" {
  role       = aws_iam_role.history_handler_role.name
  policy_arn = aws_iam_policy.history_handler_policy.arn
}

resource "aws_iam_role" "performance_handler_role" {
  name = "${var.project_name}-performance-handler-role-${var.environment}-${local.random_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "performance_handler_policy" {
  name = "${var.project_name}-performance-handler-policy-${var.environment}-${local.random_suffix}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:GetItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = [
          aws_dynamodb_table.performance_metrics.arn,
          "${aws_dynamodb_table.performance_metrics.arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "performance_handler_attachment" {
  role       = aws_iam_role.performance_handler_role.name
  policy_arn = aws_iam_policy.performance_handler_policy.arn
}

# Performance metrics DynamoDB policy attachments for all Lambda functions
resource "aws_iam_role_policy_attachment" "image_processor_performance_attachment" {
  role       = aws_iam_role.image_processor_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}

resource "aws_iam_role_policy_attachment" "gallery_lister_performance_attachment" {
  role       = aws_iam_role.gallery_lister_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}

resource "aws_iam_role_policy_attachment" "user_manager_performance_attachment" {
  role       = aws_iam_role.user_manager_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}

resource "aws_iam_role_policy_attachment" "history_handler_performance_attachment" {
  role       = aws_iam_role.history_handler_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}

resource "aws_iam_role_policy_attachment" "reddit_populator_performance_attachment" {
  role       = aws_iam_role.reddit_populator_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}

resource "aws_iam_role_policy_attachment" "mmid_populator_performance_attachment" {
  role       = aws_iam_role.mmid_populator_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}

resource "aws_iam_role_policy_attachment" "cognito_triggers_performance_attachment" {
  role       = aws_iam_role.cognito_triggers_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}

resource "aws_iam_role_policy_attachment" "performance_handler_performance_attachment" {
  role       = aws_iam_role.performance_handler_role.name
  policy_arn = aws_iam_policy.performance_metrics_dynamodb_policy.arn
}
