#!/usr/bin/env python3
"""
providers/local_folder.py — Provider para escanear cualquier carpeta local.

Recorre recursivamente una carpeta del sistema de archivos y detecta
imagenes y videos por extension. Calcula MD5 y SHA-256 directamente.
"""

import hashlib
import mimetypes
import os
import shutil
from pathlib import Path

from providers.base import MediaItem
from core.metadata import extract_metadata, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

# Extensiones que este provider puede procesar
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


class LocalFolderProvider:
    """Provider que escanea una carpeta local arbitraria."""

    name = "local_folder"
    source = "local_folder"
    source_aliases = ["local_folder"]

    def __init__(self, base_folder: str):
        self.base_folder = str(base_folder)
        if not os.path.isdir(self.base_folder):
            raise FileNotFoundError(f"La carpeta no existe: {self.base_folder}")

    def authenticate(self):
        """No requiere autenticación. Verifica que la carpeta existe."""
        if not os.path.isdir(self.base_folder):
            raise FileNotFoundError(f"La carpeta no existe: {self.base_folder}")
        return True

    def iter_media(self, root=None):
        """Recorre la carpeta recursivamente y genera MediaItems."""
        for dirpath, dirs, files in os.walk(self.base_folder):
            # Ignorar carpetas ocultas y __pycache__
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            for filename in files:
                ext = Path(filename).suffix.lower()

                # Ignorar JSON sidecars y archivos ocultos
                if filename.startswith(".") or ext == ".json":
                    continue

                if ext not in MEDIA_EXTENSIONS:
                    continue

                file_path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(file_path)
                except OSError:
                    continue

                # Inferir MIME
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = "image/jpeg" if ext in IMAGE_EXTENSIONS else "video/mp4"

                is_image = ext in IMAGE_EXTENSIONS
                is_video = ext in VIDEO_EXTENSIONS

                # Extraer metadatos locales
                metadata = {}
                try:
                    metadata = extract_metadata(file_path)
                except Exception:
                    pass

                yield MediaItem(
                    source=self.source,
                    item_id=os.path.relpath(file_path, self.base_folder),
                    name=filename,
                    path=file_path,
                    mime_type=mime_type,
                    size=stat.st_size,
                    modified_time=stat.st_mtime,
                    md5=None,
                    sha256=None,
                    web_url=None,
                    extra={"metadata": metadata} if metadata else {},
                )

    def compute_hashes(self, item: MediaItem) -> tuple[str | None, str | None]:
        """Calcula MD5 y SHA-256 del archivo local."""
        return self._compute_file_hashes(item.path)

    def download_to_path(self, item: MediaItem, local_path: str) -> str:
        """Copia el archivo a la ruta indicada."""
        shutil.copy2(item.path, local_path)
        return local_path

    @staticmethod
    def _compute_file_hashes(file_path: str) -> tuple[str | None, str | None]:
        """Calcula MD5 y SHA-256 de un archivo."""
        md5_hasher = hashlib.md5()
        sha256_hasher = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192 * 1024)  # 8 MB chunks
                    if not chunk:
                        break
                    md5_hasher.update(chunk)
                    sha256_hasher.update(chunk)
            return md5_hasher.hexdigest(), sha256_hasher.hexdigest()
        except Exception:
            return None, None
