# Lambda Deployment Guide

## 🚀 Serverless Image Processing Implementation

Your AWS Image Translation Pipeline now includes a complete serverless image processing setup with AWS Lambda. Here's what has been implemented:

### ✅ What's Included

1. **AWS Lambda Function** (`lambda/image_processor.py`)
   - Detects text in images using AWS Rekognition
   - Identifies the language using AWS Comprehend
   - Translates text to English using AWS Translate
   - Handles both S3 triggers and direct API calls

2. **API Gateway Integration**
   - REST API endpoint for direct frontend calls
   - CORS enabled for web browser access
   - POST `/process` endpoint for image processing

3. **S3 Event Triggers**
   - Automatically processes images uploaded to `uploads/` folder
   - Serverless event-driven architecture

4. **Infrastructure as Code**
   - Complete Terraform modules for Lambda, API Gateway, and IAM roles
   - Proper security policies and permissions

### 🏗️ Architecture Flow

```text
Frontend Upload → S3 Bucket → Lambda Trigger → Image Processing
     ↓              ↓              ↓              ↓
Direct API Call → API Gateway → Lambda Function → AI Services
                                     ↓              ↓
                                Return Results ← Translation
```

### 📋 Deployment Steps

1. **Deploy the infrastructure:**

   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

2. **Get the API Gateway URL:**

   ```bash
   terraform output api_gateway_url
   ```

3. **Update your frontend config:**

   ```bash
   terraform output integration_config
   ```

   Copy the `API_GATEWAY_URL` to your `frontend/js/config.js`

### 🔧 Frontend Integration

Your frontend can now:

1. **Upload images to S3** (automatic processing via S3 triggers)
2. **Call API Gateway directly** for immediate processing
3. **Use Cognito authentication** for secure access

### 💡 Usage Examples

**Direct API Call:**

```javascript
const response = await fetch(AWS_CONFIG.apiGatewayUrl + '/process', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    bucket: 'your-bucket',
    key: 'uploads/image.jpg'
  })
});
const result = await response.json();
console.log(result.translatedText);
```

**S3 Upload (automatic processing):**

```javascript
// Upload triggers Lambda automatically
await s3.upload({
  Bucket: bucketName,
  Key: 'uploads/image.jpg',
  Body: imageFile
}).promise();
```

### 🛡️ Security Features

- ✅ IAM roles with least privilege access
- ✅ CORS properly configured
- ✅ Cognito authentication integration
- ✅ S3 bucket policies for secure access

### 📊 Monitoring

After deployment, you can monitor:

- Lambda function logs in CloudWatch
- API Gateway metrics and logs
- S3 event notifications
- Error rates and performance metrics

### 💰 Cost Optimization

- Lambda runs only when triggered (pay-per-request)
- S3 lifecycle policies for storage optimization
- DynamoDB on-demand pricing
- API Gateway pay-per-call model

Your serverless image processing pipeline is now ready for deployment! 🎉
