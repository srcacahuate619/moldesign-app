# MF-02F-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En MolFlex cada conformero es una corrida de docking independiente, de modo que n_conf es tambien el numero de reinicios de busqueda; subir de K30 a K90 debe recuperar complejos cuyo fallo es de colocacion

## Protocolo

Referencia: `MF-02F-PRE/PREREGISTRO.md; corrige la lectura de MF-02A sobre el eje de muestreo; K30 reutiliza el material sellado de MF-02D via anidamiento verificado de prefijos ETKDG`

## Gate

G1 validez >=95%, G2 K90 recupera >=3 de 33 (umbral derivado de D-MF-HARD-CURVE), G3 saturacion informativa, G4 determinismo, G5 anidamiento exacto

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `e6c551f78a26e27af0ea085747a1bbcd3828f1fc`, dirty=True

## Estado

- Creado: 2026-08-18T02:32:21.612335+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T02:32:22.576263+00:00)
- Finalizado: 2026-08-18T02:32:49.284636+00:00
- Razón de la decisión: Prerregistro sellado antes de ejecutar, y nace de una correccion de mi propia lectura. MF-02A midio el techo CONFORMACIONAL y de ahi escribi en docs/49 que anadir conformeros es la palanca equivocada; eso era demasiado fuerte y el registro sellado lo contradice. En MolFlex cada conformero es una corrida de docking independiente, de modo que n_conf tiene dos papeles y MF-02A solo midio uno. D-MF-HARD-CURVE mide el otro: cobertura hard 5.9 a 17.6 a 23.5 por ciento en K5/K15/K30, ganancia pareada K15 a K30 de -0.289 A con CI95 BCa que excluye el cero, y declara que NO hay saturacion; los controles saturan en K15 y los hard no. Nadie ha medido K60/K90 con docking, y el modo de fallo dominante es la colocacion, sobre la que mas reinicios es una intervencion legitima. Se verifico ANTES de disenar que el ensemble de 30 es prefijo byte-identico del de 90 en los complejos de prueba, lo que permite reutilizar el material sellado de MF-02D como brazo K30 sin recomputar y reduce el coste en un tercio. Se declara por adelantado lo que NO es evidencia: con prefijos anidados la cobertura solo puede subir, asi que la monotonia esta garantizada por construccion y presentarla como hallazgo seria describir una tautologia; lo informativo es la magnitud y el coste por complejo recuperado. El umbral de G2 se deriva del prior sellado y no se inventa: D-MF-HARD-CURVE gano 5.9 puntos al duplicar K15 a K30, y de K30 a K90 hay 1.58 duplicaciones, que a la misma tasa dan 3 de 33. Comparte cohorte con MF-08 y queda prohibido asumir que los efectos de ambos se suman.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 4 archivo(s) con SHA-256

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
