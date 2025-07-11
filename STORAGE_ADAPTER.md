# Storage Adapter - Detailed Configuration Guide

> **Note**: For a quick overview, see the [Storage Backend Management section](README.md#-storage-backend-management) in the main README.

The AWS Image Translate project includes a **Storage Adapter** that allows seamless switching between AWS S3 and Google Cloud Storage. This detailed guide covers advanced configuration options and troubleshooting.

## Quick Reference

```bash
# Check current backend
python configure_storage.py --status

# Switch to Google Cloud Storage
python configure_storage.py --backend gcs --bucket-name gcloud-image-bucket

# Switch back to AWS S3
python configure_storage.py --backend aws
```

## Advanced Configuration

### Environment Variables

Configure storage backend via `.env.local`:

**AWS S3 (Default):**

```bash
STORAGE_BACKEND=aws
```

**Google Cloud Storage:**

```bash
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=your-gcs-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json  # Optional
```

### CLI Command Reference

```bash
# Status and help
python configure_storage.py --status
python configure_storage.py --setup-help [aws|gcs]

# Backend switching
python configure_storage.py --backend aws
python configure_storage.py --backend gcs --bucket-name your-bucket
python configure_storage.py --backend gcs --bucket-name your-bucket --credentials /path/to/key.json

# Installation
python configure_storage.py --install-gcs
```

## Cost Comparison & Use Cases

| Feature | AWS S3 Free Tier | Google Cloud Storage Always Free |
|---------|------------------|-----------------------------------|
| Storage | 5 GB for 12 months | 5 GB regional storage |
| Operations | 20,000 GET, 2,000 PUT | 5,000 Class A, 50,000 Class B operations |
| Transfer | 15 GB out per month | 1 GB network egress |

**When to use each:**

- **AWS S3**: Production deployments, full AI pipeline (Rekognition, Translate, Comprehend)
- **GCS**: Development when hitting AWS limits, additional free storage capacity
- **Both**: Maximize free tier resources (~10 GB total storage)

## Important Limitations

**AWS AI Services Requirement**: AWS Rekognition, Translate, and Comprehend can only read from AWS S3 buckets. Use GCS for:

- Development file storage when hitting AWS limits
- File uploads/downloads testing
- Additional storage capacity during development

**For full AI processing pipeline, AWS S3 is required.**

**Data Migration**: The adapter doesn't automatically migrate data between providers. Manual transfer required for permanent switches.

**Authentication Requirements**:

- **AWS S3**: Uses existing AWS credentials
- **GCS**: Requires Google Cloud authentication (see README troubleshooting section)

## API Interface

The storage adapter provides a unified API regardless of backend:

```python
from src.storage_adapter import list_images_in_bucket, upload_file_to_s3, upload_fileobj_to_s3

# These functions work with both S3 and GCS
images = list_images_in_bucket("bucket-name")
success = upload_file_to_s3("local/file.jpg", "bucket-name", "remote/file.jpg")
success = upload_fileobj_to_s3(file_object, "bucket-name", "remote/file.jpg")
```

## Troubleshooting

For detailed troubleshooting (authentication, permissions, billing, etc.), see the [README troubleshooting section](README.md#-troubleshooting-storage-issues).

**Quick fixes:**

```bash
# Install GCS dependencies
python configure_storage.py --install-gcs

# Test current configuration
python configure_storage.py --test

# Get setup help
python configure_storage.py --setup-help gcs
```
