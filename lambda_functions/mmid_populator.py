"""Populates an S3 bucket with images from the MMID dataset."""

import concurrent.futures
import hashlib
import io
import os
import random
import tarfile
import time
from functools import lru_cache
from typing import Dict, List, Tuple

import boto3
from aws_clients import OPTIMIZED_CONFIG, performance_monitor
from botocore import UNSIGNED
from botocore.client import Config
from image_processor import detect_text_from_image

PUBLIC_BUCKET = "mmid-pds"
DEST_BUCKET = os.environ.get("DEST_BUCKET")
LANGUAGES = os.environ.get("LANGUAGES", "chinese,hindi,spanish,arabic,french").split(
    ","
)
IMAGES_PER_LANGUAGE = int(os.environ.get("IMAGES_PER_LANGUAGE", "2"))
IMAGES_TO_CHECK_PER_LANGUAGE = int(os.environ.get("IMAGES_TO_CHECK_PER_LANGUAGE", "20"))

EXT_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


@lru_cache(maxsize=None)
def create_s3_clients():
    """Create optimized S3 clients for public and private buckets."""
    unsigned_config = Config(
        signature_version=UNSIGNED,
        retries={"max_attempts": 3, "mode": "adaptive"},
        max_pool_connections=50,
        tcp_keepalive=True,
        connect_timeout=5,
        read_timeout=30,
    )
    unsigned_s3 = boto3.client("s3", config=unsigned_config)
    signed_s3 = boto3.client("s3", config=OPTIMIZED_CONFIG)
    return unsigned_s3, signed_s3


def choose_images(members: List[tarfile.TarInfo], k: int) -> List[tarfile.TarInfo]:
    """Randomly samples up to k image members from the MMID dataset structure."""
    print(f"Analyzing {len(members)} total archive members...")

    mmid_images = [m for m in members if m.name.endswith(".jpg") and m.isfile()]
    print(f"Found {len(mmid_images)} MMID image files (.jpg)")

    if not mmid_images:
        print("No MMID image files found in archive")
        return []

    sample_image_names = [img.name for img in mmid_images[:5]]
    print(f"Sample MMID image paths: {sample_image_names}")

    random.shuffle(mmid_images)
    selected = mmid_images[: min(k, len(mmid_images))]
    print(f"Selected {len(selected)} candidate images for processing")
    return selected


def get_content_type(filename: str) -> str:
    """Determines the content type of a file based on its extension."""
    for ext, mime in EXT_TO_MIME.items():
        if filename.lower().endswith(ext):
            return mime
    return "application/octet-stream"


def process_single_language(
    language: str, dest_bucket: str, images_per_language: int
) -> Tuple[str, List[str]]:
    """Processes a single language, downloading and uploading images with text."""
    language = language.strip()
    print(f"Processing language: {language}")

    tar_key = f"mini_language_image_packages/mini-{language}-package.tgz"
    staging_prefix = "staging/mmid/"
    final_prefix = "mmid/"

    unsigned_s3, signed_s3 = create_s3_clients()
    uploaded_keys_for_language: List[str] = []

    try:
        tar_buffer = io.BytesIO()
        unsigned_s3.download_fileobj(PUBLIC_BUCKET, tar_key, tar_buffer)
        tar_buffer.seek(0)

        with tarfile.open(fileobj=tar_buffer) as tf:
            candidate_members = choose_images(
                tf.getmembers(), IMAGES_TO_CHECK_PER_LANGUAGE
            )
            print(f"Checking {len(candidate_members)} images for {language}...")

            for member in candidate_members:
                if len(uploaded_keys_for_language) >= images_per_language:
                    break  # Found enough images

                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                data = extracted.read()

                # Use a unique name for staging to avoid collisions
                staging_filename = (
                    f"{hashlib.md5(member.name.encode()).hexdigest()}.jpg"
                )
                staging_key = f"{staging_prefix}{staging_filename}"

                try:
                    # 1. Upload to staging
                    signed_s3.put_object(
                        Bucket=dest_bucket,
                        Key=staging_key,
                        Body=data,
                        ContentType="image/jpeg",
                    )

                    # 2. Detect text
                    detected_text = detect_text_from_image(dest_bucket, staging_key)

                    if detected_text and detected_text.strip():
                        print(f"Text found in {member.name}. Moving to final location.")
                        # 3a. Move to final location
                        path_parts = member.name.split("/")
                        if len(path_parts) >= 2:
                            directory_id = path_parts[-2]
                            final_filename = f"{directory_id}_{language}.jpg"
                        else:
                            final_filename = (
                                f"{os.path.basename(member.name)}_{language}"
                            )

                        final_key = f"{final_prefix}{final_filename}"

                        signed_s3.copy_object(
                            Bucket=dest_bucket,
                            CopySource={"Bucket": dest_bucket, "Key": staging_key},
                            Key=final_key,
                        )
                        uploaded_keys_for_language.append(final_key)
                    else:
                        print(f"No text found in {member.name}.")

                except Exception as e:
                    print(f"Error processing image {member.name}: {e}")
                finally:
                    # 4. Delete from staging
                    try:
                        signed_s3.delete_object(Bucket=dest_bucket, Key=staging_key)
                    except Exception as e:
                        print(f"Failed to delete staging file {staging_key}: {e}")

        print(
            f"Successfully uploaded {len(uploaded_keys_for_language)} images with text for {language}"
        )
        return language, uploaded_keys_for_language

    except Exception as e:
        print(f"Error processing language {language}: {str(e)}")
        return language, []


def lambda_handler(event, _):
    """Lambda handler to populate the S3 bucket with images from the MMID dataset."""
    global_seed = int(time.time() * 1000000) + hash(str(event)) % 1000000
    random.seed(global_seed)
    print(f"Initialized global random seed: {global_seed}")

    if not DEST_BUCKET:
        raise RuntimeError("DEST_BUCKET environment variable not set")

    print(f"Starting MMID populator for languages: {LANGUAGES}")
    print(f"Images per language: {IMAGES_PER_LANGUAGE}")

    all_uploaded_keys: List[str] = []
    results_by_language: Dict[str, List[str]] = {}

    max_workers = min(3, len(LANGUAGES))
    print(f"Using {max_workers} parallel workers for language processing")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_language = {
            executor.submit(
                process_single_language, language, DEST_BUCKET, IMAGES_PER_LANGUAGE
            ): language
            for language in LANGUAGES
        }

        for future in concurrent.futures.as_completed(future_to_language):
            language = future_to_language[future]
            try:
                language_clean, uploaded_keys = future.result()
                results_by_language[language_clean] = uploaded_keys
                all_uploaded_keys.extend(uploaded_keys)
                print(
                    f"[SUCCESS] Completed {language_clean}: {len(uploaded_keys)} images"
                )
            except Exception as e:
                print(f"[ERROR] Error processing language {language}: {str(e)}")
                results_by_language[language] = []

    total_uploaded = len(all_uploaded_keys)
    print(
        f"[COMPLETE] MMID population complete! Total images with text: {total_uploaded}"
    )
    print(
        f"[RESULTS] Results by language: {[(k, len(v)) for k, v in results_by_language.items()]}"
    )

    performance_monitor.persist_metrics()
    return {
        "uploaded": total_uploaded,
        "languages": LANGUAGES,
        "images_per_language": IMAGES_PER_LANGUAGE,
        "results_by_language": results_by_language,
        "all_keys": all_uploaded_keys,
        "bucket": DEST_BUCKET,
        "parallel_workers": max_workers,
        "performanceMetrics": performance_monitor.get_metrics(),
    }
