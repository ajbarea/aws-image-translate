terraform {
  required_version = ">= 1.8.0"

  backend "s3" {
    # Backend configuration will be updated dynamically by deploy.py
    # with unique resource names for developer isolation
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.2.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }
  }
}

# Generate unique suffix for all resources
resource "random_id" "this" {
  byte_length = 4
}

# Automatically generate terraform.tfvars from .env.local
resource "null_resource" "generate_tfvars" {
  triggers = {
    # Re-run if .env.local changes or env_to_tfvars.py script changes
    env_file_hash = fileexists("../.env.local") ? filemd5("../.env.local") : ""
    script_hash   = filemd5("env_to_tfvars.py")
  }

  provisioner "local-exec" {
    command     = "python env_to_tfvars.py"
    working_dir = path.module
  }

  # Ensure this runs before anything that might need the variables
  lifecycle {
    create_before_destroy = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
