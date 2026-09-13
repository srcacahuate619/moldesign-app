# Arquitectura Desktop — MolDesign

**Fecha:** 2026-08-13
**Estado:** Fuente normativa de arquitectura (Fase 3 de la auditoría de consolidación)
**Alcance:** `moldesign-build` — distribución desktop Windows

---

## Principio rector

MolDesign es **desktop-first, local y privado**. Un solo modo de ejecución
(DESKTOP), un solo contrato de almacenamiento (disco local), una cola local,
una caché local y una base SQLite. **0-telemetría**: la app nunca envía datos
del usuario a terceros; los errores los reporta el usuario activamente.
Integraciones remotas: opt-in, off por defecto (ver `docs/37_INTEGRATION_POLICY.md`).

## Visión de componentes

```text
┌─ Tauri Launcher (frontend/src-tauri) ────────────────────────────┐
│  - reserva puerto 8000-8020, spawn Uvicorn                       │
│  - health check SEMÁNTICO: /health valida app/version/app_mode/  │
│    SQLite (ya no confía en "puerto ocupado")                     │
│  - logs en app_log_dir writable de Tauri; recursos sólo lectura  │
│  - runtime instalado: Python + backend + Vina + modelos + datos  │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼ 127.0.0.1:8000+
┌─ Backend FastAPI (backend/) ─────────────────────────────────────┐
│  api/main.py       entrypoint + lifespan (bootstrap, heartbeat)  │
│  api/routers/*     evaluación, targets, auth, ai, moldex…        │
│  core/config.py    Settings — fuente única de modo (is_desktop)  │
│  core/models.py    ORM SQLAlchemy — SQLite nativo (F-04)         │
│  core/database.py  engine SQLite WAL + schema_meta versionado    │
│  db/repository.py  acceso a datos + retries operacionales        │
│  services/docking/queue_handler.py  dispatcher local (cola)      │
│  services/pipeline/runner.py        stages de evaluación         │
│  services/rescoring_bridge.py       puente ÚNICO al sidecar      │
│  utils/local_storage.py             almacenamiento en disco      │
│  utils/cache.py                     caché en memoria (Redis off) │
└───────────────┬──────────────────────────────────────────────────┘
                ▼ (bridge, sys.path resuelto en UN solo módulo)
┌─ Sidecar rescoring/ ─────────────────────────────────────────────┐
│  model_manager.py   carga de modelos + quality gate familia      │
│  model_router.py    enrutamiento GPU/CPU (NO en path eval real)  │
│  artifacts/         modelos + training_report + shap_analysis    │
└──────────────────────────────────────────────────────────────────┘
```

## Decisiones de arquitectura (con evidencia)

1. **Un solo modo de ejecución.** `Settings.app_mode` default `DESKTOP`; todos
   los módulos consultan `get_settings().is_desktop`. La rama Celery del
   dispatcher fue eliminada (F-02); `celery_app.py` ya no existe.
2. **SQLite como plataforma de referencia.** Tipos nativos (Uuid, SQLiteJSON),
   `SCHEMA_VERSION` sellado en `schema_meta`, migraciones PostgreSQL movidas a
   `legacy_postgres/` (F-04). Columnas aditivas vía ORM + `_migrate_sqlite_db`.
3. **Cola local.** `queue_handler.py` con `DESKTOP_MAX_CONCURRENCY = 4`
   (justificado por benchmark F-15: 0 locks, throughput crece con concurrencia).
   La disciplina de transacciones cortas es OBLIGATORIA — si una transacción
   vuelve a abarcar docking, los locks regresan.
4. **Almacenamiento local.** `utils/local_storage.py` (interfaz neutral,
   prefixes `targets/ligands/poses/` en `local_data_dir`). RCSB solo on-demand.
5. **Puente al sidecar.** `services/rescoring_bridge.py` es el único punto que
   toca `sys.path` y define `RESCORING_*` paths. Nadie más importa el sidecar.
6. **Retrain Fase A (2026-08-10).** Holdout scaffold-disjoint (328 complejos),
   Spearman 0.6094 [0.528–0.679]; el 0.8732 histórico está INVALIDADO por
   leakage. El modelo default es `model_a_universal.json` (167 features).
7. **0-telemetría.** Sentry eliminado; la política completa en
   `docs/37_INTEGRATION_POLICY.md`.
8. **Bundle autocontenido por lista permitida.** `scripts/bundle_helper.py`
   construye `frontend/src-tauri/resources/` sin `.env`, DB de usuario, logs,
   datasets de entrenamiento ni modelos invalidados. Tauri mapea
   `resources/: ""` a la raíz instalada que consume `bundled_layout`.
9. **Recursos inmutables.** El Python instalado recibe
   `PYTHONDONTWRITEBYTECODE=1`; los logs viven en el `app_log_dir` que Tauri
   publica como `MOLDESIGN_LOG_DIR`. El backend nunca escribe en la carpeta del
   programa.

## Flujo de una evaluación

```text
POST /evaluation/submit
  → queue_handler.submit_evaluation_job (siempre desktop)
  → _run_full_evaluation_async (transacciones cortas + retry)
  → Vina (binario local) + rescoring (bridge → sidecar)
  → persiste en SQLite (schema_meta v2) + local_data_dir
  → poll GET /evaluation/status (JobStatus con aplicabilidad/fallback)
```

## Reproducibilidad

- **Manifiesto de modelos**: `model-manifest.json` (hash SHA-256, feature
  schema, split, fecha, estado científico) expuesto en `/health`.
- **Gate de calidad Vina**: `rescoring/scripts/check_vina_importance_gate.py`
  bloquea release si el grupo Vina supera 10% de importancia (régimen
  train/inference distinto).
- **Suite de no-regresión**: `backend/tests/` (app_mode, local_storage,
  queue_handler, sqlite_roundtrip, f21_payload) + `rescoring/tests/`.
- **CI**: CSP check + backend tests + rescoring tests + gate Vina.
- **Gate de runtime desktop**: `scripts/verify_desktop_bundle.py` verifica
  hashes, archivos prohibidos, imports desde la copia staged, Vina y `/health`,
  y compara el árbol antes/después para impedir mutaciones durante el release.
- **Evidencia de instalación**: `docs/55_MVP_DESKTOP_RELEASE.md` registra
  checksum, inventario, smoke instalado, cierre del proceso y bloqueadores de
  distribución comercial.

## Deuda conocida (trackeada)

- `task_id` identifica el job del dispatcher local; schema v3 conserva la
  columna anterior sólo para rollback de datos y la API expone un alias de
  transición para clientes anteriores.
- `ensure_bucket_exists` (no-op desktop) conservado por test F-01.
- Aliases legacy en `file_handlers.py` para `queue_handler.py`.
- Comunidad remota (`/community`): decisión de producto PENDIENTE — ver
  `docs/37_INTEGRATION_POLICY.md`.
- **CSP con `unsafe-inline`** en `style-src` y `script-src`
  (`src-tauri/tauri.conf.prod.json`). ACEPTADO para 1.0, no pendiente: Next.js y
  Tailwind emiten estilos inline y el refactor a clases no cabe en este ciclo.
  `check-prod-csp.js` sí bloquea `unsafe-eval`, que es el que permitiría ejecutar
  código construido en tiempo de ejecución. Riesgo acotado: la app es local, la
  CSP restringe `connect-src` a `127.0.0.1`/`localhost` y no hay origen remoto
  que pueda inyectar. Revisar en 1.1.
- **Instancia única resuelta** (`tauri-plugin-single-instance`). Antes, un
  segundo doble clic abría otra ventana con su propio backend: dos puertos, dos
  juegos de modelos en memoria y dos motores sobre la misma base. SQLite en WAL
  lo aguantaba —los escritores se serializan— así que no corrompía datos, pero
  el usuario acababa con dos ventanas idénticas. Ahora el segundo proceso
  enfoca la primera ventana y sale.
- **`known_molecules.py` no cubre todo el vademécum.** Se retiraron 20 entradas
  cuya estructura no se pudo verificar contra fórmula de referencia; el
  resolutor las busca en MolGraph o PubChem. Ampliar la tabla exige añadir la
  fórmula de referencia en `tests/test_known_molecules.py`, que es lo que impide
  que vuelva a entrar una estructura equivocada bajo el nombre de un fármaco.
