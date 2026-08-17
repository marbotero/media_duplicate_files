# 🎨 GUI Avanzada para Media Dedupe — Resumen Completo

## ¿Qué se creó?

He diseñado una interfaz gráfica profesional y modular que permite visualizar, filtrar y gestionar archivos duplicados de forma intuitiva. El sistema cuenta con **3 paneles principales** que trabajan en conjunto.

---

## 📁 Archivos Creados

### 1. **media_dedupe_gui_advance.py** (Principal)

- **Líneas:** ~540 líneas de código Python
- **Componentes:**
  - `PanelVistaPrevia`: Miniaturas y metadatos
  - `PanelResultados`: Tabla dinámica con checkboxes
  - `PanelControl`: Filtros y acciones masivas
  - `VentanaAvanzada`: Ventana principal que integra todo
- **Dependencias:** tkinter (incluido), Pillow (PIL)
- **Uso:** `python media_dedupe_gui_advance.py`

### 2. **GUI_AVANZADA.md** (Documentación Técnica)

- Arquitectura detallada de cada componente
- Métodos y responsabilidades
- Estructura de datos esperada (JSON)
- Guía de personalización
- Ejemplos de extensión
- Depuración y troubleshooting

### 3. **GUIA_RAPIDA_GUI.md** (Guía de Usuario)

- Inicio en 5 minutos
- Flujo completo de ejemplo
- Interfaz visual (ASCII art)
- Tipos de grupos y filtros
- Tips y trucos
- Troubleshooting

### 4. **ejemplo_gui_avanzada.py** (Ejemplos)

- 5 ejemplos de uso práctico
- Análisis de reportes sin GUI
- Búsqueda de exactos
- Filtrado programático
- CLI con argumentos

---

## 🎯 Estructura de la Interfaz

```text
┌──────────────────────────────────────────────────────────────┐
│                    HEADER (Título + Botón)                   │
├──────────────────────────────────────────────────────────────┤
│                   PANEL SUPERIOR (Vista Previa)              │
│  [Miniatura 1] [Miniatura 2] [Miniatura 3] [Miniatura 4]   │
│   Con metadatos: resolución, tamaño, fecha, cámara, origen  │
├──────────────────────────────────────────────────────────────┤
│                   PANEL CENTRAL (Tabla)                      │
│ Grupo 1: 3 archivos | Similitud 100% | Espacio: 4.0 MB    │
│   [✓] Foto1    [✓] Foto2    [✓] Foto3                      │
│                                                              │
│ Grupo 2: 2 archivos | Similitud 96.5% | Espacio: 1.5 MB   │
│   [✓] Selfie1  [✓] Selfie2                                 │
├──────────────────────────────────────────────────────────────┤
│                 PANEL INFERIOR (Controles)                   │
│ Filtro: [═════●────] 95%                                    │
│ [✓ Seleccionar Filtrados] [🗑️  Eliminar Seleccionadas]     │
└──────────────────────────────────────────────────────────────┘
```

---

## ✨ Características Principales

### 1. **Panel Superior: Vista Previa Dinámica**

- ✅ Miniaturas de izquierda a derecha (scroll horizontal)
- ✅ Ordena automáticamente por resolución (mejor primero)
- ✅ Muestra metadatos legibles:
  - 📐 Resolución (4000×3000px)
  - ⏱️ Duración (si es video)
  - 💾 Tamaño (2.0 MB)
  - 📅 Fecha de captura
  - 📷 Modelo de cámara (EXIF)
  - ☁️ Origen (Drive, OneDrive, WhatsApp, etc.)
- ✅ Badge "⭐ MEJOR" para archivo de mayor resolución
- ✅ Placeholder para archivos cloud (no descarga)

### 2. **Panel Central: Tabla Dinámica**

- ✅ Una fila = un grupo de duplicados
- ✅ Columnas dinámicas (máx 4 visibles, muestra +N si hay más)
- ✅ Emojis por tipo:
  - 🔴 Exacto (100%)
  - 🟡 Imagen similar (>95%)
  - 🟢 Video similar
- ✅ Checkboxes para marcar archivos a eliminar
- ✅ Muestra espacio recuperable por grupo
- ✅ Click en fila = actualiza panel superior
- ✅ Miniatura pequeña en cada celda

### 3. **Panel Inferior: Control Inteligente**

- ✅ Slider: filtra por umbral de similitud (0-100%)
- ✅ "Seleccionar Filtrados": marca automáticamente duplicados (excepto el mejor)
- ✅ "Eliminar Seleccionadas": ejecuta con confirmación
- ✅ Solo elimina archivos locales (seguridad)
- ✅ Reporta éxitos y errores

---

## 🚀 Inicio Rápido

### Paso 1: Generar un reporte

```bash
# Escanear Google Drive
python media_dedupe.py auth google-drive
python media_dedupe.py scan --source google-drive --report reporte
```

### Paso 2: Abrir la GUI avanzada

```bash
python media_dedupe_gui_advance.py
```

### Paso 3: Cargar el reporte

- Botón "📂 Abrir Reporte..." (arriba a la derecha)
- Selecciona `reporte.json`
- ¡Listo!

### Paso 4: Filtrar y eliminar

```text
Slider: Ajusta a 95% (fotos muy similares)
Botón: "✓ Seleccionar Filtrados"
Botón: "🗑️  Eliminar Seleccionadas"
Confirmar eliminación
```

---

## 🔐 Seguridad Garantizada

### ✅ Protegido: Archivos Cloud

- Google Drive → No se puede eliminar
- OneDrive → No se puede eliminar
- Google Photos → No se puede eliminar

### ❌ Eliminable: Solo Local

- Carpeta local → Sí
- WhatsApp local → Sí
- Google Takeout (extraído) → Sí

### 🛡️ Confirmaciones

1. Diálogo de confirmación antes de eliminar
2. Valida que archivo exista antes de borrar
3. Reporta cada error sin crashear
4. Ejecuta en thread separado (no bloquea UI)

---

## 📊 Ejemplos de Uso

### Ejemplo 1: GUI Básica

```bash
python gui_advanced.py
# Cargar reporte manualmente
# Filtrar y seleccionar
```

### Ejemplo 2: GUI con Precarga

```bash
python ejemplo_gui_avanzada.py reporte.json
# Reporte ya cargado
# Filtrar slider y eliminar
```

### Ejemplo 3: GUI con Filtro Inicial

```bash
python ejemplo_gui_avanzada.py reporte.json --filter 95
# Reporte cargado
# Filtro ya en 95%
# "Seleccionar Filtrados" + "Eliminar"
```

### Ejemplo 4: Análisis sin GUI

```bash
python ejemplo_gui_avanzada.py reporte.json --analyze
# Mostrar estadísticas
# Top 5 grupos más grandes
# Simulación de eliminación segura
```

### Ejemplo 5: Reportar Qué Se Eliminaría

```bash
python ejemplo_gui_avanzada.py reporte.json --filter-report 95
# Listar archivos que se eliminarían con filtro 95%
# Sin abrir GUI
# Sin eliminar nada
```

---

## 💡 Tips Profesionales

### 1. Workflow de 2 fases

```bash
# Fase 1: Escaneo explorador (encuentra TODO)
python media_dedupe.py scan --image-threshold 90 --report duplicados_amplios

# Fase 2: GUI para revisar y seleccionar
python gui_advanced.py
# Cargar duplicados_amplios.json
# Slider al 95% para ver solo similares
# Revisar visualmente
# Eliminar con confianza
```

### 2. Combinar múltiples orígenes

```bash
python media_dedupe.py scan \
  --source google-drive \
  --source onedrive \
  --whatsapp-folder "C:\WhatsApp" \
  --report multi_origen

python gui_advanced.py
# GUI automáticamente detecta qué es eliminable (local vs cloud)
```

### 3. Iterar de forma segura

```bash
# Primera pasada: solo exactos
python media_dedupe.py scan --skip-similar --report exactos
python gui_advanced.py
# "Seleccionar Filtrados" (todos son 100%)
# "Eliminar Seleccionadas"

# Segunda pasada: similares
python media_dedupe.py scan --image-threshold 95 --report similares
python gui_advanced.py
# Filtro al 95%
# Revisar panel superior
# Seleccionar manualmente
```

---

## 🎨 Personalización

### Cambiar colores

Edita `COLORES` en `media_dedupe_gui_advance.py`:

```python
COLORES = {
    "acento": "#1a73e8",        # Azul Google
    "peligro": "#d93025",       # Rojo
    "exito": "#1e8e3e",         # Verde
    "advertencia": "#f9ab00",   # Naranja
}
```

### Cambiar tipografía

Edita `TIPOGRAFIA`:

```python
TIPOGRAFIA = {
    "título": ("Arial", 16, "bold"),
    "normal": ("Courier", 10),
}
```

### Cambiar comportamiento de eliminación

Busca `_ejecutar_eliminación()` y reemplaza:

```python
# Actual: os.remove(ruta)
# Alternativa: mover a cuarentena
import shutil
shutil.move(ruta, f"_cuarentena/{Path(ruta).name}")
```

---

## 📚 Documentación Disponible

| Documento | Propósito | Público |
| ----------- | ---------- | --------- |
| **GUI_AVANZADA.md** | Arquitectura técnica | Desarrolladores |
| **GUIA_RAPIDA_GUI.md** | Inicio y uso | Usuarios |
| **ejemplo_gui_avanzada.py** | Ejemplos prácticos | Todos |
| **README.md** | Documentación general | Todos |

---

## 🔧 Instalación de Dependencias

```bash
# Verificar Python
python --version  # 3.9+

# Instalar Pillow (para miniaturas)
pip install Pillow

# Verificar tkinter (viene con Python)
python -c "import tkinter; print('✓ tkinter ok')"
```

---

## 🐛 Troubleshooting

### Error: "No se carga el reporte"

```bash
# Verifica que JSON es válido
python -c "import json; json.load(open('reporte.json'))"
```

### Error: "Botón eliminar no funciona"

- ✓ Al menos un archivo debe estar marcado
- ✓ El archivo debe tener `path` local (no URL)

### La GUI es muy lenta

- Usa el slider para filtrar y ver menos grupos
- Divide reportes muy grandes

---

## 🎓 Flujo de Aprendizaje

```text
1. Lee README.md
   ↓
2. Ejecuta: python media_dedupe.py scan --help
   ↓
3. Prueba GUI clásica: python media_dedupe_gui.py
   ↓
4. Domina GUI avanzada: python media_dedupe_gui_advance.py
   ↓
5. Automatiza con ejemplo_gui_avanzada.py
```

---

## 📊 Resumen de Capacidades

| Función | Capacidad |
| --------- | ----------- |
| Visualizar duplicados | ✅ Vista previa con miniaturas |
| Filtrar | ✅ Por porcentaje de similitud |
| Seleccionar | ✅ Manual o automático |
| Eliminar | ✅ Solo archivos locales |
| Seguridad | ✅ Confirmación + validación |
| Extensibilidad | ✅ Código modular y comentado |

---

## 🎯 Próximos Pasos

1. **Usa GUI avanzada para eliminar duplicados**
2. **Revisa GUI_AVANZADA.md si quieres personalizar**
3. **Estudia ejemplo_gui_avanzada.py para automatizar**
4. **Contribuye mejoras al repositorio**

---

## 📞 Ayuda

Si necesitas:

- **Iniciar:** Lee GUIA_RAPIDA_GUI.md
- **Entender código:** Lee GUI_AVANZADA.md
- **Ver ejemplos:** Ejecuta ejemplo_gui_avanzada.py
- **Reportar bug:** Incluye reporte.json de ejemplo

---

## **¡Disfruta de tu nueva interfaz avanzada! 🎉**

## *Creada con ❤️ para Media Dedupe*
