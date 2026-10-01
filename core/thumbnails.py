"""
thumbnails.py — Generación de miniaturas JPEG para archivos locales.

- Imágenes: PIL (con soporte HEIC/HEIF vía pillow-heif si está instalado).
- Videos: un frame extraído con ffmpeg y miniaturizado.

Las miniaturas se cachean en `reports/cache/thumbnails/` con clave derivada de la
ruta + mtime + tamaño, de modo que no se regeneran salvo que el archivo cambie.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from config.paths import REPORTES_CACHE
from providers.base import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

logger = logging.getLogger("media_dedupe")

_THUMB_DIR = Path(REPORTES_CACHE) / "thumbnails"

# Registrar el decodificador HEIC/HEIF si pillow-heif está disponible. Muchas
# fotos de móvil (WhatsApp/iPhone) son HEIC y PIL no las abre sin esto.
try:  # pragma: no cover - depende del entorno
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass


def _cache_path(path: str, size: Tuple[int, int]) -> Path:
    st = os.stat(path)
    raw = f"{os.path.abspath(path)}|{st.st_mtime_ns}|{st.st_size}|{size[0]}x{size[1]}"
    nombre = hashlib.sha1(raw.encode("utf-8")).hexdigest() + ".jpg"
    return _THUMB_DIR / nombre


def _frame_de_video(path: str, dest: str) -> bool:
    """Extrae un frame representativo del video a `dest` (JPEG). True si tuvo éxito."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "1", "-i", path, "-frames:v", "1",
             "-vf", "scale=320:320:force_original_aspect_ratio=decrease",
             "-q:v", "3", dest],
            capture_output=True, timeout=30,
        )
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception as e:  # pragma: no cover - depende de ffmpeg
        logger.debug("ffmpeg no pudo extraer frame de %s: %s", path, e)
        return False


def generar_miniatura(path: str, size: Tuple[int, int] = (320, 320)) -> Optional[bytes]:
    """Devuelve los bytes JPEG de la miniatura, o None si no se puede generar."""
    try:
        from PIL import Image
    except ImportError:
        logger.error("Instala Pillow para generar miniaturas: pip install Pillow")
        return None

    if not path or not os.path.isfile(path):
        return None

    cache_file = _cache_path(path, size)
    if cache_file.exists():
        try:
            return cache_file.read_bytes()
        except OSError:
            pass

    _THUMB_DIR.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    tmp_frame = None

    try:
        if ext in VIDEO_EXTENSIONS:
            fd, tmp_frame = tempfile.mkstemp(suffix=".jpg", dir=str(_THUMB_DIR))
            os.close(fd)
            if not _frame_de_video(path, tmp_frame):
                return None
            img = Image.open(tmp_frame)
        else:
            # Imágenes (incluye HEIC si pillow-heif está registrado).
            img = Image.open(path)

        img = img.convert("RGB")
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img.save(cache_file, "JPEG", quality=85)
        return cache_file.read_bytes()
    except Exception as e:
        logger.debug("No se pudo miniaturizar %s: %s", path, e)
        return None
    finally:
        if tmp_frame and os.path.exists(tmp_frame):
            os.remove(tmp_frame)
