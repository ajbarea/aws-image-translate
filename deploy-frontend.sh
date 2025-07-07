#!/bin/bash

# Deploy Frontend Changes Script
echo "🚀 Deploying frontend changes..."

# Navigate to terraform directory
cd terraform

# Update frontend files and config
echo "📦 Updating frontend files..."
terraform apply -target=aws_s3_object.frontend_files -target=aws_s3_object.config_js -auto-approve

# Get CloudFront distribution ID
DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")

if [ ! -z "$DISTRIBUTION_ID" ]; then
    echo "🔄 Creating CloudFront invalidation for distribution: $DISTRIBUTION_ID"
    aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
    echo "✅ CloudFront invalidation created. Changes should be live in 1-2 minutes."
else
    echo "⚠️  Could not get CloudFront distribution ID. You may need to wait for cache to expire."
fi

echo "✅ Frontend deployment complete!"
