variable "project_name" {
  description = "The name of the project, used as a prefix for resources."
  type        = string
  default     = "aws-image-translate-dev"
}

variable "region" {
  description = "The AWS region to deploy resources into."
  type        = string
  default     = "us-east-1"
}

variable "allowed_origins" {
  description = "A list of allowed origins for CORS configuration."
  type        = list(string)
  default     = ["http://localhost:8080"]
}

variable "additional_origins" {
  description = "Additional allowed origins for CORS configuration, typically for dynamic environments."
  type        = list(string)
  default     = []
}

variable "frontend_path" {
  description = "The path to the frontend build directory."
  type        = string
}

variable "lambda_dir_path" {
  description = "The absolute path to the lambda code directory."
  type        = string
  default     = "C:/ajsoftworks/aws-image-translate/lambda"
}

variable "cognito_triggers_file_path" {
  description = "The absolute path to the cognito triggers lambda file."
  type        = string
  default     = "C:/ajsoftworks/aws-image-translate/lambda/cognito_triggers.py"
}
