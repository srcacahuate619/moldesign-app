# Entrega de Sol: CI y sello — MolDesign 1.0.2

> **Nota de reubicación (2026-10-11).** Los worktrees y clones que cita se retiraron el 2026-10-11. El clon `D:\moldesign-ci\sol-1-0-2` se borró; el commit `112a8476` que cita está en `codex/release-hygiene`. La rama `sol/ci-y-sello` sigue existiendo. Índice: [REUBICACIONES_2026-10-11.md](docs/REUBICACIONES_2026-10-11.md).

Encargo: `docs/PROMPT_SOL_CI_Y_SELLO_20261009.md`. Fecha local: 2026-10-09.
Rama: `sol/ci-y-sello`, worktree `D:\moldesign-build\.worktrees\catalogo-demostracion`.
Base autorizada: **d514fe537539cdfcd37a44eeb0cd1819455555e8**.
Código final: **112a8476f92ec250e16699bf0f58485f7a41e837**.
El commit de entrega posterior sólo incorpora documentación y evidencias: no cambia el frontend probado.

## Commits y archivos

Cada causa del 2.1 y cada punto posterior tiene su commit y su fila en `docs/versions/1.0.2_cambios.md`.

| Punto | Commit | Archivos, además del registro de cambios |
|---|---|---|
| 2.1, auditoría crítica | `7cef1d3ccd987ede224625b95ab6d895c07ad73f` | `frontend/package.json`, `frontend/package-lock.json` |
| 2.1, selector desactualizado | `db6714c17238088b1fe232e1b78595c21a606cd8` | `frontend/e2e/session-persistence.spec.ts` |
| 2.2, tres estados | `5abfb6e118166fbe6dec3ed503c50349d909aceb` | `frontend/lib/seccionCatalogo.ts`, nuevo `frontend/lib/__tests__/comparacionConElSello.test.ts`, `frontend/components/science/InsigniaDelCatalogo.tsx`, sus pruebas y `ListasDelCatalogo.test.tsx`, `frontend/context/traducciones/catalogo.ts` |
| 2.3, intervalo | `d17e70b9a7b43bf4679f27431cff12c0405b03fe` | `frontend/components/science/IntentosDeVerificacion.tsx`, sus pruebas, `frontend/context/traducciones/catalogo.ts` |
| 2.4, corrida en cada vista | `112a8476f92ec250e16699bf0f58485f7a41e837` | Nuevos `frontend/components/science/InsigniaDeCorridaGuardada.tsx` y sus pruebas; `frontend/app/preparacion/page.tsx` y `__tests__/pdbDelCatalogo.test.tsx`; `frontend/app/molcy/page.tsx` y `__tests__/page.test.tsx`; `frontend/app/evaluation/batch/page.tsx` y `__tests__/cohortes.test.tsx`; `frontend/components/evaluation/BatchRowResult.tsx`; `frontend/components/science/__tests__/ListasDelCatalogo.test.tsx` |
| Entrega | Commit que contiene este archivo | `ENTREGA_SOL_CI.md`, `docs/verificacion/ci-sello-20261009/`, registro de cambios |

## 2.1: causas reproducidas y corregidas

Reproducción local en Windows, clon independiente, `CI=true`, Node **24.20.0**, npm **11.19.0**, `core.autocrlf=true`; Playwright usa `es-ES`, Edge y un worker como declara el repositorio. Se ejecutan los ocho comandos del job `frontend` en orden. No es una ejecución alojada en GitHub Actions.

**Auditoría de dependencias.** Sobre `d514fe53`, `npm ci` pasa y `npm audit --omit=dev --audit-level=critical` falla: npm informa 32 vulnerabilidades, 3 críticas, 18 altas y 11 moderadas. Las entradas críticas son Next 16.3.4, proxy-addr 2.0.7 (Molstar → Express) y shell-quote 1.10.0 (adaptador móvil de Solana → React Native → react-devtools-core). El JSON completo está en `auditoria-inicial.json`.

En `7cef1d3c` se actualizan Next y eslint-config-next a 16.3.8; el lockfile resuelve proxy-addr 2.0.8 y shell-quote 1.12.0 dentro de los rangos existentes. Cambian 14 versiones contando los binarios de Next, sin agregar paquetes: 1634 entradas antes y después. Comando de resolución: `npm update next eslint-config-next proxy-addr shell-quote --package-lock-only --ignore-scripts`. No se usa `audit fix --force`, no se agregan overrides ni se modifica el umbral. La auditoría posterior pasa el umbral crítico; no implica ausencia de vulnerabilidades.

Se contrastaron las correcciones con los avisos de los mantenedores: [Next](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j), [proxy-addr](https://github.com/jshttp/proxy-addr/security/advisories/GHSA-jqcg-44mw-7w3h) y [shell-quote](https://github.com/ljharb/shell-quote/security/advisories/GHSA-pqg4-j6r4-53mv). El último mantenedor lo clasifica como alto, aunque el informe de npm usado por la puerta lo cuenta entre las entradas críticas. Los números anteriores describen la medición de npm.

**Spec de persistencia.** Sobre `7cef1d3c`, la build web pasa y Playwright informa 12 pruebas aprobadas y una fallida. La spec busca el botón «Crear caso»; la captura y el contexto muestran «Crear un caso», habilitado, con el nombre del caso ya rellenado. El timeout ocurre antes del clic. La migración efectiva del botón al texto `ca_crear_boton` se hizo en **29c6b33b**; la clave española ya existía desde `5ea3c6bf`.

En `db6714c1` sólo cambia el selector a `getByRole("button", { name: "Crear un caso", exact: true })`. Se conservan las aserciones de creación, persistencia, separación Alice/Bob, recuperación de corrida y autorización. No se sube ningún timeout ni se modifica el producto. Se repiten desde `test:e2e` los pasos 6–8: 13/13, 12/12 y export de escritorio aprobado. La evidencia anterior a `test:ux`, que borra `test-results`, queda en `e2e-selector-anterior/`: `error-context.md`, `test-failed-1.png` y `trace.zip`.

No hubo un arreglo del 2.1 que cambiara la interfaz visible; por eso no se requieren capturas nuevas. La captura del fallo sí se conserva. No se modificaron las specs de accesibilidad ni sus reglas.

## 2.2 y 2.3: comportamiento y pruebas

`comparacionConElSello` devuelve `difiere` y `sinDeclarar`, con orden `receptor`, `exhaustiveness`, `num_poses`, `seed`. Lee los dos hashes y las dos declaraciones de semilla. Cualquier valor declarado distinto tiene precedencia; sólo si ninguna declaración está presente (ausencia o `null`) se incluye el campo en `sinDeclarar`. Una vista sin corrida (`null` o `undefined`) no compara; una corrida vacía compara los cuatro campos. La insignia completa distingue los motivos y la compacta usa «Verificado · no describe esta corrida» cuando cualquiera de las listas tiene entradas. Conserva cifras y explicaciones en `title` y `aria-label`, con ambas traducciones.

Pruebas: matriz por campo, hashes contradictorios, semillas contradictorias, declaraciones alternativas, campos distintos y ausentes simultáneos, ninguna advertencia sin corrida, compacto en ambos idiomas y listas reales. La comprobación parcial observada fue **189/189 en 19 archivos**, duración de Vitest 14,97 s; TypeScript sin diagnósticos. Se ejecutó en el worktree sobre `db6714c1` con los cambios posteriormente registrados en `5abfb6e1`.

En los intentos, la segunda frase se elige exclusivamente con un intervalo numérico, finito y ordenado: contiene cero → azar; límite superior negativo → orden inverso; límite inferior positivo → ninguna interpretación. Un IC ausente, `null`, no numérico, infinito o invertido tampoco recibe segunda frase ni provoca una excepción al formatear. GO y conclusiones desconocidas conservan el texto neutral previo. No cambia la puerta científica ni ningún dato del experimento.

Pruebas: intervalos cruzados, extremos iguales a cero, negativos, positivos e inválidos en ambos idiomas, tanto en el bloque completo como en los atributos de la tarjeta; el JSON real de CAL-8HFI-01 sigue diciendo que no se distingue del azar. **125/125 en 8 archivos**, más **13/13** de idiomas y texto fijo; TypeScript limpio. Logs `intervalo-pruebas.log`, `intervalo-typecheck.log`, `sello-idiomas.log`. Se ejecutaron sobre `5abfb6e1` con los cambios posteriormente registrados en `d17e70b9`.

## 2.4: auditoría de todos los usos

Tabla sobre el código final `112a8476`. Las líneas son las de ese commit.

| Uso | Qué muestra | Qué pasa al sello | Razón y cambio |
|---|---|---|---|
| `app/evaluation/batch/page.tsx:604` | Receptor de una definición que aún se va a comprobar | `pdbId`, sin `corrida` | Aún no representa una ejecución; permanece igual |
| `app/evaluation/batch/page.tsx:888` | Corrida de cohorte, evidencia recibida | `receptor.prepared_sha256` como hash; `effective_config` como protocolo; PDB de la evidencia si lo declara | **Cambiado**: antes omitía el hash. `backend/services/cohort/evidence.py` devuelve la procedencia guardada; `runs.py` usa exactamente `prepared_sha256`. No se usa el hash del catálogo ni los ajustes editables |
| `app/evaluation/batch/page.tsx:1076` | Receptor de una definición de cohorte guardada | `receptor_pdb_id`, sin `corrida` | La lista tiene definición, resumen de entrada y elegibilidad; no identifica ni declara una ejecución. Permanece igual |
| `app/preparacion/page.tsx:605` | Corrida auditada | IDs de `auditoria.corrida` al adaptador; éste pasa el resultado exacto | **Cambiado**. La auditoría sólo declara identidad y rótulo, no hash/protocolo. Conserva la precedencia del PDB explícito y el respaldo antiguo por rótulo |
| `app/molcy/page.tsx:385`, fuente Moldex | Corrida guardada | `chosen.id` y `chosen.task_id`; resultado exacto al sello | **Cambiado**. `/molcy/fuentes` declara esos IDs, pero no los parámetros ni el hash; no se derivan de la configuración del vídeo |
| Mismo uso, fuente receptor | Receptor para una escena sin corrida | `chosen.id`, sin `corrida` | Se conserva como receptor; seleccionar una escena no crea un resultado científico |
| `components/evaluation/BatchRowResult.tsx:30` | Corrida de una fila, compacta | `detail.result`; antes de obtenerlo, `{}` | **Cambiado**: la falta de detalle no se trata como tarjeta de receptor. El resultado recibido se asocia a ambos IDs y no se reutiliza para otra fila |
| `BatchRowResult.tsx:42` | Resultado expandido de esa corrida | Resultado crudo de `getEvaluationResult(moleculeId, taskId)` | Ya pasaba hash y protocolo; conserva el comportamiento, con protección de identidad de la fila |
| `components/cases/CaseRunHistoryModal.tsx:499` | Resultado del historial | Resultado crudo del snapshot solicitado con ambos IDs | Correcto, sin cambio |
| `components/interfaces/pro/EvaluationEvidencePanel.tsx:210` | Evidencia de un resultado | `result` crudo, target del contexto | Correcto, sin cambio |
| `components/interfaces/pro/ProEvaluation.tsx:932` | Receptor antes de una ejecución; corrida cuando existe un resultado SUCCESS | `realResult`, que es `null` antes del resultado | Antes del resultado no compara; después utiliza hash/protocolo declarados por el resultado. Correcto, sin cambio |
| `ProEvaluation.tsx:1289` | Resultado SUCCESS | `realResult` crudo | Correcto, sin cambio |
| `components/MoldexCard.tsx:98` | Corrida guardada, compacta | `provenance.receptor_sha256`, `provenance.docking_protocol`, `provenance.random_seed` | Correcto, sin cambio; no usa configuración vigente |
| `app/moldex/page.tsx:903` | Detalle de corrida guardada | Los mismos tres campos de la procedencia de la entrada seleccionada | Correcto, sin cambio |
| `components/science/InsigniaDeCorridaGuardada.tsx:31` | Adaptador de vistas que sólo reciben IDs | Snapshot exacto o `{}` mientras no se puede comprobar | Nuevo. Sólo consulta si el catálogo declara un receptor verificado y hay ambos IDs. No solicita la proyección actual. Ignora respuestas tardías y datos de otra cuenta |
| `components/science/InsigniaDelCatalogo.tsx:42` | Delegación común a la variante verificada | `corrida` recibida sin cambios | Conserva la clasificación del consumidor |
| `components/science/SeccionDelCatalogo.tsx:32` | Tarjeta de receptor en los selectores compartido y Molcy | Verificación del receptor, sin corrida | Correcto: informa de lo medido para ese receptor, sin atribuirlo a una ejecución |
| `components/science/InsigniaDemostracion.tsx` | Alias de compatibilidad | Reexporta `InsigniaDelCatalogo` | No tiene usos de producción adicionales; las pruebas antiguas siguen comprobándolo |

Pruebas de cada uso cambiado: flujo real de la página de lotes con hash igual/distinto/ausente y PDB de evidencia distinto del formulario; Preparación con PDB explícito frente a rótulo y contrato antiguo; Molcy eligiendo corrida y después receptor; fila compacta antes/después de recuperar el resultado y al cambiar `task_id`. El adaptador cubre igualdad, diferencia y ausencia, ambos idiomas, IDs ausentes, fallo del snapshot, respuesta tardía y cambio de cuenta. **240/240 en 15 archivos**, TypeScript limpio y guardián de textos fijo/idiomas sin excepciones nuevas; logs `vistas-pruebas.log`, `vistas-typecheck.log`. Se ejecutaron sobre `d17e70b9` con los cambios posteriormente registrados en `112a8476`.

La primera ejecución de esas pruebas nuevas tuvo una aserción ambigua en Molcy: al seleccionar un receptor verificado existen dos sellos legítimos, en la tarjeta del catálogo y en la fuente seleccionada. La prueba ahora exige exactamente dos visibles y ninguna advertencia de corrida, sin cambiar el producto; se conserva `vistas-pruebas-inicial.log`.

## Registros de comandos

Todas las rutas de esta sección son relativas a `docs/verificacion/ci-sello-20261009/`. Los scripts `ejecutar-ci.ps1` y `ejecutar-worktree.ps1` guardan stdout/stderr, código de salida, duración de pared, fecha UTC y SHA completo. Los pasos e2e/UX incluyen sus prebuilds; la duración de Playwright sola figura dentro del log. Un archivo de TypeScript vacío significa ausencia de diagnósticos, con salida comprobada en el registro.

### Clon, medición inicial

| Paso | Comando | Commit | Salida | Segundos | Registro completo |
|---|---|---|---:|---:|---|
| 01 | `npm ci` | `d514fe53` | 0 | 149.44 | `ci-inicial-01.log` |
| 02 | `npm audit --omit=dev --audit-level=critical` | `d514fe53` | 1 | 2.85 | `ci-inicial-02.log` |

### Clon, dependencias corregidas

| Paso | Comando | Commit | Salida | Segundos | Registro completo |
|---|---|---|---:|---:|---|
| 01 | `npm ci` | `7cef1d3c` | 0 | 107.49 | `ci-corregida-01.log` |
| 02 | `npm audit --omit=dev --audit-level=critical` | `7cef1d3c` | 0 | 2.60 | `ci-corregida-02.log` |
| 03 | `npm run check:csp` | `7cef1d3c` | 0 | 0.77 | `ci-corregida-03.log` |
| 04 | `npm run typecheck` | `7cef1d3c` | 0 | 46.78 | `ci-corregida-04.log` |
| 05 | `npm run test:run` | `7cef1d3c` | 0 | 171.32 | `ci-corregida-05.log` |
| 06 | `npm run test:e2e` | `7cef1d3c` | 1 | 224.96 | `ci-corregida-06.log` |

### Clon, repetición desde el selector corregido

| Paso | Comando | Commit | Salida | Segundos | Registro completo |
|---|---|---|---:|---:|---|
| 06 | `npm run test:e2e` | `db6714c1` | 0 | 61.94 | `ci-e2e-corregida-06.log` |
| 07 | `npm run test:ux` | `db6714c1` | 0 | 51.81 | `ci-e2e-corregida-07.log` |
| 08 | `npm run build:desktop` | `db6714c1` | 0 | 88.39 | `ci-e2e-corregida-08.log` |

### Clon, ocho pasos finales sobre el código definitivo

| Comando | Commit | Salida | Segundos | Registro completo |
|---|---|---:|---:|---|
| `npm ci` | `112a8476` | 0 | 89.29 | `ci-final-01.log` |
| `npm audit --omit=dev --audit-level=critical` | `112a8476` | 0 | 2.23 | `ci-final-02.log` |
| `npm run check:csp` | `112a8476` | 0 | 0.51 | `ci-final-03.log` |
| `npm run typecheck` | `112a8476` | 0 | 29.33 | `ci-final-04.log` |
| `npm run test:run` | `112a8476` | 0 | 143.45 | `ci-final-05.log` |
| `npm run test:e2e` | `112a8476` | 0 | 82.27 | `ci-final-06.log` |
| `npm run test:ux` | `112a8476` | 0 | 48.83 | `ci-final-07.log` |
| `npm run build:desktop` | `112a8476` | 0 | 45.54 | `ci-final-08.log` |

### Export final, comprobaciones adicionales del artefacto

| Comando | Commit | Salida | Segundos | Registro completo |
|---|---|---:|---:|---|
| `npm run check:exported-api-url` | `112a8476` | 0 | 5.96 | `export-check-exported-api-url.log` |
| `npm run check:no-remote-assets` | `112a8476` | 0 | 1.15 | `export-check-no-remote-assets.log` |

Resultado: **8/8 pasos aprobados**, **1777/1777 pruebas en 186 archivos**, **13/13 e2e**, **12/12 UX**, Next 16.3.8 y export estático con normalización RSC y frontera Solana aprobadas. Auditoría de producción: **0 críticos, 18 altos y 11 moderados**. Comprobaciones adicionales sobre `out/`: 253 archivos sin dirección de backend horneada y 18 CSS/HTML sin recursos remotos. Se añadieron estos dos checks por la actualización de Next y el requisito de funcionamiento sin recursos remotos; no cambian los ocho pasos del encargo.

### Worktree, tres comprobaciones finales

| Comando | Commit | Salida | Segundos | Registro completo |
|---|---|---:|---:|---|
| `npm run test:run` | `112a8476` | 0 | 103.93 | `worktree-final-01.log` |
| `npx tsc --noEmit` | `112a8476` | 0 | 5.41 | `worktree-final-02.log` |
| `npm run lint` | `112a8476` | 0 | 59.80 | `worktree-final-03.log` |

Resultado: **1777/1777 pruebas en 186 archivos**, TypeScript sin diagnósticos y **lint con 0 errores y 39 advertencias**. No se silencia ni se amplía una excepción de lint. Los dos árboles probaron el mismo commit y árbol de frontend `f56ccc5115c4f6d9694cebf0c1bb62c9651f7c82`.

El guardián de textos fijos es `lib/__tests__/interfazSinTextoFijo.test.ts`: el filtro adicional `textosSinTraducir.test.ts` del log de intervalos no corresponde a un archivo. El guardián sí se ejecutó por su nombre correcto en `sello-idiomas.log`, `vistas-pruebas.log` y en las dos suites completas finales.

## Alcance, decisiones y límites

- El clon se creó inicialmente con `-b codex/release-hygiene` como decía el encargo; al detectar que el contenido requerido aún estaba en otra rama, se obtuvo la autorización explícita del propietario y se hizo checkout detached de **d514fe53** antes de instalar o probar. No se probó una rama móvil. Las correcciones se trajeron mediante fetch desde el worktree y checkout de los SHA indicados en las tablas.
- Tras arreglar el lockfile se repitió desde `npm ci`, además de los pasos a partir de la auditoría fallida, para demostrar instalación reproducible. Después del fallo e2e se repitió desde el paso 6. Al finalizar se repiten los ocho comandos sobre el código final.
- La consulta adicional del adaptador es una decisión de implementación: las respuestas actuales de Preparación y Molcy sólo tienen IDs, y no se puede suplir la procedencia con los ajustes del caso. Se consulta el endpoint ya existente, sólo para receptores verificados. Con el catálogo real vacío no añade consultas de resultado. Si faltan los IDs o falla el snapshot, se mantiene la incertidumbre; nunca se infiere un valor del sello.
- La validación del IC también rechaza infinitos e intervalos invertidos: son datos inválidos para afirmar azar u orden inverso. No cambia la puerta de aceptación científica.
- Verificados sigue vacío; las entradas verificadas de pruebas son ficticias. No se modificó `backend/`, sus registros, artefactos sellados ni el motor Molcy. Tampoco se modificaron la subida, `CustomReceptorModal.tsx` ni `uploadCustomTarget`.
- La auditoría sólo exige ausencia de críticos. Persisten vulnerabilidades altas y moderadas declaradas en su salida. `npm ci` también declara advertencias de peers/deprecaciones y scripts de instalación no aprobados por npm; no se añadieron aprobaciones globales ni se ocultaron esas advertencias.
- El lockfile cambió. No se regeneró el SBOM del runtime: su generación y el gate de release del artefacto corresponden a la integración/empaquetado posterior. No se afirma que un SBOM anterior describa las versiones nuevas.
- Playwright usa la API simulada que define el repositorio. Los pasos verdes prueban el frontend y su export; no prueban docking real, el runtime Python distribuido ni el instalador. No se ejecutaron backend, `tauri:build`, `stage:desktop`, `smoke:prod` ni cargo, conforme al encargo. No hubo push, merge ni rebase.
- Se restauró `frontend/next-env.d.ts` antes de cada commit. La junction del worktree se retira con `rmdir` literal tras comprobar enlace y destino; se conservan el clon y sus dependencias. El árbol principal no se usa para instalar las dependencias corregidas.

## Estado de entrega

Clon conservado: **`D:\moldesign-ci\sol-1-0-2` (clon borrado el 2026-10-11; su commit está en codex/release-hygiene)**, detached en **112a8476f92ec250e16699bf0f58485f7a41e837**, el commit probado. Tamaño medido: **5 109 544 667 bytes = 4,759 GiB lógicos**, 106 199 archivos, incluidas `.git`, dependencias y builds. Los hardlinks de `.git` cuentan en esa suma: no representa espacio exclusivo ocupado en disco. Fuente: `clon-tamano.json`.

La junction de `frontend/node_modules` se retiró con el comando literal del encargo después de validar que su destino era el `node_modules` de ese clon. Se comprobó que las dependencias tanto del clon como del árbol principal siguen presentes; evidencia en `junction-antes.json` y `junction-despues.json`.

El commit de entrega sólo agrega este informe, las evidencias y la fila final del registro. El frontend conserva el mismo árbol probado. `alcance.json` registra los archivos cambiados y una lista vacía de cambios en las rutas protegidas; `dependencias-comparadas.json` detalla las 14 versiones actualizadas y `entorno.json` registra las versiones utilizadas.

Los logs y el contexto del fallo conservan la salida textual; sólo se normalizan espacios al final de línea y líneas vacías terminales antes de versionarlos. Captura y trace se conservan sin modificar. El worktree queda sin la junction ni cambios sin commitear propios. El clon se deja al propietario, como pidió.
