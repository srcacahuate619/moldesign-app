> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Campaña Multi-Target — Validación masiva + MolGraph + Idea B

> **Actualización**: Julio 2026 — Paso de RCSB a PDBbind. 5 targets validados.
> **GPU Validation**: Julio 6, 2026 — Vina-GPU 2.1 benchmark en Factor Xa: EF=2.24x (vs 1.1x CPU), AUC=0.954, 10 min vs 35 min. 22x speedup estimado para datasets completos. Ver [11_GPU_BENCHMARK_RESULTS.md](11_GPU_BENCHMARK_RESULTS.md).
> Ver también: [metricas_experimentales.md §20](metricas_experimentales.md#20-multi-target-con-pdbbind--5-targets-en-4-familias)

---

## Estado Actual (6 Julio 2026) — Con Protein Surgery

| Target | PDBbind ID | Familia | AUC (stacked) | Tiempo | Status |
|--------|:----------:|---------|:------------:|:------:|:------:|
| 5-HT1A | 7E2Y | GPCR | 0.906 | — | ✅ |
| CDK2 | 3PP0 | Kinase | 0.928 | — | ✅ |
| CDK2 PDBbind | 1b38 | Kinase | 0.996 | 30 min | ✅ |
| HIV-Protease | 1HSG | Protease | 0.947 | — | ✅ |
| Factor Xa | 1f0r | Sol. Enzyme | **0.992** | 6 min | ✅ Nuevo |
| Thrombin | 1c4u | Sol. Enzyme | **0.740** (+26%) | 25 min | ✅ Arreglado |
| CA2 | 1bn1 | Metaloenz. | **0.684** (+37%) | 22 min | ⚠️ Parcial |
| AChE | 1gpk | Sol. Enzyme | **0.801** (antes: timeout) | 22 min | ✅ Arreglado |

**Mejoras por Protein Surgery:**
- AChE: TIMEOUT → AUC 0.801 (chain detector + dynamic box 15.8Å)
- Thrombin: AUC 0.586 → 0.740 (+26%, pre-docking atom filter)
- CA2: AUC ~0.5 → 0.684 (+37%, metal features pending full dataset)

---

## Índice

1. [Targets seleccionados](#1-targets-seleccionados)
2. [Arquitectura de datos](#2-arquitectura-de-datos)
3. [Estimación de tiempos](#3-estimación-de-tiempos)
4. [MM-GBSA: Full vs Subset](#4-mm-gbsa-full-vs-subset)
5. [Plan de implementación día por día](#5-plan-de-implementación-día-por-día)
6. [Archivos a modificar/crear](#6-archivos-a-modificarcrear)
7. [Pre-poblado de MolGraph](#7-pre-poblado-de-molgraph)
8. [Idea B — GNN de propagación](#8-idea-b--gnn-de-propagación)
9. [Criterios de éxito](#9-criterios-de-éxito)
10. [Apéndice: moléculas por target](#10-apéndice-moléculas-por-target)

---

## 1. Targets seleccionados

| Target | PDB ID | Familia | % en PDBbind | Representa |
|--------|:------:|:-------:|:------------:|------------|
| **5-HT1A** | **7E2Y** | **GPCR** | 2% | Receptores acoplados a proteína G |
| **CDK2** | **3PP0** | **Kinase** | 11% | Quinasas, segundo grupo más grande |
| **HIV-proteasa** | **1hsg** | **Protease** | 6% | Proteasas, diana farmacológica clásica |

**Justificación**: Con estos 3 targets cubrimos el **19%** del espacio de PDBbind en cantidad,
pero el **~95%** en diversidad de mecanismos de binding (transmembranal, ATP-competitivo, hendidura abierta).

> ⚠️ **ADVERTENCIA CIENTÍFICA (Julio 2026):** El PDB **3PP0** corresponde a **CDK2** (Cyclin-dependent kinase 2),
> no a CDK4. CDK2 y CDK4 son proteínas distintas con bolsillos de unión diferentes.
> 
> Las referencias a ChEMBL (`CHEMBL331`), DUD-E decoys, y comandos en este documento
> están configurados para **CDK4**. Si se desea mantener la campaña para CDK4,
> reemplazar 3PP0 por un PDB real de CDK4 (ej: `2W96`, `3G33`) y re-ejecutar
> la preparación del receptor. Si se desea usar 3PP0, cambiar todas las referencias
> de CDK4 a CDK2 y actualizar los ChEMBL IDs (target CDK2: `CHEMBL2522`).

```
Espacio químico cubierto (mecanismos de binding):

GPCR (7E2Y):     Pocket transmembranal hidrofóbico, sellado, acceso lateral
Kinase (3PP0):   Pocket ATP-competitivo, hinge region, solvent-exposed
Protease (1hsg): Hendidura abierta, dimerización, subsitios S1-S4
```

---

## 2. Arquitectura de datos

### Moléculas por target

| Target | Activos ChEMBL | Decoys DUD-E | Total x target | Estado |
|--------|:--------------:|:------------:|:--------------:|--------|
| 5-HT1A | 494 | 3000 | 3494 | ✅ Activos + decoys descargados |
| CDK4 | ~300 | ~2500 | ~2800 | ⏳ Por descargar |
| HIV-proteasa | ~200 | ~2500 | ~2700 | ⏳ Por descargar |
| **Total** | **~1000** | **~8000** | **~9000** | |

### Scores por molécula

| Score | Fuente | Tiempo unitario | Tiempo total (10 workers) |
|-------|--------|:---------------:|:-------------------------:|
| Vina score | AutoDock Vina 1.2.7 exh=4 | ~3.8s | ~57 min |
| Shell 96 + ECIF 56 + 1D/2D 8 | InteractionFeatureExtractor | ~1.0s | ~15 min |
| XGBoost prob | classifier_binder.joblib | ~0.01s | ~1 min |
| MM-GBSA (protein-only) | OpenMM + AMBER14SB + OBC2 | ~7s (GPU) | ~1.8h (3 paralelo) a ~10h (1 paralelo) |

### Datasets de salida

```
data/
├── multitarget/
│   ├── 5ht1a/          → datos benchmark existentes (2547 mols dockeadas)
│   ├── cdk4/            → activos + decoys + docking + scores
│   ├── hiv_protease/    → activos + decoys + docking + scores
│   └── checkpoint.json   → estado del pipeline (resumible)
```

---

## 3. Estimación de tiempos

### Con 10 workers (excluyendo MM-GBSA)

| Paso | Moléculas nuevas | Tiempo | Costo acumulado |
|------|:----------------:|:------:|:---------------:|
| Descarga ChEMBL activos | ~500 | 30 min | 30 min |
| Descarga DUD-E decoys | ~5000 | 20 min | 50 min |
| PDBQT preparación (OpenBabel) | 2 targets | 5 min | 55 min |
| Vina docking (10w, exh=4) | 5500 | **35 min** | 1.5 h |
| XGBoost scoring (10w) | 5500 | 5 min | 1.6 h |
| **Subtotal sin MM-GBSA** | **5500** | **~1.6 h** | |

### Con GPU Vina-GPU Hybrid (Julio 2026)

| Paso | Moléculas nuevas | Tiempo | Costo acumulado |
|------|:----------------:|:------:|:---------------:|
| Descarga ChEMBL activos | ~500 | 30 min | 30 min |
| Descarga DUD-E decoys | ~5000 | 20 min | 50 min |
| PDBQT preparación | 2 targets | 5 min | 55 min |
| **Vina docking (GPU batch)** | **5500** | **~8 min** | **1.1 h** |
| XGBoost scoring (10w) | 5500 | 5 min | 1.2 h |
| **Subtotal sin MM-GBSA** | **5500** | **~1.2 h** | |

> **Speedup GPU**: 35 min → 8 min (4.4×). Para 10 targets completos (~20,000 mols):
> CPU: ~33h → GPU: ~1.1h. Ver [10_VINA_GPU_HYBRID.md](10_VINA_GPU_HYBRID.md).

### Con MM-GBSA (Full vs Subset)

| Opción | Moléculas | Tiempo MM-GBSA | Tiempo total campaña |
|--------|:---------:|:--------------:|:--------------------:|
| **B — Top 200/target** | **~750** | **~30 min GPU** | **~2.5 h** |
| A — Full | ~9000 | ~7 h GPU | ~9 h (overnight) |

### Tiempo por etapa (diagrama Gantt)

```
Día 1:   Preparación         ████████████████████████████░░░░░░  2h + descargas bg
Día 1n:  Docking (bg)        ░░░░░████████████████████████████  35 min
Día 2:   XGBoost + MM-GBSA   ░░░░░░░░░░░░████░░░░████████████  1h (con top 200)
Día 2n:  MM-GBSA (opcional)  ░░░░░░░░░░░░░░░░░░░░░░██████████  7h (solo full)
Día 3:   MolGraph + Idea B   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░████  3h
Día 4:   Documentación       ████████████████████████████████  2h
```

---

## 4. MM-GBSA: Full vs Subset

### ¿Qué es MM-GBSA protein-only?

OpenMM minimiza la energía de la proteína con el ligando presente, usando:
- **AMBER14SB**: campo de fuerza para la proteína
- **OBC2**: solvente implícito (GBSA)
- **PDBFixer**: repara átomos faltantes, agrega H a pH 7.4

El resultado es ΔG_total = ΔG_vdw + ΔG_elec + ΔG_gb + ΔG_surf

**Limitación actual**: Solo calcula la energía de relajación proteica. No incluye
la energía del ligando (falta GAFF2 parametrización). Captura ~70% de la señal
real de MM-GBSA.

### Decisión: Opción B — Top 200 por target

**Razones**:
1. MM-GBSA para ~9000 moléculas toma ~7h en GPU — no vale la pena para el dato
   de las moléculas claramente inactivas que quedan al fondo del ranking
2. Las top 200 por target (~750 total) contienen los "borderline cases" donde
   MM-GBSA puede cambiar el ranking: moléculas con buen Vina pero mala relaxación
3. Para MolGraph propagation, los nodos seed de alta calidad (top 200) son
   suficientes para propagar scores a los nodos no evaluados
4. Nos ahorramos 6.5h de GPU que podemos usar para entrenar Idea B o iterar

### Implementación de MM-GBSA batch

```python
# Pseudocódigo
for target in [5HT1A, CDK4, HIV]:
    results = cargar_resultados(target)
    sorted_results = sort(results, by="composite", descending=True)
    top_200 = sorted_results[:200]
    
    for mol in top_200:
        score = run_mmgbsa(protein_pdb, ligand_sdf)
        mol["mmgbsa_score"] = score.delta_g_total
    
    guardar_resultados(target, results)  # actualizados con MM-GBSA
```

**Tiempo estimado**: 200 mols × 7s / 3 paralelo = 467s ≈ **8 min por target**
**Total**: ~24 min para los 3 targets.

---

## 5. Plan de implementación día por día

### Día 1 — Preparación (2h + descargas en background)

```
Objetivo: Tener todos los datos descargados y scripts listos para el docking.

Tareas:
□ 1. Modificar download_chembl_decoys.py
     - Agregar --target TARGET_CHEMBL_ID y --pdb PDB_ID
     - Guardar outputs en data/multitarget/{name}/
     - Reutilizar: ya funciona para 5-HT1A (CHEMBL214, CHEMBL1914)

□ 2. Descargar CDK4 activos:
     - Target ChEMBL: CHEMBL331 (CDK4/CyclinD1) o CHEMBL1907602 (CDK4)
     - Ejecutar: python scripts/download_chembl_decoys.py --target CHEMBL331 --pdb 3PP0
     - Output: data/multitarget/cdk4/actives.txt, decoys.smi

□ 3. Descargar HIV-proteasa activos:
     - Target ChEMBL: CHEMBL237 (HIV-1 protease)
     - Ejecutar: python scripts/download_chembl_decoys.py --target CHEMBL237 --pdb 1hsg
     - Output: data/multitarget/hiv_protease/actives.txt, decoys.smi

□ 4. Preparar PDBs + PDBQTs:
     - Descargar 3PP0.pdb de RCSB → data/multitarget/cdk4/3PP0.pdb
     - Descargar 1hsg.pdb de RCSB → data/multitarget/hiv_protease/1hsg.pdb
     - OpenBabel: pdb → pdbqt (rigid, +H) para ambos
     - Verificar: Vina receptor parse test para ambos

□ 5. Calcular centros de binding (desde el ligando cristalográfico):
     - 3PP0: usar el ligando co-cristalizado (SDF de PDBbind)
     - 1hsg: usar el ligando co-cristalizado (SDF de PDBbind)
     - Si no tenemos los SDFs de PDBbind, usar el promedio de los top-5
       hits de ChEMBL con docking exploratorio
```

**Centros de binding estimados** (verificar con ligando co-cristalizado):

| Target | Center X | Center Y | Center Z | Box size |
|--------|:--------:|:--------:|:--------:|:--------:|
| 7E2Y (5-HT1A) | 103.03 | 114.79 | 108.36 | 25×25×25 |
| 3PP0 (CDK4) | ~25 | ~10 | ~15 | 25×25×25 |
| 1hsg (HIV-pro) | ~0 | ~0 | ~10 | 25×25×25 |

### Día 2 — Docking masivo (~35 min con 10 workers)

```
Objetivo: Dockear todas las moléculas nuevas + repuntuar 5-HT1A.

Tareas:
□ 1. Modificar benchmark_ef_vina.py:
     - Agregar --target 3PP0, --target 1hsg
     - Cada target tiene su propio receptor PDBQT + centro de binding
     - Reutilizar: 90% del código es idéntico, solo cambian paths

□ 2. Lanzar CDK4:
     python scripts/benchmark_ef_vina.py \
       --target 3PP0 \
       --actives data/multitarget/cdk4/actives.txt \
       --decoys data/multitarget/cdk4/decoys.smi \
       --workers 10
     Output estimado: ~2550 moléculas, ~16 min ⏱️

□ 3. Lanzar HIV-proteasa:
     python scripts/benchmark_ef_vina.py \
       --target 1hsg \
       --actives data/multitarget/hiv_protease/actives.txt \
       --decoys data/multitarget/hiv_protease/decoys.smi \
       --workers 10
     Output estimado: ~2550 moléculas, ~16 min ⏱️

□ 4. Re-puntuar 5-HT1A (opcional):
     - Ya tenemos scores. Solo actualizar si cambió el clasificador.
     - Saltar si el modelo XGBoost no cambió.

Nota: Los 3 targets corren EN PARALELO si tenemos 10 workers.
      No hay dependencia entre ellos.
      Tiempo total: ~16 min (el más lento gobierna).
```

### Día 3 — Post-procesamiento + MolGraph (~3h)

```
Objetivo: Calcular MM-GBSA, poblar MolGraph, entrenar Idea B.

Tareas:
□ 1. MM-GBSA top 200 por target (~24 min GPU):
     python scripts/run_mmgbsa_batch.py \
       --target cdk4 --top 200
     python scripts/run_mmgbsa_batch.py \
       --target hiv_protease --top 200
     python scripts/run_mmgbsa_batch.py \
       --target 5ht1a --top 200
     Output: scores de solvente para ~600 moléculas clave.

□ 2. Poblado MolGraph (~30 min):
     python scripts/poblar_molgraph.py \
       --targets 5ht1a,cdk4,hiv_protease \
       --mmgbsa-top 200
     
     Esto ejecuta:
     2a. Registrar ~9000 nodos molecule + 3 nodos target
     2b. Registrar evaluaciones (Vina + XGBoost + MM-GBSA)
     2c. Calcular fingerprints 2048-bit para cada molécula
     2d. Edges de similitud: Tanimoto ≥ 0.6 entre TODAS las moléculas
         → ~9000 × (9000 × 0.05) ≈ ~4M aristas potenciales
         → Optimización: solo edges para pares con fp_cache
     2e. Edges de docking: molecule → target por evaluación

□ 3. Entrenar Idea B (~1h):
     python scripts/gnn_propagation.py \
       --molgraph-db ~/MolDesign/data/molgraph.db \
       --propagation-features fp_2048 \
       --epochs 100 \
       --output rescoring/artifacts/propagation_gnn.pt

□ 4. Calcular EF por target (~10 min):
     Para cada target:
       1. Cargar resultados (Vina + XGBoost + MM-GBSA + MolGraph)
       2. Computar EF@1%, EF@5%, EF@10%
       3. Stacking: probar pesos para mejor EF promedio
       4. Reportar

□ 5. Guardar checkpoints:
     data/multitarget/results_5ht1a.json
     data/multitarget/results_cdk4.json
     data/multitarget/results_hiv_protease.json
     data/multitarget/ef_report_multitarget.json
```

### Día 4 — Documentación + stacking multi-target (~2h)

```
Objetivo: Cerrar el experimento, documentar resultados, definir próximos pasos.

Tareas:
□ 1. Actualizar docs/metricas_experimentales.md:
     - Nueva sección: "Campaña Multi-Target: 3 familias"
     - Resultados por target: EF@1%, ROC-AUC, PR-AUC
     - Tabla comparativa: Vina vs XGBoost vs +MM-GBSA vs +MolGraph
     - EF promedio multi-target (nuestra métrica real)

□ 2. Stacking weights:
     - Por familia: ¿mismos pesos o cada familia necesita los suyos?
     - Meta-learner: LogisticRegression sobre Vina + XGB + MM-GBSA + MolGraph
     - Evaluación: Leave-one-target-out cross-validation

□ 3. Validación cruzada:
     ¿EF promedio ≥ 15x? → Pipeline listo para producción.
     ¿EF promedio < 10x? → Necesitamos mejorar antes de release.
     ¿Algún target con EF < 3x? → Investigar por qué ese target falla.

□ 4. Decisión: release vs iteración:
     Si pasa criterios → empaquetar modelo + pre-poblado → release.
     Si no pasa → diagnóstico de targets fallidos → iterar.
```

---

## 6. Archivos a modificar/crear

### Modificaciones a scripts existentes

| Archivo | Cambio | Prioridad |
|---------|--------|:---------:|
| `scripts/download_chembl_decoys.py` | Agregar `--target CHEMBL_ID` y `--pdb PDB_ID`. Output en `data/multitarget/{name}/` | 🔴 Crítica |
| `scripts/benchmark_ef_vina.py` | Agregar `--target PDB_ID` con receptor config + centro binding. Soporte para targets sin centro conocido (auto-detect from ligand) | 🔴 Crítica |
| `backend/scoring/mmgbsa.py` | Si hace falta, paralelizar GPU. Ya acepta `num_steps` param | 🟢 Opcional |

### Nuevos scripts

| Archivo | Propósito | Tamaño estimado |
|---------|-----------|:---------------:|
| `scripts/run_mmgbsa_batch.py` | Correr MM-GBSA para top N de un target. Input: checkpoint.json, Output: scores agregados | ~150 líneas |
| `scripts/poblar_molgraph.py` | Poblar MolGraph desde resultados multi-target. Computar fingerprints + edges de similitud + edges de docking | ~300 líneas |
| `scripts/gnn_propagation.py` | GNN de propagación sobre MolGraph. GCN/GAT sobre grafo de moléculas. Label propagation / ranking | ~400 líneas |

### Archivos de datos (outputs)

| Archivo | Contenido |
|---------|-----------|
| `data/multitarget/cdk4/actives.txt` | ~300 SMILES ChEMBL CDK4 con pKi |
| `data/multitarget/cdk4/decoys.smi` | ~2500 decoys DUD-E CDK4 |
| `data/multitarget/cdk4/3PP0.pdb` | CDK4 receptor |
| `data/multitarget/cdk4/3PP0.pdbqt` | CDK4 receptor preparado para Vina |
| `data/multitarget/cdk4/results.json` | Scores completos (Vina + XGBoost + MM-GBSA) |
| ... | Ídem para hiv_protease y 5ht1a |
| `data/multitarget/ef_report_multitarget.json` | Reporte consolidado |
| `rescoring/artifacts/propagation_gnn.pt` | Modelo entrenado Idea B |

---

## 7. Pre-poblado de MolGraph

### Estructura esperada post-poblado

| Tabla | Registros | Descripción |
|-------|:---------:|-------------|
| `mol_nodes` | **~9000** | 3 targets × (~300 actives + ~2700 decoys) |
| `mol_fingerprints` | **~9000** | Morgan 2048-bit (pickle) |
| `mol_edges` | **~200K** | Similitud + docking + same_target |
| `molgraph_fts` | **~9000** | FTS5 para búsqueda textual |

### Tipos de nodos

```
mol_node.type = "molecule" → ~9000
mol_node.type = "target"   → 3 (5-HT1A/7E2Y, CDK4/3PP0, HIV-proteasa/1hsg)
```

### Tipos de aristas

```
mol_edge.relation = "similar"          → Tanimoto ≥ 0.6
mol_edge.relation = "docking"          → molecule → target
mol_edge.relation = "same_scaffold"    → Bemis-Murcko scaffold ID
mol_edge.relation = "same_target"      → molecule → molecule (mismo target)
```

### Propiedades de nodos molécula

```json
{
  "smiles": "NCCC1=CNC2=C1C=C(O)C=C2",
  "mwt": 176.22,
  "logp": 1.56,
  "vina_score": -6.2,
  "xgb_prob": 0.78,
  "mmgbsa_delta_g": -12.4,
  "is_active": true,
  "target_pdb": "7E2Y",
  "family": "gpcr"
}
```

### Estrategia de edges de similitud

Computar Tanimoto entre TODOS los pares (~9000²/2 = 40M pares) es costoso.
Estrategia: **LSH + k-NN aproximado** para reducir a ~5 vecinos por molécula.

```python
from rdkit import DataStructs
from rdkit.Chem import AllChem

# Para cada molécula, encontrar top-5 vecinos más similares
for fp_i, mol_i in zip(fingerprints, molecules):
    sims = []
    for fp_j, mol_j in zip(fingerprints, molecules):
        if mol_i != mol_j:
            sim = DataStructs.TanimotoSimilarity(fp_i, fp_j)
            if sim >= 0.6:
                sims.append((mol_j, sim))
    top_5 = sorted(sims, key=lambda x: x[1], reverse=True)[:5]
    for vecino, sim in top_5:
        insert_edge(mol_i, vecino, "similar", weight=sim)
```

**Tiempo estimado**: 9000 × 5 vecinos = ~45K comparaciones. ~30 segundos.

---

## 8. Idea B — GNN de propagación

### Arquitectura propuesta

```
Input: MolGraph completo (~9000 nodos, ~200K aristas)

GCN (2 capas, hidden=64):
  Capa 1: GCNConv(fingerprint_2048 → 128) + ReLU + Dropout(0.3)
  Capa 2: GCNConv(128 → 64) + ReLU + Dropout(0.3)
  
Output: Predicción de actividad por nodo (score Vina, prob XGBoost, o binario activo/inactivo)

Loss: MSE para regresión (score) o BCE para clasificación (activo/inactivo)

Inferencia para molécula nueva:
  1. Computar fingerprint 2048-bit
  2. Encontrar top-5 vecinos en MolGraph por Tanimoto
  3. Insertar nodo temporal con aristas a vecinos
  4. GNN propagation → score predicho
```

### Comparación: propagación vs lo que ya tenemos

| Señal | Vina+XGBoost | Propagación MolGraph | Diferencia |
|-------|:------------:|:--------------------:|:-----------|
| Binding pocket | ✅ Directo | ❌ Indirecto | Ortogonal |
| SAR de análogos | ❌ No captura | ✅✅ Propaga | **Único** |
| Cold start | ✅ Funciona | ❌ No funciona | Complementario |
| Multi-target | ✅ Mismo modelo | ✅✅ Cada target separado | Flexible |

### Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|:-----------:|------------|
| Cold start: molécula sin vecinos | Media | Conectar siempre por Tanimoto |
| Señal débil: pocos activos en grafo | Baja | 300 activos/target es suficiente |
| GNN sobreentrena: grafo chico | Media | Dropout + early stopping + data augmentation (rotular decoys como inactivos) |
| No mejora el stacking | Alta | Si no suma, descartamos Idea B |

### Criterios NO-GO

- Spearman propagación vs Vina > 0.9: la GNN solo repite Vina, no suma
- EF con stacking + propagación < EF con Vina+XGBoost solo: degrada
- Coverage < 50% en moléculas nuevas: demasiado cold start

---

## 9. Criterios de éxito

### Por target

| Métrica | Mínimo | Bueno | Excelente |
|---------|:------:|:-----:|:---------:|
| EF@1% (Vina+XGBoost) | > 5x | > 15x | > 25x |
| EF@1% (+MM-GBSA) | > 6x | > 18x | > 30x |
| EF@1% (+MolGraph) | > 7x | > 20x | > 32x |
| ROC-AUC | > 0.7 | > 0.8 | > 0.85 |

### Multi-target (promedio)

| Métrica | Mínimo | Bueno | Excelente |
|---------|:------:|:-----:|:---------:|
| EF@1% promedio 3 targets | > 8x | > 15x | > 25x |
| Targets con EF@1% > 5x | 2/3 | 3/3 | 3/3 |
| Desviación estándar EF | < 50% del promedio | < 30% | < 15% |

### NO-GO

- ❌ EF@1% < 3x en algún target: ese target necesita investigación
- ❌ EF promedio < 8x: no es mejor que Vina solo generalizado
- ❌ Stacking + MolGraph < Vina+XGBoost: Idea B no suma, descartar

---

## 10. Apéndice: detalles técnicos

### CDK4 (3PP0)

| Propiedad | Valor |
|-----------|-------|
| Target ChEMBL ID | CHEMBL331 |
| PDB ID | 3PP0 |
| Resolución | 2.40Å |
| Binding pocket | ATP-binding site, hinge region |
| Centro estimado | ~25, ~10, ~15 (verificar con ligando co-cristalizado) |
| N° activos ChEMBL esperados | ~300 (Ki < 1uM, excluyendo pan-assay) |
| N° decoys DUD-E | ~2500 |
| Archivo receptor | `data/multitarget/cdk4/3PP0.pdb` |
| Archivo receptor PDBQT | `data/multitarget/cdk4/3PP0.pdbqt` |

### HIV-proteasa (1hsg)

| Propiedad | Valor |
|-----------|-------|
| Target ChEMBL ID | CHEMBL237 |
| PDB ID | 1hsg |
| Resolución | 2.00Å |
| Binding pocket | Dimer interface, subsitios S1-S4 |
| Centro estimado | ~0, ~0, ~10 (verificar con ligando co-cristalizado) |
| N° activos ChEMBL esperados | ~200 (Ki < 1uM) |
| N° decoys DUD-E | ~2500 |
| Archivo receptor | `data/multitarget/hiv_protease/1hsg.pdb` |
| Archivo receptor PDBQT | `data/multitarget/hiv_protease/1hsg.pdbqt` |

### Comandos de referencia

```powershell
# Descargar CDK4
python scripts/download_chembl_decoys.py --target CHEMBL331 --pdb 3PP0

# Descargar HIV-proteasa
python scripts/download_chembl_decoys.py --target CHEMBL237 --pdb 1hsg

# Benchmark CDK4
python scripts/benchmark_ef_vina.py --target 3PP0 --workers 10

# Benchmark HIV-proteasa
python scripts/benchmark_ef_vina.py --target 1hsg --workers 10

# MM-GBSA batch (top 200)
python scripts/run_mmgbsa_batch.py --target cdk4 --top 200

# Poblar MolGraph
python scripts/poblar_molgraph.py --targets cdk4,hiv_protease,5ht1a

# Entrenar propagación
python scripts/gnn_propagation.py --epochs 100
```

---

## Changelog

| Fecha | Cambio |
|-------|--------|
| 2026-07-04 | Versión inicial del plan multi-target |
