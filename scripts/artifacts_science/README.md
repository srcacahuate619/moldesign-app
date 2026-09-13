# Artefactos experimentales de ciencia (FND-01)

Convención del programa experimental científico definida en
`docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`, sección 17. Los resultados de
cada experimento deben poder reconstruirse sin memoria de sesión: cada
experimento produce un registro único con config, hashes, código, ambiente y
salida.

## Contador acumulado del programa (§19.3 del doc. 49)

**Actualizado al 2026-08-23.** La §19.3 exige que este README mantenga el contador para que
el volumen del programa sea auditable.

> **Este bloque es DERIVADO, no escrito a mano.** Regenerarlo con:
>
> ```
> python -c "import sys;sys.path.insert(0,'scripts');import build_registro_cientifico as B,collections;i,_=B.construir();c=collections.Counter(v['categoria'] for v in i['experimentos']);print(sum(c.values()));[print(k,v) for k,v in c.most_common()]"
> ```
>
> Se escribió a mano dos veces y las dos se pudrieron: hubo dos bloques simultáneos con
> **63** y **89** artefactos, y el segundo además descuadraba porque omitía los
> `INCONCLUSIVE` (67 GO + 20 NO_GO = 87 de 89). Un contador mantenido a mano en un
> repositorio cuyo activo declarado es la auditabilidad es exactamente el defecto que un
> revisor hostil encuentra en diez minutos.

**151 artefactos con manifest**, repartidos en las seis poblaciones de `_taxonomia.json`:

| Población | Cuenta | Qué es |
|---|---:|---|
| Medición | **40** | Mide sin decidir: no tiene umbral de aceptación |
| Prerregistro | **42** | Hipótesis y gate declarados ANTES de mirar. Se sella `GO` por convención; **no es un éxito** |
| Hallazgo | **24** | Gate real preregistrado y superado |
| Refutación | **21** | Hipótesis propia puesta a prueba y derribada |
| Inconcluso | **13** | Ejecutado y declarado sin conclusión. No se reclasifica a posteriori |
| Corrigendum | **11** | Corrección de un resultado propio cuyo valor principal ES la corrección |

**El cociente `GO`/total NO es una tasa de aciertos y no debe citarse como tal.** Por eso
este contador ya no lo publica: el campo `decision` del manifest daría 116 `GO` contra 22
`NO_GO`, y esa cifra es engañosa porque los 42 prerregistros se sellan `GO` al declararse y
las 40 mediciones no tienen umbral que superar. La única población sobre la que una tasa
significa algo es **hallazgo frente a refutación: 24 contra 21**.

Recordatorio de la §19.3: todo resultado distinto del confirmatorio es **exploratorio**, con
gate preregistrado o sin él, y ningún claim externo se apoya en un `GO` exploratorio aislado.

## Estructura de directorio

```text
scripts/artifacts_science/<EXPERIMENT_ID>/
  manifest.json      registro único: hipótesis, protocolo, fecha, git/worktree,
                     hashes, OS/CPU/GPU/RAM, seeds, dependencias, duración,
                     gate y decisión
  metrics.json       métricas agregadas del experimento (objeto JSON libre)
  per_complex.jsonl  una línea JSON por complejo evaluado
  failures.jsonl     una línea JSON por fallo (append-only)
  README.md          resumen legible generado desde manifest.json por el tool
```

## Campos del manifest (v1)

| Campo | Obligatorio | Descripción |
|---|---|---|
| `schema_version` | sí | versión del schema (1) |
| `experiment_id` | sí | identificador único del experimento |
| `hypothesis` | sí | hipótesis preregistrada |
| `protocol` | sí | referencia al protocolo (documento o ruta) |
| `created_at` | sí | fecha/hora ISO 8601 de creación del registro |
| `status` | sí | `created` / `running` / `sealed` / `finished` / `failed` |
| `git_state` | sí | `branch`, `commit` y `dirty` del repo al iniciar |
| `environment` | sí | `os`, `arch`, `cpu_count`, `total_ram_mb`, `gpu` |
| `seeds` | sí | semilla preregistrada |
| `dependencies` | sí | `python_version` + `packages` |
| `gate` | sí | descripción del criterio de decisión |
| `decision` | sí | `PENDING` / `GO` / `NO_GO` / `INCONCLUSIVE` |
| `started_at` / `finished_at` / `duration_seconds` | no | tiempos y duración de la ejecución |
| `dataset_hashes` / `model_hashes` / `binary_hashes` / `assets_hashes` | no | mapas `{ruta_relativa: sha256}` |
| `seal_maintenance` | no | lista de entradas de mantenimiento del sello (`date`, `reason`, `path`, `previous_hash`, `new_hash`, `content_commit`) |
| `sealed` / `sealed_at` | no | estado y momento del sellado |
| `decision_rationale` | no | razonamiento de la decisión final |

Claves JSON e identificadores en inglés; valores libres. El manifest se
valida contra `manifest.schema.json` (JSON Schema draft-07) con el validador
embebido en `scripts/experiment_manifest.py`, sin dependencias externas.

## Flujo de trabajo

```text
init → ejecutar el experimento → validate → seal → finish
post-seal: maintain (solo assets, auditado)
```

1. `python scripts/experiment_manifest.py init <EXPERIMENT_ID> --hypothesis "..." --protocol "..." --gate "..."`
   crea el directorio con `manifest.json` prellenado (git state y environment
   reales) y los skeletons vacíos.
2. El experimento escribe `metrics.json`, `per_complex.jsonl` y
   `failures.jsonl` (y opcionalmente `status`, `started_at`).
3. `validate` verifica el manifest contra el schema. Salida 0 si pasa, 1 si no,
   con mensajes legibles.
4. `seal [--dataset PATH] [--models PATH] [--binaries PATH] [--assets PATH]`
   registra los SHA-256 y congela el manifest. Los cuatro flags son
   repetibles (`--assets a --assets b`) y admiten múltiples paths por
   invocación (`--dataset dir1 dir2`); los paths se acumulan en sus buckets
   (`dataset_hashes`, `model_hashes`, `binary_hashes`, `assets_hashes`).
   Tras sellar, `seal` regenera el `README.md` del experimento para reflejar
   el estado post-operación.
5. `finish --decision GO|NO_GO|INCONCLUSIVE --rationale "..." [--duration-seconds N]`
   cierra el registro con la decisión y también regenera el `README.md` del
   experimento.
6. `maintain --assets PATH... --reason "..." --content-commit HASH` actualiza
   de forma auditada los assets sellados que cambiaron después del sello
   (ver sección "Mantenimiento del sello").

## Inmutabilidad post-seal

- Después de `seal`, `validate` falla si cualquier archivo sellado cambia o
  desaparece (recalcula y compara los hashes de `dataset_hashes`,
  `model_hashes`, `binary_hashes` y `assets_hashes`).
- No se permite volver a sellar un experimento ya sellado: re-sellar rompería
  el cegamiento que soporta FND-05.
- `finish` y `maintain` son las únicas operaciones que modifican
  `manifest.json` después del sellado. La regeneración del `README.md` del
  experimento por `seal`/`finish`/`maintain` es la excepción documentada a
  esta regla.
- Editar `manifest.json` a mano queda prohibido; usar los subcomandos del tool.

## Mantenimiento del sello (`maintain`)

Cuando un asset sellado cambia después del sello (por ejemplo, un documento
vivo versionado por git), `validate` falla por desviación de hash. `maintain`
documenta esa deriva sin romper el registro:

```text
python scripts/experiment_manifest.py maintain <EXPERIMENT_ID> \
  --assets <paths...> --reason "..." --content-commit <hash>
```

- Solo aplica a experimentos sellados (`sealed=true`); en otro caso, error.
- `--reason` y `--content-commit` son obligatorios.
- Solo se aceptan `--assets`. `--dataset`/`--models`/`--binaries` se
  rechazan: datasets/modelos/binarios son inmutables y `maintain` nunca
  altera `dataset_hashes`, `model_hashes` ni `binary_hashes`. Un path de
  `--assets` que pertenezca a esos buckets es un error y no se toca nada.
- Por cada path: se computa el SHA-256 actual. Si coincide con el sellado,
  no-op (`unchanged, skipped`). Si difiere, se añade una entrada a
  `seal_maintenance` y se actualiza `assets_hashes`.
- Entrada de `seal_maintenance`: `date` (ISO 8601), `reason`, `path`,
  `previous_hash` (hash sellado anterior), `new_hash` (hash actual) y
  `content_commit` (commit git del cambio). El sello original (`sealed`,
  `sealed_at`, hashes de datasets/modelos/binarios) queda intacto; el hash
  viejo de cada asset se conserva en `previous_hash` (nada se oculta).
- `maintain` regenera el `README.md` del experimento con la subsección
  "Mantenimiento del sello" (fecha, paths y motivos).

## Política futura: documentos vivos fuera de los sellos

**`docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` es un documento vivo
versionado por git y NO debe incluirse como asset en sellos futuros.** Su
historia la guarda git, no el sello. Si ya fue sellado (FND-05/FND-06), su
deriva se documenta con `maintain` en lugar de re-sellar.

## Hashes

- SHA-256 por archivo; los directorios se expanden archivo por archivo en
  orden determinístico.
- Las rutas se normalizan relativas al raíz del repositorio git. Si el archivo
  vive en otra unidad (Windows), se guarda la ruta absoluta.
- Lectura por bloques de 1 MiB: apto para datasets grandes (cientos de MB) sin
  cargarlos en memoria.

## Regla de producción

**Los artefactos de producción permanecen fuera de este árbol.** Nada de aquí
se consume en runtime de producción, y ningún artefacto de producción
(modelos, manifests operativos, thresholds) vive dentro de
`scripts/artifacts_science/`. Este árbol es el registro científico del
programa experimental y SÍ se commitea: no agregar a `.gitignore`.

## Herramienta

- `scripts/experiment_manifest.py`: CLI en Python 3.14, solo biblioteca
  estándar (json, hashlib, platform, subprocess, os, sys, argparse, datetime,
  ctypes para RAM en Windows). Sin pip ni dependencias externas.
- `scripts/test_experiment_manifest.py`: pruebas autocontenidas; imprime `OK`
  y sale 0 si pasan.
- El tool reconfigurea stdout/stderr a UTF-8 con `errors='replace'` (Windows).
- GPU detectada vía `nvidia-smi --query-gpu=name` con fallback silencioso
  `unknown`; RAM vía `GlobalMemoryStatusEx` en Windows.

## Limitaciones conocidas

- El validador embebido implementa solo el subconjunto de draft-07 usado por
  este schema (`const`, `type`, `required`, `properties`,
  `additionalProperties`, `items`, `enum`, `pattern`, `minLength`, `minimum`,
  `format: date-time`). Si un schema futuro necesita `$ref`/`oneOf`, hay que
  ampliar `_validate` en el tool.
- El `commit` de `git_state` registra el estado al hacer `init`; si se
  commitea después, ese campo queda desactualizado (es historia, no cambia).
