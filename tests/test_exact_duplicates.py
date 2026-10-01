"""Tests de agrupación de duplicados exactos entre proveedores (bug B2)."""

from core.similarity import find_exact_duplicates
from providers.base import MediaItem


def _item(source, item_id, size, **hashes):
    return MediaItem(
        source=source, item_id=item_id, name=item_id,
        mime_type="image/jpeg", size=size, **hashes,
    )


def test_hashes_are_normalized_to_lowercase():
    it = _item("onedrive", "o1", 10, sha256="AABBCC")
    assert it.sha256 == "aabbcc"


def test_case_insensitive_cross_provider_grouping():
    # Mismo contenido: local (minúsculas) y OneDrive (mayúsculas, como Graph).
    local = _item("local_folder", "l1", 100, md5="m1", sha256="s1")
    onedrive = _item("onedrive", "o1", 100, sha256="S1")

    groups = find_exact_duplicates([local, onedrive])

    assert len(groups) == 1
    assert len(groups[0].files) == 2


def test_union_across_different_algorithms():
    # A expone md5+sha256; B solo md5 (mismo valor). Deben unirse por el md5
    # compartido aunque no compartan sha256.
    a = _item("local_folder", "a", 50, md5="mm", sha256="ss")
    b = _item("google_drive", "b", 50, md5="mm")
    c = _item("google_drive", "c", 50, md5="otro")

    groups = find_exact_duplicates([a, b, c])

    assert len(groups) == 1
    keys = {(f.source, f.item_id) for f in groups[0].files}
    assert keys == {("local_folder", "a"), ("google_drive", "b")}


def test_items_without_hashes_do_not_group():
    a = _item("google_photos", "a", 0)
    b = _item("google_photos", "b", 0)

    assert find_exact_duplicates([a, b]) == []
