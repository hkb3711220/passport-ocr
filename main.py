"""Entry point for the Google Drive downloader application."""

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
import random
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from pdf2image import convert_from_path
from src.gdrive_downloader.drive_client import DriveClient
from src.gdrive_downloader.exceptions import GDriveDownloaderError
from src.gemini_ocr.ocr_client import GeminiOCR, GeminiOCRError
from autogen_core import EVENT_LOGGER_NAME
from pydantic import BaseModel
from typing import TypedDict

# Constants
SUPPORTED_IMAGE_EXTENSIONS: tuple = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
SUPPORTED_PDF_EXTENSIONS: tuple = ('.pdf',)
OCR_PROMPT: str = """Please extract the name, passport number, and nationality from the provided passport image.
Output as a JSON object in the following format:

{
  "last_name": "<last_name>",
  "first_name": "<first_name>",
  "passport_number": "<passport_number>",
  "nationality": "<nationality>"
}

Name must be in Last Name First Name order.

Return only the JSON object without any additional text, comments, or explanations.

If there are multiple records, return an array of JSON objects."""


class OCRResult(TypedDict):
    last_name: str
    first_name: str
    passport_number: str
    nationality: str


class OCRResponse(BaseModel):
    ocr_data: OCRResult


@dataclass
class AppConfig:
    """Application configuration."""
    folder_id: str
    api_key: str
    output_file: str = "ocr_results.json"
    log_level: int = logging.INFO
    max_concurrent_files: int = 3
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    max_retry_delay: float = 60.0


class FileProcessor:
    """Handles file processing operations."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def is_image_file(self, file_path: str) -> bool:
        """Check if file is a supported image format.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if file is a supported image format.
        """
        return file_path.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)

    def is_pdf_file(self, file_path: str) -> bool:
        """Check if file is a PDF format.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if file is a PDF format.
        """
        return file_path.lower().endswith(SUPPORTED_PDF_EXTENSIONS)

    def is_supported_file(self, file_path: str) -> bool:
        """Check if file is supported (image or PDF).

        Args:
            file_path: Path to the file to check.

        Returns:
            True if file is supported.
        """
        return self.is_image_file(file_path) or self.is_pdf_file(file_path)

    def convert_pdf_to_images(self, pdf_path: str) -> List[str]:
        """Convert PDF file to images.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of temporary image file paths.
        """
        try:
            self.logger.info(f"Converting PDF to images: {pdf_path}")

            # Try to find poppler path automatically
            poppler_path = None
            common_poppler_paths = [
                '/opt/homebrew/bin',  # Homebrew on Apple Silicon
                '/usr/local/bin',     # Homebrew on Intel
                '/usr/bin'            # System installation
            ]

            for path in common_poppler_paths:
                if os.path.exists(os.path.join(path, 'pdftoppm')):
                    poppler_path = path
                    break

            if poppler_path:
                self.logger.info(f"Using poppler from: {poppler_path}")
                images = convert_from_path(pdf_path, poppler_path=poppler_path)
            else:
                self.logger.info("Using system poppler installation")
                images = convert_from_path(pdf_path)

            temp_image_paths = []

            for i, image in enumerate(images):
                # Create temporary file for each page
                temp_file = tempfile.NamedTemporaryFile(
                    suffix=f'_page_{i+1}.png',
                    delete=False
                )
                temp_file.close()

                image.save(temp_file.name, 'PNG')
                temp_image_paths.append(temp_file.name)
                self.logger.info(f"Saved page {i+1} as: {temp_file.name}")

            return temp_image_paths

        except Exception as e:
            self.logger.error(f"Failed to convert PDF {pdf_path}: {e}")
            return []

    def cleanup_temp_files(self, temp_files: List[str]) -> None:
        """Clean up temporary files.

        Args:
            temp_files: List of temporary file paths to clean up.
        """
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    self.logger.debug(
                        f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up {temp_file}: {e}")

    def load_existing_results(self, output_file: str) -> Dict[str, Any]:
        """Load existing OCR results from file.

        Args:
            output_file: Path to the output file.

        Returns:
            Dictionary mapping filenames to their results.
        """
        if not os.path.exists(output_file):
            return {}

        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                results = json.load(f)

            # Create a mapping of filenames to results
            existing_results = {}
            for result in results:
                filename = result.get('filename', '')
                if filename:
                    existing_results[filename] = result

            self.logger.info(
                f"Loaded {len(existing_results)} existing results from {output_file}")
            return existing_results

        except Exception as e:
            self.logger.warning(
                f"Failed to load existing results from {output_file}: {e}")
            return {}

    def is_already_processed(self, file_path: str, existing_results: Dict[str, Any]) -> bool:
        """Check if file has already been processed successfully.

        Args:
            file_path: Path to the file to check.
            existing_results: Dictionary of existing results.

        Returns:
            True if file has already been processed successfully (no errors).
        """
        filename = Path(file_path).name
        if filename not in existing_results:
            return False

        # Check if the existing result contains an error
        result = existing_results[filename]
        has_error = 'error' in result

        if has_error:
            self.logger.info(
                f"File {filename} had previous error, will retry: {result.get('error', 'Unknown error')}")
            return False

        return True

    def create_result_entry(self, ocr_response: OCRResponse, file_path: str) -> Dict[str, Any]:
        """Create result entry from OCR response.

        Args:
            ocr_response: Structured OCR response from Gemini.
            file_path: Path to the processed file.

        Returns:
            Dictionary containing parsed result.
        """
        return {
            "filename": Path(file_path).name,
            "file_path": file_path,
            "ocr_data": ocr_response.ocr_data
        }

    def create_error_entry(self, file_path: str, error: Exception) -> Dict[str, Any]:
        """Create error entry for failed OCR processing.

        Args:
            file_path: Path to the file that failed processing.
            error: Exception that occurred.

        Returns:
            Dictionary containing error information.
        """
        return {
            "filename": Path(file_path).name,
            "file_path": file_path,
            "error": str(error)
        }


class ProgressTracker:
    """Handles progress tracking and display."""

    def __init__(self, total_files: int, logger: logging.Logger):
        self.total_files = total_files
        self.processed_files = 0
        self.successful_files = 0
        self.failed_files = 0
        self.retried_files = 0
        self.start_time = time.time()
        self.logger = logger

    def update_progress(self, success: bool = True, retry: bool = False) -> None:
        """Update progress counters."""
        self.processed_files += 1
        if success:
            self.successful_files += 1
        else:
            self.failed_files += 1
        if retry:
            self.retried_files += 1

    def display_progress(self, current_file: str = "") -> None:
        """Display current progress."""
        elapsed_time = time.time() - self.start_time
        if self.processed_files > 0:
            avg_time_per_file = elapsed_time / self.processed_files
            eta = avg_time_per_file * (self.total_files - self.processed_files)
        else:
            eta = 0

        progress_percent = (self.processed_files / self.total_files) * 100 if self.total_files > 0 else 0
        
        progress_msg = (
            f"Progress: {self.processed_files}/{self.total_files} "
            f"({progress_percent:.1f}%) | "
            f"Success: {self.successful_files} | "
            f"Failed: {self.failed_files} | "
            f"Retried: {self.retried_files} | "
            f"ETA: {eta:.1f}s"
        )
        
        if current_file:
            progress_msg += f" | Current: {current_file}"
            
        self.logger.info(progress_msg)
        print(f"\r{progress_msg}", end="", flush=True)

    def display_final_summary(self) -> None:
        """Display final processing summary."""
        total_time = time.time() - self.start_time
        print(f"\n{'='*80}")
        print(f"PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"Total files: {self.total_files}")
        print(f"Successful: {self.successful_files}")
        print(f"Failed: {self.failed_files}")
        print(f"Retried: {self.retried_files}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Average time per file: {total_time/self.processed_files:.2f}s" if self.processed_files > 0 else "N/A")
        print(f"{'='*80}")


class RetryHandler:
    """Handles retry logic with exponential backoff."""

    def __init__(self, config: AppConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    async def retry_with_backoff(
        self, 
        func: Callable, 
        *args, 
        operation_name: str = "operation",
        **kwargs
    ) -> Any:
        """Execute function with exponential backoff retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if attempt > 0:
                    self.logger.info(f"Retry attempt {attempt}/{self.config.max_retries} for {operation_name}")
                
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"Successfully completed {operation_name} after {attempt} retries")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt == self.config.max_retries:
                    self.logger.error(f"Final retry failed for {operation_name}: {e}")
                    break
                
                delay = min(
                    self.config.retry_delay * (self.config.retry_backoff_factor ** attempt),
                    self.config.max_retry_delay
                )
                
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0.1, 0.3) * delay
                delay += jitter
                
                self.logger.warning(f"Attempt {attempt + 1} failed for {operation_name}: {e}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
        
        raise last_exception


class ResultDisplayer:
    """Handles result display operations."""

    @staticmethod
    def display_ocr_result(file_path: str, ocr_response: OCRResponse) -> None:
        """Display OCR result in formatted output.

        Args:
            file_path: Path to the processed file.
            ocr_response: Structured OCR response.
        """
        filename = Path(file_path).name
        print(f"\n{'='*50}")
        print(f"FILE: {filename}")
        print(f"{'='*50}")
        print(f"OCR RESULT:")
        print(f"{'-'*20}")
        print(f"Last Name: {ocr_response.ocr_data['last_name']}")
        print(f"First Name: {ocr_response.ocr_data['first_name']}")
        print(f"Passport Number: {ocr_response.ocr_data['passport_number']}")
        print(f"Nationality: {ocr_response.ocr_data['nationality']}")
        print(f"{'='*50}\n")

    @staticmethod
    def display_summary(output_file: str, total_files: int) -> None:
        """Display processing summary.

        Args:
            output_file: Path to the output file.
            total_files: Total number of processed files.
        """
        print(f"\n{'='*60}")
        print(f"ALL OCR RESULTS SAVED TO: {output_file}")
        print(f"Total processed files: {total_files}")
        print(f"{'='*60}")


class ResultSaver:
    """Handles result saving operations."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def save_results(self, results: List[Dict[str, Any]], output_file: str) -> None:
        """Save OCR results to JSON file.

        Args:
            results: List of OCR results to save.
            output_file: Path to the output file.
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        self.logger.info(f"All OCR results saved to {output_file}")


class OCRProcessor:
    """Handles OCR processing operations."""

    def __init__(
        self,
        ocr_client: GeminiOCR,
        file_processor: FileProcessor,
        result_displayer: ResultDisplayer,
        logger: logging.Logger,
        output_file: str,
        config: AppConfig
    ):
        self.ocr_client = ocr_client
        self.file_processor = file_processor
        self.result_displayer = result_displayer
        self.logger = logger
        self.output_file = output_file
        self.config = config
        self.retry_handler = RetryHandler(config, logger)
        self.existing_results = self.file_processor.load_existing_results(
            output_file)

    async def process_single_image(self, image_path: str, original_filename: str = None) -> Optional[Dict[str, Any]]:
        """Process a single image file with OCR with retry logic.

        Args:
            image_path: Path to the image file to process.
            original_filename: Original filename for display purposes.

        Returns:
            Dictionary containing processing result or None if failed.
        """
        display_name = original_filename or Path(image_path).name
        
        async def _ocr_operation():
            return await self.ocr_client.ocr(OCR_PROMPT, image_path)

        try:
            ocr_response = await self.retry_handler.retry_with_backoff(
                _ocr_operation,
                operation_name=f"OCR processing for {display_name}"
            )
            
            self.result_displayer.display_ocr_result(display_name, ocr_response)

            # Use original filename if provided, otherwise use image path
            result_entry = self.file_processor.create_result_entry(
                ocr_response, image_path)
            if original_filename:
                result_entry["filename"] = original_filename
                result_entry["original_file_path"] = original_filename

            return result_entry

        except Exception as e:
            self.logger.error(f"OCR failed for {display_name} after all retries: {e}")
            error_entry = self.file_processor.create_error_entry(image_path, e)
            if original_filename:
                error_entry["filename"] = original_filename
                error_entry["original_file_path"] = original_filename
            return error_entry

    async def process_single_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Process a single file with OCR (supports images and PDFs).

        Args:
            file_path: Path to the file to process.

        Returns:
            Dictionary containing processing result or None if skipped.
        """
        # Check if file is supported
        if not self.file_processor.is_supported_file(file_path):
            self.logger.info(f"Skipping unsupported file: {file_path}")
            return None

        # Check if already processed
        if self.file_processor.is_already_processed(file_path, self.existing_results):
            self.logger.info(f"Skipping already processed file: {file_path}")
            return self.existing_results[Path(file_path).name]

        # Handle PDF files
        if self.file_processor.is_pdf_file(file_path):
            return await self.process_pdf_file(file_path)

        # Handle image files
        elif self.file_processor.is_image_file(file_path):
            return await self.process_single_image(file_path)

        return None

    async def process_pdf_file(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Process a PDF file by converting to images and running OCR.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Dictionary containing processing result or None if failed.
        """
        temp_image_paths = []
        try:
            # Convert PDF to images
            temp_image_paths = self.file_processor.convert_pdf_to_images(
                pdf_path)
            if not temp_image_paths:
                return self.file_processor.create_error_entry(pdf_path, Exception("Failed to convert PDF to images"))

            # Process each page
            pdf_results = []
            for i, image_path in enumerate(temp_image_paths):
                page_result = await self.process_single_image(
                    image_path,
                    f"{Path(pdf_path).name} (page {i+1})"
                )
                if page_result:
                    pdf_results.append(page_result)

            # Create combined result for the PDF
            if pdf_results:
                # For now, return the first page's result but mark it as from PDF
                main_result = pdf_results[0].copy()
                main_result["filename"] = Path(pdf_path).name
                main_result["file_path"] = pdf_path
                main_result["source_type"] = "pdf"
                main_result["total_pages"] = len(temp_image_paths)
                main_result["pages_processed"] = len(pdf_results)

                # Add page results if multiple pages
                if len(pdf_results) > 1:
                    main_result["page_results"] = pdf_results

                return main_result
            else:
                return self.file_processor.create_error_entry(pdf_path, Exception("No pages could be processed"))

        finally:
            # Clean up temporary files
            if temp_image_paths:
                self.file_processor.cleanup_temp_files(temp_image_paths)

    async def process_all_files(self, downloaded_files: List[str]) -> List[Dict[str, Any]]:
        """Process all downloaded files with OCR using batch processing.

        Args:
            downloaded_files: List of downloaded file paths.

        Returns:
            List of processing results.
        """
        results: List[Dict[str, Any]] = []

        # Add existing successful results to the results list
        successful_existing_results = {}
        for filename, result in self.existing_results.items():
            if 'error' not in result:
                results.append(result)
                successful_existing_results[filename] = result

        # Filter files that need processing
        files_to_process = []
        for file_path in downloaded_files:
            if not self.file_processor.is_already_processed(file_path, self.existing_results):
                files_to_process.append(file_path)

        if not files_to_process:
            self.logger.info("No new files to process")
            return results

        # Initialize progress tracker
        progress_tracker = ProgressTracker(len(files_to_process), self.logger)
        
        self.logger.info(f"Starting batch processing of {len(files_to_process)} files with max {self.config.max_concurrent_files} concurrent operations")

        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(self.config.max_concurrent_files)

        async def process_with_semaphore(file_path: str) -> Optional[Dict[str, Any]]:
            """Process a single file with concurrency control."""
            async with semaphore:
                filename = Path(file_path).name
                was_error_retry = (filename in self.existing_results and
                                   'error' in self.existing_results[filename])
                
                progress_tracker.display_progress(filename)
                
                try:
                    result = await self.process_single_file(file_path)
                    success = result is not None and 'error' not in result
                    progress_tracker.update_progress(success=success, retry=was_error_retry)
                    return result
                except Exception as e:
                    self.logger.error(f"Unexpected error processing {filename}: {e}")
                    progress_tracker.update_progress(success=False, retry=was_error_retry)
                    return self.file_processor.create_error_entry(file_path, e)

        # Process files concurrently
        try:
            batch_results = await asyncio.gather(
                *[process_with_semaphore(file_path) for file_path in files_to_process],
                return_exceptions=True
            )

            # Process results
            new_files_processed = 0
            retry_files_processed = 0

            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Batch processing error for {files_to_process[i]}: {result}")
                    error_result = self.file_processor.create_error_entry(files_to_process[i], result)
                    results.append(error_result)
                elif result is not None:
                    results.append(result)
                    
                    filename = Path(files_to_process[i]).name
                    was_error_retry = (filename in self.existing_results and
                                       'error' in self.existing_results[filename])
                    
                    if was_error_retry:
                        retry_files_processed += 1
                    else:
                        new_files_processed += 1

        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")
            raise

        # Display final summary
        progress_tracker.display_final_summary()
        
        successful_count = len(successful_existing_results)
        self.logger.info(
            f"Batch processing complete: {new_files_processed} new files, "
            f"{retry_files_processed} retry files, {successful_count} existing successful files"
        )
        
        return results


class PassportOCRApplication:
    """Main application class for passport OCR processing."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = self._setup_logging()
        self.file_processor = FileProcessor(self.logger)
        self.result_displayer = ResultDisplayer()
        self.result_saver = ResultSaver(self.logger)

    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration.

        Returns:
            Configured logger instance.
        """
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(EVENT_LOGGER_NAME)
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(self.config.log_level)
        return logger

    async def run(self) -> None:
        """Run the main application workflow."""
        try:
            self.logger.info("Starting Google Drive downloader application")

            # Download files from Google Drive
            drive_client = DriveClient(self.config.folder_id)
            downloaded_files = drive_client.download_all_files()
            self.logger.info("Successfully downloaded all files")

            # Initialize OCR client and processor
            ocr_client = GeminiOCR(self.config.api_key,
                                   output_content_type=OCRResponse)
            ocr_processor = OCRProcessor(
                ocr_client,
                self.file_processor,
                self.result_displayer,
                self.logger,
                self.config.output_file,
                self.config
            )

            # Process files
            results = await ocr_processor.process_all_files(downloaded_files)

            # Save results
            self.result_saver.save_results(results, self.config.output_file)
            self.result_displayer.display_summary(
                self.config.output_file, len(results))

            self.logger.info("Application completed successfully")

        except GDriveDownloaderError as e:
            self.logger.error(f"Google Drive downloader error: {e}")
            raise
        except GeminiOCRError as e:
            self.logger.error(f"OCR processing error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise


def create_config_from_args() -> AppConfig:
    """Create application configuration from command line arguments.

    Returns:
        Application configuration.

    Raises:
        SystemExit: If arguments are invalid or API key is missing.
    """
    if len(sys.argv) != 2:
        print("Usage: python main.py <folder_id>")
        sys.exit(1)

    folder_id = sys.argv[1]

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)

    return AppConfig(folder_id=folder_id, api_key=api_key)


async def main() -> NoReturn:
    """Main entry point for the Google Drive downloader application."""
    try:
        config = create_config_from_args()
        app = PassportOCRApplication(config)
        await app.run()

    except (GDriveDownloaderError, GeminiOCRError) as e:
        print(f"Application error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
