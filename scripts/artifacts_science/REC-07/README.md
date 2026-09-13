# REC-07

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El grid APO de 5TUN puede corregirse sin regresion. La correccion propuesta en doc 35 (G_MP de MolPocket) contiene los 15 hotspots pero se ALEJA del nucleofilo catalitico Cys25; una caja adaptativa minima que contenga los 15 hotspots mas la triada catalitica (G_ADAPT) los contiene todos, esta mas cerca de Cys25 que ambas alternativas y ocupa menos volumen que G_MP. Un control de docking con E64c (inhibidor canonico de cisteina-proteasas, extraido del homologo 1ITO) debe situar la pose top-1 en contacto con Cys25 SG bajo el grid aceptado.

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md seccion 7 (Cartera B, REC-07); docs/35_GRID_APO_5TUN_PENDIENTE.md; consume la evidencia sellada de REC-01-R1 (5TUN con E8, margen -5.147 A)`

## Gate

G1 contencion: el grid aceptado contiene 15/15 hotspots y 3/3 residuos de la triada catalitica; G2 ancla: no mas lejos de Cys25 SG que el grid actual del catalogo; G3 validez de docking: rc=0, archivo no vacio, 1<=modos<=9, scores finitos de REMARK VINA RESULT, geometria parseable en todas las corridas; G4 contacto catalitico: pose top-1 de E64c a <=5.0 A de Cys25 SG en al menos 3 de 5 semillas; G5 no regresion frente a G_DB en la metrica de contacto; G6 determinismo por semilla; G7 solo lectura, cero escrituras en catalogo o DB

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `93541c9dc610d56014d19b73a2b72527d36abe41`, dirty=True

## Estado

- Creado: 2026-08-17T07:08:26.933333+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-17T16:30:42.285689+00:00)
- Finalizado: 2026-08-17T16:30:55.877400+00:00
- Razón de la decisión: 6 de 7 gates pasan pero G5 (no regresion) falla: el grid recomendado G_ADAPT logra contacto catalitico en 4 de 5 semillas frente a 5 de 5 del grid del catalogo G_DB, y la regla congelada exige los siete gates para un GO. No se recomienda cambio de grid para 5TUN. El hallazgo sustantivo es que el defecto geometrico detectado por la auditoria (3 de 15 hotspots recortados, margen_min -5.147 A) NO se traduce en fallo de docking: G_DB pone el ligando E64c en contacto con Cys25 SG en las 5 semillas, mediana 0.773 A. El unico fallo de contacto de la tabla es de G_ADAPT en la semilla 45 (top-1 a 12.89 A) y es fluctuacion de muestreo, no del grid: el mejor de los 9 modos de esa misma corrida queda a 2.09 A. G_MP tiene el mejor score mediano (-6.182 vs -5.095) y contacto 5/5, pero el prerregistro seccion 6 prohibe usar el score para elegir el grid. G6 determinismo PASS: misma semilla reproduce score y distancia identicos en los 3 brazos. Incidencia registrada: la primera ejecucion paso el PDB crudo a Meeko, conservo las 387 aguas y devolvio scores positivos (+23 a +33) con 1-5 modos; G3 la marco FAIL, se corrigio la preparacion y se repitio la tanda completa sin tocar ningun criterio de decision. Consecuencia para el programa: una excepcion geometrica del catalogo no implica un fallo de docking, y la cola de 57 targets de REC-01 es una lista a verificar, no una lista de targets rotos.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
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
