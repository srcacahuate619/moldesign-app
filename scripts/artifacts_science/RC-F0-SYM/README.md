# RC-F0-SYM

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Corregir la simetria en la metrica de pose cambia la cobertura del oraculo del conjunto v2 y por tanto el denominador de la cartera D

## Protocolo

Referencia: `medicion: relectura del material de RC-F0-V2 con la metrica corregida de la §5.1; 32,215 poses de fuente molflex emparejadas por (pid, file_stem, model_idx); sin computo nuevo y sin evaluar ningun selector`

## Gate

medicion sin gates; verificacion obligatoria: el RMSD ingenuo recomputado debe reproducir el almacenado

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:50.355096+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T20:19:50.924828+00:00)
- Finalizado: 2026-08-18T20:19:51.066092+00:00
- Razón de la decisión: Medicion valida: el RMSD ingenuo recomputado reproduce el almacenado con error maximo de 0.0005 A -el redondeo del fichero- en los tres splits, 203 de 203 complejos. Resultado principal: la cobertura del oraculo NO se mueve ni un complejo (train 79.31%, val 87.50%, test 97.87%; cero complejos ganan en ninguno), lo que ACOTA el dano del defecto: las cifras de RC-F0-V2, el denominador de RS-14 y la tabla de factibilidad de la §9 se sostienen exactamente. Pero a nivel de pose las etiquetas si estan mal: positivas 357 -> 432 en train (+21.0%), 187 -> 196 en val (+4.8%), 216 -> 252 en test (+16.7%), con tasas de corrupcion distintas por split. Eso habilito RS-14-R1 bajo la condicion 2 de la §19.1. Alcance declarado: solo el 94% de las poses es recomputable, y como corregir solo puede bajar el RMSD, la cobertura reportada es una cota inferior.
- Hashes de assets: 1 archivo(s) con SHA-256

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
