# Outputs for DynamoDB module

output "table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.reddit_state.name
}

output "table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.reddit_state.arn
}

output "table_id" {
  description = "ID of the DynamoDB table"
  value       = aws_dynamodb_table.reddit_state.id
}

output "backup_table_name" {
  description = "Name of the backup DynamoDB table"
  value       = var.enable_backup_table ? aws_dynamodb_table.reddit_state_backup[0].name : null
}

output "backup_table_arn" {
  description = "ARN of the backup DynamoDB table"
  value       = var.enable_backup_table ? aws_dynamodb_table.reddit_state_backup[0].arn : null
}
