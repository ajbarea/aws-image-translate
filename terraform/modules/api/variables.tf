variable "project_name" {
  description = "The name of the project, used as a prefix for resources."
  type        = string
}

variable "allowed_origins" {
  description = "A list of allowed origins for CORS configuration."
  type        = list(string)
  default     = []
}

variable "additional_origins" {
  description = "Additional allowed origins for CORS configuration, typically for dynamic environments."
  type        = list(string)
  default     = []
}

variable "image_processor_lambda_invoke_arn" {
  description = "The invoke ARN of the image processor Lambda function."
  type        = string
}

variable "image_processor_lambda_function_name" {
  description = "The name of the image processor Lambda function."
  type        = string
}
