"""
similarity.py — Detección de casi-duplicados usando hashing perceptual.

- Imágenes: pHash (perceptual hash) con distancia Hamming.
- Videos: extracción de frames con ffmpeg + pHash de cada frame.
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from providers.base import MediaItem

logger = logging.getLogger("media_dedupe")

# Umbrales por defecto
DEFAULT_IMAGE_THRESHOLD = 95.0   # Porcentaje mínimo de similitud para imágenes
DEFAULT_VIDEO_THRESHOLD = 0.85   # Ratio mínimo de frames similares
VIDEO_NUM_FRAMES = 8
VIDEO_FRAME_THRESHOLD_OFFSET = 3  # Umbral más laxo para frames individuales


class _BKTree:
    """Índice para consultar hashes perceptuales cercanos por distancia Hamming."""

    def __init__(self):
        self.root = None

    def add(self, hash_value, index):
        if self.root is None:
            self.root = (hash_value, [index], {})
            return
        node = self.root
        while True:
            distance = hash_value - node[0]
            if distance == 0:
                node[1].append(index)
                return
            child = node[2].get(distance)
            if child is None:
                node[2][distance] = (hash_value, [index], {})
                return
            node = child

    def query(self, hash_value, max_distance):
        if self.root is None:
            return []
        matches = []
        pending = [self.root]
        while pending:
            node = pending.pop()
            distance = hash_value - node[0]
            if distance <= max_distance:
                matches.extend(node[1])
            lower = max(1, distance - max_distance)
            upper = distance + max_distance
            pending.extend(
                child for edge, child in node[2].items()
                if lower <= edge <= upper
            )
        return matches


def image_similarity_percent(hash_a, hash_b) -> float:
    """Calcula la similitud entre dos hashes pHash como porcentaje de 0 a 100."""
    if hash_a is None or hash_b is None:
        return 0.0

    distance = hash_a - hash_b
    max_bits = 64
    similarity = (1 - (distance / max_bits)) * 100
    return max(0.0, min(100.0, similarity))


@dataclass
class DuplicateGroup:
    """Grupo de archivos duplicados o casi-duplicados."""
    group_type: str          # "exact", "image_similar", "video_similar"
    files: list              # Lista de MediaItem
    score: float = 0.0
    recoverable_size: int = 0

    def to_dict(self) -> dict:
        return {
            "group_type": self.group_type,
            "score": float(self.score),
            "recoverable_size": int(self.recoverable_size),
            "files": [f.to_dict() if isinstance(f, MediaItem) else f for f in self.files],
        }


# ─── Hashing perceptual de imágenes ───────────────────────────────────────────

def compute_image_phash(item: MediaItem, provider, cache_dir: str) -> Optional[str]:
    """Descarga una imagen y calcula su perceptual hash (pHash)."""
    if item.phash:
        return item.phash

    try:
        import imagehash
        from PIL import Image
    except ImportError:
        logger.error("Instala Pillow e imagehash: pip install Pillow imagehash")
        return None

    try:
        # Si es archivo local (WhatsApp), abrir directamente
        if item.path and os.path.exists(item.path):
            with Image.open(item.path) as img:
                item.phash = str(imagehash.phash(img))
        else:
            # Descargar a temporal
            tmp_path = os.path.join(cache_dir, f"{item.source}_{item.item_id}_img.tmp")
            try:
                provider.download_to_path(item, tmp_path)
                with Image.open(tmp_path) as img:
                    item.phash = str(imagehash.phash(img))
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        return item.phash
    except Exception as e:
        logger.warning(f"  No se pudo procesar imagen '{item.name}': {e}")
        return None


def find_similar_images(
    items: list[MediaItem],
    provider,
    cache_dir: str,
    threshold: float = DEFAULT_IMAGE_THRESHOLD,
) -> list[DuplicateGroup]:
    """Encuentra imágenes casi-duplicadas usando porcentaje de similitud pHash."""
    try:
        import imagehash
    except ImportError:
        logger.error("Instala imagehash: pip install imagehash")
        return []

    images = [it for it in items if it.is_image]
    if len(images) < 2:
        return []

    logger.info(f"Procesando {len(images)} imágenes con pHash...")

    hashed = []
    for i, item in enumerate(images):
        ph = compute_image_phash(item, provider, cache_dir)
        if ph:
            hashed.append(item)
        if (i + 1) % 50 == 0:
            logger.info(f"  Procesadas {i+1}/{len(images)} imágenes...")

    logger.info(f"Comparando {len(hashed)} imágenes con hash válido...")

    parent = list(range(len(hashed)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    best_similarity = defaultdict(lambda: 0.0)
    hash_objects = [imagehash.hex_to_hash(item.phash) for item in hashed]
    max_distance = int((100 - threshold) * 64 / 100)
    index = _BKTree()
    for item_index, hash_object in enumerate(hash_objects):
        for candidate_index in index.query(hash_object, max_distance):
            pct = image_similarity_percent(hash_object, hash_objects[candidate_index])
            if pct >= threshold:
                union(item_index, candidate_index)
                best_similarity[(item_index, candidate_index)] = pct
                best_similarity[(candidate_index, item_index)] = pct
        index.add(hash_object, item_index)

    groups = defaultdict(list)
    for i in range(len(hashed)):
        groups[find(i)].append(i)

    duplicates = []
    for group_indices in groups.values():
        if len(group_indices) > 1:
            group_files = [hashed[i] for i in group_indices]
            best_pct = 0.0
            for i in group_indices:
                for j in group_indices:
                    if i != j:
                        pct = best_similarity.get((i, j), 0.0)
                        if pct > best_pct:
                            best_pct = pct
            total_size = sum(f.size for f in group_files)
            max_size = max(f.size for f in group_files)
            duplicates.append(DuplicateGroup(
                group_type="image_similar",
                files=group_files,
                score=best_pct,
                recoverable_size=total_size - max_size,
            ))

    logger.info(f"Encontrados {len(duplicates)} grupos de imágenes similares.")
    return duplicates


# ─── Hashing perceptual de videos ────────────────────────────────────────────

def extract_video_frames(item: MediaItem, provider, cache_dir: str, num_frames: int) -> list[str]:
    """
    Descarga un video, extrae N frames uniformemente distribuidos
    y calcula el pHash de cada frame.
    """
    if item.video_frame_hashes:
        return item.video_frame_hashes

    try:
        import imagehash
        from PIL import Image
    except ImportError:
        logger.error("Instala Pillow e imagehash")
        return []

    tmp_video = os.path.join(cache_dir, f"{item.source}_{item.item_id}_vid.tmp")

    try:
        # Obtener el video
        if item.path and os.path.exists(item.path):
            tmp_video = item.path  # Usar directamente si es local
        else:
            provider.download_to_path(item, tmp_video)

        # Obtener duración con ffprobe
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", tmp_video],
                capture_output=True, text=True, timeout=30,
            )
            probe_data = json.loads(probe.stdout)
            duration = float(probe_data.get("format", {}).get("duration", "0"))
        except Exception:
            duration = 0.0

        if duration <= 0:
            timestamps = [i * 10 / (num_frames + 1) for i in range(1, num_frames + 1)]
        else:
            timestamps = [duration * (i + 1) / (num_frames + 1) for i in range(num_frames)]

        frame_hashes = []
        for ts in timestamps:
            frame_path = os.path.join(cache_dir, f"{item.source}_{item.item_id}_{ts:.3f}.jpg")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(ts), "-i", tmp_video,
                     "-frames:v", "1", "-vf", "scale=256:256:force_original_aspect_ratio=decrease",
                     "-q:v", "2", frame_path],
                    capture_output=True, timeout=30,
                )
                if os.path.exists(frame_path):
                    img = Image.open(frame_path)
                    ph = str(imagehash.phash(img))
                    frame_hashes.append(ph)
                    os.remove(frame_path)
            except Exception as e:
                logger.warning(f"    Frame {ts:.1f}s de '{item.name}': {e}")

        item.video_frame_hashes = frame_hashes
        return frame_hashes

    except Exception as e:
        logger.warning(f"  No se pudo procesar video '{item.name}': {e}")
        return []
    finally:
        # Solo limpiar si era un archivo temporal descargado
        if not item.path and os.path.exists(tmp_video):
            os.remove(tmp_video)


def find_similar_videos(
    items: list[MediaItem],
    provider,
    cache_dir: str,
    threshold: float = DEFAULT_VIDEO_THRESHOLD,
    image_threshold: int = DEFAULT_IMAGE_THRESHOLD,
    num_frames: int = VIDEO_NUM_FRAMES,
) -> list[DuplicateGroup]:
    """Encuentra videos casi-duplicados comparando frames extraídos."""
    try:
        import imagehash
    except ImportError:
        logger.error("Instala imagehash")
        return []

    videos = [it for it in items if it.is_video]
    if len(videos) < 2:
        return []

    logger.info(f"Procesando {len(videos)} videos (extracción de frames)...")

    hashed = []
    for i, item in enumerate(videos):
        frames = extract_video_frames(item, provider, cache_dir, num_frames)
        if len(frames) >= 2:
            hashed.append(item)
        if (i + 1) % 10 == 0:
            logger.info(f"  Procesados {i+1}/{len(videos)} videos...")

    logger.info(f"Comparando {len(hashed)} videos con frames válidos...")

    parent = list(range(len(hashed)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    best_ratios = {}

    for i in range(len(hashed)):
        hash_objs_i = [imagehash.hex_to_hash(h) for h in hashed[i].video_frame_hashes]

        for j in range(i + 1, len(hashed)):
            hash_objs_j = [imagehash.hex_to_hash(h) for h in hashed[j].video_frame_hashes]

            # Pre-filtro: duración similar (±5%)
            if hashed[i].duration_ms and hashed[j].duration_ms:
                d1, d2 = hashed[i].duration_ms, hashed[j].duration_ms
                if d1 > 0 and d2 > 0:
                    ratio = min(d1, d2) / max(d1, d2)
                    if ratio < 0.95:
                        continue

            matches = 0
            for hi in hash_objs_i:
                min_dist = min(hi - hj for hj in hash_objs_j)
                if min_dist <= image_threshold + VIDEO_FRAME_THRESHOLD_OFFSET:
                    matches += 1

            similarity = matches / max(len(hash_objs_i), len(hash_objs_j))

            if similarity >= threshold:
                union(i, j)
                best_ratios[(i, j)] = similarity
                best_ratios[(j, i)] = similarity

    groups = defaultdict(list)
    for i in range(len(hashed)):
        groups[find(i)].append(i)

    duplicates = []
    for group_indices in groups.values():
        if len(group_indices) > 1:
            group_files = [hashed[i] for i in group_indices]
            best = 0.0
            for i in group_indices:
                for j in group_indices:
                    if i != j:
                        r = best_ratios.get((i, j), 0.0)
                        if r > best:
                            best = r
            total_size = sum(f.size for f in group_files)
            max_size = max(f.size for f in group_files)
            duplicates.append(DuplicateGroup(
                group_type="video_similar",
                files=group_files,
                score=best,
                recoverable_size=total_size - max_size,
            ))

    logger.info(f"Encontrados {len(duplicates)} grupos de videos similares.")
    return duplicates


# ─── Duplicados exactos ───────────────────────────────────────────────────────

def find_exact_duplicates(items: list[MediaItem]) -> list[DuplicateGroup]:
    """Encuentra duplicados exactos usando SHA-256/MD5 + tamaño."""
    logger.info("Buscando duplicados exactos (SHA-256/MD5 + tamaño)...")
    groups = defaultdict(list)

    for item in items:
        key = item.hash_key
        if key[0] != "none":
            groups[key].append(item)

    duplicates = []
    for key, group_items in groups.items():
        if len(group_items) > 1:
            total_size = sum(f.size for f in group_items)
            max_size = max(f.size for f in group_items)
            duplicates.append(DuplicateGroup(
                group_type="exact",
                files=group_items,
                score=0.0,
                recoverable_size=total_size - max_size,
            ))

    logger.info(f"Encontrados {len(duplicates)} grupos de duplicados exactos.")
    return duplicates
