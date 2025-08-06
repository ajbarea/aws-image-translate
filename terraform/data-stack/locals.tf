locals {
  # Generate a random suffix to ensure globally unique names for resources
  random_suffix = random_id.this.hex

  # Generate unique names for data stack resources
  translation_history_table_name = "${var.project_name}-translation-history-${var.environment}-${local.random_suffix}"
  translations_table_name        = "${var.project_name}-translations-${var.environment}-${local.random_suffix}"

  # Backend resources also need unique names
  terraform_state_bucket_name = "${var.project_name}-terraform-state-${var.environment}-${local.random_suffix}"
  terraform_lock_table_name   = "${var.project_name}-terraform-lock-${var.environment}-${local.random_suffix}"
}
