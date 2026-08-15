"""
reports.py — Generación de reportes en CSV, JSON y HTML.
"""

from __future__ import annotations

import csv
import html
import json
import logging
import time
from typing import List

from core.similarity import DuplicateGroup

logger = logging.getLogger("media_dedupe")


def format_size(size: int) -> str:
    if size >= 1024**3:
        return f"{size/1024**3:.2f} GB"
    elif size >= 1024**2:
        return f"{size/1024**2:.2f} MB"
    elif size >= 1024:
        return f"{size/1024:.2f} KB"
    return f"{size} B"


def to_json(groups: List[DuplicateGroup], output_path: str):
    """Genera un reporte JSON."""
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_groups": len(groups),
        "total_recoverable_size": sum(g.recoverable_size for g in groups),
        "groups": [g.to_dict() for g in groups],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Reporte JSON: {output_path}")


def to_csv(groups: List[DuplicateGroup], output_path: str):
    """Genera un reporte CSV."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "grupo_tipo", "score", "origen", "archivo_nombre", "mime_type",
            "tamaño_bytes", "md5", "sha256", "item_id", "ruta_o_link",
            "tamaño_recuperable_grupo",
        ])
        for group in groups:
            for item in group.files:
                writer.writerow([
                    group.group_type,
                    group.score,
                    item.source,
                    item.name,
                    item.mime_type,
                    item.size,
                    item.md5 or "",
                    item.sha256 or "",
                    item.item_id,
                    item.path or item.web_url or "",
                    group.recoverable_size,
                ])
    logger.info(f"Reporte CSV: {output_path}")


def to_html(groups: List[DuplicateGroup], output_path: str):
    """Genera un reporte HTML interactivo."""
    total_recoverable = sum(g.recoverable_size for g in groups)

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='es'><head><meta charset='UTF-8'>",
        "<title>Reporte de Duplicados — Multi-origen</title>",
        "<style>",
        "  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
        "         margin: 0; padding: 20px; background: #f5f5f5; color: #333; }",
        "  h1 { color: #1a73e8; }",
        "  .summary { background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; "
        "             box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        "  .group { background: #fff; margin-bottom: 16px; border-radius: 8px; "
        "           box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }",
        "  .group-header { padding: 12px 20px; font-weight: 600; color: #fff; }",
        "  .group.exact .group-header { background: #d93025; }",
        "  .group.image_similar .group-header { background: #f9ab00; }",
        "  .group.video_similar .group-header { background: #1e8e3e; }",
        "  table { width: 100%; border-collapse: collapse; }",
        "  th, td { padding: 10px 20px; text-align: left; border-bottom: 1px solid #eee; }",
        "  th { background: #f9f9f9; font-size: 13px; text-transform: uppercase; color: #666; }",
        "  td { font-size: 14px; }",
        "  a { color: #1a73e8; text-decoration: none; }",
        "  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; "
        "           font-size: 12px; font-weight: 600; }",
        "  .badge.exact { background: #fce8e6; color: #d93025; }",
        "  .badge.image_similar { background: #fef7e0; color: #f9ab00; }",
        "  .badge.video_similar { background: #e6f4ea; color: #1e8e3e; }",
        "  .source { font-size: 11px; color: #999; }",
        "</style></head><body>",
        "<h1>Reporte de Duplicados — Multi-origen</h1>",
        "<div class='summary'>",
        f"<p><strong>Fecha:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>",
        f"<p><strong>Grupos encontrados:</strong> {len(groups)}</p>",
        f"<p><strong>Espacio recuperable estimado:</strong> {format_size(total_recoverable)}</p>",
        "</div>",
    ]

    type_labels = {
        "exact": "Duplicado Exacto",
        "image_similar": "Imágenes Similares",
        "video_similar": "Videos Similares",
    }

    source_labels = {
        "google_drive": "Google Drive",
        "onedrive": "OneDrive",
        "whatsapp_local": "WhatsApp",
        "google_photos": "Google Photos",
        "google_photos_takeout": "Google Photos (Takeout)",
        "google_drive_takeout": "Google Drive (Takeout)",
        "youtube_takeout": "YouTube (Takeout)",
        "google_chat_takeout": "Google Chat (Takeout)",
        "hangouts_takeout": "Hangouts (Takeout)",
        "google_keep_takeout": "Google Keep (Takeout)",
        "blogger_takeout": "Blogger (Takeout)",
        "google_plus_takeout": "Google+ (Takeout)",
        "google_picasa_takeout": "Picasa (Takeout)",
        "google_takeout_other": "Google Takeout (otros)",
        "google_takeout": "Google Takeout",
        "local_folder": "Carpeta local",
    }

    for idx, group in enumerate(groups, 1):
        cls = group.group_type
        label = type_labels.get(cls, cls)
        score_label = "Distancia" if cls != "video_similar" else "Ratio similitud"
        score_str = f"{group.score:.2f}" if cls == "video_similar" else f"{group.score:.0f}"

        html_parts.append(f"<div class='group {cls}'>")
        html_parts.append(
            f"<div class='group-header'>"
            f"Grupo #{idx} — {label} | "
            f"{score_label}: {score_str} | "
            f"Recuperable: {format_size(group.recoverable_size)} | "
            f"{len(group.files)} archivos"
            f"</div>"
        )
        html_parts.append("<table><thead><tr>")
        html_parts.append("<th>Archivo</th><th>Origen</th><th>Tipo</th><th>Tamaño</th><th>MD5</th><th>SHA-256</th><th>Enlace</th>")
        html_parts.append("</tr></thead><tbody>")

        for item in group.files:
            md5_short = (item.md5[:16] + "...") if item.md5 else "—"
            sha_short = (item.sha256[:16] + "...") if item.sha256 else "—"
            safe_name = html.escape(item.name)
            safe_mime = html.escape(item.mime_type)
            source_label = source_labels.get(item.source, item.source)

            if item.web_url:
                link_html = f"<a href='{html.escape(item.web_url, quote=True)}' target='_blank'>Abrir</a>"
            elif item.path:
                link_html = f"<code>{html.escape(item.path[:60])}</code>"
            else:
                link_html = "—"

            html_parts.append(
                f"<tr>"
                f"<td>{safe_name}</td>"
                f"<td><span class='source'>{html.escape(source_label)}</span></td>"
                f"<td><span class='badge {cls}'>{safe_mime}</span></td>"
                f"<td>{format_size(item.size)}</td>"
                f"<td><code>{html.escape(md5_short)}</code></td>"
                f"<td><code>{html.escape(sha_short)}</code></td>"
                f"<td>{link_html}</td>"
                f"</tr>"
            )

        html_parts.append("</tbody></table></div>")

    html_parts.append("</body></html>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))
    logger.info(f"Reporte HTML: {output_path}")
