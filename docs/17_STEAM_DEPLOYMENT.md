> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

"""
Steamworks Integration — v1.5

Configuracion para distribucion en Steam. Este archivo documenta los pasos
necesarios para publicar MolDesign AI en Steam.

NO contiene secretos ni keys — esos van en variables de entorno.
"""

# ═══════════════════════════════════════════════════════════════════════════
# 1. STEAMWORKS SDK — Verificacion de compra
# ═══════════════════════════════════════════════════════════════════════════
#
# Flujo de verificacion:
#   1. Tauri arranca, obtiene el Steam ID del usuario via steamworks.js
#   2. Frontend envia Steam ID + App ID al backend en cada request
#   3. Backend verifica contra Steam Web API que el usuario compro la app
#   4. Si no hay Steam (modo dev), se usa licencia de desarrollo
#
# Endpoint: POST /steam/verify
#   Body: { "steam_id": "7656119...", "app_id": "1234567" }
#   Response: { "verified": true, "tier": "base" | "pro", "dlc": [...] }
#
# Steam Web API endpoint para verificacion:
#   GET https://api.steampowered.com/ISteamUser/CheckAppOwnership/v2/
#       ?key={STEAM_WEB_API_KEY}&steamid={steam_id}&appid={app_id}
#
# Requisitos:
#   - STEAM_WEB_API_KEY en .env (obtener de https://steamcommunity.com/dev/apikey)
#   - App ID asignado por Steamworks al crear la store page
#   - steamworks.js en el frontend para obtener Steam ID del cliente

STEAM_VERIFY_DOCS = """
Endpoint de verificacion de compra Steam.

Para implementar:
1. Agregar a backend/api/routers/steam.py:
   @router.post("/steam/verify")
   async def verify_steam_purchase(steam_id: str, app_id: str):
       url = f"https://api.steampowered.com/ISteamUser/CheckAppOwnership/v2/"
       params = {"key": settings.steam_web_api_key, "steamid": steam_id, "appid": app_id}
       async with httpx.AsyncClient() as client:
           resp = await client.get(url, params=params)
       data = resp.json()
       owns = data.get("appownership", {}).get("ownsapp", False)
       return {"verified": owns, "tier": "base"}
   
2. Agregar a core/config.py:
   steam_web_api_key: str = Field(default="", description="Steam Web API Key")
   steam_app_id: str = Field(default="", description="Steam App ID")

3. En el frontend, instalar steamworks.js:
   npm install steamworks.js
   
4. En Tauri (src-tauri/), agregar permiso para steamworks.js
"""


# ═══════════════════════════════════════════════════════════════════════════
# 2. STEAM CLOUD — Sincronizacion de base de datos
# ═══════════════════════════════════════════════════════════════════════════
#
# Steam Cloud sincroniza archivos entre PCs del usuario.
# Mapear la DB de SQLite para que el historial y moleculas guardadas
# se sincronicen automaticamente.
#
# Configuracion en Steamworks Dashboard:
#   Steam Cloud Settings → Add Root Path
#     Root: MolDesign
#     Pattern: data/*.db
#     Quota: 100 MB (la DB pesa ~10-20 MB tipicamente)
#
# Archivos a sincronizar:
#   - ~/MolDesign/data/moldesign_local.db  (historial de evaluaciones)
#   - ~/MolDesign/data/molgraph.db         (knowledge graph)
#   - ~/MolDesign/data/ai_memory.db        (memoria del asistente IA)
#
# PRECAUCION: SQLite no es seguro para sync bidireccional simultaneo.
# Steam Cloud sube al cerrar y baja al abrir, lo cual es seguro.
# Pero SIEMPRE cerrar la app antes de abrir en otra PC.

STEAM_CLOUD_CONFIG = """
Configuracion de Steam Cloud.

En Steamworks Partner Dashboard:
1. Ir a App Admin > Steam Cloud
2. Habilitar "Enable Cloud Saves"
3. Agregar Root Paths:
   - Root: MolDesign  | Pattern: data/*.db  | Quota: 100 MB
4. Guardar y Publicar

En Tauri (src-tauri/tauri.conf.json), verificar que los paths
de datos usen la carpeta de documentos del usuario, no el directorio
de instalacion:
   "app": {
     "dataDir": "MolDesign"  // → ~/MolDesign/data/
   }
"""


# ═══════════════════════════════════════════════════════════════════════════
# 3. MSVC REDISTRIBUTABLES — Configuracion Steamworks
# ═══════════════════════════════════════════════════════════════════════════
#
# Vina, xTB, RDKit, y Meeko requieren Visual C++ Runtime.
# Steamworks puede instalar automaticamente el redistributable
# antes de lanzar la app.
#
# En Steamworks Dashboard:
#   App Admin > Installation > Common Redistributables
#   Marcar: "Microsoft Visual C++ 2015-2022 Redistributable (x64)"
#
# Esto hace que Steam ejecute vcredist_x64.exe antes del primer
# lanzamiento. El usuario solo ve "Installing Microsoft Visual C++..."
# una vez.

MSVC_REDIST_CONFIG = """
Configuracion de MSVC Redistributables.

En Steamworks Partner Dashboard:
1. Ir a App Admin > Installation > General
2. En "Common Redistributables", marcar:
   [x] Microsoft Visual C++ 2015-2022 Redistributable (x64)
3. Publicar cambios

No requiere cambios en el codigo — Steam lo maneja automaticamente.
Los usuarios con Windows actualizado ya lo tienen.
"""


# ═══════════════════════════════════════════════════════════════════════════
# 4. CODE SIGNING — Preparacion
# ═══════════════════════════════════════════════════════════════════════════
#
# Windows Defender y SmartScreen bloquean ejecutables sin firma.
# Vina.exe, xTB.exe, y el backend compilado necesitan firma.
#
# Proveedores (precios anuales aproximados):
#   - Sectigo: ~$250-350/año (Code Signing Certificate, OV)
#   - DigiCert: ~$400-500/año
#   - SSL.com: ~$200-300/año
#
# Requisitos:
#   1. Empresa registrada (o DBA/trade name)
#   2. Identidad verificada (documentacion)
#   3. Hardware token USB o HSM (algunos proveedores)
#   4. EV Code Signing para SmartScreen instantaneo (sin "reputacion")
#
# Proceso:
#   1. Comprar certificado de proveedor
#   2. Verificar identidad (1-5 dias habiles)
#   3. Recibir token/hardware
#   4. Firmar binarios con signtool.exe:
#      signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 myapp.exe
#   5. Firmar el instalador .msi completo

CODE_SIGNING_PREP = """
Preparacion para firma de codigo.

1. Lista de archivos a firmar (en orden):
   - tools/vina/vina.exe
   - tools/vina/AutoDock-Vina-GPU-2-1.exe
   - tools/xtb/xtb.exe
   - MolDesign.exe (el binario de Tauri)
   - MolDesign_Installer.msi (el instalador final)

2. Script de firma (sign.ps1):
   $certPath = "C:\certificates\moldesign.pfx"
   $certPass = Read-Host "Cert password" -AsSecureString
   $files = @(
       "tools/vina/vina.exe",
       "tools/vina/AutoDock-Vina-GPU-2-1.exe",
       "tools/xtb/xtb.exe"
   )
   foreach ($f in $files) {
       signtool sign /fd SHA256 /f $certPath /p $certPass `
           /tr http://timestamp.digicert.com /td SHA256 $f
   }

3. Verificar firma:
   signtool verify /pa /v MolDesign.exe

4. Enviar a Microsoft para whitelist (reduce falsos positivos):
   https://www.microsoft.com/en-us/wdsi/filesubmission
"""


# ═══════════════════════════════════════════════════════════════════════════
# 5. SENTRY — Crash reporting
# ═══════════════════════════════════════════════════════════════════════════
#
# Instalacion:
#   pip install sentry-sdk
#   npm install @sentry/nextjs
#
# Configuracion en backend (api/main.py, antes de crear la app):
#   import sentry_sdk
#   sentry_sdk.init(
#       dsn=os.getenv("SENTRY_DSN", ""),
#       environment=os.getenv("APP_MODE", "DESKTOP"),
#       traces_sample_rate=0.1,
#   )
#
# En frontend (next.config.js o app/layout.tsx):
#   El SDK de Next.js se configura automaticamente con @sentry/nextjs
#
# Plan gratuito: 5000 errores/mes. Suficiente para desktop.

SENTRY_SETUP = """
Crash reporting con Sentry.

1. Crear cuenta en https://sentry.io (plan Developer, gratuito)
2. Crear proyecto "MolDesign" (Python + Next.js)
3. Agregar DSN a .env.desktop:
   SENTRY_DSN=https://xxxxx@yyyyy.ingest.sentry.io/zzzzz
4. En modo DESKTOP, los errores se envian anonimizados.
   En modo dev, Sentry se deshabilita (DSN vacio).
5. NO enviar SMILES ni datos de usuario a Sentry.
   Configurar before_send para sanitizar:
   
   def before_send(event, hint):
       if 'smiles' in str(event):
           event['extra'] = {'smiles': '[redacted]'}
       return event
"""
