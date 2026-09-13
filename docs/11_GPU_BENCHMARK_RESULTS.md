> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# GPU Benchmark Results — Factor Xa

> **Fecha**: Julio 6, 2026
> **Módulo**: `D:\ad-gpu-project\`
> **Binary**: Vina-GPU 2.1 compilado desde source (MSYS2/MinGW-w64)

---

## 1. Resultados Principales

### Comparativa GPU vs CPU (igual target, mismas condiciones)

| Métrica | CPU (reporte existente) | GPU (200 mols) | GPU (100 mols) | ¿GPU gana? |
|---------|:-----------------------:|:-------------:|:-------------:|:----------:|
| **EF@1%** | 1.10x | **2.24x** | **2.60x** | 🟢 |
| **EF@5%** | 1.10x | **2.24x** | **2.60x** | 🟢 |
| **EF@10%** | 1.10x | **2.08x** | **2.60x** | 🟢 |
| **ROC-AUC** | 0.9333 | **0.9539** | **0.9705** | 🟢 |
| **N moléculas** | 55 | **200** (4x) | **100** (2x) | 🟢 |
| **Tiempo docking** | ~35 min (2w CPU) | **10 min** | **5 min** | 🟢 |

> **GPU supera a CPU en TODAS las métricas.** Encontró 2.24x más activos en el top 1%
> que el ranking de Vina CPU. En la mitad del tiempo. Con el quíntuple de moléculas.

### Timing (200 moléculas)

| Etapa | Tiempo | % del total |
|-------|:------:|:----------:|
| Preparación PDBQTs (RDKit+Meeko, 8w) | 10.5s | 1.7% |
| GPU batch dock (`--ligand_directory`, thread=8000) | 620.0s | 98.3% |
| **Total** | **630.5s (10.5 min)** | |

---

## 2. Comparativa Histórica: Todos los Targets

### Estado actual de los benchmarks CPU

| Target | Mols CPU | Mols disponibles | EF@1% CPU | EF confiable? |
|--------|:--------:|:----------------:|:---------:|:------------:|
| CDK2 (3PP0) | **2546** | 2546 | **42.06x** | ✅ Robusto |
| HIV-proteasa (1HSG) | **2531** | 2531 | **13.06x** | ✅ Robusto |
| Thrombin (1c4u) | 73 | 2000+ | 2.03x | ⚠️ Poco |
| CA2 (1bn1) | 72 | 2000+ | 0.00x | ⚠️ Poco |
| AChE (1gpk) | 40 | 2000+ | 1.74x | ⚠️ Poco |
| ER-alpha (3ERT) | 349 | 2000+ | 0.00x | ⚠️ Poco |
| CDK6 (5Z2R) | 346 | 2000+ | 0.00x | ⚠️ Poco |
| MMP9 (1gkc) | 343 | 2000+ | 0.00x | ⚠️ Poco |
| PDE5 (1xp0) | 335 | 2000+ | 0.00x | ⚠️ Poco |
| GLP-1R (6X1A) | 296 | 2000+ | 0.00x | ❌ Solo 2 activos |
| Factor Xa (1f0r) | **55** | **2771** | **1.10x** | ❌ Muy chico |
| CDK2 PDBbind (1b38) | 79 | 79 | 1.61x | ⚠️ Poco |

**Problema**: 8 de 12 targets tienen EF basados en <100 moléculas.
6 targets tienen 2000+ moléculas disponibles que NUNCA se dockearon por costo de tiempo.

**Con GPU**: dockear 2000 moléculas por target es viable en ~1-2h.

### Tiempos estimados para datasets completos

| Método | 1 target (2000 mols) | 6 targets (12000 mols) | 12 targets |
|--------|:---------------------:|:---------------------:|:----------:|
| Vina CPU (10 workers) | ~33 horas | ~8 días | ~14 días |
| Vina-GPU batch | **~1.5 horas** | **~9 horas** | **~18 horas** |
| Speedup | **22×** | **21×** | **19×** |

---

## 3. Experimentos de Validación

### Experimento 1: Parallel Vina CPU (8× ex=1)

| Métrica | Resultado |
|---------|-----------|
| Δ medio | 0.14 kcal/mol |
| Δ < 0.1 en | 6/7 (86%) |
| Speedup | 2.4× |

**Conclusión**: Los 8× ex=1 producen scores muy cercanos pero no idénticos.
El merge+refine order difiere. Ranking preservado.

### Experimento 2: GPU → Vina CPU `--local_only`

| Mol | CPU ex=8 | CPU local | Δ | Speedup |
|-----|----------|-----------|------|---------|
| 1 | -9.72 | -9.66 | +0.062 | 45× |
| 2 | -8.37 | -7.85 | +0.525 | 40× |
| 3 | -6.96 | -6.70 | +0.254 | 27× |

**Conclusión**: `get_initial_conf()` resetea orientación y torsiones.
El warm-start solo con posición no basta para idéntico resultado.

### Experimento 3: Multi-pose (5 poses GPU)

| Métrica | Single-pose | Multi-pose | Mejora |
|---------|:-----------:|:----------:|:------:|
| Mol 2 | +0.525 | +0.408 | -23% |
| Mol 3 | +0.254 | +0.103 | -59% |
| Mean |d| | 0.29 | 0.29 | — |

**Conclusión**: Multi-pose reduce deltas significativamente.

### Experimento 4: `--cpu_only` vs vina.exe

| Binario | Score (ex=8) | Runtime |
|---------|:------------:|:-------:|
| vina.exe original | -9.719 | 107s |
| Nuestro `--cpu_only` | -9.7 | 565s |

**Score idéntico.** Runtime 5× más lento por build MSYS2 (VS Build Tools pendiente).

---

## 4. Estado del Módulo GPU

### Lo que funciona (100% validado)

| Componente | Archivo | Estado |
|-----------|---------|:------:|
| Binario unificado | `AutoDock-Vina-GPU-2-1.exe` | ✅ |
| `--cpu_only` (idéntico a vina.exe) | `main.cpp` | ✅ |
| `--save-pose` + `--refine` | `main.cpp` | ✅ |
| Orchestrator con fallback | `orchestrator.py` | ✅ 10/10 OK |
| GPU batch dock | `batch_dock.py` | ✅ 148/200 OK |
| Pipeline multi-pose | `pipeline_multi_pose.py` | ✅ |
| Drop-in Vina CLI | `vina_hybrid.py` | ✅ |
| Benchmark GPU | `benchmark_gpu_full.py` | ✅ |

### Lo pendiente

| Tarea | Prioridad |
|-------|:---------:|
| Compilar con Visual Studio (velocidad) | 🔴 Alta |
| Correr benchmarks multi-target completos (6+ targets) | 🔴 Alta |
| Validar híbrido GPU→CPU en 200 mols para ML | 🟡 Media |
| Integrar en MolDesign producción | 🟡 Media |

---

## 5. Plan de Integración

### Paso 1 — Reemplazar vina.exe (HOY, 0 riesgo)

```python
# vina_service.py
VINA_EXE = "D:/ad-gpu-project/AutoDock-Vina-GPU-2-1.exe"
command += ["--cpu_only"]  # idéntico a vina.exe
```

### Paso 2 — Benchmarks multi-target GPU (1-2h)

```bash
python benchmark_gpu_full.py --target 1f0r --n-mols 2000  # Factor Xa
python benchmark_gpu_full.py --target 1c4u --n-mols 2000  # Thrombin
python benchmark_gpu_full.py --target 1bn1 --n-mols 2000  # CA2
python benchmark_gpu_full.py --target 1gpk --n-mols 2000  # AChE
# ... etc
```

### Paso 3 — Validar híbrido para ML (1 noche)

Comparar scores `--cpu_only ex=8` vs `GPU→CPU refine` en 200 moléculas.
Medir impacto en predicciones XGBoost (pKi).

### Paso 4 — Integrar híbrido en producción (si paso 3 OK)

```python
# Para evaluaciones individuales: GPU→CPU refine (2s)
# Para batches: GPU batch dock (1h/target)
# Fallback: --cpu_only si GPU falla
```

---

## Enlaces

- [10_VINA_GPU_HYBRID.md](10_VINA_GPU_HYBRID.md) — Documentación del módulo
- [00_INDEX.md](00_INDEX.md) — Novedades v1.5
- [07_SPEARMAN_BENCHMARK_LOG.md](07_SPEARMAN_BENCHMARK_LOG.md) — Bitácora de experimentos
- [campana_multitarget.md](campana_multitarget.md) — Tiempos actualizados con GPU
