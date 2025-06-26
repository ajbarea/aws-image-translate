import boto3
from config import AWS_REGION


def list_images_in_bucket(bucket):
    s3 = boto3.client("s3", region_name=AWS_REGION)
    response = s3.list_objects_v2(Bucket=bucket)
    images = [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    return images
