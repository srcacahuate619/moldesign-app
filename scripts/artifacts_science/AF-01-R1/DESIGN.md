# AF-01-R1 — Corrigendum del estratificado por receptor de AF-01

**Fecha:** 2026-08-16
**Tipo:** corrigendum (enmienda formal de un subanálisis)
**Padre:** AF-01 — réplica sellada de Fase A + auditoría de solapamiento por receptor
**Estado:** ejecutado y verificado; SIN `seal` y SIN `finish` (por protocolo del corrigendum).

## 1. Referencia al padre AF-01

- Manifiesto sellado: `scripts/artifacts_science/AF-01/manifest.json` (`"sealed": true`, `"status": "finished"`).
- Commits: `0593983` (contenido del experimento) y `67c4e30` (sello: "experiment(af-01): SELLADO GO — REPRODUCED_WITH_SCOPE_LIMITATION").
- Decisión registrada: **GO=REPRODUCED_WITH_SCOPE_LIMITATION** (Spearman 0.6094 reproducido con Δ 0.0, n=328).
- `python scripts/experiment_manifest.py validate AF-01` sigue OK antes y después de este corrigendum.

## 2. Alcance: qué cambia y qué NO

**AF-01 se PRESERVA INTACTO.** Ningún archivo sellado de `scripts/artifacts_science/AF-01/*` ni `scripts/af01_stratify.py` fue modificado (byte-idénticos; verificado por el sello y por SHA-256).

**Único alcance SUPERSEDED:** el subanálisis estratificado por receptor de AF-01 (estratos 179/55/94 y su lectura en `metrics.json`/`DESIGN.md` de AF-01). Este corrigendum lo reemplaza por los estratos corregidos 126/108/94.

**Permanece vigente (NO se re-ejecuta):** el Spearman global **0.6094** (CI95 [0.5282, 0.6791]) y toda la réplica de Fase A (entrenamiento, evaluación, determinismo). Este corrigendum no re-entrena, no re-evalúa y no re-dockea nada: reutiliza las predicciones congeladas del sellado AF-01 (`per_complex.jsonl`, 328 pares real/predicho).

## 3. El bug

En `af01_stratify.py` (AF-01), el estrato `receptor_seen_exact` se asignaba cuando el mejor solapamiento de k-meros era **`== 1.0`**:

```python
if best >= 1.0:
    estrato = "receptor_seen_exact"
```

El coeficiente de solapamiento |A ∩ B| / min(|A|, |B|) vale 1.0 **también cuando los k-meros de una cadena CORTA son subconjunto de los de una cadena larga** (subsecuencia), no solo cuando las secuencias son idénticas. Por ejemplo, una cadena de 60 residuos contenida como subsecuencia dentro de una cadena de 200 residuos produce solapamiento 1.0 con k=8 sin ser la misma secuencia.

Consecuencia: **53 complejos** del holdout fueron clasificados `receptor_seen_exact` siendo en realidad `receptor_near_identity`.

## 4. El fix

`receptor_seen_exact` pasa a definirse por **igualdad LITERAL de secuencia por par de cadenas** (`seq_dev == seq_holdout`), sin pasar por k-meros. El resto del método queda idéntico (SEQRES por cadena, k=8, umbral 0.90 por solapamiento, bootstrap 10k seed 42).

Además, el script R1 itera los k-meros de forma **ordenada** (`sorted(ks)`) para que la atribución de `best_pair` en empates de solapamiento sea determinista entre procesos (el set de k-meros sin ordenar dependía del hash de strings de Python). Esto no cambia ningún número científico.

## 5. Estratos corregidos (reproducidos)

| Estrato | n | Spearman | CI95 bootstrap |
|---|---|---|---|
| receptor_seen_exact | **126** | **0.7240** | [0.6254, 0.7915] |
| receptor_near_identity | **108** | **0.5135** | [0.3397, 0.6623] |
| receptor_unrelated | **94** | **0.5395** | [0.3761, 0.666] |

Suma 328. Reproducción **exacta** de los valores esperados por el maintainer (n idénticos; ρ y CI coinciden al 4º decimal).

Movimientos vs AF-01: 53 complejos `seen_exact → near_identity` (179→126, 55→108); unrelated intacto (94).

Conteos por la definición canónica **por cadena** (verificados, idénticos a AF-01 porque ya usaban igualdad literal): **61** grupos de secuencia exacta cruzados, **134/537** dev afectados, **126/328** holdout afectados, **1600** pares de complejos dev×holdout ≥0.90, **2370** pares de cadenas ≥0.90.

## 6. Reconciliación del pre-audit (definiciones distintas)

El pre-audit del maintainer (45 grupos / 106-537 / 96-328 / 1185 pares) era **CORRECTO bajo la definición heredada de FND-02**: receptor completo concatenado `A:…|B:…` (una secuencia por complejo), con "near" excluyendo los exactos. Los números por cadena (61 / 134-537 / 126-328 / 1600 / 2370) corresponden a la definición **por cadena**, que es la **canónica de ahora en adelante**.

No hubo error de cálculo: había DOS definiciones midiendo cosas distintas. El registro AF-01 usó la palabra "REFUTADO" para el pre-audit; queda **sustituida por "reconciliado — definiciones distintas"**.

## 7. Lectura científica

El corrigendum **REFUERZA** la conclusión de AF-01: el rendimiento es mayor cuando la cadena receptora se comparte exactamente —

**0.7240 (visto exacto) > 0.6094 (global) > 0.5395 (no relacionado)**

El contraste es ahora más limpio que con la clasificación original (0.7138): los 53 complejos con subsecuencias ya no contaminan el estrato exacto, y `near_identity` sube de 0.3626 a 0.5135 al recibirlos. La limitación de alcance del GO de AF-01 sigue vigente: el holdout scaffold-disjoint NO es receptor-disjoint.

## 8. Determinismo

Dos corridas completas del stratify R1 producen `per_complex.jsonl` byte-idéntico (SHA-256 `6132e75a…91861b` en ambas) y `metrics_estratos.json` byte-idéntico.

## 9. No-intrusión

- `validate AF-01`: **OK** (padre sellado intacto; hashes sellados verificados).
- Inputs congelados: `split_config.json` SHA-256 `5fc4e589…` e índice `1c52a9b7…`, idénticos a los `dataset_hashes` sellados de AF-01.
- `git status --porcelain`: solo `scripts/artifacts_science/AF-01-R1/` (+ untracked preexistente `docs/moldesign-ums-paper/`).
- Sin commits, sin `seal`, sin `finish`, sin `maintain`, sin pip, sin red, sin re-docking.

## 10. Archivos de AF-01-R1

- `manifest.json` — registro init del corrigendum (sin sellar, sin finish).
- `af01_stratify_r1.py` — copia corregida del stratify (fix de igualdad literal + k-meros ordenados).
- `metrics.json` — estratos corregidos, conteos canónicos, reconciliación del pre-audit, determinismo, no-intrusión.
- `per_complex.jsonl` — 328 registros con el estrato corregido.
- `metrics_estratos.json`, `estratos_report.txt` — salida directa del stratify R1.
- `failures.jsonl` — vacío (sin fallos).
- `README.md` — generado por `init` desde el manifest.
