# Variables for DynamoDB module

variable "table_name" {
  description = "Name of the DynamoDB table"
  type        = string
}

variable "enable_backup_table" {
  description = "Whether to create a backup table"
  type        = bool
  default     = false
}

variable "billing_mode" {
  description = "DynamoDB billing mode (PAY_PER_REQUEST or PROVISIONED)"
  type        = string
  default     = "PAY_PER_REQUEST"

  validation {
    condition     = contains(["PAY_PER_REQUEST", "PROVISIONED"], var.billing_mode)
    error_message = "Billing mode must be either PAY_PER_REQUEST or PROVISIONED."
  }
}
