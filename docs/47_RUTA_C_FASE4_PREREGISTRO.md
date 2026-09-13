# Ruta C — Fase 4: pre-registro de rescoring directo a pose cristalina

**Estado:** activo, experimental; no cambia el selector operativo `pose_selector_v06`.

**Antecedentes:** [doc. 41](41_RUTA_C_INVESTIGACION_CAMPO.md), [protocolo y resultados anteriores](42_RUTA_C_PROTOCOLO.md) y [atlas de errores Fase 4.A](../scripts/artifacts_ruta_c_fase4_error_atlas.json).

## Decisión metodológica

El objetivo de producto sigue siendo `Top-1 global (RMSD <= 2.0 Å) >= 0.70`, no la exactitud condicionada tras abstenerse. El baseline operativo e inmutable es v0.6 XGBRanker: **31/47 = 0.6596** en el histórico conjunto de desarrollo. Alcanzar 0.70 en esos 47 casos exige dos aciertos netos adicionales (`33/47 = 0.7021`).

El atlas reproducible separó los 16 fallos de v0.6:

| Tipo | Casos | Implicación |
|---|---:|---|
| Fallo de ranking con una pose <=2 Å disponible | 10 | Rescoring puede recuperarlo. |
| Sin pose <=2 Å entre los candidatos | 6 | Requiere mejorar generación/docking, no sólo rescoring. |
| Pose seleccionada correctamente | 31 | No debe degradarse. |

Cinco de los diez fallos recuperables ya tienen una pose válida entre el top-3 de v0.6. La densidad de cluster no mostró una dirección consistente en esos errores; por tanto se descarta añadir una regla manual de consenso geométrico en esta iteración.

## Límite de validez actual

Los 47 complejos de `poses_test.jsonl` se han observado en v0.6, tres variantes GNN y políticas de abstención. Por esa repetición, se denominan **test de desarrollo histórico**, no confirmación ciega de una hipótesis futura. Pueden describir el techo y el error, pero no se volverán a consultar durante esta fase de selección.

Una mejora que supere posteriormente 0.70 en ese conjunto sólo será una señal de desarrollo. Antes de una afirmación científica o de producto deberá confirmarse en un nuevo conjunto externo/secuestreado, construido y bloqueado antes de medirlo.

## Hipótesis H-C1.1

El v0.6 actual aprende `-RMSD` continuo. La métrica que interesa es discreta: que la pose elegida sea cristalina (`RMSD <=2.0 Å`). Optimizar de forma directa esa relevancia binaria con el mismo espacio relativo de 233 features puede recuperar poses nativas cercanas sin reabrir la línea GNN ni introducir dependencia GPU.

Esta hipótesis es falsable: si no mejora de modo consistente la validación agrupada, se cierra. No se sustituye el modelo operativo por una mejora de desarrollo.

## Diseño congelado antes de ejecutar

- Datos de selección: sólo `poses_train.jsonl` (116 complejos, 2,739 poses).
- Transformación: idéntica a v0.6: 224 features físicas, z-score intra-complejo y nueve rangos percentiles (233 en total).
- Partición: cinco folds deterministas, estratificados por la existencia de una pose <=2 Å y agrupados estrictamente por complejo. Ninguna pose de un complejo aparece en train y evaluación del mismo fold.
- Capacidad congelada: XGBoost CPU, `seed=42`, 52 árboles, profundidad 6, learning rate 0.05, subsample 0.8, cuatro hilos. Son los 52 árboles retenidos por early stopping en v0.6; no hay barrido de hiperparámetros ni de semillas.
- Modelos comparados:
  1. `continuo_pairwise`: `rank:pairwise`, relevancia `-RMSD`; control que reproduce el objetivo anterior con capacidad igual.
  2. `native_pairwise`: `rank:pairwise`, relevancia binaria `RMSD <=2 Å`.
  3. `native_ndcg`: `rank:ndcg`, misma relevancia binaria; optimiza explícitamente la cabeza de la lista.
- Métricas OOF: Top-1 global, Top-1 condicionado a que exista candidato cristalino, RMSD mediana, Spearman por complejo y comparación pareada exacta frente al control.
- Integridad: se guarda SHA-256 de `poses_train.jsonl`, `poses_val.jsonl`, modelo y metadata v0.6. El script no abre `poses_test.jsonl`.

## Reglas de decisión

1. Un objetivo nativo avanza sólo si logra **al menos tres aciertos netos OOF** sobre `continuo_pairwise` y no empeora la RMSD mediana en más de 0.10 Å. El ganador se elige por Top-1 OOF; empates por RMSD mediana y después Spearman.
2. Sólo ese ganador se ajusta con los 116 complejos train y se mide **una vez** sobre los 40 complejos `val`.
3. Pasa la validación de desarrollo sólo con al menos **25/40 = 0.625** Top-1: dos aciertos sobre el v0.6 histórico de val (`23/40 = 0.575`).
4. Si no pasa cualquiera de los gates, se conserva v0.6 y se registra el resultado negativo. No se prueba una retícula posterior de parámetros u objetivos en esta fase.
5. Incluso si pasa, no hay promoción automática ni lectura del histórico test. La siguiente decisión será crear el conjunto confirmatorio independiente y registrar sus hashes antes de puntuarlo.

## Artefactos

- Ejecutor: `scripts/ruta_c_fase4_direct_native.py`.
- Resultado incremental y no sobrescribible por defecto: `scripts/artifacts_ruta_c_fase4_direct_native.json`.
- Atlas previo: `scripts/ruta_c_fase4_error_atlas.py` / `scripts/artifacts_ruta_c_fase4_error_atlas.json`.

La Fase 4 no modifica `rescoring/artifacts/pose_selector_v06.xgb`, `pose_selector_v06_meta.json`, `model-manifest.json` ni el sidecar de producción.

## Resultado H-C1.1 — cerrado

Ejecutado el 2026-08-15 mediante `scripts/ruta_c_fase4_direct_native.py`; integridad y resultado completo en `scripts/artifacts_ruta_c_fase4_direct_native.json`. El script verificó que `test_historico_leido` fuera `false`.

| Objetivo | Top-1 OOF | Aciertos | RMSD mediana | Cambio neto frente al continuo |
|---|---:|---:|---:|---:|
| Control continuo pairwise | 0.4397 | 51/116 | 2.5885 Å | — |
| Nativo pairwise | 0.4397 | 51/116 | 2.3740 Å | 0 |
| Nativo NDCG | 0.4483 | 52/116 | 2.3420 Å | +1 |

Ningún candidato alcanzó los tres aciertos netos OOF predefinidos; por tanto `val` no se consumió y H-C1.1 se **cierra como negativa**. El mejor resultado (`native_ndcg`) tuvo 9 recuperaciones y 8 degradaciones frente al control (McNemar exacto bilateral = 1.0). Cambiar el objetivo de entrenamiento, sin añadir información nueva, no es una ruta justificable a 0.70.

## Hipótesis H-C4.1 — ensamble de rangos con Vina

El atlas observó complementariedad, aunque v0.6 ya contiene features de Vina: sobre los 47 casos históricos, v0.6 recupera 9 errores de Vina y degrada 3 aciertos de Vina. Se probará si esa diversidad residual se convierte en ganancia **antes** de mirar de nuevo el test histórico.

- Base OOF: exactamente el `continuo_pairwise` de H-C1.1, entrenado en los mismos cinco folds train.
- Ensamble por complejo: suma convexa de rangos normalizados; `alpha * rango_v06 + (1-alpha) * rango_vina`, con rango mayor = mejor.
- Pesos congelados: `alpha = 0.00, 0.25, 0.50, 0.75, 1.00`. `1.00` es el control v0.6 OOF y `0.00` es Vina puro. No se exploran más pesos, umbrales ni reglas condicionales.
- Gate OOF: un peso distinto de 1.00 debe producir >=3 aciertos netos sobre el control y RMSD mediana no peor por más de 0.10 Å.
- Si pasa, sólo ese peso se ajusta con v0.6 entrenado en todo train y se mide una vez en val; requiere >=25/40 Top-1. Si falla, H-C4.1 queda cerrada sin leer test histórico.
- Ejecutor: `scripts/ruta_c_fase4_vina_ensemble.py`; artefacto: `scripts/artifacts_ruta_c_fase4_vina_ensemble.json`.

## Resultado H-C4.1 — cerrado

Ejecutado el 2026-08-15. El peso `alpha=0.75` fue el único que cumplió el gate OOF: **54/116** frente a **51/116** del control, con tres recuperaciones y ninguna degradación (McNemar exacto bilateral = 0.25), y RMSD mediana 2.2390 Å frente a 2.5885 Å. Por la regla preregistrada se realizó una única lectura de `val`.

En `val` obtuvo **23/40 = 0.575**, idéntico al v0.6 histórico y por debajo de los 25/40 exigidos. H-C4.1 queda **cerrada como negativa**. El artefacto confirma `test_historico_leido: false`; el split histórico de 47 no se consultó.

## Conclusión operativa de la Fase 4

Dos formas baratas de reordenar las **mismas 233 señales** han fallado con gates fijados de antemano: cambiar la pérdida por etiqueta nativa y fusionar v0.6 con Vina. No es científico insistir ahora con pesos, semillas, umbrales o heurísticas derivadas de esos mismos datos.

La siguiente fase debe añadir evidencia nueva, con dos líneas separadas:

1. **Rescoring C1 físico direccional (CPU):** construir y validar features de interacción que el vector actual no representa explícitamente —geometría donador–aceptor, aromaticidad/orientación, cargas/estados de protonación y penalización conformacional del ligando— antes de entrenar un ranker. La actual `pop_*_hb` es sólo un proxy N/O por distancia.
2. **Generación de poses:** seis de 47 casos no contienen candidato <=2 Å; ningún rescoring puede resolverlos. Medir por fuente y por receptor la cobertura/oráculo de poses y atacar esos vacíos sin confundirlo con una mejora del selector.

Antes de medir una nueva variante en el conjunto histórico de 47, se deberá crear, hashear y secuestrar un conjunto confirmatorio externo. Hasta entonces, v0.6 sigue siendo el único selector operativo y no se realizan anuncios de `>=0.70`.

El inventario que precede a cualquier descriptor nuevo está en
[`48_INVENTARIO_REUTILIZACION_MOLFLEX_RESCORING.md`](48_INVENTARIO_REUTILIZACION_MOLFLEX_RESCORING.md). Su primer experimento propuesto reutiliza MolFlex como generador de candidatos y Ruta C como selector, con gates separados para cobertura y ranking.
