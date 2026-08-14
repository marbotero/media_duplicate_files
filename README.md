# Media Dedupe — Detector de Duplicados Multi-origen

Programa en Python que detecta archivos duplicados y casi-duplicados en **Google Drive**, **Google Photos**, **Google Takeout**, **Microsoft OneDrive** y **WhatsApp** (carpeta local), con doble verificación de hashes **SHA-256 y MD5**.

## Tipos de detección

| Tipo | Método | Precisión |
|------|--------|-----------|
| Duplicados exactos | SHA-256 + MD5 + tamaño | 100% fiable |
| Imágenes similares | pHash (perceptual hash) + distancia Hamming | Detecta copias redimensionadas, recortadas, con marca de agua |
| Videos similares | Extracción de frames con ffmpeg + pHash | Detecta videos con diferente calidad/codec |

## Orígenes soportados

### Google Drive
- API v3 con OAuth2
- Usa `md5Checksum` de metadatos (sin descargar) + SHA-256 calculado
- Soporta Shared Drives y carpetas compartidas
- Recorrido recursivo con paginación

### Microsoft OneDrive
- Microsoft Graph API con MSAL (Microsoft Authentication Library)
- Usa hashes de Graph API cuando disponibles + SHA-256/MD5 calculados
- Recorrido recursivo de carpetas

### WhatsApp (carpeta local)
- **No necesita OAuth** — solo acceso al sistema de archivos
- Soporta:
  - Carpeta de WhatsApp Desktop (Windows/Mac)
  - Exportación de chat con medios
  - Carpeta del teléfono conectado por USB (Android)
- Calcula MD5 y SHA-256 directamente del archivo local
- Escanea subcarpetas: `WhatsApp Images`, `WhatsApp Video`, `WhatsApp Animated Gifs`, `WhatsApp Documents`

> **Nota sobre WhatsApp:** WhatsApp no expone una API pública para recorrer fotos del backup. Los backups cifrados de WhatsApp en Google Drive no se pueden navegar como archivos individuales. Este programa funciona con las fotos almacenadas en una carpeta local accesible desde tu equipo.

### Google Takeout (completo)

Soporta la exportación completa de Google Takeout, incluyendo todos los productos de Google con medios:

| Carpeta de Takeout | Source en reporte |
|-------------------|------------------|
| `Google Photos/` | google_photos_takeout |
| `Drive/` | google_drive_takeout |
| `YouTube and YouTube Music/` | youtube_takeout |
| `Google Chat/` | google_chat_takeout |
| `Hangouts/` | hangouts_takeout |
| `Keep/` | google_keep_takeout |
| `Blogger/` | blogger_takeout |
| (otros) | google_takeout_other |

**Características:**
- Recorre recursivamente toda la carpeta de Takeout
- Detecta automáticamente el producto de cada archivo según su carpeta
- Parsea archivos JSON sidecar de Google Photos (metadatos: fecha, URL original)
- Calcula MD5 y SHA-256 directamente de los archivos locales
- Detecta duplicados entre diferentes productos de Google (ej: misma foto en Google Photos y Drive)

**Cómo obtenerlo:**
1. Ve a [Google Takeout](https://takeout.google.com/)
2. Deselecciona todo y marca solo los productos con medios (Photos, Drive, YouTube, etc.)
3. Descarga el archivo ZIP
4. Extrae el ZIP a una carpeta local
5. Usa esa carpeta:
```bash
python media_dedupe.py auth google-takeout --google-takeout-folder /ruta/Takeout
python media_dedupe.py scan --google-takeout-folder /ruta/Takeout --report reporte
```

### Google Photos (API)

Dos formas de usar Google Photos:

**Opción A: API (medios seleccionados o subidos por la app)**

1. Reutiliza el mismo `credentials.json` de Google Drive.
2. Habilita **Photos Library API** en Google Cloud Console.
3. Autentica con:
```bash
python media_dedupe.py auth google-photos --photos-mode app-created
```

Modos disponibles:
- `app-created`: lista solo medios subidos por esta app (rapido, limitado).
- `picker`: abre el selector de Google Photos para que elijas que fotos analizar.

> **Limitacion de la API (2025):** Google ha restringido el acceso completo a la biblioteca de fotos para nuevas apps. El modo `app-created` solo lista lo subido por la app; el modo `picker` requiere seleccion manual. No es posible recorrer toda la biblioteca automaticamente con la API actual.

**Opcion B: Takeout (biblioteca completa, recomendado)**

Usa `--google-takeout-folder` (ver seccion anterior) o `--google-photos-folder` para escanear solo la carpeta de Google Photos dentro del Takeout:
```bash
python media_dedupe.py scan --google-photos-folder /ruta/Takeout/Google\ Photos --report reporte
```

Esta opcion permite analizar TODA tu biblioteca de Google Photos sin limitaciones de la API.

## Requisitos previos

### Python 3.9+
```bash
python --version
```

### ffmpeg y ffprobe
Necesario para procesamiento de videos.

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Windows:**
Descarga desde https://ffmpeg.org/download.html y añádelo al PATH.

### Dependencias de Python
```bash
pip install -r requirements.txt
```

## Configuración

### Google Drive API

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto y habilita **Google Drive API**.
3. Ve a **Credenciales > Crear credenciales > ID de cliente OAuth**.
4. Tipo: **Aplicación de escritorio**.
5. Descarga el JSON, renómbralo como `credentials.json` y colócalo en la carpeta del programa.

### Microsoft OneDrive (Graph API)

1. Ve a [Microsoft Entra ID](https://entra.microsoft.com/) (Azure Portal).
2. **App registrations > New registration**.
3. Tipo de cuenta: **Personal** (para OneDrive personal).
4. Redirect URI: `http://localhost`.
5. **API Permissions > Add permission > Microsoft Graph > Delegated > Files.Read.All**.
6. Copia el **Application (client) ID**.
7. Crea un archivo `onedrive_config.json`:
```json
{
  "client_id": "tu-client-id-aqui",
  "tenant": "consumers"
}
```

### WhatsApp

No requiere configuración de API. Solo necesitas la ruta a la carpeta de medios:
- **Windows:** `C:\Users\TU_USUARIO\Downloads\WhatsApp` o similar
- **macOS:** `~/Downloads/WhatsApp` o `~/Library/Containers/...`
- **Android por USB:** Copia la carpeta `WhatsApp/Media` al PC
- **Exportación de chat:** Usa la carpeta extraída del ZIP

### Google Takeout y Google Photos

Ver las secciones **Google Takeout (completo)** y **Google Photos (API)** más arriba en este documento para configuración detallada.

## Uso

### 1. Autenticar (primera vez)

```bash
# Google Drive
python media_dedupe.py auth google-drive

# OneDrive
python media_dedupe.py auth onedrive

# Google Photos (API)
python media_dedupe.py auth google-photos --photos-mode app-created
python media_dedupe.py auth google-photos --photos-mode picker

# Verificar carpeta de WhatsApp
python media_dedupe.py auth whatsapp --whatsapp-folder /ruta/WhatsApp/Media

# Verificar carpeta de Google Takeout completo
python media_dedupe.py auth google-takeout --google-takeout-folder /ruta/Takeout
```

### 2. Escanear

```bash
# Todos los orígenes
python media_dedupe.py scan \
  --source google-drive \
  --source onedrive \
  --source google-photos \
  --whatsapp-folder /ruta/WhatsApp/Media \
  --google-takeout-folder /ruta/Takeout \
  --report reporte

# Solo Google Drive
python media_dedupe.py scan --source google-drive --report reporte

# Solo OneDrive
python media_dedupe.py scan --source onedrive --report reporte

# Solo Google Photos (API)
python media_dedupe.py scan --source google-photos --photos-mode app-created --report reporte

# Solo Google Photos (Takeout)
python media_dedupe.py scan --google-photos-folder /ruta/Takeout/Google\ Photos --report reporte

# Solo WhatsApp
python media_dedupe.py scan --whatsapp-folder /ruta/WhatsApp/Media --report reporte

# Google Drive + WhatsApp
python media_dedupe.py scan --source google-drive --whatsapp-folder /ruta/WhatsApp --report reporte
```

### 3. Opciones avanzadas

```bash
# Modo rápido (solo metadatos de la API, sin descargar)
python media_dedupe.py scan --source google-drive --hash-mode metadata

# Modo preciso (descarga y calcula MD5 + SHA-256) — por defecto
python media_dedupe.py scan --source google-drive --source onedrive --hash-mode full

# Carpeta específica de Drive
python media_dedupe.py scan --source google-drive --drive-root 1a2b3c4d5e6f

# Ajustar sensibilidad
python media_dedupe.py scan --source google-drive --image-threshold 8 --video-threshold 0.80

# Solo duplicados exactos (sin análisis perceptual)
python media_dedupe.py scan --source google-drive --skip-similar
```

## Parámetros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--source` | Origen cloud (repetir para múltiples) | — |
| `--whatsapp-folder` | Carpeta local de WhatsApp | — |
| `--drive-root` | ID de carpeta raíz en Drive | Toda la unidad |
| `--onedrive-root` | ID de carpeta en OneDrive | Toda la unidad |
| `--hash-mode` | `metadata` (rápido) o `full` (preciso) | `full` |
| `--image-threshold` | Distancia Hamming para imágenes | `5` |
| `--video-threshold` | Ratio de similitud para videos | `0.85` |
| `--video-frames` | Frames extraídos por video | `8` |
| `--skip-similar` | Solo duplicados exactos | `false` |
| `--report` | Nombre base del reporte | `reporte_duplicados` |
| `--cache-db` | Base de datos de caché | `media_cache.db` |

## Reportes generados

| Archivo | Descripción |
|---------|-------------|
| `reporte.json` | Datos completos en JSON |
| `reporte.csv` | Tabla para Excel/Google Sheets |
| `reporte.html` | Reporte visual con colores, badges por origen y enlaces directos |

Cada archivo en el reporte incluye: nombre, origen (Drive/OneDrive/WhatsApp), tipo MIME, tamaño, MD5, SHA-256 y enlace o ruta.

## Caché SQLite

El programa usa una caché SQLite (`media_cache.db`) para evitar recalcular hashes y redescargar archivos en ejecuciones posteriores. Clave: `(source, item_id, size, modified_time)`. Si un archivo no ha cambiado, se reutilizan sus hashes.

## Umbrales de similitud

### Imágenes (pHash)
| Distancia Hamming | Interpretación |
|-------------------|---------------|
| 0 | Imagen idéntica |
| 1–4 | Casi idéntica |
| 5–8 | Muy parecida |
| 9–12 | Posible similitud (revisar) |
| >12 | Diferente |

### Videos
| Ratio | Interpretación |
|-------|---------------|
| 1.0 | Todos los frames coinciden |
| 0.85–0.99 | Casi idénticos |
| 0.70–0.84 | Muy parecidos |
| <0.70 | Diferentes |

## Seguridad

- El programa **NO borra ni mueve archivos**. Solo lee y reporta.
- Permisos de solo lectura en todos los providers.
- Los archivos se descargan temporalmente y se eliminan tras procesarlos.
- Las credenciales OAuth se guardan localmente.

## Interfaz gráfica (GUI)

El programa incluye una interfaz gráfica en Tkinter que permite ejecutar los escaneos sin usar la línea de comandos:

```bash
python media_dedupe_gui.py
```

### Características de la GUI

- **Pestaña Configuración**: selecciona orígenes con checkboxes, busca carpetas locales con diálogo nativo, configura umbrales y modo de hash.
- **Pestaña Resultados**: muestra un resumen con grupos encontrados y espacio recuperable, árbol navegable con cada grupo y sus archivos (nombre, origen, tamaño, MD5, SHA-256).
- **Pestaña Logs**: salida en vivo del proceso de escaneo.
- **Botones de autenticación**: autentica cada provider (Drive, OneDrive, Photos) directamente desde la GUI.
- **Botón de confirmación del Picker**: si usas Google Photos en modo `picker`, aparece un botón para confirmar la selección.
- **Botones de reportes**: abre los reportes HTML, CSV y JSON con la aplicación predeterminada del sistema.
- **Barra de progreso** indeterminada durante el escaneo.
- **Botón Detener**: interrumpe el escaneo en cualquier momento.

> La GUI ejecuta el CLI (`media_dedupe.py scan ...`) en segundo plano. No reimplementa la lógica de escaneo, por lo que todo el comportamiento (caché, providers, reportes) es idéntico al CLI.

## Estructura del proyecto

```
media-dedupe/
├── media_dedupe.py          # CLI principal
├── media_dedupe_gui.py      # GUI en Tkinter (interfaz gráfica)
├── requirements.txt         # Dependencias
├── README.md                # Este archivo
├── providers/
│   ├── __init__.py
│   ├── base.py              # Interfaz común + MediaItem
│   ├── google_drive.py      # Provider Google Drive (API)
│   ├── google_photos.py     # Provider Google Photos (API + Picker)
│   ├── google_takeout.py    # Provider Google Takeout completo
│   ├── onedrive.py          # Provider OneDrive (Graph API)
│   ├── whatsapp_local.py    # Provider WhatsApp (carpeta local)
│   └── router.py            # Router para despacho por origen
├── core/
│   ├── __init__.py
│   ├── hashing.py           # Cálculo MD5 + SHA-256
│   ├── similarity.py        # pHash + detección de duplicados
│   ├── cache.py             # Caché SQLite
│   └── reports.py            # Generación de CSV/JSON/HTML
├── credentials.json         # OAuth Google (tú lo descargas)
├── onedrive_config.json     # Config OneDrive (tú lo creas)
├── token_drive.json         # Token Google Drive (auto-generado)
├── token_photos.json        # Token Google Photos (auto-generado)
└── media_cache.db           # Caché SQLite (auto-generado)
```

## Limitaciones

- La detección de casi-duplicados requiere descargar archivos temporalmente (consume ancho de banda).
- Para volúmenes grandes (>10,000 archivos), el proceso puede tardar horas.
- Los backups cifrados de WhatsApp en Google Drive no son navegables archivo por archivo.
- La API de OneDrive puede no proporcionar hashes para todos los archivos; en ese caso se calculan al descargar.
- La detección de videos es aproximada (compara un subconjunto de frames, no el video completo).
