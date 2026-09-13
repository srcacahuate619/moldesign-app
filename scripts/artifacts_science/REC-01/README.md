# REC-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los grids del catalogo de 387 targets contienen un subconjunto acotado y reproducible de casos desalineados respecto al sitio de union real; auditarlos separando HOLO (con ligando nativo como ground truth) de APO (sin ground truth directo) produce una lista de excepciones accionable sin re-docking.

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md seccion 7 (Cartera B, REC-01); reutiliza backend/scripts/audit_grid_hotspots.py y docs/35_GRID_APO_5TUN_PENDIENTE.md`

## Gate

G1 cobertura 100% de los 387 targets auditados (0 omitidos silenciosos); G2 clasificacion HOLO/APO deterministica y reproducible; G3 lista de excepciones con criterio numerico preregistrado; G4 determinismo bit-a-bit entre dos corridas; G5 cero escrituras en catalogo/DB/produccion

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `93541c9dc610d56014d19b73a2b72527d36abe41`, dirty=True

## Estado

- Creado: 2026-08-17T06:38:40.133632+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T06:39:39.270866+00:00)
- Finalizado: 2026-08-17T06:39:50.544226+00:00
- Razón de la decisión: Los cinco gates del instrumento pasan: G1 cobertura 387/387 sin omisiones ni fallos; G2 estrato deterministico en todos; G3 toda excepcion con codigo E1-E7 y valor disparador; G4 determinismo byte-identico en tres corridas incluida una tras reconstruir el directorio (sha 3f4da5ab); G5 catalogo y CSV con SHA-256 intacto. GO = la auditoria es valida y reproducible, NO que el catalogo este sano. Resultado: 57/387 targets con excepcion (14.7%), 25 con grid a mas de 15 A del ligando nativo y 23 con contencion de ligando 0.00 (la caja no contiene ni un atomo del sitio real) — ~4.75x el orden de magnitud de los '12 grids problematicos' que asumia el doc 49 seccion 7. HALLAZGO NEGATIVO DECLARADO: el caso testigo 5TUN del doc 35 NO fue capturado (contencion_hotspots 0.800 en la frontera exacta del umbral y ground truth debil por ser APO), pese a tener un hotspot 5.147 A fuera de la caja; siguiendo el preregistro el umbral NO se ajusta y la correccion pasa a REC-01-R1 con el codigo E8_HOTSPOT_FUERA_DE_CAJA, que capturaria 52 targets hoy invisibles (57 -> 109, 14.7% -> 28.2%). Sin docking, sin red, cero escrituras fuera del directorio del experimento.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 7 archivo(s) con SHA-256

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
