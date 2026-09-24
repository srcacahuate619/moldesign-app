# RS-03-PARAM-A

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

OpenFF Sage 2.2.1 + NAGL openff-gnn-am1bcc-1.0.0 (produccion SHA 7981e7f5) parametriza los 116 ligandos train con cobertura >=95%, determinismo <=1e-6 y cero fallback

## Protocolo

Referencia: `RS-03-PARAM-A-PRE sellado (147abb1) refina PRE maestro (7dfa3b8) QA-2; contenedor Ubuntu moldesign-science, cliente moldesign_client.py`

## Gate

11 gates G1-G11: cobertura >=95% global y >=90% por estrato; |sum q - formal| <= 1e-4; determinismo <=1e-6; cero fallback; cero val40/test/CONFIRM; SHA registrados

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `0cf8ec5c283148f8a5c0918e4999111816ef85bc`, dirty=True

## Estado

- Creado: 2026-08-17T03:37:27+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T04:05:45.996771+00:00)
- Finalizado: 2026-08-17T04:05:46.357344+00:00
- Razón de la decisión: 11 gates G1-G11 cumplidos: 116/116 ligandos parametrizados, cobertura global 100% y 100% en los 6 estratos, determinismo 2.78e-17 (<=1e-6), |sum q - formal| max 1e-15 (<=1e-4), mapeo biyectivo + atom_order_hash, cero fallback silencioso, energia finita + serializable 100%, modelo NAGL 1.0.0 produccion SHA 7981e7f5 registrado, Sage 2.2.1. Reemplaza el tipado heuristico de molchamb_v2.py:65 como base de cargas. Siguiente: RS-03-PARAM-B (AM1-BCC estratificado) y luego RS-03-PARAM (agregacion).
- Hashes de assets: 8 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-09-24T04:04:36.718309+00:00: `scripts/run_rs03_param_a.py` `c01f6684→214f90ea` — Activo cambiado despues del sello: scripts/run_rs03_param_a.py es un modulo o documento vivo que se sello como asset (regla 4 de las reglas de metodo: no sellar un modulo de produccion vivo). El resultado sellado se produjo con la version anterior, cuyo hash queda en previous_hash; la version actual es la del commit b072e8f. Se registra el 2026-09-23, antes de la auditoria externa, para que validar_sellos.py distinga este cambio declarado de una corrupcion. No cambia ninguna cifra ni decision del experimento. (commit b072e8f)
- 2026-09-24T04:04:37.423926+00:00: `scripts/remote_docker_runner.py` `9aac660b→552ff499` — Activo cambiado despues del sello: scripts/remote_docker_runner.py es un modulo o documento vivo que se sello como asset (regla 4 de las reglas de metodo: no sellar un modulo de produccion vivo). El resultado sellado se produjo con la version anterior, cuyo hash queda en previous_hash; la version actual es la del commit b072e8f. Se registra el 2026-09-23, antes de la auditoria externa, para que validar_sellos.py distinga este cambio declarado de una corrupcion. No cambia ninguna cifra ni decision del experimento. (commit b072e8f)

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
