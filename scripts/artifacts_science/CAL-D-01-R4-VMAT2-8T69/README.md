# CAL-D-01-R4-VMAT2-8T69

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con 8T69 (VMAT2, cadena A, caja del catálogo), receta 7, Vina 1.2.7 y Q = -E(top-1), el producto reproduce la pose de la tetrabenazina (YHL) y ordena los 89 Ki publicados de US11718618B2 (Example 11, plaquetas humanas, [3H]DTBZ): rho de Spearman y rho de peor caso sobre asignaciones binarias de lote (F = 1015/703) con límite inferior del IC95 % > 0.

## Protocolo

Referencia: `scripts/artifacts_science/CAL-D-01-R4-VMAT2-8T69/entrada/protocolo.json`

## Gate

P1 del registro previo R4 (SHA-256 0a1a4aed): puerta de pose >= 3/5 semillas a RMSD <= 2 A y PoseBusters válido; GO sólo si el IC95 % inferior de rho y de rho_peor (bootstrap pareado por padre, 10000, semilla 20261021) es > 0, sin fallos persistentes ni desviaciones; < 85 padres evaluados = EXPLORATORIO; tope 168 CPU-core-h.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/cal-d-01-r4`, commit `6f3ff1b5ded74db2fe2f8b03515b0283fb6c88d4`, dirty=True

## Estado

- Creado: 2026-10-22T03:21:03.209370+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-10-22T05:18:21.139953+00:00)
- Finalizado: 2026-10-22T05:19:08.883643+00:00
- Razón de la decisión: Registro previo R4 (0a1a4aed). Puerta de pose superada: 5 de 5 semillas, RMSD 0,67-0,71 A, PoseBusters valido. Panel: 88 de 89 padres acoplados; 4-67 (biciclo[1.1.1]pentano) es un fallo persistente: el pipeline del producto lo corta a los 1200 s en los dos intentos. Medida: rho(Q,pKi) = 0,391, IC95 bootstrap [0,219; 0,537]; rho de peor caso sobre las asignaciones binarias de lote = 0,320, IC95 [0,139; 0,473]; ambos limites inferiores > 0. P2 (pares con cociente de Ki > F): concordancia 0,637 [0,576; 0,694]. La regla registrada exige cero fallos persistentes para GO, asi que la decision formal es NO_GO por ese fallo, no por la señal. Sin reglas cambiadas despues de ver scores; ver DESVIACIONES.md. Cualquier re-analisis sin 4-67 seria otro registro y otro intento.
- Hashes de dataset: 197 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 10 archivo(s) con SHA-256

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
