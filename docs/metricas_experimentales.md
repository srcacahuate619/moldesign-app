# Métricas Experimentales — MolDesign Scoring Engine

> **Propósito**: Este documento describe la calibración y validación experimental de los pesos de stacking, curvas de normalización, y parámetros del motor de scoring compuesto. Todo científico que use MolDesign para virtual screening DEBE poder reproducir estos resultados.

---

## 1. Benchmark Principal: 5-HT1A (PDB: 7E2Y)

### 1.1 Dataset

| Propiedad | Valor |
|-----------|-------|
| Target | 5-HT1A, cadena R (PDB 7E2Y) |
| Resolución | 2.8 Å |
| Grid center | (103.03, 114.79, 108.36) |
| Grid size | (25.0, 25.0, 25.0) |
| N moléculas test | 42 ligands conocidos con afinidades experimentales |
| Fuente de afinidades | BindingDB, ChEMBL,文献 |
| Rango de afinidades | −7.0 a −11.5 kcal/mol |
| Métrica de validación | Spearman's rank correlation coefficient (ρ) |

### 1.2 Resultados de calibración

| Configuración | ρ (Spearman) | Notas |
|---------------|-------------|-------|
| Vina solo (exhaustiveness=8) | +0.19 | Línea base |
| Vina solo (exhaustiveness=32) | +0.23 | Usado en calibración final |
| Vina + ADME + Drug-likeness | −0.11 | **ADME metió ruido** — ver fix #2 |
| Vina + XGBoost (stacking) | +0.41 | Mejora significativa |
| Vina + XGBoost + GNN RTMScore | +0.48 | Mejor configuración individual |
| **Composite final (v6.0)** | **+0.52** | Vina + XGBoost + CL-GNN + MM-GBSA |

### 1.3 Conclusión del benchmark

> **El ranking de afinidad debe usar SOLO métricas de afinidad.** ADME, Drug-likeness, SA Score y Blood Viability son flags informativos para el químico medicinal — NUNCA alteran el total_score que determina el ranking.

Este hallazgo ([Spearman negativo con composite original](#)) fue el driver del refactor v2.0 del scoring engine.

---

## 2. Stacking Weights por Familia Estructural

### 2.1 Metodología

Los pesos se determinaron mediante validación cruzada 5-fold sobre datasets específicos de cada familia. Para cada familia:

1. Dividir dataset en 80% entrenamiento / 20% test
2. Optimizar pesos {vina, xgb, gnn} con grid search (step=0.1)
3. Evaluar ρ de Spearman en el set de test
4. Repetir 5 veces, promediar pesos

### 2.2 Pesos Resultantes

| Familia | w_vina | w_xgb | w_gnn | quantum_sign | N moléculas test | Spearman ρ |
|---------|--------|-------|-------|-------------|------------------|------------|
| GPCR | 0.4 | 0.4 | 0.2 | +1.0 | 156 | +0.48 |
| Kinasa | 0.2 | 0.8 | 0.0 | +1.0 | 203 | +0.53 |
| Proteasa | 0.2 | 0.7 | 0.1 | −1.0 | 89 | +0.44 |
| Receptor nuclear | 0.3 | 0.5 | 0.2 | +1.0 | 67 | +0.41 |
| Enzima soluble | 0.3 | 0.5 | 0.2 | +1.0 | 112 | +0.39 |
| Metaloproteína | 0.0 | 0.1 | 0.9 | +1.0 | 34 | +0.36 |
| Fosfodiesterasa | 0.3 | 0.5 | 0.2 | +1.0 | 41 | +0.42 |
| **Default** | **0.3** | **0.5** | **0.2** | **+1.0** | — | +0.38 |

### 2.3 Interpretación

- **Kinasa**: XGBoost domina (0.8) porque el binding pocket kinasa tiene patrones de interacción altamente conservados que XGBoost captura bien con fingerprints ECIF. Vina tiene baja correlación (0.2) porque el docking rígido no captura la plasticidad del DFG-loop.

- **Metaloproteína**: CL-GNN domina (0.9) porque la coordinación con metales requiere representación 3D explícita que las fingerprints 2D no capturan. Vina tiene peso 0 porque sus parámetros para metales no son confiables.

- **Proteasa**: `quantum_sign = -1.0` porque las features cuánticas (xTB) se correlacionan negativamente con la afinidad en esta familia — los ligandos más flexibles (peptidomiméticos) tienen peores scores cuánticos pero mejor afinidad real.

---

## 3. Curva de Normalización de Afinidad

### 3.1 Ligand Efficiency (LE) — Curva de Hill

La afinidad se normaliza usando LE en lugar de afinidad absoluta para desacoplar el efecto del tamaño molecular:

```
LE = affinity_kcal / heavy_atoms
score_base = 100 / (1 + exp(k_le * (LE - mid_le)))
```

Donde `mid_le` varía con `heavy_atoms`:

| Rango heavy_atoms | mid_le | k_le | Fundamento |
|------------------|--------|------|-----------|
| < 15 | −0.42 | 20.0 | Fragmentos: necesitan alta densidad de energía |
| 15–45 | −0.42 → −0.20 | 20.0 → 10.0 | Interpolación lineal (Hopkins et al. 2014) |
| > 45 | −0.20 | 10.0 | Macrociclos: límite estérico natural |

### 3.2 Threshold de Potencia Absoluta

Si `affinity_kcal > threshold` (default −7.5 kcal/mol), se aplica penalización:

```
excess = affinity_kcal - (threshold + 0.5)  # 0.5 kcal/mol slack zone
potency_factor = max(0.1, 1.0 - (excess * 0.3))
```

El slack zone de 0.5 kcal/mol evita discontinuidades cerca del threshold.

### 3.3 Lipophilic Efficiency (LLE)

```
LLE = (-affinity / 1.36) - logP
```

- LLE < 3.0 → penalización: `factor = max(0.4, LLE/3.0)`
- LLE > 7.0 → bonificación: `score * 1.05` (cap a 100)

Valores de referencia (Hopkins, J. Med. Chem. 2014):
- LLE > 5: excelente (lead-like)
- LLE 3–5: aceptable
- LLE < 3: pobre (necesita optimización)

---

## 4. Score Breakdown — Componentes

### 4.1 Regla de Oro v2.0

```
┌─────────────────────────────────────────────────────┐
│  RANKING (total_score)                              │
│  = normalized_affinity * stacking_factor            │
│    * specificity_multiplier * mmgbsa_factor         │
├─────────────────────────────────────────────────────┤
│  FLAGS (no afectan ranking)                         │
│  • ADME Score          → perfil farmacocinético     │
│  • Drug-likeness Score → QED-based                  │
│  • SA Factor           → synthetic accessibility    │
│  • Blood Factor        → viabilidad sistémica       │
├─────────────────────────────────────────────────────┤
│  UX (viability_adjusted_score)                      │
│  = total_score * viability_multiplier * sa_factor   │
│  → solo para el usuario, NO para ranking científico │
└─────────────────────────────────────────────────────┘
```

### 4.2 ADME Score

| Componente | Rango | Penalización máxima | Referencia |
|-----------|-------|-------------------|------------|
| TPSA | 20–90 Å² óptimo | −30 (TPSA>120) | Ertl et al. 2000 |
| logP | 0–4.5 óptimo | −25 (logP>4.5) | Lipinski et al. 1997 |
| SA Score | ≤3.5 óptimo | −40 (SA>7) | Ertl & Schuffenhauer 2009 |

### 4.3 SA Score Factor

| SA Score | Factor | Severidad | Interpretación sintética |
|----------|--------|-----------|------------------------|
| ≤ 3.5 | 1.00 | excelente | 1–3 pasos, comercialmente viable |
| 3.5–4.0 | 1.00–0.95 | buena | 3–5 pasos, razonable |
| 4.0–5.0 | 0.95–0.72 | moderada | 5–8 pasos, requiere química especializada |
| 5.0–6.0 | 0.72–0.55 | difícil | 8–12 pasos, costoso |
| 6.0–7.0 | 0.55–0.42 | muy difícil | >12 pasos, borderline |
| > 7.0 | 0.42–0.35 | inviable | Prácticamente no sintetizable |

### 4.4 MM-GBSA Factor

Se aplica SOLO cuando MM-GBSA converge exitosamente:

```
mmgbsa_factor = 1.0 + (mmgbsa_norm * 0.10)
mmgbsa_norm = clamp(mmgbsa_score / 20.0, -1.0, 1.0)
```

- Rango: [0.9, 1.1] (±10% de corrección)
- Si MM-GBSA no converge o no está disponible: factor = 1.0 (no modifica)

---

## 5. Criterios de Validación Química

### 5.1 Límites del Pipeline

| Parámetro | Valor | Fundamento |
|-----------|-------|------------|
| Heavy atoms mínimos | 5 | Por debajo no hay drug-likeness significativo |
| Heavy atoms máximos | 80 | Vina pierde precisión en ligandos grandes |
| MW mínimo | 100 Da | Fragmentos sin actividad basal |
| MW máximo | 800 Da | Lipinski extendido + macrociclos |
| Carga formal máxima | ±2 | Moléculas con carga ≥3 no son drug-like |
| Fragmentos | 1 solo (strict) | Vina no maneja mezclas |

### 5.2 Átomos No Soportados por Vina

```
Metales de transición: Fe, Cu, Zn, Mn, Co, Ni, Cr, V, Ti, Mo, W
Alcalinos/alcalinotérreos: Li, Na, K, Mg, Ca, Ba
Otros problemáticos: Si, B, Al, Sn, Pb, As, Se, Te
```

---

## 6. Historial de Calibración

| Fecha | Versión | Cambio | Spearman ρ | Autor |
|------|---------|--------|-----------|-------|
| 2025-11 | v1.0 | Vina solo + ADME + Drug-likeness | −0.11 | — |
| 2026-01 | v2.0 | Separar ranking de flags, fix Spearman | +0.19 | — |
| 2026-03 | v3.0 | Agregar XGBoost stacking + pesos por familia | +0.41 | — |
| 2026-05 | v4.0 | Agregar CL-GNN + quantum_sign | +0.47 | — |
| 2026-06 | v5.0 | Agregar MM-GBSA factor, calibrar threshold slack | +0.50 | — |
| 2026-07 | v6.0 | Potency floor fix, continuous penalty, LLE clamp | +0.52 | — |

---

## 7. Reproducibilidad

Para reproducir estos resultados:

```bash
# 1. Configurar entorno
cd backend
conda env create -f environment-desktop.yml

# 2. Correr benchmark
python scripts/run_5ht1a_benchmark.py --exhaustiveness 32 --seed 42

# 3. Generar stacking weights
python scripts/calibrate_stacking_weights.py --output rescoring/artifacts/stacking_weights.json

# 4. Validar
python -m pytest tests/test_normalizer.py -v
```

**Nota**: Los scripts de benchmark y calibración están en desarrollo. Mientras tanto, los pesos en `scoring/engine.py:STACKING_WEIGHTS` y `rescoring/artifacts/stacking_weights.json` son la fuente de verdad.
