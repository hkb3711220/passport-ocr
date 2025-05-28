"""Configuration settings for the Google Drive downloader application."""

import os
from typing import List

# Google Drive API settings
SCOPES: List[str] = ['https://www.googleapis.com/auth/drive']

# File paths
DOWNLOAD_FOLDER: str = './downloads'
TOKEN_FILE: str = 'token.json'
CLIENT_SECRET_FILE: str = './config/client_secret.json'

# API settings
PAGE_SIZE: int = 10
LOCAL_SERVER_PORT: int = 0

# Ensure download folder exists
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
