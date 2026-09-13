# RS-14-R1-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Corregidas las etiquetas por simetria, el selector supera al baseline vina_score en precision condicional sobre los complejos cubiertos

## Protocolo

Referencia: `RS-14-R1-PRE/PREREGISTRO.md; conjunto v2 train (18,812 poses, 116 complejos); etiquetas rmsd_sym de RC-F0-SYM; protocolo de RS-14 congelado e importado, no copiado: features, contrato v0.6, hiperparametros, LOCO y nulo identicos`

## Gate

G1 validez de los 348 ajustes LOCO, G2 superioridad con CI95 BCa pareado excluyendo cero, G3 nulo por permutacion, G4 determinismo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:46.930353+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T20:19:47.530468+00:00)
- Finalizado: 2026-08-18T20:19:47.670652+00:00
- Razón de la decisión: Prerregistro escrito antes de ejecutar, con hash SHA-256 registrado en anterioridad.json para que el sello pueda probar que precede a los resultados. Legal bajo la condicion 2 de la §19.1: corrige un defecto de implementacion documentado (RC-F0-SYM midio +21.0% de positivas mal etiquetadas en train), no una arquitectura, una perdida ni una seed. Declara por adelantado el baseline corregido ya medido (0.5543 frente a 0.4783), la prediccion NO_GO, y la regla de cierre: un NO_GO cierra la cartera D de forma definitiva.
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
