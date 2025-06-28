import boto3


def detect_text(photo, bucket):
    """
    Detect text from an image stored in S3 using AWS Rekognition.

    Args:
        photo (str): Image filename in S3
        bucket (str): S3 bucket name

    Returns:
        tuple: (text_count, combined_text) - Number of text detections and combined LINE text
    """
    if not photo or not bucket:
        print("Photo and bucket names are required")
        return 0, ""

    session = boto3.Session(profile_name="default")
    client = session.client("rekognition", region_name="us-east-1")

    try:
        response = client.detect_text(
            Image={"S3Object": {"Bucket": bucket, "Name": photo}}
        )

        text_detections = response["TextDetections"]
        print("Detected text\n----------")

        # Collect all detected text lines
        detected_text_lines = []

        for text in text_detections:
            print("Detected text:" + text["DetectedText"])
            print("Confidence: " + "{:.2f}".format(text["Confidence"]) + "%")
            print("Id: {}".format(text["Id"]))
            if "ParentId" in text:
                print("Parent Id: {}".format(text["ParentId"]))
            print("Type:" + text["Type"])
            print()

            # Only collect LINE type text for better language detection
            if text["Type"] == "LINE":
                detected_text_lines.append(text["DetectedText"])

        # Return both the count and the combined text
        combined_text = " ".join(detected_text_lines)
        return len(text_detections), combined_text

    except Exception as e:
        error_msg = str(e)
        if "InvalidS3ObjectException" in error_msg or "NoSuchKey" in error_msg:
            print(f"Error: Image '{photo}' not found in S3 bucket '{bucket}'")
            print("Please check that the image exists and you have proper permissions")
        else:
            print(f"Error detecting text: {e}")
        return 0, ""


def main():
    bucket = "ajbarea"
    photo = "es1.png"
    text_count, detected_text = detect_text(photo, bucket)
    print("Text detected: " + str(text_count))
    print("Combined text: " + detected_text)


if __name__ == "__main__":
    main()
