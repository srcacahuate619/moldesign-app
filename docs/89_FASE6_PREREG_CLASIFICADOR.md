# Fase 6 — preregistro de validación del clasificador congelado

Fecha: 2026-09-25. Rama: `codex/audit-phase-6`, padre `c3aa4689c57087f20afd92bef0df678d4eff7cfb`. Este protocolo se fija antes de calcular métricas.

## Pregunta y límites

Se medirá el artefacto distribuido `classifier_binder.json` sobre los 328 complejos del holdout original, separando clústeres de proteína vistos y no vistos en el pool de 537. Las features son de poses cristalográficas del caché v4. Este experimento no mide poses generadas por Vina, ni generalización a proteínas remotamente homólogas bajo un umbral de secuencia más estricto.

## Entradas congeladas

| Entrada | SHA-256 |
|---|---|
| `data/pdbbind/INDEX_refined_data.2020.faseA_20260813_184439` | `1c52a9b7631cc11a31c6b3344ececa3de8a9087c86ab3e6c5a30dc69861de02d` |
| `rescoring/artifacts/split_config.json` | `bbc57126e2306e087dcddb76478a8cddfbd36fb7de3f350806b6366ee3534f6f` |
| `scripts/artifacts_science/FEP-03-PDBBIND/grupos.json` | `9756211324d16cdafb0dc6a4c473ff2bedeff8a38aa81e4f7b9144d687033568` |
| `rescoring/artifacts/classifier_binder.json` | `b83a936564036b196b53919c707250c441d49fbd1b9427b15f7ebe48850ea636` |
| `rescoring/artifacts/classifier_binder.metadata.json` | `e8b5de0feea62e3c571d0b1936ba6ac80f19709277f3ab9b2e1cfdfee3bb128b` |

El caché `feature_cache_v4` y los SDF/MOL2 de PDBBind son datos locales no versionados. El script generará un manifiesto de SHA-256 de cada entrada utilizada y el hash de la matriz resultante. No se sustituirán entradas faltantes con archivos de otra cohorte.

## Cohorte y método fijados

1. El índice Fase A determina exactamente 865 IDs; la intersección prevista es 537 pool y 328 holdout. El índice posterior de 1165 IDs queda excluido para evitar introducir 300 ejemplos añadidos después del entrenamiento.
2. `split_config.json` define holdout. `grupos.json` asigna un clúster a cada PDB ID; clúster visto significa presencia en los 537 del pool. Se espera 233 vistos y 95 no vistos. Toda discrepancia cancela el cálculo hasta diagnosticarla.
3. La matriz usa los 160 nombres y orden del metadata, `load_cached_3d_features`, `enrich_features_with_1d2d` y `build_feature_matrix` del repositorio, con el mismo umbral de exclusión por features faltantes. Se registran exclusiones y valores imputados. Se comprueba que la AUC global reproduce la cifra 0.8818 del metadata dentro de ±0.005; si no, se informa discrepancia y no se sustituye la métrica publicada.
4. El booster JSON permanece congelado; no se reentrena ni se ajusta calibrador con el holdout. Se calculan ROC-AUC, PR-AUC, Brier y ECE de diez intervalos de probabilidad iguales para todo el holdout y para los estratos visto/no visto. Se incluyen baselines de prevalencia y tasa de cobertura.
5. Los intervalos de AUC y Brier usan 2000 remuestreos de clúster proteico con semilla 42, percentiles 2.5/97.5; remuestreos con una sola clase se descartan y se informa cuántos. No se remuestrean complejos como si fueran independientes.

## Decisión predefinida

El peso XGB 0.75 no se considera validado con este experimento. Para darle cualquier peso positivo en el ranking de release se requiere además una evaluación separada sobre poses Vina con proteína disjunta, AUC con límite inferior de IC95 >0.5 y Brier menor que el baseline de prevalencia, con cobertura explícita. Si falta cualquiera de esas evidencias, el ranking provisional usa Vina 1.0 / XGB 0.0 y mantiene la probabilidad del clasificador sólo como evidencia exploratoria etiquetada.

## Salidas y custodia

El script escribirá matriz compacta, predicciones por complejo, métricas y un manifiesto SHA-256 bajo `D:\moldesign-audits\AUDIT_moldesign_ae4db6a\corrigendum\evidencia_fase6`. No se modifica ningún byte de `scripts/artifacts_science/`. La bitácora `fase6.md` consignará los hashes, el entorno y toda desviación de este preregistro.
