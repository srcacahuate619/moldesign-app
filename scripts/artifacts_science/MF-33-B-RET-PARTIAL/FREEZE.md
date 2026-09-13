# MF-33-B-RET-PARTIAL — congelación forense

## Estado

Este experimento **no es una repetición ni un análisis científico**. Es una copia
inmutable del único output parcial de `MF-33-B-RET`, preservada antes de iniciar
`MF-33-B-RET-R1`.

- Origen sin modificar: `scripts/artifacts_science/MF-33-B-RET/per_complex.jsonl`
- Snapshot: `snapshot/per_complex.jsonl`
- SHA-256 de ambos en el momento de la congelación:
  `e49f45cceb7fa015d344ef7343a2596ecf1dfad89745af77223c9588169c7d43`
- Registros: 43 de los 48 complejos de la cohorte MF-33.
- PIDs ausentes: `1hpx`, `1jq8`, `1mmq`, `1nm6`, `1nw5`.

## Por qué no se interpreta

El runner histórico escribía agregados por complejo y borraba los PDBQT. Además
sobrescribía el archivo de salida al relanzarse. Por tanto el snapshot no contiene
los pares score/RMSD por pose ni la geometría cruda que exige el contrato
`MF-33-B-RET-PRE`; los cinco ausentes tampoco son una muestra aleatoria. Calcular
un veredicto o completar solo los cinco alteraría la lectura preregistrada.

La decisión obligatoria de este registro es `INCONCLUSIVE`. Cualquier resultado
debe venir exclusivamente de `MF-33-B-RET-R1`, con reanudación por dock y
retención de PDBQT, logs, per-pose y per-complex.
