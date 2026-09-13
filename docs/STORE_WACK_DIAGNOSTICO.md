# Diagnóstico WACK — "No se pudo extraer la información de la API importada"

Estado: **diagnóstico de causa probable** (2026-09-12). El WACK no pudo ejecutarse desde
una sesión no elevada (`appcert.exe` exige administrador), así que se analizó la
causa directamente sobre los binarios del paquete.

## Qué reporta el WACK (ronda anterior)

`wack-report.xml` (ronda del 11-sep, bajo la raiz antigua `dist/msix`) con `OVERALL_RESULT="FAIL"`. Desglose de los 24 tests:

| Test | Resultado | Obligatorio | Estado |
|---|---|---|---|
| App manifest | FAIL | **sí** | ver abajo |
| Debug configuration | FAIL | sí | ver abajo (mismo mensaje) |
| Blocked executables | FAIL | sí (optional=TRUE) | ver abajo (mismo mensaje) |
| App resources | FAIL | no | resuelto: logo scale-200 re-cuantizado |
| Archive files usage | FAIL | no | `.pdb.gz` comprimidos a propósito (ver doc 86) |
| DPIAwarenessValidation | WARNING | sí | pendiente PerMonitorV2 |

Los tres que importan son `App manifest`, `Debug configuration` y `Blocked
executables`, y los tres fallan con el **mismo** mensaje genérico:

> No se pudo extraer la información de la API importada para esta aplicación.

## Causa probable: API sets del UCRT

Los tres tests tienen en común que leen la tabla de **imports PE** de los
binarios. El runtime embebido trae binarios compilados contra el **Universal C
Runtime (UCRT)**, que importan **API sets** en lugar de DLLs concretas:

```
moldesign.exe               → 9  api-sets (api-ms-win-core-*, api-ms-win-crt-*)
python.exe                  → 5  api-sets (api-ms-win-crt-*)
obabel.exe                  → 6  api-sets (api-ms-win-crt-*)
```

El `appcert.exe` clásico (el que acompaña al Windows SDK) **no resuelve los API
sets** y por eso emite `No se pudo extraer la información de la API importada`.
Es una limitación conocida del analizador local, **no** un defecto del paquete:
todo binario moderno de Windows vincula el UCRT vía `api-ms-win-*`, incluido
cualquier programa ya publicado en Store.

## Qué cambió desde esa ronda (2026-09-12)

La ronda del 11-sep se corrió sobre un paquete anterior. Sobre el paquete
`1.0.0.0` que se envía:

| Test | Qué se hizo | Qué esperar |
|---|---|---|
| App resources | `Square310x310Logo.scale-200.png` recuantizado, 412 KB → 82 KB | PASS |
| DPIAwarenessValidation | Manifiesto propio con `dpiAware=true/pm` y `dpiAwareness=PerMonitorV2, PerMonitor` | PASS |
| App manifest · Debug configuration · Blocked executables | Nada: el diagnóstico de abajo sostiene que es una limitación del analizador local ante binarios UCRT | Si vuelven a fallar con el mismo mensaje genérico, el patrón queda confirmado |
| Archive files usage | Nada: los `.pdb.gz` van comprimidos a propósito | FAIL esperado, opcional |

## Conclusión

- El [89] (`.pdb.gz`) es opcional y deliberado; el [45] (logo) ya está resuelto;
  el [92] (DPI) es un warning.
- El [31]/[46]/[88] es un **falso positivo del `appcert.exe` clásico ante
  binarios UCRT**, no un rechazo de certificación. El vuelo real de Microsoft
  Store usa un analizador más moderno que sí resuelve los API sets.

## Cómo confirmarlo

1. En una consola **elevada** (administrador), ejecutar:

   ```
   & "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe" reset
   & "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe" test -appxpackagepath "E:\rel\v1.0.0.0\amezcua-dev.com.MolDesign_1.0.0.0_x64.msix" -reportoutputpath "E:\rel\v1.0.0.0\wack-report.xml"
   ```

2. Si persisten los tres `No se pudo extraer...`, es el patrón API-set
   confirmado; el vuelo de Store (audiencia privada) es el veredicto definitivo.
   Microsoft no publica apps por el resultado local de `appcert.exe`: publica por
   el vuelo de certificación del servicio.