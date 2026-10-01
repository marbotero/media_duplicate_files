"""
app.py — Backend Flask de la GUI web local.

Sirve una SPA para revisar el reporte de duplicados (miniaturas, comparación
lado a lado, scroll nativo) y ejecutar acciones locales (cuarentena, escaneo).

No reimplementa la detección: escanea llamando al CLI `media_dedupe.py` y consume
el reporte JSON. El acceso a archivos locales se hace SOLO a través de claves
opacas resueltas contra las rutas presentes en el reporte cargado (nunca acepta
rutas arbitrarias del cliente).
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, Response, abort, jsonify, render_template, request, send_file

from config.paths import MEDIA_DEDUPE_PY, REPORTE_JSON, SECRETOS_ACCOUNTS
from core.quarantine import GestorCuarentena
from core.thumbnails import generar_miniatura


def file_key(archivo: dict) -> str:
    """Clave opaca y estable para un archivo del reporte (independiente del orden)."""
    base = "|".join([
        archivo.get("source", "") or "",
        archivo.get("item_id", "") or "",
        archivo.get("path", "") or "",
        archivo.get("web_url", "") or "",
    ])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


class _EstadoEscaneo:
    """Mantiene el proceso de escaneo activo y su log en vivo para SSE."""

    def __init__(self):
        self.proceso: Optional[subprocess.Popen] = None
        self.cola: "queue.Queue[str]" = queue.Queue()
        self.activo = False
        self.lock = threading.Lock()


def create_app() -> Flask:
    app = Flask(__name__)
    # Recargar plantillas sin reiniciar (cómodo al iterar la GUI localmente).
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    gestor = GestorCuarentena()
    registro: dict[str, str] = {}          # key -> ruta local absoluta existente
    registro_lock = threading.Lock()
    escaneo = _EstadoEscaneo()

    # ── Carga del reporte ──────────────────────────────────────────────────
    def cargar_reporte(path: str) -> dict:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        nuevo: dict[str, str] = {}
        for grupo in data.get("groups", []):
            for archivo in grupo.get("files", []):
                key = file_key(archivo)
                archivo["_key"] = key
                ruta = archivo.get("path")
                es_local = bool(ruta) and os.path.isfile(ruta)
                archivo["_local"] = es_local
                if es_local:
                    nuevo[key] = os.path.abspath(ruta)
        with registro_lock:
            registro.clear()
            registro.update(nuevo)
        return data

    def ruta_de_key(key: str) -> str:
        with registro_lock:
            ruta = registro.get(key)
        if not ruta or not os.path.isfile(ruta):
            abort(404)
        return ruta

    # ── Vistas ─────────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/report")
    def api_report():
        path = request.args.get("path") or str(REPORTE_JSON)
        if not os.path.isfile(path):
            return jsonify({"error": "No existe el reporte", "path": path}), 404
        try:
            return jsonify(cargar_reporte(path))
        except Exception as e:
            return jsonify({"error": f"No se pudo leer el reporte: {e}"}), 500

    @app.route("/api/thumbnail")
    def api_thumbnail():
        ruta = ruta_de_key(request.args.get("key", ""))
        data = generar_miniatura(ruta)
        if data is None:
            abort(404)
        return Response(data, mimetype="image/jpeg")

    @app.route("/api/file")
    def api_file():
        ruta = ruta_de_key(request.args.get("key", ""))
        return send_file(ruta)

    # ── Cuarentena ───────────────────────────────────────────────────────
    @app.route("/api/quarantine", methods=["POST"])
    def api_quarantine():
        keys = (request.get_json(silent=True) or {}).get("keys", [])
        archivos = []
        with registro_lock:
            for key in keys:
                ruta = registro.get(key)
                if ruta:
                    archivos.append({"path": ruta})
        if not archivos:
            return jsonify({"moved": 0, "errors": ["Ningún archivo local seleccionado."], "session": None})
        movidos, errores, session = gestor.mover(archivos)
        return jsonify({
            "moved": movidos,
            "errors": errores,
            "session": session.name if session else None,
        })

    @app.route("/api/quarantine/sessions")
    def api_quarantine_sessions():
        sesiones = []
        for s in gestor.sesiones():
            sesiones.append({"name": s.name, "count": len(gestor.archivos_sesion(s.name))})
        return jsonify({"sessions": sesiones})

    @app.route("/api/quarantine/restore", methods=["POST"])
    def api_quarantine_restore():
        body = request.get_json(silent=True) or {}
        session = body.get("session")
        indices = body.get("indices")
        if not session:
            return jsonify({"restored": 0, "errors": ["Falta la sesión."]}), 400
        restaurados, errores = gestor.restaurar(session, indices)
        return jsonify({"restored": restaurados, "errors": errores})

    @app.route("/api/quarantine/delete", methods=["POST"])
    def api_quarantine_delete():
        session = (request.get_json(silent=True) or {}).get("session")
        if not session:
            return jsonify({"ok": False, "error": "Falta la sesión."}), 400
        gestor.eliminar_sesion(session)
        return jsonify({"ok": True})

    # ── Escaneo (CLI vía subprocess + log en vivo por SSE) ─────────────────
    def _lanzar_escaneo(comando: list[str]):
        def ejecutar():
            try:
                proc = subprocess.Popen(
                    comando,
                    cwd=str(Path(MEDIA_DEDUPE_PY).parent),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                with escaneo.lock:
                    escaneo.proceso = proc
                for linea in proc.stdout:
                    escaneo.cola.put(linea.rstrip("\n"))
                proc.wait()
                escaneo.cola.put(f"__FIN__ {proc.returncode}")
            except Exception as e:
                escaneo.cola.put(f"__ERROR__ {e}")
            finally:
                escaneo.activo = False
                with escaneo.lock:
                    escaneo.proceso = None

        escaneo.activo = True
        threading.Thread(target=ejecutar, daemon=True).start()

    @app.route("/api/scan", methods=["POST"])
    def api_scan():
        if escaneo.activo:
            return jsonify({"ok": False, "error": "Ya hay un escaneo en curso."}), 409
        cfg = request.get_json(silent=True) or {}
        comando = [sys.executable, str(MEDIA_DEDUPE_PY), "scan"]
        for carpeta in cfg.get("local_folders", []):
            comando += ["--local-folder", carpeta]
        for src in cfg.get("sources", []):
            comando += ["--source", src]
        if cfg.get("whatsapp_folder"):
            comando += ["--whatsapp-folder", cfg["whatsapp_folder"]]
        if cfg.get("google_takeout_folder"):
            comando += ["--google-takeout-folder", cfg["google_takeout_folder"]]
        if cfg.get("hash_mode"):
            comando += ["--hash-mode", cfg["hash_mode"]]
        if cfg.get("image_threshold") is not None:
            comando += ["--image-threshold", str(cfg["image_threshold"])]
        if cfg.get("video_threshold") is not None:
            comando += ["--video-threshold", str(cfg["video_threshold"])]
        if cfg.get("skip_similar"):
            comando += ["--skip-similar"]
        if cfg.get("report"):
            comando += ["--report", cfg["report"]]
        # Vaciar cola previa
        while not escaneo.cola.empty():
            escaneo.cola.get_nowait()
        _lanzar_escaneo(comando)
        return jsonify({"ok": True, "command": " ".join(comando)})

    @app.route("/api/scan/stream")
    def api_scan_stream():
        def stream():
            while True:
                try:
                    linea = escaneo.cola.get(timeout=30)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(linea)}\n\n"
                if linea.startswith("__FIN__") or linea.startswith("__ERROR__"):
                    break
        return Response(stream(), mimetype="text/event-stream")

    @app.route("/api/scan/cancel", methods=["POST"])
    def api_scan_cancel():
        with escaneo.lock:
            proc = escaneo.proceso
        if not proc:
            return jsonify({"ok": False, "error": "No hay escaneo activo."})
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               capture_output=True, timeout=10)
            else:
                proc.terminate()
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
        return jsonify({"ok": True})

    @app.route("/api/auth", methods=["POST"])
    def api_auth():
        body = request.get_json(silent=True) or {}
        proveedor = body.get("provider")
        if proveedor not in {"google-drive", "google-photos", "onedrive"}:
            return jsonify({"ok": False, "error": "Proveedor no válido."}), 400
        comando = [sys.executable, str(MEDIA_DEDUPE_PY), "auth", proveedor]
        if body.get("profile"):
            flag = "--google-profile" if proveedor.startswith("google") else "--onedrive-profile"
            comando += [flag, body["profile"]]
        if escaneo.activo:
            return jsonify({"ok": False, "error": "Hay un proceso en curso."}), 409
        while not escaneo.cola.empty():
            escaneo.cola.get_nowait()
        _lanzar_escaneo(comando)
        return jsonify({"ok": True})

    @app.route("/api/profiles")
    def api_profiles():
        raiz = Path(SECRETOS_ACCOUNTS)
        salida = {}
        for proveedor in ("google", "onedrive"):
            carpeta = raiz / proveedor
            salida[proveedor] = sorted(p.name for p in carpeta.iterdir() if p.is_dir()) if carpeta.exists() else []
        return jsonify(salida)

    return app
