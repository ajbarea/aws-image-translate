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


def upload_file_to_s3(file_path, bucket_name, object_name=None):
    if object_name is None:
        object_name = file_path.split("/")[-1]
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return False
    return True


def upload_fileobj_to_s3(fileobj, bucket_name, object_name):
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3_client.upload_fileobj(fileobj, bucket_name, object_name)
    except Exception as e:
        print(f"Error uploading file object to S3: {e}")
        return False
    return True
