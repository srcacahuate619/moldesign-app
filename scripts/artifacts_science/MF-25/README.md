# MF-25

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El coste de colocacion responde al presupuesto de busqueda: si es falta de muestreo, subir exhaustiveness lo reduce

## Protocolo

Referencia: `MF-25/README; contenedor moldesign-lab; 48 complejos, mejor conformero por RMSD alineado, exhaustiveness 8/32/128 (16x el protocolo congelado)`

## Gate

medicion con lectura preregistrada: baja >0.5 A => PRESUPUESTO; no baja => PAISAJE

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:52:55.552450+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-19T03:52:56.310683+00:00)
- Finalizado: 2026-08-19T03:52:56.503037+00:00
- Razón de la decisión: Diagnostico: PAISAJE. Multiplicar el presupuesto por 16 convierte CERO complejos adicionales (1/33 en los tres presupuestos). El coste baja 0.784 A pero toda la mejora ocurre entre exh=8 y exh=32 (4.284 -> 3.508); de 32 a 128 el movimiento es 0.008 A -ruido- mientras el tiempo se cuadruplica a 407 s por complejo. Es la firma de saturacion: la busqueda ya habia encontrado todo lo que su funcion de puntuacion le permite. El control lo confirma por contraste: coste 0.608 A plano en los tres presupuestos y 15/15 desde exh=8. En ningun regimen el presupuesto es la palanca. Se evito la circularidad comparando la RESPUESTA al presupuesto y no el NIVEL del coste, que es tautologico porque el estrato se definio por fallo de colocacion. Nota: en exh=32 el control marca 14/15 en vez de 15/15, lo que solo es posible por estocasticidad de Vina; FND-03 midio despues que la sd en CONTROL es 0.011 A, asi que ese caso es un outlier y no un patron.
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
