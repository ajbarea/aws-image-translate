# Backend Development Guide

FastAPI backend for AWS Image Translate with Cognito authentication.

## Quick Setup

1. **Create Cognito resources:**

   ```bash
   python setup-cognito.py
   ```

2. **Add the output to `.env.local`:**

   ```env
   # Cognito Configuration
   COGNITO_REGION=us-east-1
   COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
   COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
   COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

3. **Update frontend config:**
   - Edit `frontend/js/config.js` with the values from setup output

4. **Install backend dependencies:**

   ```bash
   pip install .[dev]
   ```

5. **Start the backend:**

   ```bash
   fastapi dev backend/app.py
   ```

## Testing the Backend

1. **Test backend health:**
   Visit: <http://localhost:8000/health>

2. **API Documentation:**
   Visit: <http://localhost:8000/docs>

3. **Test with frontend:**
   - Open `frontend/index.html` with Live Server
   - Register/login with Cognito
   - Upload and process images

## What the setup creates

### setup-cognito.py

- **User Pool**: For user registration/authentication
- **User Pool Client**: Web app client configuration  
- **Identity Pool**: For AWS credential federation

### Backend Features

- **Health Check**: `/health` endpoint
- **Image Processing**: `/process` endpoint for text detection and translation
- **CORS Enabled**: For local frontend development
- **Error Handling**: Proper HTTP status codes and error messages

## Current Architecture

**Note**: Authentication is currently simplified for development. The frontend handles Cognito authentication, but the backend doesn't validate JWT tokens yet.

### Authentication Flow (Frontend Only)

1. User registers/logs in via Cognito User Pool (frontend)
2. Frontend receives JWT access token
3. Frontend manages authenticated state
4. Backend processes all requests (no token validation currently)

## API Endpoints

### `GET /health`

- **Purpose**: Health check
- **Response**: `{"status": "healthy", "service": "aws-image-translate-backend"}`

### `POST /process`

- **Purpose**: Process images for text detection and translation
- **Request Body**:

  ```json
  {
    "bucket": "bucket-name",
    "key": "image-key.jpg", 
    "targetLanguage": "en",
    "detectedText": "optional-existing-text",
    "detectedLanguage": "optional-source-lang"
  }
  ```

- **Response**:

  ```json
  {
    "detectedText": "detected text from image",
    "detectedLanguage": "es",
    "translatedText": "translated text",
    "targetLanguage": "en"
  }
  ```

## Troubleshooting

### "AWS CLI not configured"

```bash
aws configure
# Enter your AWS credentials
```

### "ModuleNotFoundError" for dependencies

```bash
pip install .[dev]
```

### Backend not starting

- Check that you're in the project root directory
- Ensure `.env.local` exists with Cognito configuration
- Verify AWS credentials are configured

### Frontend can't connect to backend

- Ensure backend is running on <http://localhost:8000>
- Check that `frontend/js/config.js` has correct `apiGatewayUrl`
- Verify CORS is enabled in backend

## Development Notes

- **Current Status**: Simplified for development without JWT validation
- **Next Steps**: Add proper JWT authentication validation
- **Production**: Will need full authentication and authorization
