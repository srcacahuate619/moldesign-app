# REC-01-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El criterio de excepcion de REC-01 tiene un falso negativo estructural: la contencion por FRACCION no detecta desalineamientos concentrados en pocos hotspots. Un codigo E8_HOTSPOT_FUERA_DE_CAJA definido como margen_min_hotspots < 0 cierra ese hueco y captura el caso testigo 5TUN del doc 35. CORRIGENDUM: el desenlace numerico ya se conoce y esta declarado en REC-01/LECTURA.md seccion 4; no es una prueba ciega.

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md seccion 7 (Cartera B, REC-01); corrigendum del sello REC-01 (GO 2026-08-17); consume por hash el per_complex.jsonl sellado de REC-01`

## Gate

G1 integridad de entrada: el per_complex.jsonl de REC-01 coincide con su SHA-256 sellado 3f4da5ab; G2 prueba de aceptacion: 5TUN queda capturado por E8; G3 conservacion: ningun target pierde una excepcion que REC-01 le habia asignado; G4 severidad asignada a los 387 con criterio preregistrado y ordenada por accionabilidad; G5 determinismo byte-a-byte; G6 cero escrituras fuera del directorio REC-01-R1 (REC-01 permanece intacto)

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `93541c9dc610d56014d19b73a2b72527d36abe41`, dirty=True

## Estado

- Creado: 2026-08-17T06:45:18.483626+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T06:49:05.848922+00:00)
- Finalizado: 2026-08-17T06:49:20.030488+00:00
- Razón de la decisión: Los seis gates pasan: G1 entrada sellada de REC-01 integra (sha 3f4da5ab); G2 prueba de aceptacion superada — 5TUN capturado por E8 con severidad S4_LEVE y margen -5.147 A; G3 conservacion sin perdidas y codigos E1-E7 reproducidos exactamente; G4 severidad asignada a los 387 sin nulos; G5 determinismo byte-identico; G6 REC-01 intacto (validate OK). RESULTADO PRINCIPAL, NO PREVISTO: la comprobacion de expectativa preregistrada detecto un ERROR DE NARRATIVA en REC-01/LECTURA.md seccion 2. Declaraba 'en 23 targets la caja no contiene ni un solo atomo del ligando'; el 23 es el conteo de E2_LIGANDO_RECORTADO (contencion < 1.0). La cifra correcta de contencion == 0.00 es 11; los otros 12 tienen contencion parcial 0.16-0.91. El dato sellado de REC-01 es correcto (E2 siempre significo <1.0); el error estuvo solo en la prosa que lo interpreto. REC-01 permanece sellado sin modificar y este corrigendum es el registro oficial de la correccion (patron RS-01A -> RS-01A-R1); todo consumo posterior debe citar 11. Corrigendum del criterio: E8_HOTSPOT_FUERA_DE_CAJA (margen_min_hotspots < 0, geometria exacta sin umbral calibrable) eleva las excepciones de 57 (14.7%) a 109 (28.2%), +52 targets. Triaje preregistrado: S1_CRITICO 11, S2_GRAVE 14, S3_MODERADO 9, S4_LEVE 69, S5_METADATO 6, S0 278. La cohorte S1+S2 (25 targets) es la entrada natural de REC-03. NO es prueba ciega: el desenlace de E8 ya estaba declarado en REC-01/LECTURA.md seccion 4. La escala de severidad es hipotesis de accionabilidad, no medicion de impacto; probarla exige docking pareado en REC-03.
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
