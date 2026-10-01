"""
onedrive.py — Provider para Microsoft OneDrive usando Microsoft Graph API.

Usa OAuth2 con MSAL (Microsoft Authentication Library).
Scopes: Files.Read.All, User.Read, offline_access
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from providers.base import (
    StorageProvider, MediaItem, IMAGE_MIMES, VIDEO_MIMES,
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
)
from config.paths import rutas_perfil_onedrive

logger = logging.getLogger("media_dedupe")

# Configuración de la app (el usuario debe registrar una app en Azure)
_DEFAULT_ONEDRIVE = rutas_perfil_onedrive("botero_estrada_marcelo")
CLIENT_ID_FILE = str(_DEFAULT_ONEDRIVE["config"])  # JSON con client_id y tenant
TOKEN_CACHE_FILE = str(_DEFAULT_ONEDRIVE["token"])

GRAPH_SCOPES = ["Files.Read.All", "User.Read"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

MAX_RETRIES = 3
RETRY_DELAY = 1.0


class OneDriveProvider(StorageProvider):
    """Provider para Microsoft OneDrive via Graph API."""

    name = "onedrive"

    def __init__(self, config_file: str = CLIENT_ID_FILE, token_cache: str = TOKEN_CACHE_FILE):
        self.config_file = config_file
        self.token_cache = token_cache
        self.client_id = None
        self.access_token = None
        self.app = None
        self._token_cache = None

    def authenticate(self) -> bool:
        try:
            import msal
            import requests
        except ImportError:
            logger.error("Instala dependencias: pip install msal requests")
            return False

        # Cargar configuración
        if not os.path.exists(self.config_file):
            logger.error(f"No se encontró '{self.config_file}'.")
            logger.error("Crea un archivo JSON con: {\"client_id\": \"tu-client-id\", \"tenant\": \"consumers\"}")
            logger.error("Para obtenerlo:")
            logger.error("  1. Ve a https://entra.microsoft.com/ (Azure Portal)")
            logger.error("  2. App registrations > New registration")
            logger.error("  3. Tipo de cuenta: Personal")
            logger.error("  4. Redirect URI: http://localhost")
            logger.error("  5. API Permissions > Add > Microsoft Graph > Files.Read.All")
            logger.error("  6. Copia el Application (client) ID")
            return False

        import json
        with open(self.config_file) as f:
            config = json.load(f)

        self.client_id = config.get("client_id")
        tenant = config.get("tenant", "consumers")

        if not self.client_id:
            logger.error("El archivo de configuración debe contener 'client_id'.")
            return False

        # Crear app MSAL con cache persistente en archivo
        self._token_cache = msal.SerializableTokenCache()
        if os.path.exists(self.token_cache):
            with open(self.token_cache, "r", encoding="utf-8") as f:
                self._token_cache.deserialize(f.read())

        self.app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{tenant}",
            token_cache=self._token_cache,
        )

        # Intentar obtener token de la cache primero
        result = None
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])

        if not result:
            logger.info("OneDrive: abriendo navegador para autenticación...")
            result = self.app.acquire_token_interactive(
                scopes=GRAPH_SCOPES,
                login_hint=None,
                prompt="select_account",
            )

        if "access_token" not in result:
            logger.error(f"OneDrive: error de autenticación: {result.get('error_description', result)}")
            return False

        self.access_token = result["access_token"]

        with open(self.token_cache, "w", encoding="utf-8") as f:
            f.write(self.app.token_cache.serialize())

        logger.info("OneDrive: autenticación exitosa.")
        return True

    def is_authenticated(self) -> bool:
        return self.access_token is not None

    def _graph_get(self, url: str) -> dict:
        """Ejecuta un GET a Microsoft Graph con reintentos."""
        import requests
        headers = {"Authorization": f"Bearer {self.access_token}"}
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, headers=headers, timeout=60)
                if resp.status_code == 429:  # Rate limit
                    wait = int(resp.headers.get("Retry-After", RETRY_DELAY))
                    logger.warning(f"OneDrive: rate limited, esperando {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"OneDrive: error (intento {attempt+1}): {e}. Reintentando en {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        # Todos los intentos fueron rate-limited (429): fallar explícitamente en
        # vez de devolver None y provocar un AttributeError en el llamador.
        raise RuntimeError(f"OneDrive: rate limit persistente tras {MAX_RETRIES} intentos: {url}")

    def _download_file(self, download_url: str, path: str) -> None:
        """Descarga un archivo desde la URL de descarga de Graph."""
        import requests
        headers = {"Authorization": f"Bearer {self.access_token}"}
        with requests.get(download_url, headers=headers, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=5 * 1024 * 1024):
                    f.write(chunk)

    def iter_media(self, root: Optional[str] = None) -> list[MediaItem]:
        if not self.is_authenticated():
            if not self.authenticate():
                return []

        if root:
            # root puede ser un item ID o una ruta como /Documents/Photos
            url = f"{GRAPH_BASE}/me/drive/items/{root}/children?$top=1000"
        else:
            url = f"{GRAPH_BASE}/me/drive/root/children?$top=1000"

        logger.info("OneDrive: listando archivos multimedia...")
        all_items = []

        while url:
            data = self._graph_get(url)
            children = data.get("value", [])

            for child in children:
                # Si es carpeta, recorrer recursivamente
                if "folder" in child:
                    sub_items = self.iter_media(root=child["id"])
                    all_items.extend(sub_items)
                    continue

                # Si es archivo, comprobar si es multimedia
                mime = child.get("file", {}).get("mimeType", "")
                name = child.get("name", "")
                ext = os.path.splitext(name)[1].lower()

                # Inferir MIME si Graph no lo proporciona o es genérico
                if not mime or mime == "application/octet-stream":
                    inferred = {
                        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
                        ".tiff": "image/tiff", ".tif": "image/tiff", ".svg": "image/svg+xml",
                        ".heic": "image/heic", ".heif": "image/heif", ".avif": "image/avif",
                        ".mp4": "video/mp4", ".avi": "video/avi", ".mov": "video/quicktime",
                        ".mkv": "video/x-matroska", ".webm": "video/webm", ".mpeg": "video/mpeg",
                        ".mpg": "video/mpeg", ".flv": "video/x-flv", ".wmv": "video/x-wmv",
                        ".3gp": "video/3gpp", ".3g2": "video/3gpp2",
                    }
                    if ext in inferred:
                        mime = inferred[ext]

                is_media = mime in IMAGE_MIMES | VIDEO_MIMES or ext in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
                if not is_media:
                    continue

                hashes = child.get("file", {}).get("hashes", {})
                img_meta = child.get("image", {})
                vid_meta = child.get("video", {})

                all_items.append(MediaItem(
                    source=self.name,
                    item_id=child["id"],
                    name=name,
                    mime_type=mime,
                    size=child.get("size", 0),
                    path=child.get("parentReference", {}).get("path"),
                    web_url=child.get("webUrl"),
                    modified_time=child.get("lastModifiedDateTime"),
                    sha256=hashes.get("sha256Hash"),
                    sha1=hashes.get("sha1Hash"),
                    quickxor=hashes.get("quickXorHash"),
                    width=img_meta.get("width"),
                    height=img_meta.get("height"),
                    duration_ms=vid_meta.get("duration"),
                ))

            # Paginación
            url = data.get("@odata.nextLink")

        logger.info(f"OneDrive: {len(all_items)} archivos multimedia encontrados.")
        return all_items

    def download_to_path(self, item: MediaItem, path: str) -> None:
        # Usar el endpoint de contenido de Graph
        url = f"{GRAPH_BASE}/me/drive/items/{item.item_id}/content"
        self._download_file(url, path)
