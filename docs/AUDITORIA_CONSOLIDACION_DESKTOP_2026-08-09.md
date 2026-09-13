# Auditoría de consolidación desktop

**Proyecto:** MolDesign  
**Fecha:** 2026-08-09  
**Estado:** Informe técnico de auditoría estática  
**Objetivo:** Consolidar MolDesign como producto **desktop-first**, reduciendo deuda heredada de cloud sin alterar el pipeline de producción que funciona actualmente.

---

# Rebaseline vigente — 2026-08-15

**Plan operativo derivado:**
[`43_PLAN_ACCION_MADUREZ.md`](43_PLAN_ACCION_MADUREZ.md).

> **Esta sección reemplaza el estado operativo de la auditoría del 9 de agosto.**
> Los hallazgos F-01…F-23 y los addenda posteriores se conservan debajo como
> trazabilidad histórica: explican por qué se hicieron los cambios, pero ya no
> deben leerse como una lista de pendientes actual. Este rebaseline inspeccionó
> el árbol de trabajo presente —incluidos cambios todavía no committeados— y
> ejecutó las comprobaciones disponibles con el runtime desktop embebido.

## Dictamen actualizado

MolDesign cambió de categoría en cinco días: ya no es un prototipo desktop que
convive accidentalmente con una arquitectura SaaS, sino una aplicación local
con contratos explícitos para SQLite, filesystem, cola local, health semántico,
CSP de producción, manifiesto de modelos y degradación de componentes
opcionales. La mayor parte de la auditoría original quedó efectivamente
superada.

Sin embargo, **el repositorio actual no está en estado de release reproducible**.
El smoke de infraestructura local pasa, pero las tres suites principales tienen
regresiones; el CI no ejecuta frontend; hay documentación normativa que ya quedó
atrás del código; y el nuevo pose-selector reveló que el generador del manifiesto
puede borrar su identidad de release. El pipeline que hoy usa el usuario puede
seguir funcionando, pero eso no equivale a que el estado completo del repositorio
sea verde ni a que una máquina limpia pueda reconstruir exactamente ese estado.

La mejora más importante es científica y cultural: el proyecto ahora registra
refutaciones, corrige métricas inválidas y mantiene modelos NO-GO fuera de
producción. Fase B no reemplazó indebidamente a Fase A; los errores de RMSD de
MolFlex fueron identificados; y Ruta C promovió XGBoost v0.6 en vez de una GNN
que no superó el baseline. Esa disciplina aporta más credibilidad que una tabla
de resultados formada únicamente por éxitos.

## Estado revalidado de F-01…F-23

| Hallazgo original | Estado 2026-08-15 | Evidencia / reserva actual |
|---|---|---|
| F-01 APP_MODE | **Cerrado** | `Settings` es la fuente efectiva y existe `test_app_mode.py`; Tauri fuerza `DESKTOP`. |
| F-02 Celery dispatcher | **Cerrado** | La rama Celery y `celery_app.py` salieron del dispatcher. Schema v3 migró el nombre persistido a `task_id` con backfill y alias API temporal. |
| F-03 storage MinIO | **Parcial** | `local_storage.py` es el backend real, pero `file_handlers.py` aún conserva un guard CLOUD/MinIO, configuración y aliases legacy. No borrarlo de golpe: todavía tiene callers. |
| F-04 PostgreSQL/JSONB | **Cerrado con archivo histórico** | SQLite tiene tipos nativos/versionado; SQL PostgreSQL vive bajo `legacy_postgres/`. Persisten comentarios y nombres JSONB históricos. |
| F-05 instalación/CI | **Reabierto parcialmente** | README y CI usan `requirements-desktop.txt` y existe lockfile; no obstante, las suites no están verdes, frontend no corre en CI y el manifiesto de requisitos contiene comentarios contradictorios. |
| F-06 documentación | **Parcial** | `docs/INDEX.md` ya clasifica histórico/normativo, pero no incorpora 38–42/arquitectura y varios documentos “vigentes” contradicen el estado real. |
| F-07 health Tauri | **Cerrado** | Polling HTTP valida identidad, versión, modo y SQLite; mata el hijo si no queda saludable. |
| F-08 build mutante | **Cerrado** | Configuración `tauri.conf.prod.json` separada; el build ya no depende de reescribir el manifiesto base. |
| F-09 cross-env/CLI | **Cerrado** | `cross-env` y `@tauri-apps/cli` están declarados. |
| F-10 diagnóstico | **Mayormente cerrado** | Logs por timestamp, puntero latest y health semántico. Falta convertir fallos de componentes científicos en UX de recuperación verificable. |
| F-11 CSP | **Cerrado para release** | El check de producción pasa sin `unsafe-eval`; queda `unsafe-inline` aceptado/documentado. |
| F-12 auth local | **Cerrado** | Desktop login está explícito; cualquier auth remota debe permanecer opcional. |
| F-13 integraciones | **Cerrado normativamente** | Existe política de integración/consentimiento y se retiró Sentry. Falta hacer cumplir esa política con tests de red cero. |
| F-14 bridge rescoring | **Cerrado en runtime** | `rescoring_bridge.py` concentra paths/import; quedan `sys.path` en scripts/tests de investigación, no en el entrypoint productivo. |
| F-15 concurrencia SQLite | **Cerrado condicionado** | Benchmark justifica 4 workers bajo transacciones cortas. `requirements-desktop.txt` aún dice `max_workers=1` y debe corregirse. |
| F-16 matriz CI | **Reabierto** | Backend/rescoring están configurados, pero fallan hoy; frontend y Tauri no forman parte del gate. |
| F-17 modularidad | **Vigente** | `chat_service.py` ~2,986 líneas, `pdf_generator.py` ~1,649, `queue_handler.py` ~1,608 y `evaluation.py` ~1,200 concentran demasiados contratos. |
| F-17a colección/tests | **Reabierto por regresión** | La colección termina, pero ya no pasa: ver matriz ejecutada debajo. |
| F-18 holdout contaminado | **Cerrado** | El 0.8732 está invalidado; Fase A usa holdout scaffold-disjoint y hashes. |
| F-19 identidad de artefactos | **Parcial / crítico** | El manifiesto base existe, pero su generador v3 sobrescribe la entrada v4 del pose-selector. |
| F-20 shift Vina | **Cerrado para Fase A** | Gate ejecutado: importancia Vina 2.8%, PASS. Debe revalidarse por cada nuevo modelo. |
| F-21 dominio/fallback | **Parcial** | UI/API muestran modelo, fallback y dominio. Sigue faltando incertidumbre calibrada del score de afinidad y evidencia suficiente por familias pequeñas. |
| F-22 dynamic box | **Parcial** | Implementación y fixes existen; `docs/35` mantiene un caso APO abierto y no hay benchmark general que cierre calidad geométrica. |
| F-23 ejecución reproducible | **Parcial** | Hay lockfile, smoke, hashes y protocolos; falta un E2E científico real de release y reparar las suites. |

## Comprobaciones ejecutadas en este rebaseline

| Comprobación | Resultado observado | Lectura correcta |
|---|---|---|
| CSP de producción | **PASS** | Sin `unsafe-eval`; `unsafe-inline` continúa como excepción explícita. |
| Gate de importancia Vina | **PASS** | Share 0.0284 < 0.10 para el modelo Fase A. |
| Smoke desktop submit → polling → SQLite → filesystem | **PASS** | Valida infraestructura y persistencia local; el docking/scoring está deliberadamente simulado, por lo que **no** es un E2E científico. |
| Frontend Vitest | **80 passed, 3 failed** | Regresión en parsing/persistencia del stream de `AIContext`; `[DONE]` entra como contenido y se pierden warning/partial. |
| Next.js production build | **FAIL** | Conflicto de tipos entre dos copias/versiones de Vite en `vitest.config.ts:31`; compila el bundle pero falla el type-check. |
| Tauri `cargo check` | **PASS con 1 warning** | El launcher Rust compila; `last_error` recibe un valor inicial nunca leído. |
| Backend pytest | **258 passed, 17 failed, 7 errors** | Fallos en certifier, contrato sync/async de llama-server, registro de `selectivity` y aislamiento de DB/fixtures. |
| Rescoring pytest | **284 passed, 25 failed, 6 skipped** | Tests/código divergen en extractor, pose filter, familias curadas, entrenamiento sintético y fallback GNN (`NaN` vs 0.5). |
| `git diff --check` | **FAIL menor** | Línea vacía adicional al EOF de `.gitignore`; además hay normalización LF→CRLF pendiente en múltiples archivos. |

Las cifras anteriores describen el árbol de trabajo auditado, no necesariamente
el último commit. Parte de los fallos puede ser prueba obsoleta frente a un
contrato nuevo —por ejemplo, la etapa `selectivity` fue añadida al registro sin
actualizar `CANONICAL_STAGE_ORDER`—, pero mientras no se clasifique y corrija,
el resultado de release sigue siendo rojo.

## Hallazgos vigentes que deben atenderse ahora

### R-01 — P0: restablecer un gate de release realmente verde

El principal riesgo ya no es Celery/PostgreSQL: es que el proyecto evolucionó
más rápido que su malla de regresión. Debe congelarse temporalmente la expansión
funcional y clasificar cada fallo como: regresión de código, expectativa de test
obsoleta o defecto de aislamiento. Prioridad concreta:

1. Alinear `selectivity` entre registro, orden canónico, eventos SSE y frontend.
2. Reparar el contrato HTTPX sync/async de `LocalLLM`; ningún test debe intentar
   red real cuando su probe está mockeado.
3. Aislar el engine SQLite en tests: hoy parte del bootstrap abre
   `%USERPROFILE%/MolDesign/data/moldesign_local.db` en vez del path inyectado.
4. Resolver la divergencia del extractor/pose filter/familias antes de afirmar
   que rescoring es reproducible desde una instalación limpia.
5. Añadir Vitest y un `cargo check`/build Tauri al CI de release.
6. Deduplicar/alinear Vite–Vitest: el build de producción falla hoy por tipos
   incompatibles en `vitest.config.ts`, aunque la compilación del bundle termine.

**Criterio:** backend, rescoring y frontend verdes en un runner limpio; smoke
local y gate científico ejecutados desde el mismo lock de release.

### R-02 — P0: hacer monotónico el manifiesto de artefactos

`docs/42` y el runtime declaran manifest v4 con `pose_selector_v06`, pero
`rescoring/scripts/generate_model_manifest.py` todavía genera v3 y únicamente
registra `model_a_universal`. Ejecutar ese script elimina silenciosamente la
identidad del selector. Este rebaseline reprodujo el defecto; se restauró la
entrada v4 usando los SHA-256 actuales del modelo, metadata y dataset.

**Acción:** convertir el generador en fuente completa del schema v4, añadir modo
`--check` no mutante y testear que nunca disminuya `manifest_version` ni pierda
modelos ya declarados. Health/release deben verificar hashes, no sólo exponer
el JSON.

### R-03 — P1: completar la purga cloud sin romper contratos locales

La purga principal avanzó, pero quedan rastros activos:

- `utils/cache.py` conserva implementación Redis completa aunque
  `_redis_available()` esté fijado a `False`.
- `/evaluation/stream/{task_id}` llama `get_redis()` y en desktop devuelve
  `stream_unavailable`; el timeline en vivo no tiene transporte local real.
- `file_handlers.py` conserva un bootstrap MinIO para un modo CLOUD retirado.
- `config.py`, excepciones, tipos frontend y nombres DB mantienen Redis/MinIO/
  Celery; algunos son contratos persistidos y requieren migración, no borrado.
- los mensajes frontend todavía traducen errores `celery`/`redis`.

**Secuencia segura:** implementar primero un bus local de eventos (cola
`asyncio`/registro por job o polling incremental); migrar callers de aliases de
storage; versionar el rename de campos persistidos; luego retirar imports,
settings y mensajes. No mezclar esta purga con cambios científicos.

### R-04 — P1: corregir documentación normativa y contrato de endpoints

El backend expone actualmente **98 decoradores de ruta**. `docs/31` documenta
26 exports base + 31 Pro y se identifica correctamente en el índice como
snapshot histórico, por lo que ya no puede usarse como mapa vigente de API.
Además:

- `docs/42` abre como “pendiente de aprobación”, pero luego declara las fases
  0–4 terminadas; duplica el paso 8 y deja refutaciones como pendientes después
  de reportarlas ejecutadas.
- `docs/INDEX.md` no incorpora 38–42 ni `ARCHITECTURE_DESKTOP.md` en sus
  secciones actuales y su fecha quedó en 2026-08-13.
- el README enlaza como documentación principal un checklist histórico y
  publica una tabla de benchmark incompleta con `...`.
- `requirements-desktop.txt` afirma simultáneamente que `slowapi` no se instala
  y lo declara; también documenta `max_workers=1` mientras producción usa 4.
- el catálogo fuente contiene **387** receptores, no 386; los claims deben
  derivarse automáticamente del artefacto para no volver a divergir.

**Acción:** generar OpenAPI durante CI y compararlo con un snapshot versionado;
crear un documento API vigente desde ese schema; rebaselinar INDEX/README/42 y
añadir un linter de claims (conteo de targets, versión de modelo, métricas).

### R-05 — P1 científico: separar “mejora prometedora” de “claim validado”

El pose-selector Ruta C v0.6 es una mejora real en el holdout congelado de 47
complejos: top-1 ≤2 Å de **0.660 vs 0.532** para Vina y RMSD mediano de
**1.428 vs 1.765 Å**. Pero:

- no alcanza el objetivo preregistrado final de 0.70;
- el 0.852 aplica sólo a los aceptados tras abstener en 43% de los casos;
- el test tiene 87.2% de complejos con alguna pose positiva, frente a 67.2% en
  train, por lo que debe reportarse rendimiento condicionado a “existe una pose
  recuperable” y estratificado por fuente/familia;
- falta validación externa temporal o por benchmark independiente;
- la GNN quedó honestamente refutada a esta escala y no debe aparecer como
  ventaja del selector de producción.

La forma correcta de comunicarlo hoy es: **“selector experimental integrado,
mejora a Vina en holdout interno y puede abstener; pendiente de validación
externa”**, no “pose prediction resuelta”.

### R-06 — P1 científico: el modelo de afinidad muestra transferencia limitada

Fase A mantiene su holdout original honesto (Spearman 0.6094), pero al evaluarlo
en el nuevo holdout de 512 complejos cae a **0.2494**; Fase B mejora sobre Fase A
en ese mismo conjunto hasta **0.3857**, aunque correctamente queda **NO-GO** por
no superar el baseline preregistrado. Esto no invalida Fase A, pero sí demuestra
que 0.6094 no debe presentarse como rendimiento universal esperado.

**Acción:** investigar el shift entre ambos holdouts (familia, año, afinidad,
scaffold, calidad estructural, fuente y disponibilidad de features), publicar
curvas de calibración/cobertura y usar lenguaje de dominio de aplicabilidad en
toda salida comercial o FEP-ready.

### R-07 — P2: reducir concentración de riesgo

Los módulos gigantes siguen siendo una barrera para revisión open source y para
evitar regresiones cruzadas. Prioridad por riesgo, no por tamaño puro:

1. separar transporte SSE/LLM, persistencia de conversación y respuesta
   determinista de `chat_service.py`;
2. dividir submit/job lifecycle, etapas científicas y persistencia de
   `queue_handler.py`;
3. generar secciones PDF desde view-models versionados en lugar de consultar
   campos dispersos dentro de `pdf_generator.py`;
4. extraer contratos de descarga/reporte/stream de `evaluation.py`.

## Prioridad de maduración propuesta

| Orden | Entregable | Condición de salida |
|---|---|---|
| 1 | Release stabilization | Tres suites verdes + CSP + Vina gate + smoke. |
| 2 | Manifest v4 reproducible | Generador idempotente, `--check`, hashes verificados en health/release. |
| 3 | Event bus desktop | SSE/progreso local sin Redis ni degradación funcional. |
| 4 | Docs-as-code | OpenAPI snapshot, INDEX vigente, claims derivados de artefactos. |
| 5 | Validación científica externa | Pose-selector y afinidad evaluados fuera de los conjuntos usados para decidir arquitectura. |
| 6 | FEP+ ready export | Estados/protonación/tautomería, series con conectividad, atom mapping, pose QA, provenance y export contractual; no sólo un score agregado. |

## Opinión actual del proyecto

Sí vale la pena seguir desarrollándolo. El valor diferencial ya no es sólo
“elegir receptor, dibujar y ejecutar”: es que MolDesign puede convertirse en la
capa local, auditable y accesible que convierte una idea química en un paquete
de decisión preparado para escalar a métodos más costosos. Los 387 receptores,
la ingesta de receptores propios, el pipeline unificado y la nueva disciplina de
validación forman una base difícil de replicar.

El peligro principal es de narrativa y control de cambios: el código avanza tan
rápido que tests, manifiestos y documentos quedan obsoletos dentro de horas. Si
se estabiliza esa capa, MolDesign tiene una propuesta open source defendible.
Si se anuncia como sustituto de FEP+ o como predictor universal antes de la
validación externa, perdería precisamente la confianza que sus nuevos
protocolos honestos están empezando a construir.

---

## Resumen ejecutivo

MolDesign posee un pipeline desktop operativo y de valor científico real: la evaluación local se ejecuta con FastAPI, un dispatcher local, SQLite, almacenamiento en disco y los motores científicos instalados en la máquina. La auditoría confirma que el flujo principal **no necesita Celery, Redis, MinIO ni PostgreSQL** para ejecutar una evaluación desktop.

El principal riesgo de consolidación no es el pipeline científico, sino la coexistencia de rutas cloud heredadas dentro de módulos que siguen activos. La purga debe ser gradual y protegida por pruebas de regresión; eliminar archivos por el nombre de una tecnología cloud podría romper interfaces que hoy dan servicio al modo local.

### Dictamen

El proyecto está en una posición buena para madurar como aplicación desktop. La prioridad inmediata debe ser convertir la intención de arquitectura en una garantía verificable: **un solo modo de ejecución, un contrato de almacenamiento local, una cola local, una caché local y documentación que describa exactamente el código distribuido.**

---

## 1. Alcance y método

Esta auditoría fue de solo lectura y se basó en la inspección de configuración, entrypoint, routers, dispatcher, almacenamiento, caché, dependencias, CI y documentación. No se modificó código ni se ejecutó el pipeline científico.

La clasificación usada es:

| Clasificación | Significado |
|---|---|
| **Crítico** | Puede cambiar el comportamiento de desktop o bloquear reproducibilidad. |
| **Alto** | Deuda activa que incrementa riesgo de regresión o mantenimiento. |
| **Medio** | Funcionalidad opcional o documentación incongruente. |
| **Conservar** | Integración externa compatible con desktop; no es cloud heredado. |

---

## 2. Camino de ejecución desktop verificado

El flujo principal identificado es:

```text
POST /evaluation/submit
  -> services.docking.queue_handler.submit_evaluation_job()
  -> _submit_evaluation_desktop()
  -> _run_full_evaluation_async()
  -> SQLite + filesystem local + Vina + rescoring/pipeline científico
```

Elementos que soportan este flujo:

- `backend/services/docking/queue_handler.py`: dispatcher local y registro de jobs desktop.
- `backend/core/database.py`: engine SQLite asíncrono, WAL y reintentos ante locks.
- `backend/utils/file_handlers.py`: escribe archivos en `local_data_dir` en modo desktop.
- `backend/utils/cache.py`: aplica caché en memoria; `_redis_available()` devuelve `False`.
- `backend/api/routers/evaluation.py`: envía la evaluación al dispatcher local.

**Conclusión operativa:** la eliminación de la infraestructura cloud debe conservar estas interfaces y probar el flujo anterior de punta a punta.

---

## 3. Hallazgos que deben resolverse con urgencia

### F-01 — Dos fuentes de verdad para el modo de ejecución

**Severidad:** Crítico  
**Evidencia:** `core/config.py` define `app_mode` con default `DESKTOP`, pero varios módulos consultan directamente `os.getenv("APP_MODE", "CLOUD")`, incluidos `api/dynamic_limiter.py`, `services/docking/preparer.py` y `utils/file_handlers.py`.

**Riesgo:** si una ejecución no exporta explícitamente `APP_MODE`, parte de la aplicación interpreta cloud aunque `Settings` diga desktop. Esto puede provocar límites, rutas o comportamiento de herramientas inconsistentes.

**Acción requerida:**

1. Establecer `Settings.app_mode` como fuente única de verdad.
2. Sustituir los defaults implícitos `"CLOUD"` por consultas a `get_settings().is_desktop`.
3. Añadir una prueba que arranque el backend sin `APP_MODE` y demuestre comportamiento desktop.
4. Registrar al inicio el modo efectivo, ruta de datos y backend de almacenamiento/cola.

**Criterio de cierre:** ninguna rama del runtime desktop depende directamente de un default `CLOUD` en variables de entorno.

### F-02 — Ramas Celery/Redis conservadas en el dispatcher activo

**Severidad:** Alto  
**Evidencia:** `queue_handler.py` importa condicionalmente `api.celery_app` y mantiene una rama `run_full_evaluation.apply_async`. `api/celery_app.py` existe exclusivamente por compatibilidad.

**Riesgo:** aunque el submit desktop usa `_submit_evaluation_desktop`, la dependencia y el código cloud siguen compartiendo el mismo módulo crítico. Cambios futuros pueden reactivar la rama incorrecta o romper imports.

**Acción requerida:**

1. Congelar con pruebas el contrato de `submit_evaluation_job` y `_DesktopTask`.
2. Eliminar la rama Celery del dispatcher en una PR independiente.
3. Eliminar `api/celery_app.py` cuando no tenga importadores.
4. Retirar Celery, Redis, Kombu, Flower y dependencias relacionadas de la instalación desktop.
5. Cambiar mensajes de error que indican “verifica Celery y Redis” por mensajes propios de la cola local.

**Criterio de cierre:** `git grep` no encuentra importaciones de Celery/Redis en el runtime desktop, y las pruebas de submit, estado, cancelación y recuperación de jobs pasan.

### F-03 — Abstracción de archivos local cubierta por nomenclatura MinIO

**Severidad:** Alto  
**Evidencia:** `utils/file_handlers.py` es usado activamente y en desktop escribe en disco, pero expone `get_minio_client`, `ensure_bucket_exists`, errores y comentarios de MinIO/S3.

**Riesgo:** una purga agresiva de este archivo rompería la preparación de targets, conformers y poses. La deuda es conceptual, no una razón para borrar el adaptador.

**Acción requerida:**

1. Mantener los nombres lógicos de objetos (`targets/`, `ligands/`, `poses/`) para no romper datos existentes.
2. Extraer una interfaz `LocalStorage` clara, con operaciones de escribir, leer, verificar, borrar temporal y descargar PDB.
3. Migrar los importadores a esa interfaz.
4. Retirar el cliente y los branches MinIO/S3 cuando los importadores estén migrados.
5. Documentar el directorio real de datos y una política de backup/limpieza.

**Criterio de cierre:** el pipeline puede preparar un receptor, guardar conformer/poses y recargarlos tras reiniciar, sin paquetes ni configuración MinIO.

### F-04 — Capa de datos desktop sobre modelos con legado PostgreSQL

**Severidad:** Alto  
**Evidencia:** `core/database.py` crea SQLite, pero `core/models.py` usa tipos PostgreSQL (`JSONB`, `UUID`) y `database.py` registra un compilador SQLite para `JSONB`. Persisten migraciones SQL para PostgreSQL.

**Riesgo:** la compatibilidad actual es pragmática, pero está basada en una adaptación interna. Una purga de PostgreSQL sin pruebas ORM puede romper serialización de JSON, UUIDs o esquemas existentes.

**Acción requerida:**

1. Considerar SQLite como plataforma de referencia y documentar versión/schema soportado.
2. Crear una migración local versionada, o un mecanismo de versionado explícito de schema SQLite.
3. Añadir pruebas de round-trip para JSON, UUID, hotspots, resultados de evaluación y persistencia de poses.
4. Solo después, retirar migraciones PostgreSQL y dependencias `asyncpg` del producto desktop.

**Criterio de cierre:** una base SQLite nueva y una existente pueden arrancar, migrar y ejecutar una evaluación sin tipos o herramientas PostgreSQL.

### F-05 — Documentación y automatización de instalación no reflejan el producto real

**Severidad:** Crítico  
**Evidencia:** `README.md` y `.github/workflows/ci.yml` invocan `requirements.txt` en la raíz, pero el archivo no existe. El manifiesto desktop real es `backend/requirements-desktop.txt`. El CI solo ejecuta `rescoring/tests/`.

**Riesgo:** el proyecto no ofrece hoy un camino verificable de “clonar, instalar y probar”; eso limita adopción, reproducibilidad y confianza científica.

**Acción requerida:**

1. Definir un único comando de instalación desktop oficialmente soportado.
2. Corregir README, BUILD_GUIDE, CONTRIBUTING y CI para usarlo.
3. Hacer que CI ejecute las pruebas backend relevantes, además de rescoring.
4. Publicar la plataforma soportada: Windows, Python, Conda/pip, binarios y requisitos de RAM/GPU.

**Criterio de cierre:** una máquina limpia puede seguir el README y llegar a una prueba smoke o suite verde sin conocimiento tácito.

### F-06 — Documentos de estado históricos se presentan como actuales

**Severidad:** Medio  
**Evidencia:** `docs/24_OSS_READINESS_CHECKLIST.md` reporta como ausentes README, licencia, CI y CONTRIBUTING, aunque existen actualmente. Otros documentos hacen referencia a adaptadores eliminados (`db_factory.py`, `dispatcher.py`, `storage.py`).

**Riesgo:** la documentación interna contradice el repositorio y dificulta determinar qué decisiones siguen vigentes.

**Acción requerida:**

1. Etiquetar documentos como `Vigente`, `Histórico`, `Plan` o `Evidencia experimental`.
2. Crear un índice documental con dueño, fecha de verificación y ruta de código asociada.
3. Mover postmortems/checklists históricos a una sección de archivo, no borrarlos.
4. Añadir revisión de enlaces y rutas en CI.

**Criterio de cierre:** un lector nuevo puede identificar la documentación normativa sin contrastar manualmente decenas de archivos.

---

## 4. Inventario de integraciones y decisión recomendada

| Componente | Papel actual | Decisión recomendada |
|---|---|---|
| Celery / Redis | Legado cloud; desktop usa dispatcher y cache locales. | Retirar gradualmente. |
| MinIO / S3 | Legado cloud; filesystem local atiende el pipeline. | Retirar el branch, conservar la abstracción local. |
| PostgreSQL / asyncpg | Legado de modelo/infraestructura; SQLite es runtime real. | Retirar en fase posterior a pruebas ORM. |
| Comunidad remota | Endpoints de compartir/sincronizar targets. | Eliminar o feature flag si el producto es offline-first. |
| Supabase / OAuth Google/Azure | Identidad opcional. | Decisión de producto independiente; no tocar junto al pipeline. |
| Sentry | Telemetría opcional. | Conservar solo si hay política de privacidad y consentimiento. |
| Steam | Licenciamiento/distribución desktop. | Conservar si Steam es canal comercial. |
| RCSB PDB | Fuente externa de estructuras. | Conservar; es una dependencia científica funcional. |
| Proveedores LLM externos | Funcionalidad opcional de MolChat. | Mantener como opt-in; separar del núcleo científico. |
| Solana | Certificación opcional. | Separar como plugin/feature opcional si no es parte del producto base. |

---

## 5. Plan de consolidación recomendado

### Fase 0 — Congelar y proteger (inmediata)

- No borrar archivos cloud todavía.
- Crear un smoke test desktop reproducible: arranque, submit de SMILES de referencia, polling de estado, resultado persistido y lectura de poses.
- Capturar un baseline: versiones, hash de modelos, configuración Vina, SQLite y resultados esperados.
- Corregir la fuente única `APP_MODE` antes de otros refactors.

### Fase 1 — Convertir runtime a desktop explícito

- Simplificar dispatcher: conservar solo ejecución local y recuperación/cancelación de jobs.
- Simplificar cache: conservar cache en memoria, eventos y API de uso; retirar Redis.
- Simplificar almacenamiento: conservar rutas lógicas y disco local; retirar MinIO.
- Actualizar mensajes de diagnóstico para no mencionar infraestructura inexistente.

### Fase 2 — Consolidar dependencias y datos

- Separar `requirements-desktop.txt` como manifiesto canónico y generar lockfile reproducible.
- Remover dependencias cloud no usadas tras comprobar imports.
- Formalizar el schema SQLite y su política de migración.
- Probar actualización desde una base local existente, no únicamente instalación limpia.

### Fase 3 — Claridad de producto y documentación

- Definir qué servicios externos siguen siendo soportados y cuáles son plugins/opcionales.
- Actualizar README, BUILD_GUIDE, CONTRIBUTING, `.env.example` y CI desde el código real.
- Crear `docs/ARCHITECTURE_DESKTOP.md` como fuente normativa de arquitectura.
- Archivar documentos históricos y eliminar enlaces rotos o instrucciones obsoletas.

---

## 6. Matriz mínima de pruebas de no regresión

| Prueba | Protege |
|---|---|
| Arranque sin `APP_MODE` | Default desktop real. |
| Submit/polling/cancelación de job | Dispatcher local y API. |
| Evaluación de SMILES de referencia | Pipeline científico completo. |
| Reinicio de aplicación + lectura de resultado | SQLite y almacenamiento local persistentes. |
| Guardar/leer conformer, receptor y poses | Contrato de storage local. |
| Carga de target curado y auto-ingestado | Catálogo, ingestión y preparación. |
| Reporte PDF y resultado API | Contrato frontend/backend. |
| Instalación desde guía oficial | Reproducibilidad operativa. |

Ningún componente cloud debe retirarse hasta que las pruebas afectadas estén automatizadas y verdes.

---

## 7. Definición de "madurez desktop"

MolDesign estará consolidado como producto desktop cuando cumpla estas condiciones:

1. Una instalación limpia sigue una guía única y produce una evaluación verificable.
2. El runtime no importa ni configura Celery, Redis, MinIO, PostgreSQL o servicios cloud heredados.
3. SQLite, cache local, cola local y filesystem local tienen contratos y pruebas explícitas.
4. Las integraciones remotas son opcionales, visibles y no bloquean el núcleo científico.
5. El README, CI, dependencias y documentación de arquitectura describen el mismo producto.
6. Cada release puede asociar resultados científicos a versión de código, datos, modelos y configuración.

---

## 8. Decisiones que requieren producto, no solo refactor

Antes de eliminar estas capacidades, debe decidirse explícitamente si forman parte del producto desktop:

- Login remoto y proveedores OAuth.
- Certificación Solana.
- Venta/verificación Steam.
- Sincronización de targets comunitarios.
- Telemetría Sentry.
- Proveedores LLM externos.

Estas integraciones no son necesarias para el pipeline científico, pero no deben eliminarse bajo la etiqueta genérica “cloud” si resuelven una necesidad comercial, de distribución o de colaboración.

---

## Conclusión

La dirección correcta no es una purga indiscriminada, sino una **consolidación contract-first**: primero proteger el comportamiento desktop actual con pruebas, después retirar cada implementación cloud detrás de ese contrato y finalmente actualizar la documentación para que sea una representación fiel del producto distribuido.

El trabajo más urgente es resolver la ambigüedad de `APP_MODE`, reparar el camino oficial de instalación/CI y fijar pruebas de no regresión para la cola, almacenamiento y persistencia locales. Con esas bases, la purga de la infraestructura heredada será segura y el proyecto avanzará de una aplicación funcional a una plataforma desktop madura y auditable.

---

# Addendum A — Auditoría ampliada de producción, seguridad y ciencia

**Fecha de ampliación:** 2026-08-09  
**Método:** inspección estática de código, manifiestos, artefactos, pruebas y documentación.  
**Límite:** los hallazgos no implican que el pipeline actual esté fallando; distinguen riesgo confirmado, inconsistencia documental y validación aún requerida. Las métricas científicas se consideran publicables solo cuando el protocolo y los artefactos asociados estén verificados mediante ejecución reproducible.

## A.1 Hallazgos de producción y empaquetado

### F-07 — El launcher Tauri confirma un puerto ocupado, no la identidad del backend

**Severidad:** Alto  
**Evidencia:** `frontend/src-tauri/src/lib.rs` reserva un puerto entre 8000–8020, inicia Uvicorn y `wait_for_port()` considera éxito que `TcpListener::bind()` falle. No hace una solicitud a `/health` ni valida la respuesta de MolDesign.

**Riesgo:** un proceso no relacionado que ocupe el puerto, o un backend que abra el socket pero falle durante el bootstrap, puede ser tratado como backend listo. El frontend podría conectarse a una instancia ajena, a una instancia obsoleta o recibir errores ambiguos.

**Acción requerida:** reemplazar el chequeo de disponibilidad de socket por polling HTTP a un endpoint health versionado que compruebe al menos: identidad de aplicación, versión, modo desktop, SQLite disponible y binarios críticos declarados. El launcher debe matar el hijo si no queda saludable antes del timeout.

**Criterio de cierre:** una prueba de integración simula un puerto ocupado por un proceso ajeno y confirma que MolDesign no lo acepta como backend.

### F-08 — El build de producción modifica un archivo versionado de configuración

**Severidad:** Alto  
**Evidencia:** `frontend/scripts/set-prod-csp.js` reescribe `frontend/src-tauri/tauri.conf.json` y crea `tauri.conf.json.backup`; `restore-csp.js` intenta restaurarlo antes de desarrollo.

**Riesgo:** un build puede dejar el working tree modificado, producir diferencias no intencionadas entre builds y desarrollo, o empaquetar una CSP distinta de la revisada. Este patrón también complica CI y reproducibilidad de releases.

**Acción requerida:** usar configuraciones inmutables por entorno (`tauri.conf.desktop.json`, `tauri.conf.dev.json`) o una plantilla generada en un directorio temporal de build. Nunca modificar el manifiesto versionado durante una compilación.

**Criterio de cierre:** `npm run build`/`tauri build` no modifica archivos rastreados por Git y la CSP final se valida desde el artefacto empaquetado.

### F-09 — Posible dependencia de build no declarada

**Severidad:** Alto  
**Evidencia:** `tauri.conf.json` usa `cross-env BUILD_TARGET=desktop npm run build`, pero `frontend/package.json` no declara `cross-env` entre dependencias o devDependencies.

**Riesgo:** el build puede depender de una instalación global o de estado accidental de la máquina de desarrollo.

**Acción requerida:** añadir la dependencia explícita o reemplazarla por una forma soportada por el shell/runner de build. Validar en entorno limpio.

### F-10 — Health, diagnóstico y recuperación deben ser contratos de release

**Severidad:** Medio  
**Evidencia:** el backend ofrece health checks y el launcher captura `backend.log`, pero el launcher sobrescribe el log por inicio y no valida salud semántica antes de exponer el puerto.

**Acción requerida:** rotar logs con timestamp, incluir versión/configuración no sensible y un código de diagnóstico de startup. Añadir una pantalla de error que distinga “Python no empaquetado”, “Vina no encontrado”, “base SQLite bloqueada” y “modelo ML no disponible”.

---

## A.2 Hallazgos de seguridad y superficie local

### F-11 — Seguridad de CSP: mitigación parcial y configuración con estado mutable

**Severidad:** Medio  
**Evidencia:** `docs/30_SECURITY_CSP_AUDIT.md` documenta nonce CSP para Next.js y el manifiesto Tauri conserva `unsafe-inline` y `unsafe-eval` como base. La eliminación de `unsafe-eval` depende del script mutante descrito en F-08.

**Riesgo:** la política efectiva depende del orden de comandos de build/dev. Aunque la aplicación sea local y el iframe de Ketcher esté sandboxed, una CSP no determinista dificulta demostrar el hardening de release.

**Acción requerida:** hacer la CSP de producción inmutable y verificable; añadir una prueba que falle si el artefacto desktop contiene `unsafe-eval` sin una excepción explícitamente aceptada.

### F-12 — Autenticación local: código y documentación deben alinearse

**Severidad:** Medio  
**Evidencia:** el encabezado de `api/routers/auth.py` todavía menciona SHA-256+salt, pero el código actual usa bcrypt si está disponible y PBKDF2 como fallback.

**Riesgo:** la documentación de seguridad resulta engañosa para auditorías internas; el fallback debe ser una decisión consciente de distribución, no un comportamiento implícito si falta una dependencia.

**Acción requerida:** corregir el docstring, exigir bcrypt en el bundle de producción y añadir tests de hash/verify/migración de hashes legacy. Mantener autenticación como superficie local: el backend está ligado a `127.0.0.1` desde Tauri, lo cual reduce exposición de red, pero no elimina la necesidad de proteger datos locales.

### F-13 — Integraciones externas deben tener una política de consentimiento y degradación

**Severidad:** Medio  
**Evidencia:** existen proveedores LLM externos, RCSB PDB, Solana, Steam, Sentry y OAuth; el núcleo científico puede funcionar sin varios de ellos.

**Acción requerida:** documentar por integración: datos transmitidos, endpoint, finalidad, default (off/on), forma de desactivar y comportamiento offline. Esta política debe estar visible en la UI y en la guía de privacidad.

---

## A.3 Hallazgos de ingeniería y calidad

### F-14 — El backend y el sidecar de rescoring siguen acoplados por `sys.path`

**Severidad:** Alto  
**Evidencia:** `api/main.py` y `services/rescoring_service.py` modifican `sys.path` y establecen rutas de artefactos mediante variables de entorno antes de importar `rescoring`.

**Riesgo:** el orden de importación, el directorio de trabajo y el bundle determinan el comportamiento. Es funcional como puente de migración, pero frágil para packaging, pruebas aisladas y actualizaciones de modelos.

**Acción requerida:** convertir `rescoring/` en un paquete Python instalable o encapsularlo detrás de una interfaz local con rutas inyectadas por configuración. Centralizar el registro de artefactos en un único módulo.

**Criterio de cierre:** el backend arranca desde cualquier directorio permitido por el instalador sin mutar `sys.path` globalmente.

### F-15 — Concurrencia desktop y SQLite requieren evidencia bajo carga

**Severidad:** Alto  
**Evidencia:** el dispatcher define `DESKTOP_MAX_CONCURRENCY = 4`, mientras SQLite/WAL sigue teniendo un único escritor y el código conserva reintentos de lock. La documentación del propio módulo reconoce problemas históricos de lock/deadlock.

**✅ RESUELTO (2026-08-13):** benchmark automatizado en `scripts/benchmark_sqlite_concurrency.py` (patrón de escritura real: molecule → result → hotspots JSON compartido → status, con `commit_with_retry`/`flush_with_retry` reales y engine réplica de `_create_engine()`). Medición: 8 y 32 evaluaciones por ronda en concurrencia 1/2/4 — **0 lock errors, 0 retries activados, 0 fallos**; throughput crece con concurrencia (2,282 evals/min @4). Consistencia verificada (sin duplicados/huérfanos, `integrity_check='ok'`). El cuello de botella NO es la ruta de escritura (transacciones cortas de v1.7.4 funcionan); la restricción real es CPU (docking/ML). **Veredicto: mantener `DESKTOP_MAX_CONCURRENCY = 4`** mientras las transacciones sigan siendo cortas. Regresión automática: `backend/tests/test_concurrency_benchmark.py` (concurrencia 2, invariante de consistencia).

**Riesgo:** cuatro evaluaciones pueden ser aceptables para cálculo, pero deben probarse con la frecuencia real de commits, poses y resultados. Sin un benchmark de estrés reproducible, el ajuste es una hipótesis operativa.

**Acción requerida:** ejecutar y automatizar una prueba con 1, 2 y 4 evaluaciones, medir throughput, locks, reintentos, fallos y consistencia de resultados. Elegir el límite por evidencia y exponerlo como configuración avanzada, no constante tácita.

### F-16 — CI no representa la matriz de riesgo del producto

**Severidad:** Alto  
**Evidencia:** el workflow instala una ruta de dependencias inexistente en raíz y solo invoca las pruebas de rescoring, mientras hay pruebas en `backend/tests/`, regresiones MolChat y pruebas frontend.

**Acción requerida:** definir jobs separados para backend unitario, rescoring, frontend unitario/lint/typecheck, empaquetado Tauri y smoke desktop. Las pruebas científicas largas deben separarse de CI rápido, pero conservar un artefacto/versionado de sus resultados.

### F-17 — Módulos grandes concentran demasiados contratos

**Severidad:** Medio  
**Evidencia:** `queue_handler.py`, `api/routers/evaluation.py`, `services/pipeline/runner.py`, `core/models.py`, `db/repository.py` y `services/ai/chat_service.py` concentran lógica extensa y transversal.

**Riesgo:** cambios de UI, persistencia, scoring y errores operativos se propagan en archivos de alto radio de impacto.

**Acción requerida:** no refactorizar por tamaño solamente. Extraer primero contratos verificables: estado de job, resultados serializables, persistencia, ejecución de stages y políticas de fallback. Cada extracción debe preservar tests de integración.

### F-17a — La colección de pruebas no completó en la ventana de auditoría

**Severidad:** Medio  
**Evidencia:** el 2026-08-09 se ejecutó `python -m pytest backend/tests rescoring/tests --collect-only -q` desde la raíz del repositorio. No ejecuta pruebas, pero tampoco completó la colección en 60 segundos y terminó por timeout, sin diagnóstico emitido.

**✅ RESUELTO (2026-08-13):** tras F-14 (bridge rescoring) y F-04 (tipos SQLite nativos), la colección completa termina en ~13s: `backend/tests` 266 tests en 13.1s, `rescoring/tests` 301 tests en 12.6s. La causa era la carga de imports pesados/sys.path durante el import de tests, ya eliminada. Criterio cumplido.

**Interpretación:** no prueba que las pruebas estén rotas; sí prueba que el descubrimiento no es actualmente una comprobación rápida y observable en este entorno. Puede deberse a imports pesados, inicialización de modelos, rutas o dependencias.

**Acción requerida:** medir el collection time por paquete, impedir carga de modelos/servicios externos durante import de tests y añadir un job CI que reporte fallos de colección con un timeout explícito y salida diagnóstica.

---

## A.4 Auditoría científica y de reproducibilidad

### F-18 — P0 científico: el holdout del modelo universal de producción está contaminado

**Severidad:** Crítico — bloquea claims de generalización del modelo XGBoost universal.  
**Evidencia:** `docs/08_SCIENTIFIC_VALIDATION.md` y `rescoring/artifacts/README.md` registran explícitamente que `model_a_universal.json` fue entrenado por `train_families.py` sin excluir `split_config.json["frozen_test_set"]` (327 complejos). La cifra de holdout ρ=0.8732 está marcada como invalidada/retractada.

**Impacto:** ningún texto de producto, paper, deck o README debe presentar esa métrica como evaluación independiente, ni inferir generalización desde ella.

**Acción requerida:** reentrenar el artefacto de producción con exclusión efectiva del holdout; registrar hash de datos, split, código, parámetros, semilla, artefacto y entorno; ejecutar `evaluate_test_set.py` sobre el artefacto nuevo y publicar intervalos de confianza. Mantener los resultados anteriores con etiqueta `INVALIDATED` para trazabilidad.

**Criterio de cierre:** un test programático prueba que train IDs y frozen-test IDs son disjuntos antes de entrenar, y el reporte independiente referencia el hash del modelo distribuido.

### F-19 — Separar con rigor el modelo distribuido, el código de inferencia y la evidencia publicada

**Severidad:** Alto  
**Evidencia:** el runtime apunta a `model_a_universal.json` y `skip_prolif=True`; documentos históricos mencionan `model_a.json` legacy con 176 features. El artefacto README identifica correctamente al universal como canónico, pero persisten referencias que describen el modelo legacy como default.

**Riesgo:** un lector o pipeline de release puede evaluar, empaquetar o citar un artefacto diferente del servido por la aplicación.

**Acción requerida:** crear un `model-manifest.json` versionado y leído por el runtime, con nombre, hash SHA-256, feature schema, dataset/split, fecha de entrenamiento, estado científico y métricas válidas. La app debe exponer ese manifiesto en `/health` o `/about`.

### F-20 — Distribution shift declarado: Vina está en inferencia y a cero en entrenamiento

**Severidad:** Alto para interpretación científica; no implica por sí mismo un bug.  
**Evidencia:** `rescoring/artifacts/README.md` indica que las cuatro features Vina son cero en entrenamiento y reales en inferencia, argumentando que el modelo les asigna importancia cercana a cero.

**Riesgo:** la conclusión es razonable como hipótesis documentada, pero requiere una prueba de paridad sobre el artefacto distribuido. Si una versión futura aprende pesos no nulos, este comportamiento se vuelve un cambio de distribución no controlado.

**Acción requerida:** añadir un quality gate que reporte importance y sensibilidad de las features Vina para cada artefacto; bloquear release si el modelo depende de una feature cuyo régimen de entrenamiento e inferencia difiere.

### F-21 — Cobertura por familia y dominio de aplicabilidad deben condicionar el lenguaje de producto

**Severidad:** Alto  
**Evidencia:** la validación reporta tamaños muy bajos en GPCR (14), receptor nuclear (15) y proteasa (40); algunos modelos familiares hacen fallback al universal. `docs/19_LIMITATIONS.md` además delimita explicitamente receptores no proteicos, glicanos, metales y pockets multichain.

**✅ RESUELTO (2026-08-13):** la UI muestra ahora `model_used` (familia/universal), `fallback_reason` (quality gate: Spearman≥0.5 & p<0.05), `in_applicability_domain` (Mahalanobis vs core threshold) y el contexto de scoring en los tabs Parámetros/Alertas/Explicabilidad. `engine_used` quedó None (no se produce en el path real de evaluación — el `RouterResult` de `model_router.py` no está en ese path). Pendiente honesto: "incertidumbre" numérica por predicción y desglose de desempeño por familia siguen como follow-up científico (Fase B).

**Acción requerida:** la API/UI debe mostrar familia, aplicabilidad, fallback usado, incertidumbre y warning de dominio. Las afirmaciones de desempeño se deben desglosar por familia y nunca extender a DNA/RNA, glycans o targets fuera de cobertura sin estudio dedicado.

### F-22 — Dynamic box: la implementación actual debe reemplazar el diagnóstico histórico

**Severidad:** Medio  
**Evidencia:** `services/docking/preparer.py` ya incorpora un fallback `compute_dynamic_box` cuando el centro recibido es `(0,0,0)`, mientras `docs/19_LIMITATIONS.md` describe la función como desconectada del runtime.

**Riesgo:** no se puede saber por documentación si el fix fue validado en targets nuevos; el documento de limitaciones se volvió parcialmente histórico.

**Acción requerida:** actualizar el documento con estado “implementado, pendiente de benchmark” y añadir casos de receptor sin centro curado, multichain y cofactors. No declarar el problema resuelto hasta medir calidad de docking.

### F-23 — Reproducibilidad científica debe incluir ejecución, no solo artefactos

**Severidad:** Alto  
**Evidencia:** existen reportes, datasets, scripts y semillas; sin embargo el README no da un camino válido de instalación/benchmark y hay claims/plans con estados diferentes.

**Acción requerida:** para cada resultado publicable, generar un paquete de evidencia con comando exacto, dataset hash, split hash, modelo hash, configuración Vina, binarios/versiones, plataforma, salida JSON y figura derivada. Idealmente, un comando debe regenerar el reporte sin editar paths manuales.

---

## A.5 Consistencia documental: divergencias confirmadas

| Fuente | Inconsistencia | Remediación |
|---|---|---|
| `README.md` y CI | Usan `requirements.txt` de raíz inexistente. | Establecer instalación desktop canónica. |
| `docs/24_OSS_READINESS_CHECKLIST.md` | Declara ausentes archivos que ya existen. | Archivar/rebaselinar como histórico. |
| `docs/31_PIPELINE_DATA_INVENTORY.md` | Describe un mock frontend que documentos posteriores indican resuelto. | Etiquetar como snapshot histórico y enlazar al contrato actual. |
| `docs/19_LIMITATIONS.md` | Declara desconectado el dynamic box, mientras el preparer actual incluye fallback. | Actualizar estado y ejecutar benchmark de confirmación. |
| `docs/08_SCIENTIFIC_VALIDATION.md`, `docs/INDEX.md`, `docs/README.md` | El primero invalida el holdout 0.8732, mientras índices aún pueden anunciarlo como validación. | Propagar etiqueta `INVALIDATED — do not cite` a toda superficie documental y de producto. |
| `api/routers/auth.py` | Docstring menciona SHA-256+salt, código usa bcrypt/PBKDF2. | Corregir y probar política de hashes. |

---

## A.6 Plan de acción consolidado (prioridad real)

### Próximas 72 horas

1. Etiquetar/retractar globalmente el holdout contaminado y prohibir su uso en claims externos.
2. Corregir README + CI para instalación y pruebas desktop reales.
3. Unificar `APP_MODE` y añadir smoke test sin variable de entorno.
4. Reemplazar el readiness por puerto del launcher con health check firmado por versión.
5. Detener la mutación de `tauri.conf.json` durante builds.

### Próximas 2 semanas

1. Crear la suite de no regresión del pipeline desktop, datos locales y empaquetado.
2. Obtener benchmark de concurrencia SQLite y fijar un límite seguro.
3. Reentrenar el modelo universal con holdout excluido y re-evaluar científicamente.
4. Crear manifiesto de modelos y exponerlo al usuario/soporte.
5. Convertir el índice documental en un registro de documentos vigentes/históricos.

### Próximas 4–6 semanas

1. Retirar ramas de Celery/Redis/MinIO de forma protegida por tests.
2. Consolidar almacenamiento local y schema SQLite versionado.
3. Empaquetar, probar y firmar una release candidate Windows desde entorno limpio.
4. Separar integraciones externas como módulos explícitos y opt-in.
5. Ejecutar revisión independiente de seguridad y reproducibilidad antes de presentar claims científicos externos.

---

## A.7 Registro de aceptación para una release madura

Una release desktop no debe declararse madura hasta que se cumplan simultáneamente los siguientes criterios:

- Build desde checkout limpio sin modificaciones posteriores del repositorio.
- Instalación en Windows limpio siguiendo solo la documentación pública.
- Backend autenticado por health check, no por disponibilidad de puerto.
- Pipeline completo y persistencia local verificados por pruebas automatizadas.
- Ausencia de dependencias cloud heredadas del runtime, o justificación explícita de cada una.
- Inventario de datos y modelo distribuido con hashes verificables.
- Métricas científicas externas calculadas con split independiente y protocolo publicable.
- Documentación vigente sin contradicciones con configuración, CI o runtime.

---

# Addendum B — Brecha hacia un handoff FEP-ready

**Referencia de capacidades:** `docs/31_PIPELINE_DATA_INVENTORY.md` y `docs/32_CROSS_VALIDATION_EVALUATION_TAB.md`.  
**Advertencia documental:** ambos son snapshots de 2026-07-29 orientados a wiring frontend y describen una UI mock. Deben utilizarse como inventario de capacidades/endpoints, no como evidencia del estado actual de UI o runtime sin contrastar contra código y una ejecución real.

## B.1 Capacidades existentes que ya son una base adecuada

El inventario muestra que MolDesign ya puede producir buena parte del material de triage previo a FEP:

| Capacidad actual | Aporte al handoff FEP |
|---|---|
| SMILES validado, conformer y propiedades | Punto de partida químico y filtros de desarrollabilidad. |
| Target curado/custom, PDB, grid y dynamic box | Hipótesis inicial de receptor y sitio de unión. |
| Vina con poses, RMSD, versión y semilla | Generación reproducible de hipótesis de pose. |
| Complejo PDB y archivo de poses SDF descargables | Material estructural exportable para preparación posterior. |
| XGBoost/CL-GNN, SHAP, hotspots y warnings | Priorización y explicación de por qué un candidato avanzó. |
| Selectividad contra anti-targets | Evita invertir FEP en candidatos con liability evidente. |
| SAR y análogos | Base para formar una serie congénere. |
| MM-GBSA opcional | Señal de refinamiento secundaria, no sustituto de FEP. |
| Datos ADMET/SA/QED | Filtro de programa medicinal antes de cómputo costoso. |
| Hardware, colas y cancelación | Base de ingeniería para trabajos largos y escalables. |

**Conclusión:** MolDesign ya está cerca de ser un *triage workbench*. Lo que falta no es otro score aislado; es el contrato que transforma un candidato prometedor en una **campaña de optimización relativa reproducible**.

## B.2 Qué significa “FEP-ready”

Un candidato no está listo para FEP por tener un score alto. Está listo cuando pertenece a una serie química definida, con una hipótesis estructural defendible y un sistema molecular preparado de forma trazable. FEP+ se aprovecha mejor para estimar cambios relativos de afinidad entre análogos cercanos; no es el siguiente paso automático para moléculas heterogéneas de una biblioteca.

El objetivo de MolDesign debe ser generar un paquete vendor-neutral `fep_ready_manifest` y sus archivos asociados. El usuario podrá importar ese paquete al flujo de Schrödinger/FEP+ después de su preparación específica, sin que MolDesign afirme ejecutar o reemplazar FEP+.

## B.3 Brechas funcionales prioritarias

### B-FEP-01 — Entidad "serie química" y campaña de optimización

**Falta:** el inventario expone moléculas, SAR y análogos, pero no un objeto persistente que represente un scaffold, una serie congénere, su objetivo, hipótesis de pose y candidatos seleccionados.

**Necesario:** `LeadSeries`/`FepCampaign` con:

- target y versión del receptor;
- molécula parental/anchor;
- miembros de la serie, estado químico y proveedor/origen;
- relación de transformación (R-group o cambio químico);
- evidencia de pose y criterios de inclusión;
- estado: `candidate`, `pose_validated`, `md_screened`, `fep_ready`, `exported`;
- historial inmutable de parámetros, usuario y resultados.

Sin esto, el sistema puede mostrar SAR, pero no puede garantizar que un conjunto sea adecuado para una red de transformaciones relativas.

### B-FEP-02 — Enumeración y selección explícita de estado químico

**Falta:** el contrato parte de SMILES/canonical SMILES, pero un paquete FEP requiere declarar cuál protómero, tautómero, estereoisómero y carga neta se seleccionaron, bajo qué pH y con qué método.

**Necesario:**

- enumeración versionada de estados;
- identificador inequívoco por estado, no solo por molécula padre;
- pH, microestado, carga formal y razón de selección;
- detección de transformaciones con cambio de carga o protonación, marcadas como riesgo;
- SDF/MOL2/estructura 3D por estado seleccionado.

Este es uno de los requisitos más importantes para evitar que el docking y el FEP partan de moléculas químicamente distintas aunque compartan nombre o SMILES base.

### B-FEP-03 — Preparación de receptor como sistema, no solo PDB/grid

**Falta:** hay target, chain, cofactors, PDB y grid; todavía falta un registro de preparación molecular de receptor adecuado para simulación.

**Necesario:**

- estructura origen y checksum;
- cadenas retenidas y justificación de complejos multichain;
- residuos faltantes, mutaciones, altlocs, puentes disulfuro y cofactores;
- estados de protonación de residuos y pH objetivo;
- aguas estructurales retenidas/eliminadas y razón;
- versión de herramienta, parámetros y estructura preparada exportable.

La unidad de trazabilidad no debe ser simplemente `PDB ID`, sino `PreparedReceptor vN`.

### B-FEP-04 — Selección y validación de hipótesis de pose

**Falta:** existen poses, RMSD, hotspots y complejos descargables; no existe un veredicto explícito de pose candidata a FEP ni una comparación formal entre poses alternativas.

**Necesario:**

- pose seleccionada y ranking de alternativas;
- clustering/consenso de poses;
- chequeo de choques, contactos clave, exposición a solvente y coherencia farmacofórica;
- bandera de aplicación de dominio/modelo y warnings;
- revisión humana opcional con decisión registrada.

El output debe ser `pose_hypothesis_id`, no solo la pose #1 de Vina.

### B-FEP-05 — MD ligera como quality gate, no como promesa de ΔG

**Falta:** MM-GBSA y OpenMM aparecen como opciones, pero no existe un contrato de preparación/equilibración/lectura de trayectoria para seleccionar poses estables.

**Necesario inicialmente:**

- construcción de sistema explícito: solvente, iones, caja periódica y force field;
- minimización y equilibración protocolizadas;
- MD corta y restringida aplicada solo a los mejores candidatos;
- métricas: RMSD de ligando y pocket, ocupación de contactos/hotspots, distancia al centro, choques, estabilidad de puentes H;
- artefactos y logs: topología, parámetros, trayectoria, snapshots, semilla y versiones;
- resultado honesto: `pose_stability_pass / caution / fail`, nunca “afinidad exacta”.

La GPU debe ser un acelerador opcional. El sistema puede iniciar CPU-first con presupuestos bajos, checkpoint, cancelación, snapshots delgados y escalamiento adaptativo.

### B-FEP-06 — Construcción de red de transformaciones FEP

**Falta:** no hay un grafo que conecte los miembros de una serie mediante mapeo atómico y transformaciones químicamente razonables.

**Necesario:**

- MCS/mapeo atómico propuesto y revisable;
- detección de cambios de carga, anillos, quiralidad y transformaciones de alto riesgo;
- grafo conectado y ciclos de cierre para control de consistencia;
- priorización por dificultad/complejidad y valor SAR;
- exportación de pares y de red completa.

MolDesign no necesita resolver el cálculo FEP para entregar valor aquí: puede preparar y validar la red que hará que el tiempo en FEP+ se invierta en comparaciones defendibles.

### B-FEP-07 — Anclas experimentales y ciclo de aprendizaje

**Falta:** hay SAR computacional, pero no un modelo explícito para capturar actividades experimentales, condiciones de ensayo y su relación con compuestos de referencia.

**Necesario:**

- importación de Ki/Kd/IC50/EC50 con unidad, protocolo, target construct y fuente;
- normalización y manejo de censura/replicados;
- elección de compuestos ancla con evidencia experimental;
- comparación posterior entre docking, MM-GBSA, MD, FEP y assay;
- recomendación de siguiente ronda de análogos.

FEP relativo es más útil cuando la red está anclada a química conocida; sin datos experimentales, MolDesign debe describir el resultado como priorización computacional, no validación.

### B-FEP-08 — Paquete de exportación reproducible y específico de integración

**Falta:** los endpoints de pose/complex PDB son buenos, pero son archivos sueltos. Para transferir trabajo a un usuario de Schrödinger hace falta un paquete de handoff consistente.

**Necesario:**

- directorio/ZIP inmutable por campaña;
- receptor preparado, ligandos 3D por estado, pose seleccionada y snapshots opcionales;
- manifest JSON/YAML con hashes SHA-256, versiones, pH, cadenas, cofactors, waters, grid y decisiones;
- tabla de serie y red de transformaciones;
- warnings y criterios que llevaron a `fep_ready`;
- formato de exportación acordado y probado con la importación de la versión de Schrödinger que use el laboratorio.

No es recomendable intentar generar formatos propietarios sin una prueba de importación real. Primero entrega un paquete vendor-neutral y después implementa un adaptador FEP+ validado por versión.

### B-FEP-09 — Política de gate y de incertidumbre

**Falta:** el pipeline tiene scores y warnings, pero falta una decisión compuesta, auditable y conservadora de cuándo un compuesto puede consumir presupuesto FEP.

**Gate mínimo propuesto:**

| Dimensión | Condición de avance |
|---|---|
| Química | Estado químico definido, sin alertas bloqueantes y síntesis/compra viable. |
| Estructura | Receptor preparado versionado y pose hipótesis aprobada. |
| Aplicabilidad | Target/molécula dentro de dominio o con warning explícito aceptado. |
| Estabilidad | MD corta no muestra salida, colapso o pérdida sostenida de contactos clave. |
| Serie | Al menos una transformación congénere mapeable y una red conectable. |
| Biología | Selectividad/ADMET no muestran una liability que invalide la inversión. |
| Evidencia | Preferentemente hay uno o más anclajes experimentales. |

El resultado debe ser `FEP_READY`, `FEP_READY_WITH_RISKS` o `NOT_READY`, con razones legibles y datos que las respalden.

## B.4 Qué ya existe y qué debe evitarse duplicar

No hace falta reconstruir estas capacidades antes de iniciar la capa FEP-ready:

- generación/descarga de poses y complejos;
- información de target, grid y hotspots;
- ADMET, SA, QED y filtros básicos;
- selectividad, SAR y MM-GBSA como evidencias auxiliares;
- cola local, estimación de hardware y cancelación;
- metadatos Vina (versión, seed, parsing source).

Tampoco debe tratarse como requisito de FEP-ready la blockchain, el chat IA o la certificación PDF. Pueden dar trazabilidad de producto, pero no sustituyen el manifiesto científico ni el protocolo de preparación.

## B.5 Orden de implementación de máximo valor

1. **Contrato `PreparedReceptor` + `LigandState` + `PoseHypothesis`**, con hashes y exportación local.  
2. **Entidad `LeadSeries/FepCampaign`** y gate manual/auditable de inclusión.  
3. **Paquete `fep_ready_manifest` vendor-neutral** y prueba de importación manual en FEP+.  
4. **MD corta de estabilidad de pose**, CPU-first y GPU opcional, con métricas y checkpoints.  
5. **Grafo/mapeo de transformaciones** y validación de red.  
6. **Importación de datos experimentales y ciclo de active learning.**  
7. Adaptador específico a FEP+ una vez que el paquete neutral se importe sin pérdida de información.

## B.6 Definición de éxito

MolDesign habrá alcanzado la meta de “FEP-ready” cuando un químico pueda seleccionar una serie y obtener, sin trabajo manual ambiguo, un paquete que responda:

1. ¿Cuál receptor preparado y qué versión estructural se usará?
2. ¿Qué estado químico exacto representa cada ligando?
3. ¿Cuál es la hipótesis de pose y qué evidencia apoya su estabilidad?
4. ¿Qué transformaciones relativas se proponen y cuáles son riesgosas?
5. ¿Qué datos, versiones, semillas y decisiones permiten reproducir el paquete?
6. ¿Qué riesgos científicos obligan a interpretar el posterior FEP con cautela?

---

# Addendum C — Dos experiencias de producto: Quick Discovery y FEP Campaign

## C.1 Principio de diseño

MolDesign debe separar explícitamente la experiencia de **explorar una hipótesis** de la experiencia de **preparar una campaña de energía libre relativa**. Ambas usan el mismo núcleo científico, pero tienen distinto usuario, evidencia mínima, costo computacional y significado de resultado.

Esta separación evita dos errores de producto:

1. obligar al usuario que quiere un primer screening a aprender conceptos de FEP antes de tiempo;
2. presentar una molécula individual con docking favorable como si fuera automáticamente apta para una campaña FEP.

La interfaz puede ser muy simple al inicio, mientras los controles científicos y la trazabilidad se conservan en el sistema.

```text
Quick Discovery
  receptor + molécula → hipótesis priorizada
                           ↓
                  colección / serie de análogos
                           ↓
FEP Campaign
  preparación estructural + gates → paquete FEP-ready
```

## C.2 Experiencia 1 — Quick Discovery

### Propósito

Permitir que un investigador obtenga rápidamente una hipótesis computacional priorizada a partir de un receptor y una molécula. Es el punto de entrada ideal para la biblioteca de receptores curados y para receptores propios.

### Flujo de usuario

```text
1. Elegir receptor curado o subir receptor propio
2. Dibujar, pegar o importar una molécula
3. Presionar “Ejecutar evaluación”
4. Revisar resultado, alertas y artefactos
5. Guardar en Moldex o añadir a una serie
```

### Capacidades ya disponibles o alineadas con el pipeline

- Catálogo de receptores curados y carga de receptor propio.
- Validación de SMILES, conformer, preparación de target y grid/dynamic box.
- Docking Vina y poses recuperables.
- Rescoring XGBoost/CL-GNN cuando aplique, propiedades y ADMET.
- Hotspots, explicabilidad, alertas científicas y selectividad opcional.
- SAR, MM-GBSA y reportes como análisis posteriores, no bloqueantes.
- Persistencia de moléculas, resultados, complejo y poses.

### Resultado que debe comunicar

El resultado de Quick Discovery no es una afirmación de afinidad experimental ni de aptitud FEP. Debe describirse como:

> “Hipótesis de pose y priorización computacional para investigación posterior.”

La UI debe mostrar de forma visible:

- score y sus componentes, sin convertirlos en certeza;
- dominio de aplicabilidad y warnings;
- estado del target: curado, auto-curado o aportado por usuario;
- artefactos descargables: pose, complejo, receptor y metadatos;
- acción principal: **Guardar / Añadir a serie**, no “enviar a FEP”.

### Criterio de éxito

Un usuario puede pasar de receptor + estructura 2D a una evaluación trazable sin configurar infraestructura, rutas, scripts o servicios externos.

## C.3 El puente — De candidatos individuales a una serie química

Quick Discovery puede producir muchos candidatos individuales. FEP relativo requiere una decisión posterior: seleccionar una **serie congénere** que responda a una pregunta de química medicinal, por ejemplo “¿qué sustituyente R mejora afinidad sin empeorar selectividad?”.

La acción de transición debe ser explícita:

```text
Moldex / resultados guardados
  → “Crear serie de optimización”
  → elegir molécula ancla y miembros
  → revisar similitud/scaffold/estados
  → crear FEP Campaign
```

La aplicación debe advertir cuando la serie es débil para FEP: miembros demasiado disímiles, cambios de carga, falta de core común, pose incierta, target fuera de dominio o ausencia de datos experimentales.

## C.4 Experiencia 2 — FEP Campaign

### Propósito

Preparar una campaña reproducible de energía libre relativa que un experto pueda revisar y ejecutar en FEP+ u otro backend compatible. Esta experiencia no pretende ocultar complejidad científica; debe convertirla en decisiones explícitas y auditables.

### Entrada mínima

- Un `PreparedReceptor` versionado, no solo un PDB ID.
- Una serie de ligandos relacionados con un scaffold/core reconocible.
- Un estado químico definido para cada miembro.
- Una hipótesis de pose de referencia defendible.
- Preferentemente datos experimentales para una o más moléculas ancla.

### Flujo de usuario propuesto

```text
1. Crear campaña desde una Lead Series
2. Seleccionar/crear PreparedReceptor
3. Confirmar estados químicos de cada ligando
4. Seleccionar y comparar poses de referencia
5. Ejecutar validación de estabilidad corta (opcional al inicio; requerida según política)
6. Generar y revisar red de transformaciones
7. Aplicar gate FEP-ready
8. Exportar paquete vendor-neutral o adaptador FEP+
```

### Módulos que debe incluir

| Módulo | Decisión que hace visible |
|---|---|
| Receptor preparado | Cadenas, protonación, aguas, cofactors, residuos/modificaciones y versión. |
| Estados de ligando | Protómero, tautómero, estereoquímica, carga, pH y conformación inicial. |
| Pose hypothesis | Pose elegida, poses alternativas, contactos, choques y evidencia de estabilidad. |
| MD stability gate | Si la pose conserva contactos/posición bajo minimización, equilibración y MD corta. |
| Transformation mapper | Core común, mapeo atómico, cambios de carga y aristas de alto riesgo. |
| Campaign evidence | Datos experimentales, SAR, selectividad, ADMET y razones de inclusión/exclusión. |
| Export package | Archivos, hashes, versiones, configuraciones, warnings y manifiesto. |

### Resultado que debe comunicar

La campaña debe producir una clasificación conservadora:

| Estado | Significado |
|---|---|
| `FEP_READY` | Datos estructurales y químicos completos; no se detectaron riesgos bloqueantes. |
| `FEP_READY_WITH_RISKS` | Exportable, pero contiene riesgos explícitos que requieren criterio experto. |
| `NOT_READY` | Falta evidencia o existe una incompatibilidad que hace prematuro gastar FEP. |

El estado no predice el resultado de FEP. Solo responde si el sistema está preparado de manera razonable para invertir recursos en ese cálculo.

## C.5 Diseño de UI: simplicidad sin falsa certeza

### Quick Discovery debe ser simple por defecto

- Un flujo principal con tres decisiones: receptor, molécula, ejecutar.
- Opciones avanzadas colapsadas: grid, cofactors, motor, workers y selectividad.
- Warnings y dominio de aplicabilidad visibles, pero no invasivos.
- Resultado interpretable sin conocer FEP.

### FEP Campaign debe ser guiada, no simplificada artificialmente

- Checklist con progreso y bloqueo por evidencia faltante.
- Valores por defecto razonables, con toda decisión editable y registrada.
- Previsualización de estados de ligando, poses y red de transformación.
- Distinción entre advertencias informativas, riesgos revisables y bloqueantes.
- Exportación solo después de que el manifiesto sea completo.

El objetivo no es hacer que FEP parezca un botón mágico. Es hacer que su preparación sea accesible, consistente y comprensible.

## C.6 Valor estratégico de la separación

| Para quién | Valor de Quick Discovery | Valor de FEP Campaign |
|---|---|---|
| Investigador nuevo | Puede empezar sin aprender workflows complejos. | Aprende qué evidencia se necesita antes de escalar. |
| Químico medicinal | Recibe candidatos y señales SAR rápidamente. | Convierte una serie en decisiones de optimización relativas. |
| Químico computacional | Evita preparación manual repetitiva y dispersa. | Revisa controles, corrige riesgos y exporta un paquete defendible. |
| Laboratorio con FEP+ | Filtra trabajo antes de usar licencias/GPU. | Recibe una campaña mejor preparada y trazable. |
| Laboratorio sin FEP+ | Puede hacer discovery local y guardar evidencia. | Puede entregar un paquete a un colaborador, CRO o servicio especializado. |

## C.7 Métricas de producto

Medir ambas experiencias por separado evita optimizar una métrica equivocada.

**Quick Discovery**:

- tiempo desde molécula hasta resultado;
- porcentaje de evaluaciones completadas sin configuración manual;
- proporción de resultados guardados/añadidos a serie;
- tasa de warnings por tipo de receptor y causa.

**FEP Campaign**:

- porcentaje de series que pasan el gate;
- causas de `NOT_READY`;
- tiempo de preparación manual evitado;
- éxito de importación del paquete en el backend elegido;
- concordancia retrospectiva entre campañas, FEP y resultados experimentales cuando estén disponibles.

## C.8 Roadmap de entrega

1. Consolidar Quick Discovery con datos reales, trazabilidad de target y un flujo de guardado a Moldex.  
2. Añadir entidades `LeadSeries`, `PreparedReceptor`, `LigandState` y `PoseHypothesis`.  
3. Implementar la transición “Crear serie de optimización”.  
4. Construir FEP Campaign como checklist y manifiesto vendor-neutral.  
5. Añadir MD corta como gate de estabilidad.  
6. Implementar mapeo/red y exportador probado con FEP+.  
7. Validar retrospectiva y prospectivamente con laboratorios piloto.

---

# Addendum D — Segmentos de mercado y estrategia de enfoque

## D.1 Tesis de mercado

MolDesign no debe competir inicialmente como “la suite completa de descubrimiento de fármacos”. Ese espacio ya está cubierto por suites enterprise y plataformas cloud. Su oportunidad es ser el **workbench desktop, local y reproducible que convierte una hipótesis estructural en una decisión de discovery defendible**.

El valor común entre segmentos es reducir tres fricciones: instalación/infraestructura, dispersión de herramientas y falta de trazabilidad entre receptor, molécula, pose, resultados y siguiente decisión.

## D.2 Segmentos priorizados

| Segmento | Problema que MolDesign resuelve | Oferta inicial | Prioridad |
|---|---|---|---|
| Laboratorios académicos de química medicinal/computacional | Herramientas dispersas, presupuesto limitado, necesidad de reproducibilidad y aprendizaje. | Quick Discovery local, biblioteca curada, receptor propio, reportes y proyectos exportables. | 1 |
| Pequeñas biotech y startups preclínicas | Necesitan priorizar sin construir infraestructura CADD completa. | Triage de hit-to-lead, series, selectividad/ADMET y dossier reproducible para CRO/FEP. | 1 |
| Grupos con acceso a Schrödinger/FEP+ | El cálculo caro requiere candidatos y sistemas mejor preparados. | FEP Campaign vendor-neutral y exportador validado hacia FEP+. | 2 |
| CROs y consultores de química computacional | Intake heterogéneo, preparación manual repetitiva y reporting al cliente. | Plantillas de proyecto, paquetes reproducibles, batch local y reporte de decisiones. | 2 |
| Consorcios de enfermedades desatendidas y open science | Necesitan flujos transparentes, auditables y transferibles entre instituciones. | Proyectos compartibles, datos/protocolos versionados y herramientas abiertas. | 2 |
| Centros de cómputo/core facilities universitarios | Dan soporte a múltiples grupos que requieren un flujo estándar. | Instalación desktop administrada, catálogos institucionales y exportación a HPC/CRO. | 3 |
| Enseñanza y formación CADD | La curva de herramientas profesionales es alta. | Modo educativo con datasets de referencia, warnings y ejercicios reproducibles. | 3 |

## D.3 Mercados que no deben ser el foco inicial

- **Uso clínico, medicina personalizada o recomendación terapéutica:** requeriría validación clínica, regulación y evidencia fuera del alcance actual.
- **Reemplazar FEP+ o competir por cálculo GPU masivo:** no es la ventaja inicial y desviaría recursos del producto diferenciador.
- **Marketplace/comunidad global de receptores antes de consolidar calidad:** un catálogo comunitario sin gobernanza puede disminuir la confianza científica.
- **Drug design generativo como promesa central:** puede integrarse después; el valor actual debe ser calidad de preparación y decisión, no generar grandes volúmenes de moléculas.

## D.4 Posicionamiento por segmento

### Para academia

> “Un laboratorio de discovery local y reproducible: del receptor y molécula a una hipótesis documentada, sin encadenar scripts.”

La biblioteca de receptores curados es especialmente útil aquí, siempre que cada target exponga procedencia, preparación, limitaciones y versión.

### Para biotech/CRO

> “Un sistema de triage y dossier científico que reduce preparación manual y facilita decisiones de hit-to-lead.”

La métrica a demostrar es tiempo ahorrado y reducción de errores antes de docking avanzado, MD, síntesis o FEP.

### Para usuarios FEP

> “La capa de calidad previa a una campaña de energía libre relativa.”

El mensaje correcto no es reemplazar FEP+; es preparar una serie, estados, poses y evidencia para usar mejor un recurso caro. Schrödinger describe FEP+ como aplicable desde hit discovery hasta lead optimization y para propiedades como selectividad y solubilidad, lo que confirma que el valor está dentro de un flujo más amplio, no aislado. [FEP+](https://www.schrodinger.com/platform/products/fep/)

## D.5 Diferenciadores que deben verificarse, no solo declararse

1. **386 receptores curados:** cada uno debe tener manifiesto de procedencia, estructura, chain, grid, cofactors, preparación, fecha, versión, nivel de confianza y limitaciones.
2. **Desktop/on-premise:** demostrar instalación estable, datos locales y operación offline parcial, no solo anunciar privacidad.
3. **Un clic para Quick Discovery:** mantener la interfaz corta sin ocultar warnings ni generar falsa certeza.
4. **Puente FEP-ready vendor-neutral:** probar exportación/importación real primero con un backend y luego ampliar compatibilidad.
5. **Rigor visible:** resultados, warnings, modelo, semilla, binarios y artefactos deben ser recuperables por proyecto.
6. **Idioma y soporte contextual:** español puede ser una ventaja de adopción regional, pero la evidencia científica y el formato exportable deben funcionar globalmente.

## D.6 Estrategia de entrada recomendada

### Etapa 1 — Academia y pilotos locales

Conseguir 2–3 grupos que usen MolDesign en una pregunta concreta de docking/hit prioritization. El objetivo no es vender FEP: es comprobar instalación, lenguaje, decisiones, fallos y utilidad de la biblioteca curada.

### Etapa 2 — Casos de estudio reproducibles

Publicar casos completos: receptor, biblioteca/serie, configuración, resultados, limitaciones y, cuando exista, comparación con assay o experto. Un caso bien documentado vale más que una lista extensa de features.

### Etapa 3 — Paquete FEP-ready y colaboración

Validar un exportador con un laboratorio que ya use FEP+ o con una CRO. Medir tiempo de preparación, errores detectados y éxito de importación. No declarar integración oficial sin acuerdo con el proveedor.

### Etapa 4 — Oferta para CRO/core facility

Añadir batch, plantillas, seguimiento de campañas y reportes para que un equipo dé servicio a varios proyectos desde una instalación controlada.

## D.7 Métrica de product-market fit

La señal correcta no es número de descargas. Es que un laboratorio vuelva a usar MolDesign para su siguiente serie porque:

- evitó repetir pasos manuales;
- detectó un problema antes de gastar tiempo experimental o GPU;
- pudo explicar y reproducir una decisión;
- entregó un paquete útil a un químico computacional, CRO o colaborador.

La industria ya combina docking, MD, ML y automatización de workflows; por eso una propuesta centrada en orquestación confiable y reproducibilidad tiene un problema real que resolver, pero debe competir mediante evidencia de ahorro de tiempo y calidad de decisión, no sólo por tener más endpoints.
