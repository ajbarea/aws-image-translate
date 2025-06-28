import boto3


def translate_text(text, source_lang, target_lang="en"):
    """
    Translate text from source language to target language.

    Args:
        text (str): Text to translate
        source_lang (str): Source language code (e.g., 'es', 'fr', 'de')
        target_lang (str): Target language code (default: 'en')

    Returns:
        str: Translated text or None if translation fails
    """
    if not text or not text.strip():
        print("No text provided for translation")
        return None

    translate = boto3.client(
        service_name="translate", region_name="us-east-1", use_ssl=True
    )

    try:
        result = translate.translate_text(
            Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang
        )

        translated_text = result.get("TranslatedText")

        print(f"Original Text: {text}")
        print(f"TranslatedText: {translated_text}")
        print(f"SourceLanguageCode: {result.get('SourceLanguageCode')}")
        print(f"TargetLanguageCode: {result.get('TargetLanguageCode')}")

        return translated_text

    except Exception as e:
        print(f"Error translating text: {e}")
        return None


def main():
    text = "Hola, mundo"
    source_lang = "es"
    target_lang = "en"

    print(f"Translating '{text}' from {source_lang} to {target_lang}")
    print("-" * 50)

    result = translate_text(text, source_lang, target_lang)

    if result:
        print("\nTranslation successful!")
    else:
        print("\nTranslation failed!")


if __name__ == "__main__":
    main()
