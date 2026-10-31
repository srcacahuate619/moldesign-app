# SUP-05-CORTES-DEL-SITIO

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El estado de Preparacion casi no depende de sus cortes sin medir: mover el de huecos (8 A) entre 7 y 9 A y el de especies junto al sitio (6 A) entre 5 y 7 A cambia la decision en <= 5 % de las entradas del catalogo

## Protocolo

Referencia: `scripts/artifacts_science/SUP-05-CORTES-DEL-SITIO/entrada/REGISTRO_PREVIO.md`

## Gate

GO si las entradas cuyo estado por huecos cambia entre 7 y 9 A y las cuyo estado por especies cambia entre 5 y 7 A son ambas <= 5 % de las medibles; NO_GO si alguna supera el 5 %; INCONCLUSIVE con < 300 medibles

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/sup05-cortes`, commit `3ca7f633dd64ef08aa311d26a0e6e0b74f4bbb8d`, dirty=True

## Estado

- Creado: 2026-10-26T03:12:02.582468+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-26T03:15:15.230946+00:00)
- Finalizado: 2026-10-26T03:15:18.147337+00:00
- Razón de la decisión: 272 de 381 entradas medibles (< 300 del registro): 109 no declaran site_ligand. Declarado sin decidir: entre 7 y 9 A cambia el estado por huecos en 8 de 272 (2,9 %); entre 5 y 7 A el de especies en 18 (6,6 %), sobre todo metales (10 a 6 A, 20 a 7 A). Control: 4JVB 6,12 A frente a 6,09 publicados; 36 metales coordinados frente a 35 del inventario.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

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
