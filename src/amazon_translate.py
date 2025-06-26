"""Amazon Translate utility functions for translating text between languages.

This module provides a function to translate text using AWS Translate.
"""

import boto3
from config import AWS_REGION


def translate_text(text, source_lang, target_lang):
    """Translate text from a source language to a target language using Amazon Translate.

    Args:
        text (str): The text to translate.
        source_lang (str): The source language code (e.g., 'es' for Spanish).
        target_lang (str): The target language code (e.g., 'en' for English).

    Returns:
        str: The translated text returned by Amazon Translate.

    Raises:
        botocore.exceptions.BotoCoreError: If the AWS SDK encounters a low-level error.
        botocore.exceptions.ClientError: If the Translate API call fails.
    """
    translate = boto3.client(
        service_name="translate", region_name=AWS_REGION, use_ssl=True
    )
    result = translate.translate_text(
        Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang
    )
    return result.get("TranslatedText")
