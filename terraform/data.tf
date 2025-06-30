# Data sources for the AWS Image Translation infrastructure

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Get current AWS region
data "aws_region" "current" {}

# Get AWS availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Example: Get existing VPC if you need to deploy into specific networking
# data "aws_vpc" "default" {
#   default = true
# }

# Example: Get latest Amazon Linux 2 AMI
# data "aws_ami" "amazon_linux" {
#   most_recent = true
#   owners      = ["amazon"]
#
#   filter {
#     name   = "name"
#     values = ["amzn2-ami-hvm-*-x86_64-gp2"]
#   }
# }
