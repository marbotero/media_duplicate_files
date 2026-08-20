#!/usr/bin/env python3
"""
media_dedupe_gui_advance.py — Interfaz gráfica avanzada para Media Dedupe.

Interfaz modular y profesional para visualizar y gestionar grupos de duplicados.

Componentes principales:
  - PanelVistaPrevia: Muestra miniaturas y metadatos del grupo seleccionado
  - PanelResultados: Tabla dinámica de grupos con checkboxes
  - PanelControl: Filtros y acciones masivas
  - VentanaDetalles: Detalles completos de un archivo

Uso:
  python media_dedupe_gui_advance.py --json reporte.json
"""

import json
import hashlib
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageTk

from config.paths import (
    MEDIA_DEDUPE_PY, REPORTE_JSON, REPORTES_QUARANTINE, SECRETOS_ACCOUNTS,
    rutas_perfil_google, rutas_perfil_onedrive,
)


class GestorPerfiles:
    """Gestiona perfiles locales sin mostrar ni registrar sus secretos."""

    ARCHIVOS = {
        "google": ("google-drive.json", "google-drive-token.json", "google-photos-token.json"),
        "onedrive": ("onedrive-config.json", "onedrive-token.json"),
    }

    def __init__(self):
        self.raiz = Path(SECRETOS_ACCOUNTS)
        self.raiz.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slug(nombre):
        limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in nombre.strip())
        return limpio.strip("._") or "cuenta"

    @classmethod
    def perfil_desde_correo(cls, correo):
        """Usa la parte anterior a @ como nombre estable del perfil."""
        local = correo.strip().split("@", 1)[0]
        return cls.slug(local)

    def perfiles(self, proveedor):
        carpeta = self.raiz / proveedor
        if not carpeta.exists():
            return []
        return sorted(p.name for p in carpeta.iterdir() if p.is_dir())

    def carpeta(self, proveedor, perfil):
        ruta = self.raiz / proveedor / self.slug(perfil)
        ruta.mkdir(parents=True, exist_ok=True)
        return ruta

    def importar(self, proveedor, perfil, origen, destino):
        ruta = self.carpeta(proveedor, perfil) / destino
        shutil.copy2(origen, ruta)
        return ruta

    def activar(self, proveedor, perfil):
        carpeta = self.carpeta(proveedor, perfil)
        return carpeta


class GestorCuarentena:
    """Mueve archivos locales a una sesión reversible de cuarentena."""

    def __init__(self):
        self.raiz = Path(REPORTES_QUARANTINE)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def mover(self, archivos: List[dict]) -> tuple[int, list[str], Path | None]:
        session = self.raiz / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        suffix = 1
        while session.exists():
            session = self.raiz / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}-{suffix:02d}"
            suffix += 1
        destino = session / "files"
        moved = []
        errors = []
        for archivo in archivos:
            original = Path(archivo.get("path", ""))
            if not original.is_file():
                errors.append(f"No existe: {original}")
                continue
            target = destino / original.name
            target.parent.mkdir(parents=True, exist_ok=True)
            counter = 1
            while target.exists():
                target = destino / f"{original.stem}_{counter}{original.suffix}"
                counter += 1
            try:
                shutil.move(str(original), str(target))
                moved.append({
                    "original": str(original),
                    "quarantine": str(target),
                    "sha256": self._sha256(target),
                })
            except OSError as error:
                errors.append(f"{original}: {error}")
        if not moved:
            return 0, errors, None
        session.mkdir(parents=True, exist_ok=True)
        (session / "manifest.json").write_text(
            json.dumps({"created_at": datetime.now().isoformat(), "files": moved}, indent=2),
            encoding="utf-8",
        )
        return len(moved), errors, session

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
                digest.update(bloque)
        return digest.hexdigest()

    def sesiones(self) -> list[Path]:
        return sorted((path for path in self.raiz.iterdir() if path.is_dir()), reverse=True)

    def archivos_sesion(self, session_name: str) -> list[dict]:
        manifest_path = self.raiz / session_name / "manifest.json"
        if not manifest_path.exists():
            return []
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("files", [])

    def restaurar_ultima(self) -> tuple[int, list[str]]:
        sessions = self.sesiones()
        if not sessions:
            return 0, ["No hay sesiones de cuarentena."]
        return self.restaurar(sessions[0].name)

    def restaurar(self, session_name: str, indices: list[int] | None = None) -> tuple[int, list[str]]:
        session = self.raiz / session_name
        manifest_path = session / "manifest.json"
        if not manifest_path.exists():
            return 0, ["La sesión no tiene manifiesto."]
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        restored = 0
        errors = []
        items = data.get("files", [])
        selected = set(indices) if indices is not None else set(range(len(items)))
        for index, item in enumerate(items):
            if index not in selected:
                continue
            source = Path(item["quarantine"])
            target = Path(item["original"])
            if not source.exists():
                errors.append(f"No existe en cuarentena: {source}")
                continue
            if target.exists():
                errors.append(f"La ruta original está ocupada: {target}")
                continue
            try:
                expected_hash = item.get("sha256")
                if expected_hash and self._sha256(source) != expected_hash:
                    errors.append(f"Hash no coincide: {source}")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                restored += 1
            except OSError as error:
                errors.append(f"{target}: {error}")
        remaining = [item for index, item in enumerate(items) if index not in selected]
        if restored:
            data["files"] = remaining + [
                item for index, item in enumerate(items)
                if index in selected and Path(item["quarantine"]).exists()
            ]
            manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return restored, errors

    def eliminar_sesion(self, session_name: str) -> None:
        session = self.raiz / session_name
        if session.exists() and session.parent == self.raiz:
            shutil.rmtree(session)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE ESTILOS
# ─────────────────────────────────────────────────────────────────────────────

COLORES = {
    "fondo": "#f5f5f5",
    "tarjeta": "#ffffff",
    "acento": "#1a73e8",
    "acento_hover": "#1557b0",
    "peligro": "#d93025",
    "exito": "#1e8e3e",
    "advertencia": "#f9ab00",
    "texto": "#333333",
    "texto_muted": "#666666",
    "borde": "#dadce0",
    "exact": "#fce8e6",
    "image_similar": "#fef7e0",
    "video_similar": "#e6f4ea",
}

TIPOGRAFIA = {
    "título": ("Segoe UI", 16, "bold"),
    "subtítulo": ("Segoe UI", 12, "bold"),
    "normal": ("Segoe UI", 10),
    "pequeño": ("Segoe UI", 8),
    "mono": ("Consolas", 9),
}


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def formato_tamaño(bytes_: int) -> str:
    """Convierte bytes a formato legible."""
    for unidad in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unidad}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def cargar_imagen_miniatura(ruta: str, tamaño: Tuple[int, int] = (150, 150)) -> Optional[ImageTk.PhotoImage]:
    """Carga una imagen local como miniatura."""
    try:
        if not os.path.exists(ruta):
            return None
        img = Image.open(ruta)
        img.thumbnail(tamaño, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Error cargando miniatura {ruta}: {e}")
        return None


def extraer_metadatos(item_dict: dict) -> str:
    """Extrae y formatea metadatos de un archivo."""
    líneas = []
    
    # Resolución (si es imagen/video)
    if item_dict.get("width") and item_dict.get("height"):
        líneas.append(f"📐 {item_dict['width']}×{item_dict['height']}px")
    
    # Duración (si es video)
    if item_dict.get("duration_ms"):
        seg = item_dict["duration_ms"] / 1000
        líneas.append(f"⏱️  {int(seg//60)}:{int(seg%60):02d}")
    
    # Tamaño
    tamaño = formato_tamaño(item_dict.get("size", 0))
    líneas.append(f"💾 {tamaño}")
    
    # Fecha modificación
    if item_dict.get("modified_time"):
        líneas.append(f"📅 {item_dict['modified_time'][:10]}")
    
    # Metadatos EXIF (si existen)
    extra = item_dict.get("extra", {})
    if isinstance(extra, dict):
        metadata = extra.get("metadata", {})
        if isinstance(metadata, dict):
            cámara = metadata.get("camera_model")
            if cámara:
                líneas.append(f"📷 {cámara}")
    
    # Origen
    source_labels = {
        "google_drive": "☁️ Google Drive",
        "onedrive": "☁️ OneDrive",
        "whatsapp_local": "💬 WhatsApp",
        "local_folder": "💻 Carpeta Local",
    }
    origen = source_labels.get(item_dict.get("source"), item_dict.get("source", ""))
    if origen:
        líneas.append(origen)
    
    return "\n".join(líneas)


# ─────────────────────────────────────────────────────────────────────────────
# PANEL: VISTA PREVIA Y DETALLES
# ─────────────────────────────────────────────────────────────────────────────

class PanelVistaPrevia(tk.Frame):
    """Panel superior que muestra miniaturas y detalles del grupo seleccionado."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORES["fondo"], **kwargs)
        
        self.grupo_actual = None
        self._foto_refs = {}  # Evitar garbage collection de imágenes
        
        self._construir_ui()
    
    def _construir_ui(self):
        """Construye la interfaz del panel."""
        # Encabezado
        encabezado = tk.Frame(self, bg=COLORES["tarjeta"], height=50)
        encabezado.pack(fill="x", padx=8, pady=8)
        encabezado.pack_propagate(False)
        
        tk.Label(
            encabezado,
            text="📋 Detalles del Grupo",
            font=TIPOGRAFIA["subtítulo"],
            bg=COLORES["tarjeta"],
            fg=COLORES["acento"],
        ).pack(side="left", padx=12, pady=12)
        
        # Contenedor de miniaturas (scroll horizontal)
        contenedor = tk.Frame(self, bg=COLORES["fondo"])
        contenedor.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Canvas con scrollbar horizontal
        self.canvas = tk.Canvas(
            contenedor,
            bg=COLORES["tarjeta"],
            highlightthickness=1,
            highlightbackground=COLORES["borde"],
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(contenedor, orient="horizontal", command=self.canvas.xview)
        scrollbar.pack(side="bottom", fill="x")
        self.canvas.configure(xscrollcommand=scrollbar.set)
        
        # Frame dentro del canvas
        self.frame_miniaturas = tk.Frame(self.canvas, bg=COLORES["tarjeta"])
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.frame_miniaturas,
            anchor="nw",
        )
        
        # Actualizar región scroll al cambiar tamaño
        self.frame_miniaturas.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
    
    def mostrar_grupo(self, grupo_dict: dict, índice_grupo: int):
        """Muestra las miniaturas y detalles de un grupo de duplicados."""
        self.grupo_actual = grupo_dict
        
        # Limpiar miniaturas anteriores
        for widget in self.frame_miniaturas.winfo_children():
            widget.destroy()
        self._foto_refs.clear()
        
        archivos = grupo_dict.get("files", [])
        
        # Ordenar: primero el archivo con mayor resolución
        archivos_ordenados = sorted(
            archivos,
            key=lambda f: (f.get("width", 0) or 0) * (f.get("height", 0) or 0),
            reverse=True,
        )
        
        # Crear tarjeta para cada archivo
        for posición, archivo in enumerate(archivos_ordenados):
            tarjeta = self._crear_tarjeta_archivo(archivo, posición)
            tarjeta.pack(side="left", padx=8, pady=12)
    
    def _crear_tarjeta_archivo(self, archivo: dict, posición: int) -> tk.Frame:
        """Crea una tarjeta visual para un archivo."""
        tarjeta = tk.Frame(
            self.frame_miniaturas,
            bg=COLORES["tarjeta"],
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORES["borde"],
        )
        
        # Miniatura
        frame_img = tk.Frame(tarjeta, bg=COLORES["fondo"], width=150, height=150)
        frame_img.pack(padx=8, pady=(8, 4))
        frame_img.pack_propagate(False)
        
        ruta_local = archivo.get("path")
        if ruta_local and os.path.exists(ruta_local):
            foto = cargar_imagen_miniatura(ruta_local, (150, 150))
            if foto:
                self._foto_refs[posición] = foto
                tk.Label(frame_img, image=foto, bg=COLORES["fondo"]).pack()
        else:
            # Placeholder si no es archivo local
            tk.Label(
                frame_img,
                text="📄",
                font=("Segoe UI", 48),
                bg=COLORES["fondo"],
                fg=COLORES["texto_muted"],
            ).pack()
        
        # Nombre de archivo (truncado)
        nombre = archivo.get("name", "sin nombre")
        nombre_corto = nombre[:20] + "..." if len(nombre) > 20 else nombre
        tk.Label(
            tarjeta,
            text=nombre_corto,
            font=TIPOGRAFIA["pequeño"],
            bg=COLORES["tarjeta"],
            fg=COLORES["texto"],
            wraplength=150,
            justify="center",
        ).pack(padx=8, pady=2)
        
        # Metadatos
        metadatos_texto = extraer_metadatos(archivo)
        tk.Label(
            tarjeta,
            text=metadatos_texto,
            font=TIPOGRAFIA["pequeño"],
            bg=COLORES["tarjeta"],
            fg=COLORES["texto_muted"],
            justify="left",
        ).pack(padx=8, pady=(4, 8), anchor="w")
        
        # Badge: "Mejor" para el primero
        if posición == 0:
            tk.Label(
                tarjeta,
                text="⭐ MEJOR",
                font=("Segoe UI", 8, "bold"),
                bg=COLORES["exito"],
                fg="white",
            ).pack(fill="x", padx=8, pady=(0, 8))
        
        return tarjeta


# ─────────────────────────────────────────────────────────────────────────────
# PANEL: TABLA DINÁMICA DE RESULTADOS
# ─────────────────────────────────────────────────────────────────────────────

class PanelResultados(tk.Frame):
    """Panel central con tabla dinámica de grupos."""
    
    def __init__(self, parent, callback_fila_seleccionada=None, **kwargs):
        super().__init__(parent, bg=COLORES["fondo"], **kwargs)
        
        self.datos_grupos = []
        self.checkbox_estados = {}  # {(grupo_idx, archivo_idx): BooleanVar}
        self.callback_fila = callback_fila_seleccionada
        self._foto_refs = {}  # Evitar garbage collection
        
        self._construir_ui()
    
    def _construir_ui(self):
        """Construye la interfaz de la tabla."""
        # Encabezado
        encabezado = tk.Frame(self, bg=COLORES["tarjeta"], height=50)
        encabezado.pack(fill="x", padx=8, pady=8)
        encabezado.pack_propagate(False)
        
        tk.Label(
            encabezado,
            text="📊 Grupos de Duplicados",
            font=TIPOGRAFIA["subtítulo"],
            bg=COLORES["tarjeta"],
            fg=COLORES["acento"],
        ).pack(side="left", padx=12, pady=12)
        
        # Canvas con scrollbar
        frame_tabla = tk.Frame(self, bg=COLORES["fondo"])
        frame_tabla.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        self.canvas = tk.Canvas(
            frame_tabla,
            bg=COLORES["fondo"],
            highlightthickness=0,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Frame de grupos
        self.frame_grupos = tk.Frame(self.canvas, bg=COLORES["fondo"])
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.frame_grupos,
            anchor="nw",
            width=self.canvas.winfo_width() or 600,
        )
        
        self.frame_grupos.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        
        # Binding para rueda del ratón
        self.canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
    
    def cargar_datos(self, grupos: List[dict]):
        """Carga los datos de grupos y construye la tabla."""
        self.datos_grupos = grupos
        self.checkbox_estados.clear()
        self._foto_refs.clear()
        
        # Limpiar tabla anterior
        for widget in self.frame_grupos.winfo_children():
            widget.destroy()
        
        # Crear fila para cada grupo
        for idx_grupo, grupo in enumerate(grupos):
            fila = self._crear_fila_grupo(idx_grupo, grupo)
            fila.pack(fill="x", padx=0, pady=(0, 8))
    
    def _crear_fila_grupo(self, idx_grupo: int, grupo: dict) -> tk.Frame:
        """Crea una fila visual para un grupo."""
        fila = tk.Frame(
            self.frame_grupos,
            bg=COLORES["tarjeta"],
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORES["borde"],
        )
        
        # Encabezado de la fila
        header = tk.Frame(fila, bg=COLORES["tarjeta"])
        header.pack(fill="x", padx=12, pady=(8, 4))
        
        tipo_grupo = grupo.get("group_type", "exacto")
        emojis_tipo = {
            "exact": "🔴",
            "image_similar": "🟡",
            "video_similar": "🟢",
        }
        emoji = emojis_tipo.get(tipo_grupo, "⚪")
        
        # Información del grupo
        info_texto = f"{emoji} Grupo {idx_grupo + 1}: {len(grupo['files'])} archivos"
        score = grupo.get("score", 100)
        if score < 100:
            info_texto += f" | Similitud: {score:.1f}%"
        
        tk.Label(
            header,
            text=info_texto,
            font=("Segoe UI", 10, "bold"),
            bg=COLORES["tarjeta"],
            fg=COLORES["texto"],
        ).pack(side="left")
        
        # Espacio recuperable
        espacio = formato_tamaño(grupo.get("recoverable_size", 0))
        tk.Label(
            header,
            text=f"Espacio: {espacio}",
            font=("Segoe UI", 9),
            bg=COLORES["tarjeta"],
            fg=COLORES["advertencia"],
        ).pack(side="right")
        
        # Grid de archivos
        archivos_ordenados = sorted(
            grupo.get("files", []),
            key=lambda f: (f.get("width", 0) or 0) * (f.get("height", 0) or 0),
            reverse=True,
        )
        
        grid_archivos = tk.Frame(fila, bg=COLORES["tarjeta"])
        grid_archivos.pack(fill="x", padx=12, pady=(4, 12))
        
        for col, archivo in enumerate(archivos_ordenados[:4]):  # Máx 4 columnas visibles
            self._crear_celda_archivo(
                grid_archivos,
                idx_grupo,
                col,
                archivo,
                col == 0,  # Es la mejor foto
            ).pack(side="left", padx=4)
        
        # Si hay más de 4, mostrar indicador
        if len(archivos_ordenados) > 4:
            tk.Label(
                grid_archivos,
                text=f"+{len(archivos_ordenados) - 4}",
                font=("Segoe UI", 12, "bold"),
                bg=COLORES["tarjeta"],
                fg=COLORES["texto_muted"],
            ).pack(side="left", padx=4)
        
        # Binding para seleccionar la fila
        fila.bind("<Button-1>", lambda e: self._seleccionar_fila(idx_grupo))
        header.bind("<Button-1>", lambda e: self._seleccionar_fila(idx_grupo))
        
        return fila
    
    def _crear_celda_archivo(
        self,
        parent: tk.Frame,
        idx_grupo: int,
        idx_archivo: int,
        archivo: dict,
        es_mejor: bool,
    ) -> tk.Frame:
        """Crea una celda para un archivo en la tabla."""
        celda = tk.Frame(
            parent,
            bg=COLORES["tarjeta"],
            relief="sunken",
            bd=1,
        )
        
        # Checkbox
        var_check = tk.BooleanVar(value=False)
        self.checkbox_estados[(idx_grupo, self._clave_archivo(archivo))] = var_check
        
        cb = tk.Checkbutton(
            celda,
            text="✓ Eliminar",
            variable=var_check,
            font=("Segoe UI", 8),
            bg=COLORES["tarjeta"],
            fg=COLORES["peligro"],
        )
        cb.pack(pady=(4, 2))
        
        # Miniatura pequeña
        frame_img = tk.Frame(celda, bg=COLORES["fondo"], width=80, height=80)
        frame_img.pack(padx=4, pady=2)
        frame_img.pack_propagate(False)
        
        ruta_local = archivo.get("path")
        if ruta_local and os.path.exists(ruta_local):
            foto = cargar_imagen_miniatura(ruta_local, (80, 80))
            if foto:
                self._foto_refs[(idx_grupo, idx_archivo)] = foto
                tk.Label(frame_img, image=foto, bg=COLORES["fondo"]).pack()
        else:
            tk.Label(
                frame_img,
                text="📄",
                font=("Segoe UI", 24),
                bg=COLORES["fondo"],
                fg=COLORES["texto_muted"],
            ).pack()
        
        # Nombre
        nombre = archivo.get("name", "sin nombre")[:12]
        tk.Label(
            celda,
            text=nombre + "...",
            font=("Segoe UI", 7),
            bg=COLORES["tarjeta"],
            fg=COLORES["texto"],
            wraplength=80,
            justify="center",
        ).pack(padx=2, pady=2)
        
        # Tamaño
        tamaño = formato_tamaño(archivo.get("size", 0))
        tk.Label(
            celda,
            text=tamaño,
            font=("Segoe UI", 7),
            bg=COLORES["tarjeta"],
            fg=COLORES["texto_muted"],
        ).pack(pady=(2, 4))
        
        # Badge "MEJOR" para el primero
        if es_mejor:
            tk.Label(
                celda,
                text="⭐",
                font=("Segoe UI", 10),
                bg=COLORES["exito"],
                fg="white",
                width=10,
            ).pack(fill="x", padx=2, pady=(2, 4))
        
        return celda

    @staticmethod
    def _clave_archivo(archivo: dict) -> tuple:
        """Identidad estable aunque cambie el orden visual de los archivos."""
        return (
            archivo.get("source", ""),
            archivo.get("item_id", ""),
            archivo.get("path", ""),
            archivo.get("web_url", ""),
        )
    
    def _seleccionar_fila(self, idx_grupo: int):
        """Callback al seleccionar una fila."""
        if self.callback_fila and idx_grupo < len(self.datos_grupos):
            self.callback_fila(self.datos_grupos[idx_grupo], idx_grupo)


# ─────────────────────────────────────────────────────────────────────────────
# PANEL: CONTROL Y FILTROS
# ─────────────────────────────────────────────────────────────────────────────

class PanelControl(tk.Frame):
    """Panel inferior con filtros y acciones masivas."""
    
    def __init__(
        self,
        parent,
        callback_filtro=None,
        callback_seleccionar_filtrados=None,
        callback_eliminar=None,
        **kwargs
    ):
        super().__init__(parent, bg=COLORES["tarjeta"], **kwargs)
        
        self.callback_filtro = callback_filtro
        self.callback_seleccionar_filtrados = callback_seleccionar_filtrados
        self.callback_eliminar = callback_eliminar
        self.var_proveedor = tk.StringVar(value="Todos")
        self.var_tipo = tk.StringVar(value="Todos")
        
        self._construir_ui()
    
    def _construir_ui(self):
        """Construye los controles."""
        # Sección de filtro
        frame_filtro = tk.Frame(self, bg=COLORES["tarjeta"])
        frame_filtro.pack(fill="x", padx=12, pady=8)
        
        tk.Label(
            frame_filtro,
            text="Filtro por similitud (%):",
            font=("Segoe UI", 10),
            bg=COLORES["tarjeta"],
            fg=COLORES["texto"],
        ).pack(side="left", padx=(0, 8))

        proveedor_combo = ttk.Combobox(
            frame_filtro, textvariable=self.var_proveedor,
            values=["Todos", "local_folder", "whatsapp_local", "google_drive", "onedrive", "google_photos"],
            state="readonly", width=16,
        )
        proveedor_combo.pack(side="left", padx=4)
        proveedor_combo.bind("<<ComboboxSelected>>", lambda _event: self._notificar_filtro(self.var_umbral.get()))
        tipo_combo = ttk.Combobox(
            frame_filtro, textvariable=self.var_tipo,
            values=["Todos", "exact", "image_similar", "video_similar"],
            state="readonly", width=16,
        )
        tipo_combo.pack(side="left", padx=4)
        tipo_combo.bind("<<ComboboxSelected>>", lambda _event: self._notificar_filtro(self.var_umbral.get()))
        
        # Slider
        self.var_umbral = tk.IntVar(value=0)
        scale = tk.Scale(
            frame_filtro,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.var_umbral,
            bg=COLORES["tarjeta"],
            fg=COLORES["acento"],
            highlightthickness=0,
            command=lambda v: self._notificar_filtro(int(v)),
        )
        scale.pack(side="left", fill="x", expand=True, padx=4)
        
        tk.Label(
            frame_filtro,
            text="0%",
            font=("Segoe UI", 9),
            bg=COLORES["tarjeta"],
            fg=COLORES["texto_muted"],
            width=3,
        ).pack(side="left")
        
        # Sección de botones
        frame_botones = tk.Frame(self, bg=COLORES["tarjeta"])
        frame_botones.pack(fill="x", padx=12, pady=(0, 12))
        
        tk.Button(
            frame_botones,
            text="✓ Seleccionar Filtrados",
            font=("Segoe UI", 10),
            bg=COLORES["acento"],
            fg="white",
            command=self.callback_seleccionar_filtrados,
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=4)
        
        tk.Button(
            frame_botones,
            text="📦  Enviar a Cuarentena",
            font=("Segoe UI", 10),
            bg=COLORES["peligro"],
            fg="white",
            command=self.callback_eliminar,
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=4)

    def _notificar_filtro(self, umbral):
        if self.callback_filtro:
            self.callback_filtro(umbral, self.var_proveedor.get(), self.var_tipo.get())

# ─────────────────────────────────────────────────────────────────────────────
# VENTANA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class PanelOperacion(tk.Frame):
    """Configura autenticacion y ejecuta el CLI sin bloquear la interfaz."""

    def __init__(self, parent, callback_auth=None, callback_scan=None,
                 callback_drive_folders=None, **kwargs):
        super().__init__(parent, bg=COLORES["fondo"], **kwargs)
        self.callback_auth = callback_auth
        self.callback_scan = callback_scan
        self.callback_drive_folders = callback_drive_folders
        self.gestor_perfiles = GestorPerfiles()
        self.carpetas_locales = []
        self.roots_drive = []
        self.var_drive = tk.BooleanVar(value=False)
        self.var_onedrive = tk.BooleanVar(value=False)
        self.var_photos = tk.BooleanVar(value=False)
        self.var_photos_mode = tk.StringVar(value="app-created")
        self.var_whatsapp = tk.StringVar(value="")
        self.var_hash_mode = tk.StringVar(value="full")
        self.var_image_threshold = tk.StringVar(value="95")
        self.var_video_threshold = tk.StringVar(value="0.85")
        self.var_skip_similar = tk.BooleanVar(value=False)
        self.var_report = tk.StringVar(value=str(REPORTE_JSON.with_suffix("")))
        self.var_auth_provider = tk.StringVar(value="google")
        self.var_auth_profile = tk.StringVar(value="")
        self.var_google_profile = tk.StringVar(value="boteroestradamarcelo")
        self.var_onedrive_profile = tk.StringVar(value="botero_estrada_marcelo")
        self.var_onedrive_client_id = tk.StringVar(value="")
        self.var_onedrive_tenant = tk.StringVar(value="consumers")
        self._construir_ui()

    def _construir_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        auth_frame = tk.Frame(notebook, bg=COLORES["fondo"])
        scan_frame = tk.Frame(notebook, bg=COLORES["fondo"])
        notebook.add(auth_frame, text="  Autenticacion  ")
        notebook.add(scan_frame, text="  Escaneo  ")

        tk.Label(
            auth_frame,
            text="Selecciona una cuenta existente o crea un perfil nuevo introduciendo su correo. El perfil usa la parte anterior a @ y los archivos se guardan en secrets/accounts/.",
            bg=COLORES["fondo"], fg=COLORES["texto_muted"],
            anchor="w", justify="left", wraplength=900,
        ).pack(fill="x", padx=16, pady=(16, 10))

        perfiles = tk.Frame(auth_frame, bg=COLORES["tarjeta"], relief="solid", bd=1)
        perfiles.pack(fill="x", padx=16, pady=5)
        tk.Label(perfiles, text="Proveedor:", bg=COLORES["tarjeta"]).grid(row=0, column=0, padx=10, pady=10)
        proveedor_combo = ttk.Combobox(
            perfiles, textvariable=self.var_auth_provider,
            values=["google", "onedrive"], state="readonly", width=14,
        )
        proveedor_combo.grid(row=0, column=1, padx=4, pady=10)
        proveedor_combo.bind("<<ComboboxSelected>>", lambda _event: self._actualizar_perfiles())
        tk.Label(perfiles, text="Cuenta:", bg=COLORES["tarjeta"]).grid(row=0, column=2, padx=(18, 6), pady=10)
        self.profile_combo = ttk.Combobox(perfiles, textvariable=self.var_auth_profile, width=24)
        self.profile_combo.grid(row=0, column=3, padx=4, pady=10)
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _event: self._actualizar_estado_perfil())
        tk.Button(perfiles, text="Nueva cuenta", command=self._nueva_perfil,
                  bg=COLORES["acento"], fg="white", relief="flat").grid(row=0, column=4, padx=6)
        tk.Button(perfiles, text="Activar cuenta", command=self._activar_perfil,
              relief="flat").grid(row=0, column=5, padx=(0, 10))

        archivos = tk.Frame(auth_frame, bg=COLORES["tarjeta"], relief="solid", bd=1)
        archivos.pack(fill="x", padx=16, pady=5)
        tk.Label(archivos, text="Archivos de credenciales del perfil", bg=COLORES["tarjeta"],
                 fg=COLORES["texto"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 5))
        tk.Button(archivos, text="Adjuntar OAuth Google", command=lambda: self._adjuntar_json("google-drive.json"), relief="flat").grid(row=1, column=0, padx=8, pady=6)
        tk.Button(archivos, text="Adjuntar token Google", command=lambda: self._adjuntar_json("google-drive-token.json"), relief="flat").grid(row=1, column=1, padx=8, pady=6)
        tk.Button(archivos, text="Adjuntar token Photos", command=lambda: self._adjuntar_json("google-photos-token.json"), relief="flat").grid(row=1, column=2, padx=8, pady=6)
        tk.Button(archivos, text="Adjuntar config OneDrive", command=lambda: self._adjuntar_json("onedrive-config.json"), relief="flat").grid(row=2, column=0, padx=8, pady=6)
        tk.Button(archivos, text="Adjuntar token OneDrive", command=lambda: self._adjuntar_json("onedrive-token.json"), relief="flat").grid(row=2, column=1, padx=8, pady=6)
        tk.Button(archivos, text="Pegar JSON de token...", command=self._pegar_token, relief="flat").grid(row=2, column=2, padx=8, pady=6)
        self.auth_status = tk.Label(archivos, text="Selecciona un perfil para ver sus archivos.", bg=COLORES["tarjeta"], fg=COLORES["texto_muted"], anchor="w")
        self.auth_status.grid(row=2, column=3, sticky="w", padx=8, pady=(0, 10))
        tk.Label(archivos, text="OneDrive client ID:", bg=COLORES["tarjeta"]).grid(row=3, column=0, padx=8, pady=(0, 10), sticky="w")
        tk.Entry(archivos, textvariable=self.var_onedrive_client_id, width=38).grid(row=3, column=1, padx=4, pady=(0, 10), sticky="ew")
        tk.Label(archivos, text="Tenant:", bg=COLORES["tarjeta"]).grid(row=3, column=2, padx=4, pady=(0, 10))
        tk.Entry(archivos, textvariable=self.var_onedrive_tenant, width=14).grid(row=3, column=3, padx=4, pady=(0, 10))
        tk.Button(archivos, text="Guardar config", command=self._guardar_config_onedrive, relief="flat").grid(row=4, column=0, padx=8, pady=(0, 10))
        tk.Button(archivos, text="Copiar ID", command=self._copiar_client_id, relief="flat").grid(row=4, column=1, padx=4, pady=(0, 10), sticky="w")
        archivos.columnconfigure(1, weight=1)

        guia = tk.Frame(auth_frame, bg=COLORES["tarjeta"], relief="solid", bd=1)
        guia.pack(fill="x", padx=16, pady=5)
        tk.Label(guia, text="Ayuda paso a paso", bg=COLORES["tarjeta"], fg=COLORES["acento"], font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.auth_guide = tk.Label(guia, bg=COLORES["tarjeta"], fg=COLORES["texto"], justify="left", anchor="w", wraplength=900)
        self.auth_guide.pack(fill="x", padx=10, pady=(0, 10))
        self._actualizar_perfiles()
        proveedores = (
            ("Google Drive", "google-drive"),
            ("OneDrive", "onedrive"),
            ("Google Photos", "google-photos"),
        )
        self.estado_proveedores = {}
        for etiqueta, proveedor in proveedores:
            fila = tk.Frame(auth_frame, bg=COLORES["tarjeta"], relief="solid", bd=1)
            fila.pack(fill="x", padx=16, pady=5)
            tk.Label(
                fila, text=etiqueta, bg=COLORES["tarjeta"], fg=COLORES["texto"],
                font=("Segoe UI", 10, "bold"), anchor="w",
            ).pack(side="left", padx=12, pady=10)
            if proveedor == "google-photos":
                ttk.Combobox(
                    fila, textvariable=self.var_photos_mode,
                    values=["app-created", "picker"], state="readonly", width=14,
                ).pack(side="left", padx=8)
            tk.Button(
                fila, text="Autenticar", command=lambda p=proveedor: self._autenticar(p),
                bg=COLORES["acento"], fg="white", relief="flat", cursor="hand2",
            ).pack(side="right", padx=12, pady=6)
            estado = tk.Label(
                fila, text="No configurado", bg=COLORES["tarjeta"],
                fg=COLORES["peligro"], font=("Segoe UI", 9),
            )
            estado.pack(side="right", padx=4)
            self.estado_proveedores[proveedor] = estado

        self._actualizar_estado_proveedores()

        self.log = tk.Text(
            auth_frame, height=12, state="disabled", wrap="word",
            bg="#1e1e1e", fg="#e8eaed", font=TIPOGRAFIA["mono"],
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(12, 16))
        progreso = tk.Frame(auth_frame, bg=COLORES["fondo"])
        progreso.pack(fill="x", padx=16, pady=(0, 12))
        self.progress_label = tk.Label(
            progreso, text="Listo", bg=COLORES["fondo"],
            fg=COLORES["texto_muted"], anchor="w",
        )
        self.progress_label.pack(fill="x")
        self.progress_bar = ttk.Progressbar(progreso, mode="determinate", maximum=100)
        self.progress_bar.pack(fill="x", pady=(4, 0))

        tk.Label(
            scan_frame, text="Origenes cloud", bg=COLORES["fondo"],
            fg=COLORES["acento"], font=TIPOGRAFIA["subtítulo"], anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 6))
        cloud = tk.Frame(scan_frame, bg=COLORES["tarjeta"], relief="solid", bd=1)
        cloud.pack(fill="x", padx=16, pady=(0, 8))
        tk.Checkbutton(cloud, text="Google Drive", variable=self.var_drive,
                       bg=COLORES["tarjeta"]).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        tk.Checkbutton(cloud, text="OneDrive", variable=self.var_onedrive,
                       bg=COLORES["tarjeta"]).grid(row=0, column=1, sticky="w", padx=10, pady=8)
        tk.Checkbutton(cloud, text="Google Photos API", variable=self.var_photos,
                       bg=COLORES["tarjeta"]).grid(row=0, column=2, sticky="w", padx=10, pady=8)
        tk.Label(cloud, text="Perfil Google:", bg=COLORES["tarjeta"],
                 fg=COLORES["texto_muted"]).grid(row=1, column=2, padx=10, pady=6)
        self.google_profile_scan = ttk.Combobox(
            cloud, textvariable=self.var_google_profile, state="readonly", width=24,
        )
        self.google_profile_scan.grid(row=1, column=3, padx=10, pady=6)
        tk.Label(cloud, text="Perfil OneDrive:", bg=COLORES["tarjeta"],
                 fg=COLORES["texto_muted"]).grid(row=2, column=2, padx=10, pady=6)
        self.onedrive_profile_scan = ttk.Combobox(
            cloud, textvariable=self.var_onedrive_profile, state="readonly", width=24,
        )
        self.onedrive_profile_scan.grid(row=2, column=3, padx=10, pady=6)
        tk.Label(cloud, text="Modo Photos:", bg=COLORES["tarjeta"],
                 fg=COLORES["texto_muted"]).grid(row=1, column=0, sticky="w", padx=10, pady=6)
        ttk.Combobox(cloud, textvariable=self.var_photos_mode,
                     values=["app-created", "picker"], state="readonly", width=14
                     ).grid(row=1, column=1, sticky="w", padx=10, pady=6)
        tk.Label(cloud, text="IDs de carpetas Drive (uno por linea):",
                 bg=COLORES["tarjeta"], fg=COLORES["texto_muted"]
                 ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(6, 2))
        self.drive_list = tk.Listbox(cloud, height=3, exportselection=False)
        self.drive_list.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        tk.Button(cloud, text="Anadir ID", command=self._anadir_drive,
                  bg=COLORES["acento"], fg="white", relief="flat").grid(row=3, column=2, padx=6)
        tk.Button(cloud, text="Quitar", command=self._quitar_drive,
                  relief="flat").grid(row=3, column=3, padx=(0, 10))
        tk.Button(cloud, text="Cargar carpetas Drive", command=self._cargar_drive,
              relief="flat").grid(row=4, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 8))
        cloud.columnconfigure(1, weight=1)

        tk.Label(scan_frame, text="Carpetas locales", bg=COLORES["fondo"],
                 fg=COLORES["acento"], font=TIPOGRAFIA["subtítulo"], anchor="w"
                 ).pack(fill="x", padx=16, pady=(4, 6))
        local = tk.Frame(scan_frame, bg=COLORES["tarjeta"], relief="solid", bd=1)
        local.pack(fill="x", padx=16, pady=(0, 8))
        self.local_list = tk.Listbox(local, height=4, exportselection=False)
        self.local_list.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        botones_local = tk.Frame(local, bg=COLORES["tarjeta"])
        botones_local.pack(side="right", padx=10)
        tk.Button(botones_local, text="Anadir carpeta...", command=self._anadir_local,
                  bg=COLORES["acento"], fg="white", relief="flat").pack(fill="x", pady=3)
        tk.Button(botones_local, text="Quitar seleccion", command=self._quitar_local,
                  relief="flat").pack(fill="x", pady=3)
        tk.Label(local, text="WhatsApp (opcional):", bg=COLORES["tarjeta"],
                 fg=COLORES["texto_muted"]).pack(side="left", padx=(0, 4))
        tk.Entry(local, textvariable=self.var_whatsapp, width=35).pack(side="left", padx=(0, 10), pady=10)

        opciones = tk.Frame(scan_frame, bg=COLORES["tarjeta"], relief="solid", bd=1)
        opciones.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(opciones, text="Hash:", bg=COLORES["tarjeta"]).grid(row=0, column=0, padx=10, pady=8)
        ttk.Combobox(opciones, textvariable=self.var_hash_mode,
                     values=["metadata", "full"], state="readonly", width=12
                     ).grid(row=0, column=1, padx=4, pady=8)
        tk.Label(opciones, text="Imagen %:", bg=COLORES["tarjeta"]).grid(row=0, column=2, padx=10)
        tk.Entry(opciones, textvariable=self.var_image_threshold, width=7).grid(row=0, column=3)
        tk.Label(opciones, text="Video ratio:", bg=COLORES["tarjeta"]).grid(row=0, column=4, padx=10)
        tk.Entry(opciones, textvariable=self.var_video_threshold, width=7).grid(row=0, column=5)
        tk.Checkbutton(opciones, text="Solo exactos", variable=self.var_skip_similar,
                       bg=COLORES["tarjeta"]).grid(row=0, column=6, padx=10)
        tk.Label(opciones, text="Reporte:", bg=COLORES["tarjeta"]).grid(row=1, column=0, padx=10, pady=8)
        tk.Entry(opciones, textvariable=self.var_report).grid(row=1, column=1, columnspan=5,
                                                              sticky="ew", padx=4, pady=8)
        tk.Button(opciones, text="Examinar...", command=self._elegir_reporte,
                  relief="flat").grid(row=1, column=6, padx=10)
        opciones.columnconfigure(5, weight=1)

        tk.Button(
            scan_frame, text="Ejecutar escaneo", command=self._escanear,
            bg=COLORES["exito"], fg="white", font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", padx=18, pady=8,
        ).pack(anchor="e", padx=16, pady=(2, 12))

    def _autenticar(self, proveedor):
        self.var_auth_provider.set("google" if proveedor.startswith("google") else "onedrive")
        self._actualizar_perfiles()
        self._actualizar_perfiles_escaneo()
        if not self.var_auth_profile.get().strip():
            self._nueva_perfil()
        if not self.var_auth_profile.get().strip():
            return
        self._activar_perfil()
        if self.callback_auth:
            self.callback_auth(proveedor, self.var_photos_mode.get(), self.var_auth_profile.get())

    def _actualizar_perfiles(self):
        perfiles = self.gestor_perfiles.perfiles(self.var_auth_provider.get())
        self.profile_combo["values"] = perfiles
        if self.var_auth_profile.get() not in perfiles:
            self.var_auth_profile.set(perfiles[0] if perfiles else "")
        self._actualizar_guia()
        self._actualizar_estado_perfil()
        self._actualizar_perfiles_escaneo()

    def _actualizar_perfiles_escaneo(self):
        google = self.gestor_perfiles.perfiles("google")
        onedrive = self.gestor_perfiles.perfiles("onedrive")
        self.google_profile_scan["values"] = google
        self.onedrive_profile_scan["values"] = onedrive
        if self.var_google_profile.get() not in google and google:
            self.var_google_profile.set(google[0])
        if self.var_onedrive_profile.get() not in onedrive and onedrive:
            self.var_onedrive_profile.set(onedrive[0])
        self._actualizar_estado_proveedores()

    def _actualizar_estado_proveedores(self):
        if not hasattr(self, "estado_proveedores"):
            return
        google = self.gestor_perfiles.carpeta("google", self.var_google_profile.get())
        onedrive = self.gestor_perfiles.carpeta("onedrive", self.var_onedrive_profile.get())
        estados = {
            "google-drive": (google / "google-drive.json", google / "google-drive-token.json"),
            "google-photos": (google / "google-photos-token.json",),
            "onedrive": (onedrive / "onedrive-config.json", onedrive / "onedrive-token.json"),
        }
        for proveedor, label in self.estado_proveedores.items():
            rutas = estados[proveedor]
            completos = all(ruta.exists() for ruta in rutas)
            label.configure(
                text="Configurado" if completos else "Pendiente",
                fg=COLORES["exito"] if completos else COLORES["peligro"],
            )

    def _guardar_config_onedrive(self):
        if self.var_auth_provider.get() != "onedrive":
            messagebox.showinfo("Proveedor", "Selecciona OneDrive antes de guardar su configuración.")
            return
        if not self._perfil_requerido():
            return
        client_id = self.var_onedrive_client_id.get().strip()
        tenant = self.var_onedrive_tenant.get().strip() or "consumers"
        if not client_id:
            messagebox.showwarning("OneDrive", "Introduce el Application (client) ID.")
            return
        ruta = self.gestor_perfiles.carpeta("onedrive", self.var_auth_profile.get()) / "onedrive-config.json"
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump({"client_id": client_id, "tenant": tenant}, archivo, indent=2)
        self._activar_perfil()
        self.auth_status.configure(text=f"Configuracion OneDrive guardada en: {ruta.name}")

    def _copiar_client_id(self):
        client_id = self.var_onedrive_client_id.get().strip()
        if client_id:
            self.clipboard_clear()
            self.clipboard_append(client_id)
            self.auth_status.configure(text="Client ID copiado al portapapeles.")

    def _actualizar_guia(self):
        if not hasattr(self, "auth_guide"):
            return
        if self.var_auth_provider.get() == "google":
            texto = (
                "1. En Google Cloud crea un cliente OAuth de tipo Aplicacion de escritorio.\n"
                "2. Descarga el JSON y pulsa 'Adjuntar OAuth Google'.\n"
                "3. Crea el perfil usando el correo; se guardará la parte anterior a @.\n"
                "4. Pulsa 'Activar cuenta' y después Autenticar; elige la cuenta en el navegador.\n"
                "5. El token se guarda automaticamente en el perfil; Drive y Photos usan tokens separados."
            )
        else:
            texto = (
                "1. En Microsoft Entra registra una aplicacion y copia el Application (client) ID.\n"
                "2. Concede permisos delegados Files.Read.All y User.Read.\n"
                "3. Crea el perfil usando el correo; se guardará la parte anterior a @.\n"
                "4. Adjunta onedrive-config.json, activa el perfil y autentica en el navegador.\n"
                "5. La caché JSON de MSAL se guarda automaticamente en el perfil."
            )
        self.auth_guide.configure(text=texto)

    def _nueva_perfil(self):
        dialogo = tk.Toplevel(self)
        dialogo.title("Nueva cuenta")
        dialogo.transient(self.winfo_toplevel())
        tk.Label(dialogo, text="Correo de la cuenta (el perfil será la parte anterior a @):").pack(padx=12, pady=(12, 4))
        entrada = tk.Entry(dialogo, width=35)
        entrada.pack(padx=12, pady=4)
        entrada.focus_set()

        def aceptar():
            correo = entrada.get().strip()
            if "@" not in correo or not correo.split("@", 1)[0].strip():
                messagebox.showwarning("Cuenta", "Introduce un correo válido, por ejemplo usuario@gmail.com.", parent=dialogo)
                return
            nombre = self.gestor_perfiles.perfil_desde_correo(correo)
            if nombre:
                self.gestor_perfiles.carpeta(self.var_auth_provider.get(), nombre)
                self.var_auth_profile.set(nombre)
                self._actualizar_perfiles()
                self.var_auth_profile.set(nombre)
            dialogo.destroy()

        tk.Button(dialogo, text="Crear", command=aceptar, bg=COLORES["acento"], fg="white", relief="flat").pack(pady=10)
        dialogo.grab_set()
        self.wait_window(dialogo)

    def _perfil_requerido(self):
        if self.var_auth_profile.get().strip():
            return True
        self._nueva_perfil()
        return bool(self.var_auth_profile.get().strip())

    def _adjuntar_json(self, nombre_destino):
        if not self._perfil_requerido():
            return
        if self.var_auth_provider.get() == "google" and nombre_destino.startswith("onedrive"):
            messagebox.showwarning("Proveedor", "Selecciona el proveedor OneDrive antes de adjuntar ese archivo.")
            return
        if self.var_auth_provider.get() == "onedrive" and nombre_destino.startswith("google"):
            messagebox.showwarning("Proveedor", "Selecciona el proveedor Google antes de adjuntar ese archivo.")
            return
        origen = filedialog.askopenfilename(
            title=f"Seleccionar {nombre_destino}",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if not origen:
            return
        try:
            with open(origen, "r", encoding="utf-8") as archivo:
                contenido = json.load(archivo)
            if not isinstance(contenido, dict):
                raise ValueError("El JSON debe contener un objeto.")
            destino = self.gestor_perfiles.importar(
                self.var_auth_provider.get(), self.var_auth_profile.get(), origen, nombre_destino
            )
            self.auth_status.configure(text=f"Guardado en el perfil: {destino.name}")
            if nombre_destino == "onedrive-config.json":
                self.var_onedrive_client_id.set(str(contenido.get("client_id", "")))
                self.var_onedrive_tenant.set(str(contenido.get("tenant", "consumers")))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("JSON no valido", f"No se pudo guardar el archivo:\n{error}")

    def _pegar_token(self):
        if not self._perfil_requerido():
            return
        proveedor = self.var_auth_provider.get()
        nombre = "google-drive-token.json" if proveedor == "google" else "onedrive-token.json"
        dialogo = tk.Toplevel(self)
        dialogo.title("Pegar JSON de token")
        dialogo.geometry("720x480")
        dialogo.transient(self.winfo_toplevel())
        tk.Label(dialogo, text="Pega el JSON del token. No se mostrara en el log ni se copiara al portapapeles.").pack(anchor="w", padx=12, pady=10)
        texto = tk.Text(dialogo, wrap="none")
        texto.pack(fill="both", expand=True, padx=12, pady=4)

        def guardar():
            try:
                contenido = json.loads(texto.get("1.0", "end-1c"))
                if not isinstance(contenido, dict):
                    raise ValueError("El JSON debe contener un objeto.")
                ruta = self.gestor_perfiles.carpeta(proveedor, self.var_auth_profile.get()) / nombre
                with open(ruta, "w", encoding="utf-8") as archivo:
                    json.dump(contenido, archivo, indent=2)
                self.auth_status.configure(text=f"Token guardado en el perfil: {nombre}")
                dialogo.destroy()
            except (ValueError, OSError) as error:
                messagebox.showerror("Token no valido", str(error), parent=dialogo)

        tk.Button(dialogo, text="Guardar token", command=guardar, bg=COLORES["acento"], fg="white", relief="flat").pack(pady=10)

    def _activar_perfil(self):
        if not self._perfil_requerido():
            return False
        proveedor = self.var_auth_provider.get()
        try:
            carpeta = self.gestor_perfiles.activar(proveedor, self.var_auth_profile.get())
            self.auth_status.configure(text=f"Perfil seleccionado: {carpeta}")
            return True
        except OSError as error:
            messagebox.showerror("Perfil", f"No se pudo activar la cuenta:\n{error}")
            return False

    def _actualizar_estado_perfil(self):
        if not hasattr(self, "auth_status") or not self.var_auth_profile.get():
            return
        carpeta = self.gestor_perfiles.carpeta(self.var_auth_provider.get(), self.var_auth_profile.get())
        archivos = sorted(p.name for p in carpeta.glob("*.json"))
        self.auth_status.configure(text="Archivos: " + (", ".join(archivos) if archivos else "ninguno"))
        configuracion = carpeta / "onedrive-config.json"
        if configuracion.exists():
            try:
                with open(configuracion, "r", encoding="utf-8") as archivo:
                    datos = json.load(archivo)
                self.var_onedrive_client_id.set(str(datos.get("client_id", "")))
                self.var_onedrive_tenant.set(str(datos.get("tenant", "consumers")))
            except (OSError, json.JSONDecodeError):
                self.var_onedrive_client_id.set("")

    def _anadir_local(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta local")
        if carpeta and carpeta not in self.carpetas_locales:
            self.carpetas_locales.append(carpeta)
            self.local_list.insert("end", carpeta)

    def _quitar_local(self):
        seleccion = list(self.local_list.curselection())
        for indice in reversed(seleccion):
            self.local_list.delete(indice)
            self.carpetas_locales.pop(indice)

    def _anadir_drive(self):
        dialogo = tk.Toplevel(self)
        dialogo.title("ID de carpeta de Google Drive")
        dialogo.transient(self.winfo_toplevel())
        tk.Label(dialogo, text="Pega el ID de la carpeta raíz de Drive:").pack(padx=12, pady=(12, 4))
        entrada = tk.Entry(dialogo, width=45)
        entrada.pack(padx=12, pady=4)
        entrada.focus_set()
        def aceptar():
            valor = entrada.get().strip()
            if valor and valor not in self.roots_drive:
                self.roots_drive.append(valor)
                self.drive_list.insert("end", valor)
            dialogo.destroy()
        tk.Button(dialogo, text="Añadir", command=aceptar).pack(pady=10)

    def _quitar_drive(self):
        seleccion = list(self.drive_list.curselection())
        for indice in reversed(seleccion):
            self.drive_list.delete(indice)
            self.roots_drive.pop(indice)

    def _cargar_drive(self):
        if self.callback_drive_folders:
            self.callback_drive_folders()

    def mostrar_carpetas_drive(self, carpetas):
        """Muestra un selector para añadir una o varias carpetas de Drive."""
        dialogo = tk.Toplevel(self)
        dialogo.title("Seleccionar carpetas de Google Drive")
        dialogo.geometry("560x420")
        dialogo.transient(self.winfo_toplevel())
        tk.Label(dialogo, text="Selecciona una o varias carpetas y pulsa Añadir:").pack(
            anchor="w", padx=12, pady=(12, 6)
        )
        lista = tk.Listbox(dialogo, selectmode="extended", exportselection=False)
        lista.pack(fill="both", expand=True, padx=12, pady=6)
        for nombre, folder_id in carpetas:
            lista.insert("end", f"{nombre}  [{folder_id}]")

        def aceptar():
            for indice in lista.curselection():
                folder_id = carpetas[indice][1]
                if folder_id not in self.roots_drive:
                    self.roots_drive.append(folder_id)
                    self.drive_list.insert("end", folder_id)
            dialogo.destroy()

        tk.Button(dialogo, text="Añadir seleccionadas", command=aceptar,
                  bg=COLORES["acento"], fg="white", relief="flat").pack(pady=10)

    def _elegir_reporte(self):
        ruta = filedialog.asksaveasfilename(
            title="Ubicacion base del reporte", defaultextension=".json",
            filetypes=[("Reporte JSON", "*.json"), ("Todos", "*.*")],
        )
        if ruta:
            self.var_report.set(str(Path(ruta).with_suffix("")))

    def _escanear(self):
        if not (self.carpetas_locales or self.var_whatsapp.get().strip()
                or self.var_drive.get() or self.var_onedrive.get() or self.var_photos.get()):
            messagebox.showwarning("Origen requerido", "Selecciona al menos una carpeta u origen cloud.")
            return
        try:
            float(self.var_image_threshold.get())
            float(self.var_video_threshold.get())
        except ValueError:
            messagebox.showerror("Opciones invalidas", "Los umbrales deben ser numericos.")
            return
        configuracion = {
            "sources": [p for p, activo in (
                ("google-drive", self.var_drive.get()),
                ("onedrive", self.var_onedrive.get()),
                ("google-photos", self.var_photos.get()),
            ) if activo],
            "drive_roots": list(self.roots_drive),
            "local_folders": list(self.carpetas_locales),
            "whatsapp_folder": self.var_whatsapp.get().strip(),
            "photos_mode": self.var_photos_mode.get(),
            "hash_mode": self.var_hash_mode.get(),
            "image_threshold": self.var_image_threshold.get(),
            "video_threshold": self.var_video_threshold.get(),
            "skip_similar": self.var_skip_similar.get(),
            "report": self.var_report.get().strip() or str(REPORTE_JSON.with_suffix("")),
            "google_profile": self.var_google_profile.get(),
            "onedrive_profile": self.var_onedrive_profile.get(),
        }
        if self.callback_scan:
            self.callback_scan(configuracion)

    def escribir_log(self, texto):
        self.log.configure(state="normal")
        self.log.insert("end", texto)
        self.log.see("end")
        self.log.configure(state="disabled")

    def actualizar_progreso(self, porcentaje, texto):
        self.progress_label.configure(text=texto)
        if porcentaje is not None:
            self.progress_bar.configure(value=max(0, min(100, porcentaje)))

class VentanaAvanzada(tk.Tk):
    """Ventana principal de la interfaz avanzada."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Media Dedupe — Interfaz Avanzada")
        self.geometry("1400x900")
        self.minsize(1000, 700)
        self.configure(bg=COLORES["fondo"])
        
        self.datos_originales = []
        self.datos_filtrados = []
        self._cola_proceso = queue.Queue()
        self._proceso_activo = False
        self._proceso = None
        self._cancel_requested = False
        self.gestor_cuarentena = GestorCuarentena()
        
        self._construir_ui()
    
    def _construir_ui(self):
        """Construye la interfaz completa."""
        # Encabezado global
        header = tk.Frame(self, bg=COLORES["acento"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="🖼️  Media Dedupe — Gestor Avanzado de Duplicados",
            font=("Segoe UI", 16, "bold"),
            bg=COLORES["acento"],
            fg="white",
        ).pack(side="left", padx=16, pady=12)
        
        tk.Button(
            header,
            text="📂 Abrir Reporte...",
            font=("Segoe UI", 10),
            bg="white",
            fg=COLORES["acento"],
            command=self._abrir_reporte,
            padx=12,
            relief="flat",
        ).pack(side="right", padx=12, pady=10)

        for etiqueta, extension in (("JSON", ".json"), ("CSV", ".csv"), ("HTML", ".html")):
            tk.Button(
                header, text=f"Abrir {etiqueta}",
                command=lambda ext=extension: self._abrir_ultimo_reporte(ext),
                bg="white", fg=COLORES["acento"], relief="flat",
            ).pack(side="right", padx=2, pady=10)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        operacion_frame = tk.Frame(self.notebook, bg=COLORES["fondo"])
        resultados_frame = tk.Frame(self.notebook, bg=COLORES["fondo"])
        self.notebook.add(operacion_frame, text="  Operacion  ")
        self.notebook.add(resultados_frame, text="  Resultados  ")

        self.panel_operacion = PanelOperacion(
            operacion_frame,
            callback_auth=self._autenticar_proveedor,
            callback_scan=self._ejecutar_escaneo,
            callback_drive_folders=self._cargar_carpetas_drive,
        )
        self.panel_operacion.pack(fill="both", expand=True)

        # Panel superior: vista previa
        self.panel_vista_previa = PanelVistaPrevia(resultados_frame)
        self.panel_vista_previa.pack(fill="x", padx=8, pady=8)
        
        # Panel central: tabla
        self.panel_resultados = PanelResultados(
            resultados_frame,
            callback_fila_seleccionada=self._fila_seleccionada,
        )
        self.panel_resultados.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        # Panel inferior: control
        self.panel_control = PanelControl(
            resultados_frame,
            callback_filtro=self._aplicar_filtro,
            callback_seleccionar_filtrados=self._seleccionar_filtrados,
            callback_eliminar=self._enviar_a_cuarentena,
        )
        self.panel_control.pack(fill="x", padx=8, pady=(0, 8))

        tk.Button(
            resultados_frame, text="Gestionar cuarentena",
            command=self._gestionar_cuarentena,
            relief="flat", cursor="hand2",
        ).pack(anchor="e", padx=12, pady=(0, 8))

        self.after(100, self._procesar_salida)

        self.boton_cancelar = tk.Button(
            header, text="Cancelar proceso", command=self._cancelar_proceso,
            bg=COLORES["peligro"], fg="white", relief="flat", state="disabled",
        )
        self.boton_cancelar.pack(side="right", padx=(0, 8), pady=10)

    def _autenticar_proveedor(self, proveedor: str, photos_mode: str, perfil: str):
        comando = [sys.executable, str(MEDIA_DEDUPE_PY), "auth", proveedor]
        proveedor_perfil = "google" if proveedor.startswith("google") else "onedrive"
        comando.extend([
            "--google-profile", perfil if proveedor_perfil == "google" else "boteroestradamarcelo",
            "--onedrive-profile", perfil if proveedor_perfil == "onedrive" else "botero_estrada_marcelo",
        ])
        if proveedor == "google-photos":
            comando.extend(["--photos-mode", photos_mode])
        self._lanzar_proceso(comando)

    def _cargar_carpetas_drive(self):
        """Carga carpetas de Drive en segundo plano usando el token configurado."""
        if self._proceso_activo:
            messagebox.showwarning("Proceso activo", "Espera a que termine el proceso actual.")
            return

        self.panel_operacion.escribir_log("Consultando carpetas de Google Drive...\n")

        def consultar():
            try:
                from providers.google_drive import GoogleDriveProvider
                perfil = self.panel_operacion.var_auth_profile.get()
                paths = rutas_perfil_google(perfil)
                provider = GoogleDriveProvider(
                    credentials_file=str(paths["credentials"]),
                    token_file=str(paths["drive_token"]),
                )
                carpetas = provider.list_folders()
                self.after(0, lambda: self._mostrar_carpetas_drive(carpetas))
            except Exception as error:
                self.after(0, lambda: messagebox.showerror(
                    "Google Drive", f"No se pudieron cargar las carpetas:\n{error}"
                ))

        threading.Thread(target=consultar, daemon=True).start()

    def _mostrar_carpetas_drive(self, carpetas):
        if not carpetas:
            messagebox.showinfo("Google Drive", "No se encontraron carpetas visibles.")
            return
        self.panel_operacion.mostrar_carpetas_drive(carpetas)

    def _ejecutar_escaneo(self, configuracion: dict):
        comando = [sys.executable, str(MEDIA_DEDUPE_PY), "scan"]
        for source in configuracion["sources"]:
            comando.extend(["--source", source])
        for root in configuracion["drive_roots"]:
            comando.extend(["--drive-root", root])
        for carpeta in configuracion["local_folders"]:
            comando.extend(["--local-folder", carpeta])
        if configuracion["whatsapp_folder"]:
            comando.extend(["--whatsapp-folder", configuracion["whatsapp_folder"]])
        comando.extend([
            "--photos-mode", configuracion["photos_mode"],
            "--hash-mode", configuracion["hash_mode"],
            "--image-threshold", configuracion["image_threshold"],
            "--video-threshold", configuracion["video_threshold"],
            "--report", configuracion["report"],
        ])
        if configuracion["skip_similar"]:
            comando.append("--skip-similar")
        google_profile = configuracion["google_profile"]
        onedrive_profile = configuracion["onedrive_profile"]
        comando.extend([
            "--google-profile", google_profile,
            "--onedrive-profile", onedrive_profile,
        ])
        self._lanzar_proceso(comando, configuracion["report"])

    def _lanzar_proceso(self, comando, reporte_base=None, callback_fin=None):
        if self._proceso_activo:
            messagebox.showwarning("Proceso activo", "Espera a que termine el proceso actual.")
            return
        self._proceso_activo = True
        self._cancel_requested = False
        self.boton_cancelar.configure(state="normal")
        self.panel_operacion.escribir_log("\n$ " + " ".join(f'"{a}"' if " " in a else a for a in comando) + "\n")
        def ejecutar():
            try:
                proceso = subprocess.Popen(
                    comando, cwd=str(Path(MEDIA_DEDUPE_PY).parent),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                self._proceso = proceso
                if self._cancel_requested:
                    proceso.terminate()
                for linea in proceso.stdout:
                    self._cola_proceso.put(("linea", linea))
                codigo = proceso.wait()
                self._cola_proceso.put((
                    "fin", codigo, reporte_base, callback_fin, self._cancel_requested
                ))
            except Exception as error:
                self._cola_proceso.put(("error", str(error)))
        threading.Thread(target=ejecutar, daemon=True).start()

    def _cancelar_proceso(self):
        if not self._proceso_activo:
            return
        self._cancel_requested = True
        self.panel_operacion.escribir_log("\nCancelando proceso...\n")
        if not self._proceso:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self._proceso.pid), "/T", "/F"],
                    capture_output=True, text=True, timeout=10,
                )
            else:
                self._proceso.terminate()
        except OSError as error:
            self.panel_operacion.escribir_log(f"No se pudo cancelar: {error}\n")

    def _procesar_salida(self):
        try:
            while True:
                evento = self._cola_proceso.get_nowait()
                if evento[0] == "linea":
                    self.panel_operacion.escribir_log(evento[1])
                    self._actualizar_progreso(evento[1])
                elif evento[0] == "error":
                    self._proceso_activo = False
                    self.panel_operacion.escribir_log(f"ERROR: {evento[1]}\n")
                    messagebox.showerror("Error de ejecucion", evento[1])
                else:
                    _, codigo, reporte_base, callback_fin, cancelado = evento
                    self._proceso_activo = False
                    self._proceso = None
                    self.boton_cancelar.configure(state="disabled")
                    if cancelado:
                        mensaje = "Proceso cancelado por el usuario."
                    else:
                        mensaje = "Proceso terminado correctamente." if codigo == 0 else f"Proceso terminado con codigo {codigo}."
                    self.panel_operacion.escribir_log(mensaje + "\n")
                    if callback_fin:
                        callback_fin(codigo)
                    if codigo == 0 and reporte_base:
                        reporte = Path(reporte_base).with_suffix(".json")
                        if reporte.exists():
                            self._cargar_reporte_json(str(reporte))
                            self.notebook.select(1)
        except queue.Empty:
            pass
        self.after(100, self._procesar_salida)

    def _actualizar_progreso(self, linea: str):
        """Extrae progreso de los mensajes del CLI sin acoplar el CLI a Tkinter."""
        patrones = (
            r"(?:Hashes calculados|Procesadas|Procesados):\s*(\d+)/(\d+)",
            r"(?:archivos listados|archivos encontrados):\s*(\d+)",
        )
        for indice, patron in enumerate(patrones):
            encontrado = re.search(patron, linea, re.IGNORECASE)
            if not encontrado:
                continue
            if indice == 0:
                actual, total = map(int, encontrado.groups())
                porcentaje = (actual / total * 100) if total else 0
                self.panel_operacion.actualizar_progreso(porcentaje, f"Procesando {actual}/{total}")
            else:
                actual = int(encontrado.group(1))
                self.panel_operacion.actualizar_progreso(None, f"Archivos listados: {actual}")
            return
    
    def _abrir_reporte(self):
        """Abre un diálogo para seleccionar un archivo JSON de reporte."""
        archivo = filedialog.askopenfilename(
            title="Abrir reporte JSON",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        
        if archivo:
            self._cargar_reporte_json(archivo)

    def _abrir_ultimo_reporte(self, extension):
        ruta = REPORTE_JSON.with_suffix(extension)
        if not ruta.exists():
            messagebox.showinfo("Reporte", f"No existe todavía:\n{ruta}")
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(ruta))
            else:
                subprocess.Popen(["xdg-open", str(ruta)])
        except OSError as error:
            messagebox.showerror("Reporte", f"No se pudo abrir el archivo:\n{error}")
    
    def _cargar_reporte_json(self, ruta: str):
        """Carga un archivo JSON de reporte."""
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)

            if datos.get("scan_status") == "partial":
                errores = datos.get("scan_errors", [])
                detalle = "\n".join(str(error) for error in errores[:5])
                self.panel_operacion.escribir_log(
                    "ADVERTENCIA: reporte parcial.\n" + detalle + "\n"
                )
                messagebox.showwarning(
                    "Reporte parcial",
                    "El reporte contiene resultados incompletos.\n\n" + detalle,
                )
            
            self.datos_originales = datos.get("groups", [])
            self.datos_filtrados = list(self.datos_originales)
            
            self.panel_resultados.cargar_datos(self.datos_filtrados)
            
            if self.datos_filtrados:
                self._fila_seleccionada(self.datos_filtrados[0], 0)
            
            self.title(f"Media Dedupe — {Path(ruta).name}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo:\n{e}")
    
    def _fila_seleccionada(self, grupo: dict, índice: int):
        """Callback al seleccionar una fila."""
        self.panel_vista_previa.mostrar_grupo(grupo, índice)
    
    def _aplicar_filtro(self, umbral: int, proveedor="Todos", tipo="Todos"):
        """Filtra grupos por similitud, proveedor y tipo."""
        self.datos_filtrados = [
            g for g in self.datos_originales
            if g.get("score", 100) >= umbral
            and (tipo == "Todos" or g.get("group_type") == tipo)
            and (
                proveedor == "Todos"
                or any(item.get("source") == proveedor for item in g.get("files", []))
            )
        ]
        
        self.panel_resultados.cargar_datos(self.datos_filtrados)
    
    def _seleccionar_filtrados(self):
        """Selecciona todos los archivos NO-MEJORES de los grupos filtrados."""
        for idx_grupo, grupo in enumerate(self.datos_filtrados):
            archivos = grupo.get("files", [])
            # El primero es el mejor, los demás se marcan
            for archivo in archivos[1:]:
                key = (idx_grupo, self.panel_resultados._clave_archivo(archivo))
                if key in self.panel_resultados.checkbox_estados:
                    self.panel_resultados.checkbox_estados[key].set(True)
    
    def _enviar_a_cuarentena(self):
        """Mueve los archivos locales seleccionados a una sesión reversible."""
        seleccionadas = [
            (idx_grupo, clave_archivo)
            for (idx_grupo, clave_archivo), var in self.panel_resultados.checkbox_estados.items()
            if var.get()
        ]
        
        if not seleccionadas:
            messagebox.showwarning("Advertencia", "No hay archivos seleccionados.")
            return
        
        # Confirmación
        cantidad = len(seleccionadas)
        if not messagebox.askyesno(
            "Confirmar",
            f"¿Mover {cantidad} archivo(s) a cuarentena?\n\nPodrás restaurarlos después.",
        ):
            return
        
        # Agrupar por grupo y archivo
        archivos_a_eliminar = []
        for idx_grupo, clave_archivo in seleccionadas:
            if idx_grupo < len(self.datos_filtrados):
                grupo = self.datos_filtrados[idx_grupo]
                archivos = grupo.get("files", [])
                archivo = next(
                    (item for item in archivos
                     if self.panel_resultados._clave_archivo(item) == clave_archivo),
                    None,
                )
                if archivo:
                    archivos_a_eliminar.append(archivo)
        
        thread = threading.Thread(
            target=self._ejecutar_cuarentena,
            args=(archivos_a_eliminar,),
            daemon=True,
        )
        thread.start()
    
    def _ejecutar_cuarentena(self, archivos: List[dict]):
        """Ejecuta el movimiento reversible fuera del hilo de Tk."""
        movidos, errores, sesion = self.gestor_cuarentena.mover(archivos)
        mensaje = f"Movidos a cuarentena: {movidos} archivo(s)"
        if errores:
            mensaje += f"\n\nErrores ({len(errores)}):\n" + "\n".join(errores[:5])
        if sesion:
            mensaje += f"\n\nSesión: {sesion.name}"
        self.after(0, lambda: messagebox.showinfo("Cuarentena", mensaje))

    def _restaurar_ultima_cuarentena(self):
        if not messagebox.askyesno("Restaurar", "¿Restaurar los archivos de la última sesión?"):
            return
        restaurados, errores = self.gestor_cuarentena.restaurar_ultima()
        mensaje = f"Restaurados: {restaurados} archivo(s)"
        if errores:
            mensaje += f"\n\nErrores ({len(errores)}):\n" + "\n".join(errores[:5])
        messagebox.showinfo("Cuarentena", mensaje)

    def _gestionar_cuarentena(self):
        sesiones = self.gestor_cuarentena.sesiones()
        if not sesiones:
            messagebox.showinfo("Cuarentena", "No hay sesiones de cuarentena.")
            return
        dialogo = tk.Toplevel(self)
        dialogo.title("Gestionar cuarentena")
        dialogo.geometry("760x500")
        dialogo.transient(self)
        tk.Label(dialogo, text="Sesiones de cuarentena:").pack(anchor="w", padx=12, pady=(12, 4))
        lista_sesiones = tk.Listbox(dialogo, height=7, exportselection=False)
        lista_sesiones.pack(fill="x", padx=12, pady=4)
        for sesion in sesiones:
            lista_sesiones.insert("end", sesion.name)

        tk.Label(dialogo, text="Archivos de la sesión seleccionada:").pack(anchor="w", padx=12, pady=(10, 4))
        lista_archivos = tk.Listbox(dialogo, selectmode="extended", exportselection=False)
        lista_archivos.pack(fill="both", expand=True, padx=12, pady=4)

        def cargar_archivos(_event=None):
            lista_archivos.delete(0, "end")
            seleccion = lista_sesiones.curselection()
            if not seleccion:
                return
            for item in self.gestor_cuarentena.archivos_sesion(sesiones[seleccion[0]].name):
                lista_archivos.insert("end", item.get("original", "sin ruta"))

        lista_sesiones.bind("<<ListboxSelect>>", cargar_archivos)
        lista_sesiones.selection_set(0)
        cargar_archivos()

        acciones = tk.Frame(dialogo)
        acciones.pack(fill="x", padx=12, pady=10)

        def restaurar_seleccionados():
            seleccion_sesion = lista_sesiones.curselection()
            if not seleccion_sesion:
                return
            indices = list(lista_archivos.curselection())
            if not indices:
                messagebox.showwarning("Cuarentena", "Selecciona al menos un archivo.", parent=dialogo)
                return
            restaurados, errores = self.gestor_cuarentena.restaurar(
                sesiones[seleccion_sesion[0]].name, indices
            )
            self._mostrar_resultado_cuarentena(dialogo, restaurados, errores)
            cargar_archivos()

        def eliminar_sesion():
            seleccion = lista_sesiones.curselection()
            if not seleccion:
                return
            nombre = sesiones[seleccion[0]].name
            if not messagebox.askyesno(
                "Eliminar cuarentena", f"¿Eliminar definitivamente la sesión {nombre}?",
                parent=dialogo,
            ):
                return
            self.gestor_cuarentena.eliminar_sesion(nombre)
            dialogo.destroy()

        tk.Button(acciones, text="Restaurar seleccionados", command=restaurar_seleccionados,
                  bg=COLORES["acento"], fg="white", relief="flat").pack(side="left", padx=4)
        tk.Button(acciones, text="Eliminar sesión definitivamente", command=eliminar_sesion,
                  bg=COLORES["peligro"], fg="white", relief="flat").pack(side="left", padx=4)
        tk.Button(acciones, text="Cerrar", command=dialogo.destroy, relief="flat").pack(side="right", padx=4)

    @staticmethod
    def _mostrar_resultado_cuarentena(parent, restaurados, errores):
        mensaje = f"Restaurados: {restaurados} archivo(s)"
        if errores:
            mensaje += f"\n\nErrores ({len(errores)}):\n" + "\n".join(errores[:5])
        messagebox.showinfo("Cuarentena", mensaje, parent=parent)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = VentanaAvanzada()
    app.mainloop()
