"""
AWS Lambda Image Processor with CloudWatch Logging

This module processes uploaded images by:
1. Detecting text using Amazon Rekognition
2. Detecting language using Amazon Comprehend
3. Translating text using Amazon Translate
4. Logging structured information to CloudWatch
"""

import hashlib
import json
import logging
import os
import random
import time
import urllib.parse
import uuid
from typing import Any, Dict, Optional, cast

from botocore.exceptions import ClientError

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from aws_clients import (
    performance_monitor,
    safe_comprehend_call,
    safe_rekognition_call,
    safe_translate_call,
)
from history_handler import _get_user_id, get_history_table, get_translations_table

# Configure structured logging for CloudWatch
logger = logging.getLogger()

# Logging configuration from environment variables
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
if log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    logger.setLevel(getattr(logging, log_level))
else:
    logger.setLevel(logging.INFO)

# Performance and debug logging controls
ENABLE_PERFORMANCE_LOGGING = (
    os.getenv("ENABLE_PERFORMANCE_LOGGING", "true").lower() == "true"
)
DEBUG_SAMPLING_RATE = float(os.getenv("DEBUG_SAMPLING_RATE", "1.0"))
INCLUDE_TRACEBACK = os.getenv("INCLUDE_TRACEBACK", "false").lower() == "true"

if logger.handlers:
    for handler in logger.handlers:
        logger.removeHandler(handler)

# Create console handler with JSON formatter for CloudWatch
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)


class CloudWatchFormatter(logging.Formatter):
    """JSON formatter for CloudWatch Logs"""

    # Core fields that should always be present
    CORE_FIELDS = {"timestamp", "level", "message", "module", "function", "line"}

    # Standard logging record attributes to exclude from custom fields
    STANDARD_ATTRIBUTES = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "getMessage",
    }

    def format(self, record):
        # Start with core log structure
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add all custom attributes dynamically
        for attr_name in dir(record):
            if (
                not attr_name.startswith("_")
                and attr_name not in self.STANDARD_ATTRIBUTES
                and not callable(getattr(record, attr_name, None))
            ):

                attr_value = getattr(record, attr_name)
                if attr_value is not None:  # Only include non-None values
                    log_entry[attr_name] = attr_value

        return json.dumps(log_entry, default=str, separators=(",", ":"))


formatter = CloudWatchFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Global request context for logging
_request_context = {}


def set_request_context(
    request_id: str,
    user_id: Optional[str] = None,
    image_key: Optional[str] = None,
    bucket: Optional[str] = None,
):
    """Set global request context for logging"""
    global _request_context
    _request_context = {
        "request_id": request_id,
        "user_id": user_id,
        "image_key": image_key,
        "bucket": bucket,
    }


def log_with_context(level: str, message: str, **kwargs):
    """Log message with request context and additional fields"""
    # Early return if log level won't be processed
    log_level_num = getattr(logging, level.upper(), logging.INFO)
    if not logger.isEnabledFor(log_level_num):
        return

    # Apply sampling for debug logs to control costs
    if level.lower() == "debug":
        if logger.isEnabledFor(logging.DEBUG) and random.random() > DEBUG_SAMPLING_RATE:
            return

    # Merge request context with provided kwargs
    extra = {**_request_context, **kwargs}

    # Filter out None values to keep logs clean
    extra = {k: v for k, v in extra.items() if v is not None}

    getattr(logger, level.lower())(message, extra=extra)


def log_operation(
    operation: str, duration_ms: Optional[float] = None, success: bool = True, **kwargs
):
    """Log operation with start/completion in a single call when duration is provided"""
    filtered_kwargs = {k: v for k, v in kwargs.items() if k != "message"}

    if duration_ms is None:
        # Starting operation
        log_with_context(
            "info", f"Starting {operation}", operation=operation, **filtered_kwargs
        )
    else:
        # Completing operation
        level = "info" if success else "error"
        status = "completed" if success else "failed"
        log_with_context(
            level,
            f"Operation {operation} {status} in {duration_ms:.2f}ms",
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            **filtered_kwargs,
        )


def log_performance_data(
    metrics: Optional[Dict[str, Any]] = None, operation: Optional[str] = None
):
    """Log performance metrics and memory usage in a single call when enabled"""
    if not ENABLE_PERFORMANCE_LOGGING:
        return

    perf_data = {}

    # Add provided metrics
    if metrics:
        perf_data.update(metrics)

    # Add memory usage if available
    if PSUTIL_AVAILABLE:
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            perf_data.update(
                {
                    "memory_rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                    "memory_percent": round(process.memory_percent(), 2),
                }
            )
        except Exception:
            # Silently ignore memory monitoring failures
            pass

    if perf_data:
        message = (
            f"Performance data for {operation}" if operation else "Performance data"
        )
        log_with_context("debug", message, **perf_data)


def log_error(
    message: str, error: Exception, operation: Optional[str] = None, **kwargs
):
    """Log error with structured information including traceback when enabled"""
    import traceback

    error_data: Dict[str, Any] = {
        "error_type": error.__class__.__name__,
        "error_message": str(error),
    }

    # Add AWS-specific error details if available
    if hasattr(error, "response") and cast(ClientError, error).response:
        client_error = cast(ClientError, error)
        error_data.update(
            {
                "error_code": client_error.response.get("Error", {}).get("Code", ""),
                "http_status": client_error.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode", ""
                ),
            }
        )

    # Include traceback for debugging when enabled or in debug mode
    if INCLUDE_TRACEBACK or logger.isEnabledFor(logging.DEBUG):
        error_data["traceback"] = traceback.format_exc()

    if operation:
        error_data["operation"] = operation

    filtered_kwargs = {k: v for k, v in kwargs.items() if k != "message"}

    log_with_context("error", message, **error_data, **filtered_kwargs)


def extract_event_parameters(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract parameters from different event types (S3, API Gateway, direct invocation)."""
    log_with_context(
        "debug", "Extracting event parameters", event_type=type(event).__name__
    )

    if "Records" in event:
        record = event["Records"][0]
        # S3 object keys are URL-encoded in event notifications
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        params = {
            "bucket": record["s3"]["bucket"]["name"],
            "key": key,
            "target_language": "en",
            "provided_detected_text": None,
            "provided_detected_language": None,
        }
        log_with_context(
            "info",
            "Extracted S3 event parameters",
            bucket=params["bucket"],
            key=params["key"],
        )
        return params

    body = event
    if "body" in event and event["body"]:
        body = (
            json.loads(event["body"])
            if isinstance(event["body"], str)
            else event["body"]
        )

    params = {
        "bucket": body.get("bucket"),
        "key": body.get("key"),
        "target_language": body.get("targetLanguage", "en"),
        "provided_detected_text": body.get("detectedText"),
        "provided_detected_language": body.get("detectedLanguage"),
    }

    log_with_context(
        "info",
        "Extracted API Gateway/direct event parameters",
        bucket=params["bucket"],
        key=params["key"],
        target_language=params["target_language"],
        has_provided_text=bool(params["provided_detected_text"]),
    )

    return params


def create_cors_headers() -> Dict[str, str]:
    """Create CORS headers for response."""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST",
    }


def create_error_response(status_code: int, error_message: str) -> Dict[str, Any]:
    """Create standardized error response."""
    return {
        "statusCode": status_code,
        "headers": create_cors_headers(),
        "body": json.dumps({"error": error_message}),
    }


def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized success response."""
    return {
        "statusCode": 200,
        "headers": create_cors_headers(),
        "body": json.dumps(data),
    }


def is_supported_image_format(key: str) -> bool:
    """Check if the image format is supported by Rekognition DetectText."""
    supported_extensions = {".jpg", ".jpeg", ".png"}
    file_extension = key.lower().split(".")[-1] if "." in key else ""
    return f".{file_extension}" in supported_extensions


def _contains_asian_characters(text: str) -> bool:
    """Check if text contains CJK (Chinese, Japanese, Korean) characters for OCR optimization."""
    if not text:
        return False

    for char in text:
        code = ord(char)
        # Check for most common Asian character ranges that benefit from lower confidence thresholds
        if (
            (
                0x4E00 <= code <= 0x9FFF
            )  # CJK Unified Ideographs (Chinese/Japanese/Korean)
            or (0x3040 <= code <= 0x309F)  # Hiragana
            or (0x30A0 <= code <= 0x30FF)  # Katakana
            or (0xAC00 <= code <= 0xD7AF)  # Hangul Syllables (Korean)
        ):
            return True
    return False


def detect_text_from_image(bucket: str, key: str) -> str:
    """Detect text from image using Rekognition with optimized confidence for Asian languages."""
    operation = "rekognition_detect_text"

    # Pre-validate image format
    if not is_supported_image_format(key):
        file_extension = key.split(".")[-1] if "." in key else "unknown"
        error_msg = f"Unsupported image format: .{file_extension}. Supported formats: JPG, JPEG, PNG"
        log_with_context(
            "error",
            error_msg,
            operation=operation,
            image_key=key,
            file_extension=file_extension,
        )
        raise ValueError(error_msg)

    log_operation(operation, bucket=bucket, image_key=key)
    start_time = time.time()

    try:
        log_with_context(
            "debug", "Calling Rekognition DetectText API", bucket=bucket, image_key=key
        )

        response = safe_rekognition_call(
            "detect_text",
            Image={"S3Object": {"Bucket": bucket, "Name": key}},
            Filters={"WordFilter": {"MinConfidence": 45.0}},
        )

        detected_texts = []
        word_confidences = []

        for text_detection in response["TextDetections"]:
            if text_detection["Type"] == "LINE":
                confidence = text_detection.get("Confidence", 0)
                detected_text = text_detection["DetectedText"]

                # Use lower confidence threshold for Asian text
                min_confidence = (
                    45.0 if _contains_asian_characters(detected_text) else 55.0
                )

                if confidence >= min_confidence:
                    detected_texts.append(detected_text)
                    word_confidences.append(confidence)
                    log_with_context(
                        "debug",
                        "Text segment detected",
                        detected_text=detected_text[:100],  # Limit length for logging
                        confidence=confidence,
                    )

        result = " ".join(detected_texts)
        duration = (time.time() - start_time) * 1000

        # Log completion with results
        avg_confidence = (
            sum(word_confidences) / len(word_confidences) if word_confidences else 0
        )
        log_operation(
            operation,
            duration,
            True,
            text_segments_found=len(detected_texts),
            avg_confidence=avg_confidence,
            text_length=len(result),
            bucket=bucket,
            image_key=key,
        )

        performance_monitor.record_operation(
            "rekognition_detect_text", duration / 1000, True
        )
        return result

    except ClientError as e:
        duration = (time.time() - start_time) * 1000
        performance_monitor.record_operation(
            "rekognition_detect_text", duration / 1000, False
        )

        error_code = e.response.get("Error", {}).get("Code", "")

        # Map AWS errors to user-friendly messages
        error_mappings = {
            "InvalidImageFormatException": "Invalid image format. Please use JPG, JPEG, or PNG format.",
            "ImageTooLargeException": "Image file is too large. Maximum supported size is 15MB.",
            "InvalidS3ObjectException": "Could not access the image file. Please try uploading again.",
        }

        error_msg = error_mappings.get(error_code, f"Failed to process image: {str(e)}")

        log_error(
            "Rekognition error occurred", e, operation, bucket=bucket, image_key=key
        )
        log_operation(operation, duration, False, error_message=error_msg)
        raise ValueError(error_msg)

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        performance_monitor.record_operation(
            "rekognition_detect_text", duration / 1000, False
        )
        log_error(
            "Unexpected error in text detection",
            e,
            operation,
            bucket=bucket,
            image_key=key,
        )
        log_operation(operation, duration, False)
        raise e


def detect_language(text: str) -> str:
    """Detect language of text using Comprehend."""
    operation = "comprehend_detect_language"

    log_operation(operation, text_length=len(text))
    start_time = time.time()

    try:
        log_with_context(
            "debug",
            "Calling Comprehend DetectDominantLanguage API",
            text_preview=text[:100] + "..." if len(text) > 100 else text,
        )

        comprehend_response = safe_comprehend_call(
            "detect_dominant_language", Text=text
        )
        detected_language = cast(
            str, comprehend_response["Languages"][0]["LanguageCode"]
        )
        language_confidence = comprehend_response["Languages"][0].get("Score", 0)

        duration = (time.time() - start_time) * 1000
        performance_monitor.record_operation(
            "comprehend_detect_language", duration / 1000, True
        )

        log_operation(
            operation,
            duration,
            True,
            detected_language=detected_language,
            language_confidence=language_confidence,
            text_length=len(text),
        )

        return detected_language

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        performance_monitor.record_operation(
            "comprehend_detect_language", duration / 1000, False
        )
        log_error("Error detecting language", e, operation, text_length=len(text))
        log_operation(operation, duration, False)
        raise e


# AWS Translate supported languages
AWS_SUPPORTED_LANGUAGES = {
    "af",
    "sq",
    "am",
    "ar",
    "hy",
    "az",
    "bn",
    "bs",
    "bg",
    "ca",
    "zh",
    "zh-TW",
    "hr",
    "cs",
    "da",
    "fa-AF",
    "nl",
    "en",
    "et",
    "fa",
    "tl",
    "fi",
    "fr",
    "fr-CA",
    "ka",
    "de",
    "el",
    "gu",
    "ht",
    "ha",
    "he",
    "hi",
    "hu",
    "is",
    "id",
    "ga",
    "it",
    "ja",
    "kn",
    "kk",
    "ko",
    "lv",
    "lt",
    "mk",
    "ms",
    "ml",
    "mt",
    "mr",
    "mn",
    "no",
    "ps",
    "pl",
    "pt",
    "pt-PT",
    "pa",
    "ro",
    "ru",
    "sr",
    "si",
    "sk",
    "sl",
    "so",
    "es",
    "es-MX",
    "sw",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "uz",
    "vi",
    "cy",
}


def is_language_supported(language_code: str) -> bool:
    """Check if a language code is supported by AWS Translate."""
    return language_code in AWS_SUPPORTED_LANGUAGES


def get_supported_language_fallback(language_code: str) -> Optional[str]:
    """Get a supported language fallback for unsupported language codes."""
    if is_language_supported(language_code):
        return language_code

    # Common fallbacks for unsupported language variants
    fallback_map = {
        "lb": "de",  # Luxembourgish -> German (common fallback)
        "eu": "es",  # Basque -> Spanish
        "gl": "es",  # Galician -> Spanish
        "co": "fr",  # Corsican -> French
        "br": "fr",  # Breton -> French
        "oc": "fr",  # Occitan -> French
        "sc": "it",  # Sardinian -> Italian
        "vec": "it",  # Venetian -> Italian
        "nap": "it",  # Neapolitan -> Italian
        "scn": "it",  # Sicilian -> Italian
        "lmo": "it",  # Lombard -> Italian
        "pms": "it",  # Piedmontese -> Italian
        "lij": "it",  # Ligurian -> Italian
        "rm": "de",  # Romansh -> German
        "gsw": "de",  # Swiss German -> German
        "bar": "de",  # Bavarian -> German
        "nds": "de",  # Low German -> German
        "pdc": "de",  # Pennsylvania Dutch -> German
        "yi": "de",  # Yiddish -> German
        "frr": "de",  # North Frisian -> German
        "stq": "de",  # Saterland Frisian -> German
    }

    return fallback_map.get(language_code)


def translate_text_if_needed(
    text: str, source_language: str, target_language: str
) -> str:
    """Translate text if source and target languages differ."""
    if source_language == target_language:
        log_with_context(
            "info",
            "No translation needed - languages match",
            source_language=source_language,
            target_language=target_language,
        )
        return text

    # Check if both languages are supported before attempting translation
    if not is_language_supported(source_language) or not is_language_supported(
        target_language
    ):
        unsupported_langs = []
        if not is_language_supported(source_language):
            unsupported_langs.append(f"source: {source_language}")
        if not is_language_supported(target_language):
            unsupported_langs.append(f"target: {target_language}")

        log_with_context(
            "warning",
            f"Unsupported language(s): {', '.join(unsupported_langs)}. Returning original text.",
            source_language=source_language,
            target_language=target_language,
            text_length=len(text),
        )
        return text

    operation = "translate_text"
    language_pair = f"{source_language}#{target_language}"

    log_operation(operation, language_pair=language_pair, text_length=len(text))
    start_time = time.time()

    try:
        log_with_context(
            "debug",
            "Calling Translate API",
            language_pair=language_pair,
            text_preview=text[:100] + "..." if len(text) > 100 else text,
        )

        translate_response = safe_translate_call(
            "translate_text",
            Text=text,
            SourceLanguageCode=source_language,
            TargetLanguageCode=target_language,
        )
        translated_text = cast(str, translate_response["TranslatedText"])

        duration = (time.time() - start_time) * 1000
        performance_monitor.record_operation("translate_text", duration / 1000, True)

        log_operation(
            operation,
            duration,
            True,
            language_pair=language_pair,
            source_text_length=len(text),
            translated_text_length=len(translated_text),
        )

        return translated_text

    except ClientError as e:
        duration = (time.time() - start_time) * 1000
        performance_monitor.record_operation("translate_text", duration / 1000, False)

        error_code = e.response.get("Error", {}).get("Code", "")

        # Handle unsupported language pairs gracefully
        if error_code == "UnsupportedLanguagePairException":
            log_with_context(
                "warning",
                f"Unsupported language pair: {source_language} to {target_language}. Returning original text.",
                language_pair=language_pair,
                text_length=len(text),
                operation=operation,
                duration_ms=duration,
            )
            # Return original text when translation is not supported
            return text

        # Handle other AWS Translate errors
        log_error(
            "Error translating text",
            e,
            operation,
            language_pair=language_pair,
            text_length=len(text),
        )
        log_operation(operation, duration, False)
        raise e

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        performance_monitor.record_operation("translate_text", duration / 1000, False)
        log_error(
            "Error translating text",
            e,
            operation,
            language_pair=language_pair,
            text_length=len(text),
        )
        log_operation(operation, duration, False)
        raise e


def _calculate_text_hash(text: str) -> str:
    """Calculate SHA256 hash of the given text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_translation_to_history(
    event: Dict[str, Any],
    image_key: str,
    source_language: str,
    target_language: str,
    detected_text: str,
    translated_text: str,
) -> None:
    """Saves the translation result to the history and translations tables."""
    operation = "save_translation_history"
    language_pair = f"{source_language}#{target_language}"
    user_id = None

    try:
        user_id = _get_user_id(event)
        log_with_context(
            "debug",
            "Extracted user ID for history save",
            user_id=user_id,
            image_key=image_key,
        )

        if not user_id:
            log_with_context(
                "warning",
                "No user ID found in event, skipping history save",
                image_key=image_key,
                language_pair=language_pair,
            )
            return

        log_operation(
            operation,
            user_id=user_id,
            image_key=image_key,
            language_pair=language_pair,
            text_length=len(detected_text),
        )

        history_table = get_history_table()
        translations_table = get_translations_table()

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        history_id = str(uuid.uuid4())
        translation_id = str(uuid.uuid4())
        text_hash = _calculate_text_hash(detected_text)

        # Save to translations table
        translations_table.put_item(
            Item={
                "translation_id": translation_id,
                "user_id": user_id,
                "image_key": image_key,
                "extracted_text": detected_text,
                "text_hash": text_hash,
                "translated_text": translated_text,
                "lang_pair": language_pair,
                "timestamp": timestamp,
            }
        )

        # Save to history table
        history_table.put_item(
            Item={
                "user_id": user_id,
                "history_id": history_id,
                "translation_id": translation_id,
                "image_key": image_key,
                "lang_pair": language_pair,
                "timestamp": timestamp,
            }
        )

        log_with_context(
            "info",
            "Successfully saved translation to history",
            user_id=user_id,
            translation_id=translation_id,
            history_id=history_id,
            image_key=image_key,
            language_pair=language_pair,
        )

    except Exception as e:
        log_error(
            "Error saving translation to history",
            e,
            operation,
            user_id=user_id,
            image_key=image_key,
            language_pair=language_pair,
        )


def get_cached_translation(
    detected_text: str, source_language: str, target_language: str
) -> Optional[str]:
    """Check for a cached translation in DynamoDB."""
    operation = "get_cached_translation"
    language_pair = f"{source_language}#{target_language}"
    text_hash = _calculate_text_hash(detected_text)

    log_operation(
        operation,
        language_pair=language_pair,
        text_length=len(detected_text),
    )

    try:
        translations_table = get_translations_table()

        response = translations_table.query(
            IndexName="text-language-index",
            KeyConditionExpression="text_hash = :hash AND lang_pair = :lang",
            ExpressionAttributeValues={
                ":hash": text_hash,
                ":lang": language_pair,
            },
            Limit=1,
        )

        if response["Items"]:
            cached_translation = response["Items"][0]["translated_text"]
            log_with_context(
                "info",
                "Found cached translation",
                language_pair=language_pair,
                text_length=len(detected_text),
                cached_translation_length=len(cached_translation),
            )
            return cached_translation
        else:
            log_with_context(
                "debug",
                "No cached translation found",
                language_pair=language_pair,
                text_length=len(detected_text),
            )
            return None

    except Exception as e:
        log_error(
            "Error checking for cached translation",
            e,
            operation,
            language_pair=language_pair,
            text_length=len(detected_text),
        )
        return None


def process_text_detection_and_translation(
    event: Dict[str, Any], params: Dict[str, Any]
) -> Dict[str, Any]:
    """Process text detection and translation logic."""
    operation = "process_text_detection_translation"
    start_time = time.time()

    log_operation(
        operation,
        bucket=params["bucket"],
        image_key=params["key"],
        target_language=params["target_language"],
        has_provided_text=bool(params["provided_detected_text"]),
    )

    try:
        if params["provided_detected_text"] and params["provided_detected_language"]:
            detected_text = params["provided_detected_text"]
            detected_language = params["provided_detected_language"]
            log_with_context(
                "info",
                "Using provided text and language",
                detected_language=detected_language,
                text_length=len(detected_text),
            )
        else:
            detected_text = detect_text_from_image(params["bucket"], params["key"])

            if not detected_text:
                duration = (time.time() - start_time) * 1000
                log_operation(
                    operation, duration, True, message="No text detected in image"
                )
                return create_success_response(
                    {
                        "detectedText": "",
                        "detectedLanguage": "",
                        "translatedText": "",
                        "targetLanguage": params["target_language"],
                        "message": "No text detected in image",
                    }
                )

            detected_language = detect_language(detected_text)

        # Handle unsupported detected languages with fallback
        original_detected_language = detected_language
        if not is_language_supported(detected_language):
            fallback_language = get_supported_language_fallback(detected_language)
            if fallback_language:
                log_with_context(
                    "info",
                    f"Using fallback language {fallback_language} for unsupported detected language {detected_language}",
                    original_language=detected_language,
                    fallback_language=fallback_language,
                )
                detected_language = fallback_language

        # Check for cached translation first
        cached_translation = get_cached_translation(
            detected_text, detected_language, params["target_language"]
        )

        if cached_translation:
            translated_text = cached_translation
            log_with_context(
                "info",
                "Using cached translation",
                language_pair=f"{detected_language}#{params['target_language']}",
            )
        else:
            translated_text = translate_text_if_needed(
                detected_text, detected_language, params["target_language"]
            )

        # Determine translation status
        translation_performed = (
            detected_language != params["target_language"]
            and translated_text != detected_text
            and is_language_supported(detected_language)
            and is_language_supported(params["target_language"])
        )

        # Save to history
        save_translation_to_history(
            event,
            params["key"],
            detected_language,
            params["target_language"],
            detected_text,
            translated_text,
        )

        duration = (time.time() - start_time) * 1000

        # Log completion with performance data
        metrics = performance_monitor.get_metrics()
        log_operation(
            operation,
            duration,
            True,
            detected_language=detected_language,
            target_language=params["target_language"],
            text_length=len(detected_text),
            translation_length=len(translated_text),
            used_cache=bool(cached_translation),
            translation_performed=translation_performed,
        )

        # Log performance data separately to keep main logs clean
        log_performance_data(metrics, operation)

        # Create response with translation status information
        response_data = {
            "detectedText": detected_text,
            "detectedLanguage": detected_language,
            "translatedText": translated_text,
            "targetLanguage": params["target_language"],
            "bucket": params["bucket"],
            "key": params["key"],
            "performanceMetrics": metrics,
            "translationPerformed": translation_performed,
        }

        # Include original detected language if fallback was used
        if original_detected_language != detected_language:
            response_data["originalDetectedLanguage"] = original_detected_language

        # Add helpful messages for different scenarios
        if detected_language == params["target_language"]:
            if original_detected_language != detected_language:
                response_data["message"] = (
                    f"No translation needed - text detected as {original_detected_language} (using {detected_language} fallback) matches target language"
                )
            else:
                response_data["message"] = (
                    "No translation needed - text is already in target language"
                )
        elif not is_language_supported(detected_language):
            response_data["message"] = (
                f"Translation not available - detected language '{detected_language}' is not supported"
            )
        elif not is_language_supported(params["target_language"]):
            response_data["message"] = (
                f"Translation not available - target language '{params['target_language']}' is not supported"
            )
        elif cached_translation:
            if original_detected_language != detected_language:
                response_data["message"] = (
                    f"Translation retrieved from cache (using {detected_language} fallback for detected {original_detected_language})"
                )
            else:
                response_data["message"] = "Translation retrieved from cache"
        elif translation_performed:
            if original_detected_language != detected_language:
                response_data["message"] = (
                    f"Text successfully translated (using {detected_language} fallback for detected {original_detected_language})"
                )
            else:
                response_data["message"] = "Text successfully translated"

        return create_success_response(response_data)

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_error(
            "Error in text detection and translation process",
            e,
            operation,
            bucket=params["bucket"],
            image_key=params["key"],
        )
        log_operation(operation, duration, False)
        raise e


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to process uploaded images:
    1. Detect text using Rekognition
    2. Detect language using Comprehend
    3. Translate text using Translate
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    set_request_context(request_id)

    # Log lambda invocation with essential context
    log_with_context(
        "info",
        "Lambda function invoked",
        function_name=getattr(context, "function_name", "unknown"),
        remaining_time_ms=getattr(context, "get_remaining_time_in_millis", lambda: 0)(),
        event_keys=list(event.keys()),
    )

    # Log performance data at start if enabled
    log_performance_data(operation="lambda_start")

    try:
        # Extract and validate parameters
        params = extract_event_parameters(event)

        # Update request context
        set_request_context(
            request_id,
            user_id=_get_user_id(event),
            image_key=params.get("key"),
            bucket=params.get("bucket"),
        )

        if not params["bucket"] or not params["key"]:
            error_msg = "Missing bucket or key parameter"
            log_with_context(
                "error", error_msg, bucket=params.get("bucket"), key=params.get("key")
            )
            return create_error_response(400, error_msg)

        # Process the image
        result = process_text_detection_and_translation(event, params)

        log_with_context(
            "info",
            "Lambda function completed successfully",
            bucket=params["bucket"],
            image_key=params["key"],
            target_language=params["target_language"],
        )

        log_performance_data(operation="lambda_end")
        performance_monitor.persist_metrics()
        return result

    except ValueError as e:
        log_error("Validation error occurred", e, "lambda_handler")
        performance_monitor.persist_metrics()
        return create_error_response(400, str(e))

    except ClientError as e:
        log_error("AWS Client error occurred", e, "lambda_handler")

        # Map AWS errors to user-friendly messages
        error_mappings = {
            "InvalidImageFormatException": "Unsupported image format. Please use JPG, JPEG, or PNG files.",
            "ImageTooLargeException": "Image file too large. Maximum size is 15MB.",
            "InvalidS3ObjectException": "Could not access the uploaded image. Please try uploading again.",
        }

        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = error_mappings.get(error_code, f"AWS service error: {str(e)}")
        status_code = 400 if error_code in error_mappings else 500

        performance_monitor.persist_metrics()
        return create_error_response(status_code, error_msg)

    except Exception as e:
        # Final error handler with proper structured logging
        log_error("Fatal error in lambda_handler", e, "lambda_handler")
        performance_monitor.persist_metrics()
        return create_error_response(
            500, f"Internal server error: {e.__class__.__name__}"
        )
