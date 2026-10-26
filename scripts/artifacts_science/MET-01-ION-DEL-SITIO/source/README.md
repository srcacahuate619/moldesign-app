# Productor MET-01

`python scripts/medir_met01.py <comando>` ejecuta estos bytes protegidos por
el atributo existente `scripts/artifacts_science/** -text`. No se modifica
`.gitattributes`. `met01.py` envuelve sin editar el método de
`scripts/calibracion_receptor.py`, importado de la base f0e64086.

`product_sources/` conserva copias de los tres soportes originales tal como
se leyeron durante el prerregistro. Es trazabilidad, no una reimplementación.
El producto ejecutado sigue siendo backend/ de f0e64086; el guardián del arnés
exige que no difiera de esa base. El lanzador usa las funciones originales de QA.

Prerregistro completo: `entrada/protocolo.json`; CCD y preparados versionados.
El runtime compartido no se versiona, está declarado en
`scripts/sellos_no_distribuidos.json`, y sus binarios se sellan con rutas del
repositorio gracias a los montajes autorizados. Se conservan hashes por pose.

`merge` une sólo la fase confirmatoria; `analyze` lee per_complex.jsonl,
`selftest` demuestra sensibilidad del analizador y `verify` reconstruye cada
fila exitosa desde su crudo y comprueba la determinación de metrics.json.
El piloto y los privados nunca entran en las métricas confirmatorias.
