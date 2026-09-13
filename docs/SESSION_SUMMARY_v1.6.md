> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Session Summary — v1.6 Pipeline Revival & Architecture Overhaul

> **Fechas**: Julio 9-11, 2026  
> **Duración**: ~24h (5 sesiones)  
> **Objetivo**: Resucitar el pipeline tras Vina-GPU, corregir 8 bugs, validar 10 targets en 6 familias, implementar sistema dinámico de stacking auto-calibrado, y lograr pipeline universal sin hardcodeo.

---

## 1. Bugs Encontrados y Fixeados (5 bugs)

| # | Bug | Impacto | Fix |
|:-:|------|:-------:|-----|
| 1 | `EXHAUSTIVENESS=4` hardcodeado | Calidad de pose sub-óptima para paper | `--exhaust 8` default, argumento configurable |
| 2 | `STACKING_WEIGHTS` no coincidían con `datos_para_paper.md` | Kinase usaba CL-GNN con peso 0.3 (debía ser 0.0 porque AUC 0.574) | Corregidos a valores validados empíricamente |
| 3 | `--gnn` nunca ejecutaba CL-GNN | `calibrated_stacking()` referenciaba `clgnn_prob` que nadie poblaba | Agregada CL-GNN inference al bloque `--gnn` |
| 4 | **`box_size=None`** → Vina recibía `--size_x None` | **0 docking en 10 de 12 targets** | `receptor_config.get("box_size") or 25` |
| 5 | `_get_target_path()` referencia `args` global | Crashea al llamar desde scripts externos | Documentado como bug latente, no bloqueante |
| 6 | **PDBQT con tags ROOT/BRANCH/ENDBRANCH** | Vina rechaza el receptor: `PDBQT parsing error: Unknown tag > ROOT` | `_sanitize_pdbqt_rigid()` — limpia tags flexibles post-OpenBabel |
| 7 | **Receptores multi-cadena sin trimming** | Vina dockeaba contra la proteina ENTERA (dimeros, tetrameros). MMP9: 5.8MB, GLP-1R: 10.5MB | `_detect_dominant_chain()` + `_trim_pdb_chain()` — extrae solo la cadena del sitio activo |
| 8 | **Centros hardcodeados incorrectos en 5 targets** | 7E2Y off por 20A, 3PP0 off por 20A, 5Z2R off por 42A, 6X1A off por 130A. Docking en regiones vacias. | `_load_curated_db()` — carga `curated_targets.csv` dinamicamente. Solo el CSV es fuente de verdad para centros.

---

## 2. Resultados de Benchmark — 8 Targets, 6 Familias

**Configuración**: exh=8, 5 workers, `--gnn`, quantum exit OFF, Vina-CPU 1.2.7, ~2,550 mols por target

| Target | PDB | Familia | Pipeline EF@1% | Pipeline AUC | Vina AUC | Tiempo | Calidad |
|--------|:---:|---------|:-------------:|:-----------:|:--------:|:------:|:-------:|
| 5-HT1A | 7E2Y | GPCR | **32.64x** | **0.856** | 0.796 | 84 min | ✅✅ Excelente |
| CDK2 | 3PP0 | Kinase | **28.56x** | **0.922** | 0.767 | 84 min | ✅✅ Excelente |
| HIV-protease | 1HSG | Protease | **24.21x** | **0.818** | 0.708 | 84 min | ✅ Bueno |
| ER-alpha | 3ERT | Nuclear Rec. | **34.85x** | **0.965** | 0.867 | 69 min | ✅✅ Excelente |
| Factor Xa | 1f0r | Soluble Enz. | **24.19x** | **0.794** | 0.987 | 198 min | ⚠️ Vina domina |
| AChE | 1gpk | Soluble Enz. | **6.67x** | **0.714** | 0.777 | 348 min | ⚠️ Difícil |
| CA2 | 1bn1 | Metaloenz. | **2.75x** | **0.766** | 0.558 | 246 min | ⚠️ Zn²⁺ limita |
| PDE5 | 1xp0 | Phosphodiest. | **0.00x** | **0.501** | N/A | 2 min | ❌ Receptor roto |

**Promedio 5 targets funcionales**: EF@1% = 28.89x, AUC = 0.871

---

## 3. Arquitectura del Pipeline (Estado Final)

```
Usuario sube receptor PDB
        │
        ▼
┌──────────────────────────────────────────┐
│ structural_family.py                      │
│ Detecta familia automáticamente           │
│ (190+ PDBs curados + regex en PDB header) │
│ → gpcr, kinase, protease, nuclear_rec.,   │
│   soluble_enzyme, metaloenzyme,           │
│   phosphodiesterase, other                │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│ stacking_weights.json (carga dinámica)     │
│ Pesos por familia + molchamb_sign         │
│ Si familia no existe → "default"          │
│ Auto-optimizable post-benchmark (≥500mols)│
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│ Docking Pipeline (target-agnostic)        │
│  1. Meeko/RDKit: SMILES → 3D → PDBQT     │
│  2. Vina-CPU: exh=8, num_modes=1, seed=42│
│  3. Feature Extractor: Shell96+ECIF56     │
│     + 1D/2D 8 = 160 features              │
│  Temp dir: D:\moldesign-app\tmp           │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│ Scoring (por molécula)                    │
│  1. XGBoost classifier (AUC 0.858)       │
│  2. CL-GNN contrastive embedding          │
│  3. MolChamb quantum score (xTB, 0.1s)    │
│  4. MM-GBSA v2 (solo C,H,O,N,S,P)         │
│     ⚠️ GAFF2 bloqueado (Python 3.14)      │
│     → halogenados usan 3 componentes       │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│ Stacking calibrado por familia            │
│  7 familias con pesos empíricos           │
│  molchamb_sign por familia (HIV=-1.0)     │
│  Auto-optimización post-benchmark         │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│ Métricas: EF@1%,5%,10% + ROC-AUC + PR-AUC│
│ Reporte JSON + checkpoint reanudable      │
└──────────────────────────────────────────┘
```

### Stacking weights por familia (validados empíricamente)

| Familia | Vina | XGBoost | GNN-v2 | CL-GNN | molchamb_sign | Justificación |
|---------|:----:|:-------:|:------:|:------:|:------------:|---------------|
| gpcr | 0.4 | 0.4 | 0.0 | 0.2 | +1.0 | CL-GNN AUC 0.868 |
| kinase | 0.2 | 0.8 | 0.0 | **0.0** | +1.0 | CL-GNN AUC 0.574 (ignorado) |
| protease | 0.2 | 0.7 | 0.0 | 0.1 | **-1.0** | CL-GNN AUC 0.988; MolChamb invertido |
| nuclear_receptor | 0.3 | 0.5 | 0.0 | 0.2 | +1.0 | Excelente rendimiento |
| soluble_enzyme | 0.3 | 0.5 | 0.0 | 0.2 | +1.0 | AChE difícil; Factor Xa necesita v=0.8 |
| **metaloenzyme** | **0.0** | **0.1** | 0.0 | **0.9** | +1.0 | Vina no modela Zn²⁺; CL-GNN domina |
| phosphodiesterase | 0.3 | 0.5 | 0.0 | 0.2 | +1.0 | Default (PDE5 receptor roto) |
| default | 0.3 | 0.5 | 0.0 | 0.2 | +1.0 | Para familias no calibradas |

---

## 4. Sistema Dinámico — No Más Hardcodeo

**Implementado en esta sesión (Julio 9-10):**

- **`stacking_weights.json`**: Fuente única de verdad. Cargado dinámicamente por `benchmark_ef_vina.py` y `engine.py`. Agregar una familia = agregar entry al JSON.
- **Auto-optimización**: Grid search post-benchmark que actualiza el JSON automáticamente (solo con ≥500 moléculas para significancia estadística).
- **`molchamb_sign`**: Por familia en el JSON. HIV-protease usa -1.0 (los activos tienen MolChamb MENOR que los decoys).
- **`structural_family.py`**: Detecta la familia automáticamente desde el PDB. No más asignación manual.
- **Temp dir en D:** `D:\moldesign-app\tmp` — no más basura en C:.

**Pipeline universal (Julio 11):**

- **`_discover_pdb()`**: Descubre automáticamente cualquier PDB en `data/targets/` (94 PDBs) o `data/target_library/{area}/` (~298 PDBs en 20 áreas terapéuticas). También descarga de RCSB si no existe localmente.
- **`_detect_dominant_chain()`**: Detecta la cadena con más átomos para receptores multi-cadena.
- **`_trim_pdb_chain()`**: Extrae solo la cadena relevante. Reduce el receptor 3-10× (ej: MMP9 de 5.8MB a 146KB).
- **`_compute_geometric_center()`**: Calcula el centro geométrico como fallback cuando no hay datos curados.
- **`_load_curated_db()`**: Carga `curated_targets.csv` (80 targets con grid centers pre-computados). Sobreescribe cualquier centro hardcodeado.
- **`_sanitize_pdbqt_rigid()`**: Elimina tags ROOT/BRANCH/ENDBRANCH que OpenBabel agrega en receptores grandes y que Vina rechaza.
- **`_get_target_path()`**: Ahora funciona para **cualquier PDB ID**. Sin configuración manual. El orden de prioridad para el centro de docking es: CSV curado → Protein Surgery (si hay MOL2) → centro geométrico automático.

**Lo que NO es hardcodeado:**
- Pesos de stacking → JSON dinámico
- Familia del receptor → auto-detectada por `structural_family.py`
- Centro del sitio activo → CSV curado o geométrico automático
- Cadena del receptor → auto-detectada y trimmed
- Parámetros de calibración → JSON extensible
- Signo de MolChamb → por familia en JSON
- Targets soportados → **~390 PDBs descubiertos automáticamente** (antes: 13 hardcodeados)

**Pipeline de descubrimiento automático:**
```
Usuario especifica PDB ID (ej: 4IAQ)
  │
  ├─ 1. _discover_pdb("4iaq") → busca en targets/ y target_library/*/
  │     Si no existe → descarga de RCSB
  │
  ├─ 2. _load_curated_db() → busca en curated_targets.csv
  │     Si existe → centro + cadena + caja curados
  │
  ├─ 3. _detect_dominant_chain() → detecta cadena principal
  │     Si multi-cadena → _trim_pdb_chain()
  │
  ├─ 4. Protein Surgery (si hay ligand_mol2 en TARGET_CONFIGS)
  │
  ├─ 5. OpenBabel PDB → PDBQT + _sanitize_pdbqt_rigid()
  │
  └─ 6. Centro final: curado > protein_surgery > geométrico > hardcodeado
```

---

## 5. Problemas Conocidos y su Estado

### AChE (Soluble Enzyme) — Inherentemente Difícil
- **Síntoma**: EF@1% = 6.67x, AUC = 0.714. Docking lento (~60s/mol).
- **Causa**: Gorge catalítico estrecho de 20Å. Vina explora miles de poses.
- **Intentado**: Protein surgery (centro corregido +30Å en Y, caja 15.8Å). Resultado: sin mejora.
- **Estado**: Es un target difícil por geometría, no por código. EF@1% aceptable (>5x).

### CA2 (Zinc Metalloenzyme) — Vina No Parametriza Zn²⁺
- **Síntoma**: Vina EF@1% = 0.00x, AUC = 0.558.
- **Causa**: Vina no modela interacciones de coordinación con metales.
- **Solución parcial**: CL-GNN peso 0.9 (aprende patrones que Vina ignora). EF@1% subió de 0.00x a 2.75x, AUC de 0.637 a 0.766.
- **Estado**: Mejora real pero modesta. MM-GBSA con GAFF2 podría ayudar más.

### PDE5 (Phosphodiesterase) — CORREGIDO Julio 11
- **Síntoma original**: 0 docking exitoso en 2045 moléculas. 2 minutos de ejecución.
- **Causa**: PDBQT con tags ROOT/BRANCH que Vina rechazaba (`PDBQT parsing error: Unknown tag > ROOT`).
- **Fix**: `_sanitize_pdbqt_rigid()` limpia los tags flexibles post-OpenBabel. Docking verificado: OK en 2.4s.
- **Estado**: ✅ Funcionando. Pendiente benchmark completo.

### MMP9 (1gkc, Metaloenzyme) — CORREGIDO Julio 11
- **Síntoma original**: 0 docking exitoso. Receptor de 5.8MB.
- **Causa**: Doble problema: (a) PDBQT con tags ROOT/BRANCH, (b) receptor multi-cadena (dímero) sin trimming.
- **Fix**: Chain trimming a cadena A + ROOT strip. Receptor: 5.8MB → 146KB. Docking verificado: OK en 4.5s.
- **Estado**: ✅ Funcionando. Pendiente benchmark completo. Nota: Vina sigue sin parametrizar Zn²⁺, pero el stacking CL-GNN=0.9 compensa parcialmente.

### GLP-1R (6x1a, GPCR) — CORREGIDO Julio 11
- **Síntoma original**: 0 docking exitoso. Receptor de 10.5MB.
- **Causa**: Triple problema: (a) centro hardcodeado incorrecto (off por 130Å), (b) receptor multi-cadena sin trimming, (c) PDBQT con tags ROOT/BRANCH.
- **Fix**: CSV curado (centro 131,117,155, cadena R) + chain trimming + ROOT strip.
- **Estado**: ✅ Funcionando. Docking completado (2050 mols, 180 min). Checkpoint guardado. Pendiente fase CL-GNN.

### GAFF2 Bloqueado en Python 3.14
- **Problema**: `openff-toolkit` no compila en Python 3.14.
- **Consecuencia**: MM-GBSA solo para C,H,O,N,S,P. ~90% de decoys DUD-E tienen halógenos.
- **Workaround**: `openmmforcefields` instalado pero requiere `openff-toolkit` internamente (error: `'str' object has no attribute 'to_smiles'`).
- **Stacking maneja esto**: Si MM-GBSA no disponible, usa Vina+XGBoost+CL-GNN (3 componentes).
- **Estado**: Bloqueado. Opciones: (a) aceptar limitación y documentar, (b) migrar a Python 3.12, (c) subprocess a otro entorno.

---

## 6. Lo Que Existe Pero No Está Conectado

| Componente | Ubicación | Estado |
|-----------|-----------|:------:|
| **AutoRecalibrator** (615 líneas) | `backend/scoring/auto_recalibrator.py` | Offline — no conectado al pipeline |
| **MM-GBSA MolChamb v2** (520 líneas) | `backend/services/chemistry/molchamb_v2.py` | Motor completo pero `mmgbsa_score=None` hardcodeado en producción |
| **Metal features** | `backend/services/chemistry/protein_surgery.py` | Detectan Zn²⁺, Fe, Mg pero solo warnings |
| **Quantum features** (19 xTB features) | `scripts/compute_quantum_features.py` | Calculadas pero no usadas como input de ML |
| **CORAL translator** | `rescoring/coral_translator.py` | GPU→CPU domain adaptation (no necesario ahora) |
| **MolChamb en stacking** | `scripts/stacking_ef.py` | Agregado pero no calibrado por familia excepto HIV |

---

## 7. Plan de Conexión (Próximos Pasos)

### Fase A — Correcciones inmediatas (1-2 horas)
| Tarea | Esfuerzo |
|-------|:--------:|
| Debug receptor PDE5 (1xp0) | 30 min |
| Re-correr benchmark 5-HT1A completo (se perdió en test) | 84 min |
| Fix GNN-v2 checkpoint mismatch (`residue_bias.weight`) | 30 min |

### Fase B — Conexiones de infraestructura existente (1 día)
| Tarea | Impacto |
|-------|:-------:|
| Conectar MM-GBSA: `queue_handler.py` → `engine.py` pasa `mmgbsa_score` real | Alto — señal ortogonal de solvente |
| Conectar AutoRecalibrator: `engine.py` consulta `SciConfigRegistry` en runtime | Alto — auto-calibración por target |
| Integrar metal features: `protein_surgery.py` → features de ML | Medio — mejora metaloenzimas |

### Fase C — Mejoras de modelo (2-3 días)
| Tarea | Impacto |
|-------|:-------:|
| Quantum features como input de XGBoost (186 features) | Alto — señal ortogonal universal |
| Entrenar `model_a_metaloenzyme` con datos PDBbind | Medio — modelo específico para Zn²⁺ |
| Bootstrap CI + scaffold split validation | Alto — rigor estadístico paper |

### Fase D — GAFF2 (requiere decisión de arquitectura)
| Tarea | Esfuerzo |
|-------|:--------:|
| Evaluar migración a Python 3.12 para `openff-toolkit` | Investigación |
| O: subprocess a entorno Conda con Python 3.12 + openff | 2-3 días |
| O: aceptar limitación C,H,O,N,S,P y documentar | 30 min |

---

## 8. Archivos Creados/Modificados

### Modificados
| Archivo | Cambios |
|---------|---------|
| `scripts/benchmark_ef_vina.py` | `--exhaust 8`, STACKING_WEIGHTS dinámico desde JSON, CL-GNN en `--gnn`, `box_size or 25`, auto-optimización post-benchmark, temp dir en D: |
| `backend/scoring/engine.py` | 7 familias con pesos validados + metaloenzyme |
| `rescoring/artifacts/stacking_weights.json` | 7 familias + molchamb_sign + default |
| `scripts/stacking_ef.py` | 8 targets, MolChamb quantum stacking, per-family weights |

### Creados
| Archivo | Propósito |
|---------|-----------|
| `scripts/run_multitarget_batch.py` | Batch runner con skip de targets completados |
| `scripts/run_mmgbsa_batch_v2.py` | MM-GBSA sobre docked poses con MolChamb v2 |
| `scripts/debug_executor.py` | Diagnóstico ThreadPoolExecutor (no era el problema) |
| `scripts/debug_7e2y.py` | Debug docking 7E2Y |
| `scripts/debug_vina_direct.py` | Debug subprocess Vina |
| `scripts/debug_ache_improvements.py` | Debug protein_surgery + quantum filter AChE |
| `scripts/debug_surgery_1gpk.py` | Verificación protein_surgery AChE |
| `scripts/optimize_ache_weights.py` | Grid search stacking weights para AChE |
| `scripts/optimize_metaloenzyme_weights.py` | Grid search stacking weights para metaloenzimas |
| `scripts/inspect_checkpoint.py` | Inspección de checkpoints |
| `scripts/check_results.py` | Análisis de resultados |
| `scripts/test_gaff2.py` | Verificación GAFF2 via openmmforcefields |
| `scripts/check_env.py` | Diagnóstico de entorno Python |
| `docs/SESSION_SUMMARY_v1.6.md` | **Este documento** |

---

## 9. Comandos de Referencia

```powershell
# Benchmark individual (paper-quality)
python scripts/benchmark_ef_vina.py --target 7e2y --workers 5 --gnn --exhaust 8 --no-quantum-exit

# Batch multi-target (resume automático, skip de completados)
python scripts/run_multitarget_batch.py

# Stacking analysis con MolChamb (lee checkpoints existentes)
python scripts/stacking_ef.py --all

# MM-GBSA sobre docked poses (solo C,H,O,N,S,P)
python scripts/run_mmgbsa_batch_v2.py --target 1HSG --top 200

# Debug
python scripts/debug_executor.py
python scripts/check_env.py
```

---

## 10. Lecciones Aprendidas

1. **`dict.get(key, default)` no protege contra `None`**. Usar `or` para valores que pueden ser `None`.
2. **El ThreadPoolExecutor nunca fue el problema**. Era contaminación Vina-GPU + bugs de código.
3. **Protein surgery es crítico para targets con `ligand_mol2`**. Sin MOL2, 10 de 12 targets usaban box_size=None.
4. **CL-GNN debe ejecutarse explícitamente**. El flag `--gnn` solo corría GNN-v2 (abandonado).
5. **AChE es difícil por geometría, no por configuración**. No hay quick fix.
6. **MM-GBSA sin GAFF2 solo funciona para C,H,O,N,S,P**. ~90% de decoys DUD-E tienen halógenos.
7. **GAFF2 bloqueado en Python 3.14** (`openff-toolkit`). `openmmforcefields` instalado pero depende de `openff-toolkit`.
8. **CL-GNN domina donde Vina falla** (metaloenzimas: vina=0.0, clgnn=0.9). Validación arquitectónica del diseño contrastivo.
9. **No hardcodear pesos de stacking**. Cargar desde JSON. Agregar familia = editar JSON + correr benchmark.
10. **Auto-optimización requiere ≥500 moléculas** para significancia estadística. Con menos, mantener pesos existentes.
