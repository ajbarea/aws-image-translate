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

    # List API Gateways
    echo -e "\n--- API Gateway REST APIs ---"
    aws apigateway get-rest-apis --region us-east-1 || echo "Failed to list API Gateway REST APIs"

    # List API Gateway v2 (HTTP APIs)
    echo -e "\n--- API Gateway v2 (HTTP APIs) ---"
    aws apigatewayv2 get-apis --region us-east-1 || echo "Failed to list API Gateway v2 APIs"

    # List CodePipelines
    echo -e "\n--- CodePipelines ---"
    aws codepipeline list-pipelines --region us-east-1 || echo "Failed to list CodePipelines"

    # List VPCs
    echo -e "\n--- VPCs ---"
    aws ec2 describe-vpcs --region us-east-1 || echo "Failed to list VPCs"

    # List CloudWatch Alarms
    echo -e "\n--- CloudWatch Alarms ---"
    aws cloudwatch describe-alarms --region us-east-1 || echo "Failed to list CloudWatch alarms"

    # List CloudWatch Log Groups
    echo -e "\n--- CloudWatch Log Groups ---"
    aws logs describe-log-groups --region us-east-1 || echo "Failed to list CloudWatch log groups"

    # List CloudWatch Dashboards
    echo -e "\n--- CloudWatch Dashboards ---"
    aws cloudwatch list-dashboards --region us-east-1 || echo "Failed to list CloudWatch dashboards"

    # List CloudWatch Custom Metrics
    echo -e "\n--- CloudWatch Custom Metrics ---"
    aws cloudwatch list-metrics --region us-east-1 --namespace "AWS/Custom" || echo "No custom metrics found or failed to list"

    # List CloudWatch Insights Queries (can be costly)
    echo -e "\n--- CloudWatch Insights Queries ---"
    aws logs describe-queries --region us-east-1 || echo "Failed to list CloudWatch Insights queries"

    # List RDS Instances
    echo -e "\n--- RDS Instances ---"
    aws rds describe-db-instances --region us-east-1 || echo "Failed to list RDS instances"

    echo -e "\n--- ✅ All checks completed! ---"
}

# Run the function
check_aws_resources
