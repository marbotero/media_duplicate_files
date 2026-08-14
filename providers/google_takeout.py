"""
google_takeout.py — Provider para Google Takeout completo.

Recorre una carpeta de exportación de Google Takeout ya extraída y detecta
todos los medios (imágenes y videos) en cualquier subcarpeta del producto:

  - Google Photos/     → source: google_photos_takeout
  - Drive/             → source: google_drive_takeout
  - YouTube/           → source: youtube_takeout
  - Google Chat/       → source: google_chat_takeout
  - Hangouts/          → source: hangouts_takeout
  - Keep/              → source: google_keep_takeout
  - Blogger/           → source: blogger_takeout
  - (cualquier otra)   → source: google_takeout_other

Además, parsea los archivos JSON sidecar de Google Photos (.json junto al
archivo) para extraer metadatos como fecha de captura y URL original.

No necesita OAuth. Solo acceso al sistema de archivos local.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from typing import Optional

from providers.base import (
    StorageProvider, MediaItem, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
)

logger = logging.getLogger("media_dedupe")

# MIME types inferidos por extensión
EXT_TO_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    ".tiff": "image/tiff", ".tif": "image/tiff", ".svg": "image/svg+xml",
    ".heic": "image/heic", ".heif": "image/heif", ".avif": "image/avif",
    ".mp4": "video/mp4", ".avi": "video/avi", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".webm": "video/webm", ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg", ".flv": "video/x-flv", ".wmv": "video/x-wmv",
    ".3gp": "video/3gpp", ".3g2": "video/3gpp2",
}

# Extensiones a ignorar (no son medios)
IGNORE_EXTENSIONS = {
    ".json", ".html", ".htm", ".csv", ".txt", ".vtt", ".srt",
    ".xml", ".m3u", ".m3u8", ".pdf", ".doc", ".docx", ".zip",
    ".tar", ".gz", ".tgz", ".ico", ".js", ".css",
}

# Mapeo de carpeta de producto (primer nivel bajo Takeout/) a source lógico
PRODUCT_FOLDER_MAP = {
    "Google Photos": "google_photos_takeout",
    "Drive": "google_drive_takeout",
    "YouTube and YouTube Music": "youtube_takeout",
    "YouTube": "youtube_takeout",
    "YouTube Music": "youtube_takeout",
    "Google Chat": "google_chat_takeout",
    "Hangouts": "hangouts_takeout",
    "Keep": "google_keep_takeout",
    "Blogger": "blogger_takeout",
    "Google+ Collections": "google_plus_takeout",
    "Picasa Web Albums": "google_picasa_takeout",
}

# Source por defecto si la carpeta no coincide con ningún producto conocido
DEFAULT_TAKEOUT_SOURCE = "google_takeout_other"


class GoogleTakeoutProvider(StorageProvider):
    """
    Provider para Google Takeout completo.

    Recorre la carpeta de exportación de Takeout, detecta medios por extensión,
    asigna el source lógico según la carpeta del producto, y parsea JSON sidecars
    de Google Photos para metadatos adicionales.
    """

    name = "google_takeout"

    # Aliases para que el ProviderRouter pueda despachar items con
    # sources específicos (google_photos_takeout, youtube_takeout, etc.)
    source_aliases = list(PRODUCT_FOLDER_MAP.values()) + [DEFAULT_TAKEOUT_SOURCE, "google_takeout"]

    def __init__(self, base_folder: str):
        """
        Args:
            base_folder: Ruta a la carpeta de Takeout extraída.
                         Puede ser la carpeta raíz del ZIP o una subcarpeta.
        """
        self.base_folder = os.path.abspath(base_folder)

    def authenticate(self) -> bool:
        """No necesita autenticación. Solo verifica que la carpeta exista."""
        if not os.path.isdir(self.base_folder):
            logger.error(f"La carpeta no existe: {self.base_folder}")
            logger.error("Para usar Google Takeout:")
            logger.error("  1. Exporta tus datos desde https://takeout.google.com/")
            logger.error("  2. Selecciona los productos (Google Photos, Drive, YouTube, etc.)")
            logger.error("  3. Descarga y extrae el ZIP")
            logger.error("  4. Usa la carpeta extraída como argumento")
            return False
        logger.info(f"Google Takeout: carpeta válida: {self.base_folder}")
        return True

    def is_authenticated(self) -> bool:
        return os.path.isdir(self.base_folder)

    def _find_takeout_root(self) -> str:
        """
        Si la carpeta contiene una subcarpeta 'Takeout', usar esa.
        Si no, usar la carpeta directamente.
        """
        entries = os.listdir(self.base_folder)
        if len(entries) == 1:
            only = os.path.join(self.base_folder, entries[0])
            if os.path.isdir(only) and entries[0].lower().startswith("takeout"):
                return only
        return self.base_folder

    def _detect_product_source(self, file_path: str, takeout_root: str) -> str:
        """
        Detecta el source lógico basado en la primera carpeta de producto
        bajo la raíz de Takeout.
        """
        rel_path = os.path.relpath(file_path, takeout_root)
        parts = rel_path.split(os.sep)
        if parts and len(parts) > 0:
            first_folder = parts[0]
            return PRODUCT_FOLDER_MAP.get(first_folder, DEFAULT_TAKEOUT_SOURCE)
        return DEFAULT_TAKEOUT_SOURCE

    def _is_media_file(self, filename: str) -> tuple[bool, str]:
        """Comprueba si un archivo es multimedia por su extensión."""
        ext = os.path.splitext(filename)[1].lower()
        if ext in IGNORE_EXTENSIONS:
            return False, ""
        if ext in IMAGE_EXTENSIONS:
            return True, EXT_TO_MIME.get(ext, "application/octet-stream")
        if ext in VIDEO_EXTENSIONS:
            return True, EXT_TO_MIME.get(ext, "application/octet-stream")
        return False, ""

    def _find_sidecar_json(self, file_path: str) -> Optional[str]:
        """
        Busca el archivo JSON sidecar de Google Photos.
        Convenciones:
          - archivo.jpg.json
          - archivo.jpg.supplemental-metadata.json
          - (mismo directorio)
        """
        base = file_path
        candidates = [
            f"{base}.json",
            f"{base}.supplemental-metadata.json",
        ]
        # También probar sin extensión original: archivo.json
        stem = os.path.splitext(base)[0]
        candidates.append(f"{stem}.json")

        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    def _parse_sidecar(self, json_path: str) -> dict:
        """
        Parsea un JSON sidecar de Google Photos y extrae metadatos útiles.
        Campos conocidos:
          - photoTakenTime.timestamp (epoch seconds como string)
          - creationTime.timestamp
          - modificationTime.timestamp
          - url (URL original en Google Photos)
          - title (nombre original del archivo)
        """
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

        result = {}

        # Timestamp de captura de la foto
        taken = data.get("photoTakenTime", {})
        if isinstance(taken, dict) and "timestamp" in taken:
            try:
                ts = int(taken["timestamp"])
                result["modified_time"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(ts)
                )
            except (ValueError, TypeError):
                pass

        # Fallback: creationTime
        if "modified_time" not in result:
            created = data.get("creationTime", {})
            if isinstance(created, dict) and "timestamp" in created:
                try:
                    ts = int(created["timestamp"])
                    result["modified_time"] = time.strftime(
                        "%Y-%m-%dT%H:%M:%S", time.gmtime(ts)
                    )
                except (ValueError, TypeError):
                    pass

        # URL original
        url = data.get("url")
        if url:
            result["web_url"] = url

        # Dimensiones si están presentes
        geo = data.get("geoData", {}) or data.get("geoDataExif", {})
        # Google Photos JSON no incluye width/height directamente,
        # pero podrían estar en algunos casos
        return result

    def iter_media(self, root: Optional[str] = None) -> list[MediaItem]:
        if not self.is_authenticated():
            if not self.authenticate():
                return []

        scan_folder = root if root else self._find_takeout_root()
        logger.info(f"Google Takeout: escaneando '{scan_folder}'...")

        items = []
        count = 0
        stats_by_source = {}

        for dirpath, dirnames, filenames in os.walk(scan_folder):
            for filename in filenames:
                is_media, mime_type = self._is_media_file(filename)
                if not is_media:
                    continue

                full_path = os.path.join(dirpath, filename)
                try:
                    size = os.path.getsize(full_path)
                    mtime = os.path.getmtime(full_path)
                except OSError:
                    continue

                if size == 0:
                    continue

                # Detectar source lógico
                source = self._detect_product_source(full_path, scan_folder)
                stats_by_source[source] = stats_by_source.get(source, 0) + 1

                # Metadatos por defecto
                modified_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime))
                web_url = None

                # Parsear JSON sidecar si existe (mejora metadatos)
                sidecar = self._find_sidecar_json(full_path)
                if sidecar:
                    extra = self._parse_sidecar(sidecar)
                    if extra.get("modified_time"):
                        modified_time = extra["modified_time"]
                    if extra.get("web_url"):
                        web_url = extra["web_url"]

                items.append(MediaItem(
                    source=source,
                    item_id=full_path,
                    name=filename,
                    mime_type=mime_type,
                    size=size,
                    path=full_path,
                    web_url=web_url,
                    modified_time=modified_time,
                ))
                count += 1
                if count % 500 == 0:
                    logger.info(f"  Google Takeout: {count} medios encontrados...")

        # Resumen por producto
        for src, cnt in sorted(stats_by_source.items()):
            logger.info(f"  {src}: {cnt} archivos")

        logger.info(f"Google Takeout: {len(items)} medios encontrados en total.")
        return items

    def download_to_path(self, item: MediaItem, path: str) -> None:
        """Para archivos locales, simplemente copia el archivo."""
        if item.path and os.path.exists(item.path):
            shutil.copy2(item.path, path)
        else:
            raise FileNotFoundError(f"Archivo no encontrado: {item.path}")

    def compute_hashes(self, item: MediaItem) -> tuple[Optional[str], Optional[str]]:
        """Calcula MD5 y SHA-256 leyendo el archivo local directamente."""
        if not item.path or not os.path.exists(item.path):
            return None, None

        import hashlib
        md5_hasher = hashlib.md5()
        sha256_hasher = hashlib.sha256()

        with open(item.path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                md5_hasher.update(chunk)
                sha256_hasher.update(chunk)

        return md5_hasher.hexdigest(), sha256_hasher.hexdigest()
