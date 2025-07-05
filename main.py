import argparse
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from config import S3_IMAGE_BUCKET, TARGET_LANGUAGE_CODE
from src.amazon_rekognition import detect_text_from_s3
from src.amazon_s3 import list_images_in_bucket
from src.amazon_translate import detect_language, translate_text


def upload_file_to_s3(file_path: str, bucket: str, key: str) -> bool:
    """Upload a file to an S3 bucket."""
    s3 = boto3.client("s3")
    try:
        s3.upload_file(file_path, bucket, key)
        return True
    except Exception as e:
        print(f"Error uploading file {file_path} to s3://{bucket}/{key}: {e}")
        return False


def process_image(photo: str, bucket: str, target_lang: str) -> Optional[str]:
    """Detect text in an image from S3 and translate it."""
    print(f"\nDetecting text in s3://{bucket}/{photo} ...")
    try:
        detected_text = detect_text_from_s3(photo, bucket)
    except Exception as e:
        print(f"Error detecting text: {e}")
        return None
    print("Detected text:", detected_text)
    if detected_text:
        try:
            # Automatically detect source language
            source_lang = detect_language(detected_text)
            print(f"Detected source language: {source_lang}")

            translated = translate_text(
                detected_text,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            print(f"Translated to {target_lang}:", translated)
            return translated
        except Exception as e:
            print(f"Error translating text: {e}")
            return None
    else:
        print("No text detected.")
        return None


def process_all_images(bucket: str, target_lang: str) -> List[str]:
    """Process all images in the given S3 bucket."""
    print(f"Listing images in s3 bucket: s3://{bucket} ...")
    try:
        images = list_images_in_bucket(bucket)
    except Exception as e:
        print(f"Error listing images: {e}")
        return []
    print("Found images:", images)
    results = []
    for photo in images:
        result = process_image(photo, bucket, target_lang)
        if result:
            results.append(result)
    return results


def main(
    bucket: str = S3_IMAGE_BUCKET,
    target_lang: str = TARGET_LANGUAGE_CODE,
) -> None:
    """Main entry point for processing images."""
    image_name = "es1.png"
    local_image_path = (
        "C:/ajsoftworks/aws-image-translate/tests/resources/spanish_images/es1.png"
    )

    if s3_object_exists(bucket, image_name):
        print(f"Image {image_name} already exists in s3://{bucket}. Skipping upload.")
    else:
        print(f"Uploading from {local_image_path} to s3://{bucket}/{image_name}...")
        if not upload_file_to_s3(local_image_path, bucket, image_name):
            print("✗ Failed to upload image. Skipping image processing.")
            return

    process_image(image_name, bucket, target_lang)


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Detect and translate text from images in an S3 bucket."
    )
    parser.add_argument(
        "--bucket", type=str, default=S3_IMAGE_BUCKET, help="S3 bucket name"
    )
    parser.add_argument(
        "--target-lang",
        type=str,
        default=TARGET_LANGUAGE_CODE,
        help="Target language code",
    )
    args = parser.parse_args()
    main(args.bucket, args.target_lang)


def s3_object_exists(bucket_name: str, object_key: str) -> bool:
    """Check if an object exists in an S3 bucket.

    Args:
        bucket_name (str): The name of the S3 bucket.
        object_key (str): The key of the object to check.

    Returns:
        bool: True if the object exists, False otherwise.
    """
    s3_client = boto3.client("s3")
    try:
        s3_client.head_object(Bucket=bucket_name, Key=object_key)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            return False
        else:
            raise


if __name__ == "__main__":  # pragma: no cover
    cli()
