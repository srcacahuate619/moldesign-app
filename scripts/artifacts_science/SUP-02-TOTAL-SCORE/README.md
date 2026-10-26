# SUP-02-TOTAL-SCORE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El total_score 0-100 que el producto muestra como indice de calidad (SAR, Comunidad, score certificado de Moldex) ordena las afinidades experimentales mejor que el score de Vina sin transformar

## Protocolo

Referencia: `scripts/artifacts_science/SUP-02-TOTAL-SCORE/entrada/REGISTRO_PREVIO.md`

## Gate

Dif. de Spearman total_score menos Vina con IC95 bootstrap pareado: GO si el IC excluye el cero por encima en las dos series; DANO si lo excluye por debajo en alguna; si no, NO_GO (no demuestra valor anadido)

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `52cfa4523854c7c09187d30fd444872a555f2aa6`, dirty=False

## Estado

- Creado: 2026-10-25T18:34:51.700590+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-10-25T18:40:30.452362+00:00)
- Finalizado: 2026-10-25T18:40:31.052171+00:00
- Razón de la decisión: El total_score 0-100 no ordena mejor que Vina sin transformar: 8T69 rho 0,397 frente a 0,392 (dif. +0,005, IC95 -0,058 a +0,061; rho total_score~Vina 0,97); 8HFI rho 0,029 frente a 0,129 (dif. -0,101, IC95 -0,334 a +0,134). Sin dano demostrado; no demuestra valor anadido.
- Hashes de dataset: 3 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

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
