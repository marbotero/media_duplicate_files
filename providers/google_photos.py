"""
google_photos.py — Provider para Google Photos usando Google Photos Library API v1.

Limitaciones importantes (2025):
  - El scope `photoslibrary.readonly` para acceso completo a la biblioteca
    ha sido restringido por Google para nuevas apps.
  - Este provider soporta dos modos:
    1. "app-created": lista solo medios subidos por esta app
       (scope: photoslibrary.readonly.appcreateddata)
    2. "picker": el usuario selecciona fotos en el selector de Google
       (Google Photos Picker API)
  - Google Photos NO proporciona MD5 ni SHA-256: se calculan al descargar.
  - Google Photos puede servir versiones transcodificadas/comprimidas,
    por lo que hashes exactos pueden no coincidir con el original de Drive/OneDrive.
    La comparación perceptual (pHash) es importante aquí.
  - Para deduplicar TODA la biblioteca de Google Photos, se recomienda
    exportar con Google Takeout y usar el modo --google-photos-folder.

Reutiliza el mismo credentials.json de Google Drive (mismo proyecto de Google Cloud),
pero usa un token separado (token_photos.json) porque los scopes son diferentes.

Es necesario habilitar la "Photos Library API" en Google Cloud Console.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from providers.base import (
    StorageProvider, MediaItem, IMAGE_MIMES, VIDEO_MIMES,
)

logger = logging.getLogger("media_dedupe")

# Scopes
SCOPE_APP_CREATED = "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
SCOPE_PICKER = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"

TOKEN_FILE = "token_photos.json"
CREDENTIALS_FILE = "credentials.json"

PHOTOS_API_BASE = "https://photoslibrary.googleapis.com/v1"
PICKER_API_BASE = "https://photospicker.googleapis.com/v1"

MAX_RETRIES = 3
RETRY_DELAY = 1.0


class GooglePhotosProvider(StorageProvider):
    """
    Provider para Google Photos.

    Modos:
      - mode="app-created": lista medios subidos por la app (Library API)
      - mode="picker": el usuario selecciona fotos en el selector (Picker API)
    """

    name = "google_photos"

    def __init__(
        self,
        credentials_file: str = CREDENTIALS_FILE,
        token_file: str = TOKEN_FILE,
        mode: str = "app-created",
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.mode = mode
        self.session = None
        # Mapa de item_id -> baseUrl para descargas posteriores
        self._base_urls: dict[str, str] = {}

    def authenticate(self) -> bool:
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.auth.transport.requests import AuthorizedSession
        except ImportError:
            logger.error("Instala dependencias: pip install google-auth-oauthlib")
            return False

        scopes = [SCOPE_APP_CREATED] if self.mode == "app-created" else [SCOPE_PICKER]

        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    logger.error(f"No se encontró '{self.credentials_file}'.")
                    logger.error("Usa el mismo credentials.json de Google Drive.")
                    logger.error("Además, habilita 'Photos Library API' en Google Cloud Console.")
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, scopes)
                creds = flow.run_local_server(port=0)
            with open(self.token_file, "w") as f:
                f.write(creds.to_json())

        self.session = AuthorizedSession(creds)
        logger.info(f"Google Photos: autenticación exitosa (modo: {self.mode}).")
        return True

    def is_authenticated(self) -> bool:
        return self.session is not None

    def _api_get(self, url: str, params: dict = None) -> dict:
        """Ejecuta un GET a la API con reintentos."""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(url, params=params, timeout=60)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", RETRY_DELAY))
                    logger.warning(f"Google Photos: rate limited, esperando {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Google Photos: error (intento {attempt+1}): {e}. Reintentando...")
                    time.sleep(wait)
                else:
                    raise

    def _api_post(self, url: str, json_body: dict) -> dict:
        """Ejecuta un POST a la API con reintentos."""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(url, json=json_body, timeout=60)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", RETRY_DELAY))
                    logger.warning(f"Google Photos: rate limited, esperando {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Google Photos: error (intento {attempt+1}): {e}. Reintentando...")
                    time.sleep(wait)
                else:
                    raise

    def _parse_media_item(self, raw: dict) -> Optional[MediaItem]:
        """Convierte un media item de la API en un MediaItem."""
        mime = raw.get("mimeType", "")
        if mime not in IMAGE_MIMES and mime not in VIDEO_MIMES:
            return None

        media_meta = raw.get("mediaMetadata", {})
        photo_meta = media_meta.get("photo", {})
        video_meta = media_meta.get("video", {})

        # Duración del video (formato ISO 8601 duration, ej: "10s")
        duration_ms = None
        if video_meta and "duration" in video_meta:
            duration_ms = self._parse_duration(video_meta["duration"])

        try:
            width = int(media_meta.get("width", 0)) or None
        except (ValueError, TypeError):
            width = None
        try:
            height = int(media_meta.get("height", 0)) or None
        except (ValueError, TypeError):
            height = None

        item_id = raw.get("id", "")

        # Guardar baseUrl para descarga posterior
        if raw.get("baseUrl"):
            self._base_urls[item_id] = raw["baseUrl"]

        return MediaItem(
            source=self.name,
            item_id=item_id,
            name=raw.get("filename", ""),
            mime_type=mime,
            size=0,  # Google Photos no reporta tamaño; se actualiza al descargar
            web_url=raw.get("productUrl"),
            modified_time=media_meta.get("creationTime"),
            width=width,
            height=height,
            duration_ms=duration_ms,
        )

    def _parse_duration(self, duration_str: str) -> Optional[int]:
        """Parsea una duración ISO 8601 (ej: '10s', '1m30s') a milisegundos."""
        try:
            import re
            # Formato simple: "Ns" o "Nm Ss"
            match = re.match(r"(?:(\d+)m)?\s*(?:(\d+(?:\.\d+)?)s)?", duration_str)
            if match:
                minutes = int(match.group(1) or 0)
                seconds = float(match.group(2) or 0)
                return int((minutes * 60 + seconds) * 1000)
        except Exception:
            pass
        return None

    def iter_media(self, root: Optional[str] = None) -> list[MediaItem]:
        """Lista medios de Google Photos."""
        if not self.is_authenticated():
            if not self.authenticate():
                return []

        if self.mode == "app-created":
            return self._list_app_created_media()
        elif self.mode == "picker":
            return self._list_picker_media()
        else:
            logger.error(f"Modo desconocido: {self.mode}")
            return []

    def _list_app_created_media(self) -> list[MediaItem]:
        """Lista medios subidos por la app usando la Library API."""
        logger.info("Google Photos: listando medios subidos por la app (Library API)...")

        items = []
        page_token = None

        while True:
            # Usar search endpoint para listar todos los medios de la app
            body = {"pageSize": 100, "filters": {"includeNonAppCreatedData": False}}
            if page_token:
                body["pageToken"] = page_token

            data = self._api_post(f"{PHOTOS_API_BASE}/mediaItems:search", body)

            for raw_item in data.get("mediaItems", []):
                item = self._parse_media_item(raw_item)
                if item:
                    items.append(item)

            logger.info(f"  Google Photos: {len(items)} medios listados...")
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Google Photos: {len(items)} medios encontrados.")
        logger.info("  NOTA: Solo se listan medios subidos por esta app.")
        logger.info("  Para toda la biblioteca, exporta con Google Takeout y usa --google-photos-folder.")
        return items

    def _list_picker_media(self) -> list[MediaItem]:
        """
        Lista medios seleccionados por el usuario en Google Photos Picker.
        Flujo: crear sesión -> abrir picker -> esperar selección -> listar items.
        """
        logger.info("Google Photos: iniciando sesión del Picker API...")

        # Crear sesión del picker
        session_data = self._api_post(f"{PICKER_API_BASE}/sessions", {})
        session_id = session_data.get("name", "").split("/")[-1]
        picker_uri = session_data.get("pickerUri", "")

        if not session_id:
            logger.error("Google Photos: no se pudo crear sesión del picker.")
            return []

        logger.info(f"\n{'='*60}")
        logger.info("SELECCIÓN DE FOTOS DE GOOGLE PHOTOS")
        logger.info(f"{'='*60}")
        logger.info(f"Abre este enlace en tu navegador para seleccionar fotos:")
        logger.info(f"  {picker_uri}")
        logger.info(f"\nSelecciona las fotos/videos que quieres analizar.")
        logger.info("Cuando termines, presiona Enter aquí...")
        logger.info(f"{'='*60}\n")

        input("Presiona Enter cuando hayas terminado de seleccionar...")

        # Listar medios seleccionados
        items = []
        page_token = None

        while True:
            params = {"sessionId": session_id, "pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            data = self._api_get(f"{PICKER_API_BASE}/mediaItems", params)

            for raw_item in data.get("mediaItems", []):
                item = self._parse_media_item(raw_item)
                if item:
                    items.append(item)

            logger.info(f"  Google Photos: {len(items)} medios seleccionados listados...")
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Google Photos: {len(items)} medios seleccionados.")
        return items

    def download_to_path(self, item: MediaItem, path: str) -> None:
        """
        Descarga un medio de Google Photos.
        - Imágenes: baseUrl + "=d" (descarga original)
        - Videos: baseUrl + "=dv" (descarga original)
        """
        base_url = self._base_urls.get(item.item_id)

        if not base_url:
            # Refrescar baseUrl si expiró
            logger.debug(f"Google Photos: refrescando baseUrl para {item.item_id}...")
            data = self._api_get(f"{PHOTOS_API_BASE}/mediaItems/{item.item_id}")
            base_url = data.get("baseUrl")
            if base_url:
                self._base_urls[item.item_id] = base_url

        if not base_url:
            raise ValueError(f"No se pudo obtener URL de descarga para '{item.name}'")

        # Construir URL de descarga
        suffix = "=dv" if item.is_video else "=d"
        download_url = base_url + suffix

        # Descargar con streaming
        resp = self.session.get(download_url, stream=True, timeout=120)
        resp.raise_for_status()

        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=5 * 1024 * 1024):
                f.write(chunk)

        # Actualizar tamaño real
        item.size = os.path.getsize(path)
