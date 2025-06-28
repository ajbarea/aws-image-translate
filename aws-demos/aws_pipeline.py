"""
AWS Translation Pipeline

This script orchestrates the complete translation pipeline:
1. Detect text from images using AWS Rekognition
2. Detect language of extracted text using AWS Comprehend
3. Translate text to target language using AWS Translate
4. Clean up any AWS resources (if needed)
"""

import time
import boto3
from typing import Dict, Tuple, Optional

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


class AWSTranslationPipeline:
    """Main pipeline class that orchestrates the translation workflow."""

    def __init__(
        self, bucket_name: str, target_language: str = "en", region: str = "us-east-1"
    ):
        """
        Initialize the pipeline.

        Args:
            bucket_name (str): S3 bucket name containing images
            target_language (str): Target language for translation (default: 'en')
            region (str): AWS region (default: 'us-east-1')
        """
        self.bucket_name = bucket_name
        self.target_language = target_language
        self.region = region
        self.session = boto3.Session(profile_name="default")

        # Track resources for cleanup
        self.processed_files = []
        self.temp_resources = []

    def run_pipeline(self, image_name: str) -> Dict:
        """
        Run the complete translation pipeline for a single image.

        Args:
            image_name (str): Name of the image file in S3

        Returns:
            dict: Pipeline results including original text, detected language, and translation
        """
        print("=" * 70)
        print("AWS TRANSLATION PIPELINE")
        print("=" * 70)
        print(f"Processing image: {image_name}")
        print(f"S3 Bucket: {self.bucket_name}")
        print(f"Target language: {self.target_language}")
        print(f"AWS Region: {self.region}")
        print()

        # Initialize result dictionary
        result = {
            "image": image_name,
            "bucket": self.bucket_name,
            "success": False,
            "original_text": "",
            "detected_language": "",
            "language_confidence": 0.0,
            "translated_text": "",
            "error": None,
        }

        try:
            # Step 1: Detect text from image
            print("STEP 1: Detecting text from image...")
            print("-" * 40)
            text_count, detected_text = self._step1_detect_text(image_name)

            if not detected_text:
                if text_count == 0:
                    result["error"] = (
                        f"No text detected in image '{image_name}'. Image may not exist in S3 bucket or contains no readable text."
                    )
                else:
                    result["error"] = "No readable text found in image"
                print(f"✗ {result['error']}")
                return result

            result["original_text"] = detected_text
            print(f"✓ Successfully detected {text_count} text elements")
            print(f"Combined text: '{detected_text}'")
            print()

            # Step 2: Detect language
            print("STEP 2: Detecting language of extracted text...")
            print("-" * 50)
            language_result = self._step2_detect_language(detected_text)

            if not language_result:
                result["error"] = "Failed to detect language"
                print("✗ Language detection failed")
                return result

            detected_lang = language_result["language_code"]
            confidence = language_result["confidence"]
            result["detected_language"] = detected_lang
            result["language_confidence"] = confidence

            print(
                f"✓ Language detected: {detected_lang} (confidence: {confidence:.2%})"
            )
            print()

            # Step 3: Translate text
            print("STEP 3: Translating text...")
            print("-" * 30)

            if detected_lang == self.target_language:
                print(f"Text is already in target language ({self.target_language})")
                result["translated_text"] = detected_text
                print("✓ No translation needed")
            else:
                translated_text = self._step3_translate_text(
                    detected_text, detected_lang, self.target_language
                )

                if not translated_text:
                    result["error"] = "Translation failed"
                    print("✗ Translation failed")
                    return result

                result["translated_text"] = translated_text
                print("✓ Translation successful!")
            print()

            # Step 4: Cleanup
            print("STEP 4: Cleaning up resources...")
            print("-" * 35)
            self._step4_cleanup()
            print("✓ Cleanup completed")
            print()

            result["success"] = True
            self._print_summary(result)

        except Exception as e:
            result["error"] = str(e)
            print(f"✗ Pipeline failed with error: {e}")

        return result

    def _step1_detect_text(self, image_name: str) -> Tuple[int, str]:
        """Step 1: Detect text from image using AWS Rekognition."""
        try:
            text_count, detected_text = detect_text(image_name, self.bucket_name)
            self.processed_files.append(f"s3://{self.bucket_name}/{image_name}")
            return text_count, detected_text
        except Exception as e:
            print(f"Error in text detection: {e}")
            return 0, ""

    def _step2_detect_language(self, text: str) -> Optional[Dict]:
        """Step 2: Detect language using AWS Comprehend."""
        try:
            return detect_language(text)
        except Exception as e:
            print(f"Error in language detection: {e}")
            return None

    def _step3_translate_text(
        self, text: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """Step 3: Translate text using AWS Translate."""
        try:
            return translate_text(text, source_lang, target_lang)
        except Exception as e:
            print(f"Error in translation: {e}")
            return None

    def _step4_cleanup(self):
        """
        Step 4: Clean up AWS resources.

        Note: This pipeline primarily uses read-only operations, so cleanup
        mainly involves clearing temporary data and ensuring no persistent
        resources are left behind.
        """
        try:
            # Clear processed files list
            self.processed_files.clear()

            # Clear any temporary resources
            self.temp_resources.clear()

            # For this pipeline, we don't create persistent AWS resources
            # like DynamoDB tables, S3 objects, or Lambda functions
            # But if we did, we would clean them up here

            # Example cleanup operations (uncomment if needed):
            # self._cleanup_dynamodb_tables()
            # self._cleanup_s3_temp_objects()
            # self._cleanup_lambda_functions()

            print("Resources cleaned up successfully")

        except Exception as e:
            print(f"Warning: Cleanup encountered an issue: {e}")

    def _cleanup_dynamodb_tables(self):
        """Clean up any temporary DynamoDB tables (if created)."""
        # Example implementation:
        # dynamodb = self.session.client('dynamodb', region_name=self.region)
        # for table_name in self.temp_resources:
        #     try:
        #         dynamodb.delete_table(TableName=table_name)
        #         print(f"Deleted DynamoDB table: {table_name}")
        #     except Exception as e:
        #         print(f"Failed to delete table {table_name}: {e}")
        pass

    def _cleanup_s3_temp_objects(self):
        """Clean up any temporary S3 objects (if created)."""
        # Example implementation:
        # s3 = self.session.client('s3', region_name=self.region)
        # for obj_key in self.temp_resources:
        #     try:
        #         s3.delete_object(Bucket=self.bucket_name, Key=obj_key)
        #         print(f"Deleted S3 object: s3://{self.bucket_name}/{obj_key}")
        #     except Exception as e:
        #         print(f"Failed to delete object {obj_key}: {e}")
        pass

    def _print_summary(self, result: Dict):
        """Print a summary of the pipeline results."""
        print("=" * 70)
        print("PIPELINE SUMMARY")
        print("=" * 70)
        print(f"Image: {result['image']}")
        print(f"Original text: {result['original_text']}")
        print(
            f"Detected language: {result['detected_language']} ({result['language_confidence']:.2%} confidence)"
        )
        print(f"Translated text: {result['translated_text']}")
        print("=" * 70)
        print("🎉 Pipeline completed successfully!")
        print()


def run_batch_pipeline(
    bucket_name: str, image_list: list, target_language: str = "en"
) -> list:
    """
    Run the pipeline for multiple images.

    Args:
        bucket_name (str): S3 bucket name
        image_list (list): List of image filenames
        target_language (str): Target language for translation

    Returns:
        list: Results for all processed images
    """
    pipeline = AWSTranslationPipeline(bucket_name, target_language)
    results = []

    print(f"Processing {len(image_list)} images...")
    print()

    for i, image_name in enumerate(image_list, 1):
        print(f"Processing image {i}/{len(image_list)}: {image_name}")
        result = pipeline.run_pipeline(image_name)
        results.append(result)

        # Add a small delay between processing to avoid API throttling
        if i < len(image_list):
            time.sleep(1)

    # Print batch summary
    successful = len([r for r in results if r["success"]])
    failed = len(results) - successful

    print("=" * 70)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 70)
    print(f"Total images processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed images:")
        for result in results:
            if not result["success"]:
                print(f"  - {result['image']}: {result['error']}")

    return results


def main():
    """Main function to run the pipeline with example data."""
    # Configuration
    bucket_name = "ajbarea"  # Replace with your S3 bucket
    target_language = "en"  # Target language for translation

    # Test with a single image
    print("Running single image pipeline test...")
    image_name = "es1.png"  # Replace with your test image
    local_image_path = "C:/ajsoftworks/aws-image-translate/spanish_images/es1.png"

    # Ensure the image exists in S3
    if not s3_object_exists(bucket_name, image_name):
        print(
            f"Image s3://{bucket_name}/{image_name} not found. Uploading from {local_image_path}..."
        )
        if not upload_file_to_s3(local_image_path, bucket_name, image_name):
            print("✗ Failed to upload image. Skipping single image pipeline test.")
            return

    pipeline = AWSTranslationPipeline(bucket_name, target_language)
    result = pipeline.run_pipeline(image_name)

    if result["success"]:
        print("Single image test completed successfully!")
    else:
        print(f"Single image test failed: {result['error']}")

    print("\n" + "=" * 70)
    print()

    # Example of batch processing (uncomment to test)
    # print("Running batch pipeline test...")
    # image_list = ["es1.png", "es2.jpg", "es3.png"]
    # batch_results = run_batch_pipeline(bucket_name, image_list, target_language)


if __name__ == "__main__":
    main()
