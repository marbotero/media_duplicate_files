"""Tests de manejo de rate limit 429 persistente (bug B4).

Antes del fix, si todos los reintentos devolvían 429 la función retornaba None y
el llamador reventaba con AttributeError. Ahora eleva un RuntimeError manejable.
"""

import pytest
import requests

from providers.google_photos import GooglePhotosProvider
from providers.onedrive import OneDriveProvider


class _Resp429:
    status_code = 429
    headers = {"Retry-After": "0"}  # 0 → sin espera real en el test

    def json(self):
        return {}

    def raise_for_status(self):
        pass


def test_onedrive_raises_on_persistent_429(monkeypatch):
    provider = OneDriveProvider()
    provider.access_token = "token"
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp429())

    with pytest.raises(RuntimeError):
        provider._graph_get("https://graph.microsoft.com/v1.0/me/drive/root")


def test_google_photos_raises_on_persistent_429():
    provider = object.__new__(GooglePhotosProvider)

    class _Session:
        def get(self, *a, **k):
            return _Resp429()

        def post(self, *a, **k):
            return _Resp429()

    provider.session = _Session()

    with pytest.raises(RuntimeError):
        provider._api_get("https://photoslibrary.googleapis.com/v1/mediaItems")
    with pytest.raises(RuntimeError):
        provider._api_post("https://photoslibrary.googleapis.com/v1/mediaItems:search", {})
