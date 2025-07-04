# Frontend Deployment Guide

This guide explains how to deploy and configure the frontend application for AWS Image Translate.

## Prerequisites

1. **Deploy the Terraform infrastructure first** - See [terraform/README.md](../terraform/README.md)
2. **Python 3.8+** for running deployment scripts (actively tested with Python 3.13.2)
3. **AWS CLI configured** with appropriate credentials
4. **Note down the following values from Terraform output:**
   - User Pool ID
   - User Pool Client ID
   - Identity Pool ID
   - S3 Bucket Name
   - AWS Region

## Configuration

1. **Create the configuration file**:

   ```bash
   cd frontend/js
   cp config.js.example config.js
   ```

2. **Get configuration values from Terraform:**

   ```bash
   cd ../../terraform
   terraform output
   # or for specific values:
   terraform output integration_config
   ```

3. **Update `frontend/js/config.js`** with the actual values from Terraform output:

   ```javascript
   const AWS_CONFIG = {
       region: 'us-east-1',
       userPoolId: 'us-east-1_XXXXXXXXX',
       userPoolWebClientId: 'XXXXXXXXXX',
       identityPoolId: 'us-east-1:XXXXXX',
       bucketName: 'your-bucket-name'
   };
   ```

## Testing

1. Create a user in the Cognito User Pool:

   ```bash
   aws cognito-idp sign-up \
     --client-id YOUR_CLIENT_ID \
     --username test@example.com \
     --password "YourPassword123!" \
     --user-attributes Name=email,Value=test@example.com
   ```

2. Confirm the user:

   ```bash
   aws cognito-idp admin-confirm-sign-up \
     --user-pool-id YOUR_USER_POOL_ID \
     --username test@example.com
   ```

## Deployment

You can deploy this frontend in several ways:

### 1. S3 Static Website Hosting (Recommended)

```bash
# Sync to S3 bucket (replace with your bucket name)
aws s3 sync . s3://YOUR_BUCKET_NAME/frontend/ --exclude "*.md"

# Enable static website hosting
aws s3 website s3://YOUR_BUCKET_NAME --index-document index.html
```

### 2. Local Development Server

```bash
# Simple Python server
python -m http.server 8000

# Or using Node.js
npx http-server -p 8000
```

### 3. Static Hosting Services

- **Netlify**: Drag and drop the frontend folder
- **Vercel**: Connect your GitHub repository

## Security and Best Practices

### Production Deployment Considerations

1. **CORS Configuration**: In production, update CORS settings in Terraform to restrict `allowed_origins` to your specific domain
2. **HTTPS**: Always enable HTTPS for production deployments to protect authentication tokens
3. **Token Management**: Consider implementing refresh token handling for better security
4. **Error Handling**: Add comprehensive error handling for authentication failures
5. **Environment Variables**: Never commit actual API keys or credentials to version control

### Cost Optimization

- Use S3 static website hosting for cost-effective deployment
- Enable S3 lifecycle policies to automatically transition old objects to cheaper storage classes
- Monitor AWS costs through CloudWatch and set up billing alerts
- Consider using CloudFront CDN for global content delivery and cost optimization

## Integration Notes

The frontend works in conjunction with:

- **AWS Cognito**: User authentication and authorization
- **AWS S3**: Image storage and retrieval
- **Backend Processing**: Connects to the main Python pipeline for image processing
- **Terraform Infrastructure**: All AWS resources are provisioned via Infrastructure as Code

For a complete setup, ensure all components are properly configured and deployed following the main project documentation.
