# CAL-D-01-R4-2-VMAT2-8T69

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con el producto de 1.0.4 y el protocolo congelado de R4 (8T69, receta 7, Vina 1.2.7, Q = -E(top-1)), el producto completa los 89 padres de US11718618B2, 4-67 incluido, y rho y rho_peor (F = 1015/703) tienen limite inferior del IC95 % > 0

## Protocolo

Referencia: `scripts/artifacts_science/CAL-D-01-R4-2-VMAT2-8T69/entrada/REGISTRO_PREVIO_R4_2.md`

## Gate

La de R4 sin cambios: puerta de pose >= 3/5 semillas a RMSD <= 2 A y PoseBusters passed; GO si el IC95 % inferior de rho y de rho_peor (bootstrap pareado por padre, 10000, semilla 20261021) > 0, sin fallos persistentes (sin score tras el reintento) ni desviaciones; < 85 padres = EXPLORATORIO. Una validacion fisica not_evaluated con score cuenta como evaluada y se declara aparte sin decidir.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `18eb7e13e7a7cff0f7f5e2f33df329c97fee2560`, dirty=True

## Estado

- Creado: 2026-10-25T02:18:21.916825+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-10-25T02:58:57.030671+00:00)
- Finalizado: 2026-10-25T03:00:05.252708+00:00
- Razón de la decisión: Puerta de pose 5/5 (RMSD 0,67-0,71 A, PoseBusters passed); 89/89 padres evaluados, 4-67 incluido, sin fallos persistentes ni desviaciones; rho 0,39 (IC95 0,22-0,54) y rho_peor 0,32 (IC95 0,14-0,47). Declarado sin decidir: 4-67 con validacion fisica not_evaluated; sin el, rho 0,39 (0,22-0,54). Los 88 comunes con R4 reproducen su energia.
- Hashes de dataset: 202 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

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
