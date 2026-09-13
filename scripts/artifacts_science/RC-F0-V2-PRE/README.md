# RC-F0-V2-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El conjunto de poses v1 se construyo con distinta politica de generacion segun el complejo (MolFlex en 13 de 116); reconstruirlo aplicando el generador congelado a los tres splits produce un conjunto homogeneo cuya cobertura del oraculo es medible y cuya tarea de ranking es la de produccion

## Protocolo

Referencia: `RC-F0-V2-PRE/PREREGISTRO.md; contrato original build_pose_selector_dataset.py + ruta_c_fase1_5_v05.py; gate de reproduccion superado antes de anadir poses`

## Gate

G1 reproduccion linea a linea de v1, G2 integridad del cache de features, G3 conservacion de split, G4 conservacion de etiquetas y features base de las poses v1 conservadas, G5 cobertura >= 79.3% en train y >= v1 por split, G6 cero poses sin features y cero NaN

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `3e07fe51f44462efee34e2e67d5387ad345ea6c7`, dirty=True

## Estado

- Creado: 2026-08-18T01:38:05.168375+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T01:38:05.905772+00:00)
- Finalizado: 2026-08-18T01:38:06.077203+00:00
- Razón de la decisión: Prerregistro sellado antes de reconstruir. Declara tres decisiones de diseno y sus consecuencias: (1) se regenera en los TRES splits porque anadir poses solo a train pondria train y val/test en regimenes distintos -numero de candidatos, distribucion de cluster_density que no es invariante de escala, dificultad del ranking- y un selector medido asi mediria el cambio de regimen y no su capacidad; generar poses en val/test no es fuga porque no se ajusta nada ni se miran etiquetas para decidir, y D-RC-CONFIRM no se toca. (2) Entran TODAS las poses dockeadas, que es el contrato que ya tenia la fuente S2, con la consecuencia declarada de que la tarea cambia de rankear ~9 candidatos a ~180: v2 no es v1 ampliado sino una tarea distinta y mas parecida a produccion, y queda PROHIBIDO comparar cifras de v0.6 entre v1 y v2 sin re-entrenar. (3) La fuente molflex se regenera entera desde MF-02D/E porque el receptor con el que se calcularon las poses molflex de v1 ya no existe en disco y mezclarlas meteria una firma de procedencia dentro de una misma fuente. Dos gates ya estan superados y declarados: la reproduccion linea a linea de los tres splits v1 desde los registros intermedios (2739/730/831 identicos, incluida la division por scaffold con semilla 42) y la integridad del cache de 4300x215 features, cuyos SHA de splits coinciden. Fuera de alcance explicito: no se entrena ni evalua ningun selector.
- Hashes de dataset: 4 archivo(s) con SHA-256
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
