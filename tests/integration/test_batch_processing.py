"""Integration tests for batch processing functionality."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import pytest
from PIL import Image

from main import (
    PassportOCRApplication, AppConfig, OCRProcessor, FileProcessor, 
    ResultDisplayer, ResultSaver, ProgressTracker, RetryHandler,
    OCRResponse, OCRResult
)
from src.gemini_ocr.ocr_client import GeminiOCR

pytestmark = pytest.mark.integration


class TestBatchProcessingIntegration:
    """Integration tests for batch processing system."""

    @pytest.fixture
    def integration_config(self, temp_directory):
        """Create integration test configuration."""
        return AppConfig(
            folder_id="test_folder_id",
            api_key="test_api_key",
            output_file=os.path.join(temp_directory, "integration_results.json"),
            max_concurrent_files=2,
            max_retries=2,
            retry_delay=0.01,  # Fast retries for testing
            retry_backoff_factor=2.0,
            max_retry_delay=0.1
        )

    @pytest.fixture
    def mock_drive_client(self, sample_files_list):
        """Create a mock DriveClient that returns sample files."""
        mock_client = Mock()
        mock_client.download_all_files.return_value = sample_files_list
        return mock_client

    @pytest.fixture
    def sample_ocr_responses(self):
        """Create sample OCR responses for testing."""
        responses = []
        for i in range(3):
            ocr_data = OCRResult(
                last_name=f"LASTNAME{i}",
                first_name=f"FIRSTNAME{i}",
                passport_number=f"AB{i:06d}",
                nationality="TEST"
            )
            responses.append(OCRResponse(ocr_data=ocr_data))
        return responses

    @pytest.mark.asyncio
    async def test_end_to_end_batch_processing(self, integration_config, sample_files_list, 
                                              sample_ocr_responses, test_logger):
        """Test complete end-to-end batch processing workflow."""
        # Create mock OCR client
        mock_ocr_client = Mock(spec=GeminiOCR)
        mock_ocr_client.ocr = AsyncMock()
        mock_ocr_client.ocr.side_effect = sample_ocr_responses

        # Create processors
        file_processor = FileProcessor(test_logger)
        result_displayer = ResultDisplayer()
        result_saver = ResultSaver(test_logger)

        # Create OCR processor
        ocr_processor = OCRProcessor(
            ocr_client=mock_ocr_client,
            file_processor=file_processor,
            result_displayer=result_displayer,
            logger=test_logger,
            output_file=integration_config.output_file,
            config=integration_config
        )

        # Process files
        results = await ocr_processor.process_all_files(sample_files_list)

        # Verify results
        assert len(results) == 3
        for i, result in enumerate(results):
            assert "filename" in result
            assert "ocr_data" in result
            assert result["ocr_data"]["last_name"] == f"LASTNAME{i}"

        # Verify OCR client was called for each file
        assert mock_ocr_client.ocr.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_processing_with_failures_and_retries(self, integration_config, 
                                                             sample_files_list, test_logger):
        """Test batch processing with some failures and successful retries."""
        # Create mock OCR client with failures
        mock_ocr_client = Mock(spec=GeminiOCR)
        mock_ocr_client.ocr = AsyncMock()
        
        # First file: success on first try
        # Second file: fail twice, then succeed
        # Third file: always fail
        ocr_data = OCRResult(
            last_name="SUCCESS",
            first_name="TEST",
            passport_number="AB123456",
            nationality="TEST"
        )
        success_response = OCRResponse(ocr_data=ocr_data)
        
        mock_ocr_client.ocr.side_effect = [
            success_response,  # File 1: immediate success
            Exception("Temporary failure"),  # File 2: first attempt fails
            Exception("Temporary failure"),  # File 2: second attempt fails
            success_response,  # File 2: third attempt succeeds
            Exception("Permanent failure"),  # File 3: first attempt fails
            Exception("Permanent failure"),  # File 3: second attempt fails
            Exception("Permanent failure"),  # File 3: third attempt fails
        ]

        # Create processors
        file_processor = FileProcessor(test_logger)
        result_displayer = ResultDisplayer()

        ocr_processor = OCRProcessor(
            ocr_client=mock_ocr_client,
            file_processor=file_processor,
            result_displayer=result_displayer,
            logger=test_logger,
            output_file=integration_config.output_file,
            config=integration_config
        )

        # Process files
        results = await ocr_processor.process_all_files(sample_files_list)

        # Verify results
        assert len(results) == 3
        
        # Check that we have the right mix of successes and failures
        successful_results = [r for r in results if "ocr_data" in r]
        failed_results = [r for r in results if "error" in r]
        
        assert len(successful_results) == 2  # Two files should succeed
        assert len(failed_results) == 1     # One file should fail permanently

        # Verify retry logic was used (actual calls may vary due to concurrent processing)
        assert mock_ocr_client.ocr.call_count >= 5  # At least 5 attempts should be made

    @pytest.mark.asyncio
    async def test_concurrent_processing_behavior(self, integration_config, test_logger):
        """Test that concurrent processing actually processes files in parallel."""
        # Create more files than max_concurrent_files to test queuing
        num_files = 5
        integration_config.max_concurrent_files = 2
        
        # Create temporary files
        temp_files = []
        for i in range(num_files):
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                image = Image.new('RGB', (50, 50), color='red')
                image.save(temp_file.name, 'JPEG')
                temp_files.append(temp_file.name)

        try:
            # Track timing of OCR calls
            call_times = []
            
            async def mock_ocr_with_timing(*args, **kwargs):
                call_times.append(asyncio.get_event_loop().time())
                await asyncio.sleep(0.1)  # Simulate processing time
                ocr_data = OCRResult(
                    last_name="TEST",
                    first_name="USER",
                    passport_number="AB123456",
                    nationality="TEST"
                )
                return OCRResponse(ocr_data=ocr_data)

            # Create mock OCR client
            mock_ocr_client = Mock(spec=GeminiOCR)
            mock_ocr_client.ocr = AsyncMock(side_effect=mock_ocr_with_timing)

            # Create processors
            file_processor = FileProcessor(test_logger)
            result_displayer = ResultDisplayer()

            ocr_processor = OCRProcessor(
                ocr_client=mock_ocr_client,
                file_processor=file_processor,
                result_displayer=result_displayer,
                logger=test_logger,
                output_file=integration_config.output_file,
                config=integration_config
            )

            # Process files
            results = await ocr_processor.process_all_files(temp_files)

            # Verify all files were processed
            assert len(results) == num_files
            assert len(call_times) == num_files

            # Verify concurrency: first two calls should start almost simultaneously
            time_diff_first_two = call_times[1] - call_times[0]
            assert time_diff_first_two < 0.05, "First two calls should start concurrently"

            # Verify queuing: later calls should be delayed due to semaphore
            time_diff_first_third = call_times[2] - call_times[0]
            assert time_diff_first_third >= 0.08, "Third call should be queued"

        finally:
            # Cleanup temporary files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_progress_tracking_integration(self, integration_config, sample_files_list, 
                                                test_logger):
        """Test progress tracking during batch processing."""
        # Create mock OCR client
        mock_ocr_client = Mock(spec=GeminiOCR)
        
        # Mix of success and failure responses
        ocr_data = OCRResult(
            last_name="TEST",
            first_name="USER", 
            passport_number="AB123456",
            nationality="TEST"
        )
        success_response = OCRResponse(ocr_data=ocr_data)
        
        mock_ocr_client.ocr = AsyncMock()
        mock_ocr_client.ocr.side_effect = [
            success_response,
            Exception("OCR failed"),
            success_response
        ]

        # Create processors
        file_processor = FileProcessor(test_logger)
        result_displayer = ResultDisplayer()

        ocr_processor = OCRProcessor(
            ocr_client=mock_ocr_client,
            file_processor=file_processor,
            result_displayer=result_displayer,
            logger=test_logger,
            output_file=integration_config.output_file,
            config=integration_config
        )

        # Mock progress tracker to capture updates
        progress_updates = []
        
        with patch('main.ProgressTracker') as MockProgressTracker:
            mock_tracker = Mock()
            mock_tracker.update_progress = Mock(side_effect=lambda **kwargs: progress_updates.append(kwargs))
            mock_tracker.display_progress = Mock()
            mock_tracker.display_final_summary = Mock()
            MockProgressTracker.return_value = mock_tracker

            # Process files
            results = await ocr_processor.process_all_files(sample_files_list)

            # Verify progress tracking was used
            MockProgressTracker.assert_called_once_with(3, test_logger)
            
            # Should have progress updates for each file
            assert len(progress_updates) == 3
            
            # Check success/failure tracking
            success_count = sum(1 for update in progress_updates if update.get('success', False))
            failure_count = sum(1 for update in progress_updates if not update.get('success', True))
            
            assert success_count == 2  # Two successful files
            assert failure_count == 1  # One failed file

    @pytest.mark.asyncio
    async def test_existing_results_integration(self, integration_config, sample_files_list, 
                                               test_logger):
        """Test integration with existing results file."""
        # Create existing results file
        existing_results = [
            {
                "filename": Path(sample_files_list[0]).name,
                "file_path": sample_files_list[0],
                "ocr_data": {
                    "last_name": "EXISTING",
                    "first_name": "USER",
                    "passport_number": "EX123456",
                    "nationality": "EXISTING"
                }
            },
            {
                "filename": Path(sample_files_list[1]).name,
                "file_path": sample_files_list[1],
                "error": "Previous error - should retry"
            }
        ]

        # Write existing results to file
        with open(integration_config.output_file, 'w', encoding='utf-8') as f:
            json.dump(existing_results, f)

        # Create mock OCR client (should only be called for retry and new file)
        mock_ocr_client = Mock(spec=GeminiOCR)
        ocr_data = OCRResult(
            last_name="NEW",
            first_name="RESULT",
            passport_number="NR123456",
            nationality="NEW"
        )
        mock_ocr_client.ocr = AsyncMock(return_value=OCRResponse(ocr_data=ocr_data))

        # Create processors
        file_processor = FileProcessor(test_logger)
        result_displayer = ResultDisplayer()

        ocr_processor = OCRProcessor(
            ocr_client=mock_ocr_client,
            file_processor=file_processor,
            result_displayer=result_displayer,
            logger=test_logger,
            output_file=integration_config.output_file,
            config=integration_config
        )

        # Process files
        results = await ocr_processor.process_all_files(sample_files_list)

        # Verify results
        assert len(results) == 3

        # First file should use existing successful result
        existing_result = next(r for r in results if r.get("ocr_data", {}).get("last_name") == "EXISTING")
        assert existing_result is not None

        # Should have processed retry file and new file
        new_results = [r for r in results if r.get("ocr_data", {}).get("last_name") == "NEW"]
        assert len(new_results) == 2  # Retry + new file

        # OCR client should only be called twice (retry + new file)
        assert mock_ocr_client.ocr.call_count == 2

    @pytest.mark.asyncio
    async def test_result_saving_integration(self, integration_config, sample_files_list, 
                                            sample_ocr_responses, test_logger):
        """Test integration with result saving."""
        # Create mock OCR client
        mock_ocr_client = Mock(spec=GeminiOCR)
        mock_ocr_client.ocr = AsyncMock()
        mock_ocr_client.ocr.side_effect = sample_ocr_responses

        # Create processors
        file_processor = FileProcessor(test_logger)
        result_displayer = ResultDisplayer()
        result_saver = ResultSaver(test_logger)

        ocr_processor = OCRProcessor(
            ocr_client=mock_ocr_client,
            file_processor=file_processor,
            result_displayer=result_displayer,
            logger=test_logger,
            output_file=integration_config.output_file,
            config=integration_config
        )

        # Process and save results
        results = await ocr_processor.process_all_files(sample_files_list)
        result_saver.save_results(results, integration_config.output_file)

        # Verify results were saved to file
        assert os.path.exists(integration_config.output_file)
        
        with open(integration_config.output_file, 'r', encoding='utf-8') as f:
            saved_results = json.load(f)

        assert len(saved_results) == 3
        for i, result in enumerate(saved_results):
            assert result["ocr_data"]["last_name"] == f"LASTNAME{i}"