# Retención de `MF-33-B-RET-R1` — qué está en git y qué no

El prerregistro de este experimento exige conservar la geometría cruda y los logs de cada
dock. **Se conservan**, y esa retención es lo que permitió diagnosticar en minutos el fallo
que tumbó su G0 y lo que después hizo posible medir `MF-33-PB`. Pero no todo entra en el
repositorio.

## Qué está versionado aquí

| | Tamaño | Qué es |
|---|---:|---|
| `manifest.json`, `metrics.json` | KB | El registro sellado |
| `per_complex.jsonl` | KB | Un registro por complejo |
| `per_pose/` (48 ficheros) | 3.3 MB | **Un registro por pose**, con `identity`, score, RMSD, y el `raw_sha256` de su PDBQT |
| `checkpoints/` (48 ficheros) | 3.5 MB | Estado por complejo, reusado verbatim por `MF-33-B-RET-R2` |

## Qué NO está versionado, y por qué se puede verificar igual

| | Tamaño | Dónde |
|---|---:|---|
| `raw_pdbqt/` (969 ficheros) | 35 MB | Disco local |
| `logs/` (1940 ficheros) | 4.7 MB | Disco local |

**No se pierde verificabilidad.** Cada registro de `per_pose/` lleva el campo `raw_sha256`
del fichero PDBQT del que salió, así que cualquiera puede comprobar que un PDBQT
concreto es el que produjo esa pose, sin que los 35 MB vivan en el historial de git.

Es la misma lógica con la que `MF-33-B-RET-R2` reusa los 47 checkpoints de aquí: su
`metrics.json` guarda el SHA-256 de cada uno, uno a uno.

## Lo que esto NO autoriza

Borrar `raw_pdbqt/` o `logs/`. La retención es una obligación del prerregistro, no una
conveniencia: sin ella, `MF-33-B-RET` original quedó forense e ilegible y `C10` estuvo
bloqueado durante semanas. Si hiciera falta liberar espacio, el camino es archivarlos
comprimidos con su hash, no eliminarlos.
