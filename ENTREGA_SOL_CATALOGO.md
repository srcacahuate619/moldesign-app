# Entrega Sol: catálogo de demostración

> **Nota de reubicación (2026-10-11).** El worktree `catalogo-demostracion` se retiró el 2026-10-11. La rama `sol/catalogo-demostracion` conserva el código y las capturas (`docs/qa/catalogo-demostracion/`). Los enlaces a `D:\moldesign-build\.worktrees\catalogo-demostracion\...` se leen con `git show sol/catalogo-demostracion:<ruta>`. Índice: [REUBICACIONES_2026-10-11.md](docs/REUBICACIONES_2026-10-11.md).

Fecha: 2026-10-09. Encargo: `PROMPT_SOL_CATALOGO_DEMOSTRACION_20261008.md`.
Rama: `sol/catalogo-demostracion`. Worktree: `D:\moldesign-build\.worktrees\catalogo-demostracion`.
Base: `codex/release-hygiene`, commit `cbaf63c4` (1.0.2, receta de receptor 7).

Las fases A–D están implementadas para la revisión de Claude. Verificados permanece vacío.
La sección y sus avisos no modifican la disponibilidad, la selección ni los estados científicos.
La adaptación de la subida de anti-dianas se hizo después de la autorización explícita del propietario.

## Commits y archivos

### `0341d3a2` — Declara las secciones del catálogo y sus avisos medidos

- [backend/api/routers/targets.py](D:/moldesign-build/.worktrees/catalogo-demostracion/backend/api/routers/targets.py)
- [backend/core/models.py](D:/moldesign-build/.worktrees/catalogo-demostracion/backend/core/models.py)
- [backend/data/avisos_catalogo.json](D:/moldesign-build/.worktrees/catalogo-demostracion/backend/data/avisos_catalogo.json)
- [backend/data/receptores_verificados.json](D:/moldesign-build/.worktrees/catalogo-demostracion/backend/data/receptores_verificados.json)
- [backend/services/targets/seccion_catalogo.py](D:/moldesign-build/.worktrees/catalogo-demostracion/backend/services/targets/seccion_catalogo.py)
- [backend/tests/test_seccion_catalogo.py](D:/moldesign-build/.worktrees/catalogo-demostracion/backend/tests/test_seccion_catalogo.py)
- [docs/api/test-counts.json](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/api/test-counts.json)
- [docs/versions/1.0.2_cambios.md](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/versions/1.0.2_cambios.md)

### `04a0082a` — Divide los selectores en verificados, propios y demostración

- [docs/versions/1.0.2_cambios.md](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/versions/1.0.2_cambios.md)
- [frontend/app/molcy/__tests__/page.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/app/molcy/__tests__/page.test.tsx)
- [frontend/app/molcy/page.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/app/molcy/page.tsx)
- [frontend/components/interfaces/pro/TargetSelectorModal.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/TargetSelectorModal.tsx)
- [frontend/components/interfaces/pro/__tests__/TargetSelectorModal.render.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/__tests__/TargetSelectorModal.render.test.tsx)
- [frontend/components/molcy/CatalogoReceptoresMolcy.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/molcy/CatalogoReceptoresMolcy.tsx)
- [frontend/components/molcy/__tests__/CatalogoReceptoresMolcy.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/molcy/__tests__/CatalogoReceptoresMolcy.test.tsx)
- [frontend/components/science/SeccionDelCatalogo.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/science/SeccionDelCatalogo.tsx)
- [frontend/context/traducciones/catalogo.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/context/traducciones/catalogo.ts)
- [frontend/context/traducciones/index.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/context/traducciones/index.ts)
- [frontend/hooks/useCatalogoDeReceptores.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/hooks/useCatalogoDeReceptores.ts)
- [frontend/lib/__tests__/seccionCatalogo.test.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/lib/__tests__/seccionCatalogo.test.ts)
- [frontend/lib/api.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/lib/api.ts)
- [frontend/lib/seccionCatalogo.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/lib/seccionCatalogo.ts)

### `c0d60228` — Declara la demostración en resultados, corridas y auditorías

- [docs/versions/1.0.2_cambios.md](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/versions/1.0.2_cambios.md)
- [frontend/app/evaluation/batch/page.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/app/evaluation/batch/page.tsx)
- [frontend/app/molcy/page.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/app/molcy/page.tsx)
- [frontend/app/moldex/page.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/app/moldex/page.tsx)
- [frontend/app/preparacion/page.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/app/preparacion/page.tsx)
- [frontend/components/MoldexCard.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/MoldexCard.tsx)
- [frontend/components/cases/CaseRunHistoryModal.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/cases/CaseRunHistoryModal.tsx)
- [frontend/components/evaluation/BatchRowResult.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/evaluation/BatchRowResult.tsx)
- [frontend/components/interfaces/pro/EvaluationEvidencePanel.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/EvaluationEvidencePanel.tsx)
- [frontend/components/interfaces/pro/ProEvaluation.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/ProEvaluation.tsx)
- [frontend/components/science/InsigniaDemostracion.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/science/InsigniaDemostracion.tsx)
- [frontend/components/science/__tests__/InsigniaDemostracion.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/science/__tests__/InsigniaDemostracion.test.tsx)
- [frontend/hooks/useCatalogoDeReceptores.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/hooks/useCatalogoDeReceptores.ts)

### `8821ba47` — Agrupa las anti-dianas y reutiliza la subida existente

- [docs/versions/1.0.2_cambios.md](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/versions/1.0.2_cambios.md)
- [frontend/components/interfaces/pro/AntiDianasSelector.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/AntiDianasSelector.tsx)
- [frontend/components/interfaces/pro/CustomReceptorModal.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/CustomReceptorModal.tsx)
- [frontend/components/interfaces/pro/__tests__/AntiDianasSelector.catalogo.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/__tests__/AntiDianasSelector.catalogo.test.tsx)
- [frontend/components/interfaces/pro/__tests__/CustomReceptorModal.antiDiana.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/__tests__/CustomReceptorModal.antiDiana.test.tsx)
- [frontend/lib/antiDianas.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/lib/antiDianas.ts)

### `e53e69dd` — Traduce los encabezados de familia del selector

- [docs/versions/1.0.2_cambios.md](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/versions/1.0.2_cambios.md)
- [frontend/components/interfaces/pro/TargetSelectorModal.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/TargetSelectorModal.tsx)
- [frontend/components/interfaces/pro/__tests__/TargetSelectorModal.render.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/interfaces/pro/__tests__/TargetSelectorModal.render.test.tsx)
- [frontend/context/traducciones/catalogo.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/context/traducciones/catalogo.ts)

### `b296b18c` — Conserva la atribución de la insignia en corridas históricas

- [docs/versions/1.0.2_cambios.md](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/versions/1.0.2_cambios.md)
- [frontend/components/cases/CaseRunHistoryModal.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/cases/CaseRunHistoryModal.tsx)
- [frontend/components/cases/__tests__/CaseRunHistoryModal.catalogo.test.tsx](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/components/cases/__tests__/CaseRunHistoryModal.catalogo.test.tsx)
- [frontend/lib/__tests__/seccionCatalogo.test.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/lib/__tests__/seccionCatalogo.test.ts)
- [frontend/lib/seccionCatalogo.ts](D:/moldesign-build/.worktrees/catalogo-demostracion/frontend/lib/seccionCatalogo.ts)

### Commit de entrega — Documenta la entrega y las comprobaciones del catálogo

Este documento y las capturas se incluyen en ese commit. Su hash se obtiene con
`git log -1 --format="%h %s" -- ENTREGA_SOL_CATALOGO.md`; no se incluye dentro del
propio archivo porque cambiaría el hash que intenta registrar.

- [ENTREGA_SOL_CATALOGO.md](D:/moldesign-build/.worktrees/catalogo-demostracion/ENTREGA_SOL_CATALOGO.md)
- [docs/versions/1.0.2_cambios.md](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/versions/1.0.2_cambios.md)
- [docs/qa/catalogo-demostracion/selector-es.png](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/qa/catalogo-demostracion/selector-es.png)
- [docs/qa/catalogo-demostracion/selector-en.png](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/qa/catalogo-demostracion/selector-en.png)
- [docs/qa/catalogo-demostracion/capturas.json](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/qa/catalogo-demostracion/capturas.json)

## Pruebas añadidas

Backend: **19 pruebas nuevas** en `test_seccion_catalogo.py`: registro real vacío,
privados y comunidad, evidencia completa inyectada, bloques ausentes o vacíos,
receta diferente, archivo ausente/corrupto, los 16 avisos y transporte por el
router sin cambiar disponibilidad. La prueba del registro real falla si se
añade cualquier verificado sin sustituir deliberadamente ese guardián.

Frontend: **23 pruebas nuevas**:

| Archivo | Nuevas | Qué demuestra |
|---|---:|---|
| `lib/__tests__/seccionCatalogo.test.ts` | 5 | Contrato antiguo, evidencia incompleta, orden, caché por PDB y aislamiento entre sesiones; también identificador ausente/vacío. |
| `components/interfaces/pro/__tests__/TargetSelectorModal.render.test.tsx` | 5 | Tres secciones reales, estado vacío, cifras de una entrada inyectada, avisos, selección, búsqueda de propios/comunidad y traducción inglesa de familias. |
| `components/molcy/__tests__/CatalogoReceptoresMolcy.test.tsx` | 1 | Fuentes antiguas, disponibilidad, búsqueda y apertura de la subida existente. |
| `components/science/__tests__/InsigniaDemostracion.test.tsx` | 3 | Aviso visible sin backend, petición compartida y ausencia de insignia para propios/comunidad/evidencia completa. |
| `components/interfaces/pro/__tests__/AntiDianasSelector.catalogo.test.tsx` | 4 | Agrupación en ambos idiomas, selección disponible, indisponibilidad, búsqueda de propias, subida/refresco y referencias conservadas. |
| `components/interfaces/pro/__tests__/CustomReceptorModal.antiDiana.test.tsx` | 2 | FormData del modal existente: `is_anti_target=true` sólo en modo anti-diana; nombre, archivo y cadena conservados. |
| `components/cases/__tests__/CaseRunHistoryModal.catalogo.test.tsx` | 3 | Una corrida anterior o sin huella no hereda el receptor privado del sistema actual. |

Las referencias a 8HFI y sus cifras son fixtures de prueba; no se añadió una
entrada a `receptores_verificados.json`. Se actualizaron las dos comprobaciones
de Molcy que esperaban el selector nativo anterior.

## Comandos y resultados

Todos los comandos se ejecutaron desde el worktree. No se instalaron nuevas dependencias.

| Comando | Resultado |
|---|---|
| `npm run test:run -- --maxWorkers=4` desde `frontend` | Código de salida 0: 179 archivos, 1658 pruebas pasaron; 188,73 s. Incluye el guardián de textos e idiomas. |
| `npx tsc --noEmit` desde `frontend` | Código de salida 0, sin diagnósticos. |
| `npm run lint` desde `frontend` | Código de salida 0: 0 errores, 39 advertencias. No se ejecutó `--fix`. |
| Pytest del contrato y rutas (comando de abajo) | 81 pasaron; 2 advertencias; 33,44 s. |
| Pytest de preflight privado y política de búsqueda | 7 pasaron; 1 advertencia; 4,53 s. |
| `python-embed scripts/report_test_counts.py --write` desde la raíz del worktree | Código de salida 0; 3993 pruebas de backend **recolectadas**, no ejecutadas. |
| Render e idiomas tras revisar las capturas | 23 pasaron en 2 archivos. |
| Historial y ayudante tras corregir la atribución | 37 pasaron en 3 archivos. |
| `git diff --check cbaf63c4` | Código de salida 0, sin incidencias de whitespace. |

Frontend usó TEMP y TMP dentro de `frontend/.tmp` para que Vite no dependiera
de una caché temporal que desaparecía. La limitación a cuatro workers sólo
regula concurrencia; ejecuta toda la suite:

```powershell
Set-Location 'D:\moldesign-build\.worktrees\catalogo-demostracion\frontend'
$env:TEMP = (Resolve-Path '.tmp').Path
$env:TMP = $env:TEMP
npm run test:run -- --maxWorkers=4
npx tsc --noEmit
npm run lint
```

Las suites que cubren el router se localizaron buscando sus imports y usos.
Se ejecutaron con Python embebido 3.11.9, desde `backend`:

```powershell
Set-Location 'D:\moldesign-build\.worktrees\catalogo-demostracion\backend'
& 'D:\moldesign-build\python-embed\python.exe' -m pytest tests/test_seccion_catalogo.py tests/test_target_authorization.py tests/test_catalogo_sin_barrido.py tests/test_la_advertencia_de_calibracion_no_se_pierde.py tests/test_resincronizacion_catalogo.py tests/test_resolucion_del_catalogo_coincide_con_su_estructura.py tests/test_phase7_api_contract.py -q -p no:cacheprovider
& 'D:\moldesign-build\python-embed\python.exe' -m pytest tests/test_preflight_targets_privados.py tests/test_search_policy_phase1.py -q -p no:cacheprovider
Set-Location 'D:\moldesign-build\.worktrees\catalogo-demostracion'
& 'D:\moldesign-build\python-embed\python.exe' scripts/report_test_counts.py --write
```

El sandbox bloqueó `asyncio.socketpair()` en Windows al crear el event loop:
el traceback quedó detenido en `socket.accept`. Las ejecuciones atascadas se
detuvieron y esas suites se ejecutaron después con permiso de escalación.
Las advertencias del backend fueron de deprecación de httpx/FastAPI y ProDy/NumPy.

Durante QA hubo fallos corregidos antes de entregar: dos expectativas antiguas
del selector nativo de Molcy; acceso al rótulo de una corrida ausente en mocks
de Preparación; una opción de Testing Library que TypeScript no admitía;
traducciones redundantes de términos idénticos; y la caché de React creada para
capturas, que lint estaba analizando. Se borró sólo esa caché temporal.
No se modificaron guardianes ni se ampliaron sus excepciones.

Una pasada de la suite completa falló en la prueba existente «ofrece instalación
explícita cuando falta Molecular Nodes»: no encontró el botón en estado
`cy_addon_installing` dentro de su espera de 5 s. Se repitió toda la suite sin
cambios y pasaron las 1658 pruebas. Se declara el fallo de espera; no se da por
diagnosticada su causa ni se modificó el flujo de instalación para ocultarlo.

## Capturas y alcance de la comprobación visual

- [Selector en castellano](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/qa/catalogo-demostracion/selector-es.png)
- [Selector en inglés](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/qa/catalogo-demostracion/selector-en.png)
- [Encabezados y errores de navegador](D:/moldesign-build/.worktrees/catalogo-demostracion/docs/qa/catalogo-demostracion/capturas.json)

Se renderizó el **componente real** del selector con sus providers y CSS, en un
servidor Vite local temporal. Edge headless abrió una sesión aislada por idioma,
a 1440×1800. La muestra tiene 1UZJ y 5COP del catálogo, los avisos y disponibilidad
reales de los JSON, y ningún receptor propio ni verificado. Se normalizaron los
flags al tipo booleano que sirve la API. Las peticiones se limitaron a localhost.
Las capturas finales se inspeccionaron y registran las tres secciones, textos
vacíos, subida y aviso medido; no hubo errores de JavaScript.
El navegador y servidor se cerraron; los archivos del harness se retiraron.
Esto demuestra la presentación del componente en desarrollo, no el artefacto instalado.

## Lo que no se verificó

- No se ejecutaron `tauri:build`, `stage:desktop` ni `smoke:prod`, conforme al encargo.
  Tampoco se probó el export con la CSP de producción ni el instalador.
- No se ejecutó una corrida científica, una subida real de PDB o un render de Molcy
  con el backend. La subida se probó en el frontend inspeccionando FormData;
  la API del catálogo se probó con fixtures del router.
- No se ejecutaron las 3993 pruebas de backend. Pasaron las 88 relacionadas con
  este contrato y sus rutas; el número de 3993 es sólo colección.
- No se midió pose ni calibración de ningún receptor. Verificados queda vacío.
- La evidencia visual cubre el selector compartido; las demás superficies se
  comprobaron con las pruebas automatizadas, sin recorrido manual completo.
- Dossier, PDF, acta/vídeo de Molcy, certificación y cualquier nuevo requisito
  científico de Preparación siguen a cargo de Claude, como exige el encargo.

## Decisiones y diferencias respecto al encargo

1. **Subida de anti-dianas:** la API tenía `is_anti_target`, pero el modal no
   enviaba ese campo. Se detuvo esa adaptación y se consultó al propietario,
   que respondió **«Adaptar el modal existente (recomendado)»**. Se añadió una
   prop opcional al mismo modal y se reutilizó el endpoint; no se creó otro flujo.
   Tras éxito se invalida la caché y se usa el refresco existente del panel.
2. **Comunidad:** se conserva dentro de Tus receptores, fuera del catálogo
   incluido, con su rótulo Comunidad y autor. Mantiene sus permisos y la subida
   privada mantiene la acción de compartir.
3. **Molcy:** tenía un selector nativo separado. Se añadió un componente de
   presentación con las tres secciones y búsqueda; su disponibilidad sigue
   viniendo de las fuentes de Molcy, no del nuevo estado del catálogo.
4. **Insignias:** se añadió un hook pequeño para consumir la caché existente
   sin mantener una segunda copia caducada. Su identidad y caducidad se
   respetan; sin dato se muestra demostración. El texto explicativo es visible,
   no depende del hover. No se escribió sección nueva en snapshots científicos.
5. **Preparación:** el contrato del rótulo de corrida usa `PDB · nombre`.
   Se extrae el PDB de ese rótulo, con fallback al sistema del caso si falta;
   sólo se añadió el aviso de cabecera. No se alteran cálculo ni estados.
6. **Historial:** una huella distinta o ausente impide usar el receptor del
   sistema actual para quitar la insignia de una corrida antigua. La ausencia
   de identificador también conserva el valor seguro de demostración.
7. **Accesibilidad:** las tarjetas del selector compartido conservan el click
   y añaden un botón de selección accesible por teclado, con la misma
   indisponibilidad de antes. Las secciones tienen encabezados reales.
8. **Traducciones de familias:** la captura inglesa mostró los encabezados
   existentes en castellano. Se tradujo sólo la presentación, sin modificar
   `targetGrouping`, sus claves ni el orden; los términos iguales en ambos
   idiomas conservan su nombre.
9. **Avisos:** se leyó la fuente citada de
   `D:\moldesign-build\.worktrees\receptores-20261008\docs\auditorias\receptores-continuacion-20261008\ensamblajes_validacion_resumen.json`,
   campo `entries_needing_site_chain_reannotation`. Coincide exactamente con
   los 16 PDB del encargo, sin cambios de lista. Ese otro worktree sólo se leyó.
10. **Entorno:** se reutilizó node_modules mediante junction para las pruebas.
    Al terminar se verificó que apuntaba exactamente al node_modules del árbol
    principal y se quitó con `cmd.exe /d /c rmdir` sobre la ruta literal del
    enlace, sin borrado recursivo. La junction ya no existe; el node_modules
    real y su dependencia Vitest permanecen.

No se modificaron los artefactos científicos sellados, el motor vendorizado,
la CSP ni los guardianes de build. Los únicos archivos de backend modificados
son los autorizados en la fase A. No se hizo push, fusión ni rebase. La rama
queda disponible para la revisión de Claude.
