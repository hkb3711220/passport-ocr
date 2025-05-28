"""Custom exceptions for the Google Drive downloader application."""


class GDriveDownloaderError(Exception):
    """Base exception for Google Drive downloader application."""
    pass


class AuthenticationError(GDriveDownloaderError):
    """Raised when Google Drive authentication fails."""
    pass


class DownloadError(GDriveDownloaderError):
    """Raised when file download fails."""
    pass


class FileNotFoundError(GDriveDownloaderError):
    """Raised when no files are found in the specified folder."""
    pass
