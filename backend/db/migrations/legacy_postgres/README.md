# Migraciones PostgreSQL — LEGACY (histórico)

Los archivos `.sql` de este directorio son **snapshots PostgreSQL** de la
época en que el backend corría contra PostgreSQL (modo CLOUD):

- `001_initial.sql` — esquema inicial (extensión uuid-ossp, ENUMs nativos,
  tablas con UUID/JSONB nativos).
- `002` … `008` — columnas posteriores (reproducibilidad de docking, QED,
  GNN score, viabilidad sanguínea, custom targets, multiplicadores, creador
  de targets).
- `create_benchmark_table.sql` — tabla `benchmark_results` para benchmarks.

**Estado actual**: el producto es desktop-only y su plataforma de
referencia es SQLite (hallazgo de auditoría F-04). Estos scripts:

- NO se ejecutan en ningún arranque ni proceso del runtime desktop.
- NO son compatibles con SQLite (JSONB, UUID nativo, `CREATE EXTENSION`,
  bloques `DO $$`).
- Se conservan únicamente como registro histórico del esquema cloud, por si
  algún día se reactiva un despliegue con PostgreSQL o se necesita
  referencia de la evolución del esquema.

El versionado real del esquema desktop está documentado en el README del
directorio padre (`backend/db/migrations/README.md`): constante
`SCHEMA_VERSION` + tabla `schema_meta` + `create_all`/`_migrate_sqlite_db`.
