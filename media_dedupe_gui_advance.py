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
import os
import shutil
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageTk

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
        if ruta_local and ruta_local.startswith("/") and os.path.exists(ruta_local):
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
        self.checkbox_estados[(idx_grupo, idx_archivo)] = var_check
        
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
            command=lambda v: self.callback_filtro(int(v)) if self.callback_filtro else None,
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
            text="🗑️  Eliminar Seleccionadas",
            font=("Segoe UI", 10),
            bg=COLORES["peligro"],
            fg="white",
            command=self.callback_eliminar,
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=4)


# ─────────────────────────────────────────────────────────────────────────────
# VENTANA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

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
        
        # Panel superior: vista previa
        self.panel_vista_previa = PanelVistaPrevia(self)
        self.panel_vista_previa.pack(fill="x", padx=8, pady=8)
        
        # Panel central: tabla
        self.panel_resultados = PanelResultados(
            self,
            callback_fila_seleccionada=self._fila_seleccionada,
        )
        self.panel_resultados.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        # Panel inferior: control
        self.panel_control = PanelControl(
            self,
            callback_filtro=self._aplicar_filtro,
            callback_seleccionar_filtrados=self._seleccionar_filtrados,
            callback_eliminar=self._eliminar_seleccionadas,
        )
        self.panel_control.pack(fill="x", padx=8, pady=(0, 8))
    
    def _abrir_reporte(self):
        """Abre un diálogo para seleccionar un archivo JSON de reporte."""
        archivo = filedialog.askopenfilename(
            title="Abrir reporte JSON",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        
        if archivo:
            self._cargar_reporte_json(archivo)
    
    def _cargar_reporte_json(self, ruta: str):
        """Carga un archivo JSON de reporte."""
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
            
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
    
    def _aplicar_filtro(self, umbral: int):
        """Filtra los grupos según el umbral de similitud."""
        self.datos_filtrados = [
            g for g in self.datos_originales
            if g.get("score", 100) >= umbral
        ]
        
        self.panel_resultados.cargar_datos(self.datos_filtrados)
    
    def _seleccionar_filtrados(self):
        """Selecciona todos los archivos NO-MEJORES de los grupos filtrados."""
        for idx_grupo, grupo in enumerate(self.datos_filtrados):
            archivos = grupo.get("files", [])
            # El primero es el mejor, los demás se marcan
            for idx_archivo in range(1, len(archivos)):
                key = (idx_grupo, idx_archivo)
                if key in self.panel_resultados.checkbox_estados:
                    self.panel_resultados.checkbox_estados[key].set(True)
    
    def _eliminar_seleccionadas(self):
        """Elimina los archivos seleccionados."""
        seleccionadas = [
            (idx_grupo, idx_archivo)
            for (idx_grupo, idx_archivo), var in self.panel_resultados.checkbox_estados.items()
            if var.get()
        ]
        
        if not seleccionadas:
            messagebox.showwarning("Advertencia", "No hay archivos seleccionados.")
            return
        
        # Confirmación
        cantidad = len(seleccionadas)
        if not messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar {cantidad} archivo(s)?\n\nEsta acción no se puede deshacer.",
        ):
            return
        
        # Agrupar por grupo y archivo
        archivos_a_eliminar = []
        for idx_grupo, idx_archivo in seleccionadas:
            if idx_grupo < len(self.datos_filtrados):
                grupo = self.datos_filtrados[idx_grupo]
                archivos = grupo.get("files", [])
                if idx_archivo < len(archivos):
                    archivo = archivos[idx_archivo]
                    archivos_a_eliminar.append(archivo)
        
        # Ejecutar eliminación en thread
        thread = threading.Thread(
            target=self._ejecutar_eliminación,
            args=(archivos_a_eliminar,),
        )
        thread.start()
    
    def _ejecutar_eliminación(self, archivos: List[dict]):
        """Ejecuta la eliminación de archivos."""
        eliminados = 0
        errores = []
        
        for archivo in archivos:
            ruta = archivo.get("path")
            if not ruta:
                continue
            
            # Validar que sea una ruta local
            if not os.path.exists(ruta):
                errores.append(f"No existe: {ruta}")
                continue
            
            try:
                os.remove(ruta)
                eliminados += 1
            except Exception as e:
                errores.append(f"{ruta}: {e}")
        
        # Mostrar resultado
        mensaje = f"✓ Eliminados: {eliminados} archivo(s)"
        if errores:
            mensaje += f"\n\n⚠️  Errores ({len(errores)}):\n" + "\n".join(errores[:5])
        
        messagebox.showinfo("Resultado", mensaje)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = VentanaAvanzada()
    app.mainloop()
