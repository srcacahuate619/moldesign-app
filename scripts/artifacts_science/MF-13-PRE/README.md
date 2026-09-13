# MF-13-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La funcion de puntuacion de Vina prefiere la pose nativa cuando se la entregan; separar fallo de busqueda de fallo de puntuacion en la cohorte dificil

## Protocolo

Referencia: `MF-13-PRE/PREREGISTRO.md; contenedor moldesign-lab; 116 complejos de train; score_only y local_only sobre la pose cristalografica en su propio receptor y su propia caja, los mismos del docking v2`

## Gate

G1 >=95% de complejos con score finito; G2 fraccion de COLOCACION donde el cristal relajado gana al mejor dock: >=0.70 BUSQUEDA, <=0.30 PUNTUACION, intermedio MIXTO

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:46.071994+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T20:19:46.642578+00:00)
- Finalizado: 2026-08-18T20:19:46.784735+00:00
- Razón de la decisión: Prerregistro escrito antes de ejecutar. MF-09 midio que el buscador no PRODUCE la pose nativa, pero nadie pregunto si la funcion la RECONOCERIA si se la entregaran. Son dos fallos con consecuencias opuestas: si la funcion prefiere la nativa la palanca es el muestreo; si no, ninguna palanca de muestreo puede funcionar. Se declaran los umbrales 0.70/0.30 y la prediccion BUSQUEDA antes de ver datos, y se declara el sondeo de 3 complejos que descubrio y corrigio un defecto del montaje (local_only no escribe REMARK VINA RESULT y la pose relajada hay que re-puntuarla).
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
