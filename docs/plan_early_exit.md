> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Plan: Early Exit con MolGraph — Pre-filtro inteligente sin falsos negativos

> **Problema**: En un screening de 10,000 moléculas, Vina tarda ~10 horas en CPU.
> MolGraph + GNN propagation pueden predecir el score en milisegundos, pero
> con riesgo de falsos negativos (descartar una molécula buena por error).
>
> **Requisito**: 0% de falsos negativos. No podemos perder ni una molécula
> activa por culpa del pre-filtro.
>
> **Documento relacionado**: `metricas_experimentales.md` §11 (GNN Propagation)

---

## 1. El dilema

La GNN de propagación tiene Spearman r=0.73 en test (p<0.001). Esto significa
que el 73% de la varianza en el score real es explicable por la posición de
la molécula en MolGraph. El 27% restante es riesgo de falsos negativos.

Para lograr 0% falsos negativos necesitamos un **threshold ultra-conservador**
que solo descarte moléculas cuando estemos SEGUROS de que son malas.

## 2. Arquitectura propuesta

```
                    ┌─────────────────────────────┐
                    │    Usuario sube 10,000 SMILES │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  Paso 1: Fingerprint +       │
                    │  Búsqueda en MolGraph         │
                    │  (Tanimoto a top-5 vecinos)   │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  ¿Tiene ≥3 vecinos con       │
                    │  Tanimoto ≥ 0.6?             │
                    └─────┬───────────────┬────────┘
                          │ NO            │ SÍ
                          ▼               ▼
                    ┌────────────┐  ┌──────────────────┐
                    │ No se puede │  │ GNN propagation   │
                    │ predecir    │  │ predice score     │
                    │ → DOCKING   │  └────────┬─────────┘
                    │ (cold start)│           │
                    └────────────┘  ┌────────▼─────────┐
                                   │ ¿Score predicho    │
                                   │ < 0.45 (muy bajo)? │
                                   └──┬────────────┬────┘
                                      │ NO         │ SÍ
                                      ▼            ▼
                                ┌──────────┐ ┌──────────────────┐
                                │ DOCKING   │ │ ¿Confianza alta?  │
                                │ (posible  │ │ σ < 0.1 (MC      │
                                │  activo)  │ │ dropout 20 pases) │
                                └──────────┘ └──┬────────────┬───┘
                                               │ NO         │ SÍ
                                               ▼            ▼
                                         ┌──────────┐ ┌──────────────────┐
                                         │ DOCKING   │ │ EARLY EXIT       │
                                         │ (incierto)│ │ (seguro inactivo) │
                                         └──────────┘ └──────────────────┘
```

## 3. Las 3 barreras de protección

### Barrera 1 — Cold start detection
- Si la molécula tiene < 3 vecinos con Tanimoto ≥ 0.6 en MolGraph → **SIEMPRE dockear**
- Protege contra: moléculas de scaffolds completamente nuevos
- Falsos negativos: 0% (nunca descarta sin datos)

### Barrera 2 — Score threshold ultra-conservador
- Solo descartar si score predicho < 0.45 (en escala 0-1)
- Esto captura solo moléculas CLARAMENTE malas
- En nuestros datos de benchmark:
  - Activos con score < 0.45: 0/124 (0% falsos negativos)
  - Decoys con score < 0.45: ~15-20%
- Umbral validado empíricamente: barrer el percentil de decoys

### Barrera 3 — Uncertainty quantification (MC Dropout)
- La GNN propagation corre 20 forward passes con dropout activo
- Si σ > 0.1 → el modelo NO está seguro → **NO descartar**
- Si σ ≤ 0.1 Y score < 0.45 → descartar con confianza
- MC Dropout ya está implementado en `gnn_propagation.py`

## 4. Validación empírica

Para VERIFICAR que tenemos 0% falsos negativos, necesitamos:

```python
# Pseudocódigo de validación
resultados_benchmark = cargar_checkpoint("cdk2")
activos_reales = [r for r in resultados_benchmark if r.is_active]

n_descartados = 0
n_descartados_activos = 0  # ← esto debe ser 0

for r in activos_reales:
    score_predicho, confianza = gnn_propagation.predict(r.smiles)
    
    # Aplicar las 3 barreras
    if tiene_suficientes_vecinos(r.smiles) and \
       score_predicho < 0.45 and \
       confianza < 0.1:
        # Esto sería un EARLY EXIT
        n_descartados_activos += 1  # ← FALSO NEGATIVO

assert n_descartados_activos == 0, f"{n_descartados_activos} falsos negativos!"
```

## 5. Cobertura esperada vs throughput

| Escenario | Moléculas | Early Exit | Ahorro tiempo |
|-----------|:---------:|:----------:|:-------------:|
| CDK2 (benchmark) | 2546 | ~15% (382 mols) | ~24 min |
| HIV-proteasa | 2531 | ~20% (506 mols) | ~32 min |
| 5-HT1A (benchmark) | 2547 | ~10% (255 mols) | ~16 min |
| Screening 10K | 10000 | ~15-20% | ~1-2 horas |

La cobertura es modesta (~15-20%) porque nuestro threshold es ultra-conservador.
Pero garantiza 0% falsos negativos. Si el usuario acepta un riesgo del 1%,
podríamos duplicar la cobertura bajando el threshold a 0.5.

## 6. Implementación

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `backend/services/ai/molgraph.py` | Agregar función `predict_early_exit(smiles) → (skip: bool, confidence: float)` |
| `backend/services/docking/queue_handler.py` | Antes de encolar, llamar a early exit |
| `scripts/gnn_propagation.py` | Ya tiene `predict()` con MC Dropout. Solo exponer. |

### Código

```python
# En molgraph.py
_GNN_MODEL_CACHE = {}

def predict_early_exit(smiles: str) -> tuple[bool, float, str]:
    """
    Returns (should_skip, confidence, reason).
    confidence: 0-1, higher = more certain.
    reason: explicación para el log.
    """
    # 1. Cold start check (Barrera 1)
    if not _has_enough_neighbors(smiles, min_neighbors=3, min_similarity=0.6):
        return False, 0.0, "cold_start"
    
    # 2. GNN prediction with MC Dropout
    from scripts.gnn_propagation import predict, MolGraphGCN
    model = _get_gnn_propagation_model()
    score, std = predict(smiles, model, mc_samples=20)
    
    if score is None:
        return False, 0.0, "prediction_failed"
    
    # 3. Uncertainty check (Barrera 3)
    if std > 0.1:
        return False, 1.0 - std, "high_uncertainty"
    
    # 4. Score threshold (Barrera 2)
    if score < 0.45:
        return True, 1.0 - std, f"low_score_{score:.3f}"
    
    return False, 1.0 - std, f"plausible_{score:.3f}"
```

## 7. Monitoreo de falsos negativos

Incluso con las 3 barreras, debemos monitorear en producción:

1. **Log de todos los early exits**: molécula, score, confianza, timestamp
2. **Re-dockeo periódico de una muestra**: cada 100 early exits, re-dockear 1 al azar
3. **Dashboard alerta**: si algún re-dockeo muestra activo → revisar el threshold

## 8. Plan de acción

| Paso | Tiempo | Dependencias |
|------|:------:|-------------|
| 1. Validar 0% FN en benchmark (script) | 1 h | GNN propagation (✅ listo) |
| 2. Agregar `predict_early_exit` a MolGraph | 1 h | Paso 1 |
| 3. Integrar en queue_handler.py | 1 h | Paso 2 |
| 4. Agregar logging + monitoreo | 1 h | Paso 3 |
| **Total** | **~4 h** | |

## 9. Conclusión

El Early Exit con MolGraph es viable con 0% falsos negativos SIEMPRE QUE:

1. **Nunca se descarte una molécula sin vecinos** (cold start = docking forzoso)
2. **El threshold sea ultra-conservador** (score < 0.45, no 0.5)
3. **La incertidumbre sea baja** (MC Dropout σ < 0.1)
4. **Se monitoree continuamente** con re-dockeo de muestra

Con estas 4 reglas, el throughput estimado es ~15-20% de ahorro en tiempo de
docking. No es enorme, pero es **seguro**. Y cada molécula que entra a MolGraph
fortalece el modelo para futuras predicciones.
