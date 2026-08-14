"""
ProviderRouter — Despaca download_to_path según el origen del item.
Permite comparar casi-duplicados entre diferentes providers.
"""

from __future__ import annotations

import logging
from providers.base import MediaItem

logger = logging.getLogger("media_dedupe")


class ProviderRouter:
    """Router que despacha descargas al provider correcto según item.source."""

    def __init__(self, providers: dict):
        """
        Args:
            providers: dict {source_name: StorageProvider}
        """
        self.providers = providers

    def download_to_path(self, item: MediaItem, path: str) -> None:
        provider = self.providers.get(item.source)
        if not provider:
            raise ValueError(f"No hay provider registrado para source='{item.source}'")
        provider.download_to_path(item, path)

    @property
    def name(self):
        return "router"
