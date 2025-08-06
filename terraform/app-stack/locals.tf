locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
  }

  # Generate a random suffix to ensure globally unique names for resources
  random_suffix = random_id.this.hex

  # Use random_id for bucket uniqueness - this is managed by Terraform
  # and ensures each deployment gets unique S3 bucket names
  s3_bucket_name                 = "${var.project_name}-image-storage-${var.environment}-${local.random_suffix}"
  frontend_bucket_name           = "${var.project_name}-frontend-hosting-${var.environment}-${local.random_suffix}"
  reddit_processed_posts_name    = "${var.project_name}-reddit-processed-posts-${var.environment}-${local.random_suffix}"
  reddit_processed_images_name   = "${var.project_name}-reddit-processed-images-${var.environment}-${local.random_suffix}"
  reddit_processed_urls_name     = "${var.project_name}-reddit-processed-urls-${var.environment}-${local.random_suffix}"
  performance_metrics_table_name = "${var.project_name}-performance-metrics-${var.environment}-${local.random_suffix}"

  all_frontend_files = fileset(var.frontend_path, "**/*")
  frontend_files     = [for f in local.all_frontend_files : f if f != "js/config.js"]

  mime_types = {
    "html" = "text/html"
    "css"  = "text/css"
    "js"   = "application/javascript"
    "png"  = "image/png"
    "jpg"  = "image/jpeg"
    "jpeg" = "image/jpeg"
    "gif"  = "image/gif"
    "ico"  = "image/x-icon"
  }

  # Read and parse .env.local file for environment variables
  env_file_content = fileexists("../.env.local") ? file("../.env.local") : ""
  env_vars = {
    for line in split("\n", local.env_file_content) :
    split("=", line)[0] => join("=", slice(split("=", line), 1, length(split("=", line))))
    if length(split("=", line)) >= 2 && !startswith(trimspace(line), "#") && trimspace(line) != ""
  }

  # Extract specific values from .env.local for use in resources
  reddit_client_id      = lookup(local.env_vars, "REDDIT_CLIENT_ID", var.reddit_client_id)
  reddit_client_secret  = lookup(local.env_vars, "REDDIT_CLIENT_SECRET", var.reddit_client_secret)
  reddit_user_agent     = lookup(local.env_vars, "REDDIT_USER_AGENT", var.reddit_user_agent)
  reddit_subreddits     = split(",", lookup(local.env_vars, "REDDIT_SUBREDDITS", "translator"))
  cognito_region        = lookup(local.env_vars, "COGNITO_REGION", var.region)
  github_connection_arn = var.github_connection_arn
}
