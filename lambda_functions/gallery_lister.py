import json
import os
import time
from typing import Any, Dict, List

from aws_clients import get_s3_client, performance_monitor
from botocore.exceptions import ClientError


def create_cors_headers() -> Dict[str, str]:
    """Create CORS headers for the API response"""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
    }


def create_error_response(status_code: int, error_message: str) -> Dict[str, Any]:
    """Create a standardized error response"""
    return {
        "statusCode": status_code,
        "headers": create_cors_headers(),
        "body": json.dumps({"error": error_message}),
    }


def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized success response"""
    return {
        "statusCode": 200,
        "headers": create_cors_headers(),
        "body": json.dumps(data),
    }


def list_images_from_s3(bucket: str, prefix: str = "reddit/") -> List[Dict[str, str]]:
    """
    Lists all images from an S3 bucket under a specified prefix

    Args:
        bucket: The S3 bucket name
        prefix: The prefix to filter images by

    Returns:
        A list of dictionaries, each representing an image with a presigned URL
    """
    images = []
    start_time = time.time()

    try:
        s3_client = get_s3_client()
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

        for page in page_iterator:
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    image_extensions = (
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".bmp",
                        ".webp",
                    )
                    if key.lower().endswith(image_extensions):
                        presigned_url = s3_client.generate_presigned_url(
                            "get_object",
                            Params={"Bucket": bucket, "Key": key},
                            ExpiresIn=3600,
                        )
                        filename = key.split("/")[-1]
                        alt_text = (
                            filename.replace("_", " ")
                            .replace("-", " ")
                            .replace(".", " ")
                        )

                        # Get the last modified timestamp for sorting
                        last_modified = obj.get("LastModified")
                        timestamp = last_modified.timestamp() if last_modified else 0

                        images.append(
                            {
                                "id": len(images) + 1,
                                "src": presigned_url,
                                "alt": alt_text,
                                "key": key,
                                "filename": filename,
                                "timestamp": timestamp,
                                "lastModified": (
                                    last_modified.isoformat() if last_modified else None
                                ),
                            }
                        )

        # Sort images by timestamp (newest first)
        images.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        # Re-assign IDs after sorting
        for i, image in enumerate(images):
            image["id"] = i + 1

        duration = time.time() - start_time
        performance_monitor.record_operation("s3_list_objects", duration, True)
        print(
            f"Found {len(images)} images in bucket {bucket} under prefix {prefix} (sorted by newest first)"
        )
        return images

    except ClientError as e:
        duration = time.time() - start_time
        performance_monitor.record_operation("s3_list_objects", duration, False)
        print(f"Error listing objects from S3: {e}")
        raise e


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to list all images from the S3 bucket
    Returns a list of images with presigned URLs for frontend display
    """
    try:
        if event.get("httpMethod") == "OPTIONS":
            return create_success_response({"message": "CORS preflight successful"})

        bucket_name = os.environ.get("S3_BUCKET", "lenslate-image-storage")
        images = []
        prefixes = ["reddit/", "mmid/"]

        for p in prefixes:
            try:
                images.extend(list_images_from_s3(bucket_name, p))
            except Exception as e:
                print(f"[WARNING] Failed to list images for prefix {p}: {e}")

        # Sort all images by timestamp (newest first) across all prefixes
        images.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        # Re-assign IDs after final sorting
        for i, image in enumerate(images):
            image["id"] = i + 1

        print(f"Final gallery: {len(images)} images sorted by newest first")

        performance_monitor.persist_metrics()
        return create_success_response(
            {
                "images": images,
                "count": len(images),
                "bucket": bucket_name,
                "prefix": "reddit/",
                "performanceMetrics": performance_monitor.get_metrics(),
            }
        )

    except ClientError as e:
        print(f"AWS Client Error: {e}")
        performance_monitor.persist_metrics()
        return create_error_response(500, f"AWS Error: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        performance_monitor.persist_metrics()
        return create_error_response(500, f"Internal server error: {str(e)}")
