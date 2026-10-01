import json

from core.reports import to_csv, to_html, to_json
from core.cache import MediaCache
from core.quarantine import GestorCuarentena
from webgui import file_key


def test_empty_report_records_scan_status(tmp_path):
    output = tmp_path / "report.json"

    to_json([], str(output), "partial", ["Drive: timeout"], 12)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["groups"] == []
    assert data["scan_status"] == "partial"
    assert data["scan_errors"] == ["Drive: timeout"]
    assert data["scanned_items"] == 12


def test_file_key_is_stable_and_distinct():
    first = {"source": "local_folder", "item_id": "a.jpg", "path": "C:/a.jpg"}
    second = {"source": "local_folder", "item_id": "b.jpg", "path": "C:/b.jpg"}

    assert file_key(first) == file_key(dict(first))   # estable
    assert file_key(first) != file_key(second)          # distintos archivos


def test_quarantine_moves_and_restores_file(tmp_path):
    original = tmp_path / "media" / "foto.jpg"
    original.parent.mkdir()
    original.write_bytes(b"media-data")

    quarantine = GestorCuarentena(tmp_path / "quarantine")
    moved, errors, session = quarantine.mover([{"path": str(original)}])

    assert moved == 1
    assert errors == []
    assert session is not None
    assert not original.exists()
    assert (session / "manifest.json").exists()

    restored, errors = quarantine.restaurar_ultima()

    assert restored == 1
    assert errors == []
    assert original.read_bytes() == b"media-data"


def test_empty_report_status_is_visible_in_csv_and_html(tmp_path):
    csv_output = tmp_path / "report.csv"
    html_output = tmp_path / "report.html"

    to_csv([], str(csv_output), "partial", ["OneDrive: timeout"], 7)
    to_html([], str(html_output), "partial", ["OneDrive: timeout"], 7, {"onedrive": 7})

    csv_text = csv_output.read_text(encoding="utf-8")
    html_text = html_output.read_text(encoding="utf-8")
    assert "estado_escaneo" in csv_text
    assert "partial" in csv_text
    assert "OneDrive: timeout" in csv_text
    assert "Escaneo parcial" in html_text
    assert "OneDrive: timeout" in html_text
    assert "Archivos analizados:</strong> 7" in html_text
    assert "Archivos por proveedor" in html_text
    assert "onedrive" in html_text

def test_quarantine_supports_selective_restore_and_delete(tmp_path):
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    quarantine = GestorCuarentena(tmp_path / "quarantine")
    moved, errors, session = quarantine.mover([
        {"path": str(first)}, {"path": str(second)},
    ])
    assert moved == 2
    assert errors == []

    restored, errors = quarantine.restaurar(session.name, [0])
    assert restored == 1
    assert errors == []
    assert first.read_bytes() == b"first"
    assert not second.exists()
    assert len(quarantine.archivos_sesion(session.name)) == 1

    quarantine.eliminar_sesion(session.name)
    assert not session.exists()


def test_cache_persists_perceptual_hashes_in_one_transaction(tmp_path):
    cache = MediaCache(str(tmp_path / "cache.db"))
    cache.put(
        "local_folder", "foto.jpg", 5, "mtime",
        md5="md5", sha256="sha", phash="abcd", video_frame_hashes=["frame"],
        commit=False,
    )
    cache.commit()

    data = cache.get("local_folder", "foto.jpg", 5, "mtime")
    cache.close()
    assert data["phash"] == "abcd"
    assert data["video_frame_hashes"] == ["frame"]