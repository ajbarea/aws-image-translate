output "translations_table_name" {
  description = "The name of the translations DynamoDB table"
  value       = aws_dynamodb_table.translations.name
}

output "translation_history_table_name" {
  description = "The name of the history DynamoDB table"
  value       = aws_dynamodb_table.translation_history.name
}

output "translations_table_arn" {
  description = "The ARN of the translations DynamoDB table"
  value       = aws_dynamodb_table.translations.arn
}

output "translation_history_table_arn" {
  description = "The ARN of the history DynamoDB table"
  value       = aws_dynamodb_table.translation_history.arn
}
