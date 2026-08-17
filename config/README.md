# ⚙️ Carpeta de Configuración

Esta carpeta centraliza todas las rutas y configuraciones del proyecto.

## 📄 Archivos

### `paths.py` - Rutas Centralizadas

Define todas las rutas del proyecto en un único módulo.

**Uso básico:**

```python
from config.paths import GOOGLE_DRIVE_TOKEN, REPORTES_JSON

# Cargar credenciales
with open(GOOGLE_DRIVE_TOKEN) as f:
    token = json.load(f)

# Cargar último reporte
with open(REPORTES_JSON) as f:
    datos = json.load(f)
```

**Rutas disponibles:**

```python
# Secretos
from config.paths import (
    SECRETOS_DIR,
    GOOGLE_DRIVE_CREDENTIALS,
    GOOGLE_DRIVE_TOKEN,
    GOOGLE_PHOTOS_TOKEN,
    ONEDRIVE_CONFIG,
    ONEDRIVE_TOKEN,
)

# Reportes
from config.paths import (
    REPORTES_DIR,
    REPORTES_CACHE,
    REPORTES_LATEST,
    REPORTES_EXAMPLES,
    REPORTES_ARCHIVE,
    MEDIA_CACHE_DB,
    REPORTE_JSON,
    REPORTE_HTML,
    REPORTE_CSV,
)
```

**Funciones de utilidad:**

```python
from config.paths import validar_rutas, crear_directorios

# Crear directorios si no existen
crear_directorios()

# Validar que todo está en su lugar
validar_rutas()
```

---

### `.env.example` - Variables de Entorno

Plantilla de configuración con variables de entorno.

**Uso:**

1. Copia `.env.example` a `.env`
2. Actualiza los valores con tus credenciales
3. Carga en tu código:

```python
from dotenv import load_dotenv
import os

load_dotenv("config/.env")
GOOGLE_DRIVE_ID = os.getenv("GOOGLE_DRIVE_CLIENT_ID")
```

---

## 🔄 Cómo Actualizar el Código Existente

### Paso 1: Importar rutas centralizadas

**Antes:**

```python
# Rutas hardcodeadas
TOKEN_PATH = "token_drive.json"
REPORTE_PATH = "reporte_duplicados.json"
```

**Después:**

```python
from config.paths import GOOGLE_DRIVE_TOKEN, REPORTE_JSON

TOKEN_PATH = GOOGLE_DRIVE_TOKEN
REPORTE_PATH = REPORTE_JSON
```

---

### Paso 2: En `providers/google_drive.py`

```python
# Cambiar esto:
def authenticate():
    # config = load_from("credentials.json")
    
# Por esto:
from config.paths import GOOGLE_DRIVE_CREDENTIALS, GOOGLE_DRIVE_TOKEN

def authenticate():
    with open(GOOGLE_DRIVE_CREDENTIALS) as f:
        config = json.load(f)
```

---

### Paso 3: En `media_dedupe.py`

```python
# Cambiar esto:
def save_report(data):
    with open("reporte_duplicados.json", "w") as f:
        json.dump(data, f)

# Por esto:
from config.paths import REPORTES_JSON, REPORTES_LATEST

def save_report(data):
    # Crear directorio si no existe
    REPORTES_LATEST.mkdir(parents=True, exist_ok=True)
    
    with open(REPORTES_JSON, "w") as f:
        json.dump(data, f)
```

---

### Paso 4: En `core/hashing.py` (caché)

```python
# Cambiar esto:
CACHE_DB = "media_cache.db"

# Por esto:
from config.paths import MEDIA_CACHE_DB

CACHE_DB = str(MEDIA_CACHE_DB)
```

---

## 📋 Checklist de Integración

- [ ] Actualizar `providers/google_drive.py` con rutas de config
- [ ] Actualizar `providers/onedrive.py` con rutas de config
- [ ] Actualizar `providers/google_photos.py` con rutas de config
- [ ] Actualizar `media_dedupe.py` para usar rutas centralizadas
- [ ] Actualizar `media_dedupe_gui_advance.py` para cargar reportes desde rutas
- [ ] Actualizar `core/hashing.py` para caché en nueva ubicación
- [ ] Probar que todo funciona: `python config/paths.py`
- [ ] Actualizar `.gitignore` si es necesario

---

## 🧪 Verificación

Ejecuta esto para verificar que todo está en su lugar:

```bash
python config/paths.py
```

**Salida esperada:**

```text
📁 ESTRUCTURA DEL PROYECTO

🔒 SECRETOS:
   ✓ google-drive.json
   ✓ google-drive-token.json
   ✓ google-photos-token.json
   ✓ onedrive-config.json
   ✓ onedrive-token.json

💾 CACHÉ:
   ✓ media_cache.db

📋 REPORTES ACTUALES:
   ✓ duplicados.json
   ✓ duplicados.html
   ✓ duplicados.csv

📚 EJEMPLOS:
   ✓ sample_reporte.json

✅ Todas las rutas están correctas
```

---

## 💡 Beneficios de esta Estructura

| Ventaja | Descripción |
| --------- | ------------- |
| 🔐 **Seguridad** | Secretos centralizados y protegidos |
| 🔧 **Mantenibilidad** | Una fuente de verdad para rutas |
| 🔄 **Portabilidad** | Fácil mover proyecto a otra ubicación |
| 📦 **Modularidad** | Cada módulo importa solo lo que necesita |
| 🧪 **Testing** | Fácil mockar rutas en tests |

---

## 🚀 Próximos Pasos

1. Ejecuta `python config/paths.py` para verificar
2. Actualiza gradualmente los módulos (ve checklist arriba)
3. Prueba cada módulo después de cambios
4. Elimina rutas hardcodeadas del código
