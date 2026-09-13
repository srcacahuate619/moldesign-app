# RS-04-OOF

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La feature de strain MMFF94s mejora Top-1 OOF de v0.6 sin degradar RMSD pareado

## Protocolo

Referencia: `CAMPANA-2-PLAN sellado (41b7f09) QA-6 + RS-04-QC sellado (5ffb256)`

## Gate

Top-1 OOF >=50/116; mediana pareada dRMSD <=+0.1A; cobertura >=95%; costes P95; sin regresion grave por estrato

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `5ffb25639280e49f10e7f9af7f6d4405939e7281`, dirty=True

## Estado

- Creado: 2026-08-16T23:27:03.349822+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-16T23:53:29.314279+00:00)
- Finalizado: 2026-08-16T23:53:29.708386+00:00
- Razón de la decisión: Gate operacional FAIL: Top-1 OOF 39/116 vs 50 requeridos (baseline v0.6 47/116, Delta -8); McNemar bilateral p=0.115318 (ns); regresion grave en estrato hard. Mediana pareada 0.000 A cumple (<=0.1), cobertura 100% y costes P95 cumplen. El strain MMFF94s es coste-neutral en RMSD pero sin poder de seleccion en esta cohorte; v0.6 sigue siendo el selector de produccion. val40/D-RC-CONFIRM intactas.
- Hashes de assets: 9 archivo(s) con SHA-256

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
