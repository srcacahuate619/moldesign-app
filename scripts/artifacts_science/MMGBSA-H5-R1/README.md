# MMGBSA-H5-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Replica de MMGBSA-H5-GBN2-PARIDAD con un filtro de validez geometrica: entre las topologias con Br o I de geometria posible, OpenMM 8.5.2 (Reference) reproduce a sander en vacuum y GBn2 sin superficie (residuo < 0.001 kcal/mol, fuerza convertida < 0.001 kcal/mol/A), con la misma excepcion del azufre que H5; y el OpenMM del runtime de Windows reproduce al de Linux.

## Protocolo

Referencia: `backend/audits/gbn2_paridad_halogenos_r1.py, que importa sin modificar el script sellado de H5, sobre las mismas 55 topologias; corridas nuevas en directorios nuevos (servidor con sander; esta maquina con frontend/src-tauri/resources/python). Filtro declarado antes de medir: geometria imposible si dos atomos estan a < 0.5 A o un angulo de valencia mide < 30 grados. Se diseno despues de ver 5mlj en H5 y se comprobo solo sobre geometrias (sin energias) antes de este prerregistro: marca 5mlj (Br) y 6gnp (Cl, control); en los dos el SDF de PDBBind anade un H a un carbono sp2 halogenado. Diagnostico fuera del gate: recolocar ese H (perpendicular al plano si el centro es plano) y medir la paridad.`

## Gate

GO si entre las topologias con Br o I de geometria posible hay al menos 20 y todas pasan en vacuum y GBn2_no_SA, o -solo si llevan S- el vacio pasa y el desacuerdo desaparece con el S como elemento generico; las de geometria imposible cuentan como INDETERMINADO; y OpenMM de Windows reproduce al de Linux (< 1e-6 kcal/mol y kcal/mol/A) en todas las comparaciones con las mismas entradas. Cualquier otro fallo: NO_GO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `ddb5304aedd27e913ec54a1f25d5218563fc8a95`, dirty=True

## Estado

- Creado: 2026-09-23T17:59:05.333933+00:00
- Status: created
- Decisión: PENDING

## Flujo de trabajo

1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.
2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.
3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.
4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.
5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.
6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.

Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.

## Inmutabilidad post-seal

- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).
- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.
- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.
- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.
- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).

## Archivos

- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).
- `metrics.json`: métricas agregadas del experimento.
- `per_complex.jsonl`: una línea JSON por complejo evaluado.
- `failures.jsonl`: una línea JSON por fallo.
- `README.md`: este archivo.
