# Fase 6: decisión provisional del ranking M4 (2026-09-25)

## Decisión

El ranking genérico M4 de release usa Vina 1.0, XGBoost 0.0, GNN legacy
0.0 y CL-GNN 0.0 en todas las familias. El clasificador XGBoost y
CL-GNN pueden ejecutarse y registrarse como señales experimentales;
sus probabilidades no modifican total_score. M5-Zn conserva su
protocolo separado. Esta decisión sustituye el contrato M4 alpha v1,
cuyos pesos 0.25/0.75 eran una renormalización de un perfil histórico,
no una calibración de la combinación distribuida.

## Evidencia que sí se reprodujo

El protocolo se fijó antes de calcular métricas en
docs/89_FASE6_PREREG_CLASIFICADOR.md (commit 183a57d). Se utilizó el
índice Fase A original de PDBbind, el split congelado 537/328, los 160
descriptores originales, el modelo exacto SHA-256
b83a936564036b196b53919c707250c441d49fbd1b9427b15f7ebe48850ea636
y poses cristalográficas. El experimento reproducible está en
scripts/phase6_classifier_holdout.py (commit 3f626c3; SHA-256
8ff8289663d1b349bf6e71f1c6af4dcf73af13e26c0d937a7f2e7f1c4a6c4e2e).
Matriz SHA-256
9ee1917995ff6a3b38ebf0f21b076f75b5bee6d6acb2c26a574a70a2f6501851.
Las salidas están en el corrigendum externo,
evidencia_fase6/score007_native.

| Estrato | N | ROC-AUC | IC 95 % por bootstrap de clúster proteico | Brier | ECE 10 |
|---|---:|---:|---:|---:|---:|
| Holdout completo | 328 | 0.8818 | 0.8292–0.9270 | 0.1370 | 0.0649 |
| Clúster visto en entrenamiento | 233 | 0.8852 | 0.8214–0.9388 | 0.1386 | 0.1009 |
| Clúster no visto | 95 | 0.8544 | 0.7408–0.9373 | 0.1332 | 0.1079 |

El AUC completo difiere del 0.8818 registrado por 0.0000049. Las
métricas son **del clasificador sobre poses cristalográficas**. No
miden ranking de la aplicación, pose Vina, mejora incremental frente
a Vina ni calibración bajo prevalencia de cribado.

## Fórmula exacta del resultado distribuido

Sea a la afinidad Vina en kcal/mol y h el número de átomos pesados.
A(a,h) es normalize_affinity: una función de eficiencia de ligando
a/h, con centro y pendiente dependientes de h y penalización por
afinidad débil. v = min(1, abs(a)/12). Con los pesos de release vigentes:

    stacking_raw    = 1.0*v + 0.0*p_XGB + 0.0*p_GNN + 0.0*p_CLGNN
    stacking_factor = 0.5 + stacking_raw
    total_score     = clamp_0_100(A(a,h) * stacking_factor / 1.5
                                  * specificity_multiplier)

En el caso ordinario specificity_multiplier=1. Sólo hotspots con
procedencia curated_experimental pueden cambiarlo. El resultado es
función de Vina y tamaño del ligando; no debe describirse como un
promedio lineal 100 % de la energía Vina. Vina entra tanto en
A(a,h) como en v; 1.0 es el peso **dentro del factor de stacking**,
no una fracción de influencia global. La afinidad y total_score
siguen siendo métricas de priorización computacional, no potencias
experimentales ni probabilidades de unión.

## Puerta para volver a dar peso a ML

Requiere poses producidas por el pipeline de release, separación por
familia proteica y diana, modelo identificado por hash, pesos fijados
fuera del conjunto de evaluación, comparación directa con esta base
Vina, intervalos de incertidumbre y un análisis de calibración bajo
la prevalencia prevista. El resultado cristalográfico de esta fase
no satisface esa puerta. El registro conserva v1 como historial,
declara v2 y lleva un nuevo config_hash; el espejo, el fallback de
emergencia y la interfaz coinciden con v2.
