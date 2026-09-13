# MF-22

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El presupuesto de error explica el fallo: el error conformacional y el de colocacion se suman, y un conformero a 1.36 A consume casi todo el margen de 2 A

## Protocolo

Referencia: `medicion: cruce por conformero del RMSD alineado de entrada con el mejor RMSD en marco de pocket que ESE conformero produjo; sin computo nuevo`

## Gate

medicion sin gates; curva de conversion frente al error conformacional de partida

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:07.414708+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-19T03:53:08.181525+00:00)
- Finalizado: 2026-08-19T03:53:08.380021+00:00
- Razón de la decisión: HIPOTESIS REFUTADA para el estrato dificil. En COLOCACION la tasa de conversion es CERO en todas las bandas, incluida 0.0-0.5 A (7 conformeros con conformacion practicamente perfecta y ninguno produjo una pose <=2 A). Lo que separa a los estratos es el COSTE DE COLOCACION: 0.741 A en control frente a 3.847 A en los dificiles, cinco veces mas. En CONTROL el modelo SI funciona y da una especificacion usable: curva monotona (0.947 / 0.870 / 0.581 / 0) con corte alrededor de 1.5 A de error conformacional, y colocacion casi gratis (0.55-0.78 A). Hallazgo de diseno registrado: el MF-22 planeado -dockear rigido cada conformero- YA es el pipeline (molflex.dockear_conformero dockea conf{cid}.rigid.pdbqt con TORSDOF 0), asi que se rediseno para medir el presupuesto de error. Se detecto y corrigio una violacion del teorema de cuerpo rigido (pose < alineado, imposible) en 70 de 970 conformeros, causada por el hidrogeno retenido que MolFromMolFile deja en 6 complejos; tras corregir con RemoveAllHs, 0 violaciones de 970.
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
