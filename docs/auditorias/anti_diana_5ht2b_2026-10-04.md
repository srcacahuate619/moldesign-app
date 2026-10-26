# Anti-diana 5-HT2B — medida y adopción

Fecha local: 2026-10-04; consultas UTC 2026-10-05. Intérprete distribuido Python 3.11.9; datos propios `.tmp/tarea2/data`, MOLDESIGN_TESTING=1. Sin datos del investigador.

## Defecto de partida

La función del producto `services.docking.preparer.huecos_del_esqueleto`, sobre la cadena A de 4NC3 y la caja curada, devuelve THR197 → VAL199, C–N 4,79 Å, un ausente declarado en REMARK 465 (198), distancia a caja 1,250 Å y site_critical=true (margen del producto ≤6 Å). ECL2 conserva un corte real; no es sólo numeración.

## Búsqueda y protocolo

Consulta a [RCSB Search](https://search.rcsb.org/rcsbsearch/v2/query): accession P41595 / UniProt, X-RAY DIFFRACTION o ELECTRON MICROSCOPY, resolución ≤3,5 Å, orden ascendente. Devuelve 14 entradas; se excluye la 4NC3 ya medida y se toman las primeras diez. No se consultó UniProt ni se descargaron otros receptores.

El script existente `bowes44_validar_estructuras.validar` se usó sin cambios: se adaptó sólo `leer` a los archivos externos, y se sembró el raw en almacenamiento propio. Caja del centroide del ligando pesado, extensión máxima +8 Å, lado limitado 18–40 Å. Cadenas a ≤4,5 Å del ligando. Continuidad con la función del producto ANTES del recorte; si falla junto al sitio, no procede redocking. Prepare_target del producto, Meeko del runtime, ligando SDF ideal del CCD; Vina 1.2.7, exhaustiveness=16, seed=42, num_modes=9. Admitir exige centroide pose1 ≤4 Å. RMSD simétrico RDKit sin alinear y pose_reproducida ≤2 Å se informan, no deciden, como en las 38 históricas.

| PDB | Método/resolución Å | Ligando/cadenas | Huecos críticos | Centroide pose1 Å | RMSD pose1 Å | Pose reproducida | Resultado | Duración s |
|---|---|---|---:|---:|---:|---|---|---:|
| 4IB4 | X-RAY DIFFRACTION / 2.7 | ERM / A | 1 | — | — | — | no_procede | — |
| 7SRQ | ELECTRON MICROSCOPY / 2.7 | 7LD / R | 0 | 0.7 | 1.81 | True | sitio_confirmado | 17.09 |
| 5TVN | X-RAY DIFFRACTION / 2.9 | 7LD / A | 0 | 0.41 | 1.12 | True | sitio_confirmado | 16.58 |
| 7SRR | ELECTRON MICROSCOPY / 2.9 | 7LD / R | 0 | 0.85 | 1.31 | True | sitio_confirmado | 14.61 |
| 6DRY | X-RAY DIFFRACTION / 2.918 | H8D / A | 1 | — | — | — | no_procede | — |
| 9WNG | ELECTRON MICROSCOPY / 2.98 | A1EXY / R | 0 | 0.74 | 3.65 | False | sitio_confirmado | 37.25 |
| 5TUD | X-RAY DIFFRACTION / 3.0 | ERM / A | 0 | 0.21 | 0.96 | True | sitio_confirmado | 57.34 |
| 6DRX | X-RAY DIFFRACTION / 3.1 | H8G / A | 0 | 3.74 | 7.69 | False | sitio_confirmado | 20.73 |
| 6DRZ | X-RAY DIFFRACTION / 3.102 | H8J / A | 0 | 0.57 | 1.83 | True | sitio_confirmado | 23.62 |
| 9WQB | ELECTRON MICROSCOPY / 3.18 | A1EYD / A | 0 | 1.12 | 2.24 | False | sitio_confirmado | 11.26 |

Ocho pasan el criterio de sitio; 4IB4 y 6DRY no proceden por hueco crítico. Las poses de 9WNG, 6DRX y 9WQB no se reprodujeron bajo este protocolo aunque el centroide cumple. No se interpretan sus scores como seguridad.

## Decisión y límites

Se adopta **7SRQ** por la mejor resolución entre las admitidas (2,7 Å). La entidad 1/cadena R declara HTR2B, Homo sapiens/9606 y P41595 (SIFTS) en [RCSB Data](https://data.rcsb.org/rest/v1/core/polymer_entity/7SRQ/1). El ligando 7LD/LSD está en el bolsillo de ASP135; la adjudicación ortostérica es una inferencia de identidad, ligando y contactos del sitio, sin ensayos nuevos. Receptor genéticamente modificado: la cobertura de la secuencia de referencia es 0,64657, no una proteína nativa completa.

Redocking: centroide 0,70 Å, RMSD pose1 1,81 Å, mejor 1,61 Å en pose2. Caja [152.587,158.245,155.595], tamaño [18,18,18], R/7LD. El informe REAL de preparación también devuelve cero huecos críticos: sus dos huecos están a 19,60 y 22,31 Å. Trunca **22 cadenas laterales en total, cuatro a ≤6 Å de caja**: GLU R118 (5,33 Å), PHE R333 (4,752 Å), MET R360 y GLU R363 (0 Å). Se declaran en el API, selector bilingüe y disponibilidad; esta adopción resuelve el corte de esqueleto, no esas cadenas laterales.

Catálogo 380→381; 4NC3 se conserva, sin borrar estructuras/resultados históricos. El panel predeterminado pasa de 5VA1/4NC3 a 5VA1/7SRQ. El generador lee la nueva medida del manifiesto activo y escribe una tabla VIGENTE aparte: ae4db6a permanece histórico. Se tocaron seis archivos de datos: catálogo JSON/CSV, PDB gzip, disponibilidad, panel Bowes y nuevo manifiesto del catálogo. No requiere cambiar empaquetado. Hotspots: discover_pocket_from_pdb sobre R+7LD, top15 automático; no anotación experimental.

No verificado: afinidad experimental, toxicidad, actividad agonista/antagonista de otras moléculas, readiness FEP, densidad de todos los residuos ni equivalencia conformacional con 4NC3. Ningún RMSD redock demuestra estas cosas. No se construyó instalador.

## Archivos y procedencia

Descargas en `D:\moldesign-worktrees\sol-cierre-1-0-2-DATOS\rcsb`. `busqueda_P41595.json`, `candidatas.json`, `medidas_candidatas.json`, `validacion_candidatas.json`, `7SRQ_identidad.json` y CCD permiten rastrear esta medida. Para mmCIF se usa gemmi.make_pdb_string, primer modelo: sólo 9WNG/9WQB (PDB clásico da 404). Las coordenadas convertidas no son una segunda entrada.

| PDB | Fuente descargada | Fecha UTC | Bytes | SHA-256 |
|---|---|---|---:|---|
| 4IB4 | [RCSB](https://files.rcsb.org/download/4IB4.pdb) | 2026-10-05T02:41:24.961743+00:00 | 547236 | `56b68bbe5d88dfea42da6500109e863cc54bf5dc9e6ebc922fe0e5c44a83b01f` |
| 7SRQ | [RCSB](https://files.rcsb.org/download/7SRQ.pdb) | 2026-10-05T02:41:26.450914+00:00 | 342549 | `9eacb519d9f9fb2d419bad54457dc315ed7bf95c283ec675fab6ad3a1c9c14dc` |
| 5TVN | [RCSB](https://files.rcsb.org/download/5TVN.pdb) | 2026-10-05T02:41:29.192455+00:00 | 531036 | `afbf068ca193d4a9fe8d55fd94bb03949218d119cb8dc272860906af09bce870` |
| 7SRR | [RCSB](https://files.rcsb.org/download/7SRR.pdb) | 2026-10-05T02:41:30.337353+00:00 | 900801 | `f0c28c1479b92a3bf37cf08af48d0fc8b24c3198ba3307d1b2090ff7ac320948` |
| 6DRY | [RCSB](https://files.rcsb.org/download/6DRY.pdb) | 2026-10-05T02:41:33.366649+00:00 | 535248 | `11c90b1e7558dca29c902196522f34a07ecbd7a33c21581ef5319f6d6df64b41` |
| 9WNG | [RCSB](https://files.rcsb.org/download/9WNG.cif) | 2026-10-05T02:44:33.254578+00:00 | 608115 | `f5d0321b387af900941aa09add48dfc232aac8ba3de185c1b3c798efc959bfe1` |
| 5TUD | [RCSB](https://files.rcsb.org/download/5TUD.pdb) | 2026-10-05T02:41:35.915281+00:00 | 2106243 | `cb87345888922a8ec2032258a1a1e88fac88c13edf4bc2cc3610920d8dce75fd` |
| 6DRX | [RCSB](https://files.rcsb.org/download/6DRX.pdb) | 2026-10-05T02:41:37.788363+00:00 | 485190 | `7ff4fd7c12bbb67ae3c71c925f3173793a877c822d7e1fb1eb6ca2c7c7d0958a` |
| 6DRZ | [RCSB](https://files.rcsb.org/download/6DRZ.pdb) | 2026-10-05T02:41:40.876678+00:00 | 514998 | `23c997a3f38472a3024375d20a10556020eb7eddd0277638855f5fdb79f3971b` |
| 9WQB | [RCSB](https://files.rcsb.org/download/9WQB.cif) | 2026-10-05T02:46:52.833183+00:00 | 607911 | `0fab6eeec35e693866e7563831031aebb0835bbd6745bb7ba0019cd5ee8f58e8` |

Los SDF ideales de ERM/7LD/H8G/H8J/A1EXY/A1EYD quedan en el mismo directorio; sus URL, fecha, tamaño y SHA figuran en sdf_source de validacion_candidatas.json. El SHA del receptor PREPARADO y el del CCD de 7SRQ están en docs/catalog_versions/anti-diana-5ht2b-2026-10-05.json, separados del SHA del PDB RAW.

## Verificación de implementación

Cinco pruebas backend nuevas fallan sin la adopción (IDs, caja/cadenas, continuidad física, API sin metadata y generador). Dos pruebas frontend nuevas es/en fallan sin el aviso. Con cambios: 105 backend focalizadas, 21 frontend focalizadas; panel --check y sellos 167/0 pasan. Primera repetición detectó una serialización con lectura cp1252 de disponibilidad y dos expectativas viejas del catálogo; corregido leyendo UTF-8, regenerando por la función existente, derivando hotspots y declarando 381. Sin cambio de presupuesto i18n.
