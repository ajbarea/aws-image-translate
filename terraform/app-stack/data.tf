// Terraform configuration for the app stack
data "terraform_remote_state" "data" {
  backend = "s3"

  config = {
    bucket = var.data_stack_state_bucket
    key    = "data-stack/terraform.tfstate"
    region = "us-east-1"
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
