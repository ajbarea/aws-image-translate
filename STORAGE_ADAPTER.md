# Storage Adapter - Switch Between AWS S3 and Google Cloud Storage

The AWS Image Translate project now includes a **Storage Adapter** that allows you to temporarily switch from AWS S3 to Google Cloud Storage during development. This is particularly useful when you're hitting AWS free tier limits but want to continue development without changing your core application logic.

## Quick Start

### Switch to Google Cloud Storage (Temporary Development)

1. **Install Google Cloud Storage dependencies:**

   ```bash
   pip install google-cloud-storage
   # OR use the project's optional dependencies
   pip install .[gcs]
   # OR
   python configure_storage.py --install-gcs
   ```

2. **Set up Google Cloud Storage:**

   ```bash
   # Create a GCS bucket (replace with your unique name, or use the default)
   gsutil mb gs://gcloud-image-bucket
   # OR use your own unique bucket name
   gsutil mb gs://your-dev-bucket-name

   # Authenticate with Google Cloud
   gcloud auth application-default login
   ```

3. **Configure the storage adapter:**

   ```bash
   python configure_storage.py --backend gcs --bucket-name gcloud-image-bucket
   ```

4. **Your app now uses Google Cloud Storage!** No code changes needed.

### Switch Back to AWS S3 (Production)

```bash
python configure_storage.py --backend aws
```

## How It Works

The storage adapter provides the same API interface regardless of whether you're using AWS S3 or Google Cloud Storage:

```python
# These functions work with both S3 and GCS
from src.storage_adapter import list_images_in_bucket, upload_file_to_s3, upload_fileobj_to_s3

# List images (works with both backends)
images = list_images_in_bucket("bucket-name")

# Upload file (works with both backends)
success = upload_file_to_s3("local/file.jpg", "bucket-name", "remote/file.jpg")

# Upload file object (works with both backends)
success = upload_fileobj_to_s3(file_object, "bucket-name", "remote/file.jpg")
```

The adapter automatically routes calls to the appropriate backend based on your configuration.

## Configuration

The storage backend is controlled by environment variables in your `.env.local` file:

### AWS S3 (Default)

```bash
STORAGE_BACKEND=aws
```

### Google Cloud Storage

```bash
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=your-gcs-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json  # Optional
```

## Management Commands

### Check Current Status

```bash
python configure_storage.py --status
```

### Get Setup Help

```bash
# AWS setup instructions
python configure_storage.py --setup-help aws

# Google Cloud Storage setup instructions
python configure_storage.py --setup-help gcs
```

### Switch Backends

```bash
# Switch to AWS S3
python configure_storage.py --backend aws

# Switch to Google Cloud Storage
python configure_storage.py --backend gcs --bucket-name your-bucket

# Include service account credentials path
python configure_storage.py --backend gcs --bucket-name your-bucket --credentials /path/to/key.json
```

## Cost Comparison

| Feature | AWS S3 Free Tier | Google Cloud Storage Always Free |
|---------|------------------|-----------------------------------|
| Storage | 5 GB for 12 months | 5 GB regional storage |
| Operations | 20,000 GET, 2,000 PUT | 5,000 Class A, 50,000 Class B operations |
| Transfer | 15 GB out per month | 1 GB network egress |

Both provide sufficient resources for development, and switching between them gives you double the free resources!

## Important Notes

1. **Development vs Production**: This adapter is designed for temporary development use. For production, stick with your primary choice (AWS S3 in this case).

2. **AWS AI Services Limitation**: AWS Rekognition, Translate, and Comprehend can only read from AWS S3 buckets. The Google Cloud Storage option is useful for:
   - Storing intermediate files during development
   - File uploads and downloads
   - Testing storage functionality
   - When you need extra storage space during development

   For full AI processing pipeline, you'll need AWS S3.

3. **Data Migration**: The adapter doesn't automatically migrate existing data between storage providers. You'll need to manually transfer files if switching permanently.

4. **Authentication**:
   - AWS S3: Uses your existing AWS credentials
   - GCS: Requires Google Cloud authentication (see setup instructions)

5. **Bucket Names**:
   - AWS S3: Bucket name passed to each function call
   - GCS: Uses the bucket name from `GCS_BUCKET_NAME` environment variable

6. **Regional Considerations**:
   - AWS S3: Bucket region set in `config.py` (`AWS_REGION`)
   - GCS: Buckets are global, but you can specify regions during creation

## Troubleshooting

### "Import Error: google.cloud.storage"

```bash
pip install google-cloud-storage
# OR use project dependencies
pip install .[gcs]
```

### "GCS_BUCKET_NAME environment variable is required"

```bash
python configure_storage.py --backend gcs --bucket-name your-bucket-name
```

### "Storage connectivity check failed"

Check your authentication:

- **AWS**: `aws configure` or verify environment variables
- **GCS**: `gcloud auth application-default login`

### "Permission denied" errors

Ensure your credentials have the necessary permissions:

- **AWS S3**: `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`
- **GCS**: `storage.objects.create`, `storage.objects.get`, `storage.objects.list`

## Example Workflow

```bash
# You're developing and hit AWS free tier limits
python configure_storage.py --status
# Shows: Backend: AWS S3, remaining quota low

# Switch to Google Cloud Storage for continued development
python configure_storage.py --setup-help gcs  # Follow setup instructions
python configure_storage.py --backend gcs --bucket-name gcloud-image-bucket

# Continue development as normal
python main.py  # Works exactly the same!

# When ready for production, switch back
python configure_storage.py --backend aws
```
