# Data sources for the AWS Image Translation infrastructure

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Get current AWS region
data "aws_region" "current" {}

# Get AWS availability zones
data "aws_availability_zones" "available" {
  state = "available"
}
