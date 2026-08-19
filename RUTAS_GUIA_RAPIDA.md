# 🎯 GUÍA RÁPIDA: Rutas Centralizadas Integradas

## 🚀 Cómo Usar

### Opción 1: Scan con reportes en carpeta centralizada (Recomendado)

```bash
python media_dedupe.py scan --source google-drive

# Genera automáticamente:
# - reports/latest/duplicados.json
# - reports/latest/duplicados.csv
# - reports/latest/duplicados.html
# - reports/cache/media_cache.db
```

### Opción 2: Scan con reportes en carpeta personalizada

```bash
python media_dedupe.py scan --source google-drive --report mi_scan

# Genera:
# - mi_scan.json
# - mi_scan.csv
# - mi_scan.html
```

### Opción 3: Verificar rutas configuradas

```bash
python config/paths.py

# Salida:
# 📁 ESTRUCTURA DEL PROYECTO
# 🔒 SECRETOS:
#    ✓ google-drive-token.json
#    ✓ onedrive-token.json
#    ...
# 💾 CACHÉ:
#    ✓ media_cache.db
# 📋 REPORTES ACTUALES:
#    ✓ duplicados.json
#    ...
```

---

## 🔍 Dónde Buscar Cada Cosa

| Qué | Dónde |
| ----- | ------- |
| 🔐 Tokens de Google Drive | `secrets/credentials/google-drive-token.json` |
| 🔐 Tokens de OneDrive | `secrets/credentials/onedrive-token.json` |
| 🔐 Tokens de Google Photos | `secrets/credentials/google-photos-token.json` |
| 💾 Base de datos de caché | `reports/cache/media_cache.db` |
| 📋 Últimos reportes JSON | `reports/latest/duplicados.json` |
| 📊 Últimos reportes CSV | `reports/latest/duplicados.csv` |
| 📄 Últimos reportes HTML | `reports/latest/duplicados.html` |
| ⚙️ Rutas centralizadas | `config/paths.py` |
| 🔧 Variables de entorno | `config/.env` (edita config/.env.example) |

---

## 💡 Cambiar Rutas (5 segundos)

Si necesitas cambiar dónde se guardan los archivos:

### Ejemplo: Cambiar carpeta de caché

**Archivo:** `config/paths.py`

```python
# Cambiar esta línea:
MEDIA_CACHE_DB = REPORTES_CACHE / "media_cache.db"

# Por esto (ejemplo):
MEDIA_CACHE_DB = Path("/mnt/backup/cache/media_cache.db")
```

### Ejemplo: Cambiar carpeta de reportes

**Archivo:** `config/paths.py`

```python
# Cambiar esto:
REPORTES_LATEST = REPORTES_DIR / "latest"

# Por esto (ejemplo):
REPORTES_LATEST = PROYECTO_ROOT / "resultados"
```

**Eso es todo.** El código automáticamente usa las nuevas rutas.

---

## 🧪 Verificar que Funciona

```bash
# Test 1: Validar rutas
python config/paths.py

# Test 2: Validar imports
python -c "from media_dedupe import *; print('✅ OK')"

# Test 3: Autenticar (prueba rápida)
python media_dedupe.py auth google-drive

# Test 4: Ver help actualizado
python media_dedupe.py scan --help
# Nota: el --report por defecto ahora es "reports/latest/duplicados"
```

---

## 📊 Impacto

### Módulos que usan config.paths

- ✅ `providers/google_drive.py` - Carga token centralizado
- ✅ `providers/onedrive.py` - Carga token centralizado
- ✅ `providers/google_photos.py` - Carga token centralizado
- ✅ `media_dedupe.py` - Caché, reportes, tokens centralizados

### Directorio que se actualiza automáticamente

- ✅ `reports/latest/` - Siempre contiene últimos reportes
- ✅ `reports/cache/` - Siempre tiene media_cache.db

### Seguridad mejorada

- ✅ `secrets/` está en `.gitignore`
- ✅ Tokens no se suben a Git
- ✅ Fácil regenerar si algo se expone

---

## ⚡ Ejemplos Prácticos

### Caso 1: Ejecutar scan y ver resultados en GUI

```bash
# 1. Hacer scan
python media_dedupe.py scan --source google-drive

# 2. Los reportes se generan automáticamente en reports/latest/

# 3. Abrir GUI (carga automáticamente)
python media_dedupe_gui_advance.py
# → Botón "Abrir Reporte" → reports/latest/duplicados.json
```

### Caso 2: Ejecutar múltiples scans y archivar

```bash
# Scan de Google Drive
python media_dedupe.py scan --source google-drive --report scan1

# Scan de OneDrive
python media_dedupe.py scan --source onedrive --report scan2

# Los reportes están en:
# - scan1.json, scan1.csv, scan1.html
# - scan2.json, scan2.csv, scan2.html

# Los últimos reportes están en:
# - reports/latest/duplicados.{json,csv,html}
```

### Caso 3: Backup periódico

```bash
# Crear carpeta con fecha
mkdir reports/archive/2026-08-17

# Copiar reportes actuales
cp reports/latest/* reports/archive/2026-08-17/

# Limpiamente archivado
```

---

## 🎓 Para Aprender Más

- 📖 [RUTAS_INTEGRACION.md](RUTAS_INTEGRACION.md) - Detalles técnicos
- 📖 [config/README.md](config/README.md) - Cómo personalizar
- 📖 [ESTRUCTURA_PROYECTO.md](ESTRUCTURA_PROYECTO.md) - Visión general

---

## ❓ Preguntas Frecuentes

**P: ¿Dónde están mis credenciales?**
R: En `secrets/credentials/`. Están protegidas por `.gitignore`.

**P: ¿Los reportes se guardan automáticamente?**
R: Sí. Por defecto en `reports/latest/`. Puedes especificar otra carpeta con `--report`.

**P: ¿Puedo cambiar las rutas?**
R: Sí. Edita `config/paths.py` y listo. Una fuente de verdad.

**P: ¿Qué pasa si cambio de carpeta del proyecto?**
R: Todo sigue funcionando. Las rutas son relativas a la raíz del proyecto.

**P: ¿Cómo hago backup de los secretos?**
R: `cp -r secrets/ secretos_backup/`. NO hagas commit de esta carpeta.

**P: ¿Puede un compañero usar el mismo proyecto?**
R: Sí. Los secretos están en `.gitignore`, así que no verá tus tokens. Debe autenticarse por su cuenta.

---

## 🎉 Resumen

✅ **Rutas centralizadas en un archivo** (config/paths.py)
✅ **Secretos automáticamente protegidos**
✅ **Reportes en carpeta organizada** (reports/latest/)
✅ **Código limpio y fácil de mantener**
✅ **Listo para producción**

**¡A usar!** 🚀
