"""Interfaces with Amazon Translate and Comprehend services for language operations.

This module provides functionality for language detection and text translation using
AWS services. It uses Amazon Comprehend for language detection and Amazon Translate
for text translation between languages.
"""

import logging
from typing import Optional

import boto3

from config import AWS_REGION

logging.basicConfig(level=logging.INFO)


def detect_language(text: str) -> str:
    """Detects the primary language of the input text using Amazon Comprehend.

    Uses Amazon Comprehend's language detection capability to identify the dominant
    language in the provided text. If multiple languages are detected, returns the
    most confident detection.

    Args:
        text (str): The text content to analyze for language detection.

    Returns:
        str: The ISO language code of the detected language (e.g., 'en' for English,
            'es' for Spanish). Defaults to 'en' if no language is detected or in
            case of an error.

    Raises:
        Exception: Logs any AWS service errors and returns default 'en'.
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
    """Translates text from one language to another using Amazon Translate.

    Uses Amazon Translate service to perform machine translation of text content
    between specified languages.

    Args:
        text (str): The text to translate.
        source_lang (str): The ISO language code of the source text (e.g., 'en').
        target_lang (str): The ISO language code of the desired translation (e.g., 'es').

    Returns:
        Optional[str]: The translated text if successful, None if translation fails
            or no text is returned from the service.

    Raises:
        botocore.exceptions.BotoCoreError: If there's an AWS service error.
        botocore.exceptions.ClientError: If there's an error with the API request.
    """
    translate = boto3.client(
        service_name="translate", region_name=AWS_REGION, use_ssl=True
    )
    result = translate.translate_text(
        Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang
    )
    translated_text = result.get("TranslatedText")
    return str(translated_text) if translated_text else None
