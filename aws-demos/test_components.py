"""
Test script for individual pipeline components

This script tests each component individually to ensure they work correctly
before running the full pipeline.
"""

import boto3

from pipeline import detect_text, detect_language, translate_text


def s3_object_exists(bucket, key):
    """Check if an object exists in an S3 bucket."""
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except s3.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise


def upload_file_to_s3(file_path, bucket, key):
    """Upload a file to an S3 bucket."""
    s3 = boto3.client("s3")
    try:
        s3.upload_file(file_path, bucket, key)
        return True
    except Exception as e:
        print(f"Error uploading file {file_path} to s3://{bucket}/{key}: {e}")
        return False


def test_text_detection():
    """Test the text detection functionality."""
    print("Testing Text Detection...")
    print("-" * 25)

    # Note: This requires actual AWS credentials and S3 access
    bucket = "ajbarea"  # Replace with your test bucket
    photo = "es1.png"  # Replace with your test image
    local_image_path = "C:/ajsoftworks/aws-image-translate/spanish_images/es1.png"

    # Ensure the image exists in S3
    if not s3_object_exists(bucket, photo):
        print(
            f"Image s3://{bucket}/{photo} not found. Uploading from {local_image_path}..."
        )
        if not upload_file_to_s3(local_image_path, bucket, photo):
            print("✗ Failed to upload image. Skipping text detection test.")
            return

    print(f"Testing with s3://{bucket}/{photo}")
    try:
        text_count, detected_text = detect_text(photo, bucket)
        print(f"Text elements detected: {text_count}")
        print(f"Combined text: '{detected_text}'")
        if detected_text:
            print("✓ Text detection successful!")
        else:
            print("⚠ No text detected in image")
    except Exception as e:
        print(f"✗ Text detection failed: {e}")
        print("Note: This test requires AWS credentials and S3 access")
    print()


def test_language_detection():
    """Test the language detection functionality."""
    print("Testing Language Detection...")
    print("-" * 30)

    test_cases = [
        "Hola, ¿cómo estás? Me llamo María.",  # Spanish
        "Bonjour, comment allez-vous?",  # French
        "Hello, how are you today?",  # English
        "Guten Tag, wie geht es Ihnen?",  # German
    ]

    for text in test_cases:
        print(f"Text: {text}")
        result = detect_language(text)
        if result:
            print(
                f"✓ Language: {result['language_code']} (confidence: {result['confidence']:.2%})"
            )
        else:
            print("✗ Language detection failed")
        print()


def test_translation():
    """Test the translation functionality."""
    print("Testing Translation...")
    print("-" * 20)

    test_cases = [
        ("Hola mundo", "es", "en"),
        ("Bonjour le monde", "fr", "en"),
        ("Hello world", "en", "es"),
    ]

    for text, source, target in test_cases:
        print(f"Translating '{text}' from {source} to {target}")
        translated = translate_text(text, source, target)
        if translated:
            print(f"✓ Translation: '{translated}'")
        else:
            print("✗ Translation failed")
        print()


def main():
    print("AWS Translation Pipeline Component Tests")
    print("=" * 50)
    print()

    # Test text detection
    test_text_detection()
    print()

    # Test language detection
    test_language_detection()
    print()

    # Test translation
    test_translation()

    print("Component testing completed!")


if __name__ == "__main__":
    main()
