# 📊 Reportes - Resultados de Scans

Este directorio contiene todos los reportes generados y caché de ejecuciones.

## 📁 Estructura Interna

```text
reports/
├── cache/           ← Base de datos de índices
├── latest/          ← Últimos resultados (acceso rápido)
├── quarantine/      ← Archivos locales movidos desde la GUI, con undo
└── archive/         ← Histórico automático organizado por fecha y hora
    └── YYYY-MM-DD/
        └── HH-MM-SS/ ← Cada ejecución archivada
```

---

## 📂 Subcarpetas

### `cache/` - Base de Datos de Caché

```text
cache/
└── media_cache.db   ← Hashes y metadatos de archivos
```

**Propósito:** Acelerar scans posteriores evitando re-hashear archivos

**Gestión:**

```bash
# Ver tamaño
du -sh cache/

# Limpiar caché antiguo (reinicia indexación)
rm cache/media_cache.db

# Backup periódico
cp cache/media_cache.db cache/media_cache.db.backup
```

---

### `latest/` - Últimos Reportes

```text
latest/
├── duplicados.json  ← Datos estructurados (para programas)
├── duplicados.html  ← Visualización web (para humanos)
└── duplicados.csv   ← Tabla (para Excel/análisis)
```

**Propósito:** Acceso rápido a los resultados más recientes

**Ciclo de vida:**

1. Antes de un nuevo escaneo, los archivos existentes se mueven automáticamente a `archive/YYYY-MM-DD/HH-MM-SS/`.
2. Cada ejecución archivada usa siempre fecha y hora.
3. Si dos ejecuciones coinciden en el mismo segundo, se añade un sufijo incremental.
4. El nuevo escaneo se genera en `latest/`.
5. El usuario accede a `latest/` para ver los resultados actuales.

---

---

### `archive/` - Histórico Completo

```text
archive/
├── 2026-08-17/
│   ├── scan_google-drive_2026-08-17_10-30.json
│   ├── scan_google-drive_2026-08-17_10-30.html
│   ├── scan_google-drive_2026-08-17_10-30.csv
│   ├── scan_onedrive_2026-08-17_14-45.json
│   ├── scan_onedrive_2026-08-17_14-45.html
│   └── scan_onedrive_2026-08-17_14-45.csv
├── 2026-08-16/
│   └── scan_google-photos_2026-08-16_09-15.json
│   └── ...
└── 2026-08-15/
    └── ...
```

**Propósito:** Rastrear histórico de duplicados a través del tiempo

**Beneficios:**

- ✓ Comparar duplicados entre scans
- ✓ Auditar qué se eliminó y cuándo
- ✓ Recuperar reportes antiguos si es necesario

---

## 🚀 Flujo Recomendado

### 1️⃣ Ejecutar Scan

```bash
python media_dedupe.py scan --source google-drive --report reporte
```

**Genera:** `reporte_duplicados.{json,html,csv}`

### 2️⃣ Organizar Automáticamente (script)

```bash
# Mueve reporte a archive/ con timestamp
mv reporte_duplicados.json reports/archive/2026-08-17/scan_google-drive_2026-08-17_10-30.json
# Copia a latest/
cp reports/archive/2026-08-17/scan_google-drive_2026-08-17_10-30.json reports/latest/duplicados.json
```

### 3️⃣ Visualizar en GUI

```bash
python media_dedupe_web.py
# Abre el navegador y carga automáticamente reports/latest/duplicados.json
```

### 4️⃣ Eliminar Duplicados

```python
# Desde GUI: checkboxes + botón "Eliminar"
# Los archivos se eliminan, reporte permanece en archive/
```

---

## 📋 Nombramiento de Archivos

### Estándar Recomendado

```text
scan_{SOURCE}_{FECHA}_{HORA}.{FORMAT}

Ejemplos:
- scan_google-drive_2026-08-17_10-30.json
- scan_onedrive_2026-08-17_14-45.html
- scan_google-photos_2026-08-16_09-15.csv
- scan_local-folder_2026-08-15_22-00.json
```

### Placeholders

- `{SOURCE}` = google-drive | onedrive | google-photos | local-folder | whatsapp_local
- `{FECHA}` = YYYY-MM-DD
- `{HORA}` = HH-MM (24h)
- `{FORMAT}` = json | html | csv

---

## 🧹 Mantenimiento

### Limpiar Reportes Antiguos (>30 días)

```bash
# Script para eliminar archivos más antiguos de 30 días
find reports/archive -type f -mtime +30 -delete
```

### Comprimir Histórico

```bash
# Comprimir carpetas de 2-3 meses atrás
tar -czf reports/archive/2026-05.tar.gz reports/archive/2026-05/
rm -rf reports/archive/2026-05/
```

### Backup Periódico

```bash
# Backup semanal
tar -czf "reports_backup_$(date +%Y-%m-%d).tar.gz" reports/
cp reports_backup_*.tar.gz /mnt/backup/
```

---

## 📊 Estadísticas

### Ver tamaño total

```bash
du -sh reports/
du -sh reports/cache/
du -sh reports/archive/
```

### Contar reportes

```bash
find reports/archive -name "*.json" | wc -l
```

### Reportes por fuente

```bash
ls reports/archive/2026-08-17/ | grep -o "scan_[^_]*" | sort | uniq -c
```

---

## ⚠️ Notas Importantes

- **Permiso de lectura:** Cualquiera puede ver reportes (no incluyen datos personales)
- **Permiso de escritura:** Solo `media_dedupe.py` escribe aquí
- **Eliminaciones:** Los archivos duplicados se eliminan, los reportes permanecen
- **Recuperación:** Si eliminas accidentalmente un archivo, mira `reports/archive/` para recuperar

---

## 🔗 Archivos Relacionados

- [README.md](../README.md) - Documentación principal
- [media_dedupe.py](../media_dedupe.py) - Script de generación
- [media_dedupe_web.py](../media_dedupe_web.py) - Visualizador GUI web local
