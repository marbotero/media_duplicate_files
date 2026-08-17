# GUI Avanzada — Documentación Técnica

## Descripción General

`media_dedupe_gui_advance.py` es una interfaz gráfica profesional y modular para visualizar, filtrar y gestionar archivos duplicados detectados por Media Dedupe.

**Características principales:**

- ✅ **Panel Superior**: Vista previa con miniaturas y metadatos detallados de cada archivo
- ✅ **Panel Central**: Tabla dinámica de grupos con checkboxes para selección de eliminación
- ✅ **Panel Inferior**: Filtros por similitud y acciones masivas
- ✅ **Modular**: Componentes reutilizables y bien separados
- ✅ **Seguro**: Confirmación antes de eliminar, no ejecuta borrados en Drive/OneDrive
- ✅ **Comentado en español**: Código limpio y fácil de mantener

---

## Arquitectura y Componentes

### 1. **PanelVistaPrevia**

**Ubicación:** Línea 101 del código  
**Responsabilidad:** Mostrar miniaturas y metadatos del grupo seleccionado

**Características:**

- Muestra miniaturas de izquierda a derecha (scroll horizontal)
- Ordena automáticamente archivos por resolución (mejor primero)
- Extrae y formatea metadatos (resolución, tamaño, fecha, cámara)
- Marca el archivo "MEJOR" con badge ⭐
- Maneja archivos locales y cloud

**Métodos clave:**

```python
def mostrar_grupo(self, grupo_dict: dict, índice_grupo: int)
```

Carga y visualiza los archivos de un grupo.

```python
def _crear_tarjeta_archivo(self, archivo: dict, posición: int)
```

Crea una tarjeta visual individual para un archivo.

**Ejemplo de uso:**

```python
panel = PanelVistaPrevia(parent_frame)
grupo = {...}  # Datos del grupo
panel.mostrar_grupo(grupo, indice=0)
```

---

### 2. **PanelResultados**

**Ubicación:** Línea 218 del código  
**Responsabilidad:** Tabla dinámica de grupos con checkboxes

**Características:**

- Una fila por grupo de duplicados
- Columnas dinámicas (máx 4 visible, muestra +N si hay más)
- El archivo "mejor" aparece primero automáticamente
- Checkboxes para seleccionar archivos a eliminar
- Click en fila = selecciona grupo en panel superior

**Métodos clave:**

```python
def cargar_datos(self, grupos: List[dict])
```

Carga todos los grupos y construye la tabla.

```python
def _crear_fila_grupo(self, idx_grupo: int, grupo: dict)
```

Crea una fila visual para un grupo.

```python
def _crear_celda_archivo(self, parent, idx_grupo, idx_archivo, archivo, es_mejor)
```

Crea una celda individual en la tabla con checkbox y miniatura.

**Estructura de datos esperada:**

```json
{
  "group_type": "exact | image_similar | video_similar",
  "score": 100.0,
  "recoverable_size": 2097152,
  "files": [
    {
      "name": "archivo.jpg",
      "size": 2097152,
      "width": 4000,
      "height": 3000,
      "path": "C:\\ruta\\local.jpg",
      "source": "google_drive | onedrive | local_folder | whatsapp_local",
      "extra": {"metadata": {"camera_model": "Canon EOS"}}
    }
  ]
}
```

---

### 3. **PanelControl**

**Ubicación:** Línea 379 del código  
**Responsabilidad:** Filtros y acciones masivas

**Características:**

- Slider para filtrar por umbral de similitud (0-100%)
- Botón "Seleccionar Filtrados": marca automáticamente duplicados (excepto el mejor)
- Botón "Eliminar Seleccionadas": ejecuta borrado con confirmación
- Elimina solo archivos locales (seguridad)

**Métodos clave:**

```python
def _aplicar_filtro(self, umbral: int)
```

Filtra grupos por puntuación mínima.

```python
def _seleccionar_filtrados(self)
```

Marca automáticamente todos los duplicados (excepto el mejor).

```python
def _eliminar_seleccionadas(self)
```

Ejecuta la eliminación en un thread separado.

**Validaciones de seguridad:**

- ✅ Confirmación con `messagebox.askyesno()`
- ✅ Solo elimina archivos con `path` local (no URL cloud)
- ✅ Valida que el archivo exista antes de eliminar
- ✅ Ejecuta en thread para no bloquear UI
- ✅ Reporta errores sin crashear

---

## Funciones Auxiliares

### `formato_tamaño(bytes_: int) -> str`

Convierte bytes a formato legible:

```python
formato_tamaño(2097152)  # "2.0 MB"
formato_tamaño(1024)     # "1.0 KB"
```

### `cargar_imagen_miniatura(ruta: str, tamaño=(150, 150)) -> Optional[ImageTk.PhotoImage]`

Carga una imagen local como miniatura:

- Maneja excepciones si el archivo no existe
- Redimensiona automáticamente
- Retorna `None` si falla

### `extraer_metadatos(item_dict: dict) -> str`

Extrae metadatos legibles de un archivo:

```text
📐 4000×3000px
⏱️  3:45
💾 2.0 MB
📅 2026-08-10
📷 Canon EOS 5D
☁️ Google Drive
```

---

## Flujo de Uso

### 1. **Iniciar la GUI avanzada**

```bash
python gui_advanced.py
```

### 2. **Cargar un reporte**

Opción A: Menú "📂 Abrir Reporte..."  
Opción B: Pasar JSON por argumento (futuro)

```bash
# Después de escanear:
python media_dedupe.py scan --source google-drive --report reporte
# Luego:
python gui_advanced.py
# Y hacer clic en "📂 Abrir Reporte..." para seleccionar reporte.json
```

### 3. **Filtrar por similitud**

- Mover slider a la izquierda = ver todos los grupos
- Mover slider a la derecha = solo grupos muy similares

### 4. **Seleccionar archivos a eliminar**

#### **Opción A: Manual**

- Hacer clic en checkboxes individuales en cada archivo

#### **Opción B: Automática (recomendado)**

- Ajustar filtro al nivel deseado
- Clic en "✓ Seleccionar Filtrados" → automáticamente marca todos los duplicados (excepto el mejor)

### 5. **Ejecutar eliminación**

- Clic en "🗑️  Eliminar Seleccionadas"
- Confirmar en diálogo
- Los archivos locales se eliminan inmediatamente
- Mensaje de resultado con éxitos y errores

### 6. **Ver detalles completos**

- Hacer clic en una fila de grupo
- Panel superior actualiza con miniaturas y metadatos
- Para archivos cloud: muestra icono 📄 (no descarga)

---

## Estructura de Datos: Formato JSON del Reporte

El archivo `reporte.json` generado por `media_dedupe.py` tiene esta estructura:

```json
{
  "generated_at": "2026-08-17 10:00:00",
  "total_groups": 5,
  "total_recoverable_size": 10485760,
  "groups": [
    {
      "group_type": "exact",
      "score": 100.0,
      "recoverable_size": 2097152,
      "files": [
        {
          "source": "google_drive",
          "item_id": "1a2b3c4d5e6f",
          "name": "foto.jpg",
          "mime_type": "image/jpeg",
          "size": 2097152,
          "path": null,
          "web_url": "https://drive.google.com/file/d/1a2b3c4d5e6f",
          "modified_time": "2026-08-10T15:30:00",
          "md5": "abc123def456",
          "sha256": "xyz789...",
          "width": 4000,
          "height": 3000,
          "extra": {
            "metadata": {
              "camera_model": "Canon EOS 5D",
              "exposure": "1/125",
              "aperture": "f/5.6",
              "iso": 400
            },
            "extraction_engine": "exiftool"
          }
        }
      ]
    }
  ]
}
```

---

## Personalización

### Cambiar colores

Edita el diccionario `COLORES` al inicio del archivo:

```python
COLORES = {
    "acento": "#1a73e8",      # Azul Google
    "peligro": "#d93025",     # Rojo
    "exito": "#1e8e3e",       # Verde
    # ... más colores
}
```

### Cambiar tipografía

Edita `TIPOGRAFIA`:

```python
TIPOGRAFIA = {
    "título": ("Arial", 16, "bold"),
    "normal": ("Courier New", 10),
    # ...
}
```

### Cambiar comportamiento de eliminación

Método `_ejecutar_eliminación()` (línea 530):

```python
def _ejecutar_eliminación(self, archivos: List[dict]):
    # Aquí se ejecuta la lógica de borrado
    # Puedes cambiar a "mover a cuarentena" en lugar de eliminar
    
    # Actual: os.remove(ruta)
    # Alternativa: shutil.move(ruta, cuarentena_folder)
```

---

## Extensiones Futuras

### Ideas de mejora

1. **Integración con CLI**

   ```python
   # Pasar el JSON directamente desde CLI
   python gui_advanced.py --json reporte.json --auto-load
   ```

2. **Vista previa de videos**
   - Extraer frame inicial y mostrar como miniatura
   - Mostrar duración

3. **Cuarentena en lugar de borrado permanente**

   ```python
   # Mover a carpeta _media_dedupe_eliminated/ en lugar de eliminar
   shutil.move(ruta, cuarentena_path)
   ```

4. **Historial y restauración**
   - Guardar log de eliminaciones
   - Botón para restaurar desde historial

5. **Exportar lista de seleccionadas**
   - CSV o JSON con archivos marcados

6. **Comparación lado a lado**
   - Panel expandible con EXIF completo de 2 archivos

---

## Depuración

### Logs

Para ver detalles de ejecución, añade al inicio:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### Prueba sin reporte real

```bash
python -c "
import media_dedupe_gui_advance
app = media_dedupe_gui_advance.VentanaAvanzada()
# Cargar sample_reporte.json por el menú
app.mainloop()
"
```

### Verificar estructura del JSON

```bash
python -c "
import json
with open('reporte.json') as f:
    data = json.load(f)
    print(f'Grupos: {len(data[\"groups\"])}')
    for i, g in enumerate(data['groups']):
        print(f'  Grupo {i}: {len(g[\"files\"])} archivos, tipo={g[\"group_type\"]}, score={g[\"score\"]}')
"
```

---

## Dependencias

- `tkinter` (incluido en Python)
- `Pillow` (PIL): para procesar imágenes
- `json`: para leer reportes

Instalar si es necesario:

```bash
pip install Pillow
```

---

## Ejemplos de Uso

### Ejemplo 1: Cargar reporte y eliminar automáticamente

```python
from media_dedupe_gui_advance import VentanaAvanzada
import tkinter as tk

app = VentanaAvanzada()
app._cargar_reporte_json("reporte.json")
app._aplicar_filtro(95)  # Solo similares al 95% o más
app._seleccionar_filtrados()  # Marcar automáticamente
app.mainloop()
```

### Ejemplo 2: Procesar archivo programáticamente

```python
import json

def procesar_reporte(ruta_json):
    with open(ruta_json) as f:
        datos = json.load(f)
    
    for grupo in datos["groups"]:
        if grupo["score"] == 100.0:  # Solo exactos
            archivos = grupo["files"]
            mejor = archivos[0]  # Ya ordenados
            for archivo_eliminar in archivos[1:]:
                ruta = archivo_eliminar.get("path")
                if ruta and os.path.exists(ruta):
                    os.remove(ruta)
                    print(f"Eliminado: {ruta}")

procesar_reporte("reporte.json")
```

---

## Licencia y Autoría

Parte de **Media Dedupe** — Detector de duplicados multi-origen  
Diseño de GUI avanzado con componentes modulares  
Código comentado en español para máxima comprensibilidad
