"""Pytest configuration and fixtures."""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

import pytest
from PIL import Image

from main import AppConfig, OCRResult, OCRResponse
from src.gemini_ocr.ocr_client import GeminiOCR


@pytest.fixture
def app_config():
    """Create a test configuration."""
    return AppConfig(
        folder_id="test_folder_id",
        api_key="test_api_key",
        output_file="test_results.json",
        log_level=logging.DEBUG,
        max_concurrent_files=2,
        max_retries=2,
        retry_delay=0.1,
        retry_backoff_factor=2.0,
        max_retry_delay=1.0
    )


@pytest.fixture
def test_logger():
    """Create a test logger."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def mock_ocr_response():
    """Create a mock OCR response."""
    ocr_data = OCRResult(
        last_name="DOE",
        first_name="JOHN",
        passport_number="AB123456",
        nationality="USA"
    )
    return OCRResponse(ocr_data=ocr_data)


@pytest.fixture
def mock_ocr_client():
    """Create a mock OCR client."""
    mock_client = Mock(spec=GeminiOCR)
    mock_client.ocr = AsyncMock()
    return mock_client


@pytest.fixture
def sample_image_path():
    """Create a temporary sample image file."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
        # Create a simple test image
        image = Image.new('RGB', (100, 100), color='white')
        image.save(temp_file.name, 'JPEG')
        yield temp_file.name
        
        # Cleanup
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


@pytest.fixture
def temp_directory():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_results_data():
    """Sample OCR results data."""
    return [
        {
            "filename": "passport1.jpg",
            "file_path": "./downloads/passport1.jpg",
            "ocr_data": {
                "last_name": "SMITH",
                "first_name": "JANE",
                "passport_number": "CD789012",
                "nationality": "UK"
            }
        },
        {
            "filename": "passport2.jpg",
            "file_path": "./downloads/passport2.jpg",
            "error": "OCR processing failed"
        }
    ]


@pytest.fixture
def sample_files_list(temp_directory):
    """Create sample files for testing."""
    files = []
    for i in range(3):
        file_path = Path(temp_directory) / f"test_file_{i}.jpg"
        # Create dummy image files
        image = Image.new('RGB', (50, 50), color='red')
        image.save(file_path, 'JPEG')
        files.append(str(file_path))
    return files


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_existing_results():
    """Mock existing results for testing."""
    return {
        "existing_success.jpg": {
            "filename": "existing_success.jpg",
            "file_path": "./downloads/existing_success.jpg",
            "ocr_data": {
                "last_name": "EXISTING",
                "first_name": "USER",
                "passport_number": "EX123456",
                "nationality": "TEST"
            }
        },
        "existing_error.jpg": {
            "filename": "existing_error.jpg",
            "file_path": "./downloads/existing_error.jpg",
            "error": "Previous OCR error"
        }
    }