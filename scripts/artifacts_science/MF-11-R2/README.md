# MF-11-R2

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El umbral de deduplicacion de MF-11-R1 (1.5 A, derivado sobre v1) no es transferible al conjunto v2, 6.9x mas denso

## Protocolo

Referencia: `MF-11-R1 contrato heredado literal (diametro controlado, medoid geometrico, umbrales 0.5-2.0); solo cambia el conjunto; train, val y test por separado`

## Gate

G1 validez; G2 existe un umbral con 0 perdidas de cobertura, degradacion mediana <=0.1 A y reduccion >=10%; se elige el MAYOR que cumpla las tres

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:14.563009+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:15.337984+00:00)
- Finalizado: 2026-08-19T03:53:15.520999+00:00
- Razón de la decisión: Entregable 9 del programa, pendiente desde el 2026-08-17. Umbral elegido 2.0 A en los tres splits, frente a 1.5 A de v1: reduccion 31.7% en train (18,812 -> 12,852 poses), 37.7% en val y 38.2% en test, con 0 perdidas de cobertura. RC-F0-V2 tenia razon al exigir la re-derivacion. TENSION DECLARADA: 2.0 A es TAMBIEN el umbral de exito. Un cluster de diametro 2.0 puede contener una pose a 1.9 A del cristal y otra a 3.9 A, y si el medoid cae del lado malo se pierde cobertura. En train no ocurrio, pero el margen es fino y la regla solo restringe la mediana, no la cola (p90 = 0.358 A). Para produccion, 1.5 A es la eleccion conservadora aunque la regla preregistrada seleccione 2.0. ANOMALIA REGISTRADA: val pierde 1 complejo a U=1.5 y 0 a U=2.0 -no monotono-, porque al cambiar el umbral cambia toda la particion y el medoid de otra particion puede ser mejor pose. Las "0 perdidas" a 2.0 son en parte suerte de particion, no garantia.
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
