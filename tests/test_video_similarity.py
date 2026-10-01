"""Tests del umbral de similitud de video (bug B1)."""

from core.similarity import find_similar_videos
from providers.base import MediaItem


def _video(item_id, frames):
    it = MediaItem(
        source="local_folder", item_id=item_id, name=item_id,
        mime_type="video/mp4", size=1000,
    )
    it.video_frame_hashes = frames
    return it


def test_dissimilar_videos_are_not_grouped():
    # Frames completamente distintos (distancia Hamming 64). Antes del fix la
    # condición era siempre verdadera y los agrupaba igualmente.
    a = _video("a", ["0000000000000000"] * 8)
    b = _video("b", ["ffffffffffffffff"] * 8)

    groups = find_similar_videos([a, b], provider=None, cache_dir="",
                                 threshold=0.85, image_threshold=95)

    assert groups == []


def test_identical_videos_are_grouped():
    a = _video("a", ["0000000000000000"] * 8)
    b = _video("b", ["0000000000000000"] * 8)

    groups = find_similar_videos([a, b], provider=None, cache_dir="",
                                 threshold=0.85, image_threshold=95)

    assert len(groups) == 1
    assert len(groups[0].files) == 2
