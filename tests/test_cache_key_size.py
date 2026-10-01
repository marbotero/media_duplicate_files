"""Test de la invariante de clave de caché para Google Photos (bug B3).

Google Photos reporta size=0 al listar y el valor real tras descargar. La clave
de caché incluye el tamaño, así que get y put deben usar el MISMO tamaño (el del
listado) o la caché falla siempre. Este test documenta esa sensibilidad.
"""

from core.cache import MediaCache


def test_cache_hit_requires_consistent_key_size(tmp_path):
    cache = MediaCache(str(tmp_path / "cache.db"))
    # Guardado con el tamaño de listado (0), como hace ahora el flujo de hashing.
    cache.put("google_photos", "gp1", 0, "t", md5="m", sha256="s", commit=True)

    # Con el mismo tamaño de clave → acierto (evita re-descargar).
    assert cache.get("google_photos", "gp1", 0, "t") is not None
    # Con el tamaño real (post-descarga) → fallo: por eso hay que fijar key_size.
    assert cache.get("google_photos", "gp1", 123456, "t") is None
    cache.close()
