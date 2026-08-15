#!/usr/bin/env python3
"""
media_dedupe_gui.py — Interfaz gráfica para Media Dedupe.

GUI en Tkinter que ejecuta los escaneos del CLI (media_dedupe.py) con:
  - Selección visual de orígenes (Google Drive, OneDrive, Google Photos,
    WhatsApp, Google Takeout, carpeta local arbitraria)
  - Botones de autenticación
  - Logs en vivo del proceso
  - Resultados con comparación lado a lado de metadatos
  - Selección y eliminación segura de duplicados

Uso:
  python media_dedupe_gui.py
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Directorio del proyecto (donde está media_dedupe.py)
PROJECT_DIR = Path(__file__).parent.resolve()

# Sources que permiten eliminación (archivos locales)
DELETABLE_SOURCES = {
    "local_folder", "whatsapp_local",
    "google_photos_takeout", "google_drive_takeout", "youtube_takeout",
    "google_chat_takeout", "hangouts_takeout", "google_keep_takeout",
    "blogger_takeout", "google_takeout_other", "google_takeout",
}

# Colores y estilos
BG_COLOR = "#f5f5f5"
CARD_BG = "#ffffff"
ACCENT = "#1a73e8"
ACCENT_HOVER = "#1557b0"
DANGER = "#d93025"
SUCCESS = "#1e8e3e"
WARNING = "#f9ab00"
TEXT_COLOR = "#333333"
MUTED = "#666666"
CARD_BORDER = "#dadce0"

# Etiquetas legibles para cada source
SOURCE_LABELS = {
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
    "google_takeout_other": "Google Takeout (otros)",
    "google_takeout": "Google Takeout",
    "local_folder": "Carpeta local",
}


class MediaDedupeGUI:
    """Interfaz gráfica principal."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Media Dedupe — Detector de Duplicados Multi-origen")
        self.root.geometry("1100x780")
        self.root.minsize(900, 650)
        self.root.configure(bg=BG_COLOR)

        # Estado
        self.scan_process = None
        self.log_queue: queue.Queue = queue.Queue()
        self.report_base = None
        self.scan_data = None  # JSON completo del último reporte
        self.local_folders = []  # lista de carpetas locales añadidas

        # Variables de Tkinter
        self.var_drive = tk.BooleanVar(value=False)
        self.var_onedrive = tk.BooleanVar(value=False)
        self.var_photos_api = tk.BooleanVar(value=False)
        self.var_whatsapp = tk.BooleanVar(value=False)
        self.var_takeout = tk.BooleanVar(value=False)
        self.var_local_folder = tk.BooleanVar(value=False)

        self.var_whatsapp_folder = tk.StringVar()
        self.var_takeout_folder = tk.StringVar()
        self.var_local_folder_path = tk.StringVar()
        self.var_photos_mode = tk.StringVar(value="app-created")
        self.var_hash_mode = tk.StringVar(value="full")
        self.var_skip_similar = tk.BooleanVar(value=False)
        self.var_image_threshold = tk.StringVar(value="5")
        self.var_video_threshold = tk.StringVar(value="0.85")
        self.var_report_name = tk.StringVar(value="reporte_duplicados")

        # Referencias para miniaturas (evitar garbage collection)
        self._photo_refs = {}

        self._build_ui()
        self._poll_log_queue()

    # ─── Construcción de la UI ──────────────────────────────────────────

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        title = tk.Label(
            main_frame, text="Media Dedupe",
            font=("Segoe UI", 18, "bold"),
            bg=BG_COLOR, fg=ACCENT,
        )
        title.pack(anchor="w", pady=(0, 2))

        subtitle = tk.Label(
            main_frame,
            text="Detector de duplicados y casi-duplicados multi-origen",
            font=("Segoe UI", 10),
            bg=BG_COLOR, fg=MUTED,
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True)

        config_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(config_frame, text="  Configuracion  ")
        self._build_config_tab(config_frame)

        results_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(results_frame, text="  Resultados  ")
        self._build_results_tab(results_frame)

        logs_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(logs_frame, text="  Logs  ")
        self._build_logs_tab(logs_frame)

        quarantine_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(quarantine_frame, text="  Cuarentena  ")
        self._build_quarantine_tab(quarantine_frame)

        self.notebook = notebook

    def _build_config_tab(self, parent):
        canvas = tk.Canvas(parent, bg=BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_COLOR)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side="right", fill="y", pady=8)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Orígenes Cloud ──
        self._section_label(scroll_frame, "Origenes Cloud", 0)

        cloud_frame = tk.LabelFrame(
            scroll_frame, text=" Cloud ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        cloud_frame.pack(fill="x", padx=10, pady=(4, 8))

        # Google Drive
        row = tk.Frame(cloud_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=2)
        tk.Checkbutton(row, text="Google Drive", variable=self.var_drive,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Button(row, text="Autenticar", width=10,
                  command=lambda: self._run_auth("google-drive")).pack(side="right")

        # OneDrive
        row = tk.Frame(cloud_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=2)
        tk.Checkbutton(row, text="OneDrive", variable=self.var_onedrive,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Button(row, text="Autenticar", width=10,
                  command=lambda: self._run_auth("onedrive")).pack(side="right")

        # Google Photos API
        row = tk.Frame(cloud_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=2)
        tk.Checkbutton(row, text="Google Photos (API)", variable=self.var_photos_api,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Label(row, text="Modo:", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        ttk.Combobox(row, textvariable=self.var_photos_mode,
                     values=["app-created", "picker"], width=12, state="readonly").pack(side="left")
        tk.Button(row, text="Autenticar", width=10,
                  command=lambda: self._run_auth("google-photos")).pack(side="right")

        # ── Carpetas Locales ──
        self._section_label(scroll_frame, "Carpetas Locales", 16)

        local_frame = tk.LabelFrame(
            scroll_frame, text=" Carpetas Locales ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        local_frame.pack(fill="x", padx=10, pady=(4, 8))

        # WhatsApp
        row = tk.Frame(local_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)
        tk.Checkbutton(row, text="WhatsApp", variable=self.var_whatsapp,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(row, textvariable=self.var_whatsapp_folder, width=45,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), fill="x", expand=True)
        tk.Button(row, text="Buscar...", command=self._browse_whatsapp).pack(side="right")

        # Google Takeout
        row = tk.Frame(local_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)
        tk.Checkbutton(row, text="Google Takeout", variable=self.var_takeout,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(row, textvariable=self.var_takeout_folder, width=45,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), fill="x", expand=True)
        tk.Button(row, text="Buscar...", command=self._browse_takeout).pack(side="right")

        tk.Label(local_frame, text="Takeout escanea todos los productos de Google (Photos, Drive, YouTube, etc.)",
                 bg=BG_COLOR, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        # Carpeta local arbitraria
        row = tk.Frame(local_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)
        tk.Checkbutton(row, text="Carpeta local", variable=self.var_local_folder,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(row, textvariable=self.var_local_folder_path, width=45,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), fill="x", expand=True)
        tk.Button(row, text="Buscar...", command=self._browse_local_folder).pack(side="right")

        tk.Label(local_frame, text="Selecciona cualquier carpeta del explorador para buscar duplicados",
                 bg=BG_COLOR, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        # ── Opciones ──
        self._section_label(scroll_frame, "Opciones de Escaneo", 16)

        opts_frame = tk.LabelFrame(
            scroll_frame, text=" Opciones ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        opts_frame.pack(fill="x", padx=10, pady=(4, 8))

        row = tk.Frame(opts_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Modo de hash:", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left")
        ttk.Radiobutton(row, text="Completo (descargar + MD5/SHA-256)",
                        variable=self.var_hash_mode, value="full").pack(side="left", padx=8)
        ttk.Radiobutton(row, text="Metadatos (rapido)",
                        variable=self.var_hash_mode, value="metadata").pack(side="left")

        row = tk.Frame(opts_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Umbral imagenes (Hamming):", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        tk.Spinbox(row, from_=0, to=20, textvariable=self.var_image_threshold,
                   width=5, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(row, text="   Umbral videos (ratio):", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(20, 4))
        tk.Spinbox(row, from_=0.50, to=1.00, increment=0.05,
                   textvariable=self.var_video_threshold, width=6,
                   font=("Segoe UI", 9), format="%.2f").pack(side="left")

        row = tk.Frame(opts_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)
        tk.Checkbutton(row, text="Solo duplicados exactos (saltar casi-duplicados)",
                       variable=self.var_skip_similar, bg=BG_COLOR,
                       font=("Segoe UI", 9)).pack(side="left")

        row = tk.Frame(opts_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Nombre del reporte:", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(row, textvariable=self.var_report_name, width=30,
                 font=("Segoe UI", 9)).pack(side="left", padx=8)

        # ── Botones de acción ──
        btn_frame = tk.Frame(scroll_frame, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=10, pady=(12, 8))

        self.btn_scan = tk.Button(
            btn_frame, text="Iniciar escaneo", font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            activeforeground="white", relief="flat", padx=20, pady=8,
            cursor="hand2", command=self._start_scan,
        )
        self.btn_scan.pack(side="left")

        self.btn_stop = tk.Button(
            btn_frame, text="Detener", font=("Segoe UI", 10),
            bg=DANGER, fg="white", relief="flat", padx=12, pady=8,
            cursor="hand2", command=self._stop_scan, state="disabled",
        )
        self.btn_stop.pack(side="left", padx=8)

        self.btn_picker_confirm = tk.Button(
            btn_frame, text="Ya seleccione las fotos", font=("Segoe UI", 10),
            bg=WARNING, fg="white", relief="flat", padx=12, pady=8,
            cursor="hand2", command=self._confirm_picker, state="disabled",
        )
        self.btn_picker_confirm.pack(side="left", padx=8)

        self.progress = ttk.Progressbar(btn_frame, mode="indeterminate", length=200)
        self.progress.pack(side="right")

    def _build_results_tab(self, parent):
        """Pestaña de resultados con comparacion lado a lado y eliminacion."""
        # Panel superior: arbol de grupos + resumen
        top_panel = tk.Frame(parent, bg=BG_COLOR)
        top_panel.pack(fill="x", padx=8, pady=(8, 4))

        # Resumen
        self.lbl_summary = tk.Label(
            top_panel, text="Ejecuta un escaneo para ver resultados.",
            bg=BG_COLOR, fg=MUTED, font=("Segoe UI", 10), justify="left",
        )
        self.lbl_summary.pack(anchor="w")

        # Botones de reportes
        reports_row = tk.Frame(top_panel, bg=BG_COLOR)
        reports_row.pack(fill="x", pady=(4, 4))

        self.btn_open_html = tk.Button(
            reports_row, text="Abrir HTML", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=10, pady=4,
            cursor="hand2", command=lambda: self._open_report("html"),
            state="disabled",
        )
        self.btn_open_html.pack(side="left", padx=(0, 4))

        self.btn_open_csv = tk.Button(
            reports_row, text="Abrir CSV", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=10, pady=4,
            cursor="hand2", command=lambda: self._open_report("csv"),
            state="disabled",
        )
        self.btn_open_csv.pack(side="left", padx=4)

        self.btn_open_json = tk.Button(
            reports_row, text="Abrir JSON", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=10, pady=4,
            cursor="hand2", command=lambda: self._open_report("json"),
            state="disabled",
        )
        self.btn_open_json.pack(side="left", padx=4)

        # Arbol de grupos
        tree_frame = tk.Frame(parent, bg=BG_COLOR)
        tree_frame.pack(fill="x", padx=8, pady=(0, 4))

        tk.Label(tree_frame, text="Grupos de duplicados encontrados:",
                 bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 9, "bold")).pack(anchor="w")

        columns = ("tipo", "score", "archivos", "recuperable")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=6)
        self.tree.heading("#0", text="Grupo")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("score", text="Score")
        self.tree.heading("archivos", text="N. archivos")
        self.tree.heading("recuperable", text="Recuperable")

        self.tree.column("#0", width=300)
        self.tree.column("tipo", width=120)
        self.tree.column("score", width=60)
        self.tree.column("archivos", width=70)
        self.tree.column("recuperable", width=100)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="x", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_group_select)

        self.tree.tag_configure("exact", background="#fce8e6")
        self.tree.tag_configure("image_similar", background="#fef7e0")
        self.tree.tag_configure("video_similar", background="#e6f4ea")

        # Panel inferior: comparacion lado a lado
        detail_label = tk.Label(parent, text="Comparacion de archivos:",
                                bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 9, "bold"))
        detail_label.pack(anchor="w", padx=8, pady=(8, 4))

        # Canvas con scroll horizontal para las tarjetas
        self.cards_canvas = tk.Canvas(parent, bg=BG_COLOR, highlightthickness=0, height=380)
        cards_scroll = ttk.Scrollbar(parent, orient="horizontal", command=self.cards_canvas.xview)
        self.cards_inner = tk.Frame(self.cards_canvas, bg=BG_COLOR)

        self.cards_inner.bind(
            "<Configure>",
            lambda e: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))
        )
        self.cards_canvas.create_window((0, 0), window=self.cards_inner, anchor="nw")
        self.cards_canvas.configure(xscrollcommand=cards_scroll.set)

        self.cards_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        cards_scroll.pack(fill="x", padx=8, pady=(0, 4))

        # Boton de eliminacion
        delete_frame = tk.Frame(parent, bg=BG_COLOR)
        delete_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.btn_delete = tk.Button(
            delete_frame, text="Mover seleccionados a cuarentena",
            font=("Segoe UI", 10, "bold"),
            bg=DANGER, fg="white", relief="flat", padx=16, pady=6,
            cursor="hand2", command=self._delete_selected, state="disabled",
        )
        self.btn_delete.pack(side="left")

        self.lbl_delete_info = tk.Label(
            delete_frame, text="",
            bg=BG_COLOR, fg=MUTED, font=("Segoe UI", 9),
        )
        self.lbl_delete_info.pack(side="left", padx=12)

        # Estado interno de checkboxes de eliminacion
        self._delete_vars = {}  # file_key -> BooleanVar

    def _build_logs_tab(self, parent):
        self.log_text = tk.Text(
            parent, wrap="word", font=("Consolas", 9),
            bg="#1e1e1e", fg="#cccccc", insertbackground="white",
            state="disabled", relief="flat",
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        log_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y", pady=8)

        btn_clear = tk.Button(
            parent, text="Limpiar logs", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=4,
            command=self._clear_logs,
        )
        btn_clear.pack(side="bottom", anchor="e", padx=8, pady=(0, 4))

    def _build_quarantine_tab(self, parent):
        """Pestaña para ver y restaurar archivos en cuarentena."""
        # Panel superior: lista de sesiones de cuarentena
        top = tk.Frame(parent, bg=BG_COLOR)
        top.pack(fill="x", padx=8, pady=8)

        tk.Label(top, text="Sesiones de cuarentena",
                 font=("Segoe UI", 11, "bold"), bg=BG_COLOR, fg=ACCENT).pack(anchor="w")

        tk.Label(top, text="Los archivos movidos a cuarentena se pueden restaurar a su ubicacion original.",
                 font=("Segoe UI", 9), bg=BG_COLOR, fg=MUTED).pack(anchor="w", pady=(2, 0))

        # Boton actualizar
        btn_refresh = tk.Button(
            top, text="Actualizar lista", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=10, pady=4,
            cursor="hand2", command=self._load_quarantine_sessions,
        )
        btn_refresh.pack(anchor="w", pady=(8, 0))

        # Arbol de sesiones
        sessions_frame = tk.Frame(parent, bg=BG_COLOR)
        sessions_frame.pack(fill="x", padx=8, pady=(4, 4))

        self.quarantine_tree = ttk.Treeview(
            sessions_frame, columns=("files", "date", "size"),
            show="tree headings", height=6,
        )
        self.quarantine_tree.heading("#0", text="Sesion / Archivo")
        self.quarantine_tree.heading("files", text="N. archivos")
        self.quarantine_tree.heading("date", text="Fecha")
        self.quarantine_tree.heading("size", text="Tamano")
        self.quarantine_tree.column("#0", width=350)
        self.quarantine_tree.column("files", width=80)
        self.quarantine_tree.column("date", width=140)
        self.quarantine_tree.column("size", width=80)

        q_scroll = ttk.Scrollbar(sessions_frame, orient="vertical", command=self.quarantine_tree.yview)
        self.quarantine_tree.configure(yscrollcommand=q_scroll.set)
        self.quarantine_tree.pack(side="left", fill="both", expand=True)
        q_scroll.pack(side="right", fill="y")

        self.quarantine_tree.bind("<<TreeviewSelect>>", self._on_quarantine_session_select)

        # Panel de detalle del archivo seleccionado
        detail_frame = tk.LabelFrame(
            parent, text=" Detalle del archivo ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        detail_frame.pack(fill="x", padx=8, pady=(4, 4))

        self.quarantine_detail = tk.Label(
            detail_frame, text="Selecciona un archivo para ver su detalle.",
            bg=BG_COLOR, fg=MUTED, font=("Segoe UI", 9), justify="left", anchor="w",
        )
        self.quarantine_detail.pack(anchor="w")

        # Botones de accion
        actions_frame = tk.Frame(parent, bg=BG_COLOR)
        actions_frame.pack(fill="x", padx=8, pady=(4, 8))

        self.btn_restore_selected = tk.Button(
            actions_frame, text="Restaurar archivo seleccionado",
            font=("Segoe UI", 10, "bold"),
            bg=SUCCESS, fg="white", relief="flat", padx=16, pady=6,
            cursor="hand2", command=self._restore_selected_file, state="disabled",
        )
        self.btn_restore_selected.pack(side="left")

        self.btn_restore_all = tk.Button(
            actions_frame, text="Restaurar toda la sesion",
            font=("Segoe UI", 10),
            bg="#e8f0fe", fg=ACCENT, relief="flat", padx=16, pady=6,
            cursor="hand2", command=self._restore_full_session, state="disabled",
        )
        self.btn_restore_all.pack(side="left", padx=8)

        self.btn_delete_session = tk.Button(
            actions_frame, text="Eliminar sesion definitivamente",
            font=("Segoe UI", 10),
            bg=DANGER, fg="white", relief="flat", padx=16, pady=6,
            cursor="hand2", command=self._delete_quarantine_session, state="disabled",
        )
        self.btn_delete_session.pack(side="left", padx=8)

        # Estado interno
        self._quarantine_data = {}  # session_id -> {registro, files}
        self._current_quarantine_selection = None  # (session_id, file_index)

        # Cargar sesiones al iniciar
        self.root.after(500, self._load_quarantine_sessions)

    # ─── Cuarentena: logica ─────────────────────────────────────────────

    def _get_quarantine_base_dir(self) -> str:
        return os.path.join(PROJECT_DIR, "_media_dedupe_eliminados")

    def _load_quarantine_sessions(self):
        """Carga las sesiones de cuarentena disponibles."""
        # Limpiar arbol
        for item in self.quarantine_tree.get_children():
            self.quarantine_tree.delete(item)
        self._quarantine_data = {}
        self._current_quarantine_selection = None
        self.quarantine_detail.config(text="Selecciona un archivo para ver su detalle.")
        self.btn_restore_selected.config(state="disabled")
        self.btn_restore_all.config(state="disabled")
        self.btn_delete_session.config(state="disabled")

        base_dir = self._get_quarantine_base_dir()
        if not os.path.isdir(base_dir):
            return

        sessions = sorted(os.listdir(base_dir), reverse=True)
        for session_id in sessions:
            session_path = os.path.join(base_dir, session_id)
            if not os.path.isdir(session_path):
                continue

            registro_path = os.path.join(session_path, "registro_eliminacion.json")
            if not os.path.exists(registro_path):
                continue

            try:
                with open(registro_path, "r", encoding="utf-8") as f:
                    registro = json.load(f)
            except Exception:
                continue

            moved = registro.get("moved", [])
            errors = registro.get("errors", [])
            timestamp = registro.get("timestamp", session_id)

            # Formatear fecha
            try:
                dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                date_str = dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                date_str = timestamp

            total_size = sum(
                os.path.getsize(m.get("quarantine_path", ""))
                if os.path.exists(m.get("quarantine_path", "")) else 0
                for m in moved
            )

            self._quarantine_data[session_id] = {
                "registro": registro,
                "session_path": session_path,
            }

            parent_id = self.quarantine_tree.insert(
                "", "end",
                text=f"Sesion {timestamp}",
                values=(len(moved), date_str, self._format_size(total_size)),
                tags=("session",),
            )
            self.quarantine_tree.tag_configure("session", font=("Segoe UI", 9, "bold"))

            for idx, m in enumerate(moved):
                name = m.get("name", "?")
                orig_path = m.get("original_path", "?")
                quar_path = m.get("quarantine_path", "?")
                exists = os.path.exists(quar_path)
                status = "" if exists else " (archivo no encontrado)"

                self.quarantine_tree.insert(
                    parent_id, "end",
                    text=f"{name}{status}",
                    values=("", "", self._format_size(
                        os.path.getsize(quar_path) if exists else 0
                    )),
                )

    def _on_quarantine_session_select(self, event):
        """Cuando se selecciona un item en el arbol de cuarentena."""
        selection = self.quarantine_tree.selection()
        if not selection:
            return

        item = self.quarantine_tree.item(selection[0])
        parent_id = self.quarantine_tree.parent(selection[0])

        # Si es un archivo (hijo de una sesion)
        if parent_id:
            # Obtener session_id del padre
            parent_item = self.quarantine_tree.item(parent_id)
            session_text = parent_item["text"]
            try:
                session_id = session_text.replace("Sesion ", "")
            except Exception:
                return

            if session_id not in self._quarantine_data:
                return

            # Obtener indice del archivo
            children = self.quarantine_tree.get_children(parent_id)
            file_idx = list(children).index(selection[0])

            registro = self._quarantine_data[session_id]["registro"]
            moved = registro.get("moved", [])

            if file_idx >= len(moved):
                return

            m = moved[file_idx]
            self._current_quarantine_selection = (session_id, file_idx)

            exists = os.path.exists(m.get("quarantine_path", ""))
            detail = (
                f"Archivo: {m.get('name', '?')}\n"
                f"Origen: {m.get('source', '?')}\n"
                f"Ruta original: {m.get('original_path', '?')}\n"
                f"Ruta cuarentena: {m.get('quarantine_path', '?')}\n"
                f"Estado: {'Disponible para restaurar' if exists else 'Archivo no encontrado'}"
            )

            # Verificar si la ruta original ya esta ocupada
            orig_path = m.get("original_path", "")
            if orig_path and os.path.exists(orig_path):
                detail += f"\nADVERTENCIA: Ya existe un archivo en la ruta original."

            self.quarantine_detail.config(text=detail, fg=TEXT_COLOR)
            self.btn_restore_selected.config(state="normal" if exists else "disabled")
            self.btn_restore_all.config(state="normal")
            self.btn_delete_session.config(state="normal")

        else:
            # Es una sesion (nodo padre)
            session_text = item["text"]
            try:
                session_id = session_text.replace("Sesion ", "")
            except Exception:
                return

            if session_id not in self._quarantine_data:
                return

            registro = self._quarantine_data[session_id]["registro"]
            moved = registro.get("moved", [])
            errors = registro.get("errors", [])

            detail = (
                f"Sesion: {session_id}\n"
                f"Archivos movidos: {len(moved)}\n"
                f"Errores: {len(errors)}\n"
                f"Carpeta: {self._quarantine_data[session_id]['session_path']}"
            )

            self.quarantine_detail.config(text=detail, fg=TEXT_COLOR)
            self.btn_restore_selected.config(state="disabled")
            self.btn_restore_all.config(state="normal")
            self.btn_delete_session.config(state="normal")

    def _restore_selected_file(self):
        """Restaura el archivo seleccionado a su ruta original."""
        if not self._current_quarantine_selection:
            return

        session_id, file_idx = self._current_quarantine_selection
        if session_id not in self._quarantine_data:
            return

        registro = self._quarantine_data[session_id]["registro"]
        moved = registro.get("moved", [])
        if file_idx >= len(moved):
            return

        m = moved[file_idx]
        quar_path = m.get("quarantine_path", "")
        orig_path = m.get("original_path", "")

        if not os.path.exists(quar_path):
            messagebox.showerror("Error", "El archivo no existe en la cuarentena.")
            return

        # Verificar conflicto
        conflict = os.path.exists(orig_path) if orig_path else False
        if conflict:
            result = messagebox.askyesno(
                "Conflicto",
                f"Ya existe un archivo en la ruta original:\n{orig_path}\n\n"
                f"Si continuas, se restaurara con un sufijo _restaurado.\n\nContinuar?"
            )
            if not result:
                return

        confirm = messagebox.askyesno(
            "Confirmar restauracion",
            f"Se restaurara:\n  {m.get('name', '?')}\n\n"
            f"De: {quar_path}\n"
            f"A: {orig_path}\n\nContinuar?"
        )
        if not confirm:
            return

        try:
            dest = orig_path
            if conflict:
                name, ext = os.path.splitext(orig_path)
                dest = f"{name}_restaurado{ext}"

            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(quar_path, dest)
            self._log(f">>> Restaurado: {m.get('name', '?')} -> {dest}")

            messagebox.showinfo("Restauracion completada",
                                f"Archivo restaurado a:\n{dest}")

            self._load_quarantine_sessions()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo restaurar el archivo:\n{e}")

    def _restore_full_session(self):
        """Restaura todos los archivos de una sesion de cuarentena."""
        selection = self.quarantine_tree.selection()
        if not selection:
            return

        item = self.quarantine_tree.item(selection[0])
        parent_id = self.quarantine_tree.parent(selection[0])

        # Obtener session_id
        if parent_id:
            parent_item = self.quarantine_tree.item(parent_id)
            session_text = parent_item["text"]
        else:
            session_text = item["text"]

        try:
            session_id = session_text.replace("Sesion ", "")
        except Exception:
            return

        if session_id not in self._quarantine_data:
            return

        registro = self._quarantine_data[session_id]["registro"]
        moved = registro.get("moved", [])

        available = [m for m in moved if os.path.exists(m.get("quarantine_path", ""))]
        if not available:
            messagebox.showinfo("Sin archivos", "No hay archivos disponibles para restaurar en esta sesion.")
            return

        # Construir texto de confirmacion
        msg = f"Se restauraran {len(available)} archivo(s) a sus ubicaciones originales:\n\n"
        for m in available:
            msg += f"  - {m.get('name', '?')}\n"
            msg += f"    -> {m.get('original_path', '?')}\n"

        conflicts = [m for m in available if os.path.exists(m.get("original_path", ""))]
        if conflicts:
            msg += f"\nADVERTENCIA: {len(conflicts)} archivo(s) tienen conflictos (ya existe un archivo en el destino).\n"
            msg += "Esos se restauraran con sufijo _restaurado."

        msg += "\nContinuar?"

        if not messagebox.askyesno("Confirmar restauracion completa", msg):
            return

        restored = 0
        errors = []
        for m in available:
            quar_path = m.get("quarantine_path", "")
            orig_path = m.get("original_path", "")
            try:
                dest = orig_path
                if os.path.exists(orig_path):
                    name, ext = os.path.splitext(orig_path)
                    dest = f"{name}_restaurado{ext}"

                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.move(quar_path, dest)
                restored += 1
                self._log(f">>> Restaurado: {m.get('name', '?')} -> {dest}")
            except Exception as e:
                errors.append((m.get("name", "?"), str(e)))

        result_msg = f"Se restauraron {restored} archivo(s) correctamente."
        if errors:
            result_msg += f"\n\n{len(errors)} archivo(s) no se pudieron restaurar."
        messagebox.showinfo("Restauracion completada", result_msg)

        self._load_quarantine_sessions()

    def _delete_quarantine_session(self):
        """Elimina definitivamente una sesion de cuarentena."""
        selection = self.quarantine_tree.selection()
        if not selection:
            return

        item = self.quarantine_tree.item(selection[0])
        parent_id = self.quarantine_tree.parent(selection[0])

        if parent_id:
            parent_item = self.quarantine_tree.item(parent_id)
            session_text = parent_item["text"]
        else:
            session_text = item["text"]

        try:
            session_id = session_text.replace("Sesion ", "")
        except Exception:
            return

        if session_id not in self._quarantine_data:
            return

        session_path = self._quarantine_data[session_id]["session_path"]
        registro = self._quarantine_data[session_id]["registro"]
        moved = registro.get("moved", [])

        # Contar archivos que se borrarian
        file_count = sum(1 for m in moved if os.path.exists(m.get("quarantine_path", "")))

        msg = (
            f"VAS A BORRAR DEFINITIVAMENTE {file_count} archivo(s) de la cuarentena.\n\n"
            f"Esta accion NO se puede deshacer.\n\n"
            f"Sesion: {session_id}\n"
            f"Carpeta: {session_path}\n\n"
            f"Continuar?"
        )

        if not messagebox.askyesno("Confirmar borrado definitivo", msg):
            return

        try:
            shutil.rmtree(session_path)
            self._log(f">>> Sesion de cuarentena eliminada: {session_id}")
            messagebox.showinfo("Sesion eliminada", "La sesion de cuarentena se ha eliminado definitivamente.")
            self._load_quarantine_sessions()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar la sesion:\n{e}")

    # ─── Helpers de UI ─────────────────────────────────────────────────

    def _section_label(self, parent, text, top_pad=0):
        tk.Label(parent, text=text, font=("Segoe UI", 11, "bold"),
                 bg=BG_COLOR, fg=ACCENT).pack(anchor="w", padx=10, pady=(top_pad, 0))

    def _browse_whatsapp(self):
        folder = filedialog.askdirectory(title="Selecciona la carpeta de WhatsApp Media")
        if folder:
            self.var_whatsapp_folder.set(folder)

    def _browse_takeout(self):
        folder = filedialog.askdirectory(title="Selecciona la carpeta de Google Takeout")
        if folder:
            self.var_takeout_folder.set(folder)

    def _browse_local_folder(self):
        folder = filedialog.askdirectory(title="Selecciona una carpeta para escanear")
        if folder:
            self.var_local_folder_path.set(folder)

    # ─── Autenticación ──────────────────────────────────────────────────

    def _run_auth(self, provider: str):
        cmd = [sys.executable, str(PROJECT_DIR / "media_dedupe.py"), "auth", provider]

        if provider == "google-photos":
            cmd += ["--photos-mode", self.var_photos_mode.get()]

        self._log(f">>> Autenticando {provider}...")

        def _run():
            try:
                proc = subprocess.Popen(
                    cmd, cwd=str(PROJECT_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                )
                for line in proc.stdout:
                    self.log_queue.put(line.rstrip("\n"))
                proc.wait()
                if proc.returncode == 0:
                    self._log(f">>> {provider}: autenticacion exitosa.")
                else:
                    self._log(f">>> {provider}: error (codigo {proc.returncode}).")
            except Exception as e:
                self._log(f">>> Error: {e}")

        threading.Thread(target=_run, daemon=True).start()

    # ─── Escaneo ────────────────────────────────────────────────────────

    def _start_scan(self):
        cmd = [sys.executable, str(PROJECT_DIR / "media_dedupe.py"), "scan"]

        sources = []
        if self.var_drive.get():
            sources.append("google-drive")
        if self.var_onedrive.get():
            sources.append("onedrive")
        if self.var_photos_api.get():
            sources.append("google-photos")
            cmd += ["--photos-mode", self.var_photos_mode.get()]

        for s in sources:
            cmd += ["--source", s]

        if self.var_whatsapp.get() and self.var_whatsapp_folder.get():
            cmd += ["--whatsapp-folder", self.var_whatsapp_folder.get()]

        if self.var_takeout.get() and self.var_takeout_folder.get():
            cmd += ["--google-takeout-folder", self.var_takeout_folder.get()]

        if self.var_local_folder.get() and self.var_local_folder_path.get():
            cmd += ["--local-folder", self.var_local_folder_path.get()]

        has_any = (sources or
                   (self.var_whatsapp.get() and self.var_whatsapp_folder.get()) or
                   (self.var_takeout.get() and self.var_takeout_folder.get()) or
                   (self.var_local_folder.get() and self.var_local_folder_path.get()))

        if not has_any:
            messagebox.showwarning("Sin origenes", "Selecciona al menos un origen para escanear.")
            return

        cmd += ["--hash-mode", self.var_hash_mode.get()]
        cmd += ["--image-threshold", self.var_image_threshold.get()]
        cmd += ["--video-threshold", self.var_video_threshold.get()]

        if self.var_skip_similar.get():
            cmd += ["--skip-similar"]

        self.report_base = self.var_report_name.get() or "reporte_duplicados"
        cmd += ["--report", self.report_base]

        # Limpiar UI
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._clear_cards()
        self._delete_vars = {}
        self.lbl_summary.config(text="Escaneando...", fg=WARNING)

        self.btn_scan.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_delete.config(state="disabled")

        if self.var_photos_api.get() and self.var_photos_mode.get() == "picker":
            self.btn_picker_confirm.config(state="normal")

        self.progress.start(15)
        self.notebook.select(2)

        self._log(f">>> Comando: {' '.join(cmd)}")
        self._log(">>> Iniciando escaneo...")

        def _run():
            try:
                self.scan_process = subprocess.Popen(
                    cmd, cwd=str(PROJECT_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True, bufsize=1,
                )
                for line in self.scan_process.stdout:
                    self.log_queue.put(line.rstrip("\n"))
                self.scan_process.wait()
                rc = self.scan_process.returncode
                self.scan_process = None

                if rc == 0:
                    self.log_queue.put(">>> Escaneo completado.")
                    self.root.after(100, self._load_results)
                else:
                    self.log_queue.put(f">>> Escaneo terminado con error (codigo {rc}).")
                    self.root.after(100, lambda: self._scan_finished(False))
            except Exception as e:
                self.log_queue.put(f">>> Error: {e}")
                self.root.after(100, lambda: self._scan_finished(False))

        threading.Thread(target=_run, daemon=True).start()

    def _stop_scan(self):
        if self.scan_process and self.scan_process.poll() is None:
            self.scan_process.terminate()
            self._log(">>> Deteniendo escaneo...")
            self._scan_finished(False)

    def _confirm_picker(self):
        if self.scan_process and self.scan_process.poll() is None:
            try:
                self.scan_process.stdin.write("\n")
                self.scan_process.stdin.flush()
                self._log(">>> Confirmacion enviada al selector de Google Photos.")
                self.btn_picker_confirm.config(state="disabled")
            except Exception:
                pass

    def _scan_finished(self, success=True):
        self.btn_scan.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_picker_confirm.config(state="disabled")
        self.progress.stop()

        if not success:
            self.lbl_summary.config(text="El escaneo no se completo correctamente.", fg=DANGER)

    # ─── Resultados ─────────────────────────────────────────────────────

    def _load_results(self):
        self._scan_finished(True)

        report_path = f"{self.report_base}.json"
        if not os.path.exists(report_path):
            report_path = str(PROJECT_DIR / report_path)
            if not os.path.exists(report_path):
                self.lbl_summary.config(text="No se encontro el reporte JSON.", fg=DANGER)
                return

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                self.scan_data = json.load(f)
        except Exception as e:
            self.lbl_summary.config(text=f"Error leyendo reporte: {e}", fg=DANGER)
            return

        groups = self.scan_data.get("groups", [])
        total_recoverable = self.scan_data.get("total_recoverable_size", 0)

        type_labels = {
            "exact": "Duplicado Exacto",
            "image_similar": "Imagenes Similares",
            "video_similar": "Videos Similares",
        }

        by_type = {}
        for g in groups:
            by_type[g["group_type"]] = by_type.get(g["group_type"], 0) + 1

        summary_lines = [f"Grupos encontrados: {len(groups)}"]
        for gtype, count in by_type.items():
            summary_lines.append(f"  - {type_labels.get(gtype, gtype)}: {count} grupos")
        summary_lines.append(f"Espacio recuperable: {self._format_size(total_recoverable)}")
        self.lbl_summary.config(text="\n".join(summary_lines), fg=TEXT_COLOR)

        # Llenar arbol
        for idx, group in enumerate(groups, 1):
            gtype = group["group_type"]
            label = type_labels.get(gtype, gtype)
            score = group["score"]
            num_files = len(group["files"])
            recoverable = self._format_size(group["recoverable_size"])

            self.tree.insert(
                "", "end",
                text=f"Grupo #{idx} - {label}",
                values=(label, f"{score:.1f}", num_files, recoverable),
                tags=(gtype,),
            )

        self.btn_open_html.config(state="normal")
        self.btn_open_csv.config(state="normal")
        self.btn_open_json.config(state="normal")

        self.notebook.select(1)

    def _on_group_select(self, event):
        """Cuando se selecciona un grupo en el arbol, mostrar las tarjetas."""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        # Verificar que es un grupo de nivel superior (no un hijo)
        parent = self.tree.parent(selection[0])
        if parent:
            return

        group_text = item["text"]
        # Extraer indice del grupo
        try:
            idx = int(group_text.split("#")[1].split(" ")[0]) - 1
        except (IndexError, ValueError):
            return

        if not self.scan_data or idx >= len(self.scan_data["groups"]):
            return

        group = self.scan_data["groups"][idx]
        self._show_file_cards(group, idx)

    def _show_file_cards(self, group: dict, group_idx: int):
        """Muestra tarjetas lado a lado con todos los metadatos de cada archivo."""
        self._clear_cards()
        self._delete_vars = {}

        files = group.get("files", [])

        for file_idx, f in enumerate(files):
            self._create_file_card(f, group_idx, file_idx, len(files))

        # Habilitar boton de eliminacion si hay archivos eliminables
        has_deletable = any(
            f.get("source", "") in DELETABLE_SOURCES and f.get("path")
            for f in files
        )
        if has_deletable:
            self.btn_delete.config(state="normal")
            self.lbl_delete_info.config(
                text="Los archivos se mueven a _media_dedupe_eliminados/ (no se borran permanentemente)"
            )
        else:
            self.btn_delete.config(state="disabled")
            self.lbl_delete_info.config(
                text="Estos archivos estan en la nube: no se pueden eliminar desde la GUI"
            )

    def _create_file_card(self, f: dict, group_idx: int, file_idx: int, total: int):
        """Crea una tarjeta con todos los metadatos de un archivo."""
        card = tk.Frame(
            self.cards_inner, bg=CARD_BG, relief="solid",
            borderwidth=1, highlightbackground=CARD_BORDER,
            highlightthickness=1,
        )
        card.pack(side="left", padx=6, pady=4, fill="y", anchor="n")

        # Cabecera de la tarjeta
        header = tk.Frame(card, bg=CARD_BG)
        header.pack(fill="x", padx=8, pady=(8, 4))

        source = f.get("source", "?")
        source_label = SOURCE_LABELS.get(source, source)
        is_deletable = source in DELETABLE_SOURCES and f.get("path")

        tk.Label(
            header, text=f"Archivo {file_idx + 1} de {total}",
            font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=ACCENT,
        ).pack(anchor="w")

        tk.Label(
            header, text=f.get("name", "?"),
            font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_COLOR,
            wraplength=280, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            header, text=source_label,
            font=("Segoe UI", 9), bg=CARD_BG, fg=MUTED,
        ).pack(anchor="w")

        # Miniatura si es imagen local
        file_path = f.get("path", "")
        if file_path and os.path.exists(file_path) and self._is_image_file(file_path):
            try:
                from PIL import Image as PILImage, ImageTk
                pil_img = PILImage.open(file_path)
                pil_img.thumbnail((280, 200))
                photo = ImageTk.PhotoImage(pil_img)
                self._photo_refs[f"{group_idx}_{file_idx}"] = photo

                thumb_label = tk.Label(card, image=photo, bg=CARD_BG)
                thumb_label.pack(padx=8, pady=4)
            except Exception:
                tk.Label(card, text="[vista previa no disponible]",
                         bg=CARD_BG, fg=MUTED, font=("Segoe UI", 8)).pack(pady=4)

        # Tabla de metadatos
        meta_frame = tk.Frame(card, bg=CARD_BG)
        meta_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        row = 0

        # Informacion basica del archivo
        self._add_meta_row(meta_frame, row, "Ruta", f.get("path", "N/A")); row += 1
        self._add_meta_row(meta_frame, row, "Tamano", self._format_size(f.get("size", 0))); row += 1
        self._add_meta_row(meta_frame, row, "Tipo MIME", f.get("mime_type", "N/A")); row += 1

        # Hashes
        md5 = f.get("md5")
        self._add_meta_row(meta_frame, row, "MD5", md5[:24] + "..." if md5 and len(md5) > 24 else md5 or "N/A"); row += 1
        sha = f.get("sha256")
        self._add_meta_row(meta_frame, row, "SHA-256", sha[:24] + "..." if sha and len(sha) > 24 else sha or "N/A"); row += 1

        # Fecha de modificacion
        import datetime as dt
        mod_time = f.get("modified_time")
        if mod_time:
            try:
                if isinstance(mod_time, (int, float)):
                    mod_str = dt.datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    mod_str = str(mod_time)
            except Exception:
                mod_str = str(mod_time)
        else:
            mod_str = "N/A"
        self._add_meta_row(meta_frame, row, "Modificado", mod_str); row += 1

        # URL web si existe
        web_url = f.get("web_url")
        if web_url:
            self._add_meta_row(meta_frame, row, "URL", web_url[:40] + "..."); row += 1

        # Separador
        sep = tk.Frame(meta_frame, bg=CARD_BORDER, height=1)
        sep.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1

        # Metadatos extraidos (EXIF / ffprobe)
        extra = f.get("extra", {})
        metadata = extra.get("metadata", {}) if isinstance(extra, dict) else {}

        if metadata:
            # Resolucion
            res = metadata.get("resolution")
            if res:
                self._add_meta_row(meta_frame, row, "Resolucion",
                                   f"{res.get('width', '?')}x{res.get('height', '?')} px"); row += 1

            # Formato
            fmt = metadata.get("format") or metadata.get("format_long_name")
            if fmt:
                self._add_meta_row(meta_frame, row, "Formato", fmt); row += 1

            # Modo de color
            color_mode = metadata.get("color_mode")
            if color_mode:
                self._add_meta_row(meta_frame, row, "Modo color", color_mode); row += 1

            # Fecha de captura (EXIF)
            date_taken = metadata.get("date_taken")
            if date_taken:
                self._add_meta_row(meta_frame, row, "Fecha captura", date_taken); row += 1

            # Camara
            make = metadata.get("camera_make")
            model = metadata.get("camera_model")
            if make or model:
                self._add_meta_row(meta_frame, row, "Camara", f"{make or ''} {model or ''}".strip()); row += 1

            # ISO, apertura, focal
            iso = metadata.get("iso")
            if iso:
                self._add_meta_row(meta_frame, row, "ISO", str(iso)); row += 1
            aperture = metadata.get("aperture")
            if aperture:
                self._add_meta_row(meta_frame, row, "Apertura", f"f/{aperture}"); row += 1
            focal = metadata.get("focal_length")
            if focal:
                self._add_meta_row(meta_frame, row, "Longitud focal", f"{focal}mm"); row += 1
            exposure = metadata.get("exposure_time")
            if exposure:
                self._add_meta_row(meta_frame, row, "Exposicion", str(exposure)); row += 1

            # Software
            software = metadata.get("software")
            if software:
                self._add_meta_row(meta_frame, row, "Software", software); row += 1

            # Orientacion
            orientation = metadata.get("orientation")
            if orientation:
                self._add_meta_row(meta_frame, row, "Orientacion", str(orientation)); row += 1

            # GPS
            gps = metadata.get("gps")
            if gps and isinstance(gps, dict):
                lat = gps.get("latitude_decimal")
                lon = gps.get("longitude_decimal")
                if lat and lon:
                    self._add_meta_row(meta_frame, row, "GPS", f"{lat}, {lon}"); row += 1
                    maps_url = gps.get("google_maps_url")
                    if maps_url:
                        self._add_meta_row(meta_frame, row, "Mapa", maps_url[:40] + "..."); row += 1

            # Video especificos
            duration = metadata.get("duration_seconds")
            if duration:
                mins = int(duration // 60)
                secs = duration % 60
                self._add_meta_row(meta_frame, row, "Duracion", f"{mins}:{secs:05.2f}"); row += 1

            fps = metadata.get("fps")
            if fps:
                self._add_meta_row(meta_frame, row, "FPS", f"{fps:.2f}"); row += 1

            video_codec = metadata.get("video_codec")
            if video_codec:
                self._add_meta_row(meta_frame, row, "Codec video", video_codec); row += 1

            audio_codec = metadata.get("audio_codec")
            if audio_codec:
                self._add_meta_row(meta_frame, row, "Codec audio", audio_codec); row += 1

            bit_rate = metadata.get("bit_rate")
            if bit_rate:
                self._add_meta_row(meta_frame, row, "Bitrate", f"{bit_rate/1000:.0f} kbps"); row += 1

            creation_time = metadata.get("creation_time")
            if creation_time:
                self._add_meta_row(meta_frame, row, "Creacion video", creation_time); row += 1

            # EXIF completo
            exif = metadata.get("exif")
            if exif and isinstance(exif, dict) and len(exif) > 2:
                sep2 = tk.Frame(meta_frame, bg=CARD_BORDER, height=1)
                sep2.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1
                tk.Label(meta_frame, text="EXIF completo:",
                         font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=MUTED).grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=(2, 0))
                row += 1
                for tag_name, tag_value in list(exif.items())[:15]:
                    val_str = str(tag_value)
                    if len(val_str) > 40:
                        val_str = val_str[:37] + "..."
                    self._add_meta_row(meta_frame, row, tag_name, val_str); row += 1

            # Campos adicionales de ExifTool (no disponibles en Pillow)
            lens_model = metadata.get("lens_model")
            if lens_model:
                self._add_meta_row(meta_frame, row, "Lente", str(lens_model)); row += 1

            focal_35 = metadata.get("focal_length_35mm")
            if focal_35:
                self._add_meta_row(meta_frame, row, "Focal 35mm", str(focal_35)); row += 1

            flash = metadata.get("flash")
            if flash:
                self._add_meta_row(meta_frame, row, "Flash", str(flash)); row += 1

            color_space = metadata.get("color_space")
            if color_space:
                self._add_meta_row(meta_frame, row, "Espacio color", str(color_space)); row += 1

            white_balance = metadata.get("white_balance")
            if white_balance:
                self._add_meta_row(meta_frame, row, "Balance blancos", str(white_balance)); row += 1

            gps_alt = metadata.get("gps_altitude")
            if gps_alt:
                self._add_meta_row(meta_frame, row, "Altitud GPS", str(gps_alt)); row += 1

            camera_type_mn = metadata.get("camera_type_makernote")
            if camera_type_mn:
                self._add_meta_row(meta_frame, row, "Tipo camara (MN)", str(camera_type_mn)); row += 1

            # MakerNotes (datos secretos de marcas: Canon, Sony, Apple, etc.)
            makernotes = metadata.get("makernotes")
            if makernotes and isinstance(makernotes, dict) and len(makernotes) > 0:
                sep_mn = tk.Frame(meta_frame, bg=CARD_BORDER, height=1)
                sep_mn.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1
                tk.Label(meta_frame, text=f"MakerNotes ({len(makernotes)} campos):",
                         font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg="#b8860b").grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=(2, 0))
                row += 1
                for tag_name, tag_value in list(makernotes.items())[:20]:
                    val_str = str(tag_value)
                    if len(val_str) > 40:
                        val_str = val_str[:37] + "..."
                    # Quitar prefijos de grupo (MakerNotes:, Canon:, Nikon:, etc.)
                    display_name = tag_name.split(":", 1)[-1] if ":" in tag_name else tag_name
                    self._add_meta_row(meta_frame, row, display_name, val_str); row += 1

            # Boton para ver TODOS los tags en ventana ampliable
            all_tags = metadata.get("exiftool_all_tags")
            if all_tags and isinstance(all_tags, dict) and len(all_tags) > 0:
                sep_at = tk.Frame(meta_frame, bg=CARD_BORDER, height=1)
                sep_at.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1
                tag_count = metadata.get("exiftool_tag_count", len(all_tags))
                engine = metadata.get("extraction_engine", "?")
                tk.Label(meta_frame, text=f"ExifTool: {tag_count} tags (motor: {engine})",
                         font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=MUTED).grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=(2, 0))
                row += 1
                btn_all_tags = tk.Button(
                    meta_frame, text=f"Ver todos los {tag_count} tags",
                    font=("Segoe UI", 8), relief="flat",
                    bg="#e8f0fe", fg=ACCENT, padx=8, pady=2, cursor="hand2",
                    command=lambda m=metadata, n=f.get("name", "?"): self._show_all_tags_window(m, n),
                )
                btn_all_tags.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
                row += 1
        else:
            tk.Label(meta_frame, text="(Sin metadatos EXIF disponibles)",
                     font=("Segoe UI", 8), bg=CARD_BG, fg=MUTED).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=4)
            row += 1

        # Checkbox de eliminacion
        sep3 = tk.Frame(meta_frame, bg=CARD_BORDER, height=1)
        sep3.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1

        file_key = f"{group_idx}_{file_idx}"
        var_delete = tk.BooleanVar(value=False)
        self._delete_vars[file_key] = (var_delete, f)

        footer = tk.Frame(card, bg=CARD_BG)
        footer.pack(fill="x", padx=8, pady=(4, 8))

        if is_deletable:
            cb = tk.Checkbutton(
                footer, text="Marcar para eliminar",
                variable=var_delete, bg=CARD_BG,
                font=("Segoe UI", 9), fg=DANGER,
            )
            cb.pack(side="left")

            btn_keep = tk.Button(
                footer, text="Conservar este", font=("Segoe UI", 8),
                relief="flat", bg="#e8f0fe", fg=ACCENT, padx=6, pady=2,
                cursor="hand2",
                command=lambda v=var_delete: self._keep_this_and_mark_others(file_key),
            )
            btn_keep.pack(side="right")
        else:
            tk.Label(footer, text="No eliminable (en la nube)",
                     font=("Segoe UI", 8), bg=CARD_BG, fg=MUTED).pack(side="left")

    def _add_meta_row(self, parent, row, label, value):
        """Anade una fila de etiqueta:valor a la tabla de metadatos."""
        tk.Label(parent, text=label + ":", font=("Segoe UI", 8),
                 bg=CARD_BG, fg=MUTED, anchor="nw").grid(
            row=row, column=0, sticky="nw", padx=(0, 6), pady=1)
        tk.Label(parent, text=str(value), font=("Segoe UI", 8),
                 bg=CARD_BG, fg=TEXT_COLOR, anchor="nw", wraplength=180, justify="left").grid(
            row=row, column=1, sticky="nw", pady=1)

    def _show_all_tags_window(self, metadata: dict, file_name: str):
        """Abre una ventana ampliable con TODOS los tags de ExifTool."""
        all_tags = metadata.get("exiftool_all_tags", {})
        makernotes = metadata.get("makernotes", {})
        engine = metadata.get("extraction_engine", "desconocido")
        tag_count = metadata.get("exiftool_tag_count", len(all_tags))

        win = tk.Toplevel(self.root)
        win.title(f"Tags de ExifTool — {file_name}")
        win.geometry("900x650")
        win.minsize(600, 400)
        win.configure(bg=BG_COLOR)
        win.transient(self.root)
        win.grab_set()

        # Cabecera
        header = tk.Frame(win, bg=BG_COLOR)
        header.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(header, text=file_name,
                 font=("Segoe UI", 13, "bold"), bg=BG_COLOR, fg=ACCENT,
                 wraplength=850, justify="left").pack(anchor="w")

        tk.Label(header,
                 text=f"{tag_count} tags extraidos — Motor: {engine}",
                 font=("Segoe UI", 9), bg=BG_COLOR, fg=MUTED).pack(anchor="w", pady=(2, 0))

        # Barra de busqueda
        search_frame = tk.Frame(win, bg=BG_COLOR)
        search_frame.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(search_frame, text="Buscar:", font=("Segoe UI", 10),
                 bg=BG_COLOR, fg=MUTED).pack(side="left", padx=(0, 6))
        search_var = tk.StringVar()
        search_var.trace_add("write", lambda *_: self._filter_tags_tree(tags_tree, search_var.get(), all_items, self._tags_result_label))
        search_entry = tk.Entry(search_frame, textvariable=search_var, width=40,
                                font=("Segoe UI", 10))
        search_entry.pack(side="left", fill="x", expand=True)

        btn_clear_search = tk.Button(
            search_frame, text="Limpiar", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, cursor="hand2",
            command=lambda: search_var.set(""),
        )
        btn_clear_search.pack(side="left", padx=6)

        # Contador de resultados
        self._tags_result_label = tk.Label(search_frame, text="", font=("Segoe UI", 9),
                                          bg=BG_COLOR, fg=MUTED)
        self._tags_result_label.pack(side="left", padx=8)

        # Botones superiores
        btn_frame = tk.Frame(win, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=12, pady=(0, 4))

        btn_expand = tk.Button(
            btn_frame, text="Expandir todo", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=3, cursor="hand2",
            command=lambda: self._toggle_all_groups(tags_tree, True),
        )
        btn_expand.pack(side="left")

        btn_collapse = tk.Button(
            btn_frame, text="Contraer todo", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=3, cursor="hand2",
            command=lambda: self._toggle_all_groups(tags_tree, False),
        )
        btn_collapse.pack(side="left", padx=4)

        btn_copy = tk.Button(
            btn_frame, text="Copiar todo al portapapeles", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=3, cursor="hand2",
            command=lambda: self._copy_all_tags(all_tags, makernotes),
        )
        btn_copy.pack(side="right")

        # Notebook con dos pestanas: Todos los tags / MakerNotes
        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        # === Pestana 1: Todos los tags ===
        tab_all = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(tab_all, text=f"Todos los tags ({len(all_tags)})")

        tree_frame = tk.Frame(tab_all, bg=BG_COLOR)
        tree_frame.pack(fill="both", expand=True)

        tags_tree = ttk.Treeview(
            tree_frame, columns=("value",), show="tree headings", height=20,
        )
        tags_tree.heading("#0", text="Tag")
        tags_tree.heading("value", text="Valor")
        tags_tree.column("#0", width=320)
        tags_tree.column("value", width=550)

        tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tags_tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tags_tree.xview)
        tags_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        tags_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Colores por grupo
        tags_tree.tag_configure("group_file", background="#e8f0fe", foreground=ACCENT)
        tags_tree.tag_configure("group_exif", background="#fef7e0", foreground="#b8860b")
        tags_tree.tag_configure("group_makernotes", background="#fce8e6", foreground=DANGER)
        tags_tree.tag_configure("group_composite", background="#e6f4ea", foreground=SUCCESS)
        tags_tree.tag_configure("group_xmp", background="#f3e8fd", foreground="#7c3aed")
        tags_tree.tag_configure("group_iptc", background="#fff3e0", foreground="#e65100")
        tags_tree.tag_configure("group_other", background=CARD_BG, foreground=TEXT_COLOR)
        tags_tree.tag_configure("tag", background=CARD_BG)

        # Llenar el arbol agrupado por categoria
        all_items = []  # (item_id, tag_name, value) para filtrado

        # Agrupar tags por su prefijo (grupo)
        groups = {}
        for tag_name, tag_value in all_tags.items():
            if ":" in tag_name:
                group, name = tag_name.split(":", 1)
            else:
                group, name = "General", tag_name
            if group not in groups:
                groups[group] = []
            groups[group].append((name, tag_value))

        # Etiquetas y colores para grupos
        group_config = {
            "File": ("group_file", "Archivo"),
            "EXIF": ("group_exif", "EXIF"),
            "MakerNotes": ("group_makernotes", "MakerNotes (datos secretos de marcas)"),
            "Composite": ("group_composite", "Composite"),
            "XMP": ("group_xmp", "XMP"),
            "IPTC": ("group_iptc", "IPTC"),
            "QuickTime": ("group_other", "QuickTime (video)"),
        }

        for group_name in sorted(groups.keys()):
            tags = groups[group_name]
            tag_str = group_config.get(group_name, ("group_other", group_name))
            color_tag, display_name = tag_str

            parent_id = tags_tree.insert(
                "", "end",
                text=f"{display_name} ({len(tags)} tags)",
                values=("",),
                open=False,
                tags=(color_tag,),
            )
            all_items.append((parent_id, f"{display_name} ({len(tags)})", "", True))

            for tag_name, tag_value in sorted(tags, key=lambda x: x[0].lower()):
                val_str = str(tag_value)
                if len(val_str) > 200:
                    val_str = val_str[:197] + "..."
                child_id = tags_tree.insert(
                    parent_id, "end",
                    text=tag_name,
                    values=(val_str,),
                    tags=("tag",),
                )
                all_items.append((child_id, tag_name, val_str, False))

        # Actualar contador inicial
        total_tags = sum(1 for _, _, _, is_group in all_items if not is_group)
        self._tags_result_label.config(text=f"{total_tags} tags")

        # Doble clic para copiar valor
        def _on_double_click(event):
            selection = tags_tree.selection()
            if not selection:
                return
            item = tags_tree.item(selection[0])
            val = item.get("values", [""])[0] if item.get("values") else ""
            if val:
                self.root.clipboard_clear()
                self.root.clipboard_append(str(val))
        tags_tree.bind("<Double-1>", _on_double_click)

        # === Pestana 2: MakerNotes completos ===
        tab_mn = tk.Frame(notebook, bg=BG_COLOR)
        mn_count = len(makernotes) if makernotes else 0
        notebook.add(tab_mn, text=f"MakerNotes ({mn_count})")

        if mn_count == 0:
            tk.Label(
                tab_mn,
                text="Este archivo no contiene MakerNotes.\n\n"
                     "Los MakerNotes son datos secretos que las marcas (Canon, Sony,\n"
                     "Apple, Nikon, etc.) incluyen en sus archivos. Para verlos,\n"
                     "escanea fotos tomadas directamente con una camara real.",
                font=("Segoe UI", 11), bg=BG_COLOR, fg=MUTED,
                justify="center", wraplength=600,
            ).pack(expand=True)
        else:
            # Cabecera informativa de MakerNotes
            mn_header = tk.Frame(tab_mn, bg="#fce8e6")
            mn_header.pack(fill="x", padx=4, pady=(4, 2))
            tk.Label(
                mn_header,
                text=f"MakerNotes — {mn_count} campos secretos de marca",
                font=("Segoe UI", 12, "bold"), bg="#fce8e6", fg=DANGER,
            ).pack(anchor="w", padx=8, pady=4)
            tk.Label(
                mn_header,
                text="Estos datos son exclusivos de ExifTool y no pueden leerse con Pillow ni ffprobe.\n"
                     "Incluyen configuracion interna de camara, numero de disparos, temperatura del sensor, etc.",
                font=("Segoe UI", 9), bg="#fce8e6", fg=MUTED,
                justify="left", wraplength=800,
            ).pack(anchor="w", padx=8, pady=(0, 4))

            # Barra de busqueda para MakerNotes
            mn_search_frame = tk.Frame(tab_mn, bg=BG_COLOR)
            mn_search_frame.pack(fill="x", padx=4, pady=(2, 4))

            tk.Label(mn_search_frame, text="Buscar:", font=("Segoe UI", 10),
                     bg=BG_COLOR, fg=MUTED).pack(side="left", padx=(0, 6))
            mn_search_var = tk.StringVar()
            mn_search_entry = tk.Entry(mn_search_frame, textvariable=mn_search_var, width=40,
                                        font=("Segoe UI", 10))
            mn_search_entry.pack(side="left", fill="x", expand=True)

            mn_result_label = tk.Label(mn_search_frame, text="", font=("Segoe UI", 9),
                                       bg=BG_COLOR, fg=MUTED)
            mn_result_label.pack(side="left", padx=8)
            self._mn_result_label = mn_result_label

            # Botones MakerNotes
            mn_btn_frame = tk.Frame(tab_mn, bg=BG_COLOR)
            mn_btn_frame.pack(fill="x", padx=4, pady=(0, 2))

            tk.Button(
                mn_btn_frame, text="Expandir todo", font=("Segoe UI", 9),
                relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=3, cursor="hand2",
                command=lambda: self._toggle_all_groups(mn_tree, True),
            ).pack(side="left")
            tk.Button(
                mn_btn_frame, text="Contraer todo", font=("Segoe UI", 9),
                relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=3, cursor="hand2",
                command=lambda: self._toggle_all_groups(mn_tree, False),
            ).pack(side="left", padx=4)
            tk.Button(
                mn_btn_frame, text="Copiar MakerNotes", font=("Segoe UI", 9),
                relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=3, cursor="hand2",
                command=lambda: self._copy_all_tags(makernotes, {}),
            ).pack(side="right")

            # Treeview de MakerNotes
            mn_tree_frame = tk.Frame(tab_mn, bg=BG_COLOR)
            mn_tree_frame.pack(fill="both", expand=True, padx=4, pady=2)

            mn_tree = ttk.Treeview(
                mn_tree_frame, columns=("value",), show="tree headings", height=20,
            )
            mn_tree.heading("#0", text="Tag MakerNotes")
            mn_tree.heading("value", text="Valor completo")
            mn_tree.column("#0", width=350)
            mn_tree.column("value", width=520)

            mn_scroll_y = ttk.Scrollbar(mn_tree_frame, orient="vertical", command=mn_tree.yview)
            mn_scroll_x = ttk.Scrollbar(mn_tree_frame, orient="horizontal", command=mn_tree.xview)
            mn_tree.configure(yscrollcommand=mn_scroll_y.set, xscrollcommand=mn_scroll_x.set)

            mn_tree.grid(row=0, column=0, sticky="nsew")
            mn_scroll_y.grid(row=0, column=1, sticky="ns")
            mn_scroll_x.grid(row=1, column=0, sticky="ew")
            mn_tree_frame.grid_rowconfigure(0, weight=1)
            mn_tree_frame.grid_columnconfigure(0, weight=1)

            # Colores para MakerNotes
            mn_tree.tag_configure("mn_group", background="#fce8e6", foreground=DANGER,
                                  font=("Segoe UI", 9, "bold"))
            mn_tree.tag_configure("mn_tag", background=CARD_BG)
            mn_tree.tag_configure("mn_value_highlight", background="#fff8e1", foreground="#b8860b")

            # Agrupar MakerNotes por marca (Canon:, Nikon:, Sony:, MakerNotes:, etc.)
            mn_items = []
            mn_groups = {}
            for tag_name, tag_value in makernotes.items():
                if ":" in tag_name:
                    group, name = tag_name.split(":", 1)
                else:
                    group, name = "General", tag_name
                if group not in mn_groups:
                    mn_groups[group] = []
                mn_groups[group].append((name, tag_value))

            for group_name in sorted(mn_groups.keys()):
                tags_in_group = mn_groups[group_name]
                parent_id = mn_tree.insert(
                    "", "end",
                    text=f"{group_name} ({len(tags_in_group)} campos)",
                    values=("",),
                    open=False,
                    tags=("mn_group",),
                )
                mn_items.append((parent_id, f"{group_name} ({len(tags_in_group)})", "", True))

                for tag_name, tag_value in sorted(tags_in_group, key=lambda x: x[0].lower()):
                    val_str = str(tag_value)
                    if len(val_str) > 300:
                        val_str = val_str[:297] + "..."
                    child_id = mn_tree.insert(
                        parent_id, "end",
                        text=tag_name,
                        values=(val_str,),
                        tags=("mn_tag",),
                    )
                    mn_items.append((child_id, tag_name, val_str, False))

            # Contador inicial
            mn_total = sum(1 for _, _, _, is_group in mn_items if not is_group)
            mn_result_label.config(text=f"{mn_total} campos")

            # Busqueda en MakerNotes
            mn_search_var.trace_add(
                "write",
                lambda *_: self._filter_tags_tree(mn_tree, mn_search_var.get(), mn_items, mn_result_label),
            )

            # Doble clic para copiar valor
            def _on_mn_double_click(event):
                selection = mn_tree.selection()
                if not selection:
                    return
                item = mn_tree.item(selection[0])
                val = item.get("values", [""])[0] if item.get("values") else ""
                if val:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(str(val))
            mn_tree.bind("<Double-1>", _on_mn_double_click)

            # Si hay MakerNotes, seleccionar esa pestana automaticamente
            if mn_count > 0:
                notebook.select(tab_mn)

        # Boton cerrar
        btn_close_frame = tk.Frame(win, bg=BG_COLOR)
        btn_close_frame.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(
            btn_close_frame, text="Cerrar", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", relief="flat", padx=20, pady=6, cursor="hand2",
            command=win.destroy,
        ).pack(side="right")

    def _filter_tags_tree(self, tree, query, all_items, result_label=None):
        """Filtra el arbol de tags por texto de busqueda."""
        query = query.lower().strip()
        label = result_label or getattr(self, "_tags_result_label", None)

        if not query:
            # Mostrar todo, contraer
            self._toggle_all_groups(tree, False)
            count = sum(1 for _, _, _, is_group in all_items if not is_group)
            if label:
                label.config(text=f"{count} tags")
            return

        # Ocultar items que no coinciden
        match_count = 0
        for item_id, tag_name, tag_value, is_group in all_items:
            if is_group:
                continue
            matches = query in tag_name.lower() or query in tag_value.lower()
            if matches:
                tree.reattach(item_id, tree.parent(item_id), tk.END)
                match_count += 1
                # Asegurar que el padre este visible y expandido
                parent = tree.parent(item_id)
                if parent:
                    tree.item(parent, open=True)
                    tree.reattach(parent, tree.parent(parent), tk.END)
            else:
                tree.detach(item_id)

        # Ocultar grupos vacios
        for item_id, tag_name, tag_value, is_group in all_items:
            if not is_group:
                continue
            children = tree.get_children(item_id)
            visible_children = [c for c in children if tree.exists(c)]
            if not visible_children:
                tree.detach(item_id)

        if label:
            label.config(text=f"{match_count} resultados")

    def _toggle_all_groups(self, tree, expand: bool):
        """Expande o contrae todos los grupos del arbol de tags."""
        for item in tree.get_children():
            tree.item(item, open=expand)

    def _copy_all_tags(self, all_tags: dict, makernotes: dict):
        """Copia todos los tags al portapapeles en formato texto."""
        lines = []
        for tag_name, tag_value in sorted(all_tags.items()):
            lines.append(f"{tag_name}: {tag_value}")
        text = "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._log(f">>> {len(lines)} tags copiados al portapapeles")

    def _keep_this_and_mark_others(self, keep_key: str):
        """Marca todos los archivos del grupo actual para eliminacion excepto este."""
        for key, (var, f) in self._delete_vars.items():
            if key == keep_key:
                var.set(False)
            else:
                source = f.get("source", "")
                if source in DELETABLE_SOURCES and f.get("path"):
                    var.set(True)

    def _clear_cards(self):
        """Limpia las tarjetas del panel de comparacion."""
        for widget in self.cards_inner.winfo_children():
            widget.destroy()
        self._photo_refs = {}

    # ─── Eliminacion segura ─────────────────────────────────────────────

    def _delete_selected(self):
        """Mueve los archivos seleccionados a una carpeta de cuarentena."""
        to_delete = []
        for key, (var, f) in self._delete_vars.items():
            if var.get():
                file_path = f.get("path", "")
                if file_path and os.path.exists(file_path):
                    source = f.get("source", "")
                    if source in DELETABLE_SOURCES:
                        to_delete.append((key, f, file_path))

        if not to_delete:
            messagebox.showinfo("Sin seleccion", "No hay archivos seleccionados para eliminar.")
            return

        # Verificar que no se vayan a eliminar todos los archivos de un grupo
        total_files = len(self._delete_vars)
        if len(to_delete) >= total_files:
            result = messagebox.askyesno(
                "Advertencia",
                f"Estas a punto de eliminar TODOS los {len(to_delete)} archivos de este grupo.\n"
                f"No quedara ninguna copia. Deseas continuar?"
            )
            if not result:
                return

        # Ventana de confirmacion con lista completa
        confirm_text = "Se moveran los siguientes archivos a cuarentena:\n\n"
        for key, f, path in to_delete:
            confirm_text += f"  - {f.get('name', '?')}\n    {path}\n"
        confirm_text += f"\nTotal: {len(to_delete)} archivo(s)\n"
        confirm_text += "\nLos archivos se moveran a: _media_dedupe_eliminados/\n"
        confirm_text += "No se borraran permanentemente."

        result = messagebox.askyesno("Confirmar eliminacion", confirm_text)
        if not result:
            return

        # Crear carpeta de cuarentena
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantine_dir = os.path.join(PROJECT_DIR, "_media_dedupe_eliminados", timestamp)
        os.makedirs(quarantine_dir, exist_ok=True)

        # Mover archivos
        moved = []
        errors = []
        for key, f, path in to_delete:
            try:
                dest = os.path.join(quarantine_dir, os.path.basename(path))
                # Evitar colision de nombres
                counter = 1
                while os.path.exists(dest):
                    name, ext = os.path.splitext(os.path.basename(path))
                    dest = os.path.join(quarantine_dir, f"{name}_{counter}{ext}")
                    counter += 1

                shutil.move(path, dest)
                moved.append({"original_path": path, "quarantine_path": dest,
                              "name": f.get("name", "?"), "source": f.get("source", "?")})
                self._log(f">>> Movido: {f.get('name', '?')} -> {dest}")
            except Exception as e:
                errors.append({"path": path, "error": str(e)})
                self._log(f">>> Error moviendo {path}: {e}")

        # Guardar registro de eliminacion
        log_path = os.path.join(quarantine_dir, "registro_eliminacion.json")
        with open(log_path, "w", encoding="utf-8") as lf:
            json.dump({
                "timestamp": timestamp,
                "moved": moved,
                "errors": errors,
            }, lf, ensure_ascii=False, indent=2)

        # Resumen
        msg = f"Se movieron {len(moved)} archivo(s) a:\n{quarantine_dir}"
        if errors:
            msg += f"\n\n{len(errors)} archivo(s) no se pudieron mover."
        messagebox.showinfo("Eliminacion completada", msg)

        # Desmarcar checkboxes
        for key, (var, f) in self._delete_vars.items():
            var.set(False)

        self.btn_delete.config(state="disabled")
        self.lbl_delete_info.config(text=f"Movidos: {len(moved)} archivo(s) a {quarantine_dir}")

    # ─── Reportes ───────────────────────────────────────────────────────

    def _open_report(self, ext: str):
        if not self.report_base:
            return
        path = f"{self.report_base}.{ext}"
        if not os.path.exists(path):
            path = str(PROJECT_DIR / path)
            if not os.path.exists(path):
                return

        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo: {e}")

    # ─── Logs ───────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self.log_queue.put(msg)

    def _clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _poll_log_queue(self):
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
            except queue.Empty:
                break
        self.root.after(100, self._poll_log_queue)

    # ─── Utils ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_size(size: int) -> str:
        if size >= 1024**3:
            return f"{size/1024**3:.2f} GB"
        elif size >= 1024**2:
            return f"{size/1024**2:.2f} MB"
        elif size >= 1024:
            return f"{size/1024:.2f} KB"
        return f"{size} B"

    @staticmethod
    def _is_image_file(path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}


def main():
    root = tk.Tk()

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TCheckbutton", background=BG_COLOR, font=("Segoe UI", 10))
    style.configure("TRadiobutton", background=BG_COLOR, font=("Segoe UI", 10))
    style.configure("TNotebook", background=BG_COLOR)
    style.configure("TNotebook.Tab", padding=[12, 6], font=("Segoe UI", 10))
    style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
    style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    app = MediaDedupeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
