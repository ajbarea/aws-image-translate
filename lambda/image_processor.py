import json
from typing import Any, Dict, Tuple, cast

import boto3
from botocore.exceptions import ClientError


def extract_event_parameters(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract parameters from different event types (S3, API Gateway, direct invocation)."""
    if "Records" in event:
        record = event["Records"][0]
        return {
            "bucket": record["s3"]["bucket"]["name"],
            "key": record["s3"]["object"]["key"],
            "target_language": "en",
            "provided_detected_text": None,
            "provided_detected_language": None,
        }

    body = event
    if "body" in event and event["body"]:
        body = (
            json.loads(event["body"])
            if isinstance(event["body"], str)
            else event["body"]
        )

    return {
        "bucket": body.get("bucket"),
        "key": body.get("key"),
        "target_language": body.get("targetLanguage", "en"),
        "provided_detected_text": body.get("detectedText"),
        "provided_detected_language": body.get("detectedLanguage"),
    }


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


def detect_text_from_image(rekognition_client: Any, bucket: str, key: str) -> str:
    """Detect text from image using Rekognition."""
    print(f"Detecting text in s3://{bucket}/{key}")

    rekognition_response = rekognition_client.detect_text(
        Image={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    detected_lines = [
        text["DetectedText"]
        for text in rekognition_response["TextDetections"]
        if text["Type"] == "LINE"
    ]

    return " ".join(detected_lines)


def detect_language(comprehend_client: Any, text: str) -> str:
    """Detect language of text using Comprehend."""
    print(f"Detected text: {text}")

    comprehend_response = comprehend_client.detect_dominant_language(Text=text)
    detected_language = cast(str, comprehend_response["Languages"][0]["LanguageCode"])

    print(f"Detected language: {detected_language}")
    return detected_language


def translate_text_if_needed(
    translate_client: Any, text: str, source_language: str, target_language: str
) -> str:
    """Translate text if source and target languages differ."""
    if source_language == target_language:
        print(
            f"Text is already in target language ({target_language}), no translation needed"
        )
        return text

    translate_response = translate_client.translate_text(
        Text=text,
        SourceLanguageCode=source_language,
        TargetLanguageCode=target_language,
    )
    translated_text = cast(str, translate_response["TranslatedText"])
    print(f"Translated text to {target_language}: {translated_text}")
    return translated_text


def process_text_detection_and_translation(
    params: Dict[str, Any], aws_clients: Tuple[Any, Any, Any]
) -> Dict[str, Any]:
    """Process text detection and translation logic."""
    rekognition, comprehend, translate_client = aws_clients

    if params["provided_detected_text"] and params["provided_detected_language"]:
        detected_text = params["provided_detected_text"]
        detected_language = params["provided_detected_language"]
        print(f"Using provided text: {detected_text}")
        print(f"Using provided language: {detected_language}")
    else:
        detected_text = detect_text_from_image(
            rekognition, params["bucket"], params["key"]
        )

        if not detected_text:
            return create_success_response(
                {
                    "detectedText": "",
                    "detectedLanguage": "",
                    "translatedText": "",
                    "targetLanguage": params["target_language"],
                    "message": "No text detected in image",
                }
            )

        detected_language = detect_language(comprehend, detected_text)

    # Translate text if needed
    translated_text = translate_text_if_needed(
        translate_client, detected_text, detected_language, params["target_language"]
    )

    return create_success_response(
        {
            "detectedText": detected_text,
            "detectedLanguage": detected_language,
            "translatedText": translated_text,
            "targetLanguage": params["target_language"],
            "bucket": params["bucket"],
            "key": params["key"],
        }
    )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function to process uploaded images:
    1. Detect text using Rekognition
    2. Detect language using Comprehend
    3. Translate text using Translate
    """
    try:
        # Extract parameters from event
        params = extract_event_parameters(event)

        # Validate required parameters
        if not params["bucket"] or not params["key"]:
            return create_error_response(400, "Missing bucket or key parameter")

        # Initialize AWS clients
        aws_clients = (
            boto3.client("rekognition"),
            boto3.client("comprehend"),
            boto3.client("translate"),
        )

        # Process text detection and translation
        return process_text_detection_and_translation(params, aws_clients)

    except ClientError as e:
        print(f"AWS Client Error: {e}")
        return create_error_response(500, f"AWS Error: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        return create_error_response(500, f"Internal server error: {str(e)}")
