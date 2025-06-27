import boto3
from config import AWS_REGION


def translate_text(text, source_lang, target_lang):
    translate = boto3.client(
        service_name="translate", region_name=AWS_REGION, use_ssl=True
    )
    result = translate.translate_text(
        Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang
    )
    return result.get("TranslatedText")
