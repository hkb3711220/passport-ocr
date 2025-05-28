"""Google Drive client for file operations."""

import io
import os
from typing import List, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from .config import PAGE_SIZE, DOWNLOAD_FOLDER
from .exceptions import DownloadError, FileNotFoundError
from .auth import get_credentials


class DriveClient:
    """Google Drive client for file operations."""

    def __init__(self, folder_id: str) -> None:
        """Initialize the Drive client with authenticated credentials.

        Args:
            folder_id: Google Drive folder ID to download files from.
        """
        self.folder_id = folder_id
        self.credentials = get_credentials()
        self.service = build('drive', 'v3', credentials=self.credentials)

    def list_files(self) -> List[Dict[str, Any]]:
        """List all files in the specified Google Drive folder.

        Returns:
            List[Dict[str, Any]]: List of file metadata dictionaries.

        Raises:
            FileNotFoundError: If no files are found in the folder.
            HttpError: If the API request fails.
        """
        try:
            results = self.service.files().list(
                pageSize=PAGE_SIZE,
                q=f"'{self.folder_id}' in parents",
                fields="nextPageToken, files(id, name)"
            ).execute()

            items = results.get('files', [])

            if not items:
                raise FileNotFoundError(
                    'No files found in the specified folder.')

            return items

        except HttpError as error:
            raise HttpError(f'Failed to list files: {error}')

    def download_file(self, file_id: str, file_name: str) -> None:
        """Download a single file from Google Drive.

        Args:
            file_id: The Google Drive file ID.
            file_name: The name to save the file as.

        Raises:
            DownloadError: If the download fails.
        """
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_path = os.path.join(DOWNLOAD_FOLDER, file_name)

            with io.FileIO(file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    progress = int(status.progress() * 100)
                    print(f"Downloading {file_name}: {progress}%")

        except Exception as error:
            raise DownloadError(f'Failed to download {file_name}: {error}')

    def download_all_files(self) -> List[str]:
        """Download all files from the specified Google Drive folder.

        Returns:
            List[str]: List of downloaded file paths.

        Raises:
            FileNotFoundError: If no files are found.
            DownloadError: If any download fails.
        """
        files = self.list_files()
        downloaded_files = []

        # Check which files already exist in the download folder
        existing_files = set()
        if os.path.exists(DOWNLOAD_FOLDER):
            existing_files = set(os.listdir(DOWNLOAD_FOLDER))

        # Add existing files to the downloaded_files list
        for existing_file in existing_files:
            file_path = os.path.join(DOWNLOAD_FOLDER, existing_file)
            downloaded_files.append(file_path)

        # Filter out files that already exist
        files_to_download = []
        for file_info in files:
            if file_info['name'] not in existing_files:
                files_to_download.append(file_info)
            else:
                print(
                    f"Skipping {file_info['name']} - already exists in download folder")

        files = files_to_download

        print(f"Found {len(files)} files to download:")
        for file_info in files:
            print(f"  - {file_info['name']} ({file_info['id']})")

        for file_info in files:
            self.download_file(file_info['id'], file_info['name'])
            file_path = os.path.join(DOWNLOAD_FOLDER, file_info['name'])
            downloaded_files.append(file_path)

        return downloaded_files
