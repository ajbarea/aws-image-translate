# terraform/locals.tf

locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
  }

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
}
