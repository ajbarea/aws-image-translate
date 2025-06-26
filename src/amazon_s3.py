"""Amazon S3 utility functions for listing and uploading images.

This module provides helper functions to list image files in an S3 bucket and to upload files or file-like objects to S3.
"""

import boto3
from config import AWS_REGION


def list_images_in_bucket(bucket):
    """List image files in an S3 bucket with supported extensions.

    Args:
        bucket (str): The name of the S3 bucket.

    Returns:
        list: A list of image file keys (str) found in the bucket.

    Raises:
        botocore.exceptions.BotoCoreError: If the AWS SDK encounters a low-level error.
        botocore.exceptions.ClientError: If the S3 API call fails.
    """
    s3 = boto3.client("s3", region_name=AWS_REGION)
    response = s3.list_objects_v2(Bucket=bucket)
    images = [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    return images


def upload_file_to_s3(file_path, bucket_name, object_name=None):
    """Upload a file to an S3 bucket.

    Args:
        file_path (str): Path to the file to upload.
        bucket_name (str): Name of the S3 bucket to upload to.
        object_name (str, optional): S3 object name. If not specified, the file name is used.

    Returns:
        bool: True if the file was uploaded successfully, False otherwise.

    Raises:
        botocore.exceptions.BotoCoreError: If the AWS SDK encounters a low-level error.
        botocore.exceptions.ClientError: If the S3 API call fails.
    """
    if object_name is None:
        object_name = file_path.split("/")[
            -1
        ]  # Use the file name if object_name is not provided

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return False
    return True


def upload_fileobj_to_s3(fileobj, bucket_name, object_name):
    """Upload a file-like object to an S3 bucket.

    Args:
        fileobj (file-like): File-like object to upload.
        bucket_name (str): Name of the S3 bucket to upload to.
        object_name (str): S3 object name.

    Returns:
        bool: True if the file was uploaded successfully, False otherwise.

    Raises:
        botocore.exceptions.BotoCoreError: If the AWS SDK encounters a low-level error.
        botocore.exceptions.ClientError: If the S3 API call fails.
    """
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3_client.upload_fileobj(fileobj, bucket_name, object_name)
    except Exception as e:
        print(f"Error uploading file object to S3: {e}")
        return False
    return True
