#!/usr/bin/env python3
"""
media_dedupe_web.py — Lanzador de la GUI web local de Media Dedupe.

Arranca un servidor Flask local y abre el navegador en la vista de revisión.
Sustituye a la antigua GUI Tkinter.

Uso:
    python media_dedupe_web.py [--port 5000] [--no-browser]
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import webbrowser

# Asegurar que la raíz del proyecto esté en sys.path aunque se lance desde otra cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.paths import crear_directorios
from webgui import create_app

logging.basicConfig(level=logging.INFO, format="%(message)s")


def _puerto_libre(preferido: int) -> int:
    """Devuelve `preferido` si está libre; si no, un puerto efímero disponible."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferido))
            return preferido
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description="GUI web local de Media Dedupe")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador automáticamente")
    args = parser.parse_args()

    crear_directorios()
    puerto = _puerto_libre(args.port)
    url = f"http://127.0.0.1:{puerto}"

    app = create_app()
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"\n  Media Dedupe — revisor web en {url}")
    print("  (Ctrl+C para detener)\n")
    app.run(host="127.0.0.1", port=puerto, debug=False, threaded=True)


if __name__ == "__main__":
    main()
