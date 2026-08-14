"""
base.py — Interfaz común para todos los providers de almacenamiento.

Cada provider (Google Drive, OneDrive, WhatsApp Local) implementa
esta interfaz para listar y descargar archivos multimedia.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("media_dedupe")

# MIME types de interés
IMAGE_MIMES = {
    "image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp",
    "image/tiff", "image/x-tiff", "image/svg+xml", "image/heic",
    "image/heif", "image/avif",
}
VIDEO_MIMES = {
    "video/mp4", "video/avi", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm", "video/mpeg", "video/x-flv",
    "video/x-wmv", "video/3gpp", "video/3gpp2",
}
MEDIA_MIMES = IMAGE_MIMES | VIDEO_MIMES

# Extensiones comunes para detección por extensión cuando el MIME no es fiable
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".heic", ".heif", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpeg", ".mpg", ".flv", ".wmv", ".3gp", ".3g2"}


@dataclass
class MediaItem:
    """Representa un archivo multimedia encontrado en cualquier origen."""
    source: str              # google_drive, onedrive, whatsapp_local
    item_id: str             # ID único dentro del provider
    name: str
    mime_type: str
    size: int
    path: Optional[str] = None          # Ruta local o estructura de carpetas
    web_url: Optional[str] = None       # URL para abrir en navegador
    modified_time: Optional[str] = None
    # Hashes (se calculan progresivamente)
    md5: Optional[str] = None
    sha256: Optional[str] = None
    sha1: Optional[str] = None          # OneDrive a veces provee SHA-1
    quickxor: Optional[str] = None      # OneDrive quickXorHash
    # Metadatos de medios
    width: Optional[int] = None
    height: Optional[int] = None
    duration_ms: Optional[int] = None
    # Hash perceptual (se calcula al descargar)
    phash: Optional[str] = None
    video_frame_hashes: list = field(default_factory=list)

    @property
    def is_image(self) -> bool:
        return self.mime_type in IMAGE_MIMES

    @property
    def is_video(self) -> bool:
        return self.mime_type in VIDEO_MIMES

    @property
    def is_binary_media(self) -> bool:
        return self.is_image or self.is_video

    @property
    def hash_key(self) -> tuple:
        """Clave para detectar duplicados exactos: prioriza SHA-256, luego MD5."""
        if self.sha256:
            return ("sha256", self.sha256, self.size)
        if self.md5:
            return ("md5", self.md5, self.size)
        return ("none", self.item_id, self.size)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Asegurar tipos nativos de Python (numpy puede devolver int64)
        d["size"] = int(d["size"]) if d["size"] else 0
        if d.get("width"):
            d["width"] = int(d["width"])
        if d.get("height"):
            d["height"] = int(d["height"])
        if d.get("duration_ms"):
            d["duration_ms"] = int(d["duration_ms"])
        return d


class StorageProvider(abc.ABC):
    """Interfaz base para todos los providers de almacenamiento."""

    name: str = "base"

    @abc.abstractmethod
    def authenticate(self) -> bool:
        """Autentica con el provider. Devuelve True si tuvo éxito."""
        ...

    @abc.abstractmethod
    def iter_media(self, root: Optional[str] = None) -> list[MediaItem]:
        """Lista todos los archivos multimedia. Si se especifica root, lista solo de esa carpeta."""
        ...

    @abc.abstractmethod
    def download_to_path(self, item: MediaItem, path: str) -> None:
        """Descarga un archivo a la ruta especificada."""
        ...

    def is_authenticated(self) -> bool:
        """Verifica si ya está autenticado."""
        return False
