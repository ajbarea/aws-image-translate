"""Interfaces with Amazon Rekognition for text detection in images stored in S3.

This module provides functionality to detect and extract text from images stored in
Amazon S3 buckets using the AWS Rekognition service.
"""

import boto3

from config import AWS_REGION


def detect_text_from_s3(photo: str, bucket: str) -> str:
    """Detects and extracts text from an image stored in an S3 bucket.

    Uses Amazon Rekognition's text detection capability to identify and extract
    text content from images. Only includes text of type 'LINE' for more accurate
    and coherent results.

    Args:
        photo (str): The key (path) of the image file in the S3 bucket.
        bucket (str): The name of the S3 bucket containing the image.

    Returns:
        str: A space-separated string containing all detected lines of text from
            the image. Returns an empty string if no text is detected.

    Raises:
        botocore.exceptions.BotoCoreError: If there's an AWS service error.
        botocore.exceptions.ClientError: If there's an error with the API request.
    """
    session = boto3.Session(profile_name="default")
    client = session.client("rekognition", region_name=AWS_REGION)
    response = client.detect_text(Image={"S3Object": {"Bucket": bucket, "Name": photo}})
    text_detections = response["TextDetections"]
    # Only include detected text of type 'LINE' for more accurate results
    detected_lines = [
        text["DetectedText"] for text in text_detections if text["Type"] == "LINE"
    ]
    return " ".join(detected_lines)
