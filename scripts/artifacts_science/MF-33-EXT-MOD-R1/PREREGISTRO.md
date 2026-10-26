# MF-33-EXT-MOD-R1 — preregistro (2026-10-22, antes de calcular)

**Origen:** SCI-B-131. El BLOQUE 3 de `MF-33-EXT-MOD-PRE` es su regla de decisión: un predictor sólo
es candidato a política adaptativa si su Spearman con `beneficio_ensemble` sobrevive a
Benjamini-Hochberg (q = 0.05) en los **68 complejos fuera de la cohorte de 48**. El productor
tomó `torsdof`, `rot_bonds`, `diversidad` y `n_heavy` sólo de MF-33-DOSIS, que cubre los 48, así
que en los 68 los cuatro quedaron vacíos (n = 0) y el bloque no se ejecutó. MF-33-EXT-MOD está
sellado y no se toca: esto es la medida que faltaba.

## Qué se calcula

Para los 68 (filas de `MF-33-EXT-MOD/per_complex.jsonl` con `en_cohorte_48 = false`), con las
**funciones del productor sellado de MF-33-DOSIS**, importadas sin modificarlas
(`analisis_mf33dosis_cuando_hace_falta_ensemble.py`): `torsdof` del `conf0.flex.pdbqt`,
`rot_bonds` y `n_heavy` del SDF del cristal (RDKit, `molflex.leer_ligando`), y `diversidad`
(RMSD medio por pares, Kabsch, hasta 30 confórmeros `conf*.flex.pdbqt`). Material:
`data/molflex_train_v2/` y `data/pdbbind/` (no viajan en el repo; se registran sus SHA-256).
`n_conformeros` y `beneficio_ensemble` se leen de MF-33-EXT-MOD sin recalcular.

La correlación usa `_correlar` del productor sellado de MF-33-EXT-MOD, también importada: los
cinco predictores prospectivos, Spearman, BH q = 0.05 sobre los cinco, mínimo 8 pares y 3 valores
distintos. `n_conformeros` entra porque el PRE lo fija, pero se declara confundido: SINGLE usa un
confórmero y ENSEMBLE K, así que su relación con el beneficio no es un descriptor previo al
cálculo. Se informa también el ρ detectable al 80 % con n = 68 (`_rho_detectable`).

## Puertas

| | Criterio |
|---|---|
| G0 reproducción | Las mismas funciones sobre los 48 de la cohorte dan exactamente los valores de MF-33-DOSIS (`torsdof`, `rot_bonds`, `n_heavy` iguales; `diversidad` a ≤ 1e-4) |
| G1 completitud | Los cuatro predictores no nulos en ≥ 65 de 68 (95 %) |

Control, no puerta: la misma correlación con `beneficio_ensemble` barajado (semilla 42), que se
espera sin supervivientes.

## Decisión

- **INCONCLUSIVE** si falla G0 o G1.
- **GO** si al menos uno de los **cuatro** descriptores (`torsdof`, `rot_bonds`, `diversidad`,
  `n_heavy`) sobrevive a BH en los 68: es *candidato* a política adaptativa según el PRE, no una
  política validada.
- **NO_GO** si ninguno de los cuatro sobrevive: el BLOQUE 3 no da un predictor estático
  utilizable. Si `n_conformeros` sobrevive solo, se informa y no cuenta, por la confusión.

**No dice:** nada sobre los bloques 1, 2 y 4 ni sobre la cantidad primaria de MF-33-EXT; no
reabre el escenario de MF-33-EXT-MOD. Sin docking. CPU local, minutos.
