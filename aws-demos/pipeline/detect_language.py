import boto3


def detect_language(text):
    """
    Detect the language of the given text using AWS Comprehend.

    Args:
        text (str): The text to analyze for language detection

    Returns:
        dict: Language detection results with language code and confidence score
    """
    if not text or not text.strip():
        print("No text provided for language detection")
        return None

    session = boto3.Session(profile_name="default")
    comprehend = session.client("comprehend", region_name="us-east-1")

    try:
        response = comprehend.detect_dominant_language(Text=text)
        languages = response["Languages"]

        if languages:
            dominant_language = languages[0]
            language_code = dominant_language["LanguageCode"]
            confidence = dominant_language["Score"]

            print(f"Detected Language: {language_code}")
            print(f"Confidence: {confidence:.2f}")

            return {
                "language_code": language_code,
                "confidence": confidence,
                "all_languages": languages,
            }
        else:
            print("No language detected")
            return None

    except Exception as e:
        print(f"Error detecting language: {e}")
        return None


def main():
    test_text = "Hola, ¿cómo estás? Me llamo María y vivo en España."

    print("Analyzing text:", test_text)
    print("-" * 50)

    result = detect_language(test_text)

    if result:
        print(
            f"\nResult: Detected {result['language_code']} with {result['confidence']:.2%} confidence"
        )
    else:
        print("\nFailed to detect language")


if __name__ == "__main__":
    main()
