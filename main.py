import argparse
from typing import List, Optional
from src.amazon_rekognition import detect_text_from_s3
from src.amazon_translate import translate_text
from src.amazon_s3 import list_images_in_bucket
from config import S3_IMAGE_BUCKET, SOURCE_LANGUAGE_CODE, TARGET_LANGUAGE_CODE


def process_image(
    photo: str, bucket: str, source_lang: str, target_lang: str
) -> Optional[str]:
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


def process_all_images(bucket: str, source_lang: str, target_lang: str) -> List[str]:
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
        result = process_image(photo, bucket, source_lang, target_lang)
        if result:
            results.append(result)
    return results


def main(
    bucket: str = S3_IMAGE_BUCKET,
    source_lang: str = SOURCE_LANGUAGE_CODE,
    target_lang: str = TARGET_LANGUAGE_CODE,
):
    """Main entry point for processing images."""
    process_all_images(bucket, source_lang, target_lang)


def cli():
    parser = argparse.ArgumentParser(
        description="Detect and translate text from images in an S3 bucket."
    )
    parser.add_argument(
        "--bucket", type=str, default=S3_IMAGE_BUCKET, help="S3 bucket name"
    )
    parser.add_argument(
        "--source-lang",
        type=str,
        default=SOURCE_LANGUAGE_CODE,
        help="Source language code",
    )
    parser.add_argument(
        "--target-lang",
        type=str,
        default=TARGET_LANGUAGE_CODE,
        help="Target language code",
    )
    args = parser.parse_args()
    main(args.bucket, args.source_lang, args.target_lang)


if __name__ == "__main__":  # pragma: no cover
    cli()
