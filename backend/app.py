from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.amazon_rekognition import detect_text_from_s3
from src.amazon_translate import detect_language, translate_text

app = FastAPI(title="AWS Image Translate Backend")

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcessRequest(BaseModel):
    bucket: str
    key: str
    targetLanguage: str
    detectedText: Optional[str] = None
    detectedLanguage: Optional[str] = None


class ProcessResponse(BaseModel):
    detectedText: Optional[str]
    detectedLanguage: Optional[str]
    translatedText: Optional[str]
    targetLanguage: str


@app.get("/health")
async def health_check():
    """Health check endpoint - no authentication required"""
    return {"status": "healthy", "service": "aws-image-translate-backend"}


@app.post("/process", response_model=ProcessResponse)
async def process_image(request: ProcessRequest):
    """
    Process an image: detect text and translate it.
    Note: Authentication temporarily disabled for development
    """
    print(f"Processing image: {request.key}")

    try:
        # If no detectedText provided, run detection and translation pipeline
        if not request.detectedText:
            detected = detect_text_from_s3(request.key, request.bucket)
            if not detected:
                return ProcessResponse(
                    detectedText="",
                    detectedLanguage=None,
                    translatedText=None,
                    targetLanguage=request.targetLanguage,
                )
            source_lang = detect_language(detected)
            translated = translate_text(
                detected,
                source_lang=source_lang,
                target_lang=request.targetLanguage,
            )
            return ProcessResponse(
                detectedText=detected,
                detectedLanguage=source_lang,
                translatedText=translated,
                targetLanguage=request.targetLanguage,
            )
        # Else, re-translate existing text
        else:
            if not request.detectedLanguage:
                # fallback detect if missing
                source_lang = detect_language(request.detectedText)
            else:
                source_lang = request.detectedLanguage
            translated = translate_text(
                request.detectedText,
                source_lang=source_lang,
                target_lang=request.targetLanguage,
            )
            return ProcessResponse(
                detectedText=request.detectedText,
                detectedLanguage=source_lang,
                translatedText=translated,
                targetLanguage=request.targetLanguage,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
