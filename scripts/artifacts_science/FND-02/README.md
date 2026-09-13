# FND-02

Auditoría de duplicados ocultos y fuga en los splits de Ruta C
(`data/pose_selector_dataset`, split `scaffold_group_holdout_seed42`).
Registro experimental vía `scripts/experiment_manifest.py` (FND-01).

## Hipótesis

Los splits de Ruta C no contienen duplicados ocultos ni fuga train/val/test.

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` FND-02 +
`docs/42_RUTA_C_PROTOCOLO.md`. Análisis solo-lectura con
`scripts/audit_split_leakage.py` (stdlib + RDKit): deduplicación por PDB,
InChIKey/prefijo-14 del ligando (desde `data/pdbbind/{pid}/{pid}_ligand.sdf`),
scaffold Murcko recomputado, secuencia SEQRES del receptor (exacta y k-meros)
y distribución de fuentes por split.

## Gate

Cero fuga train-val-test por PDB, ligando, scaffold y fuente; duplicados
justificados.

## Resultado: NO_GO

El gate NO se cumple. Fuga real sin justificar:

1. **Ligando (InChIKey): 2 pares de complejos con ligando idéntico cruzan
   splits.** `1ft7` (val) ↔ `1lcp` (test); `1hmr` (train) ↔ `1hmt` (val).
   Causa raíz: ligandos acíclicos (sin anillos) tienen scaffold Murcko
   vacío; `build_pose_selector_dataset.scaffold_del_pid` trata la cadena
   vacía como fallo (`if scaf:`) y cae al fallback `pid:{pid}`, rompiendo
   la disyunción por grupo de scaffold.
2. **Secuencia del receptor: 85 pares de secuencia SEQRES idéntica cruzan
   splits** (14 grupos/familias, 57 de 203 complejos), p. ej. la familia
   de trombina repartida entre train/val/test (`1bn*`, `1bnt/1bnu/1bnw`,
   `1cnw/1cnx/1cny`, `1g1d/1g45/…`, `1if7/1if8`, …). Se suman 162 pares
   de homólogos cercanos (k-mer ≥0.9) cruzando splits. El split agrupa por
   scaffold del LIGANDO, no por receptor: el mismo receptor con ligandos
   distintos queda repartido entre particiones.
3. **Desequilibrio de fuente**: `ruta_a` aporta 187/553 poses (33.8%) al
   test (22.5% del test vs ~10.4% en train/val); `molflex` está
   sub-representado en test (33.6% vs 58.3% en train).

Lo que SÍ pasa: cero PDB en múltiples splits, cero scaffold Murcko
compartido entre splits (recomputado), cero poses duplicadas a nivel de
clave/línea/tupla, conteos 116/40/47 complejos y 2739/730/831 poses
verificados, SHA-256 de los JSONL y del holdout `test_pids` intactos.

## Recomendaciones

- Corregir el fallback de scaffold para ligandos acíclicos (grupo explícito
  `acyclic` o SMILES canónico sin anillos como agrupador).
- Para D-RC-CONFIRM (FND-05): reagrupar por identidad de receptor
  (secuencia) antes de congelar el holdout; las 14 familias exactas deben
  caer completas en una sola partición.
- Documentar el desequilibrio de fuente como riesgo para comparaciones
  inter-split (FND-06).

## Archivos

- `manifest.json`: registro único del experimento (sellado, SHA-256 del dataset).
- `metrics.json`: métricas agregadas de la auditoría.
- `per_complex.jsonl`: identidad química/estructural por complejo auditado.
- `failures.jsonl`: 114 hallazgos (27 duplicados de ligando, 2 fugas de ligando, 85 fugas de secuencia exacta).
- `README.md`: este archivo.
