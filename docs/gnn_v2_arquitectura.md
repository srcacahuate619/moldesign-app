> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# GNN-v2 — Arquitectura, Auditoría y Plan de Implementación

> **Versión**: Draft v1 (Julio 2026)
> **Objetivo**: Reemplazar RTMScore con una GNN entrenada en dominio (redocked poses)
> que capture señal ORTOGONAL a Vina + XGBoost para consensus stacking.
> **Framework**: PyTorch 2.14 + PyTorch Geometric 2.8 + CUDA 12.6

---

## Índice

1. [Auditoría de datos](#1-auditoría-de-datos)
2. [Por qué RTMScore fracasó](#2-por-qué-rtmscore-fracasó)
3. [Qué señal ORTOGONAL debe capturar GNN-v2](#3-qué-señal-ortogonal-debe-capturar-gnn-v2)
4. [Arquitectura propuesta](#4-arquitectura-propuesta)
5. [Estrategia de training](#5-estrategia-de-training)
6. [Plan de implementación](#6-plan-de-implementación)
7. [Criterios de éxito](#7-criterios-de-éxito)

---

## 1. Auditoría de datos

### PDBbind Refined Set (lo que tenemos)

| Concepto | Cantidad | Calidad |
|----------|:--------:|---------|
| Complejos totales | **865** | 100% refined set |
| Protein PDBs | **865/865** (100%) | Resolución ≤2.5Å, media 1.88Å |
| Ligand SDF (crystal pose) | **865/865** (100%) | Con coordenadas 3D |
| Ligand MOL2 | **5,316** (general set) | Con tipos atómicos Sybyl |
| Labels (pKi) | **865/865** (100%) | Ki (455), Kd (305), IC50 (103), EC50 (2) |
| Feature caches (crystal) | **865/865** | 1192 features (Shell 96 + ECIF 56 + ProLIF + Morgan) |
| Feature caches con Vina | **0/865** | ❌ Redocking no guardado |

```
Distribución de pKi:
  Range:  0.8 —— 13.7  (media 6.7)
  Binders (pKi > 7):  414/865 (47%)
  Weak (pKi 5-7):     268/865 (31%)
  Inactive (pKi < 5): 183/865 (21%)
```

### Distribución por familia estructural

| Familia | Complejos | % |
|---------|:---------:|:-:|
| soluble_enzyme | 678 | 78% |
| kinase | 96 | 11% |
| protease | 51 | 6% |
| nuclear_receptor | 19 | 2% |
| gpcr | 18 | 2% |
| phosphodiesterase | 3 | <1% |

⚠️ **Sesgo**: 78% del training set son enzimas solubles. GPCRs y NRs
están subrepresentados. Esto afecta generalización para targets como 5-HT1A.

### Lo que FALTA generar

| Artefacto | Cantidad | Estimación de tiempo |
|-----------|:--------:|:---------------------|
| Redocked poses (Vina exh=4) | 865 | ~15 min (6 workers) |
| Redocked poses (Vina exh=8) | 865 | ~30 min (6 workers) |
| Feature caches enriched (Vina scores) | 865 | Incluido en docking |
| Protein-ligand graphs (GNN input) | 865 × 2 (crystal + docked) | ~10 min |
| GNN training dataset (train/val/test) | 693/86/86 (80/10/10) | Instantáneo |

### Hardware disponible

| Componente | Especificación |
|------------|---------------|
| CPU | Ryzen 5 5500 (6C/12T) |
| GPU | GTX 1660 SUPER (6GB VRAM, CUDA 12.6) |
| RAM | 32 GB DDR4 |
| Storage | SSD NVMe |

---

## 2. Por qué RTMScore fracasó

### RTMScore

- **Arquitectura**: Graph Transformer + Mixture Density Network (MDN)
- **Training**: PDBbind v2016 crystal complexes (poses cristalográficas)
- **Coverage**: 30-60% (falla en construcción de grafo para ~40% de moléculas)
- **Spearman ρ**: +0.071 a +0.200 (p > 0.3, NO significativo)
- **Anti-correlación**: ρ = -0.56 en varias corridas
- **Tiempo/mol**: 1.7s CPU, 3.0s GPU (overhead > beneficio)

### Causas raíz

1. **Domain shift**: Entrenado en poses cristalográficas de PDBbind, infiere
   sobre poses dockeadas de ChEMBL/DUD-E. Las features geométricas no transfieren.

2. **Coverage catastrófica**: La construcción de grafos (MDAnalysis → grafo PyG)
   es frágil. Cualquier átomo no estándar, missing residue, o conformación
   atípica rompe el pipeline.

3. **Graph Transformer = overkill**: 5 capas de transformer con attention
   multi-head en grafos de ~500 átomos totales. Sobreparametrizado para
   la cantidad de datos (865 complejos). Overfitting severo.

4. **Señal no independiente**: El transformer aprende las mismas features
   geométricas que Shell+ECIF, pero con más ruido. No agrega información
   nueva al stacking.

### Lecciones para GNN-v2

| Lección | Acción |
|---------|--------|
| Domain matching | Entrenar en poses REDOCKEADAS, no cristalográficas |
| Coverage ≥ 95% | Grafo más simple, tolerante a missing atoms |
| No sobreparametrizar | Arquitectura ligera (2-3 capas GNN, no 5 transformers) |
| Señal ortogonal | NO usar features geométricas que Shell+ECIF ya captura |
| Classification > Regression | P(binder) más robusto que pKi para domain shift |
| Ensemble-friendly | Output con uncertainty para stacking decisions |

---

## 3. Qué señal ORTOGONAL debe capturar GNN-v2

### Lo que Vina captura
- Función de scoring empírica: steric + hydrogen bond + hydrophobic + torsion
- Basada en fuerza de campo (FF) y conteo de pares atómicos
- **Qué ignora**: Patrones relacionales, contexto de pocket, jerarquía espacial

### Lo que XGBoost captura (Shell + ECIF)
```
Shell (96 features):  Conteo de pares atómicos en bins de distancia
  Ej: shell_C_N_4_8 = "cuántos pares C(proteína)-N(ligando) a 4-8Å"
  → Estadística agregada, sin relaciones espaciales

ECIF (56 features):   Conteo de contactos por tipo atómico
  Ej: ecif_N_don_O = "cuántas interacciones N-donor con O"
  → Agregado, sin topología

1D/2D (8 features):   Descriptores moleculares (mw, logp, tpsa, etc.)
  → Propiedades del ligando aislado
```

### Lo que GNN-v2 CAPTURARÁ (ortogonal a ambos)

| Señal | Vina | XGBoost | GNN-v2 |
|-------|:----:|:-------:|:------:|
| Pairwise distances (pares) | ✅ | ✅✅✅ | ✅ |
| Graph topology (quién conecta con quién) | ❌ | ❌ | ✅✅✅ |
| Message passing (info flows through graph) | ❌ | ❌ | ✅✅✅ |
| Multi-hop relationships (A→B→C afecta D) | ❌ | ❌ | ✅✅ |
| Attention (qué interacciones importan más) | ❌ | ❌ | ✅✅✅ |
| Spatial hierarchy (átomo→residuo→pocket) | ❌ | ❌ | ✅✅ |
| Local geometry (ángulos, diedros, no solo distancias) | ❌ | ❌ | ✅ |
| Uncertainty estimation (MC Dropout) | ❌ | ❌ | ✅✅✅ |
| Pocket context (entorno químico del binding site) | ❌ | ❌ | ✅✅ |

**La tesis**: GNN-v2 no compite con Shell+ECIF contando pares atómicos.
Aprende PATRONES RELACIONALES: "un donante de H en posición 3 del ligando,
conectado a un anillo aromático en posición 5, interactuando con ASP116
vía puente salino Y con PHE361 vía π-stacking".

Esto es información que ni Vina ni XGBoost pueden capturar porque:
1. Vina no modela relaciones multi-hop (solo pares directos)
2. XGBoost agrega todo en conteos (pierde la topología)

---

## 4. Arquitectura propuesta

### Diseño de alto nivel

```
┌─────────────────────────────────────────────────────────────────┐
│                        GNN-v2 (Binary Classifier)               │
│                                                                  │
│  Protein PDB ──→ Protein Graph ──→ GAT (2 layers) ──→ h_prot   │
│                                       │                          │
│  Ligand SDF ───→ Ligand Graph ───→ GIN (3 layers) ──→ h_lig    │
│                                       │                          │
│                              ┌────────┴────────┐                 │
│                              │  Cross-Attention │                │
│                              │  lig attends to  │                │
│                              │  prot residues   │                 │
│                              └────────┬────────┘                 │
│                                       │                          │
│                              Set2Set Pooling                     │
│                                       │                          │
│                              ┌────────┴────────┐                 │
│                              │  MLP + MC Drop   │                │
│                              │  P(binder) + σ   │                │
│                              └─────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

### Protein Encoder

```
Input:  Protein PDB → residuos del binding pocket (≤8Å del ligando)
Graph:  Nodos = Cα atoms de cada residuo
        Aristas = Cα-Cα distance < 15Å (k-NN con k=10)
        
Features por nodo (residuo):
  - Tipo de residuo (one-hot, 20 aminoácidos)
  - Hidrofobicidad (escala Kyte-Doolittle)
  - Carga a pH 7.4 (-1, 0, +1)
  - SASA relativa (si disponible)
  - Coordenadas 3D del Cα (para E(n)-equivariance)

Encoder: 2 capas GAT (Graph Attention Network)
  - hidden_dim = 128
  - heads = 4
  - dropout = 0.2
  - LayerNorm + residual
  
Output:  Tensor (N_res × 128) — embedding por residuo
```

### Ligand Encoder

```
Input:  Ligand (SDF/MOL2 con coordenadas 3D)
Graph:  Nodos = átomos pesados (Z > 1, excluye H)
        Aristas = bonds covalentes (de SDF) + spatial edges (d < 4Å)
        
Features por nodo (átomo):
  - Tipo atómico (one-hot: C, N, O, S, P, F, Cl, Br, I, other)
  - Hibridación (sp, sp2, sp3)
  - Grado (número de heavy neighbors)
  - Carga formal
  - aromaticidad (bool)
  - Número de H implícitos
  - ¿En anillo? (bool)

Encoder: 3 capas GIN (Graph Isomorphism Network)
  - hidden_dim = 128
  - ε-learnable
  - dropout = 0.2
  - BatchNorm + residual

¿Por qué GIN y no GAT para el ligando?
  GIN es más expresivo para grafos moleculares pequeños (~30 átomos).
  GAT tiene más parámetros pero no necesariamente mejor para moléculas.
  
Output:  Tensor (N_lig × 128) — embedding por átomo
```

### Cross-Attention (Ligando → Proteína)

```
Input:  h_lig (N_lig × 128), h_prot (N_res × 128)

Q = W_q @ h_lig     # ligand atoms query protein residues
K = W_k @ h_prot
V = W_v @ h_prot

Attention = softmax(Q @ K^T / √d_k) @ V

Output: h_cross (N_lig × 128) — ligand features contextualizadas
        por los residuos relevantes de la proteína

¿Por qué solo lig → prot y no prot → lig?
  El ligando es pequeño (~30 átomos), la proteína es grande (~200 residues de pocket).
  Lo que importa es "¿a qué residuos le presta atención este átomo del ligando?".
  Bidireccional sería más costoso sin beneficio claro.
```

### Global Pooling

```
Input:  h_cross (N_lig × 128)

Pooling: Set2Set (6 processing steps)
  - Aprende a resumir el grafo del ligando en un vector fijo
  - Mejor que mean/max pooling porque captura interacciones multi-átomo
  - Output: 256-dim (2 × hidden_dim)

Alternativa considerada: Attention Pooling (más simple, mismo orden de expresividad)
  - Elegir entre Set2Set y Attention Pooling via ablation en training
```

### Classification Head

```
Input:  h_global (256-dim)

MLP:
  Linear(256 → 128) + ReLU + Dropout(0.3)
  Linear(128 → 64)  + ReLU + Dropout(0.3)
  Linear(64 → 1)    → logit

Output: P(binder) = sigmoid(logit)

MC Dropout (para uncertainty):
  - Durante inferencia, dropout se mantiene ACTIVO
  - 20 forward passes → μ_prob, σ_prob
  - σ_prob alto = "GNN no está segura" → menor peso en stacking
```

### Comparación con RTMScore

| Aspecto | RTMScore | GNN-v2 |
|---------|----------|--------|
| Protein encoder | Graph Transformer (5 layers) | GAT (2 layers) |
| Ligand encoder | Graph Transformer (5 layers) | GIN (3 layers) |
| Protein granularity | Heavy atoms (~3000) | Cα residues (~200) |
| Coverage issue | Átomos no estándar | Solo 20 aminoácidos → nunca falla |
| Inter-graph | Ninguna (concatenación) | Cross-attention lig→prot |
| Output head | MDN (regression + variance) | Binary + MC Dropout |
| Parámetros | ~2M | ~500K |
| Training data | Crystal poses | Crystal + Docked poses |
| Overfitting risk | Alto | Bajo (regularización fuerte) |

---

## 5. Estrategia de training

### Split

```
865 complejos PDBbind → stratified split por pKi bin:
  Train:  693 (80%)
  Val:     86 (10%)  ← early stopping, hyperparam tuning
  Test:    86 (10%)  ← evaluación final

Stratification bins: pKi < 5, 5-6, 6-7, 7-8, 8-9, > 9
```

### Domain-aware training

```
Fase 1 — Crystal pre-training (opcional, ~1 hora en GPU)
  Train en 693 poses cristalográficas (el ligando en su pose nativa)
  → La GNN aprende el "modo" del receptor + binding patterns básico
  → Valida en 86 crystal
    
Fase 2 — Docked fine-tuning (obligatorio)
  Re-dockear los 693+86 complejos con Vina (exh=4)
  Fine-tunear la GNN en poses REDOCKEADAS
  → La GNN aprende a generalizar sobre el output del pipeline real
  → Esto elimina el domain shift que mató a RTMScore

Fase 3 — Multi-target generalization
  Entrenar en los 86 de test como held-out para 5-HT1A específicamente
  Evaluar transferencia a otros targets
```

### Data augmentation (para combatir imbalance de familias)

```
Para GPCR (18 complejos) y NR (19 complejos):
  - Rotación aleatoria del ligando (±15°) antes de dockear
  - Múltiples poses de docking por ligando (top 3 modos)
  - SMILES augmentation: tautómeros, estereoisómeros
```

### Loss function

```
Binary Cross-Entropy:
  target = 1 if pKi > 7, else 0
  threshold alternativos a probar: pKi > 6, pKi > 8
  → classification es más robusta al label noise (Ki vs Kd vs IC50)

Class-balanced loss (opcional):
  Si hay imbalance fuerte (>70% binders o >70% non-binders)
  → weight = 1 / class_frequency
```

### Optimization

```
Optimizer: AdamW
  lr = 1e-3 (initial), cosine annealing to 1e-5
  weight_decay = 1e-4

Batch size: 16 (6GB VRAM)
Gradient accumulation: 2 → effective batch = 32

Early stopping: patience = 30 epochs on validation loss
Max epochs: 200

Regularization:
  - Dropout 0.2 (GNN layers) + 0.3 (MLP head)
  - LayerNorm / BatchNorm after each GNN layer
  - Residual connections en todas las capas
  - Weight decay 1e-4
```

### Data loading

```python
class PLComplexDataset(InMemoryDataset):
    """Protein-Ligand Complex Dataset for PyG.
    
    Cada muestra:
      - protein_graph: Data (N_res × features_prot, edge_index_prot)
      - ligand_graph: Data (N_lig × features_lig, edge_index_lig, edge_attr_lig)
      - cross_edges: Tensor (2 × E_cross) — índices [lig_idx, prot_idx]
      - y: float — pKi label
      - y_binary: int — P(pKi > 7)
      - pdb_id: str
      - family: str
    """
```

---

## 6. Plan de implementación

### Fase 0 — Preparación de datos (hoy)

```powershell
# 1. Re-dockear 865 complejos PDBbind con Vina
python rescoring/scripts/redock_pdbbind.py --exhaustiveness 4 --workers 6

# 2. Construir dataset PyG (procesar PDB + SDF → grafos)
# 3. Split estratificado train/val/test
```

### Fase 1 — GNN mínima viable (2-3 días)

1. `rescoring/gnn_v2/data.py` — PLComplexDataset
2. `rescoring/gnn_v2/models.py` — ProteinEncoder, LigandEncoder, CrossAttention
3. `rescoring/gnn_v2/train.py` — Training loop con early stopping
4. Validación: ROC-AUC en test set ≥ 0.75

### Fase 2 — Optimización y domain-tuning (1-2 días)

1. Fine-tuning en poses dockeadas
2. Ablation: GIN vs GAT para ligand encoder
3. Ablation: con/sin cross-attention
4. Ablation: Set2Set vs Attention Pooling
5. Threshold sweep para pKi binario

### Fase 3 — Integración con stacking (1-2 días)

1. Exportar modelo a `rescoring/artifacts/gnn_v2.pt`
2. `gnn_service_v2.py` — carga modelo + infiere con MC Dropout
3. `stacking_service.py` — Vina + XGBoost + GNN-v2 con pesos aprendidos
4. Validación final: EF benchmark en 5-HT1A con y sin GNN-v2

### Fase 4 — Multi-target validation (1 semana)

1. Correr EF benchmark en ≥3 targets adicionales
2. Comparar: Vina solo, Vina+XGBoost, Vina+XGBoost+GNN-v2
3. Documentar resultados en metricas_experimentales.md

---

## 7. Criterios de éxito

### GNN-v2 individual

| Métrica | Mínimo aceptable | Bueno | Excelente |
|---------|:----------------:|:-----:|:---------:|
| Coverage | ≥ 95% | ≥ 98% | 100% |
| ROC-AUC (test set) | ≥ 0.70 | ≥ 0.80 | ≥ 0.85 |
| Spearman ρ (5-HT1A) | ≥ 0.15 (p < 0.05) | ≥ 0.25 | ≥ 0.35 |
| Tiempo/mol | < 1s | < 0.5s | < 0.2s |

### Stacking (Vina + XGBoost + GNN-v2)

| Métrica | Baseline (Vina+XGBoost) | Target | Stretch |
|---------|:----------------------:|:------:|:-------:|
| EF@1% (5-HT1A) | 32.5x | ≥ 35x | ≥ 40x |
| EF@5% (5-HT1A) | 9.0x | ≥ 10x | ≥ 12x |
| ROC-AUC (5-HT1A) | 0.834 | ≥ 0.85 | ≥ 0.88 |
| PR-AUC (5-HT1A) | 0.355 | ≥ 0.40 | ≥ 0.45 |

### NO-GO criteria (si esto pasa, GNN-v2 no suma y abandonamos)

- ❌ Coverage < 85% (no confiable para producción)
- ❌ Spearman ρ < 0.05 o p > 0.5 (no mejor que random)
- ❌ EF del stacking < EF de Vina+XGBoost solo (degrada)
- ❌ Tiempo/mol > 3s (más lento que dockear)

---

## Apéndice A: ¿Por qué GIN y no GAT/GCN/Transformer?

```
GCN (Kipf & Welling 2017):
  - Message: mean(neighbor_features) * W
  - Expresividad: ≤ 1-WL test
  - Ventaja: simple, rápido
  - Desventaja: no distingue algunos grafos no-isomorfos
  → Buen baseline, pero sub-óptimo para moléculas

GAT (Veličković 2018):
  - Message: attention-weighted neighbor aggregation
  - Ventaja: aprende qué vecinos son importantes
  - Desventaja: más parámetros, puede overfitear en datasets chicos
  → Bueno para protein encoder (muchos nodos, pocas muestras)

GIN (Xu et al. 2019):
  - Message: MLP((1+ε)·self + sum(neighbors))
  - Expresividad: = 1-WL test (máxima para GNNs message-passing)
  - Ventaja: matemáticamente más expresivo que GCN/GAT
  - Desventaja: más lento que GCN
  → Óptimo para ligand encoder (grafos chicos, necesita expresividad)

Graph Transformer:
  - Message: self-attention sobre todos los pares de nodos
  - Ventaja: captura long-range interactions
  - Desventaja: O(N²), sobreparametrizado para N<100
  → Overkill. RTMScore lo usó y overfiteó.
```

## Apéndice B: Stacking weights

```
Composite final:
  score = w₁ · score_vina_norm + w₂ · prob_xgb + w₃ · prob_gnn

Pesos aprendidos via Logistic Regression en validation set:
  - Si GNN captura señal ortogonal → w₃ significativo (> 0.1)
  - Si GNN captura misma señal → w₃ ≈ 0 (no suma)
  - Si GNN degrada → w₃ < 0 (la descartamos)

Con MC Dropout:
  σ_gnn = std(20 forward passes)
  w₃_dynamic = w₃ / (1 + σ_gnn)  # menos peso si la GNN no está segura
```

## Apéndice C: Referencias

- **GIN**: Xu et al. "How Powerful are Graph Neural Networks?" ICLR 2019
- **GAT**: Veličković et al. "Graph Attention Networks" ICLR 2018
- **Set2Set**: Vinyals et al. "Order Matters: Sequence to sequence for sets" ICLR 2016
- **MC Dropout**: Gal & Ghahramani "Dropout as a Bayesian Approximation" ICML 2016
- **Cross-attention**: Vaswani et al. "Attention is All You Need" NeurIPS 2017
- **RTMScore**: Shen et al. "Boosting Protein-Ligand Binding Affinity Prediction" JCIM 2022
- **ECIF**: Sánchez-Cruz et al. "Extended Connectivity Interaction Features" JCIM 2021
- **PDBbind**: Liu et al. "PDBbind v2020" J. Med. Chem. 2020
