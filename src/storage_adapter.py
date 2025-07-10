"""Storage adapter that provides a unified interface for AWS S3 and Google Cloud Storage.

This module allows seamless switching between AWS S3 and Google Cloud Storage
by providing the same API interface regardless of the backend storage provider.
Switch between providers using the STORAGE_BACKEND environment variable.

Environment Variables:
    STORAGE_BACKEND: 'aws' (default) or 'gcs'
    GCS_BUCKET_NAME: Google Cloud Storage bucket name (when using GCS)
    GOOGLE_APPLICATION_CREDENTIALS: Path to GCS service account JSON file
"""

import os
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

from config import AWS_REGION

# Try to import dependencies but don't fail if they're not available
try:
    import boto3

    # Do not import BaseClient for type annotation, use Any instead
except ImportError:
    boto3 = None  # type: ignore[assignment]

try:
    from google.cloud import storage as gcs
except ImportError:
    gcs = None

# Global variables for lazy initialization
_gcs_client: Optional[Any] = None
_gcs_bucket: Optional[Any] = None
_s3_client: Optional[Any] = None
_last_backend: Optional[str] = None


def _reset_clients() -> None:
    """Reset all cached clients. Used for testing."""
    global _gcs_client, _gcs_bucket, _s3_client, _last_backend
    _gcs_client = None
    _gcs_bucket = None
    _s3_client = None
    _last_backend = None


def _get_storage_backend() -> str:
    """Get the current storage backend from environment variable."""
    global _last_backend
    current_backend = os.getenv("STORAGE_BACKEND", "aws").lower()

    # If backend changed, reset clients
    if _last_backend is not None and _last_backend != current_backend:
        _reset_clients()

    _last_backend = current_backend
    return current_backend


def _get_gcs_client() -> Tuple[Any, Any]:
    """Lazy initialization of Google Cloud Storage client."""
    global _gcs_client, _gcs_bucket

    if _gcs_client is None or _gcs_bucket is None:
        if gcs is None:
            raise ImportError(
                "Google Cloud Storage dependencies not installed. "
                "Run: pip install '.[gcs]'"
            )

        try:
            # Initialize GCP client
            gcs_bucket_name = os.getenv("GCS_BUCKET_NAME")
            if not gcs_bucket_name:
                raise ValueError(
                    "GCS_BUCKET_NAME environment variable is required when using GCS backend"
                )

            _gcs_client = gcs.Client()
            _gcs_bucket = _gcs_client.bucket(gcs_bucket_name)
            print(f"Initialized Google Cloud Storage with bucket: {gcs_bucket_name}")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Cloud Storage: {e}")

    return _gcs_client, _gcs_bucket


def _get_s3_client() -> Any:
    """Lazy initialization of AWS S3 client."""
    global _s3_client

    if _s3_client is None:
        if boto3 is None:
            raise ImportError(
                "AWS SDK dependencies not installed. Run: pip install boto3"
            )
        _s3_client = boto3.client("s3", region_name=AWS_REGION)
        print(f"Using AWS S3 backend in region: {AWS_REGION}")

    return _s3_client


def list_images_in_bucket(bucket: str) -> List[str]:
    """Lists all image files in the specified bucket (S3 or GCS).

    Args:
        bucket (str): The name of the bucket to search. For GCS, this parameter
                     is ignored and the configured GCS_BUCKET_NAME is used.

    Returns:
        List[str]: A list of object keys/names for image files found in the bucket.

    Raises:
        Exception: If there's an error accessing the storage service.
    """
    image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp")

    if _get_storage_backend() == "gcs":
        try:
            _, gcs_bucket = _get_gcs_client()
            blobs = gcs_bucket.list_blobs()
            images = [
                blob.name
                for blob in blobs
                if blob.name and blob.name.lower().endswith(image_extensions)
            ]
            return images
        except Exception as e:
            gcs_bucket_name = os.getenv("GCS_BUCKET_NAME", "unknown")
            print(f"Error listing images in GCS bucket {gcs_bucket_name}: {e}")
            raise
    else:
        # AWS S3 implementation
        try:
            s3_client = _get_s3_client()
            response = s3_client.list_objects_v2(Bucket=bucket)
            images = [
                obj["Key"]
                for obj in response.get("Contents", [])
                if "Key" in obj and obj["Key"].lower().endswith(image_extensions)
            ]
            return images
        except Exception as e:
            print(f"Error listing images in S3 bucket {bucket}: {e}")
            raise


def upload_file_to_s3(
    file_path: str, bucket_name: str, object_name: Optional[str] = None
) -> bool:
    """Uploads a file to the storage bucket (S3 or GCS).

    Args:
        file_path (str): The path to the local file to upload.
        bucket_name (str): The name of the destination bucket. For GCS, this parameter
                          is ignored and the configured GCS_BUCKET_NAME is used.
        object_name (Optional[str]): The desired name for the file in storage.
                                   If not specified, uses the basename of the local file.

    Returns:
        bool: True if the upload was successful, False otherwise.
    """
    if object_name is None:
        object_name = os.path.basename(file_path)

    if _get_storage_backend() == "gcs":
        try:
            _, gcs_bucket = _get_gcs_client()
            blob = gcs_bucket.blob(object_name)
            blob.upload_from_filename(file_path)
            print(f"Successfully uploaded {file_path} to GCS as {object_name}")
            return True
        except Exception as e:
            print(f"Error uploading file to GCS: {e}")
            return False
    else:
        # AWS S3 implementation
        try:
            s3_client = _get_s3_client()
            s3_client.upload_file(file_path, bucket_name, object_name)
            print(
                f"Successfully uploaded {file_path} to S3 bucket {bucket_name} as {object_name}"
            )
            return True
        except Exception as e:
            print(f"Error uploading file to S3: {e}")
            return False


def upload_fileobj_to_s3(
    fileobj: Union[BytesIO, Any], bucket_name: str, object_name: str
) -> bool:
    """Uploads a file-like object to the storage bucket (S3 or GCS).

    Args:
        fileobj (Union[BytesIO, Any]): A file-like object to upload. Must support read() method.
        bucket_name (str): The name of the destination bucket. For GCS, this parameter
                          is ignored and the configured GCS_BUCKET_NAME is used.
        object_name (str): The desired name for the file in storage.

    Returns:
        bool: True if the upload was successful, False otherwise.
    """
    if _get_storage_backend() == "gcs":
        try:
            _, gcs_bucket = _get_gcs_client()
            blob = gcs_bucket.blob(object_name)
            # Reset file pointer to beginning
            if hasattr(fileobj, "seek"):
                fileobj.seek(0)
            blob.upload_from_file(fileobj)
            print(f"Successfully uploaded file object to GCS as {object_name}")
            return True
        except Exception as e:
            print(f"Error uploading file object to GCS: {e}")
            return False
    else:
        # AWS S3 implementation
        try:
            s3_client = _get_s3_client()
            s3_client.upload_fileobj(fileobj, bucket_name, object_name)
            print(
                f"Successfully uploaded file object to S3 bucket {bucket_name} as {object_name}"
            )
            return True
        except Exception as e:
            print(f"Error uploading file object to S3: {e}")
            return False


def get_storage_info() -> Dict[str, str]:
    """Returns information about the current storage configuration.

    Returns:
        Dict[str, str]: Storage configuration details including backend type and bucket info.
    """
    if _get_storage_backend() == "gcs":
        gcs_bucket_name = os.getenv("GCS_BUCKET_NAME", "Not configured")
        return {
            "backend": "Google Cloud Storage",
            "bucket": gcs_bucket_name,
            "region": "N/A (GCS is global)",
        }
    else:
        return {
            "backend": "AWS S3",
            "bucket": "Varies by function call",
            "region": AWS_REGION,
        }


def check_storage_connectivity() -> bool:
    """Checks if the storage backend is accessible and properly configured.

    Returns:
        bool: True if storage is accessible, False otherwise.
    """
    try:
        if _get_storage_backend() == "gcs":
            # Try to check if bucket exists and is accessible
            _, gcs_bucket = _get_gcs_client()
            gcs_bucket.reload()
            gcs_bucket_name = os.getenv("GCS_BUCKET_NAME", "unknown")
            print(f"✓ Google Cloud Storage bucket '{gcs_bucket_name}' is accessible")
            return True
        else:
            # Try to list buckets to verify AWS credentials and connectivity
            s3_client = _get_s3_client()
            s3_client.list_buckets()
            print(f"✓ AWS S3 is accessible in region '{AWS_REGION}'")
            return True
    except Exception as e:
        print(f"✗ Storage connectivity check failed: {e}")
        return False


if __name__ == "__main__":
    # Print current configuration and test connectivity
    info = get_storage_info()
    print(f"Storage Backend: {info['backend']}")
    print(f"Bucket: {info['bucket']}")
    print(f"Region: {info['region']}")
    print()

    # Test connectivity
    if check_storage_connectivity():
        print("Storage backend is ready!")
    else:
        print("Storage backend configuration needs attention.")
