# DynamoDB table to track processed Reddit posts
resource "aws_dynamodb_table" "reddit_processed_posts" {
  name         = local.reddit_processed_posts_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "subreddit"
  range_key    = "processed_at"

  attribute {
    name = "subreddit"
    type = "S"
  }

  attribute {
    name = "processed_at"
    type = "N"
  }

  attribute {
    name = "post_id"
    type = "S"
  }

  # Global Secondary Index to query by post_id
  global_secondary_index {
    name            = "post-id-index"
    hash_key        = "post_id"
    projection_type = "ALL"
  }

  # TTL to automatically delete old entries after 7 days
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-reddit-processed-posts"
    Environment = var.environment
  }
}

# DynamoDB table to track processed image content hashes (for duplicate detection)
resource "aws_dynamodb_table" "reddit_processed_images" {
  name         = local.reddit_processed_images_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "content_hash"

  attribute {
    name = "content_hash"
    type = "S"
  }

  # TTL to automatically delete old entries after 30 days
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-reddit-processed-images"
    Environment = var.environment
    Purpose     = "Reddit image duplicate detection"
  }
}

# DynamoDB table to track processed URLs (for duplicate detection)
resource "aws_dynamodb_table" "reddit_processed_urls" {
  name         = local.reddit_processed_urls_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "url_hash"

  attribute {
    name = "url_hash"
    type = "S"
  }

  # TTL to automatically delete old entries after 7 days
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-reddit-processed-urls"
    Environment = var.environment
    Purpose     = "Reddit URL duplicate detection"
  }
}

# DynamoDB table for performance metrics with TTL
resource "aws_dynamodb_table" "performance_metrics" {
  name         = local.performance_metrics_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "function_name"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "GSI1PK"
    type = "S"
  }

  # Global Secondary Index for querying by function name and timestamp
  global_secondary_index {
    name            = "function-timestamp-index"
    hash_key        = "function_name"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # GSI for querying all metrics by time
  global_secondary_index {
    name            = "metrics-by-time-index"
    hash_key        = "GSI1PK"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # TTL to automatically delete old entries after 7 days
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-performance-metrics"
    Environment = var.environment
    Purpose     = "Lambda function performance monitoring"
  }
}

# IAM policy for DynamoDB access
resource "aws_iam_policy" "reddit_dynamodb_policy" {
  name = "${var.project_name}-reddit-dynamodb-policy-${var.environment}-${local.random_suffix}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.reddit_processed_posts.arn,
          "${aws_dynamodb_table.reddit_processed_posts.arn}/index/*",
          aws_dynamodb_table.reddit_processed_images.arn,
          aws_dynamodb_table.reddit_processed_urls.arn,
          data.terraform_remote_state.data.outputs.translations_table_arn,
          "${data.terraform_remote_state.data.outputs.translations_table_arn}/index/*"
        ]
      }
    ]
  })
}

# IAM policy for performance metrics DynamoDB access
resource "aws_iam_policy" "performance_metrics_dynamodb_policy" {
  name = "${var.project_name}-performance-metrics-dynamodb-policy-${var.environment}-${local.random_suffix}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.performance_metrics.arn,
          "${aws_dynamodb_table.performance_metrics.arn}/index/*"
        ]
      }
    ]
  })
}
