# !/usr/bin/env python3

"""
guía_rápida_gui_avanzada.md — Guía de inicio rápido para la GUI avanzada.
"""

## GUÍA RÁPIDA: GUI AVANZADA DE MEDIA DEDUPE

## ⚡ Inicio en 5 minutos

### Paso 1: Generar un reporte

Ejecuta un escaneo normal desde CLI:

```bash
# Google Drive
python media_dedupe.py auth google-drive
python media_dedupe.py scan --source google-drive --report reporte

# O desde la GUI clásica
python media_dedupe_gui.py
```

Esto genera:

- `reporte.json` ← Usa este
- `reporte.csv`
- `reporte.html`

### Paso 2: Abrir la GUI avanzada

```bash
python media_dedupe_gui_advance.py
```

### Paso 3: Cargar el reporte

1. Clic en botón "📂 Abrir Reporte..." (arriba a la derecha)
2. Selecciona `reporte.json`
3. ¡La interfaz se carga automáticamente!

### Paso 4: Filtrar y seleccionar

#### **Opción A: Manual (seguro)**

- Haz clic en cada checkbox para marcar archivos
- Solo se marcan los duplicados (no el "mejor")

#### **Opción B: Automático (recomendado)**

1. Ajusta el slider "Filtro por similitud (%)" a tu gusto
   - 100% = solo duplicados exactos
   - 95% = también fotos muy similares
   - 90% = incluso fotos ligeramente diferentes
2. Clic en "✓ Seleccionar Filtrados"
3. Automáticamente marca TODOS los duplicados en el rango

### Paso 5: Eliminar

1. Clic en "🗑️  Eliminar Seleccionadas"
2. Confirma en el diálogo emergente
3. Los archivos se eliminan en segundos
4. Recibes un reporte de lo eliminado

---

## 🎯 Flujo Completo de Ejemplo

```bash
# 1. Autenticar
python media_dedupe.py auth google-drive
python media_dedupe.py auth onedrive

# 2. Escanear múltiples orígenes
python media_dedupe.py scan \
  --source google-drive \
  --source onedrive \
  --whatsapp-folder "C:\Users\Usuario\Downloads\WhatsApp" \
  --report mis_duplicados

# 3. Abrir GUI avanzada
python media_dedupe_gui_advance.py

# 4. En la GUI:
#    - Cargar "mis_duplicados.json"
#    - Mover slider a 95% para fotos muy similares
#    - Clic "Seleccionar Filtrados"
#    - Clic "Eliminar Seleccionadas"
#    - ¡Listo! Se eliminan automáticamente
```

---

## 🎨 Descripción de la Interfaz

### Panel Superior: Vista Previa

```text
┌─────────────────────────────────────────────────────────┐
│ 📋 Detalles del Grupo                                   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   [FOTO]    │  │   [FOTO]    │  │   [FOTO]    │     │
│  │ 📐 4000×3k  │  │ 📐 2560×1k  │  │ 📐 1920×1k  │     │
│  │ 💾 2.0 MB   │  │ 💾 1.5 MB   │  │ 💾 800 KB   │     │
│  │ 📷 Canon    │  │ 📷 iPhone   │  │ 💬 WhatsApp │     │
│  │ ⭐ MEJOR    │  │             │  │             │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

**Features:**

- Miniaturas de izquierda a derecha
- Metadatos debajo de cada foto
- Marca "⭐ MEJOR" al archivo de mayor resolución
- Scroll horizontal si hay muchos archivos

### Panel Central: Tabla de Grupos

```text
┌────────────────────────────────────────────────────────┐
│ 📊 Grupos de Duplicados                                 │
├────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────┐  │
│ │ 🔴 Grupo 1: 3 archivos | Similitud: 100%         │  │
│ │ Espacio recuperable: 4.0 MB                       │  │
│ │                                                   │  │
│ │  [✓ Eliminar]  [✓ Eliminar]  [✓ Eliminar]       │  │
│ │   foto1.jpg      foto2.jpg      foto3.jpg        │  │
│ │   ⭐ MEJOR      2.0 MB         1.5 MB           │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ ┌──────────────────────────────────────────────────┐  │
│ │ 🟡 Grupo 2: 2 archivos | Similitud: 96.5%       │  │
│ │ Espacio recuperable: 1.5 MB                       │  │
│ │                                                   │  │
│ │  [✓ Eliminar]  [✓ Eliminar]                     │  │
│ │   selfie_v1.jpg  selfie_v2.jpg                  │  │
│ │   ⭐ MEJOR      1.5 MB                           │  │
│ └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

**Features:**

- Una fila = un grupo de duplicados
- Emojis indican tipo: 🔴 exacto, 🟡 similar imagen, 🟢 similar video
- Muestra % de similitud si no es 100%
- Checkboxes para marcar archivos a eliminar
- Espacio recuperable en MB/GB

### Panel Inferior: Controles

```text
┌────────────────────────────────────────────────────────┐
│ Filtro por similitud (%): [═════●────] 95%            │
│                                                        │
│ [✓ Seleccionar Filtrados] [🗑️  Eliminar Seleccionadas]│
└────────────────────────────────────────────────────────┘
```

**Features:**

- Slider: filtra grupos por puntuación mínima
- "Seleccionar Filtrados": marca automáticamente duplicados
- "Eliminar": ejecuta el borrado (pide confirmación)

---

## 🔐 Seguridad y Restricciones

### ✅ Seguro: Solo elimina archivos locales

- ✓ Archivos en `C:\Ruta\Local\`
- ✓ Archivos en WhatsApp local
- ✓ Archivos de Google Takeout (extraído)

### ❌ Nunca elimina archivos cloud

- ✗ Google Drive (no se puede borrar desde GUI)
- ✗ OneDrive (no se puede borrar desde GUI)
- ✗ Google Photos (no se puede borrar desde GUI)

### 🛡️ Confirmaciones

1. Antes de eliminar: "¿Eliminar X archivos?"
2. Reporta cada error sin crashear
3. Muestra resultado final: éxitos + errores

---

## 📊 Tipos de Grupos

| Emoji | Tipo | Significado | Acción |
| ------- | ------ | ------------- | -------- |
| 🔴 | `exact` | Idéntico (100%) | Eliminar sin dudas |
| 🟡 | `image_similar` | Imagen parecida (>95%) | Revisar antes |
| 🟢 | `video_similar` | Video parecido | Revisar antes |

---

## 💡 Tips y Trucos

### Tip 1: Filtrar por tipo

```text
Copias exactas (100%):
- Slider al 100%
- "Seleccionar Filtrados"
- Son seguros de eliminar

Fotos muy similares (>95%):
- Slider al 95%
- Revisar visualmente en panel superior
- Marcar manualmente las que quieres eliminar
```

### Tip 2: Workflow recomendado

1. Escanear con umbral bajo (90%) → encuentra TODAS las similares
2. Filtrar en GUI con slider alto (98%) → ve solo las casi-exactas
3. Seleccionar automáticamente → marca duplicados
4. Revisar panel superior antes de eliminar
5. Eliminar con confianza

### Tip 3: Usar con múltiples orígenes

```bash
# Encuentra duplicados entre Google Drive y Takeout
python media_dedupe.py scan \
  --source google-drive \
  --google-takeout-folder "C:\Takeout" \
  --report drive_vs_takeout

# Luego en GUI:
# - Los archivos de Takeout son locales → se pueden eliminar
# - Los de Drive son cloud → protegidos automáticamente
```

### Tip 4: Dos escaneos para máxima seguridad

```bash
# Escaneo 1: Solo metadatos (rápido)
python media_dedupe.py scan \
  --source google-drive \
  --hash-mode metadata \
  --report duplicados_rapido

# Escaneo 2: Con hashes perceptuales (completo)
python media_dedupe.py scan \
  --source google-drive \
  --hash-mode full \
  --image-threshold 95 \
  --report duplicados_completo
```

---

## 🐛 Troubleshooting

### Problema: "No se carga el reporte"

**Solución:**

```bash
# Verifica que el JSON es válido
python -c "import json; json.load(open('reporte.json'))"

# Si da error, el reporte está corrupto. Regenera:
python media_dedupe.py scan --source google-drive --report reporte_nuevo
```

### Problema: "No veo miniaturas"

**Solución:**

- Los archivos deben tener `path` local (ruta en disco)
- Archivos cloud (Drive, OneDrive) no muestran miniatura
- Mover imagen al disco o usar Google Takeout para verla

### Problema: "Botón eliminar no funciona"

**Solución:**

```python
# Verifica que al menos un archivo esté marcado
# Y que tenga "path" local (no URL cloud)

# Si es archivo cloud:
# - No se puede eliminar desde GUI
# - Usa Drive/OneDrive web o sincroniza localmente
```

### Problema: "GUI muy lenta"

**Solución:**

- Reportes muy grandes (>1000 grupos) pueden ser lentos
- Usa filtro (slider) para ver menos grupos a la vez
- Divide en escaneos más pequeños

---

## 📝 Ejemplos de Comandos

### Buscar exactos en Google Drive

```bash
python media_dedupe.py scan --source google-drive --skip-similar --report exactos
python media_dedupe_gui_advance.py
# Cargar exactos.json
# Slider al 100% (solo exactos)
# "Seleccionar Filtrados" + "Eliminar"
```

### Buscar fotos similares en OneDrive

```bash
python media_dedupe.py auth onedrive
python media_dedupe.py scan --source onedrive --image-threshold 95 --report fotos_similares
python media_dedupe_gui_advance.py
# Cargar fotos_similares.json
# Slider al 95%
```

### Comparar Google Drive con Takeout

```bash
# Descarga Takeout desde https://takeout.google.com
# Extrae a C:\Takeout

python media_dedupe.py scan \
  --source google-drive \
  --google-takeout-folder "C:\Takeout" \
  --report drive_vs_takeout

python media_dedupe_gui_advance.py
# Cargar drive_vs_takeout.json
# Elimina copias de Takeout (son locales)
```

---

## 🎓 Flujo Educativo

Si eres nuevo:

1. **Primero:** Lee [README.md](README.md)
2. **Luego:** Prueba CLI con `python media_dedupe.py scan --help`
3. **Después:** Usa GUI clásica `python media_dedupe_gui.py`
4. **Finalmente:** Domina GUI avanzada `python media_dedupe_gui_advance.py`

---

## 📞 Soporte

Si algo no funciona:

1. Verifica que `reporte.json` existe y es válido
2. Prueba con `sample_reporte.json` de ejemplo
3. Revisa [GUI_AVANZADA.md](GUI_AVANZADA.md) para detalles técnicos
4. Mira logs con `python media_dedupe_gui_advance.py 2>&1 | tee debug.log`

---

## **¡Disfruta limpiando tus duplicados! 🗑️🧹**
