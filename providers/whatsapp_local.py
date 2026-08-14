"""
whatsapp_local.py — Provider para fotos/videos de WhatsApp desde carpeta local.

WhatsApp no expone una API pública para recorrer el almacenamiento de fotos.
Este provider soporta:
  - Carpeta de WhatsApp Desktop (Windows/Mac)
  - Carpeta de medios de WhatsApp exportada desde el teléfono
  - Carpeta montada del teléfono conectado por USB (Android: /storage/.../WhatsApp/Media)

Subcarpetas típicas que se escanean:
  - WhatsApp Images/
  - WhatsApp Video/
  - WhatsApp Animated Gifs/
  - WhatsApp Voice Notes/  (ignorado — no es imagen/video)
  - WhatsApp Documents/    (escaneado por extensión)

No necesita OAuth. Solo acceso al sistema de archivos local.
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

logger = logging.getLogger("media_dedupe")

# Subcarpetas típicas de medios de WhatsApp
WHATSAPP_MEDIA_SUBDIRS = [
    "WhatsApp Images",
    "WhatsApp Video",
    "WhatsApp Animated Gifs",
    "WhatsApp Documents",
    "WhatsApp Media",  # Algunos teléfonos usan esta estructura
]

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


class WhatsAppLocalProvider(StorageProvider):
    """Provider para medios de WhatsApp desde carpeta local."""

    name = "whatsapp_local"

    def __init__(self, base_folder: str):
        """
        Args:
            base_folder: Ruta a la carpeta de medios de WhatsApp.
                         Ej: /home/user/Downloads/WhatsApp
                             C:\\Users\\user\\Documents\\WhatsApp
                             /run/user/1000/gvfs/.../WhatsApp/Media
        """
        self.base_folder = os.path.abspath(base_folder)

    def authenticate(self) -> bool:
        """No necesita autenticación. Solo verifica que la carpeta exista."""
        if not os.path.isdir(self.base_folder):
            logger.error(f"La carpeta no existe: {self.base_folder}")
            logger.error("Para fotos de WhatsApp:")
            logger.error("  Android por USB: copia la carpeta WhatsApp/Media al PC")
            logger.error("  WhatsApp Desktop: busca en Descargas o Documentos")
            logger.error("  Exportación de chat: usa la carpeta extraída")
            return False
        logger.info(f"WhatsApp Local: carpeta válida: {self.base_folder}")
        return True

    def is_authenticated(self) -> bool:
        return os.path.isdir(self.base_folder)

    def _is_media_file(self, filename: str) -> tuple[bool, str]:
        """Comprueba si un archivo es multimedia por su extensión. Devuelve (es_media, mime_type)."""
        ext = os.path.splitext(filename)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            return True, EXT_TO_MIME.get(ext, "application/octet-stream")
        if ext in VIDEO_EXTENSIONS:
            return True, EXT_TO_MIME.get(ext, "application/octet-stream")
        return False, ""

    def iter_media(self, root: Optional[str] = None) -> list[MediaItem]:
        if not self.is_authenticated():
            if not self.authenticate():
                return []

        scan_folder = root if root else self.base_folder
        if not os.path.isabs(scan_folder):
            scan_folder = os.path.join(self.base_folder, scan_folder)

        logger.info(f"WhatsApp Local: escaneando '{scan_folder}'...")
        items = []
        count = 0

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

                # Ignorar archivos vacíos
                if size == 0:
                    continue

                items.append(MediaItem(
                    source=self.name,
                    item_id=full_path,  # Usar la ruta como ID único
                    name=filename,
                    mime_type=mime_type,
                    size=size,
                    path=full_path,
                    web_url=None,
                    modified_time=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime)),
                ))
                count += 1
                if count % 500 == 0:
                    logger.info(f"  WhatsApp Local: {count} archivos encontrados...")

        logger.info(f"WhatsApp Local: {len(items)} archivos multimedia encontrados.")
        return items

    def download_to_path(self, item: MediaItem, path: str) -> None:
        """Para archivos locales, simplemente copia el archivo."""
        import shutil
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
