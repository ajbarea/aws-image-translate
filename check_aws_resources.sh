#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to check AWS resources
check_aws_resources() {
    echo "--- Checking AWS Resources ---"

    # List DynamoDB Tables
    echo -e "\n--- DynamoDB Tables ---"
    aws dynamodb list-tables --region us-east-1 || echo "Failed to list DynamoDB tables"

    # List S3 Buckets
    echo -e "\n--- S3 Buckets ---"
    aws s3 ls || echo "Failed to list S3 buckets"

    # List EC2 Instances
    echo -e "\n--- EC2 Instances ---"
    aws ec2 describe-instances --region us-east-1 || echo "Failed to list EC2 instances"

    # List Lambda FunctionNames
    echo -e "\n--- Lambda FunctionNames ---"
    aws lambda list-functions --query 'Functions[*].FunctionName' --output text --region us-east-1 || echo "Failed to list Lambda FunctionNames"

    # List CloudFormation Stacks
    echo -e "\n--- CloudFormation Stacks ---"
    aws cloudformation describe-stacks --region us-east-1 || echo "Failed to list CloudFormation stacks"

    # List IAM RoleNames
    echo -e "\n--- IAM RoleNames ---"
    aws iam list-roles --query 'Roles[*].RoleName' --output text || echo "Failed to list IAM RoleNames"

    # List CloudFront Distributions
    echo -e "\n--- CloudFront Distributions ---"
    aws cloudfront list-distributions || echo "Failed to list CloudFront distributions"

    # List RDS Instances
    echo -e "\n--- RDS Instances ---"
    aws rds describe-db-instances --region us-east-1 || echo "Failed to list RDS instances"

    echo -e "\n--- ✅ All checks completed! ---"
}

# Run the function
check_aws_resources
