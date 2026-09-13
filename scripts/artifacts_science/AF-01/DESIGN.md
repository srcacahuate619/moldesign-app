# AF-01 — Réplica sellada de Fase A + auditoría de solapamiento por receptor

**Fecha:** 2026-08-15
**Estado:** ejecutado y verificado; `seal` y `finish` PENDIENTES por autorización del maintainer (protocolo).
**Gate preregistrado:** GO=REPRODUCED_WITH_SCOPE_LIMITATION si Spearman reproduce 0.6094 (±0.005); NO_GO=P0 si no.

## 1. Resultado

**GO=REPRODUCED_WITH_SCOPE_LIMITATION (preliminar).**

| Métrica | Fase A (10-Ago-2026) | Réplica AF-01 | Δ |
|---|---|---|---|
| Spearman holdout (328) | 0.6094 | **0.6094** | 0.0000 |
| CI95 Spearman | [0.5282, 0.6791] | [0.5282, 0.6791] | 0 |
| Pearson | 0.6048 | 0.6048 | 0 |
| RMSE | 1.9755 | 1.9755 | 0 |
| MAE | 1.6749 | 1.6749 | 0 |
| CV val universal | 0.7731 (best_iter 162) | 0.7731 (best_iter 162) | 0 |
| Entrenamiento por familia | kinase 0.5868 / protease 0.5429 / SE 0.668 / gpcr,nr SKIP | idéntico | 0 |

Reproducción **exacta a 4 decimales** en las dos corridas independientes (workspace regenerado). Determinismo: Δ Spearman run1−run2 = 0.0.

**Alcance (limitación documentada):** la auditoría por receptor confirma que el holdout scaffold-disjoint NO es receptor-disjoint. El estrato `receptor_seen_exact` (n=179) alcanza Spearman 0.7138 > global 0.6094 > `receptor_unrelated` 0.5395: el solapamiento de receptor infla la métrica. 0.6094 debe citarse con esta limitación.

## 2. Protocolo ejecutado

### 2.1 Workspace sellado (sin tocar el repo de producción)

```
C:\Users\JOHANA~1\AppData\Local\Temp\opencode\af01_replica\        (run 1)
C:\Users\JOHANA~1\AppData\Local\Temp\opencode\af01_replica_run2\   (run 2, regenerado limpio)
  rescoring/                  ← git archive 86b95f0 rescoring (146 archivos)
  data/pdbbind/
    INDEX_refined_data.2020   ← copia del snapshot histórico (865)
    feature_cache_v4/         ← 865 archivos de cache (subset del cache de producción de 1165)
    {pid}/{pid}_ligand.sdf|mol2 ← 1730 archivos (entrada del enriquecimiento SMILES del propio código)
  assembly_info.json          ← hashes y verificaciones del ensamblado
```

Pasos:
1. `git archive --format=tar --output=... 86b95f0 rescoring` + `tar -x` (PowerShell corrompe el pipe binario; por eso archive a archivo). Sin checkout/worktree.
2. Copia del snapshot `INDEX_refined_data.2020.faseA_20260813_184439` como `INDEX_refined_data.2020` (ruta que el código de 86b95f0 espera). SHA-256 verificado: `1C52A9B7…` = 1C52A9B7631CC11A31C6B3344ECECA3DE8A9087C86AB3E6C5A30DC69861DE02D. 865 pids; 0 diferencias de pKi contra el índice de producción para esos pids.
3. `split_config.json` copiado del working tree (SHA-256 `5FC4E589…` = 5FC4E589B78311AE12EB1D5E51EEF51D39CC218C7A9C9D033880BDFB031FB3D5). El `frozen_test_set` (328) es idéntico al del commit 86b95f0 (verificado por comparación de conjuntos; el hash difiere solo por formato/contenido de `folds`). Se usa el congelado por el protocolo.
4. Cache: selección por pid del snapshot (match case-insensitive del nombre de archivo; hay nombres tipo `185L.json`). 865 archivos copiados.
5. **`cache_aggregate_sha256`** (dato ausente en el manifest histórico, ahora congelado): SHA-256 de cada archivo de cache, ordenados por nombre, concatenados y re-hasheados = `E4A1A62149639A6081F0DA109B02A1358CD50F57FDCF1CB080F2A2CE6553EB96` (idéntico en run 1 y run 2).
6. Seed 42: el código de 86b95f0 lo usa (`train_families.py` SEED=42; `MLTrainer(seed=42)`; `xgb seed=42`; `np.random.seed(42)` antes del shuffle). Sin discrepancia.

### 2.2 Entrenamiento

`python train_families.py` desde `rescoring/` del workspace (rutas relativas `../data/pdbbind/...` resueltas contra el workspace). Pool 537 = 865 − 328 (exclusión del frozen set por el propio código, "P0-SCI"). 0 complejos excluidos por gap de features. Salida: `model_a_{universal,kinase,protease,soluble_enzyme}.joblib`.

### 2.3 Evaluación

`evaluate_test_set.py` (del commit, con bootstrap 10k nativo, seed 42 del RNG de bootstrap) sobre los 328. **Ajustes de ruta documentados (cero cambios de comportamiento):**
- El commit guarda `.joblib` pero `evaluate_test_set.py` carga `artifacts/model_a_universal.json`; el histórico `convert_models.py` hardcodea `/app/artifacts/` y solo cubre `model_a`/`model_null`. Se escribió `af01_convert_models.py` en el workspace que replica su semántica para `model_a_universal` (y por familia) en la ruta local. El modelo convertido es byte-equivalente (joblib→booster.save_model).
- Nota documental: el docstring de `evaluate_test_set.py` dice "327 complejos"; el split congelado tiene 328 (la Fase A evaluó 328). Sin impacto en ejecución.
- Nota documental: `rescoring/deprecated/README.md` de 86b95f0 aún cita 0.8732 como válido (ver §5).

### 2.4 Auditoría de solapamiento por receptor (método FND-05/FND-02, implementación propia)

`scripts/af01_stratify.py` (stdlib puro; rdkit no necesario):
- SEQRES por cadena de `data/pdbbind/{pid}/{pid}_protein.pdb` (solo lectura; 865/865 con SEQRES, 0 fallback CA).
- k-mers k=8, coeficiente de solapamiento |A∩B|/min(|A|,|B|), máximo sobre pares de cadenas dev×holdout.
- Estratos: `receptor_seen_exact` (ov==1.0), `receptor_near_identity` (0.90≤ov<1.0), `receptor_unrelated` (ov<0.90).
- Predicciones del holdout reusando la lógica de carga/predicción del commit (`af01_predict.py` en workspace → `predictions_run.jsonl`).

Resultados: **61** grupos de secuencia exacta cruzados; **134/537** dev y **126/328** holdout afectados; **1600** pares de complejos dev×holdout ≥0.90; **2370** pares de cadenas ≥0.90. Estratos: seen_exact 179 (ρ=0.7138 [0.6324, 0.7758]), near_identity 55 (ρ=0.3626 [0.0754, 0.6127]), unrelated 94 (ρ=0.5395 [0.3761, 0.666]).

**Pre-audit del maintainer (45 / 106/537 / 96/328 / 1185): REFUTADO.** Se probaron 6+ variantes de definición (secuencias distintas, componentes conexas de complejos, una cadena por complejo, filtros de longitud, ATOM/CA, orientaciones de "pares") sin reproducir la cuádrupla; el detalle está en `metrics.json` y `metrics_estratos.json`. Los números que cuentan son los de esta implementación (la especificada en el protocolo AF-01).

### 2.5 Cifra 0.8732

Sigue INVALIDATED (leakage) en toda la documentación de producción; no se cita como válida aquí. **Anotación:** el árbol congelado de 86b95f0 la cita como válida en `rescoring/artifacts/README.md` y `rescoring/deprecated/README.md` (artefactos históricos previos a la propagación de INVALIDATED; la producción ya los corrigió).

## 3. Versiones reales de paquetes

Python 3.14.3 · numpy 2.4.4 · scipy 1.17.1 · xgboost 3.2.0 · joblib 1.4.2 · rdkit 2025.09.6 · sklearn 1.8.0.

## 4. No-intrusión

- SHA-256 de `data/pdbbind/INDEX_refined_data.2020` ANTES y DESPUÉS: `CA7702C5E6FD4E814281A3E65DDBDCF17BD62DF78E62DAEF6DAAA2106F70C4B6` (idéntico; el índice de 1165 entradas queda intacto).
- `git status --porcelain`: solo lo nuevo de `scripts/artifacts_science/AF-01/` y `scripts/af01_stratify.py` (+ untracked preexistente `docs/moldesign-ums-paper/`). `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` sigue limpio en el working tree (no lo tocó esta ejecución).
- `python scripts/experiment_manifest.py validate AF-01`: **OK**.
- `validate FND-05` y `validate FND-06`: **FAIL preexistente, no causado por AF-01** — ambos manifiestos sellaron `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` con SHA-256 `5b95ffd8…`, pero el commit `2ba4a1d` (`docs(af-01): reformulacion…`, el HEAD actual) modificó ese documento después del sellado de FND-05/FND-06 (hash actual `686c0a39…`). El drift proviene del commit del maintainer que preregistró AF-01; resolverlo (re-seal o aceptación documental) queda fuera del alcance de este experimento y se reporta para decisión del maintainer.
- Sin re-docking, sin re-extracción de features, sin modificaciones a `rescoring/artifacts` de producción, sin commits, sin `seal`/`finish`.

## 5. Archivos del registro AF-01

- `manifest.json` — registro único (init; sin sellar).
- `metrics.json` — reproducción, estratos, hashes de inputs, determinismo, refutación del pre-audit.
- `per_complex.jsonl` — 328 registros: pid, estrato_receptor, best_overlap, par dev ganador, real, predicho, error.
- `failures.jsonl` — vacío (sin fallos).
- `metrics_estratos.json`, `estratos_report.txt` — salida directa de `scripts/af01_stratify.py`.
- `training_report.json` — reporte de la réplica (formato del reporte Fase A de producción).
- `evaluation_report.json` — evaluación holdout de la réplica con bootstrap 10k.
- `af01_stratify.py` — copia del script de estratificación usado.
- `DESIGN.md` — este documento.
