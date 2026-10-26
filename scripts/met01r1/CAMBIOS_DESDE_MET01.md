# MET-01-R1: cambios del productor respecto de MET-01

`met01r1.py` se genera desde `scripts/artifacts_science/MET-01-ION-DEL-SITIO/source/met01.py`
con estas sustituciones, cada una con su número exacto de apariciones comprobado.
`capsula.mjs` es una copia byte a byte del de MET-01.

| Motivo | Apariciones |
|---|---:|
| docstring | 1 |
| experiment folder | 1 |
| pre-seal folder | 1 |
| product under measurement: includes a27ded64 (whitelist kept) | 1 |
| reuse MET-01 CCD bytes | 1 |
| variant names | 1 |
| job names | 1 |
| case ids | 1 |
| capsule path | 1 |
| metrics id | 1 |
| protocol id | 1 |
| paper path | 1 |
| audit path | 1 |

No cambia ninguna regla científica: población, configuración, semillas, gate, RMSD,
validez física, potencia y regla de parada son las de MET-01.

## Después de los resultados: sólo el texto del informe (2026-10-21)

Al generar el paper con las 380 corridas, el texto conservaba restos de la plantilla de MET-01:
la entradilla y la pregunta decían «MET-01», el apartado de reproducción citaba la auditoría,
la carpeta y el script de MET-01, la auditoría se titulaba con la fecha de MET-01 y una frase
imprimía «Faltan controles completos: True». Se corrigieron en `report()`, y en ninguna otra
función: el análisis, el gate y las métricas no cambian (`verificacion.json` se regeneró igual).
