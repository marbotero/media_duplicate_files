#!/usr/bin/env python3
"""
media_dedupe_gui.py — Interfaz gráfica para Media Dedupe.

GUI en Tkinter que ejecuta los escaneos del CLI (media_dedupe.py) con:
  - Selección visual de orígenes (Google Drive, OneDrive, Google Photos, WhatsApp, Takeout)
  - Botones de autenticación
  - Logs en vivo del proceso
  - Resultados del escaneo con resumen y árbol de grupos
  - Botones para abrir reportes generados

Uso:
  python media_dedupe_gui.py
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Directorio del proyecto (donde está media_dedupe.py)
PROJECT_DIR = Path(__file__).parent.resolve()

# ─── Colores y estilos ────────────────────────────────────────────────────────

BG_COLOR = "#f5f5f5"
CARD_BG = "#ffffff"
ACCENT = "#1a73e8"
ACCENT_HOVER = "#1557b0"
DANGER = "#d93025"
SUCCESS = "#1e8e3e"
WARNING = "#f9ab00"
TEXT_COLOR = "#333333"
MUTED = "#666666"


class MediaDedupeGUI:
    """Interfaz gráfica principal."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Media Dedupe — Detector de Duplicados Multi-origen")
        self.root.geometry("960x720")
        self.root.minsize(800, 600)
        self.root.configure(bg=BG_COLOR)

        # Estado
        self.scan_process = None
        self.log_queue: queue.Queue = queue.Queue()
        self.report_base = None

        # Variables de Tkinter
        self.var_drive = tk.BooleanVar(value=False)
        self.var_onedrive = tk.BooleanVar(value=False)
        self.var_photos_api = tk.BooleanVar(value=False)
        self.var_whatsapp = tk.BooleanVar(value=False)
        self.var_takeout = tk.BooleanVar(value=False)

        self.var_whatsapp_folder = tk.StringVar()
        self.var_takeout_folder = tk.StringVar()
        self.var_photos_mode = tk.StringVar(value="app-created")
        self.var_hash_mode = tk.StringVar(value="full")
        self.var_skip_similar = tk.BooleanVar(value=False)
        self.var_image_threshold = tk.StringVar(value="5")
        self.var_video_threshold = tk.StringVar(value="0.85")
        self.var_report_name = tk.StringVar(value="reporte_duplicados")

        self._build_ui()
        self._poll_log_queue()

    # ─── Construcción de la UI ──────────────────────────────────────────

    def _build_ui(self):
        """Construye toda la interfaz."""
        # Frame principal con scroll
        main_frame = tk.Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Título
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

        # Notebook con pestañas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True)

        # Pestaña 1: Configuración
        config_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(config_frame, text="  Configuración  ")
        self._build_config_tab(config_frame)

        # Pestaña 2: Resultados
        results_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(results_frame, text="  Resultados  ")
        self._build_results_tab(results_frame)

        # Pestaña 3: Logs
        logs_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(logs_frame, text="  Logs  ")
        self._build_logs_tab(logs_frame)

        self.notebook = notebook

    def _build_config_tab(self, parent):
        """Pestaña de configuración de orígenes y opciones."""
        # Frame con scroll
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

        # Bind mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Sección: Orígenes Cloud ──
        self._section_label(scroll_frame, "Orígenes Cloud", 0)

        cloud_frame = tk.LabelFrame(
            scroll_frame, text=" Orígenes Cloud ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        cloud_frame.pack(fill="x", padx=10, pady=(4, 8))

        # Google Drive
        drive_row = tk.Frame(cloud_frame, bg=BG_COLOR)
        drive_row.pack(fill="x", pady=2)
        tk.Checkbutton(drive_row, text="Google Drive", variable=self.var_drive,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Button(drive_row, text="Autenticar", width=10,
                  command=lambda: self._run_auth("google-drive")).pack(side="right")

        # OneDrive
        onedrive_row = tk.Frame(cloud_frame, bg=BG_COLOR)
        onedrive_row.pack(fill="x", pady=2)
        tk.Checkbutton(drive_row.master, text="OneDrive", variable=self.var_onedrive,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(in_=onedrive_row, side="left")
        tk.Button(onedrive_row, text="Autenticar", width=10,
                  command=lambda: self._run_auth("onedrive")).pack(side="right")

        # Google Photos API
        photos_row = tk.Frame(cloud_frame, bg=BG_COLOR)
        photos_row.pack(fill="x", pady=2)
        tk.Checkbutton(photos_row, text="Google Photos (API)", variable=self.var_photos_api,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Label(photos_row, text="Modo:", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        photos_combo = ttk.Combobox(photos_row, textvariable=self.var_photos_mode,
                                     values=["app-created", "picker"], width=12, state="readonly")
        photos_combo.pack(side="left")
        tk.Button(photos_row, text="Autenticar", width=10,
                  command=lambda: self._run_auth("google-photos")).pack(side="right")

        # ── Sección: Carpetas Locales ──
        self._section_label(scroll_frame, "Carpetas Locales", 16)

        local_frame = tk.LabelFrame(
            scroll_frame, text=" Carpetas Locales ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        local_frame.pack(fill="x", padx=10, pady=(4, 8))

        # WhatsApp
        wa_row = tk.Frame(local_frame, bg=BG_COLOR)
        wa_row.pack(fill="x", pady=4)
        tk.Checkbutton(wa_row, text="WhatsApp", variable=self.var_whatsapp,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(wa_row, textvariable=self.var_whatsapp_folder, width=45,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), fill="x", expand=True)
        tk.Button(wa_row, text="Buscar...", command=self._browse_whatsapp).pack(side="right")

        # Google Takeout
        to_row = tk.Frame(local_frame, bg=BG_COLOR)
        to_row.pack(fill="x", pady=4)
        tk.Checkbutton(to_row, text="Google Takeout", variable=self.var_takeout,
                       bg=BG_COLOR, font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(to_row, textvariable=self.var_takeout_folder, width=45,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), fill="x", expand=True)
        tk.Button(to_row, text="Buscar...", command=self._browse_takeout).pack(side="right")

        tk.Label(local_frame, text="Nota: Takeout escanea todos los productos de Google "
                  "(Photos, Drive, YouTube, etc.)",
                 bg=BG_COLOR, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        # ── Sección: Opciones ──
        self._section_label(scroll_frame, "Opciones de Escaneo", 16)

        opts_frame = tk.LabelFrame(
            scroll_frame, text=" Opciones ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        opts_frame.pack(fill="x", padx=10, pady=(4, 8))

        # Hash mode
        hash_row = tk.Frame(opts_frame, bg=BG_COLOR)
        hash_row.pack(fill="x", pady=4)
        tk.Label(hash_row, text="Modo de hash:", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left")
        ttk.Radiobutton(hash_row, text="Completo (descargar + MD5/SHA-256)",
                        variable=self.var_hash_mode, value="full").pack(side="left", padx=8)
        ttk.Radiobutton(hash_row, text="Metadatos (rápido, sin descargar)",
                        variable=self.var_hash_mode, value="metadata").pack(side="left")

        # Thresholds
        thr_row = tk.Frame(opts_frame, bg=BG_COLOR)
        thr_row.pack(fill="x", pady=4)
        tk.Label(thr_row, text="Umbral imágenes (Hamming):", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        tk.Spinbox(thr_row, from_=0, to=20, textvariable=self.var_image_threshold,
                   width=5, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(thr_row, text="   Umbral videos (ratio):", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(20, 4))
        tk.Spinbox(thr_row, from_=0.50, to=1.00, increment=0.05,
                   textvariable=self.var_video_threshold, width=6,
                   font=("Segoe UI", 9), format="%.2f").pack(side="left")

        # Skip similar
        skip_row = tk.Frame(opts_frame, bg=BG_COLOR)
        skip_row.pack(fill="x", pady=4)
        tk.Checkbutton(skip_row, text="Solo duplicados exactos (saltar casi-duplicados)",
                       variable=self.var_skip_similar, bg=BG_COLOR,
                       font=("Segoe UI", 9)).pack(side="left")

        # Report name
        report_row = tk.Frame(opts_frame, bg=BG_COLOR)
        report_row.pack(fill="x", pady=4)
        tk.Label(report_row, text="Nombre del reporte:", bg=BG_COLOR, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(report_row, textvariable=self.var_report_name, width=30,
                 font=("Segoe UI", 9)).pack(side="left", padx=8)

        # ── Botones de acción ──
        btn_frame = tk.Frame(scroll_frame, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=10, pady=(12, 8))

        self.btn_scan = tk.Button(
            btn_frame, text="▶  Iniciar Escaneo", font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            activeforeground="white", relief="flat", padx=20, pady=8,
            cursor="hand2", command=self._start_scan,
        )
        self.btn_scan.pack(side="left")

        self.btn_stop = tk.Button(
            btn_frame, text="⏹  Detener", font=("Segoe UI", 10),
            bg=DANGER, fg="white", activebackground="#a52a1a",
            activeforeground="white", relief="flat", padx=12, pady=8,
            cursor="hand2", command=self._stop_scan, state="disabled",
        )
        self.btn_stop.pack(side="left", padx=8)

        # Botón especial para picker
        self.btn_picker_confirm = tk.Button(
            btn_frame, text="✓  Ya seleccioné las fotos", font=("Segoe UI", 10),
            bg=WARNING, fg="white", relief="flat", padx=12, pady=8,
            cursor="hand2", command=self._confirm_picker, state="disabled",
        )
        self.btn_picker_confirm.pack(side="left", padx=8)

        # Barra de progreso
        self.progress = ttk.Progressbar(btn_frame, mode="indeterminate", length=200)
        self.progress.pack(side="right")

    def _build_results_tab(self, parent):
        """Pestaña de resultados del escaneo."""
        # Resumen
        summary_frame = tk.LabelFrame(
            parent, text=" Resumen ", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        summary_frame.pack(fill="x", padx=10, pady=10)

        self.lbl_summary = tk.Label(
            summary_frame, text="Ejecuta un escaneo para ver resultados.",
            bg=BG_COLOR, fg=MUTED, font=("Segoe UI", 10), justify="left",
        )
        self.lbl_summary.pack(anchor="w")

        # Botones para abrir reportes
        reports_frame = tk.Frame(parent, bg=BG_COLOR)
        reports_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.btn_open_html = tk.Button(
            reports_frame, text="📄 Abrir HTML", font=("Segoe UI", 10),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=12, pady=6,
            cursor="hand2", command=lambda: self._open_report("html"),
            state="disabled",
        )
        self.btn_open_html.pack(side="left", padx=(0, 4))

        self.btn_open_csv = tk.Button(
            reports_frame, text="📊 Abrir CSV", font=("Segoe UI", 10),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=12, pady=6,
            cursor="hand2", command=lambda: self._open_report("csv"),
            state="disabled",
        )
        self.btn_open_csv.pack(side="left", padx=4)

        self.btn_open_json = tk.Button(
            reports_frame, text="📋 Abrir JSON", font=("Segoe UI", 10),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=12, pady=6,
            cursor="hand2", command=lambda: self._open_report("json"),
            state="disabled",
        )
        self.btn_open_json.pack(side="left", padx=4)

        # Árbol de grupos de duplicados
        tree_frame = tk.Frame(parent, bg=BG_COLOR)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("tipo", "score", "archivos", "recuperable")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=12)
        self.tree.heading("#0", text="Grupo / Archivo")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("score", text="Score")
        self.tree.heading("archivos", text="Nº Archivos")
        self.tree.heading("recuperable", text="Recuperable")

        self.tree.column("#0", width=350)
        self.tree.column("tipo", width=100)
        self.tree.column("score", width=60)
        self.tree.column("archivos", width=80)
        self.tree.column("recuperable", width=100)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Configurar tags para colores
        self.tree.tag_configure("exact", background="#fce8e6")
        self.tree.tag_configure("image_similar", background="#fef7e0")
        self.tree.tag_configure("video_similar", background="#e6f4ea")

    def _build_logs_tab(self, parent):
        """Pestaña de logs en vivo."""
        self.log_text = tk.Text(
            parent, wrap="word", font=("Consolas", 9),
            bg="#1e1e1e", fg="#cccccc", insertbackground="white",
            state="disabled", relief="flat",
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        # Scrollbar
        log_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y", pady=8)

        # Botón limpiar logs
        btn_clear = tk.Button(
            parent, text="Limpiar logs", font=("Segoe UI", 9),
            relief="flat", bg="#e8f0fe", fg=ACCENT, padx=8, pady=4,
            command=self._clear_logs,
        )
        btn_clear.pack(side="bottom", anchor="e", padx=8, pady=(0, 4))

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

    # ─── Autenticación ──────────────────────────────────────────────────

    def _run_auth(self, provider: str):
        """Ejecuta la autenticación de un provider en un hilo separado."""
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
                    self._log(f">>> {provider}: autenticación exitosa.")
                else:
                    self._log(f">>> {provider}: error de autenticación (código {proc.returncode}).")
            except Exception as e:
                self._log(f">>> Error: {e}")

        threading.Thread(target=_run, daemon=True).start()

    # ─── Escaneo ────────────────────────────────────────────────────────

    def _start_scan(self):
        """Inicia el proceso de escaneo."""
        # Construir comando
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

        # Verificar que hay al menos un origen
        if not sources and not (self.var_whatsapp.get() and self.var_whatsapp_folder.get()) \
           and not (self.var_takeout.get() and self.var_takeout_folder.get()):
            messagebox.showwarning(
                "Sin orígenes",
                "Selecciona al menos un origen para escanear."
            )
            return

        cmd += ["--hash-mode", self.var_hash_mode.get()]
        cmd += ["--image-threshold", self.var_image_threshold.get()]
        cmd += ["--video-threshold", self.var_video_threshold.get()]

        if self.var_skip_similar.get():
            cmd += ["--skip-similar"]

        self.report_base = self.var_report_name.get() or "reporte_duplicados"
        cmd += ["--report", self.report_base]

        # Limpiar árbol de resultados
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.lbl_summary.config(text="Escaneando...", fg=WARNING)

        # Deshabilitar botón scan, habilitar stop
        self.btn_scan.config(state="disabled")
        self.btn_stop.config(state="normal")

        # Si es modo picker, habilitar botón de confirmación
        if self.var_photos_api.get() and self.var_photos_mode.get() == "picker":
            self.btn_picker_confirm.config(state="normal")

        # Iniciar barra de progreso
        self.progress.start(15)

        # Cambiar a pestaña de logs
        self.notebook.select(2)

        self._log(f">>> Comando: {' '.join(cmd)}")
        self._log(">>> Iniciando escaneo...")

        # Ejecutar en hilo
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
                    self.log_queue.put(f">>> Escaneo terminado con error (código {rc}).")
                    self.root.after(100, lambda: self._scan_finished(False))
            except Exception as e:
                self.log_queue.put(f">>> Error: {e}")
                self.root.after(100, lambda: self._scan_finished(False))

        threading.Thread(target=_run, daemon=True).start()

    def _stop_scan(self):
        """Detiene el proceso de escaneo."""
        if self.scan_process and self.scan_process.poll() is None:
            self.scan_process.terminate()
            self._log(">>> Deteniendo escaneo...")
            self._scan_finished(False)

    def _confirm_picker(self):
        """Envía Enter al stdin del proceso para confirmar la selección del picker."""
        if self.scan_process and self.scan_process.poll() is None:
            try:
                self.scan_process.stdin.write("\n")
                self.scan_process.stdin.flush()
                self._log(">>> Confirmación enviada al selector de Google Photos.")
                self.btn_picker_confirm.config(state="disabled")
            except Exception:
                pass

    def _scan_finished(self, success=True):
        """Limpia la UI después del escaneo."""
        self.btn_scan.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_picker_confirm.config(state="disabled")
        self.progress.stop()

        if not success:
            self.lbl_summary.config(text="El escaneo no se completó correctamente.", fg=DANGER)

    # ─── Resultados ─────────────────────────────────────────────────────

    def _load_results(self):
        """Carga los resultados del reporte JSON y los muestra."""
        self._scan_finished(True)

        report_path = f"{self.report_base}.json"
        if not os.path.exists(report_path):
            report_path = str(PROJECT_DIR / report_path)
            if not os.path.exists(report_path):
                self.lbl_summary.config(text="No se encontró el reporte JSON.", fg=DANGER)
                return

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.lbl_summary.config(text=f"Error leyendo reporte: {e}", fg=DANGER)
            return

        groups = data.get("groups", [])
        total_recoverable = data.get("total_recoverable_size", 0)

        # Etiquetas por tipo
        type_labels = {
            "exact": "Duplicado Exacto",
            "image_similar": "Imágenes Similares",
            "video_similar": "Videos Similares",
        }

        by_type = {}
        for g in groups:
            by_type[g["group_type"]] = by_type.get(g["group_type"], 0) + 1

        # Resumen
        summary_lines = [f"Grupos encontrados: {len(groups)}"]
        for gtype, count in by_type.items():
            summary_lines.append(f"  • {type_labels.get(gtype, gtype)}: {count} grupos")
        summary_lines.append(f"Espacio recuperable: {self._format_size(total_recoverable)}")
        self.lbl_summary.config(text="\n".join(summary_lines), fg=TEXT_COLOR)

        # Llenar árbol
        for idx, group in enumerate(groups, 1):
            gtype = group["group_type"]
            label = type_labels.get(gtype, gtype)
            score = group["score"]
            num_files = len(group["files"])
            recoverable = self._format_size(group["recoverable_size"])

            parent_id = self.tree.insert(
                "", "end",
                text=f"Grupo #{idx} — {label}",
                values=(label, f"{score:.1f}", num_files, recoverable),
                tags=(gtype,),
            )

            for f in group["files"]:
                source_label = {
                    "google_drive": "Drive",
                    "onedrive": "OneDrive",
                    "whatsapp_local": "WhatsApp",
                    "google_photos": "Photos",
                    "google_photos_takeout": "Photos (Takeout)",
                    "google_drive_takeout": "Drive (Takeout)",
                    "youtube_takeout": "YouTube (Takeout)",
                    "google_takeout_other": "Takeout (otros)",
                    "google_takeout": "Takeout",
                }.get(f.get("source", ""), f.get("source", "?"))

                size = self._format_size(f.get("size", 0))
                md5_short = (f.get("md5", "") or "—")[:12]
                sha_short = (f.get("sha256", "") or "—")[:12]

                self.tree.insert(
                    parent_id, "end",
                    text=f"{f.get('name', '?')}  [{source_label}, {size}]",
                    values=("", "", f"MD5: {md5_short}…  SHA: {sha_short}…", ""),
                )

        # Habilitar botones de reportes
        self.btn_open_html.config(state="normal")
        self.btn_open_csv.config(state="normal")
        self.btn_open_json.config(state="normal")

        # Cambiar a pestaña de resultados
        self.notebook.select(1)

    def _open_report(self, ext: str):
        """Abre un reporte con la aplicación predeterminada del sistema."""
        if not self.report_base:
            return
        path = f"{self.report_base}.{ext}"
        if not os.path.exists(path):
            path = str(PROJECT_DIR / path)
            if not os.path.exists(path):
                return

        # Abrir con la aplicación predeterminada
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
        """Envía un mensaje a la cola de logs."""
        self.log_queue.put(msg)

    def _clear_logs(self):
        """Limpia el área de logs."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _poll_log_queue(self):
        """Procesa mensajes de la cola de logs (ejecutado periódicamente)."""
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


def main():
    root = tk.Tk()

    # Estilo ttk
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Configurar estilo
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
