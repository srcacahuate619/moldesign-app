# RS-03-PARAM-B

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La referencia AM1-BCC estratificada (antechamber+sqm) caracteriza descriptivamente las cargas NAGL nativas de RS-03-PARAM-A sobre los 116 ligandos train, sin ser selector ni criterio de aceptacion

## Protocolo

Referencia: `RS-03-PARAM-B-PRE sellado (147abb1) que refina el PRE maestro RS-03-PARAM-PRE (7dfa3b8); contenedor Ubuntu moldesign-science en 192.168.1.64, 3 shards disjuntos + 1 shard de reintento`

## Gate

Completitud del reporte (no aceptacion/rechazo de NAGL): cohorte de A, conservacion de carga reportada, |q_NAGL - q_AM1BCC| por atomo sobre mapeo biyectivo verificado, carga molecular, dipolo, estabilidad de energias, todo estratificado por los 6 estratos; prohibido concluir sobre NAGL desde B

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `9e92df43820d62fddea9aecb0995d46abc4c36a1`, dirty=True

## Estado

- Creado: 2026-08-17T18:42:29.612818+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T18:42:52.943485+00:00)
- Finalizado: 2026-08-17T18:43:08.037722+00:00
- Razón de la decisión: Gate de completitud del reporte cumplido (B es caracterizacion, no selector): cobertura 115/116 (99.14%) de la cohorte de A; mapeo biyectivo VERIFICADO elemento a elemento y por coordenadas en 115/115 con max|dr|=0.0005 A, no asumido por indice como en el runner anterior; conservacion de carga de AM1-BCC max |sum q - formal| = 0.006 e; energia finita y serializable con Sage 2.2.1 en 115/115 para ambos juegos de cargas; dipolo reportado para NAGL y AM1-BCC; todo estratificado por los 6 estratos del PRE maestro. Diferencia NAGL vs AM1-BCC: |dq| por atomo medio 0.0142 e, mediana 0.0118 e, maximo 0.4255 e, con 13 de 115 ligandos por encima de 0.2 e en algun atomo; |dE| de punto unico mediana 24.3 kJ/mol y maxima 216.4 kJ/mol, que es del orden de lo que un rescoring pretende resolver. Estratos: azufre/fosforo divergen mas (0.0168 vs 0.0125 e) y contienen el maximo global; la divergencia crece con tamano y flexibilidad (fragmentos 0.0107 -> drug-like 0.0155; <5 rotables 0.0113 -> >10 rotables 0.0157). El unico fallo, 1nw5, es quimico real (sqm no converge) y no de presupuesto. Los 4 timeouts de la primera fusion eran artefacto de la contencion de 3 shards en 4 cores y se recuperaron en solitario con 2400 s. PROHIBIDO concluir sobre NAGL desde B: la decision es de RS-03-PARAM agregando A y B contra el contrato del PRE maestro.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 19 archivo(s) con SHA-256

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
