# terraform/main.tf
# Updated on July 4, 2025 to trigger Terraform Cloud run

provider "aws" {
  region = var.region
}
