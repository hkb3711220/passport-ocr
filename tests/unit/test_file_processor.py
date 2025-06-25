"""Unit tests for FileProcessor class."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

from main import FileProcessor, OCRResponse, OCRResult

pytestmark = pytest.mark.unit


class TestFileProcessor:
    """Test cases for FileProcessor class."""

    def test_init(self, test_logger):
        """Test FileProcessor initialization."""
        processor = FileProcessor(logger=test_logger)
        assert processor.logger == test_logger

    def test_is_image_file_valid_extensions(self, test_logger):
        """Test image file detection with valid extensions."""
        processor = FileProcessor(logger=test_logger)
        
        valid_images = [
            "test.png",
            "test.jpg", 
            "test.jpeg",
            "test.gif",
            "test.bmp",
            "TEST.PNG",  # Case insensitive
            "file.JPG"
        ]
        
        for image_path in valid_images:
            assert processor.is_image_file(image_path), f"Should detect {image_path} as image"

    def test_is_image_file_invalid_extensions(self, test_logger):
        """Test image file detection with invalid extensions."""
        processor = FileProcessor(logger=test_logger)
        
        invalid_files = [
            "test.pdf",
            "test.txt",
            "test.doc",
            "test.zip",
            "test",  # No extension
            "test."  # Empty extension
        ]
        
        for file_path in invalid_files:
            assert not processor.is_image_file(file_path), f"Should not detect {file_path} as image"

    def test_is_pdf_file_valid_extensions(self, test_logger):
        """Test PDF file detection with valid extensions."""
        processor = FileProcessor(logger=test_logger)
        
        valid_pdfs = [
            "document.pdf",
            "FILE.PDF",  # Case insensitive
            "test.Pdf"
        ]
        
        for pdf_path in valid_pdfs:
            assert processor.is_pdf_file(pdf_path), f"Should detect {pdf_path} as PDF"

    def test_is_pdf_file_invalid_extensions(self, test_logger):
        """Test PDF file detection with invalid extensions."""
        processor = FileProcessor(logger=test_logger)
        
        invalid_files = [
            "test.jpg",
            "test.txt",
            "test.doc",
            "test",  # No extension
            "test."  # Empty extension
        ]
        
        for file_path in invalid_files:
            assert not processor.is_pdf_file(file_path), f"Should not detect {file_path} as PDF"

    def test_is_supported_file(self, test_logger):
        """Test supported file detection."""
        processor = FileProcessor(logger=test_logger)
        
        supported_files = [
            "image.jpg",
            "document.pdf",
            "photo.PNG",
            "scan.PDF"
        ]
        
        unsupported_files = [
            "text.txt",
            "archive.zip",
            "document.doc"
        ]
        
        for file_path in supported_files:
            assert processor.is_supported_file(file_path), f"Should support {file_path}"
            
        for file_path in unsupported_files:
            assert not processor.is_supported_file(file_path), f"Should not support {file_path}"

    @patch('main.convert_from_path')
    @patch('os.path.exists')
    def test_convert_pdf_to_images_success(self, mock_exists, mock_convert, test_logger):
        """Test successful PDF to images conversion."""
        processor = FileProcessor(logger=test_logger)
        
        # Mock successful conversion
        mock_image = Mock()
        mock_convert.return_value = [mock_image, mock_image]  # 2 pages
        mock_exists.return_value = True  # Poppler exists
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test_page_1.png"
            mock_temp.return_value = mock_temp_file
            
            result = processor.convert_pdf_to_images("test.pdf")
            
            assert len(result) == 2
            assert mock_convert.called

    @patch('main.convert_from_path')
    def test_convert_pdf_to_images_failure(self, mock_convert, test_logger):
        """Test PDF to images conversion failure."""
        processor = FileProcessor(logger=test_logger)
        
        mock_convert.side_effect = Exception("PDF conversion failed")
        
        result = processor.convert_pdf_to_images("test.pdf")
        
        assert result == []

    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_temp_files_success(self, mock_unlink, mock_exists, test_logger):
        """Test successful cleanup of temporary files."""
        processor = FileProcessor(logger=test_logger)
        
        mock_exists.return_value = True
        temp_files = ["/tmp/file1.png", "/tmp/file2.png"]
        
        processor.cleanup_temp_files(temp_files)
        
        assert mock_unlink.call_count == 2
        mock_unlink.assert_any_call("/tmp/file1.png")
        mock_unlink.assert_any_call("/tmp/file2.png")

    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_temp_files_with_errors(self, mock_unlink, mock_exists, test_logger):
        """Test cleanup with some files failing to delete."""
        processor = FileProcessor(logger=test_logger)
        
        mock_exists.return_value = True
        mock_unlink.side_effect = [None, Exception("Permission denied")]
        temp_files = ["/tmp/file1.png", "/tmp/file2.png"]
        
        # Should not raise exception
        processor.cleanup_temp_files(temp_files)
        
        assert mock_unlink.call_count == 2

    def test_load_existing_results_file_not_exists(self, test_logger):
        """Test loading results when file doesn't exist."""
        processor = FileProcessor(logger=test_logger)
        
        result = processor.load_existing_results("nonexistent.json")
        
        assert result == {}

    def test_load_existing_results_success(self, test_logger, sample_results_data):
        """Test successful loading of existing results."""
        processor = FileProcessor(logger=test_logger)
        
        with patch('builtins.open', mock_open(read_data=json.dumps(sample_results_data))):
            with patch('os.path.exists', return_value=True):
                result = processor.load_existing_results("results.json")
        
        assert len(result) == 2
        assert "passport1.jpg" in result
        assert "passport2.jpg" in result

    def test_load_existing_results_invalid_json(self, test_logger):
        """Test loading results with invalid JSON."""
        processor = FileProcessor(logger=test_logger)
        
        with patch('builtins.open', mock_open(read_data="invalid json")):
            with patch('os.path.exists', return_value=True):
                result = processor.load_existing_results("results.json")
        
        assert result == {}

    def test_is_already_processed_not_in_results(self, test_logger):
        """Test file that hasn't been processed."""
        processor = FileProcessor(logger=test_logger)
        existing_results = {}
        
        result = processor.is_already_processed("new_file.jpg", existing_results)
        
        assert result is False

    def test_is_already_processed_with_error(self, test_logger):
        """Test file that was processed but had error."""
        processor = FileProcessor(logger=test_logger)
        existing_results = {
            "error_file.jpg": {
                "filename": "error_file.jpg",
                "error": "Previous error"
            }
        }
        
        result = processor.is_already_processed("error_file.jpg", existing_results)
        
        assert result is False  # Should retry files with errors

    def test_is_already_processed_success(self, test_logger):
        """Test file that was processed successfully."""
        processor = FileProcessor(logger=test_logger)
        existing_results = {
            "success_file.jpg": {
                "filename": "success_file.jpg",
                "ocr_data": {"last_name": "TEST"}
            }
        }
        
        result = processor.is_already_processed("success_file.jpg", existing_results)
        
        assert result is True

    def test_create_result_entry(self, test_logger, mock_ocr_response):
        """Test creating result entry from OCR response."""
        processor = FileProcessor(logger=test_logger)
        
        result = processor.create_result_entry(mock_ocr_response, "/path/to/test.jpg")
        
        assert result["filename"] == "test.jpg"
        assert result["file_path"] == "/path/to/test.jpg"
        assert result["ocr_data"] == mock_ocr_response.ocr_data

    def test_create_error_entry(self, test_logger):
        """Test creating error entry for failed processing."""
        processor = FileProcessor(logger=test_logger)
        
        error = Exception("Test error message")
        result = processor.create_error_entry("/path/to/test.jpg", error)
        
        assert result["filename"] == "test.jpg"
        assert result["file_path"] == "/path/to/test.jpg"
        assert result["error"] == "Test error message"

    def test_file_path_handling(self, test_logger):
        """Test proper handling of different file path formats."""
        processor = FileProcessor(logger=test_logger)
        
        test_cases = [
            ("/absolute/path/file.jpg", "file.jpg"),
            ("relative/path/file.jpg", "file.jpg"),
            ("file.jpg", "file.jpg"),
            ("./file.jpg", "file.jpg"),
            ("../file.jpg", "file.jpg")
        ]
        
        for file_path, expected_filename in test_cases:
            result = processor.create_error_entry(file_path, Exception("test"))
            assert result["filename"] == expected_filename