# Migraciones — MolDesign (modo DESKTOP)

Plataforma de referencia: **SQLite** (`sqlite+aiosqlite`, archivo
`moldesign_local.db`). El ORM (`core/models.py`) es la fuente de verdad del
esquema; este directorio documenta cómo se versiona.

## Versionado del esquema

- Constante `SCHEMA_VERSION` en `core/database.py` (actualmente `8`).
- Tabla `schema_meta` (`schema_version INTEGER NOT NULL`, `applied_at TEXT`).
  Se crea y sella en cada arranque dentro de `create_all_tables()`
  (`core/database.py → _stamp_schema_version`).
- Flujo de arranque:
  1. `_migrate_sqlite_db()` compara columnas del ORM contra `PRAGMA
     table_info` y hace `ALTER TABLE ADD COLUMN` de las columnas faltantes.
  2. `Base.metadata.create_all` crea las tablas que no existen.
  3. `_stamp_schema_version` hace upsert del sello:
     - DB nueva o sin sello → INSERT de `SCHEMA_VERSION`.
     - Sello menor → `log.warning` con el delta y actualización del sello.
       **No se auto-migran datos arbitrarios**: desktop no tiene runner de
       migraciones.

## Cómo hacer bump de SCHEMA_VERSION

### Columnas aditivas (el caso habitual)

Agregar la columna al ORM y subir `SCHEMA_VERSION` en 1. Es seguro porque:

- Las DB nuevas la crean directamente con `create_all`.
- Las DB existentes la reciben por `_migrate_sqlite_db` al arrancar
  (`ALTER TABLE ADD COLUMN`). El `ALTER TABLE ADD COLUMN` de SQLite solo
  admite columnas **nullable o con default constante** — mantener esa
  restricción. El tipo se infiere del tipo SQLAlchemy (Integer/Boolean →
  INTEGER, Float/Numeric → REAL, resto → TEXT).

### Cambios estructurales (renombrar, eliminar, cambiar tipo, backfill)

`create_all` no los detecta. Requieren SQL manual versionado (un script por
cambio, documentado aquí o en `legacy_postgres/`) y un plan de rollout para
las DB existentes. Nunca eliminar archivos de migración sin plan: las DB
reales de los usuarios no se recrean.

La excepción actual es schema v3: `evaluation_results.task_id` reemplaza el
nombre heredado `celery_task_id`. `_migrate_sqlite_db()` añade la columna y
ejecuta un backfill idempotente; deja la columna original intacta para que el
rollback de la aplicación no pierda jobs existentes. El backend nuevo usa sólo
`task_id`; la API mantiene `celery_task_id` como alias de transición.

## `legacy_postgres/`

Contiene los scripts `001_initial.sql` … `008_*.sql` y
`create_benchmark_table.sql`: **snapshots PostgreSQL heredados de la época
CLOUD**, conservados solo por historia. No forman parte del runtime desktop,
ningún código los ejecuta, y su dialecto (JSONB, UUID nativo, `CREATE
EXTENSION`, `DO $$`) no aplica a SQLite.

## Nota sobre `db/seed_targets_v46.sql`

Es un seed de datos (INSERTs), no una migración. Se mantiene junto al
repositorio por referencia; no participa del versionado del esquema.
### v6 — receptor preparado inmutable en corridas de cohorte

Añade `cohort_runs.receptor_prepared_bytes` como BLOB nullable para migración
aditiva. Las corridas nuevas guardan y consumen el PDBQT exacto; el catálogo
mutable deja de ser la fuente durante la ejecución y reanudación.

### v7 — evidencia estructural por pose

Añade `evaluation_results.structural_evidence` (JSON nullable). Las
evaluaciones anteriores la tienen a `NULL`, que se lee como «no evaluada» y
nunca como un fallo de la pose. Contrato en
`services/chemistry/structural_evidence.py`.

### v8 — selección de pose

Añade `evaluation_results.pose_selection` (JSON nullable). Misma forma aditiva:
lo anterior queda a `NULL` y el modelo de lectura lo abre como `unavailable`
—el selector no existía cuando esa evaluación corrió—, con Vina top-1 declarado
como fallback. Contrato en `services/chemistry/pose_selection.py`.
