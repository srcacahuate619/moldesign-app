# RS-04-OOF-R1 — Corrigendum narrativo del NO_GO de RS-04-OOF

**Fecha:** 2026-08-16
**Tipo:** corrigendum EXCLUSIVAMENTE narrativo/estadístico (sin cambio de datos, sin re-evaluación)
**Padre:** RS-04-OOF — sellado NO_GO (commit `a8c9523`)
**Estado:** documentado y verificado; SIN `seal` y SIN `finish` (por protocolo del corrigendum).

## 1. Referencia al padre RS-04-OOF

- Manifiesto sellado: `scripts/artifacts_science/RS-04-OOF/manifest.json` (`"sealed": true`, `"status": "finished"`, decisión NO_GO).
- Commit del sello: `a8c9523` — "experiment(rs-04-oof): SELLADO NO_GO — strain sin poder de seleccion (9 assets)".
- `python scripts/experiment_manifest.py validate RS-04-OOF` sigue OK antes y después de este corrigendum.

## 2. Alcance: qué cambia y qué NO

**RS-04-OOF se PRESERVA INTACTO.** Ningún archivo sellado de `scripts/artifacts_science/RS-04-OOF/*`, `scripts/run_rs04_oof.py` ni `scripts/run_rs04_qc.py` fue modificado (solo LECTURA; verificado por el sello y por SHA-256).

Este corrigendum **NO** re-ejecuta cómputo, NO cambia datos, NO re-entrena y NO re-evalúa nada: es una enmienda narrativa y estadística sobre los resultados ya sellados. El sello histórico NO se toca. Lo único que se corrige es la REDACCIÓN DE LA GENERALIZACIÓN: se elimina una inferencia no soportada por la evidencia y se fija el alcance exacto del NO_GO.

## 3. Texto EXACTO del corrigendum (cita textual)

> "La feature strain MMFF94s produjo una reducción observada de 8 hits. El bootstrap primario por componentes excluyó cero [−14, −1], mientras que McNemar por complejo no alcanzó significancia (p=0.115). La mediana pareada de 0.000 Å indica ausencia de desplazamiento en la mediana, no equivalencia ni neutralidad. El NO_GO se limita a esta feature, este modelo y este contrato."

## 4. Corrección de generalización

- **INCORRECTO**: "el camino no está en features de física barata" (generalización global, no soportada por la evidencia).
- **CORRECTO**: "esta formulación de strain MMFF94s no aporta poder de selección".

**No refutadas** por este experimento (la evidencia de RS-04-OOF NO las toca): clashes, contactos direccionales, desolvación, strain condicionado por flexibilidad. Cada una de esas señales baratas queda abierta para su propia evaluación bajo su propio contrato.

## 5. Evidencia verificada (cifras del sellado, incorporadas tal cual)

| Ítem | Valor verificado |
|---|---|
| Caída por fold (baseline → aumentado) | +1, −2, −2, −1, −4 (4 folds en negativo; fold 4: −4) |
| Ganadores distintos entre brazos | 48/116 complejos |
| Discordancias McNemar | 20 (14 perdidos, 6 recuperados) |
| Estrato hard | 5/17 → 2/17 (**GRAVE**, pérdida > 2) |
| Bootstrap primario por componentes | 38 componentes, BCa ΔTop-1 **[−14, −1] — excluye cero** |
| McNemar por complejo | p = 0.115 (ns) — lectura de SENSIBILIDAD por complejo; **no invalida el agrupado primario** por componentes |
| Modelos baseline | los 5 reproducen EXACTAMENTE los SHA de RS-01B (`brazo_original`: `6e872ba2`, `2541609f`, `9584f7d9`, `8eab79bf`, `fabc39ec`) |
| Cuarentena / imputación / determinismo | correctos (cohortes prohibidas sin acceso; imputación con mediana del outer-train; salidas deterministas) |

## 6. Alcance del NO_GO (limitación explícita)

El NO_GO queda limitado a TRES dimensiones, ninguna de las cuales se extrapola:

1. **Esta feature**: strain MMFF94s con este contrato QA-5 (topología autoritativa, solo H optimizados, sin truncamiento).
2. **Este modelo**: v0.6+strain, XGBoost congelado (rank:pairwise, 52 árboles, max_depth 6, lr 0.05, seed 42).
3. **Este gate**: operacional RS-04 (Top-1 OOF ≥ 50/116, mediana pareada ≤ +0.1 Å, sin regresión grave por estrato).

**No refuta** otras señales baratas ni otras formulaciones de strain; tampoco refuta el uso futuro del strain en otros contextos (p. ej. MM-GBSA selectivo), que requeriría su propio contrato.

## 7. No-intrusión

- `validate RS-04-OOF`: **OK** (padre sellado intacto; hashes sellados verificados).
- `validate RS-04-OOF-R1`: **OK** (manifest de este corrigendum).
- Sin commits, sin `seal`, sin `finish`, sin `maintain`, sin pip, sin red, sin cómputo.

## 8. Archivos de RS-04-OOF-R1

- `manifest.json` — registro init del corrigendum (sin sellar, sin finish).
- `DESIGN.md` — este documento (cita textual §3, corrección de generalización §4, evidencia §5, alcance §6).
- `README.md` — resumen breve (3 líneas).
- Skeletons vacíos (`metrics.json`, `per_complex.jsonl`, `failures.jsonl`) — sin datos, sin re-evaluación (por protocolo).