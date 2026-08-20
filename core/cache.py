"""
cache.py — Caché SQLite para evitar redescargar y recalcular hashes.

Clave: (source, item_id, size, modified_time)
Almacena: md5, sha256, phash, video_frame_hashes
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Optional

logger = logging.getLogger("media_dedupe")

SCHEMA = """
CREATE TABLE IF NOT EXISTS media_cache (
    source TEXT NOT NULL,
    item_id TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_time TEXT,
    md5 TEXT,
    sha256 TEXT,
    phash TEXT,
    video_frame_hashes TEXT,
    PRIMARY KEY (source, item_id, size, modified_time)
);
"""


class MediaCache:
    """Caché en SQLite para metadatos y hashes calculados."""

    def __init__(self, db_path: str = "media_cache.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(SCHEMA)
        self.conn.commit()
        logger.debug(f"Caché SQLite: {db_path}")

    def get(
        self, source: str, item_id: str, size: int, modified_time: Optional[str]
    ) -> Optional[dict]:
        """Recupera un item de la caché. Devuelve dict con hashes o None."""
        cursor = self.conn.execute(
            "SELECT md5, sha256, phash, video_frame_hashes FROM media_cache "
            "WHERE source=? AND item_id=? AND size=? AND modified_time IS ?",
            (source, item_id, size, modified_time),
        )
        row = cursor.fetchone()
        if row:
            return {
                "md5": row[0],
                "sha256": row[1],
                "phash": row[2],
                "video_frame_hashes": json.loads(row[3]) if row[3] else [],
            }
        return None

    def put(
        self,
        source: str,
        item_id: str,
        size: int,
        modified_time: Optional[str],
        md5: Optional[str] = None,
        sha256: Optional[str] = None,
        phash: Optional[str] = None,
        video_frame_hashes: Optional[list] = None,
        commit: bool = True,
    ) -> None:
        """Guarda o actualiza un item en la caché."""
        self.conn.execute(
            "INSERT OR REPLACE INTO media_cache "
            "(source, item_id, size, modified_time, md5, sha256, phash, video_frame_hashes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source, item_id, size, modified_time,
                md5, sha256, phash,
                json.dumps(video_frame_hashes) if video_frame_hashes else None,
            ),
        )
        if commit:
            self.conn.commit()

    def commit(self) -> None:
        """Confirma una tanda de actualizaciones de cache."""
        self.conn.commit()

    def close(self):
        self.conn.close()
