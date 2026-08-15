"""
hashing.py — Cálculo de hashes MD5 y SHA-256 para archivos.

Soporta archivos locales y descargados desde providers remotos.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from typing import Optional

from providers.base import MediaItem
from core.metadata import extract_metadata

logger = logging.getLogger("media_dedupe")


def compute_hashes_from_file(path: str) -> tuple[Optional[str], Optional[str]]:
    """
    Calcula MD5 y SHA-256 de un archivo local.
    Devuelve (md5_hex, sha256_hex).
    """
    md5_hasher = hashlib.md5()
    sha256_hasher = hashlib.sha256()

    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                md5_hasher.update(chunk)
                sha256_hasher.update(chunk)
        return md5_hasher.hexdigest(), sha256_hasher.hexdigest()
    except Exception as e:
        logger.warning(f"Error calculando hashes de '{path}': {e}")
        return None, None


def compute_hashes_from_provider(
    item: MediaItem,
    provider,
    cache_dir: str,
) -> tuple[Optional[str], Optional[str]]:
    """
    Descarga un archivo desde un provider remoto y calcula MD5 + SHA-256.
    El archivo se descarga a un directorio temporal y se elimina tras procesarlo.
    """
    # Si el item ya tiene ambos hashes, no hacer nada
    if item.md5 and item.sha256:
        return item.md5, item.sha256

    os.makedirs(cache_dir, exist_ok=True)
    tmp_path = os.path.join(cache_dir, f"{item.source}_{item.item_id}.tmp")

    try:
        provider.download_to_path(item, tmp_path)
        md5, sha256 = compute_hashes_from_file(tmp_path)

        if md5:
            item.md5 = md5
        if sha256:
            item.sha256 = sha256

        # Extraer metadatos del archivo descargado
        try:
            metadata = extract_metadata(tmp_path)
            if metadata:
                if not item.extra:
                    item.extra = {}
                item.extra["metadata"] = metadata
        except Exception:
            pass

        return md5, sha256
    except Exception as e:
        logger.warning(f"Error descargando/calculando hashes de '{item.name}': {e}")
        return item.md5, item.sha256
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def ensure_hashes(
    item: MediaItem,
    provider,
    cache_dir: str,
) -> MediaItem:
    """
    Garantiza que el item tenga MD5 y SHA-256.
    - Si el provider ya los proporcionó (metadatos), los usa.
    - Si no, descarga el archivo y los calcula.
    """
    # Provider de WhatsApp local: calcular directamente
    if hasattr(provider, "compute_hashes"):
        if not item.md5 or not item.sha256:
            md5, sha256 = provider.compute_hashes(item)
            if md5:
                item.md5 = md5
            if sha256:
                item.sha256 = sha256
        return item

    # Providers remotos: descargar y calcular si faltan
    if not item.md5 or not item.sha256:
        compute_hashes_from_provider(item, provider, cache_dir)

    return item
