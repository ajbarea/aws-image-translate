variable "project_name" {
  description = "Name of the project for resource tagging"
  type        = string
  default     = "lenslate"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}
