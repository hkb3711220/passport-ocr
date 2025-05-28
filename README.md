# Passport OCR Application

A modern Python application for downloading files from Google Drive folders and extracting structured passport information using Google's Gemini OCR with a clean, class-based architecture.

## ✨ Features

- **🔄 Google Drive Integration**: Download files from any specified Google Drive folder
- **🔍 Passport OCR**: Extract structured passport information (name, passport number, nationality) using Google's Gemini model
- **📄 JSON Output**: All OCR results are saved in a structured JSON format with error handling
- **🔐 Secure Authentication**: OAuth2 authentication with Google Drive API
- **📊 Progress Tracking**: Real-time download progress display
- **🛡️ Comprehensive Error Handling**: Robust error handling and structured logging
- **🏗️ Clean Architecture**: Modern class-based design with dependency injection
- **🔧 Type Safety**: Full type hints and Pydantic models for data validation

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
├── config/
│   └── client_secret.json           # Google API credentials (not in repo)
├── downloads/                       # Downloaded files directory
├── main.py                          # Entry point with class-based architecture
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── ocr_results.json                 # OCR output file (generated)
└── README.md                        # This file
```

## 🏛️ Architecture Overview

The application follows a clean, class-based architecture with dependency injection:

```
PassportOCRApplication (Main Application)
├── AppConfig (Configuration Management)
├── FileProcessor (File Operations)
├── ResultDisplayer (Output Formatting)
├── ResultSaver (Data Persistence)
└── OCRProcessor (OCR Orchestration)
    ├── GeminiOCR (External OCR Service)
    ├── FileProcessor (Injected Dependency)
    ├── ResultDisplayer (Injected Dependency)
    └── Logger (Injected Dependency)
```

### Key Classes

- **`PassportOCRApplication`**: Main application orchestrator
- **`AppConfig`**: Configuration management with dataclasses
- **`FileProcessor`**: File validation and result creation
- **`OCRProcessor`**: OCR workflow management
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
   pip install -r requirements.txt
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
python main.py 1j59kbKXVunetn_f37t4lkLjrQ7bl8cWg0Ig31Q3rwNLObQY3o0KCBQIfdJ7McVlMmtknfcQz
```

### Application Workflow

1. **Authentication**: Validates Google Drive credentials and Gemini API key
2. **Download**: Downloads all files from the specified Google Drive folder
3. **Processing**: Processes image files (PNG, JPG, JPEG, GIF, BMP) with OCR
4. **Extraction**: Extracts passport information using structured prompts
5. **Output**: Displays results in console and saves to `ocr_results.json`

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
    "filename": "passport2.jpg",
    "file_path": "./downloads/passport2.jpg",
    "error": "OCR processing failed: Invalid image format"
  }
]
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

### Testing

```bash
# Test package imports
python -c "from src.gemini_ocr import GeminiOCR; print('✓ Gemini OCR import successful')"
python -c "from src.gdrive_downloader import DriveClient; print('✓ Drive Client import successful')"

# Test main application
python -c "from main import PassportOCRApplication; print('✓ Main application import successful')"
```

### Development Dependencies

```bash
pip install -r requirements-dev.txt
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
- **`pydantic==2.10.3`**: Data validation

### Development Dependencies

- **`black`**: Code formatting
- **`flake8`**: Linting
- **`mypy`**: Type checking
- **`pytest`**: Testing framework

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
5. Test your changes
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **Authentication Error**: Ensure `config/client_secret.json` is properly configured
2. **API Key Error**: Verify `GEMINI_API_KEY` environment variable is set
3. **Import Error**: Check that all dependencies are installed in the virtual environment
4. **OCR Processing Error**: Ensure image files are in supported formats (PNG, JPG, JPEG, GIF, BMP)

### Support

For issues and questions, please create an issue in the repository with:
- Error message and stack trace
- Steps to reproduce
- Environment details (Python version, OS) 