provider "aws" {
  region = var.region
}

# User Management Module
module "user_management" {
  source = "../../modules/user_management"

  project_name               = var.project_name
  s3_bucket_arn              = module.image_translation.s3_bucket_arn
  cognito_triggers_file_path = var.cognito_triggers_file_path
}

# Image Translation Module
module "image_translation" {
  source = "../../modules/image_translation"

  project_name       = var.project_name
  s3_bucket_name     = "${var.project_name}-image-storage"
  force_destroy      = true
  enable_versioning  = true
  enable_lifecycle   = true
  table_name         = "${var.project_name}-reddit-state"
  billing_mode       = "PAY_PER_REQUEST"
  allowed_origins    = var.allowed_origins
  additional_origins = var.additional_origins
}

# API Module
module "api" {
  source = "../../modules/api"

  project_name                         = var.project_name
  allowed_origins                      = var.allowed_origins
  additional_origins                   = var.additional_origins
  image_processor_lambda_invoke_arn    = module.image_translation.image_processor_lambda_invoke_arn
  image_processor_lambda_function_name = module.image_translation.image_processor_lambda_function_name
}

# Frontend Hosting Module
module "frontend_hosting" {
  source = "../../modules/frontend_hosting"

  bucket_name       = "${var.project_name}-frontend-hosting"
  environment       = "dev"
  frontend_path     = var.frontend_path
  config_file_ready = true # Assuming config.js is generated before apply
}
