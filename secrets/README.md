# Credenciales de Media Dedupe

Esta carpeta contiene secretos OAuth. No publiques, envíes ni hagas commit de ningún archivo de `secrets/`. El proyecto ya la excluye mediante `.gitignore`.

## Inventario actual

Cada perfil contiene sus propios JSON en `secrets/accounts/<proveedor>/<perfil>/`; solo el OAuth de Google se descarga manualmente y los tokens se generan automáticamente:

| Archivo | Servicio | Cómo se obtiene | Para qué sirve |
| --- | --- | --- | --- |
| `google-drive.json` | Google Drive y Google Photos | Se descarga una vez desde Google Cloud | Credencial OAuth de aplicación de escritorio; la comparten Drive y Photos |
| `google-drive-token.json` | Google Drive | Lo crea `auth google-drive` | Sesión OAuth de Drive y sus permisos `drive.readonly` |
| `google-photos-token.json` | Google Photos | Lo crea `auth google-photos` | Sesión OAuth independiente para Photos; sus permisos son diferentes |
| `onedrive-config.json` | Microsoft OneDrive | Lo creas manualmente | `client_id` y `tenant` de la aplicación registrada en Microsoft Entra |
| `onedrive-token.json` | Microsoft OneDrive | Lo crea `auth onedrive` | Caché de sesión de MSAL; evita iniciar sesión en cada ejecución |

### Respuesta corta: ¿por qué hay tantos archivos de Google?

Google usa **un solo archivo de credenciales de aplicación**:

```text
google-drive.json
```

Ese archivo identifica la aplicación OAuth y se reutiliza para Google Drive y Google Photos. Sin embargo, cada servicio necesita permisos distintos y la biblioteca de Google guarda una sesión separada para cada conjunto de permisos:

```text
google-drive-token.json   # Drive: drive.readonly
google-photos-token.json   # Photos: appcreateddata o Picker
```

Por tanto, para Google son necesarios **tres archivos en total**, pero solo **uno se descarga manualmente**. Los otros dos aparecen después de autenticarte. No necesitas descargar `google-photos.json`, `credentials-photos.json` ni un segundo OAuth client para Photos.

## Google Drive y Google Photos

### Paso 1: crear el proyecto de Google

1. Abre [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto nuevo o selecciona uno existente.
3. Anota el proyecto que vas a usar para ambas APIs.

### Paso 2: habilitar las APIs

En **APIs y servicios > Biblioteca**, habilita:

1. **Google Drive API**, obligatoria para Drive.
2. **Photos Library API**, solo si vas a usar `--source google-photos`.

Para analizar toda la biblioteca de Google Photos, la opción recomendada es descargar Google Takeout y usar una carpeta local. La API de Photos tiene restricciones para aplicaciones nuevas.

### Paso 3: configurar la pantalla de consentimiento OAuth

1. Ve a **APIs y servicios > Pantalla de consentimiento OAuth**.
2. Selecciona **Externo** si vas a usar una cuenta personal de Google.
3. Completa el nombre de la aplicación y el correo de soporte.
4. Añade tu cuenta como usuario de prueba si la aplicación está en modo de prueba.
5. Guarda la configuración.

### Paso 4: crear y descargar `google-drive.json`

1. Ve a **APIs y servicios > Credenciales**.
2. Pulsa **Crear credenciales > ID de cliente de OAuth**.
3. Selecciona el tipo **Aplicación de escritorio**.
4. Pon un nombre identificable, por ejemplo `Media Dedupe Desktop`.
5. Pulsa **Crear**.
6. En la lista de credenciales, busca el cliente recién creado.
7. Pulsa el botón de descarga de JSON.
8. Renombra el archivo descargado exactamente como:

```text
google-drive.json
```

9. Muévelo a:

```text
secrets/credentials/google-drive.json
```

El archivo debe tener una estructura de cliente instalado, normalmente con una clave superior llamada `installed`. No cambies sus valores ni lo edites para crear el token.

### Paso 5: autenticar Google Drive

Desde la raíz del proyecto ejecuta:

```powershell
python media_dedupe.py auth google-drive
```

Se abrirá el navegador. Selecciona tu cuenta, acepta el permiso de solo lectura y vuelve a la consola. El programa creará:

```text
secrets/credentials/google-drive-token.json
```

Después puedes comprobar Drive con:

```powershell
python media_dedupe.py scan --source google-drive --skip-similar
```

### Paso 6: autenticar Google Photos, si se necesita la API

No descargues otro client secret. Usa el mismo `google-drive.json` y ejecuta uno de estos modos:

```powershell
# Medios creados o subidos por esta aplicación
python media_dedupe.py auth google-photos --photos-mode app-created

# Selección manual mediante Google Photos Picker
python media_dedupe.py auth google-photos --photos-mode picker
```

La primera autenticación creará:

```text
secrets/credentials/google-photos-token.json
```

Ese token es independiente del de Drive porque los scopes son diferentes. Para escanear:

```powershell
python media_dedupe.py scan --source google-photos --photos-mode app-created
python media_dedupe.py scan --source google-photos --photos-mode picker
```

Si solo quieres toda la biblioteca, descarga [Google Takeout](https://takeout.google.com/), extrae el ZIP y ejecuta:

```powershell
python media_dedupe.py scan --google-photos-folder "C:\Takeout\Google Photos"
```

Ese flujo no necesita token de Google Photos.

## Microsoft OneDrive

OneDrive usa dos archivos, pero solo uno se descarga desde Microsoft. El archivo de configuración lo creas tú con el identificador de la aplicación.

### Paso 1: registrar la aplicación

1. Abre [Microsoft Entra admin center](https://entra.microsoft.com/).
2. Ve a **Applications > App registrations > New registration**.
3. Escribe un nombre, por ejemplo `Media Dedupe Desktop`.
4. En tipos de cuenta, selecciona **Accounts in any organizational directory and personal Microsoft accounts** o la opción equivalente que incluya cuentas personales.
5. Registra la aplicación.
6. En la página **Overview**, copia **Application (client) ID**.

### Paso 2: conceder permisos de Microsoft Graph

1. En la aplicación, abre **API permissions**.
2. Pulsa **Add a permission**.
3. Selecciona **Microsoft Graph > Delegated permissions**.
4. Añade:

```text
Files.Read.All
User.Read
```

5. Guarda los permisos. Para una cuenta personal normalmente no hace falta consentimiento de administrador; si Microsoft lo solicita, concédelo con una cuenta autorizada.

El código usa esos dos permisos para leer el contenido de OneDrive. No necesita permisos de escritura ni de eliminación.

### Paso 3: crear `onedrive-config.json`

Crea manualmente el archivo `secrets/credentials/onedrive-config.json` con este contenido:

```json
{
  "client_id": "PEGA_AQUI_APPLICATION_CLIENT_ID",
  "tenant": "consumers"
}
```

Para cuentas corporativas, reemplaza `consumers` por el tenant correspondiente. No pongas aquí el access token ni la contraseña.

### Paso 4: autenticar OneDrive

Desde la raíz del proyecto ejecuta:

```powershell
python media_dedupe.py auth onedrive
```

MSAL abrirá el navegador para iniciar sesión. Al terminar, el programa creará automáticamente:

```text
secrets/credentials/onedrive-token.json
```

Comprueba el acceso con:

```powershell
python media_dedupe.py scan --source onedrive --skip-similar
```

## Qué no debes descargar ni crear

No necesitas estos nombres adicionales:

```text
google-photos.json       # No se usa
credentials-photos.json  # No se usa
onedrive.json            # No se usa
token_drive.json         # Nombre antiguo; el actual es google-drive-token.json
token_photos.json        # Nombre antiguo; el actual es google-photos-token.json
```

Los nombres efectivos están definidos en `config/paths.py` y son los que utilizan `media_dedupe.py` y los providers.

## Regenerar una autenticación

Si un token se invalida, puedes borrar solo el token correspondiente y volver a autenticar:

```powershell
Remove-Item secrets/credentials/google-drive-token.json
python media_dedupe.py auth google-drive

Remove-Item secrets/credentials/google-photos-token.json
python media_dedupe.py auth google-photos --photos-mode app-created

Remove-Item secrets/credentials/onedrive-token.json
python media_dedupe.py auth onedrive
```

Si el client secret de Google se expone, revoca o elimina esa credencial desde Google Cloud Console y descarga un nuevo `google-drive.json`. Si se expone un secreto de OneDrive, elimina la aplicación registrada y crea otra.

## Usar varias cuentas

Cada cuenta es un perfil independiente. El nombre de perfil recomendado es la parte anterior a `@` del correo (`botero@example.com` → `botero`).

1. Coloca el JSON de credenciales en la carpeta del perfil (ver rutas más abajo).
2. Autentica con el CLI indicando el perfil; el token se guarda en esa misma carpeta:

   ```bash
   python media_dedupe.py auth google-drive --google-profile botero
   python media_dedupe.py auth onedrive --onedrive-profile botero
   ```

3. Escanea usando el mismo perfil (`--google-profile` / `--onedrive-profile`).

Desde la GUI web (`media_dedupe_web.py`, vista **Operación**) puedes disparar la autenticación de cada proveedor, que delega en estos mismos comandos del CLI.

Los perfiles se almacenan directamente en:

```text
secrets/accounts/google/<perfil>/
secrets/accounts/onedrive/<perfil>/
```

La aplicación pasa directamente las rutas del perfil seleccionado a los providers. No existe una carpeta puente de credenciales. Los tokens no se muestran en el log ni se copian automáticamente al portapapeles; también puedes pegarlos con **Pegar JSON de token...**.

## Comprobar los archivos sin mostrar secretos

Desde PowerShell puedes verificar nombres y claves estructurales sin imprimir valores sensibles:

```powershell
Get-ChildItem secrets\credentials\*.json | ForEach-Object {
    $json = Get-Content $_.FullName -Raw | ConvertFrom-Json
    "$($_.Name): $($json.PSObject.Properties.Name -join ', ')"
}
```

La salida esperada es aproximadamente:

```text
google-drive-token.json: token, refresh_token, token_uri, client_id, client_secret, scopes, ...
google-drive.json: installed
google-photos-token.json: token, refresh_token, token_uri, client_id, client_secret, scopes, ...
onedrive-config.json: client_id, tenant
onedrive-token.json: AccessToken, Account, IdToken, RefreshToken, AppMetadata
```

## Seguridad

- No subas ningún archivo de `secrets/` a GitHub.
- No pegues tokens en issues, chats, logs ni capturas de pantalla.
- Si una credencial se filtra, revócala en el proveedor antes de borrarla localmente.
- Los tokens permiten acceder a datos de tus cuentas; trátalos como contraseñas.
