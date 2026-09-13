# MF-15

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Existe un embudo en el paisaje de puntuacion que guia hacia el minimo nativo

## Protocolo

Referencia: `medicion: lectura de rmsd y vina_score del conjunto v2 sellado; Spearman restringido a poses con rmsd <= R, para R creciente; sin computo nuevo`

## Gate

medicion sin gates; embudo => rho POSITIVO entre rmsd y score

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:00.205032+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:01.048295+00:00)
- Finalizado: 2026-08-19T03:53:01.243755+00:00
- Razón de la decisión: El embudo existe en control y resto y esta casi ausente en el estrato dificil: rho global 0.209 en COLOCACION frente a 0.497 en CONTROL y 0.360 en RESTO, y debil A TODOS LOS RADIOS, no solo lejos. Un buscador que se guie por el score no tiene nada que seguir en esos complejos. Salvedad declarada: la tabla de score por banda de RMSD (-8.85 en 0-1 A hasta -6.27 en >12 A) PARECE un embudo global de 2.6 kcal/mol pero MEZCLA complejos -solo 9 de 33 tienen alguna pose bajo 1 A, y son mejores unidores de partida-, asi que ese gradiente aparente es en parte efecto de seleccion entre complejos. El numero honesto dentro de cada complejo es el Spearman. Y para COLOCACION los radios pequenos no son usables: a R<=2 A hay 0 complejos con muestra suficiente y a R<=3 A solo 2.
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
