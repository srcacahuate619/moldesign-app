# MF-12

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Se puede predecir el fallo de colocacion antes de dockear, con predictores disponibles sin conocer la pose cristalografica

## Protocolo

Referencia: `MF-12-PRE/PREREGISTRO.md; regresion logistica; entrenamiento en los 116 de train, evaluacion UNA sola vez en los 87 de val+test; dos niveles de disponibilidad (L solo ligando, L+S con sitio)`

## Gate

G2 precision balanceada de L supera al baseline mayoritario con CI95 que excluya el cero; G3 se reportan L y L+S por separado y el claim se hace sobre L

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:52:56.704098+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:52:57.444192+00:00)
- Finalizado: 2026-08-19T03:52:57.641607+00:00
- Razón de la decisión: ID declarado desde el inicio del programa y nunca ejecutado por falta de predictores medidos. Nivel L (solo ligando, sin conocer el sitio): precision balanceada 0.654 frente a 0.500 del baseline, diferencia pareada +0.218 con CI95 BCa [0.081, 0.322]. El MDE declarado ANTES de correr era 0.136, y el efecto observado lo supera: es resoluble por este diseno. Anadir descriptores de sitio (L+S) suma apenas +0.015, asi que el clasificador NO depende de conocer el bolsillo, que es lo que lo hace usable. Se descartaron por fuga los tres predictores de MF-24 que usan la pose cristalografica (rmsd_conf, enterramiento, ocupacion_caja). Dos de las tres predicciones preregistradas FALLARON: el enterramiento del sitio no era necesario (L funciona sin el) y el rendimiento supero el rango previsto. La tercera se cumplio y con holgura: las torsiones aportan +0.0165, esencialmente cero. Los coeficientes dominantes son ocupacion del conformero (-1.009) y numero de conformeros (-0.876): lo que predice el fallo es el volumen efectivo de busqueda, no el conteo de torsiones. Limitaciones: 0.654 no es un clasificador de produccion; no se mide el coste de enrutar mal; un solo modelo y un solo split.
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
