# RS-14-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Corregidas las etiquetas por simetria, el selector supera al baseline vina_score en precision condicional

## Protocolo

Referencia: `RS-14-R1-PRE/PREREGISTRO.md; v2 train; etiquetas rmsd_sym; protocolo de RS-14 congelado e importado`

## Gate

G1 validez, G2 superioridad con CI95 BCa pareado excluyendo cero, G3 nulo por permutacion

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:51.209581+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-18T20:19:51.779245+00:00)
- Finalizado: 2026-08-18T20:19:51.918291+00:00
- Razón de la decisión: Precision condicional 0.4601 frente a 0.5543 del baseline, diferencia pareada -0.0942 con CI95 BCa [-0.2138, +0.0217] sobre los mismos 92 complejos cubiertos. Corregir el defecto ENSANCHO la brecha: de -0.0471 en RS-14 a -0.0942 aqui, porque el baseline gano +7.6 pp (7 complejos) y el selector solo +2.9 pp. El defecto de simetria estaba ocultando cuanto mejor es ya vina_score. Las tres predicciones preregistradas se cumplieron: selector en [0.45, 0.58] -> 0.4601; diferencia en [-0.15, +0.05] -> -0.0942; G3 pasa con holgura -> 0.4601 frente a p95 0.1848 con p empirico 0.0. El selector SIGUE aprendiendo senal real, casi 2.5x el nulo, pero lo que aprende no anade nada sobre el score de Vina. Por la regla de cierre declarada en el prerregistro antes de ejecutar, este NO_GO cierra la cartera D de forma definitiva: el corrigendum no cambio la decision, asi que por la §19.1 no reinicia el contador de futilidad, y RS-11/12/13 quedan bloqueados permanentemente bajo este diseno. Limitacion declarada: 1,143 de 18,812 poses (6.1%) conservan RMSD ingenuo, sesgo que va EN CONTRA de un GO. Val y test intactos.
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
