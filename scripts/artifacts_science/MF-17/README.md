# MF-17

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Alguno de los cuatro mecanismos medidos (cobertura, preferencia de la funcion, radio de cuenca, embudo) separa los complejos que el docking resuelve de los que no

## Protocolo

Referencia: `medicion descriptiva: cruce de MF-09, MF-13, MF-14 y MF-15-EXT sobre la misma cohorte de 48; sin computo nuevo`

## Gate

medicion sin gates; correlacional sobre n=48, no identifica causas

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:03.893802+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:04.727650+00:00)
- Finalizado: 2026-08-19T03:53:04.940403+00:00
- Razón de la decisión: Solo el embudo separa: rho 0.480 en los resueltos frente a 0.211 en los que fallan (+0.269). El radio de captura NO discrimina nada (r50 = 2.0 en ambos grupos) y que la funcion prefiera la nativa tampoco (61% frente a 67%). La ventaja del cristal va al reves -mayor donde falla (2.22 vs 0.72)- pero eso es consecuencia, no causa: donde el docking fracasa todas las poses son malas y el cristal les gana por mucho. CONFUSION DECLARADA que limita el hallazgo: el grupo resuelto es 15 de 18 CONTROL y el que falla es 30 de 30 COLOCACION. Los estratos se definieron POR exito de docking, asi que la separacion esta casi perfectamente confundida con el estrato y es en buena parte MF-15 dicho de otra forma. El contraste limpio seria dentro de COLOCACION, y ahi hay 3 resueltos contra 30: no se puede.
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
