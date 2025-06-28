# AWS Translation Pipeline Demo

> **Complete End-to-End Translation Pipeline Demonstration**  
> Hands-on examples showcasing AWS Rekognition OCR, Comprehend language detection, and Translate multi-language capabilities with real image processing workflows.

This directory contains a complete demonstration of an AWS-based translation pipeline that extracts text from images, detects the language, and translates it to a target language.

## 🔧 Components

### Individual Pipeline Scripts (located in `pipeline/`)

1. **`detect_text.py`** - **AWS Rekognition OCR**: Extracts text from images using computer vision
2. **`detect_language.py`** - **AWS Comprehend NLP**: Detects the language of text using natural language processing  
3. **`translate_text.py`** - **AWS Translate**: Translates text between 75+ languages using machine translation

### Orchestration Scripts

- **`aws_pipeline.py`** - **Complete Pipeline Orchestrator**: Chains all three components in sequence, includes automatic S3 image upload and error handling
- **`test_components.py`** - **Unit Component Testing**: Tests individual components with sample data for validation

## 📋 Prerequisites

### AWS Configuration Requirements

1. **AWS Account** with appropriate IAM permissions
2. **AWS CLI** configured with credentials (`aws configure`)
3. **S3 Bucket** with sample images containing readable text
4. **Required AWS Service Permissions**:
   - **Rekognition**: `DetectText` (OCR text extraction)
   - **Comprehend**: `DetectDominantLanguage` (language identification)
   - **Translate**: `TranslateText` (text translation)
   - **S3**: `GetObject`, `PutObject` (image storage operations)

### Python Environment Dependencies

Install required packages:

```bash
pip install -r requirements.txt
```

### Configuration Setup

Update the configuration in `aws_pipeline.py`:

```python
bucket_name = "your-s3-bucket-name"  # Replace with your S3 bucket
image_name = "your-image.png"        # Replace with your test image
target_language = "en"               # Target language code (ISO 639-1)
```

**Note**: The `aws_pipeline.py` and `test_components.py` scripts will automatically upload `spanish_images/es1.png` to your S3 bucket if it's not already present.

## 🚀 Usage Guide

### Running Individual Components

**Test OCR text detection:**

```bash
python aws-demos/pipeline/detect_text.py
```

**Test language detection:**

```bash
python aws-demos/pipeline/detect_language.py
```

**Test machine translation:**

```bash
python aws-demos/pipeline/translate_text.py
```

### Running the Complete Pipeline

**Execute full translation workflow:**

```bash
python aws-demos/aws_pipeline.py
```

### Testing Components

**Run component validation tests:**

```bash
python aws-demos/test_components.py
```

## 🔄 Pipeline Workflow

1. **Text Detection**: Uses AWS Rekognition to extract text from an image stored in S3
2. **Language Detection**: Uses AWS Comprehend to identify the language of the extracted text
3. **Translation**: Uses AWS Translate to convert text to the target language (if needed)

## 📊 Sample Output

```log
==============================================================
AWS TRANSLATION PIPELINE
==============================================================
Processing image: es1.png
S3 Bucket: ajbarea
Target language: en
AWS Region: us-east-1

STEP 1: Detecting text from image...
----------------------------------------
Image s3://ajbarea/es1.png not found. Uploading from C:/ajsoftworks/aws-image-translate/spanish_images/es1.png...
Detected text
----------
Detected text:Hola
Confidence: 99.50%
Id: 0
Type:LINE

✓ Successfully detected 2 text elements
Combined text: 'Hola mundo'

STEP 2: Detecting language of extracted text...
--------------------------------------------------
Detected Language: es
Confidence: 0.99
✓ Language detected: es (confidence: 99.00%)

STEP 3: Translating text...
----------------------------------------
✓ Translation successful!

STEP 4: Cleaning up resources...
-----------------------------------
Resources cleaned up successfully
✓ Cleanup completed

==============================================================
PIPELINE SUMMARY
==============================================================
Image: es1.png
Original text: Hola mundo
Detected language: es (99.00% confidence)
Translated text: Hello world
==============================================================
🎉 Pipeline completed successfully!
```

## Error Handling

The pipeline includes comprehensive error handling:

- Failed text detection (no text found)
- Failed language detection (unsupported language)
- Failed translation (service errors)
- AWS service errors (permissions, connectivity)

## Supported Languages

### Rekognition Text Detection

Supports text in many languages including:

- English, Spanish, French, German, Italian, Portuguese
- Arabic, Russian, Chinese, Japanese, Korean
- And many more

### Comprehend Language Detection

Supports over 100 languages including all major world languages.

### Translate Language Support

Supports translation between 75+ languages. Common language codes:

- `en` - English
- `es` - Spanish  
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `zh` - Chinese
- `ja` - Japanese
- `ko` - Korean
- `ar` - Arabic
- `ru` - Russian

## Troubleshooting

### Common Issues

1. **"No credentials found"**
   - Ensure AWS CLI is configured: `aws configure`
   - Or set environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

2. **"Access Denied"**
   - Check IAM permissions for Rekognition, Comprehend, Translate, and S3
   - Ensure your AWS user/role has the required permissions

3. **"Bucket does not exist"**
   - Verify bucket name in the configuration
   - Ensure the bucket is in the correct AWS region

4. **"Image not found"**
   - Verify the image exists in the specified S3 bucket
   - Check the image filename and extension

5. **"Text not detected"**
   - Ensure the image contains readable text
   - Try images with clearer, larger text
   - Supported formats: JPEG, PNG

## Cost Considerations

AWS services used in this pipeline are pay-per-use:

- **Rekognition**: ~$0.001 per image for text detection
- **Comprehend**: ~$0.0001 per 100 characters for language detection  
- **Translate**: ~$15 per million characters translated
- **S3**: Standard storage and transfer costs

For development/testing, costs are typically minimal.

## Next Steps

- Integrate with the main application pipeline
- Add batch processing capabilities
- Implement result caching
- Add support for multiple target languages
- Create a web interface
- Add confidence thresholds for text/language detection
