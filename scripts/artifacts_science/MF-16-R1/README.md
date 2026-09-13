# MF-16-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El potencial fisico relajado ordena las poses mejor que Vina; la conclusion de MF-16 era un artefacto del punto unico

## Protocolo

Referencia: `corrigendum: relectura de las energias YA MINIMIZADAS que MF-10 registro sobre las mismas 714 poses; sin computo nuevo`

## Gate

medicion sin gates; comparacion PAREADA por complejo contra Vina

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:02.633659+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:03.457163+00:00)
- Finalizado: 2026-08-19T03:53:03.676033+00:00
- Razón de la decisión: CORRIGENDUM de MF-16, que se ejecuto y se reporto con energias de PUNTO UNICO. Esa energia esta dominada por choque esterico -36 de 714 poses superan 1e4 kcal/mol y algunas llegan a 1e8- de modo que el Spearman ordenaba por severidad de colision, no por calidad de union. Con las energias relajadas: rho 0.199 en COLOCACION frente a -0.110 del punto unico y 0.132 de Vina; 0.588 en CONTROL frente a 0.140 y 0.533. La conclusion de MF-16 -que el potencial fisico no orienta- queda INVALIDADA. Pero la lectura correcta NO es que el FF gane en ambos estratos: comparado PAREADO, en COLOCACION el FF supera a Vina (delta +0.107, mejor en 16 de 25) y en CONTROL PIERDE (delta -0.099, mejor en 6 de 13). Las medianas por estrato sugerian lo contrario en CONTROL y por eso se reporta el pareado. El hallazgo especifico es que el potencial fisico ayuda JUSTO donde Vina es debil. Advertencia: la relajacion mueve la pose, asi que rmsd_despues no es el mismo objeto que el rmsd_antes con el que se evalua a Vina; la comparacion es indicativa y no un head-to-head exacto.
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
