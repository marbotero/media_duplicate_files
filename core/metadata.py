#!/usr/bin/env python3
"""
core/metadata.py — Extracción de metadatos 100% real de imágenes y videos.

Motor principal: PyExifTool (wraps ExifTool de Phil Harvey).
  - Lee TODOS los metadatos: EXIF, IPTC, XMP, MakerNotes (Canon, Sony, Apple, Nikon, etc.)
  - Funciona con imágenes Y videos (MP4, MOV, MKV, AVI)
  - Soporta RAW (CR2, NEF, ARW, DNG)
  - GPS de fotos y videos
  - Campos de cámara que Pillow no puede leer

Fallback: si ExifTool no está instalado, usa Pillow (imágenes) + ffprobe (videos).

Toda la salida es JSON-serializable.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Extensiones soportadas
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif",
    ".webp", ".heic", ".heif", ".raw",
    # RAW de cámara
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2",
    ".pef", ".raf", ".srw",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv",
    ".3gp", ".webm", ".mpeg", ".mpg",
}

# Tags de ExifTool que nos interesan (para acceso rápido en la GUI)
# ExifTool usa nombres con dos puntos, ej: "EXIF:DateTimeOriginal"
# Grupos que NO son MakerNotes (grupos estándar de ExifTool)
_STANDARD_GROUPS = {
    "File", "EXIF", "JFIF", "Composite", "XMP", "IPTC", "ICC_Profile",
    "ExifTool", "QuickTime", "SourceFile", "General", "System",
    "IFD0", "IFD1", "IFD2", "ExifIFD", "GPS", "InteropIFD", "SubIFD",
    "Photoshop", "Adobe", "APP14", "MPF", "FLIR", "AFCP", "APP1",
    "Doc", "AIFF", "APE", "ASF", "BMP", "BPG", "DICOM", "DV", "EPS",
    "FLAC", "FLIF", "GIF", "H264", "ICO", "IND", "JPEG", "JSON",
    "M2TS", "M4A", "M4V", "MKV", "MNG", "MOI", "MOV", "MP3", "MP4",
    "MPC", "MPEG", "MRW", "OGG", "OGV", "Opus", "PCD", "PDF", "PICT",
    "PNG", "PPM", "PSD", "PSP", "QTIF", "RAF", "RAR", "RAW", "RM",
    "RIFF", "RSRC", "SWF", "TIFF", "Vorbis", "WAV", "WebM", "WebP",
    "WMF", "WTV", "X3F", "ZIP",
}

# Marcas conocidas cuyos MakerNotes usan su propio nombre de grupo
_MAKERNOTE_BRANDS = {
    "Canon", "Nikon", "Sony", "Apple", "Panasonic", "Olympus",
    "Fujifilm", "Pentax", "Leica", "Samsung", "Minolta", "Casio",
    "Ricoh", "Sigma", "GoPro", "DJI", "PhaseOne", "Hasselblad",
    "Mamiya", "Kodak", "Sanyo", "Sharp", "JVC", "Sanyo", "Casio",
    "Polaroid", "Yashica", "Contax", "Kyocera", "Rollei", "Apple",
    "Red", "Blackmagic", "Garmin", "TomTom",
}


def _is_makernote_tag(tag_name: str) -> bool:
    """Detecta si un tag pertenece a MakerNotes (datos secretos de marcas).

    ExifTool usa nombres de grupo especificos por marca (Canon:, Nikon:, Sony:)
    en lugar de un grupo generico 'MakerNotes:'. Esta funcion detecta ambos casos.
    """
    if not ":" in tag_name:
        return False
    group = tag_name.split(":", 1)[0]
    # Grupo generico 'MakerNotes'
    if group == "MakerNotes":
        return True
    # Grupos especificos de marca conocida
    if group in _MAKERNOTE_BRANDS:
        return True
    # Cualquier grupo que no sea estandar ni de marca conocida
    # podria ser MakerNotes de una marca menos comun
    if group not in _STANDARD_GROUPS:
        return True
    return False


KEY_TAGS = {
    # Básicos
    "File:FileName", "File:FileSize", "File:FileType",
    "File:FileTypeExtension", "File:MIMEType",
    "File:FileModifyDate", "File:FileCreateDate",
    # Dimensiones
    "File:ImageWidth", "File:ImageHeight",
    "EXIF:ExifImageWidth", "EXIF:ExifImageHeight",
    "EXIF:ImageWidth", "EXIF:ImageHeight",
    "QuickTime:ImageWidth", "QuickTime:ImageHeight",
    # Fecha de captura
    "EXIF:DateTimeOriginal", "EXIF:CreateDate", "EXIF:ModifyDate",
    "QuickTime:CreateDate", "QuickTime:ModifyDate",
    "XMP:CreateDate", "XMP:ModifyDate",
    # Cámara
    "EXIF:Make", "EXIF:Model", "EXIF:Software", "EXIF:OwnerName",
    "MakerNotes:CameraType", "MakerNotes:InternalSerialNumber",
    # Exposure
    "EXIF:ISO", "EXIF:FocalLength", "EXIF:FNumber", "EXIF:ExposureTime",
    "EXIF:ExposureMode", "EXIF:ExposureCompensation",
    "EXIF:ApertureValue", "EXIF:MaxApertureValue",
    "EXIF:ShutterSpeedValue", "EXIF:BrightnessValue",
    # GPS
    "EXIF:GPSLatitude", "EXIF:GPSLongitude",
    "EXIF:GPSLatitudeRef", "EXIF:GPSLongitudeRef",
    "EXIF:GPSAltitude", "EXIF:GPSDateTime",
    "Composite:GPSLatitude", "Composite:GPSLongitude",
    "Composite:GPSPosition",
    # Video específicos
    "QuickTime:Duration", "Track1:Duration", "Track0:Duration",
    "QuickTime:VideoCodec", "QuickTime:AudioCodec",
    "QuickTime:FrameRate", "QuickTime:AvgBitrate",
    # Orientación
    "EXIF:Orientation", "EXIF:ResolutionUnit",
    "EXIF:XResolution", "EXIF:YResolution",
    # Lente
    "EXIF:LensModel", "EXIF:LensMake", "EXIF:LensSerialNumber",
    "EXIF:FocalLengthIn35mmFormat",
    # Color
    "EXIF:ColorSpace", "EXIF:WhiteBalance",
    # Flash
    "EXIF:Flash", "EXIF:FlashEnergy",
}


def _exiftool_available() -> bool:
    """Verifica si exiftool está instalado en el sistema."""
    try:
        result = subprocess.run(
            ["exiftool", "-ver"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Verificar disponibilidad al importar
_HAS_EXIFTOOL = _exiftool_available()


def extract_metadata(file_path: str) -> dict:
    """
    Extrae TODOS los metadatos disponibles de un archivo.

    Usa PyExifTool (motor principal) si está disponible.
    Fallback a Pillow (imágenes) + ffprobe (videos) si no.

    Retorna un dict JSON-serializable.
    """
    file_path = str(file_path)
    if not os.path.exists(file_path):
        return {"file_type": "unknown", "error": "Archivo no encontrado"}

    ext = Path(file_path).suffix.lower()

    result = {
        "file_type": "unknown",
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "file_size": os.path.getsize(file_path),
        "modified_time": datetime.fromtimestamp(
            os.path.getmtime(file_path)
        ).isoformat(),
        "extraction_engine": "none",
    }

    if _HAS_EXIFTOOL:
        try:
            exif_data = _extract_with_exiftool(file_path)
            if exif_data:
                result.update(exif_data)
                result["extraction_engine"] = "exiftool"
                return result
        except Exception as e:
            result["extraction_engine"] = "fallback"
            result["exiftool_error"] = str(e)

    # Fallback: Pillow + ffprobe
    if ext in IMAGE_EXTENSIONS:
        img_meta = _extract_image_metadata_pillow(file_path)
        result.update(img_meta)
        result["extraction_engine"] = "pillow_fallback"
    elif ext in VIDEO_EXTENSIONS:
        vid_meta = _extract_video_metadata_ffprobe(file_path)
        result.update(vid_meta)
        result["extraction_engine"] = "ffprobe_fallback"
    else:
        result["file_type"] = "unknown"

    return result


# ─── PyExifTool (motor principal) ───────────────────────────────────────────

def _extract_with_exiftool(file_path: str) -> dict:
    """
    Extrae metadatos usando PyExifTool.
    Lee TODOS los tags disponibles, incluyendo MakerNotes.
    """
    try:
        import exiftool  # PyExifTool
    except ImportError:
        # Si PyExifTool no está instalado, usar exiftool directamente por CLI
        return _extract_with_exiftool_cli(file_path)

    result = {}

    with exiftool.ExifToolHelper() as et:
        # get_metadata devuelve una lista de dicts (uno por archivo)
        raw_list = et.get_metadata(file_path)

    if not raw_list:
        return {}

    raw = raw_list[0]  # Un solo archivo

    # Determinar tipo de archivo
    mime = raw.get("File:MIMEType", "")
    if mime.startswith("image/"):
        result["file_type"] = "image"
    elif mime.startswith("video/"):
        result["file_type"] = "video"
    elif mime.startswith("audio/"):
        result["file_type"] = "audio"
    else:
        result["file_type"] = "other"

    # Resolución
    width = raw.get("EXIF:ExifImageWidth") or raw.get("File:ImageWidth") or raw.get("QuickTime:ImageWidth")
    height = raw.get("EXIF:ExifImageHeight") or raw.get("File:ImageHeight") or raw.get("QuickTime:ImageHeight")
    if width and height:
        result["resolution"] = {"width": int(width), "height": int(height)}

    # Formato
    result["format"] = raw.get("File:FileType")
    result["mime_type"] = mime

    # Fecha de captura
    date_taken = (
        raw.get("EXIF:DateTimeOriginal")
        or raw.get("EXIF:CreateDate")
        or raw.get("QuickTime:CreateDate")
        or raw.get("XMP:CreateDate")
    )
    if date_taken:
        result["date_taken"] = str(date_taken)

    # Cámara
    make = raw.get("EXIF:Make")
    model = raw.get("EXIF:Model")
    if make:
        result["camera_make"] = str(make)
    if model:
        result["camera_model"] = str(model)

    # MakerNotes específicos (datos secretos de marcas)
    maker_notes = {}
    camera_type = raw.get("MakerNotes:CameraType")
    if camera_type:
        result["camera_type_makernote"] = str(camera_type)
        maker_notes["CameraType"] = str(camera_type)

    internal_serial = raw.get("MakerNotes:InternalSerialNumber")
    if internal_serial:
        maker_notes["InternalSerialNumber"] = str(internal_serial)

    # Software
    software = raw.get("EXIF:Software")
    if software:
        result["software"] = str(software)

    # Orientación
    orientation = raw.get("EXIF:Orientation")
    if orientation:
        result["orientation"] = str(orientation)

    # ISO, apertura, focal
    iso = raw.get("EXIF:ISO")
    if iso:
        result["iso"] = int(iso) if isinstance(iso, (int, float)) else str(iso)

    focal = raw.get("EXIF:FocalLength")
    if focal:
        result["focal_length"] = float(focal) if isinstance(focal, (int, float)) else str(focal)

    aperture = raw.get("EXIF:FNumber")
    if aperture:
        result["aperture"] = float(aperture) if isinstance(aperture, (int, float)) else str(aperture)

    exposure = raw.get("EXIF:ExposureTime")
    if exposure:
        result["exposure_time"] = str(exposure)

    # Lente
    lens_model = raw.get("EXIF:LensModel")
    if lens_model:
        result["lens_model"] = str(lens_model)

    focal_35 = raw.get("EXIF:FocalLengthIn35mmFormat")
    if focal_35:
        result["focal_length_35mm"] = str(focal_35)

    # GPS
    lat = raw.get("Composite:GPSLatitude") or raw.get("EXIF:GPSLatitude")
    lon = raw.get("Composite:GPSLongitude") or raw.get("EXIF:GPSLongitude")
    if lat is not None and lon is not None:
        result["gps"] = {
            "latitude": float(lat) if isinstance(lat, (int, float)) else str(lat),
            "longitude": float(lon) if isinstance(lon, (int, float)) else str(lon),
        }
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            result["gps"]["latitude_decimal"] = round(float(lat), 6)
            result["gps"]["longitude_decimal"] = round(float(lon), 6)
            result["gps"]["google_maps_url"] = f"https://maps.google.com/?q={lat},{lon}"

    gps_alt = raw.get("EXIF:GPSAltitude")
    if gps_alt:
        result["gps_altitude"] = str(gps_alt)

    # Video específicos
    duration = raw.get("QuickTime:Duration") or raw.get("Track1:Duration") or raw.get("Track0:Duration")
    if duration:
        try:
            result["duration_seconds"] = float(duration)
        except (ValueError, TypeError):
            result["duration_seconds"] = str(duration)

    fps = raw.get("QuickTime:FrameRate") or raw.get("Video:FrameRate")
    if fps:
        try:
            result["fps"] = float(fps)
        except (ValueError, TypeError):
            result["fps"] = str(fps)

    video_codec = raw.get("QuickTime:VideoCodec") or raw.get("Composite:VideoCodec")
    if video_codec:
        result["video_codec"] = str(video_codec)

    audio_codec = raw.get("QuickTime:AudioCodec")
    if audio_codec:
        result["audio_codec"] = str(audio_codec)

    bit_rate = raw.get("QuickTime:AvgBitrate") or raw.get("File:AvgBitrate")
    if bit_rate:
        try:
            result["bit_rate"] = int(bit_rate)
        except (ValueError, TypeError):
            result["bit_rate"] = str(bit_rate)

    # Flash
    flash = raw.get("EXIF:Flash")
    if flash:
        result["flash"] = str(flash)

    # Color
    color_space = raw.get("EXIF:ColorSpace")
    if color_space:
        result["color_space"] = str(color_space)

    white_balance = raw.get("EXIF:WhiteBalance")
    if white_balance:
        result["white_balance"] = str(white_balance)

    # Guardar TODOS los tags de ExifTool (raw completo)
    # Filtrar tags muy largos o binarios no útiles
    all_tags = {}
    for tag_name, tag_value in raw.items():
        # Saltar tags binarios enormes
        if isinstance(tag_value, (bytes, bytearray)):
            continue
        val_str = str(tag_value)
        if len(val_str) > 500:
            continue
        all_tags[tag_name] = val_str

    result["exiftool_all_tags"] = all_tags
    result["exiftool_tag_count"] = len(all_tags)

    # MakerNotes completos (datos secretos de marcas: Canon, Sony, Apple, Nikon, etc.)
    # ExifTool usa grupos por marca (Canon:, Nikon:, Sony:) ademas de MakerNotes:
    makernote_tags = {
        k: str(v) for k, v in raw.items()
        if _is_makernote_tag(k) and not isinstance(v, (bytes, bytearray))
        and len(str(v)) < 500
    }
    if makernote_tags:
        result["makernotes"] = makernote_tags
        maker_notes.update(makernote_tags)

    if maker_notes:
        result["makernotes_summary"] = maker_notes

    return result


def _extract_with_exiftool_cli(file_path: str) -> dict:
    """
    Fallback: usa exiftool por línea de comandos si PyExifTool no está instalado
    pero exiftool sí está disponible en el sistema.
    """
    result = {}

    cmd = [
        "exiftool",
        "-j",  # JSON output
        "-G",  # Incluir grupos (EXIF:, MakerNotes:, etc.)
        "-n",  # Valores numéricos donde sea posible
        "-charset", "utf8",
        file_path,
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            return {}

        data = json.loads(proc.stdout)
        if not data:
            return {}

        raw = data[0]
    except Exception:
        return {}

    # Determinar tipo
    mime = raw.get("File:MIMEType", "")
    if mime.startswith("image/"):
        result["file_type"] = "image"
    elif mime.startswith("video/"):
        result["file_type"] = "video"
    else:
        result["file_type"] = "other"

    result["mime_type"] = mime
    result["format"] = raw.get("File:FileType")

    # Resolución
    width = raw.get("EXIF:ExifImageWidth") or raw.get("File:ImageWidth")
    height = raw.get("EXIF:ExifImageHeight") or raw.get("File:ImageHeight")
    if width and height:
        result["resolution"] = {"width": int(width), "height": int(height)}

    # Fecha
    date_taken = raw.get("EXIF:DateTimeOriginal") or raw.get("EXIF:CreateDate")
    if date_taken:
        result["date_taken"] = str(date_taken)

    # Cámara
    if raw.get("EXIF:Make"):
        result["camera_make"] = str(raw["EXIF:Make"])
    if raw.get("EXIF:Model"):
        result["camera_model"] = str(raw["EXIF:Model"])

    # Software
    if raw.get("EXIF:Software"):
        result["software"] = str(raw["EXIF:Software"])

    # ISO, apertura, focal
    if raw.get("EXIF:ISO"):
        result["iso"] = str(raw["EXIF:ISO"])
    if raw.get("EXIF:FocalLength"):
        result["focal_length"] = str(raw["EXIF:FocalLength"])
    if raw.get("EXIF:FNumber"):
        result["aperture"] = str(raw["EXIF:FNumber"])
    if raw.get("EXIF:ExposureTime"):
        result["exposure_time"] = str(raw["EXIF:ExposureTime"])

    # GPS
    lat = raw.get("Composite:GPSLatitude") or raw.get("EXIF:GPSLatitude")
    lon = raw.get("Composite:GPSLongitude") or raw.get("EXIF:GPSLongitude")
    if lat is not None and lon is not None:
        result["gps"] = {
            "latitude_decimal": float(lat) if isinstance(lat, (int, float)) else str(lat),
            "longitude_decimal": float(lon) if isinstance(lon, (int, float)) else str(lon),
            "google_maps_url": f"https://maps.google.com/?q={lat},{lon}",
        }

    # Video
    duration = raw.get("QuickTime:Duration")
    if duration:
        result["duration_seconds"] = float(duration) if isinstance(duration, (int, float)) else str(duration)

    fps = raw.get("QuickTime:FrameRate")
    if fps:
        result["fps"] = float(fps) if isinstance(fps, (int, float)) else str(fps)

    # Guardar TODOS los tags
    all_tags = {}
    for k, v in raw.items():
        if isinstance(v, (bytes, bytearray)):
            continue
        val_str = str(v)
        if len(val_str) > 500:
            continue
        all_tags[k] = val_str

    result["exiftool_all_tags"] = all_tags
    result["exiftool_tag_count"] = len(all_tags)

    # MakerNotes (datos secretos de marcas: Canon, Nikon, Sony, Apple, etc.)
    makernote_tags = {
        k: str(v) for k, v in raw.items()
        if _is_makernote_tag(k) and not isinstance(v, (bytes, bytearray))
        and len(str(v)) < 500
    }
    if makernote_tags:
        result["makernotes"] = makernote_tags

    return result


# ─── Fallback: Pillow (imágenes) ─────────────────────────────────────────────

def _extract_image_metadata_pillow(file_path: str) -> dict:
    """Fallback: extrae metadatos de imagen usando Pillow."""
    result = {"file_type": "image"}

    try:
        from PIL import Image, ExifTags
        img = Image.open(file_path)

        result["resolution"] = {"width": img.width, "height": img.height}
        result["format"] = img.format or "desconocido"
        result["color_mode"] = img.mode or "desconocido"

        # EXIF básico
        exif_data = {}
        try:
            exif = img.getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")
                    exif_data[tag_name] = _normalize_exif_value(value)

                gps_info = _extract_gps_pillow(exif)
                if gps_info:
                    exif_data["GPS"] = gps_info
        except Exception:
            pass

        result["exif"] = exif_data

        # Campos clave
        result["date_taken"] = exif_data.get("DateTimeOriginal") or exif_data.get("DateTime")
        result["camera_make"] = exif_data.get("Make")
        result["camera_model"] = exif_data.get("Model")
        result["software"] = exif_data.get("Software")
        result["orientation"] = exif_data.get("Orientation")
        result["iso"] = exif_data.get("ISOSpeedRatings")
        result["focal_length"] = exif_data.get("FocalLength")
        result["aperture"] = exif_data.get("FNumber")
        result["exposure_time"] = exif_data.get("ExposureTime")
        result["gps"] = exif_data.get("GPS")

        img.close()
    except Exception as e:
        result["error"] = f"Error leyendo imagen: {e}"

    return result


def _extract_gps_pillow(exif) -> dict | None:
    """Fallback: extrae GPS del EXIF con Pillow."""
    try:
        from PIL.ExifTags import GPSTAGS
        gps_raw = exif.get_ifd(0x8825)
        if not gps_raw:
            return None

        gps_data = {}
        for tag_id, value in gps_raw.items():
            tag_name = GPSTAGS.get(tag_id, f"GPS_{tag_id}")
            gps_data[tag_name] = _normalize_exif_value(value)

        lat = _gps_to_decimal(gps_data.get("GPSLatitude"), gps_data.get("GPSLatitudeRef"))
        lon = _gps_to_decimal(gps_data.get("GPSLongitude"), gps_data.get("GPSLongitudeRef"))
        if lat is not None and lon is not None:
            gps_data["latitude_decimal"] = lat
            gps_data["longitude_decimal"] = lon
            gps_data["google_maps_url"] = f"https://maps.google.com/?q={lat},{lon}"

        return gps_data if gps_data else None
    except Exception:
        return None


def _gps_to_decimal(gps_value, ref) -> float | None:
    if not gps_value or not isinstance(gps_value, (list, tuple)):
        return None
    try:
        if len(gps_value) < 3:
            return None
        d, m, s = float(gps_value[0] or 0), float(gps_value[1] or 0), float(gps_value[2] or 0)
        decimal = d + m / 60 + s / 3600
        if ref and ref.upper() in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def _normalize_exif_value(value):
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        if value.denominator == 0:
            return None
        return float(value.numerator) / float(value.denominator)
    if isinstance(value, (list, tuple)):
        return [_normalize_exif_value(v) for v in value]
    if isinstance(value, bytes):
        try:
            return value.decode("ascii", errors="replace").strip("\x00")
        except Exception:
            return f"<bytes:{len(value)}>"
    if isinstance(value, str):
        return value.strip("\x00")
    if isinstance(value, (int, float)):
        return value
    return str(value)


# ─── Fallback: ffprobe (videos) ──────────────────────────────────────────────

def _extract_video_metadata_ffprobe(file_path: str) -> dict:
    """Fallback: extrae metadatos de video usando ffprobe."""
    result = {"file_type": "video"}

    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", file_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:
            result["error"] = "ffprobe no pudo leer el video"
            return result

        data = json.loads(proc.stdout)
        fmt = data.get("format", {})
        result["duration_seconds"] = float(fmt.get("duration", 0))
        result["bit_rate"] = int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None
        result["format_long_name"] = fmt.get("format_long_name")
        result["format_tags"] = fmt.get("tags", {})

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                result["video_codec"] = stream.get("codec_name")
                result["resolution"] = {
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                }
                result["fps"] = _parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
            elif stream.get("codec_type") == "audio":
                result["audio_codec"] = stream.get("codec_name")
                result["audio_channels"] = stream.get("channels")
                result["audio_sample_rate"] = stream.get("sample_rate")

        tags = fmt.get("tags", {})
        result["creation_time"] = tags.get("creation_time")

    except FileNotFoundError:
        result["error"] = "ffprobe no está instalado"
    except Exception as e:
        result["error"] = f"Error: {e}"

    return result


def _parse_fps(fps_str: str | None) -> float | None:
    if not fps_str:
        return None
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            den = float(den)
            return float(num) / den if den != 0 else None
        return float(fps_str)
    except Exception:
        return None
