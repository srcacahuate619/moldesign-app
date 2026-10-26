# Arranque con idioma persistido: IPC y conexión al motor

Fecha de la investigación: **2026-10-07**. Entorno del reporte: esta máquina,
Windows, **Tauri en modo desarrollo**.

## Reporte y diagnóstico

La aplicación arrancó con inglés guardado, se creó un caso y una evaluación
falló con «Failed to fetch». Después de cambiar a español y reiniciar, otra
evaluación funcionó. Los logs aportados mostraban:

```text
IPC custom protocol failed, Tauri will now use the postMessage interface instead
TypeError: Failed to fetch
```

Las trazas llegaban a `invoke → resolveFromDesktop → getApiUrl → AIContext` y a
`listen → DownloadProvider`. Corresponden al transporte IPC entre JavaScript y
Tauri, anterior a las peticiones HTTP a FastAPI. El mensaje anuncia un cambio
al transporte alternativo `postMessage`; **por sí solo no demuestra que se
perdiera la evaluación ni que Vina fallara**.

Se reprodujeron tres defectos o límites del cliente:

1. **CSP sin el origen IPC.** El header generado por `frontend/proxy.ts` no
   permitía `http://ipc.localhost`, usado por el protocolo de Tauri en Windows.
   Permitir `tauri.localhost`, `localhost:*` o el backend en `127.0.0.1` no
   cubría ese origen. Las configuraciones Tauri también carecían de permisos
   explícitos para IPC. No bastaba con suponer que el header de Next se omitía
   dentro de Tauri: `tauri dev` navega al mismo `localhost:3000` que un navegador.
2. **Idioma aplicado a todo `fetch`.** `LanguageProvider` añadía
   `Accept-Language` a cualquier destino, incluidos IPC, assets, WASM y servicios
   externos. Esto sucedía tanto con `es` como con `en`; no se demostró que ese
   header fuera por sí mismo la causa del fallo de transporte.
3. **Recuperación de puerto incompleta.** La recuperación de `api.request()` no
   cubría peticiones directas como preflight de Evaluación, receptores del visor
   y PRO. Las pruebas reprodujeron que seguían fallando si el puerto memorizado
   ya no era el que Rust comunicaba. Es un defecto adicional comprobado, no una
   causa confirmada del reporte original.

**No se reprodujo una causa exclusiva del inglés.** Una evaluación real con
Vina terminó en inglés y otra terminó en español. La mejora observada tras el
reinicio no permite separar el efecto del idioma del resto del estado de arranque.

## Cambios e invariantes

- `frontend/proxy.ts`, `tauri.conf.json`, `tauri.conf.prod.json` y
  `tauri.conf.msix.json` permiten `ipc:` y `http://ipc.localhost` en `connect-src`.
  Desarrollo también declara el origen propio y `data:` para el WASM local.
  No se amplían los permisos de ejecución de scripts ni la lista de motores.
- `frontend/context/LanguageContext.tsx` sólo añade `Accept-Language` cuando el
  destino tiene el origen del backend confirmado por `lib/config.ts`. Se
  suscribe a los cambios de dirección. IPC, archivos y terceros reciben su
  petición original; para la API se conservan cuerpo, sesión, señal y headers.
  La dirección se obtiene fuera del interceptor para evitar recursión:
  resolver `ensure_backend` también puede usar `fetch`.
- `frontend/lib/backendFetch.ts` concentra el transporte de las peticiones REST,
  preflight, binarios y apertura de SSE. Los clientes de Evaluación, PRO,
  visores, cohortes, dossier, MolChat, Molcy, Comunidad y autenticación lo usan.
  Ante un error de red consulta de nuevo la dirección y sólo reenvía si cambió.
  Las peticiones concurrentes comparten la revalidación; HTTP 4xx/5xx y
  cancelaciones no disparan esta recuperación. No se repite a ciegas un POST
  contra el mismo puerto, ni se ordena reiniciar el motor.
- `lib/config.ts` sigue siendo el único dueño de la dirección: en escritorio
  se obtiene de Rust, sin adivinar `:8000`. Los enlaces de medios y el sondeo
  de salud sobre un puerto explícitamente recibido mantienen su función.
- `check-prod-csp.js` comprueba el IPC de Next dev y Tauri, incluye autotests
  que rechazan permisos ausentes y coincidencias parciales y conserva la
  paridad de producción/MSIX.
- `smoke-ipc-csp.mjs` ejecuta el proxy real para obtener su header y prueba un
  `fetch` con headers del protocolo IPC bajo cada CSP. Intercepta el destino en
  Playwright; un caso deliberadamente bloqueado acredita que el test detecta
  la regresión. Forma parte de `smoke:prod`.
- El smoke recorre las 11 rutas exportadas en ambos idiomas, comprueba 12
  endpoints por idioma y falla por errores de red, HTTP 5xx del backend o CSP.
  Sólo excluye `net::ERR_ABORTED`, esperado al navegar y cancelar peticiones.

## Verificación realizada

Medidas de esta investigación, no conteos permanentes del proyecto:

| Comprobación | Resultado y condición |
|---|---|
| Regresión IPC antes de corregir CSP | El fetch quedó bloqueado con el header real del proxy y las tres políticas Tauri leídas directamente de sus archivos. No se evaluó una reescritura de CSP por el empaquetador nativo. |
| Regresión IPC después de corregir CSP | Las cuatro políticas permitieron el fetch; el autotest restrictivo siguió bloqueándolo. |
| Idioma antes de limitar el interceptor | Las pruebas detectaron la modificación indebida de peticiones IPC en `en` y `es`. |
| Recuperación antes de compartir transporte | Preflight y receptor del visor fallaron con un puerto memorizado obsoleto y otro puerto comunicado por Rust simulado. |
| `npm run test:run` | **1.586/1.586**, 170 archivos. Incluye idioma, cancelación, sesión y recuperación compartida del puerto. |
| Verificación tras añadir comentarios y documentación | **49/49** en las cinco suites de idioma, sesión de MolChat, puerto, reintentos de PRO y dossier; `check:csp` también correcto. |
| TypeScript y `npm run build:desktop` | Correctos; export reconstruido después de las correcciones. |
| `npm run check:csp` | Correcto, incluidos autotests y paridad de las políticas producción/MSIX. |
| `check:exported-api-url` / `check:no-remote-assets` | Correctos sobre el export generado. |
| `npm run smoke:prod` | **62/62** con export real, CSP de producción y backend empaquetado, datos temporales, 11 rutas en `en` y `es` y 12 endpoints por idioma con HTTP 200 y `Content-Language` esperado. |
| Evaluación real con Vina 1.2.7 | **SUCCESS** en `en` y `es`, aspirina contra `3F75`, cadena A, con el backend staged y datos temporales. Inglés se ejecutó primero; la segunda ejecución pudo reutilizar caché. No es una comparación de rendimiento ni una validación científica de la pose. |

Las pruebas de navegador usan Chrome/Edge y un puente Tauri simulado. La prueba
IPC acredita el permiso CSP sobre un fetch interceptado, **no la ejecución de
un comando Rust, el fallback nativo, WebView2 ni un instalador nuevo**. El
barrido verifica las rutas y peticiones ejercitadas, no todas las operaciones
posibles de cada pestaña. Tampoco confirma que el inglés causara el fallo
original de evaluación.

## Reproducción de las verificaciones

Desde `frontend/`:

```powershell
npx vitest run context/__tests__/LanguageFetch.test.tsx lib/__tests__/puertoDelMotor.test.ts
npm run check:csp
node scripts/smoke-ipc-csp.mjs
npm run build:desktop
npm run check:exported-api-url
npm run check:no-remote-assets
npm run smoke:prod
```

La prueba IPC independiente usa Edge instalado. El smoke de producción busca
Chrome o Edge y requiere el runtime staged existente. Usa datos temporales.

Para aplicar la configuración a la aplicación de desarrollo hay que **cerrar y
volver a arrancar `tauri dev`**. Recargar componentes por HMR no sustituye el
reinicio del contenedor que carga la CSP. Después puede comprobarse el arranque
con `en` guardado, creación de un caso, evaluación, cierre y reapertura, y
repetir el flujo en `es`; esa comprobación manual con WebView2 sigue siendo
distinta de las pruebas automatizadas descritas arriba.
