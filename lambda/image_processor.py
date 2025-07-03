import json

import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    Lambda function to process uploaded images:
    1. Detect text using Rekognition
    2. Detect language using Comprehend
    3. Translate text using Translate
    """

    try:
        # Extract S3 bucket and key from the event
        if "Records" in event:
            # S3 trigger event
            record = event["Records"][0]
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]
            target_language = "en"  # Default for S3 triggers
            provided_detected_text = None
            provided_detected_language = None
        else:
            # API Gateway event - parse the body
            if "body" in event and event["body"]:
                # Parse the JSON body from API Gateway
                body = (
                    json.loads(event["body"])
                    if isinstance(event["body"], str)
                    else event["body"]
                )
                bucket = body.get("bucket")
                key = body.get("key")
                target_language = body.get("targetLanguage", "en")
                provided_detected_text = body.get("detectedText")
                provided_detected_language = body.get("detectedLanguage")
            else:
                # Direct invocation (for testing)
                bucket = event.get("bucket")
                key = event.get("key")
                target_language = event.get("targetLanguage", "en")
                provided_detected_text = event.get("detectedText")
                provided_detected_language = event.get("detectedLanguage")

        if not bucket or not key:
            return {
                "statusCode": 400,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "POST",
                },
                "body": json.dumps({"error": "Missing bucket or key parameter"}),
            }

        # Initialize AWS clients
        rekognition = boto3.client("rekognition")
        comprehend = boto3.client("comprehend")
        translate_client = boto3.client("translate")

        # Step 1: Detect text using Rekognition (skip if already provided)
        if provided_detected_text and provided_detected_language:
            # Use provided text and language (for re-translation)
            detected_text = provided_detected_text
            detected_language = provided_detected_language
            print(f"Using provided text: {detected_text}")
            print(f"Using provided language: {detected_language}")
        else:
            # Detect text using Rekognition
            print(f"Detecting text in s3://{bucket}/{key}")

            rekognition_response = rekognition.detect_text(
                Image={"S3Object": {"Bucket": bucket, "Name": key}}
            )

            # Extract line-level text (more accurate than word-level)
            detected_lines = [
                text["DetectedText"]
                for text in rekognition_response["TextDetections"]
                if text["Type"] == "LINE"
            ]

            detected_text = " ".join(detected_lines)

            if not detected_text:
                return {
                    "statusCode": 200,
                    "headers": {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type",
                        "Access-Control-Allow-Methods": "POST",
                    },
                    "body": json.dumps(
                        {
                            "detectedText": "",
                            "detectedLanguage": "",
                            "translatedText": "",
                            "targetLanguage": target_language,
                            "message": "No text detected in image",
                        }
                    ),
                }

            # Step 2: Detect language using Comprehend
            print(f"Detected text: {detected_text}")

            comprehend_response = comprehend.detect_dominant_language(
                Text=detected_text
            )
            detected_language = comprehend_response["Languages"][0]["LanguageCode"]

            print(f"Detected language: {detected_language}")

        # Step 3: Translate to target language
        translated_text = detected_text
        if detected_language != target_language:
            translate_response = translate_client.translate_text(
                Text=detected_text,
                SourceLanguageCode=detected_language,
                TargetLanguageCode=target_language,
            )
            translated_text = translate_response["TranslatedText"]
            print(f"Translated text to {target_language}: {translated_text}")
        else:
            print(
                f"Text is already in target language ({target_language}), no translation needed"
            )

        # Return the results
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "POST",
            },
            "body": json.dumps(
                {
                    "detectedText": detected_text,
                    "detectedLanguage": detected_language,
                    "translatedText": translated_text,
                    "targetLanguage": target_language,
                    "bucket": bucket,
                    "key": key,
                }
            ),
        }

    except ClientError as e:
        print(f"AWS Client Error: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": f"AWS Error: {str(e)}"}),
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": f"Internal server error: {str(e)}"}),
        }
