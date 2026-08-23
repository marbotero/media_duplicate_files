# Media Dedupe

Detector de duplicados y casi-duplicados de imagenes y videos para carpetas locales, WhatsApp, Google Drive, Google Photos, Google Takeout y Microsoft OneDrive.

El programa se ejecuta desde la consola y solo lee archivos multimedia para generar reportes. Antes de escribir un nuevo reporte, puede mover reportes anteriores de `latest` a `archive`; no mueve ni elimina archivos multimedia. La GUI disponible es la avanzada y sirve para revisar un reporte y gestionar archivos locales.

## Requisitos

- Python 3.9 o posterior.
- `ffmpeg` y `ffprobe` para analizar videos.
- ExifTool recomendado para extraer todos los metadatos EXIF, XMP, IPTC, RAW y de video.
- Credenciales solo para los servicios cloud.

### Instalar dependencias

Clona el repositorio y entra en la carpeta raíz del proyecto antes de crear el entorno virtual.

```bash
cd media_duplicate_files
python -m venv .venv
```

#### Activar la venv

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
.venv\Scripts\activate.bat
```

Linux o macOS:

```bash
source .venv/bin/activate
```

#### Instalar paquetes del proyecto

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

#### Usarla desde VS Code

Si abres el proyecto en VS Code, selecciona el intérprete del entorno virtual:

1. Presiona `Ctrl+Shift+P`
2. Elige `Python: Select Interpreter`
3. Selecciona la opción que apunte a `.venv` dentro de la raíz del proyecto

Esto hace que las terminales, el depurador y el autocompletado usen la misma Python del proyecto.

Instala las herramientas externas con tu gestor habitual:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg libimage-exiftool-perl

# macOS
brew install ffmpeg exiftool
```

En Windows, descarga [FFmpeg](https://ffmpeg.org/download.html) y [ExifTool](https://exiftool.org/), y agrega sus ejecutables al `PATH`.

Comprueba la instalacion:

```bash
python --version
ffmpeg -version
exiftool -ver
```

## Configuracion de credenciales

Las credenciales se guardan en `secrets/accounts/<proveedor>/<perfil>/` y no deben subirse al repositorio.

### Google Drive y Google Photos

1. Crea un proyecto en [Google Cloud Console](https://console.cloud.google.com/).
2. Habilita Google Drive API y, si usaras la API de Photos, Photos Library API.
3. Crea credenciales OAuth de tipo aplicacion de escritorio.
4. Guarda el JSON descargado dentro de `secrets/accounts/google/<perfil>/google-drive.json`.
5. Ejecuta la autenticacion:

```bash
python media_dedupe.py auth google-drive
python media_dedupe.py auth google-photos --photos-mode app-created --google-profile boteroestradamarcelo
```

Para otra cuenta de Google, cambia el perfil por la parte anterior a `@` del correo:

```bash
python media_dedupe.py auth google-drive --google-profile otra_cuenta
python media_dedupe.py auth google-photos --photos-mode app-created --google-profile otra_cuenta
```

Google Photos limita la API para aplicaciones nuevas. `app-created` solo muestra medios creados por esta aplicacion y `picker` requiere seleccion manual. Para analizar toda la biblioteca, usa Google Takeout.

### OneDrive

1. Registra una aplicacion en [Microsoft Entra ID](https://entra.microsoft.com/).
2. Usa una URI de redireccion `http://localhost`.
3. Concede el permiso delegado `Files.Read.All` de Microsoft Graph.
4. Crea `secrets/accounts/onedrive/<perfil>/onedrive-config.json`:

```json
{
  "client_id": "tu-application-client-id",
  "tenant": "consumers"
}
```

1. Autentica:

```bash
python media_dedupe.py auth onedrive
```

Para otra cuenta de OneDrive:

```bash
python media_dedupe.py auth onedrive --onedrive-profile otra_cuenta
```

### Origenes locales

WhatsApp, Google Takeout y carpetas locales no necesitan OAuth:

```bash
python media_dedupe.py auth whatsapp --whatsapp-folder "C:\\Users\\TuUsuario\\Downloads\\WhatsApp"
python media_dedupe.py auth google-takeout --google-takeout-folder "C:\\Takeout"
```

## Uso desde la consola

### Escaneos basicos

El reporte predeterminado se guarda en `reports/latest/duplicados.{json,csv,html}`.

```bash
# Carpeta local
python media_dedupe.py scan --local-folder "C:\\Fotos"

# Varias carpetas locales
python media_dedupe.py scan --local-folder "C:\\Fotos" --local-folder "D:\\Backup\\Fotos"

# WhatsApp
python media_dedupe.py scan --whatsapp-folder "C:\\WhatsApp\\Media"

# Google Takeout completo
python media_dedupe.py scan --google-takeout-folder "C:\\Takeout"

# Solo Google Photos dentro de Takeout
python media_dedupe.py scan --google-photos-folder "C:\\Takeout\\Google Photos"

# Google Drive
python media_dedupe.py scan --source google-drive --google-profile boteroestradamarcelo

# OneDrive
python media_dedupe.py scan --source onedrive --onedrive-profile botero_estrada_marcelo

# Google Photos API
python media_dedupe.py scan --source google-photos --photos-mode picker
```

### Combinar origenes

Puedes repetir `--source` y combinarlo con carpetas locales:

```bash
python media_dedupe.py scan \
  --source google-drive \
  --source onedrive \
  --google-profile boteroestradamarcelo \
  --onedrive-profile botero_estrada_marcelo \
  --whatsapp-folder "C:\\WhatsApp\\Media" \
  --local-folder "D:\\Fotos" \
  --report "reports/latest/multi_origen"
```

En PowerShell, el caracter de continuacion es el acento grave:

```powershell
python media_dedupe.py scan `
  --source google-drive `
  --local-folder "D:\Fotos" `
  --report "reports/latest/multi_origen"
```

### Modos y sensibilidad

```bash
# Solo duplicados exactos; no calcula similitud perceptual
python media_dedupe.py scan --local-folder "C:\\Fotos" --skip-similar

# Rapido: usa hashes disponibles en la API
python media_dedupe.py scan --source google-drive --hash-mode metadata

# Completo: descarga y calcula MD5 y SHA-256
python media_dedupe.py scan --source google-drive --hash-mode full

# Imagenes casi identicas
python media_dedupe.py scan --local-folder "C:\\Fotos" --image-threshold 98

# Imagenes similares con un criterio mas amplio
python media_dedupe.py scan --local-folder "C:\\Fotos" --image-threshold 90

# Videos similares
python media_dedupe.py scan --local-folder "C:\\Videos" --video-threshold 0.80 --video-frames 8

# Limitar una carpeta concreta de Drive o OneDrive
python media_dedupe.py scan --source google-drive --drive-root ID_DE_CARPETA
python media_dedupe.py scan --source onedrive --onedrive-root ID_DE_CARPETA
```

Los valores orientativos de imagen son: `98` para variantes casi identicas, `95` para recortes o redimensionados y `90` para coincidencias mas amplias con mas falsos positivos. El programa usa pHash para imagenes y frames con ffmpeg para videos.

Consulta siempre las opciones disponibles en la version instalada:

```bash
python media_dedupe.py --help
python media_dedupe.py scan --help
python media_dedupe.py auth --help
```

## Reportes y cache

Cada escaneo genera tres formatos:

| Archivo | Uso |
| --- | --- |
| `duplicados.json` | Datos completos, grupos, hashes y metadatos |
| `duplicados.csv` | Analisis en Excel o Google Sheets; incluye estado, errores y archivos analizados |
| `duplicados.html` | Consulta visual en el navegador; muestra estado, errores, archivos analizados y resumen por proveedor |

El JSON incluye `scan_status` (`complete` o `partial`), `scan_errors` y `scanned_items`. Un escaneo sin duplicados también genera reportes vacíos, por lo que `latest` no conserva resultados antiguos.

Ubicaciones predeterminadas:

- `reports/latest/`: ultimos reportes.
- `reports/cache/media_cache.db`: cache SQLite de hashes y descargas.
- `reports/archive/`: histórico automático de reportes anteriores, organizado por fecha.
- `reports/quarantine/`: sesiones reversibles de archivos locales enviados desde la GUI.

Antes de generar un nuevo reporte en `reports/latest/`, los archivos existentes se mueven automáticamente a una carpeta con fecha y hora:

```text
reports/archive/YYYY-MM-DD/HH-MM-SS/
```

Cada proceso usa siempre esta estructura completa, también la primera ejecución del día:

```text
reports/archive/YYYY-MM-DD/HH-MM-SS/
```

Si dos ejecuciones coinciden en el mismo segundo, se añade un sufijo incremental para no sobrescribir archivos.

- `secrets/accounts/`: perfiles de credenciales y tokens locales.

Para guardar un reporte en otra ubicacion, indica el nombre base sin extension. El archivado automático de `latest` se aplica cuando el destino es `reports/latest`:

```bash
python media_dedupe.py scan --local-folder "C:\\Fotos" --report "reports/archive/fotos_agosto"
```

La cache evita recalcular hashes cuando el origen, identificador, tamano y fecha de modificacion no han cambiado. También conserva pHash de imágenes y hashes de frames de video. Las actualizaciones se confirman por tandas para reducir operaciones SQLite. La búsqueda de imágenes similares usa un índice BK-tree por distancia Hamming para evitar comparar todos los pares cuando la colección es grande. Para usar otra base:

```bash
python media_dedupe.py scan --local-folder "C:\\Fotos" --cache-db "C:\\Temp\\media_cache.db"
```

## GUI avanzada

La interfaz disponible es `media_dedupe_gui_advance.py`. Abre un reporte JSON, muestra grupos, miniaturas y metadatos, permite filtrar por similitud y eliminar archivos locales seleccionados.

```bash
python media_dedupe_gui_advance.py
```

La pestaña **Operacion** permite:

- Autenticar Google Drive, OneDrive y Google Photos.
- Seleccionar varias carpetas locales mediante el explorador.
- Cargar y seleccionar varias carpetas de Google Drive despues de autenticarlas.
- Configurar modo de hash, umbrales, solo duplicados exactos y nombre base del reporte.
- Mostrar el estado de configuración de Google Drive, Google Photos y OneDrive.
- Ejecutar el CLI con las rutas centralizadas y ver su salida en tiempo real.
- Mostrar la fase y el progreso aproximado del proceso.
- Cancelar el proceso activo desde la ventana sin cerrar la GUI.
- Cargar automaticamente el JSON generado en la pestaña **Resultados**.

La pestaña **Resultados** mantiene la revision por grupos, el filtro de similitud y las acciones sobre archivos locales. Los archivos seleccionados se mueven a `reports/quarantine/<sesion>/` con un manifiesto SHA-256. Desde **Gestionar cuarentena** puedes listar sesiones, restaurar archivos individuales o múltiples, y eliminar definitivamente una sesión.

En Resultados puedes filtrar por umbral de similitud, proveedor y tipo de grupo. La cabecera permite abrir directamente los últimos reportes JSON, CSV y HTML.

Al cancelar un escaneo en Windows, la GUI termina el árbol completo del proceso, incluidos `ffmpeg` y `ffprobe`, y el CLI limpia sus temporales al salir. El escaneo cancelado no se presenta como un resultado completo.

Flujo recomendado:

1. Ejecuta un escaneo desde la consola.
2. Abre la GUI avanzada.
3. Carga `reports/latest/duplicados.json`.
4. Revisa cada grupo y ajusta el filtro.
5. Selecciona manualmente los archivos que quieras retirar.
6. Confirma la accion.

La GUI solo puede actuar sobre rutas locales existentes. Los elementos de Google Drive, OneDrive y Google Photos no tienen una ruta local movible. La GUI no elimina directamente: mueve los archivos locales a cuarentena para permitir undo/restauración.

## Seguridad y limitaciones

- El CLI no borra ni mueve archivos multimedia; solo lee y genera reportes. La GUI mueve archivos locales seleccionados a cuarentena.
- No compartas ni confirmes credenciales dentro del repositorio.
- Los backups cifrados de WhatsApp en Google Drive no se pueden recorrer como archivos individuales.
- La deteccion de similares puede requerir descargar archivos y tardar en colecciones grandes.
- OneDrive puede no proporcionar hashes para todos los archivos; en ese caso se calculan localmente.
- La deteccion de videos compara frames y es aproximada.

## Estructura relevante

```text
media_duplicate_files/
|-- media_dedupe.py                 # CLI principal
|-- media_dedupe_gui_advance.py     # GUI para revisar reportes
|-- config/paths.py                 # Rutas centralizadas
|-- core/                           # Hashes, metadatos, similitud y reportes
|-- providers/                      # Google, Microsoft y carpetas locales
|-- reports/                        # Cache, ultimos reportes e historico archivado
|-- secrets/                        # Credenciales locales, no publicar
|-- tests/                          # Pruebas automatizadas
`-- requirements.txt
```

## Verificacion y pruebas

```bash
# Crear las carpetas de datos y validar rutas
python config/paths.py

# Comprobar que el CLI carga correctamente
python -c "from config.paths import validar_rutas; validar_rutas(); print('OK')"

# Ejecutar las pruebas
python -m pytest
```

Las pruebas incluyen selección estable de archivos, reportes parciales/vacíos y el ciclo completo de cuarentena y restauración.

Si una ruta o credencial no existe, `config/paths.py` indicara que falta. Completa primero la configuracion del proveedor que quieras escanear.
