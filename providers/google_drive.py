"""
google_drive.py — Provider para Google Drive usando la API v3.

Usa OAuth2 con credenciales de aplicación de escritorio.
Proporciona md5Checksum directamente desde metadatos (sin descargar).
"""

from __future__ import annotations

import io
import logging
import os
import sys
import time
from typing import Optional

from providers.base import (
    StorageProvider, MediaItem, IMAGE_MIMES, VIDEO_MIMES,
)

logger = logging.getLogger("media_dedupe")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_FILE = "token_drive.json"
CREDENTIALS_FILE = "credentials.json"

FILE_FIELDS = (
    "nextPageToken,files("
    "id,name,mimeType,size,md5Checksum,parents,webViewLink,modifiedTime,"
    "imageMediaMetadata(width,height),"
    "videoMediaMetadata(durationMillis,width,height)"
    ")"
)

MAX_RETRIES = 3
RETRY_DELAY = 1.0


class GoogleDriveProvider(StorageProvider):
    """Provider para Google Drive."""

    name = "google_drive"

    def __init__(self, credentials_file: str = CREDENTIALS_FILE, token_file: str = TOKEN_FILE):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None

    def authenticate(self) -> bool:
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            logger.error("Instala dependencias: pip install -r requirements.txt")
            return False

        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    logger.error(f"No se encontró '{self.credentials_file}'.")
                    logger.error("Descarga el JSON de OAuth desde Google Cloud Console.")
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_file, "w") as f:
                f.write(creds.to_json())

        self.service = build("drive", "v3", credentials=creds)
        logger.info("Google Drive: autenticación exitosa.")
        return True

    def is_authenticated(self) -> bool:
        return self.service is not None

    def _api_call(self, request):
        """Ejecuta una llamada a la API con reintentos."""
        for attempt in range(MAX_RETRIES):
            try:
                return request.execute()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Error de API (intento {attempt+1}/{MAX_RETRIES}): {e}. Reintentando en {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def iter_media(self, root: Optional[str] = None) -> list[MediaItem]:
        if not self.is_authenticated():
            if not self.authenticate():
                return []

        if root:
            logger.info(f"Google Drive: listando recursivamente desde carpeta {root}...")
            raw_files = self._list_files_recursive(root)
        else:
            logger.info("Google Drive: listando todos los archivos multimedia...")
            raw_files = self._list_all()

        items = []
        for rf in raw_files:
            img_meta = rf.get("imageMediaMetadata", {})
            vid_meta = rf.get("videoMediaMetadata", {})
            try:
                size = int(rf.get("size", "0"))
            except (ValueError, TypeError):
                size = 0
            try:
                duration_ms = int(vid_meta.get("durationMillis", 0)) if vid_meta.get("durationMillis") else None
            except (ValueError, TypeError):
                duration_ms = None

            items.append(MediaItem(
                source=self.name,
                item_id=rf["id"],
                name=rf.get("name", ""),
                mime_type=rf.get("mimeType", ""),
                size=size,
                web_url=rf.get("webViewLink", ""),
                modified_time=rf.get("modifiedTime", ""),
                md5=rf.get("md5Checksum"),
                width=img_meta.get("width"),
                height=img_meta.get("height"),
                duration_ms=duration_ms,
            ))

        logger.info(f"Google Drive: {len(items)} archivos multimedia encontrados.")
        return items

    def _list_all(self) -> list:
        """Lista todos los archivos multimedia en Drive (no en papelera)."""
        all_files = []
        page_token = None

        mime_conditions = [f"mimeType='{m}'" for m in IMAGE_MIMES | VIDEO_MIMES]
        query = f"trashed=false and ({' or '.join(mime_conditions)})"

        while True:
            req = self.service.files().list(
                q=query,
                spaces="drive",
                fields=FILE_FIELDS,
                orderBy="folder,name",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="allDrives",
            )
            response = self._api_call(req)
            all_files.extend(response.get("files", []))
            logger.info(f"  Google Drive: {len(all_files)} archivos listados...")
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return all_files

    def _list_files_recursive(self, folder_id: str) -> list:
        """Recorre recursivamente una carpeta."""
        all_files = []

        # Subcarpetas con paginación
        folder_page_token = None
        while True:
            folder_req = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="nextPageToken, files(id,name)",
                pageSize=1000,
                pageToken=folder_page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="allDrives",
            )
            folder_response = self._api_call(folder_req)
            for folder in folder_response.get("files", []):
                logger.info(f"  Google Drive: entrando en carpeta '{folder['name']}'")
                all_files.extend(self._list_files_recursive(folder["id"]))
            folder_page_token = folder_response.get("nextPageToken")
            if not folder_page_token:
                break

        # Archivos multimedia en esta carpeta
        mime_conditions = [f"mimeType='{m}'" for m in IMAGE_MIMES | VIDEO_MIMES]
        query = f"'{folder_id}' in parents and ({' or '.join(mime_conditions)}) and trashed=false"

        page_token = None
        while True:
            req = self.service.files().list(
                q=query,
                spaces="drive",
                fields=FILE_FIELDS,
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="allDrives",
            )
            response = self._api_call(req)
            all_files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return all_files

    def download_to_path(self, item: MediaItem, path: str) -> None:
        from googleapiclient.http import MediaIoBaseDownload

        request = self.service.files().get_media(fileId=item.item_id, supportsAllDrives=True)
        with open(path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request, chunksize=5 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
