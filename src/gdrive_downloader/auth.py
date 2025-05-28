"""Google Drive authentication module."""

import os
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import SCOPES, TOKEN_FILE, CLIENT_SECRET_FILE, LOCAL_SERVER_PORT
from .exceptions import AuthenticationError


def get_credentials() -> Credentials:
    """Get valid Google Drive API credentials.

    Returns:
        Credentials: Valid Google Drive API credentials.

    Raises:
        AuthenticationError: If authentication fails.
    """
    creds: Optional[Credentials] = None

    # Load existing credentials if available
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            raise AuthenticationError(
                f"Failed to load existing credentials: {e}")

    # Refresh or obtain new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise AuthenticationError(
                    f"Failed to refresh credentials: {e}")
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRET_FILE, SCOPES
                )
                creds = flow.run_local_server(port=LOCAL_SERVER_PORT)
            except Exception as e:
                raise AuthenticationError(
                    f"Failed to obtain new credentials: {e}")

        # Save credentials for future use
        try:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            raise AuthenticationError(f"Failed to save credentials: {e}")

    return creds
