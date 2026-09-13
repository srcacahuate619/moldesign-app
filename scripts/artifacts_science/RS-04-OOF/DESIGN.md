# RS-04-OOF — Strain MMFF94s como feature sobre v0.6 (cross-fitting completo)

## Contexto

- **Plan**: CAMPANA-2-PLAN sellado (`41b7f09`, IT1/DECISIONS QA-5/QA-6).
- **QC previo**: RS-04-QC sellado (`5ffb256`) — mapeo 99.49%, cobertura 116/116, pesados 0.0 Å, determinismo, costes P95 dentro de gates.
- **Hipótesis**: "La feature de strain MMFF94s mejora Top-1 OOF de v0.6 sin degradar RMSD pareado".

## Protocolo ejecutado (contrato sellado)

- **Cross-fitting completo**: 5 folds sellados de RS-01B ([55,16,15,15,15] por 38 componentes combinadas; scaffold+receptor agrupados). Baseline v0.6 y modelo aumentado sobre EXACTAMENTE los mismos 116 complejos.
- **Features**: contrato A1 (variance/range por corrida; cluster_density/z/percentiles históricos) + strain MMFF94s: topología desde SDF sanitizado, mapeo heavy-atom biyectivo, AddHs(addCoords=True), solo H optimizados en la pose (pesados fijados, k=1e6 + restauración exacta), referencia aislada Nconfs=min(200, max(50, 10×rot_bonds)) ETKDGv3 seed 42 numThreads=1, optimización MMFF94s completa, mínimo energético. **Strain = E_pose_Hopt − E_isolated_min, SIN truncamiento** (negativo válido, QA-5).
- **Poses degeneradas** (14: 1kpm, 1nm6): imputación con la MEDIANA del outer-train de su fold (definida dentro del outer-train).
- **XGBoost CONGELADO**: rank:pairwise, n_estimators=52, max_depth 6, lr 0.05, subsample 0.8, seed 42, n_jobs 4, sin early stopping; eval_metric=auc (reporte). Mismos hiperparámetros en baseline y aumentado. Preprocesamiento/imputación/z/pct ajustados DENTRO del outer-train.
- **Cohortes prohibidas**: val40, D-RC-CONFIRM, poses_val, poses_test — 0 acceso (FORBIDDEN en runner; whitelist auditada).
- **Incertidumbre**: bootstrap por componentes (BCa donde ≥5 componentes; percentil 2.5–97.5 descriptivo en folds), seed 42; McNemar exacto bilateral (binomtest, sin ×2).
- **Costes**: cold-start P95, cacheado pose/complejo (patrón QC, 3 repeticiones).
- Determinismo: salidas sin timestamps, strain cacheado por ligando (ETKDG seed 42), seed 42.

## Resultados

### Global (OOF acumulado, 116 complejos)

| Métrica | Baseline v0.6 | Aumentado (+strain) |
|---|---|---|
| Top-1 hits | **47** (40.5%) | **39** (33.6%) |
| Δ Top-1 | — | **−8** |
| RMSD mediana ganador | 3.0305 Å | 2.8585 Å |
| Abstenciones | 61 (52.6%) | 55 (47.4%) |

- **Mediana pareada ΔRMSD**: 0.000 Å (PRIMARIA) — cumple ≤ +0.1 Å.
- Secundarias: diferencia de medianas −0.172 Å; suma pareada −23.79 Å; media pareada −0.205 Å.
- **McNemar exacto bilateral**: 14 perdidos vs 6 ganados (20 discordantes), **p = 0.115318** (ns).

### Por fold (hits baseline → aumentado)

| Fold | n | Baseline | Aumentado | Δ |
|---|---|---|---|---|
| 0 | 55 | 21 | 22 | +1 |
| 1 | 16 | 9 | 7 | −2 |
| 2 | 15 | 5 | 3 | −2 |
| 3 | 15 | 6 | 5 | −1 |
| 4 | 15 | 6 | 2 | **−4** |

### Estratos (preregistrado: grave = pérdida >2 o mediana pareada >0.1 Å)

- **hard: GRAVE** (pérdida > 2) → `es_grave: true`
- control: no grave → `es_grave: false`

### Costes (gates QA-6)

- Cold-start P95: 40.7 ms ≤ 5000 ms ✓
- Cacheado P95: 66.0 ms/pose ≤ 100 ms ✓
- Complejo P95: 1689 ms ≤ 3000 ms ✓

### Strain (cache por ligando, sin truncamiento)

- Mediana strain por outer-train: 104.8–118.7 kcal/mol (fold 1–0); 116 ligandos con referencia aislada.
- Resultados separados neutros vs ionizados disponibles en per_complex.jsonl (carga_formal por ligando).

## Veredicto del gate operacional: **FAIL**

| Criterio | Requerido | Observado | Cumple |
|---|---|---|---|
| Top-1 OOF | ≥ 50/116 | 39/116 | **NO** |
| Mediana pareada ΔRMSD | ≤ +0.1 Å | 0.000 Å | Sí |
| Cobertura química | ≥ 95% | 100% | Sí |
| Cold-start P95 | ≤ 5 s/ligando | 40.7 ms | Sí |
| Cacheado P95 pose/complejo | ≤ 100 ms / ≤ 3 s | 66 ms / 1.7 s | Sí |
| Sin regresión grave por estrato | hard y control | **hard GRAVE** | **NO** |

## Conclusión científica (narrativa oficial)

- La feature de strain MMFF94s **NO mejora el Top-1 OOF** de v0.6: 39 vs 47 (−8), McNemar p=0.115 (ns), con **regresión grave en el estrato hard** y pérdida concentrada en el fold 4 (−4).
- La mediana pareada de 0.000 Å indica que el strain no daña ni reordena la mayoría de las selecciones: es **coste-neutral en RMSD pero sin poder de selección** adicional en esta cohorte.
- **No hay GO de desarrollo para el brazo aumentado**; v0.6 sigue siendo el selector de producción.
- El strain queda documentado como feature explorada y rechazada por el gate preregistrado; no se descarta su uso futuro en otros contextos (p. ej. MM-GBSA selectivo), pero NO entra en la cascada con este contrato.
- Cohortes val40/D-RC-CONFIRM permanecen intactas para el claim confirmatorio futuro.

## Archivos

- `scripts/run_rs04_oof.py` — runner (por composición, importa run_rs04_qc para strain/bench).
- `metrics.json` — métricas globales + por fold + gates + bootstrap + McNemar.
- `per_complex.jsonl` (116) — fold, componente, ganador OOF, rmsd, Δ pareado, strain, estrato, ionizado.
- `failures.jsonl`, `benchmarks.json`, `strain_cache/referencias.jsonl`, `fold_models/` (10 modelos + sha).
- `manifest.json` — init (created, seeds 42).