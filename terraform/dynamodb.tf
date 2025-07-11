# terraform/dynamodb.tf

resource "aws_dynamodb_table" "state_table" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "subreddit_key"

  attribute {
    name = "subreddit_key"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = local.common_tags
}
