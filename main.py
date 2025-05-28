"""Entry point for the Google Drive downloader application."""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, List, Dict, Any, Optional

from src.gdrive_downloader.drive_client import DriveClient
from src.gdrive_downloader.exceptions import GDriveDownloaderError
from src.gemini_ocr.ocr_client import GeminiOCR, GeminiOCRError
from autogen_core import EVENT_LOGGER_NAME
from pydantic import BaseModel
from typing import TypedDict

# Constants
SUPPORTED_IMAGE_EXTENSIONS: tuple = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
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
        logger: logging.Logger
    ):
        self.ocr_client = ocr_client
        self.file_processor = file_processor
        self.result_displayer = result_displayer
        self.logger = logger

    async def process_single_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Process a single file with OCR.

        Args:
            file_path: Path to the file to process.

        Returns:
            Dictionary containing processing result or None if skipped.
        """
        if not self.file_processor.is_image_file(file_path):
            self.logger.info(f"Skipping non-image file: {file_path}")
            return None

        self.logger.info(f"Processing OCR for: {file_path}")

        try:
            ocr_response = await self.ocr_client.ocr(OCR_PROMPT, file_path)
            self.result_displayer.display_ocr_result(file_path, ocr_response)
            return self.file_processor.create_result_entry(ocr_response, file_path)

        except Exception as e:
            self.logger.error(f"OCR failed for {file_path}: {e}")
            return self.file_processor.create_error_entry(file_path, e)

    async def process_all_files(self, downloaded_files: List[str]) -> List[Dict[str, Any]]:
        """Process all downloaded files with OCR.

        Args:
            downloaded_files: List of downloaded file paths.

        Returns:
            List of processing results.
        """
        results: List[Dict[str, Any]] = []

        for file_path in downloaded_files:
            result = await self.process_single_file(file_path)
            if result is not None:
                results.append(result)

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
                self.logger
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
