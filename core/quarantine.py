"""
quarantine.py — Sesiones reversibles de cuarentena para archivos locales.

Mueve archivos locales seleccionados a `reports/quarantine/<sesión>/files/`
guardando un manifiesto con el SHA-256 de cada uno. La restauración verifica el
hash antes de devolver el archivo a su ruta original.

Extraído de la antigua GUI Tkinter para poder reutilizarlo desde el backend web
y probarlo sin dependencias de interfaz gráfica.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config.paths import REPORTES_QUARANTINE
from core.hashing import sha256_file

logger = logging.getLogger("media_dedupe")


class GestorCuarentena:
    """Mueve archivos locales a una sesión reversible de cuarentena."""

    def __init__(self, raiz: Optional[Path] = None):
        self.raiz = Path(raiz) if raiz is not None else Path(REPORTES_QUARANTINE)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def mover(self, archivos: List[dict]) -> tuple[int, list[str], Optional[Path]]:
        """Mueve a cuarentena los archivos indicados (cada dict con clave 'path')."""
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
                    "sha256": sha256_file(str(target)),
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
        logger.info("Cuarentena: %d archivo(s) movidos a %s", len(moved), session)
        return len(moved), errors, session

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

    def restaurar(self, session_name: str, indices: Optional[list[int]] = None) -> tuple[int, list[str]]:
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
                if expected_hash and sha256_file(str(source)) != expected_hash:
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
