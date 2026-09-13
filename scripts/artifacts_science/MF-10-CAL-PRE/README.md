# MF-10-CAL-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El suelo del instrumento y la convergencia del minimizador determinan si el NO_GO de MF-10 es una medicion valida del campo de fuerza o un artefacto

## Protocolo

Referencia: `MF-10-CAL-PRE/PREREGISTRO.md; contenedor moldesign-lab; brazo A control positivo minimizando el cristal de los 48 complejos; brazo B barrido maxIterations 500/2000/10000 sobre 24 poses de la banda 2-3 A elegidas por score`

## Gate

C1 reportar la deriva del cristal, C2 deriva mediana < 1.0 A, C3 mejora <= 0.1 A al multiplicar por 20 el presupuesto

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:45.190256+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T20:19:45.796338+00:00)
- Finalizado: 2026-08-18T20:19:45.933271+00:00
- Razón de la decisión: Prerregistro escrito antes de ejecutar. Cubre los dos controles ausentes que la auditoria de MF-10 identifico: no habia control positivo (nunca se minimizo el cristal, asi que no se conocia el suelo del instrumento) y no se registraba la convergencia (la correlacion entre caida de energia y movimiento del ligando fue 0.134, compatible con presupuesto agotado en los hidrogenos de proteina). Se declara la prediccion de deriva en (0, 1.0) A y la regla de lectura de C3 antes de ver resultados: C3 PASS deja el G3 de MF-10 como medicion legitima, C3 FAIL lo convierte en inconcluso.
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
