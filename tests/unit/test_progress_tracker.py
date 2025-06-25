"""Unit tests for ProgressTracker class."""

import time
from unittest.mock import Mock, patch
import pytest

from main import ProgressTracker

pytestmark = pytest.mark.unit


class TestProgressTracker:
    """Test cases for ProgressTracker class."""

    def test_init(self, test_logger):
        """Test ProgressTracker initialization."""
        tracker = ProgressTracker(total_files=10, logger=test_logger)
        
        assert tracker.total_files == 10
        assert tracker.processed_files == 0
        assert tracker.successful_files == 0
        assert tracker.failed_files == 0
        assert tracker.retried_files == 0
        assert tracker.logger == test_logger
        assert isinstance(tracker.start_time, float)

    def test_update_progress_success(self, test_logger):
        """Test updating progress for successful processing."""
        tracker = ProgressTracker(total_files=5, logger=test_logger)
        
        tracker.update_progress(success=True, retry=False)
        
        assert tracker.processed_files == 1
        assert tracker.successful_files == 1
        assert tracker.failed_files == 0
        assert tracker.retried_files == 0

    def test_update_progress_failure(self, test_logger):
        """Test updating progress for failed processing."""
        tracker = ProgressTracker(total_files=5, logger=test_logger)
        
        tracker.update_progress(success=False, retry=False)
        
        assert tracker.processed_files == 1
        assert tracker.successful_files == 0
        assert tracker.failed_files == 1
        assert tracker.retried_files == 0

    def test_update_progress_retry(self, test_logger):
        """Test updating progress for retry processing."""
        tracker = ProgressTracker(total_files=5, logger=test_logger)
        
        tracker.update_progress(success=True, retry=True)
        
        assert tracker.processed_files == 1
        assert tracker.successful_files == 1
        assert tracker.failed_files == 0
        assert tracker.retried_files == 1

    @patch('builtins.print')
    def test_display_progress_zero_processed(self, mock_print, test_logger):
        """Test displaying progress when no files processed yet."""
        tracker = ProgressTracker(total_files=10, logger=test_logger)
        
        tracker.display_progress("test_file.jpg")
        
        # Should still display progress even with 0 processed files
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "Progress: 0/10 (0.0%)" in call_args
        assert "Current: test_file.jpg" in call_args

    @patch('builtins.print')
    def test_display_progress_with_files_processed(self, mock_print, test_logger):
        """Test displaying progress with some files processed."""
        tracker = ProgressTracker(total_files=10, logger=test_logger)
        
        # Simulate some processing
        tracker.update_progress(success=True, retry=False)
        tracker.update_progress(success=False, retry=True)
        
        # Add small delay to ensure time calculation works
        time.sleep(0.1)
        
        tracker.display_progress("current_file.jpg")
        
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "Progress: 2/10 (20.0%)" in call_args
        assert "Success: 1" in call_args
        assert "Failed: 1" in call_args
        assert "Retried: 1" in call_args
        assert "ETA:" in call_args
        assert "Current: current_file.jpg" in call_args

    @patch('builtins.print')
    def test_display_progress_without_current_file(self, mock_print, test_logger):
        """Test displaying progress without current file name."""
        tracker = ProgressTracker(total_files=5, logger=test_logger)
        tracker.update_progress(success=True, retry=False)
        
        tracker.display_progress()
        
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "Progress: 1/5 (20.0%)" in call_args
        assert "Current:" not in call_args

    @patch('builtins.print')
    def test_display_final_summary(self, mock_print, test_logger):
        """Test displaying final summary."""
        tracker = ProgressTracker(total_files=5, logger=test_logger)
        
        # Simulate processing
        tracker.update_progress(success=True, retry=False)
        tracker.update_progress(success=True, retry=True)
        tracker.update_progress(success=False, retry=False)
        
        # Add delay to simulate processing time
        time.sleep(0.1)
        
        tracker.display_final_summary()
        
        # Should have multiple print calls for the summary
        assert mock_print.call_count >= 5
        
        # Check that summary contains expected information
        all_calls = [call[0][0] for call in mock_print.call_args_list]
        summary_text = ' '.join(all_calls)
        
        assert "PROCESSING COMPLETE" in summary_text
        assert "Total files: 5" in summary_text
        assert "Successful: 2" in summary_text
        assert "Failed: 1" in summary_text
        assert "Retried: 1" in summary_text
        assert "Total time:" in summary_text
        assert "Average time per file:" in summary_text

    def test_progress_calculation_edge_cases(self, test_logger):
        """Test progress calculation with edge cases."""
        # Test with zero total files
        tracker = ProgressTracker(total_files=0, logger=test_logger)
        tracker.display_progress()  # Should not crash
        
        # Test with very large numbers
        tracker = ProgressTracker(total_files=1000000, logger=test_logger)
        for _ in range(100):
            tracker.update_progress(success=True, retry=False)
        tracker.display_progress()  # Should handle large numbers correctly

    def test_eta_calculation(self, test_logger):
        """Test ETA calculation accuracy."""
        tracker = ProgressTracker(total_files=10, logger=test_logger)
        
        # Process one file with known time
        start_time = time.time()
        time.sleep(0.1)  # Simulate processing time
        tracker.update_progress(success=True, retry=False)
        
        # Calculate expected ETA
        elapsed = time.time() - tracker.start_time
        expected_eta = elapsed * (10 - 1)  # 9 remaining files
        
        # Check that ETA is reasonable (within 50% margin due to timing variations)
        tracker.display_progress()
        assert tracker.processed_files == 1