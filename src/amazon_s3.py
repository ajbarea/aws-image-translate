"""Interfaces with Amazon S3 for image storage and management.

This module provides utilities for interacting with Amazon S3 buckets, including
listing images, uploading files, and managing file objects. It supports common
image formats and provides error handling for S3 operations.
"""

from typing import Any, List, Optional

import boto3

from config import AWS_REGION


def list_images_in_bucket(bucket: str) -> List[str]:
    """Lists all image files in the specified S3 bucket.

    Searches the specified bucket for files with common image extensions
    (.png, .jpg, .jpeg) and returns their keys.

    Args:
        bucket (str): The name of the S3 bucket to search.

    Returns:
        List[str]: A list of S3 object keys (paths) for image files found in the bucket.
            Returns an empty list if no images are found or if the bucket is empty.

    Raises:
        botocore.exceptions.BotoCoreError: If there's an AWS service error.
        botocore.exceptions.ClientError: If there's an error accessing the bucket.
    """
    s3 = boto3.client("s3", region_name=AWS_REGION)
    response = s3.list_objects_v2(Bucket=bucket)
    images = [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    return images


def upload_file_to_s3(
    file_path: str, bucket_name: str, object_name: Optional[str] = None
) -> bool:
    """Uploads a file from the local filesystem to an S3 bucket.

    Args:
        file_path (str): The path to the local file to upload.
        bucket_name (str): The name of the destination S3 bucket.
        object_name (Optional[str]): The desired name (key) for the file in S3.
            If not specified, uses the basename of the local file.

    Returns:
        bool: True if the upload was successful, False otherwise.

    Raises:
        Exception: Logs any errors during upload but does not re-raise them.
    """
    if object_name is None:
        object_name = file_path.split("/")[-1]
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return False
    return True


def upload_fileobj_to_s3(fileobj: Any, bucket_name: str, object_name: str) -> bool:
    """Uploads a file-like object to an S3 bucket.

    This function is particularly useful for uploading in-memory file objects
    or streams without first saving them to disk.

    Args:
        fileobj (Any): A file-like object to upload. Must support read() method.
        bucket_name (str): The name of the destination S3 bucket.
        object_name (str): The desired name (key) for the file in S3.

    Returns:
        bool: True if the upload was successful, False otherwise.

    Raises:
        Exception: Logs any errors during upload but does not re-raise them.
    """
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3_client.upload_fileobj(fileobj, bucket_name, object_name)
    except Exception as e:
        print(f"Error uploading file object to S3: {e}")
        return False
    return True
