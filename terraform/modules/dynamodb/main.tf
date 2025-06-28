# DynamoDB module for Reddit state tracking

resource "aws_dynamodb_table" "reddit_state" {
  name           = var.table_name
  billing_mode   = var.billing_mode
  hash_key       = "subreddit_key"
  
  # Conditional provisioned billing mode settings
  read_capacity  = var.billing_mode == "PROVISIONED" ? 1 : null
  write_capacity = var.billing_mode == "PROVISIONED" ? 1 : null
  
  attribute {
    name = "subreddit_key"
    type = "S"
  }
  
  # Enable point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }
  
  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
  
  tags = {
    Name    = var.table_name
    Purpose = "reddit-state-tracking"
  }
}

# Optional: DynamoDB table for backup/archival
resource "aws_dynamodb_table" "reddit_state_backup" {
  count = var.enable_backup_table ? 1 : 0
  
  name           = "${var.table_name}-backup"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "subreddit_key"
  range_key      = "timestamp"
  
  attribute {
    name = "subreddit_key"
    type = "S"
  }
  
  attribute {
    name = "timestamp"
    type = "S"
  }
  
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  
  tags = {
    Name    = "${var.table_name}-backup"
    Purpose = "reddit-state-backup"
  }
}
