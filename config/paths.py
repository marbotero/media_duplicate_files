# 🔧 Configuración de Rutas - Media Dedupe

"""
Módulo centralizador de rutas del proyecto.
Actualiza automáticamente todos los imports para usar las nuevas carpetas.

Uso:
    from config.paths import SECRETOS_DIR, REPORTES_DIR
    
    # Cargar credenciales
    with open(SECRETOS_DIR / "credentials" / "google-drive.json") as f:
        config = json.load(f)
"""

from pathlib import Path
import os

# Raíz del proyecto
PROYECTO_ROOT = Path(__file__).parent.parent

# 🔐 SECRETOS Y CREDENCIALES
SECRETOS_DIR = PROYECTO_ROOT / "secrets"
SECRETOS_CREDENTIALS = SECRETOS_DIR / "credentials"

# Rutas individuales de credenciales
GOOGLE_DRIVE_CREDENTIALS = SECRETOS_CREDENTIALS / "google-drive.json"
GOOGLE_DRIVE_TOKEN = SECRETOS_CREDENTIALS / "google-drive-token.json"
GOOGLE_PHOTOS_TOKEN = SECRETOS_CREDENTIALS / "google-photos-token.json"
ONEDRIVE_CONFIG = SECRETOS_CREDENTIALS / "onedrive-config.json"
ONEDRIVE_TOKEN = SECRETOS_CREDENTIALS / "onedrive-token.json"

# 📊 REPORTES Y CACHÉ
REPORTES_DIR = PROYECTO_ROOT / "reports"
REPORTES_CACHE = REPORTES_DIR / "cache"
REPORTES_LATEST = REPORTES_DIR / "latest"
REPORTES_EXAMPLES = REPORTES_DIR / "examples"
REPORTES_ARCHIVE = REPORTES_DIR / "archive"

# Rutas de archivos de caché
MEDIA_CACHE_DB = REPORTES_CACHE / "media_cache.db"

# Rutas de reportes actuales
REPORTE_JSON = REPORTES_LATEST / "duplicados.json"
REPORTE_HTML = REPORTES_LATEST / "duplicados.html"
REPORTE_CSV = REPORTES_LATEST / "duplicados.csv"

# 📚 CÓDIGO Y DOCUMENTACIÓN (quedan en raíz)
CODIGO_DIR = PROYECTO_ROOT
CORE_DIR = CODIGO_DIR / "core"
PROVIDERS_DIR = CODIGO_DIR / "providers"
TESTS_DIR = CODIGO_DIR / "tests"

# Archivos principales
MEDIA_DEDUPE_PY = CODIGO_DIR / "media_dedupe.py"
GUI_ADVANCE = CODIGO_DIR / "media_dedupe_gui_advance.py"

# 📄 DOCUMENTACIÓN
README = CODIGO_DIR / "README.md"
REQUIREMENTS = CODIGO_DIR / "requirements.txt"


# ✅ FUNCIONES DE VALIDACIÓN

def validar_rutas():
    """Valida que todas las rutas existan."""
    paths_criticas = [
        SECRETOS_DIR,
        REPORTES_DIR,
        CORE_DIR,
        PROVIDERS_DIR,
    ]
    
    faltantes = []
    for ruta in paths_criticas:
        if not ruta.exists():
            faltantes.append(str(ruta))
    
    if faltantes:
        raise FileNotFoundError(
            f"Faltan carpetas críticas:\n" + 
            "\n".join(f"  ❌ {r}" for r in faltantes)
        )
    
    return True


def crear_directorios():
    """Crea directorios si no existen."""
    for ruta in [SECRETOS_CREDENTIALS, REPORTES_CACHE, REPORTES_LATEST, 
                 REPORTES_EXAMPLES, REPORTES_ARCHIVE]:
        ruta.mkdir(parents=True, exist_ok=True)


def listar_estructura():
    """Imprime la estructura de carpetas."""
    print("📁 ESTRUCTURA DEL PROYECTO\n")
    
    print("🔒 SECRETOS:")
    for archivo in SECRETOS_CREDENTIALS.glob("*.json"):
        print(f"   ✓ {archivo.name}")
    
    print("\n💾 CACHÉ:")
    for archivo in REPORTES_CACHE.glob("*"):
        if archivo.is_file():
            print(f"   ✓ {archivo.name}")
    
    print("\n📋 REPORTES ACTUALES:")
    for archivo in REPORTES_LATEST.glob("*"):
        if archivo.is_file():
            print(f"   ✓ {archivo.name}")
    
    print("\n📚 EJEMPLOS:")
    for archivo in REPORTES_EXAMPLES.glob("*"):
        if archivo.is_file():
            print(f"   ✓ {archivo.name}")


if __name__ == "__main__":
    crear_directorios()
    validar_rutas()
    listar_estructura()
    print("\n✅ Todas las rutas están correctas")
