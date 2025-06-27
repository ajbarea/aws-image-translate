import boto3
from config import AWS_REGION


def detect_text_from_s3(photo, bucket):
    session = boto3.Session(profile_name="default")
    client = session.client("rekognition", region_name=AWS_REGION)
    response = client.detect_text(Image={"S3Object": {"Bucket": bucket, "Name": photo}})
    text_detections = response["TextDetections"]
    # Only include detected text of type 'LINE' for more accurate results
    detected_lines = [
        text["DetectedText"] for text in text_detections if text["Type"] == "LINE"
    ]
    return " ".join(detected_lines)
