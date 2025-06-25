# Passport OCR Application

A modern Python application for downloading files from Google Drive folders and extracting structured passport information using Google's Gemini OCR with a clean, class-based architecture.

## ✨ Features

### Core Functionality
- **🔄 Google Drive Integration**: Download files from any specified Google Drive folder
- **🔍 Passport OCR**: Extract structured passport information (name, passport number, nationality) using Google's Gemini model
- **📄 PDF Support**: Automatic PDF to image conversion with per-page processing
- **📄 JSON Output**: All OCR results are saved in a structured JSON format with error handling

### Performance & Reliability
- **⚡ Batch Processing**: Concurrent file processing with configurable limits (up to 3x faster)
- **🔄 Smart Retry System**: Exponential backoff with jitter for failed operations
- **📊 Real-time Progress**: Live progress tracking with ETA calculations and success/failure counters
- **🛡️ Comprehensive Error Handling**: Robust error handling with automatic retry for transient failures

### Architecture & Quality
- **🏗️ Clean Architecture**: Modern class-based design with dependency injection
- **🔧 Type Safety**: Full type hints and Pydantic models for data validation
- **🧪 Comprehensive Testing**: 60+ unit tests and integration tests with 80%+ coverage
- **🔐 Secure Authentication**: OAuth2 authentication with Google Drive API

## 🏗️ Project Structure

```
passport-ocr/
├── src/
│   ├── gdrive_downloader/           # Google Drive operations package
│   │   ├── __init__.py
│   │   ├── config.py                # Configuration constants
│   │   ├── auth.py                  # Google Drive authentication
│   │   ├── drive_client.py          # Google Drive API client
│   │   └── exceptions.py            # Custom exception classes
│   └── gemini_ocr/                  # OCR processing package
│       ├── __init__.py
│       └── ocr_client.py            # Gemini OCR client with AutoGen
├── tests/                           # Comprehensive test suite
│   ├── conftest.py                  # Shared fixtures and configuration
│   ├── test_runner.py               # Custom test runner
│   ├── unit/                        # Unit tests (60+ test cases)
│   │   ├── test_progress_tracker.py
│   │   ├── test_retry_handler.py
│   │   ├── test_file_processor.py
│   │   └── test_ocr_processor.py
│   └── integration/                 # Integration tests
│       └── test_batch_processing.py
├── config/
│   └── client_secret.json           # Google API credentials (not in repo)
├── downloads/                       # Downloaded files directory
├── main.py                          # Entry point with batch processing & retry system
├── requirements.txt                 # Production dependencies
├── requirements-test.txt            # Testing dependencies
├── pytest.ini                      # Pytest configuration
├── ocr_results.json                 # OCR output file (generated)
└── README.md                        # This file
```

## 🏛️ Architecture Overview

The application follows a clean, class-based architecture with dependency injection and modern performance optimizations:

```
PassportOCRApplication (Main Application)
├── AppConfig (Configuration Management with Batch & Retry Settings)
├── FileProcessor (File Operations & PDF Conversion)
├── ProgressTracker (Real-time Progress & ETA Calculation)
├── ResultDisplayer (Output Formatting)
├── ResultSaver (Data Persistence)
└── OCRProcessor (OCR Orchestration with Batch Processing)
    ├── GeminiOCR (External OCR Service)
    ├── RetryHandler (Exponential Backoff & Jitter)
    ├── FileProcessor (Injected Dependency)
    ├── ProgressTracker (Injected Dependency)
    └── Logger (Injected Dependency)
```

### Key Classes

- **`PassportOCRApplication`**: Main application orchestrator
- **`AppConfig`**: Configuration management with batch processing and retry settings
- **`FileProcessor`**: File validation, PDF conversion, and result creation
- **`OCRProcessor`**: OCR workflow management with concurrent batch processing
- **`ProgressTracker`**: Real-time progress tracking with ETA calculations
- **`RetryHandler`**: Smart retry logic with exponential backoff and jitter
- **`ResultDisplayer`**: Console output formatting
- **`ResultSaver`**: JSON file persistence

## 🚀 Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd passport-ocr
   ```

2. **Create virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   # Production dependencies
   pip install -r requirements.txt
   
   # Development and testing dependencies (optional)
   pip install -r requirements-test.txt
   ```

4. **Set up Google Drive API credentials**

   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google Drive API
   - Create credentials (OAuth 2.0 Client ID)
   - Download the credentials file as `config/client_secret.json`

5. **Set up Gemini API key**
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   ```

## 📖 Usage

### Basic Usage

```bash
python main.py <google_drive_folder_id>
```

### Example

```bash
python main.py xxx
```

### Application Workflow

1. **Authentication**: Validates Google Drive credentials and Gemini API key
2. **Download**: Downloads all files from the specified Google Drive folder
3. **Batch Processing**: Processes files concurrently with configurable limits (default: 3 concurrent files)
4. **Smart Processing**: 
   - Images (PNG, JPG, JPEG, GIF, BMP): Direct OCR processing
   - PDFs: Automatic conversion to images, then per-page OCR processing
5. **Retry Logic**: Automatic retry with exponential backoff for failed operations
6. **Progress Tracking**: Real-time progress display with ETA and success/failure counters
7. **Output**: Displays results in console and saves to `ocr_results.json`

### OCR Output Format

```json
[
  {
    "filename": "passport1.jpg",
    "file_path": "./downloads/passport1.jpg",
    "ocr_data": {
      "last_name": "SMITH",
      "first_name": "JOHN",
      "passport_number": "AB123456",
      "nationality": "USA"
    }
  },
  {
    "filename": "document.pdf",
    "file_path": "./downloads/document.pdf",
    "source_type": "pdf",
    "total_pages": 2,
    "pages_processed": 2,
    "ocr_data": {
      "last_name": "DOE",
      "first_name": "JANE",
      "passport_number": "CD789012",
      "nationality": "UK"
    },
    "page_results": [
      {"filename": "document.pdf (page 1)", "ocr_data": {...}},
      {"filename": "document.pdf (page 2)", "ocr_data": {...}}
    ]
  },
  {
    "filename": "corrupted_image.jpg",
    "file_path": "./downloads/corrupted_image.jpg",
    "error": "OCR processing failed after all retries: Invalid image format"
  }
]
```

### Progress Output Example

```
Progress: 15/50 (30.0%) | Success: 12 | Failed: 2 | Retried: 1 | ETA: 45.2s | Current: passport_scan_15.jpg
```

## ⚙️ Configuration

### Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key (required)

### Configuration Files

- `config/client_secret.json`: Google Drive API credentials
- `token.json`: OAuth2 token (auto-generated on first run)

### AppConfig Class

```python
@dataclass
class AppConfig:
    folder_id: str
    api_key: str
    output_file: str = "ocr_results.json"
    log_level: int = logging.INFO
    # Batch processing settings
    max_concurrent_files: int = 3
    # Retry system settings
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    max_retry_delay: float = 60.0
```

### Performance Configuration

You can customize the batch processing and retry behavior:

```python
config = AppConfig(
    folder_id="your-folder-id",
    api_key="your-api-key",
    max_concurrent_files=5,    # Process up to 5 files simultaneously
    max_retries=5,             # Retry failed operations up to 5 times
    retry_delay=0.5,           # Start with 0.5s delay
    retry_backoff_factor=3.0,  # Triple delay each retry
    max_retry_delay=120.0      # Maximum delay of 2 minutes
)
```

## 🔧 API Reference

### PassportOCRApplication

```python
from main import PassportOCRApplication, AppConfig

# Create configuration
config = AppConfig(
    folder_id="your-folder-id",
    api_key="your-api-key"
)

# Initialize and run application
app = PassportOCRApplication(config)
await app.run()
```

### GeminiOCR Class

```python
from src.gemini_ocr import GeminiOCR, OCRResponse

# Initialize OCR client with structured output
ocr_client = GeminiOCR(
    api_key="your-api-key",
    output_content_type=OCRResponse
)

# Extract structured data from image
result = await ocr_client.ocr(
    message="Extract passport information",
    image_path="path/to/passport.jpg"
)
```

### DriveClient Class

```python
from src.gdrive_downloader import DriveClient

# Initialize Drive client
drive_client = DriveClient(folder_id="your-folder-id")

# Download all files
downloaded_files = drive_client.download_all_files()
```

## 🛡️ Error Handling

The application includes comprehensive error handling with custom exceptions:

### Exception Hierarchy

- **`GDriveDownloaderError`**: Google Drive related errors
  - Authentication failures
  - Network connectivity issues
  - File access permissions
- **`GeminiOCRError`**: OCR processing errors
  - `ImageProcessingError`: Image validation failures
  - `ModelError`: Gemini model processing failures

### Error Response Format

```json
{
  "filename": "corrupted_image.jpg",
  "file_path": "./downloads/corrupted_image.jpg",
  "error": "ImageProcessingError: Unable to process image file"
}
```

## 📊 Logging

The application uses structured logging with different levels:

- **`INFO`**: Application workflow and progress
- **`WARNING`**: Non-critical issues (e.g., skipped files)
- **`ERROR`**: Critical errors that affect processing

### Log Format

```
2024-01-15 10:30:45 - autogen_core - INFO - Processing OCR for: ./downloads/passport1.jpg
2024-01-15 10:30:47 - autogen_core - INFO - Successfully processed passport1.jpg
```

## 🧪 Development

### Code Quality Standards

This project follows modern Python best practices:

- **Type Hints**: Complete type annotations throughout
- **Google-style Docstrings**: Comprehensive documentation
- **Class-based Design**: Single responsibility principle
- **Dependency Injection**: Testable and maintainable code
- **Dataclasses**: Type-safe configuration management
- **Pydantic Models**: Data validation and serialization

## 🧪 Testing

The application includes a comprehensive testing suite with 60+ test cases covering unit tests and integration tests.

### Running Tests

```bash
# Install testing dependencies
pip install -r requirements-test.txt

# Run all tests
python tests/test_runner.py

# Run specific test types
python tests/test_runner.py unit           # Unit tests only
python tests/test_runner.py integration    # Integration tests only
python tests/test_runner.py coverage       # Full coverage report
python tests/test_runner.py quick          # Quick test run

# Using pytest directly
pytest tests/unit/ -v                      # Unit tests
pytest tests/integration/ -v               # Integration tests
pytest tests/ --cov=main --cov=src        # With coverage report
```

### Test Coverage

- **Unit Tests**: 60+ test cases covering all major components
  - `ProgressTracker`: Progress tracking and ETA calculations
  - `RetryHandler`: Exponential backoff and jitter logic
  - `FileProcessor`: File validation and PDF conversion
  - `OCRProcessor`: Batch processing and retry integration

- **Integration Tests**: End-to-end workflow testing
  - Batch processing with concurrent operations
  - Retry logic with simulated failures
  - Progress tracking during real operations
  - File processing with existing results

### Test Results Example

```bash
================================= test session starts =================================
collected 68 items

tests/unit/test_progress_tracker.py::TestProgressTracker::test_init PASSED     [ 1%]
tests/unit/test_retry_handler.py::TestRetryHandler::test_exponential_backoff PASSED [ 2%]
...
tests/integration/test_batch_processing.py::test_concurrent_behavior PASSED   [100%]

================================= 68 passed in 12.34s =================================

Coverage Report:
main.py                    95%
src/gemini_ocr/           87%
src/gdrive_downloader/    82%
Total Coverage:           88%
```

### Development Dependencies

```bash
pip install -r requirements-test.txt
```

## 📦 Dependencies

### Core Dependencies

- **`google-auth==2.23.4`**: Google authentication
- **`google-auth-oauthlib==1.1.0`**: OAuth2 flow
- **`google-api-python-client==2.108.0`**: Google Drive API
- **`autogen-agentchat==0.5.7`**: AI agent framework
- **`autogen-core==0.5.7`**: Core AutoGen functionality
- **`autogen-ext==0.5.7`**: Extended AI models
- **`Pillow==10.4.0`**: Image processing
- **`pdf2image==1.17.0`**: PDF to image conversion
- **`pydantic==2.10.3`**: Data validation

### Testing Dependencies

- **`pytest==7.4.3`**: Testing framework
- **`pytest-asyncio==0.21.1`**: Async test support
- **`pytest-cov==4.1.0`**: Coverage reporting
- **`pytest-mock==3.12.0`**: Mocking utilities
- **`black==23.11.0`**: Code formatting
- **`flake8==6.1.0`**: Linting
- **`mypy==1.7.1`**: Type checking
- **`factory-boy==3.3.0`**: Test data generation

## 🔒 Security Notes

- ❌ Never commit `config/client_secret.json` to version control
- ✅ Store API keys as environment variables
- ✅ Use OAuth2 for secure Google Drive access
- ✅ Validate all input files before processing
- ✅ Handle sensitive data with appropriate logging levels

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the existing code style and architecture
4. Add type hints and docstrings
5. Write tests for new features
6. Ensure all tests pass: `python tests/test_runner.py`
7. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **Authentication Error**: Ensure `config/client_secret.json` is properly configured
2. **API Key Error**: Verify `GEMINI_API_KEY` environment variable is set
3. **Import Error**: Check that all dependencies are installed in the virtual environment
4. **OCR Processing Error**: Ensure image files are in supported formats (PNG, JPG, JPEG, GIF, BMP, PDF)
5. **PDF Conversion Error**: Install poppler-utils: `brew install poppler` (macOS) or `apt-get install poppler-utils` (Ubuntu)
6. **Concurrent Processing Issues**: Reduce `max_concurrent_files` if experiencing rate limits
7. **Memory Issues**: Lower concurrent processing limit for large files or limited memory systems

### Support

For issues and questions, please create an issue in the repository with:

- Error message and stack trace
- Steps to reproduce
- Environment details (Python version, OS)
