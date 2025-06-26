"""Amazon Rekognition utility functions for text detection in images stored on S3.

This module provides a function to detect and extract text lines from images in an S3 bucket
using AWS Rekognition's text detection capabilities.
"""

import boto3
from config import AWS_REGION


def detect_text_from_s3(photo, bucket):
    """Detect and extract text lines from an image in an S3 bucket using Amazon Rekognition.

    Args:
        photo (str): The name of the image file in the S3 bucket.
        bucket (str): The name of the S3 bucket containing the image.

    Returns:
        str: A single string containing all detected text lines, separated by spaces.

    Raises:
        botocore.exceptions.BotoCoreError: If the AWS SDK encounters a low-level error.
        botocore.exceptions.ClientError: If the Rekognition API call fails.
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
