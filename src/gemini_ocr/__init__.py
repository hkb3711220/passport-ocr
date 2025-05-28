"""Gemini OCR package for text extraction from images using Google's Gemini model."""

from .ocr_client import GeminiOCR, GeminiOCRError, ImageProcessingError, ModelError

__version__ = "1.0.0"
__author__ = "Your Name"

__all__ = [
    "GeminiOCR",
    "GeminiOCRError",
    "ImageProcessingError",
    "ModelError"
]
