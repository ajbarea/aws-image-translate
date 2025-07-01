import logging
from typing import Optional

import boto3

from config import AWS_REGION

logging.basicConfig(level=logging.INFO)


def detect_language(text: str) -> str:
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
            return str(languages[0]["LanguageCode"])
        return "en"  # Default to English if no language detected
    except Exception as e:
        logging.error(f"Error detecting language: {str(e)}")
        return "en"  # Default to English on error


def translate_text(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    translate = boto3.client(
        service_name="translate", region_name=AWS_REGION, use_ssl=True
    )
    result = translate.translate_text(
        Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang
    )
    translated_text = result.get("TranslatedText")
    return str(translated_text) if translated_text else None
