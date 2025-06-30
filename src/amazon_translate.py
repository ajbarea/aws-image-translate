import boto3
from config import AWS_REGION
import logging

logging.basicConfig(level=logging.INFO)


def detect_language(text):
    """
    Detect the language of the input text using Amazon Comprehend.

    Args:
        text (str): Text to detect language for

    Returns:
        str: ISO language code of the detected language
    """
    comprehend = boto3.client("comprehend", region_name=AWS_REGION)
    try:
        response = comprehend.detect_dominant_language(Text=text)
        languages = response["Languages"]
        if languages:
            # Return the language code of the most confident detection
            return languages[0]["LanguageCode"]
        return "en"  # Default to English if no language detected
    except Exception as e:
        logging.error(f"Error detecting language: {str(e)}")
        return "en"  # Default to English on error


def translate_text(text, source_lang, target_lang):
    translate = boto3.client(
        service_name="translate", region_name=AWS_REGION, use_ssl=True
    )
    result = translate.translate_text(
        Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang
    )
    return result.get("TranslatedText")
