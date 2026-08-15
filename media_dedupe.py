#!/usr/bin/env python3
"""
media_dedupe.py — Detector de duplicados y casi-duplicados multi-origen.

Soporta:
  - Google Drive (API v3, OAuth2)
  - Microsoft OneDrive (Microsoft Graph API, MSAL)
  - WhatsApp (carpeta local: Desktop, exportación, o teléfono montado por USB)

Detección:
  1. Duplicados exactos: SHA-256 + MD5 + tamaño
  2. Imágenes casi-duplicadas: perceptual hash (pHash) + distancia Hamming
  3. Videos casi-duplicados: extracción de frames con ffmpeg + pHash

Uso:
  python media_dedupe.py auth google-drive
  python media_dedupe.py auth onedrive
  python media_dedupe.py scan --source google-drive --source onedrive --whatsapp-folder /ruta/WhatsApp --report reporte

Autor: Generado por Perplexity Computer
"""

import argparse
import logging
import os
import sys
import tempfile
import time
from collections import defaultdict
from typing import List, Optional

# Asegurar que el directorio actual está en el path para imports relativos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.base import MediaItem, IMAGE_MIMES, VIDEO_MIMES
from providers.google_drive import GoogleDriveProvider
from providers.google_photos import GooglePhotosProvider
from providers.google_takeout import GoogleTakeoutProvider
from providers.local_folder import LocalFolderProvider
from providers.onedrive import OneDriveProvider
from providers.whatsapp_local import WhatsAppLocalProvider
from providers.router import ProviderRouter
from core.hashing import ensure_hashes
from core.similarity import (
    find_exact_duplicates, find_similar_images, find_similar_videos,
    DEFAULT_IMAGE_THRESHOLD, DEFAULT_VIDEO_THRESHOLD, VIDEO_NUM_FRAMES,
)
from core.cache import MediaCache
from core import reports

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("media_dedupe")

CACHE_DB = "media_cache.db"
CACHE_DIR = tempfile.mkdtemp(prefix="media_dedupe_")


# ─── Comandos ─────────────────────────────────────────────────────────────────

def cmd_auth(args):
    """Autentica con un provider específico."""
    if args.provider == "google-drive":
        client = GoogleDriveProvider(
            credentials_file=args.credentials,
            token_file="token_drive.json",
        )
        if client.authenticate():
            print("Google Drive: autenticación exitosa.")
        else:
            print("Google Drive: error de autenticación.")
            sys.exit(1)

    elif args.provider == "onedrive":
        client = OneDriveProvider(
            config_file=args.onedrive_config,
            token_cache="token_onedrive.json",
        )
        if client.authenticate():
            print("OneDrive: autenticación exitosa.")
        else:
            print("OneDrive: error de autenticación.")
            sys.exit(1)

    elif args.provider == "whatsapp":
        if not args.whatsapp_folder:
            print("ERROR: Especifica --whatsapp-folder para verificar la carpeta.")
            sys.exit(1)
        client = WhatsAppLocalProvider(base_folder=args.whatsapp_folder)
        if client.authenticate():
            print(f"WhatsApp Local: carpeta válida: {args.whatsapp_folder}")
        else:
            print(f"WhatsApp Local: la carpeta no existe: {args.whatsapp_folder}")
            sys.exit(1)

    elif args.provider == "google-photos":
        client = GooglePhotosProvider(
            credentials_file=args.credentials,
            token_file="token_photos.json",
            mode=args.photos_mode,
        )
        if client.authenticate():
            print(f"Google Photos: autenticación exitosa (modo: {args.photos_mode}).")
        else:
            print("Google Photos: error de autenticación.")
            print("  Asegúrate de habilitar 'Photos Library API' en Google Cloud Console.")
            print("  Reutiliza el mismo credentials.json de Google Drive.")
            sys.exit(1)

    elif args.provider == "google-photos-folder":
        if not args.google_photos_folder:
            print("ERROR: Especifica --google-photos-folder para verificar la carpeta.")
            sys.exit(1)
        client = WhatsAppLocalProvider(base_folder=args.google_photos_folder)
        if client.authenticate():
            print(f"Google Photos (Takeout): carpeta válida: {args.google_photos_folder}")
        else:
            print(f"Google Photos (Takeout): la carpeta no existe: {args.google_photos_folder}")
            sys.exit(1)

    elif args.provider == "google-takeout":
        if not args.google_takeout_folder:
            print("ERROR: Especifica --google-takeout-folder para verificar la carpeta.")
            sys.exit(1)
        client = GoogleTakeoutProvider(base_folder=args.google_takeout_folder)
        if client.authenticate():
            print(f"Google Takeout: carpeta válida: {args.google_takeout_folder}")
        else:
            print(f"Google Takeout: la carpeta no existe: {args.google_takeout_folder}")
            sys.exit(1)

    else:
        print(f"Provider desconocido: {args.provider}")
        sys.exit(1)


def cmd_scan(args):
    """Ejecuta el escaneo completo de duplicados en todos los orígenes configurados."""
    providers = []
    provider_names = []

    # Configurar Google Drive
    if "google-drive" in args.sources:
        gd = GoogleDriveProvider(
            credentials_file=args.credentials,
            token_file="token_drive.json",
        )
        providers.append(("google_drive", gd, args.drive_root))
        provider_names.append("Google Drive")

    # Configurar OneDrive
    if "onedrive" in args.sources:
        od = OneDriveProvider(
            config_file=args.onedrive_config,
            token_cache="token_onedrive.json",
        )
        providers.append(("onedrive", od, args.onedrive_root))
        provider_names.append("OneDrive")

    # Configurar WhatsApp Local
    if args.whatsapp_folder:
        wa = WhatsAppLocalProvider(base_folder=args.whatsapp_folder)
        providers.append(("whatsapp_local", wa, None))
        provider_names.append("WhatsApp (local)")

    # Configurar Google Photos (API)
    if "google-photos" in args.sources:
        gp = GooglePhotosProvider(
            credentials_file=args.credentials,
            token_file="token_photos.json",
            mode=args.photos_mode,
        )
        providers.append(("google_photos", gp, None))
        provider_names.append(f"Google Photos (modo: {args.photos_mode})")

    # Configurar Google Photos (carpeta local / Takeout solo de Photos)
    if args.google_photos_folder:
        gp_local = WhatsAppLocalProvider(base_folder=args.google_photos_folder)
        gp_local.name = "google_photos_takeout"
        providers.append(("google_photos_takeout", gp_local, None))
        provider_names.append("Google Photos (Takeout local)")

    # Configurar Google Takeout completo
    if args.google_takeout_folder:
        gt = GoogleTakeoutProvider(base_folder=args.google_takeout_folder)
        providers.append(("google_takeout", gt, None))
        provider_names.append("Google Takeout (completo)")

    # Configurar carpeta(s) local(es) arbitraria(s)
    if args.local_folder:
        for folder in args.local_folder:
            lf = LocalFolderProvider(base_folder=folder)
            providers.append(("local_folder", lf, None))
            provider_names.append(f"Carpeta local: {folder}")

    if not providers:
        print("ERROR: Especifica al menos un origen:")
        print("  --source google-drive")
        print("  --source onedrive")
        print("  --source google-photos")
        print("  --whatsapp-folder /ruta/a/WhatsApp")
        print("  --google-photos-folder /ruta/Takeout/Google Photos")
        print("  --google-takeout-folder /ruta/Takeout")
        print("  --local-folder /ruta/a/carpeta")
        sys.exit(1)

    print(f"\nOrígenes configurados: {', '.join(provider_names)}")
    print(f"Modo de hash: {args.hash_mode}")
    print()

    # Caché SQLite
    cache = MediaCache(args.cache_db or CACHE_DB)
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Fase 1: Listar archivos de cada provider
    all_items: List[MediaItem] = []

    for source_name, provider, root in providers:
        logger.info(f"── Listando archivos de {source_name} ──")
        try:
            items = provider.iter_media(root=root)
            all_items.extend(items)
        except Exception as e:
            logger.error(f"Error listando {source_name}: {e}")

    if not all_items:
        print("\nNo se encontraron archivos multimedia en ningún origen.")
        cache.close()
        return

    # Resumen
    by_source = defaultdict(int)
    for item in all_items:
        by_source[item.source] += 1
    num_images = sum(1 for f in all_items if f.is_image)
    num_videos = sum(1 for f in all_items if f.is_video)
    total_size = sum(f.size for f in all_items)

    print(f"\n{'='*60}")
    print("RESUMEN DE ARCHIVOS ENCONTRADOS")
    print(f"{'='*60}")
    for source, count in by_source.items():
        print(f"  {source}: {count} archivos")
    print(f"  Total: {len(all_items)} archivos ({num_images} imágenes, {num_videos} videos)")
    print(f"  Tamaño total: {reports.format_size(total_size)}")
    print()

    # Crear mapa de providers con aliases para despacho correcto
    provider_map = {}
    for name, provider, _ in providers:
        provider_map[name] = provider
        provider_map[provider.name] = provider
        for alias in getattr(provider, "source_aliases", []):
            provider_map[alias] = provider

    # Fase 2: Calcular hashes (SHA-256 + MD5)
    if args.hash_mode == "full":
        logger.info("── Calculando hashes (MD5 + SHA-256) ──")
        for i, item in enumerate(all_items):
            # Comprobar caché primero
            cached = cache.get(item.source, item.item_id, item.size, item.modified_time)
            if cached:
                if cached.get("md5"):
                    item.md5 = cached["md5"]
                if cached.get("sha256"):
                    item.sha256 = cached["sha256"]
                if cached.get("phash"):
                    item.phash = cached["phash"]
                if cached.get("video_frame_hashes"):
                    item.video_frame_hashes = cached["video_frame_hashes"]

            # Si faltan hashes, calcularlos
            if not item.md5 or not item.sha256:
                # Encontrar el provider correspondiente (usando aliases)
                provider = provider_map.get(item.source)
                if provider:
                    ensure_hashes(item, provider, CACHE_DIR)
                    # Guardar en caché
                    cache.put(
                        item.source, item.item_id, item.size, item.modified_time,
                        md5=item.md5, sha256=item.sha256,
                    )

            if (i + 1) % 50 == 0:
                logger.info(f"  Hashes calculados: {i+1}/{len(all_items)}")

    elif args.hash_mode == "metadata":
        logger.info("Modo metadata: usando hashes disponibles de la API (sin descargar).")
        # Los hashes ya están en los items si el provider los proporcionó

    # Fase 3: Detectar duplicados
    logger.info("── Detectando duplicados ──")

    # 3a. Duplicados exactos
    exact = find_exact_duplicates(all_items)

    # Excluir exactos del análisis perceptual, pero mantener un representante
    exact_ids = set()
    exact_representatives = set()
    for g in exact:
        group_ids = {(f.source, f.item_id) for f in g.files}
        rep = list(group_ids)[0]
        exact_representatives.add(rep)
        exact_ids.update(group_ids)

    remaining = [f for f in all_items if (f.source, f.item_id) not in exact_ids]
    remaining += [f for f in all_items if (f.source, f.item_id) in exact_representatives]

    all_groups = list(exact)

    # 3b. Casi-duplicados (comparando entre todos los orígenes)
    if not args.skip_similar:
        # Reutilizar el provider_map con aliases ya construido
        router = ProviderRouter(provider_map)

        img_similar = find_similar_images(
            remaining, router, CACHE_DIR, args.image_threshold
        )
        all_groups.extend(img_similar)

        vid_similar = find_similar_videos(
            remaining, router, CACHE_DIR,
            args.video_threshold, args.image_threshold, args.video_frames
        )
        all_groups.extend(vid_similar)

    cache.close()

    # Fase 4: Generar reportes
    if not all_groups:
        print("\nNo se encontraron duplicados ni archivos similares.")
        return

    base_path = args.report
    reports.to_json(all_groups, f"{base_path}.json")
    reports.to_csv(all_groups, f"{base_path}.csv")
    reports.to_html(all_groups, f"{base_path}.html")

    # Resumen final
    print(f"\n{'='*60}")
    print("RESULTADOS DEL ESCANEO")
    print(f"{'='*60}")
    print(f"Archivos analizados: {len(all_items)}")
    print(f"Grupos de duplicados: {len(all_groups)}")

    by_type = defaultdict(int)
    recoverable = 0
    for g in all_groups:
        by_type[g.group_type] += 1
        recoverable += g.recoverable_size

    labels = {
        "exact": "Duplicados exactos",
        "image_similar": "Imágenes similares",
        "video_similar": "Videos similares",
    }
    for gtype, count in by_type.items():
        print(f"  {labels.get(gtype, gtype)}: {count} grupos")

    print(f"\nEspacio recuperable estimado: {reports.format_size(recoverable)}")
    print(f"\nReportes generados:")
    print(f"  - {base_path}.json")
    print(f"  - {base_path}.csv")
    print(f"  - {base_path}.html")
    print(f"{'='*60}")
    print("\nNOTA: El programa NO borra nada. Revisa los reportes y decide manualmente.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Detector de duplicados y casi-duplicados multi-origen "
                    "(Google Drive, OneDrive, Google Photos, WhatsApp).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  1. Autenticar (primera vez):
     python media_dedupe.py auth google-drive
     python media_dedupe.py auth onedrive
     python media_dedupe.py auth google-photos --photos-mode app-created
     python media_dedupe.py auth google-photos --photos-mode picker

  2. Verificar carpeta local:
     python media_dedupe.py auth whatsapp --whatsapp-folder /ruta/WhatsApp/Media
     python media_dedupe.py auth google-takeout --google-takeout-folder /ruta/Takeout

  3. Escanear todo:
     python media_dedupe.py scan --source google-drive --source onedrive \\
       --source google-photos --whatsapp-folder /ruta/WhatsApp \\
       --google-takeout-folder /ruta/Takeout --report reporte

  4. Solo Google Takeout (biblioteca completa de Google):
     python media_dedupe.py scan --google-takeout-folder /ruta/Takeout --report reporte

  5. Solo Google Photos (API):
     python media_dedupe.py scan --source google-photos --photos-mode app-created --report reporte
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Subcomando: auth
    auth_parser = subparsers.add_parser("auth", help="Autentica con un provider")
    auth_parser.add_argument("provider", choices=["google-drive", "onedrive", "whatsapp", "google-photos", "google-photos-folder", "google-takeout"],
                              help="Provider a autenticar")
    auth_parser.add_argument("--credentials", default="credentials.json",
                              help="Ruta a credentials.json de Google (OAuth)")
    auth_parser.add_argument("--onedrive-config", default="onedrive_config.json",
                              help="Ruta a onedrive_config.json con client_id")
    auth_parser.add_argument("--whatsapp-folder", default=None,
                              help="Ruta de la carpeta de WhatsApp (para verificar)")
    auth_parser.add_argument("--google-photos-folder", default=None,
                              help="Ruta de la carpeta de Google Photos Takeout (para verificar)")
    auth_parser.add_argument("--google-takeout-folder", default=None,
                              help="Ruta de la carpeta de Google Takeout completa (para verificar)")
    auth_parser.add_argument("--photos-mode", choices=["app-created", "picker"], default="app-created",
                              help="Modo de Google Photos API: 'app-created' (solo medios de la app) o 'picker' (selección manual)")

    # Subcomando: scan
    scan_parser = subparsers.add_parser("scan", help="Ejecuta el escaneo de duplicados")
    scan_parser.add_argument("--source", action="append", dest="sources",
                              choices=["google-drive", "onedrive", "google-photos"], default=[],
                              help="Orígenes cloud a escanear (repetir para múltiples)")
    scan_parser.add_argument("--whatsapp-folder", default=None,
                              help="Carpeta local de WhatsApp Media")
    scan_parser.add_argument("--google-photos-folder", default=None,
                              help="Carpeta local de Google Photos (exportación Takeout, solo Photos)")
    scan_parser.add_argument("--google-takeout-folder", default=None,
                              help="Carpeta de Google Takeout completa (todos los productos de Google)")
    scan_parser.add_argument("--local-folder", action="append", default=[],
                              help="Carpeta local arbitraria a escanear (repetir para múltiples)")
    scan_parser.add_argument("--photos-mode", choices=["app-created", "picker"], default="app-created",
                              help="Modo de Google Photos API: 'app-created' o 'picker'")
    scan_parser.add_argument("--drive-root", default=None,
                              help="ID de carpeta raíz en Google Drive (opcional)")
    scan_parser.add_argument("--onedrive-root", default=None,
                              help="ID de carpeta raíz en OneDrive (opcional)")
    scan_parser.add_argument("--credentials", default="credentials.json",
                              help="Ruta a credentials.json de Google (OAuth)")
    scan_parser.add_argument("--onedrive-config", default="onedrive_config.json",
                              help="Ruta a onedrive_config.json con client_id")
    scan_parser.add_argument("--hash-mode", choices=["metadata", "full"], default="full",
                              help="metadata: solo hashes de la API (rápido). full: descargar y calcular MD5+SHA-256 (preciso). Default: full")
    scan_parser.add_argument("--image-threshold", type=int, default=DEFAULT_IMAGE_THRESHOLD,
                              help=f"Distancia Hamming máxima para imágenes similares (default: {DEFAULT_IMAGE_THRESHOLD})")
    scan_parser.add_argument("--video-threshold", type=float, default=DEFAULT_VIDEO_THRESHOLD,
                              help=f"Ratio mínimo de similitud para videos (default: {DEFAULT_VIDEO_THRESHOLD})")
    scan_parser.add_argument("--video-frames", type=int, default=VIDEO_NUM_FRAMES,
                              help=f"Número de frames a extraer por video (default: {VIDEO_NUM_FRAMES})")
    scan_parser.add_argument("--skip-similar", action="store_true",
                              help="Saltar detección de casi-duplicados (solo exactos)")
    scan_parser.add_argument("--cache-db", default=None,
                              help="Ruta de la base de datos de caché (default: media_cache.db)")
    scan_parser.add_argument("--report", default="reporte_duplicados",
                              help="Nombre base del reporte (sin extensión)")

    args = parser.parse_args()

    if args.command == "auth":
        cmd_auth(args)
    elif args.command == "scan":
        cmd_scan(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
