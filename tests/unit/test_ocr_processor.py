"""Unit tests for OCRProcessor class."""

import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import pytest

from main import OCRProcessor, FileProcessor, ResultDisplayer

pytestmark = pytest.mark.unit


class TestOCRProcessor:
    """Test cases for OCRProcessor class."""

    @pytest.fixture
    def mock_file_processor(self):
        """Create a mock FileProcessor."""
        mock = Mock(spec=FileProcessor)
        mock.load_existing_results.return_value = {}
        mock.is_already_processed.return_value = False
        mock.is_supported_file.return_value = True
        mock.is_image_file.return_value = True
        mock.is_pdf_file.return_value = False
        mock.create_result_entry.return_value = {"filename": "test.jpg", "ocr_data": {}}
        mock.create_error_entry.return_value = {"filename": "test.jpg", "error": "Test error"}
        return mock

    @pytest.fixture
    def mock_result_displayer(self):
        """Create a mock ResultDisplayer."""
        return Mock(spec=ResultDisplayer)

    @pytest.fixture
    def ocr_processor(self, mock_ocr_client, mock_file_processor, mock_result_displayer, 
                     test_logger, app_config):
        """Create OCRProcessor instance with mocked dependencies."""
        return OCRProcessor(
            ocr_client=mock_ocr_client,
            file_processor=mock_file_processor,
            result_displayer=mock_result_displayer,
            logger=test_logger,
            output_file="test_output.json",
            config=app_config
        )

    def test_init(self, ocr_processor, mock_ocr_client, mock_file_processor, 
                  mock_result_displayer, test_logger, app_config):
        """Test OCRProcessor initialization."""
        assert ocr_processor.ocr_client == mock_ocr_client
        assert ocr_processor.file_processor == mock_file_processor
        assert ocr_processor.result_displayer == mock_result_displayer
        assert ocr_processor.logger == test_logger
        assert ocr_processor.config == app_config
        assert ocr_processor.output_file == "test_output.json"
        assert ocr_processor.retry_handler is not None

    @pytest.mark.asyncio
    async def test_process_single_image_success(self, ocr_processor, mock_ocr_client, 
                                               mock_ocr_response, mock_file_processor,
                                               mock_result_displayer):
        """Test successful single image processing."""
        mock_ocr_client.ocr.return_value = mock_ocr_response
        mock_file_processor.create_result_entry.return_value = {
            "filename": "test.jpg",
            "ocr_data": mock_ocr_response.ocr_data
        }
        
        result = await ocr_processor.process_single_image("test.jpg")
        
        assert result["filename"] == "test.jpg"
        assert "ocr_data" in result
        mock_result_displayer.display_ocr_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_image_with_original_filename(self, ocr_processor, 
                                                              mock_ocr_client, mock_ocr_response,
                                                              mock_file_processor):
        """Test single image processing with original filename."""
        mock_ocr_client.ocr.return_value = mock_ocr_response
        
        result = await ocr_processor.process_single_image("temp.jpg", "original.pdf")
        
        assert result["filename"] == "original.pdf"
        assert "original_file_path" in result

    @pytest.mark.asyncio
    async def test_process_single_image_failure(self, ocr_processor, mock_ocr_client,
                                               mock_file_processor):
        """Test single image processing failure."""
        mock_ocr_client.ocr.side_effect = Exception("OCR failed")
        mock_file_processor.create_error_entry.return_value = {
            "filename": "test.jpg",
            "error": "OCR failed"
        }
        
        result = await ocr_processor.process_single_image("test.jpg")
        
        assert "error" in result
        assert result["error"] == "OCR failed"

    @pytest.mark.asyncio
    async def test_process_single_file_unsupported(self, ocr_processor, mock_file_processor):
        """Test processing unsupported file type."""
        mock_file_processor.is_supported_file.return_value = False
        
        result = await ocr_processor.process_single_file("test.txt")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_process_single_file_already_processed(self, ocr_processor, mock_file_processor):
        """Test processing file that's already been processed."""
        mock_file_processor.is_already_processed.return_value = True
        ocr_processor.existing_results = {"test.jpg": {"filename": "test.jpg", "ocr_data": {}}}
        
        result = await ocr_processor.process_single_file("test.jpg")
        
        assert result == {"filename": "test.jpg", "ocr_data": {}}

    @pytest.mark.asyncio
    async def test_process_single_file_image(self, ocr_processor, mock_file_processor,
                                            mock_ocr_client, mock_ocr_response):
        """Test processing single image file."""
        mock_file_processor.is_image_file.return_value = True
        mock_file_processor.is_pdf_file.return_value = False
        mock_ocr_client.ocr.return_value = mock_ocr_response
        
        with patch.object(ocr_processor, 'process_single_image', return_value={"success": True}) as mock_process:
            result = await ocr_processor.process_single_file("test.jpg")
            
            mock_process.assert_called_once_with("test.jpg")
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_process_single_file_pdf(self, ocr_processor, mock_file_processor):
        """Test processing single PDF file."""
        mock_file_processor.is_image_file.return_value = False
        mock_file_processor.is_pdf_file.return_value = True
        
        with patch.object(ocr_processor, 'process_pdf_file', return_value={"pdf_result": True}) as mock_process:
            result = await ocr_processor.process_single_file("test.pdf")
            
            mock_process.assert_called_once_with("test.pdf")
            assert result == {"pdf_result": True}

    @pytest.mark.asyncio
    async def test_process_pdf_file_success(self, ocr_processor, mock_file_processor,
                                           mock_ocr_client, mock_ocr_response):
        """Test successful PDF processing."""
        mock_file_processor.convert_pdf_to_images.return_value = ["page1.png", "page2.png"]
        mock_ocr_client.ocr.return_value = mock_ocr_response
        
        with patch.object(ocr_processor, 'process_single_image') as mock_process:
            mock_process.return_value = {"filename": "test.pdf (page 1)", "ocr_data": {}}
            
            result = await ocr_processor.process_pdf_file("test.pdf")
            
            assert result["filename"] == "test.pdf"
            assert result["source_type"] == "pdf"
            assert result["total_pages"] == 2
            assert result["pages_processed"] == 2

    @pytest.mark.asyncio
    async def test_process_pdf_file_conversion_failed(self, ocr_processor, mock_file_processor):
        """Test PDF processing when conversion fails."""
        mock_file_processor.convert_pdf_to_images.return_value = []
        mock_file_processor.create_error_entry.return_value = {
            "filename": "test.pdf",
            "error": "Failed to convert PDF to images"
        }
        
        result = await ocr_processor.process_pdf_file("test.pdf")
        
        assert "error" in result

    @pytest.mark.asyncio
    async def test_process_all_files_no_new_files(self, ocr_processor, mock_file_processor):
        """Test processing when no new files need processing."""
        mock_file_processor.is_already_processed.return_value = True
        ocr_processor.existing_results = {"test.jpg": {"filename": "test.jpg", "ocr_data": {}}}
        
        result = await ocr_processor.process_all_files(["test.jpg"])
        
        assert len(result) == 1  # Only existing successful result

    @pytest.mark.asyncio
    async def test_process_all_files_batch_processing(self, ocr_processor, mock_file_processor,
                                                     mock_ocr_client, mock_ocr_response):
        """Test batch processing of multiple files."""
        files = ["file1.jpg", "file2.jpg", "file3.jpg"]
        
        mock_file_processor.is_already_processed.return_value = False
        mock_ocr_client.ocr.return_value = mock_ocr_response
        
        with patch.object(ocr_processor, 'process_single_file') as mock_process:
            mock_process.return_value = {"filename": "test.jpg", "ocr_data": {}}
            
            result = await ocr_processor.process_all_files(files)
            
            assert len(result) == 3
            assert mock_process.call_count == 3

    @pytest.mark.asyncio
    async def test_process_all_files_with_existing_results(self, ocr_processor, mock_file_processor):
        """Test processing with mix of new files and existing results."""
        ocr_processor.existing_results = {
            "existing_success.jpg": {"filename": "existing_success.jpg", "ocr_data": {}},
            "existing_error.jpg": {"filename": "existing_error.jpg", "error": "Previous error"}
        }
        
        def mock_is_processed(file_path, existing_results):
            filename = Path(file_path).name
            return filename == "existing_success.jpg"
        
        mock_file_processor.is_already_processed.side_effect = mock_is_processed
        
        with patch.object(ocr_processor, 'process_single_file') as mock_process:
            mock_process.return_value = {"filename": "new.jpg", "ocr_data": {}}
            
            files = ["existing_success.jpg", "existing_error.jpg", "new_file.jpg"]
            result = await ocr_processor.process_all_files(files)
            
            # Should have existing success + retried error + new file
            assert len(result) >= 2
            assert mock_process.call_count == 2  # Only processes error retry and new file

    @pytest.mark.asyncio
    async def test_process_all_files_concurrency_limit(self, ocr_processor, mock_file_processor,
                                                      app_config):
        """Test that concurrency is properly limited."""
        files = ["file1.jpg", "file2.jpg", "file3.jpg", "file4.jpg", "file5.jpg"]
        app_config.max_concurrent_files = 2
        
        mock_file_processor.is_already_processed.return_value = False
        
        call_times = []
        
        async def mock_process_file(file_path):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)  # Simulate processing time
            return {"filename": Path(file_path).name, "ocr_data": {}}
        
        with patch.object(ocr_processor, 'process_single_file', side_effect=mock_process_file):
            await ocr_processor.process_all_files(files)
            
            # Check that not all files started processing at the same time
            # (due to semaphore limiting concurrency)
            assert len(call_times) == 5
            
            # First two should start almost immediately
            assert call_times[1] - call_times[0] < 0.05
            
            # Subsequent calls should be delayed
            assert call_times[2] - call_times[0] >= 0.08

    @pytest.mark.asyncio
    async def test_process_all_files_exception_handling(self, ocr_processor, mock_file_processor):
        """Test exception handling in batch processing."""
        files = ["file1.jpg", "file2.jpg"]
        
        mock_file_processor.is_already_processed.return_value = False
        mock_file_processor.create_error_entry.return_value = {"filename": "file1.jpg", "error": "Test error"}
        
        async def mock_process_file(file_path):
            if "file1" in file_path:
                raise Exception("Processing error")
            return {"filename": "file2.jpg", "ocr_data": {}}
        
        with patch.object(ocr_processor, 'process_single_file', side_effect=mock_process_file):
            result = await ocr_processor.process_all_files(files)
            
            assert len(result) == 2
            # Should handle exceptions gracefully and continue processing other files

    @pytest.mark.asyncio
    async def test_retry_integration(self, ocr_processor, mock_ocr_client, mock_file_processor):
        """Test integration with retry handler."""
        mock_file_processor.is_already_processed.return_value = False
        mock_file_processor.is_image_file.return_value = True
        mock_file_processor.is_pdf_file.return_value = False
        
        # Mock OCR to fail twice then succeed
        mock_ocr_client.ocr.side_effect = [
            Exception("First failure"),
            Exception("Second failure"), 
            {"ocr_data": {"last_name": "SUCCESS"}}
        ]
        
        result = await ocr_processor.process_single_file("test.jpg")
        
        # Should have retried and eventually succeeded
        assert mock_ocr_client.ocr.call_count == 3
        assert result is not None