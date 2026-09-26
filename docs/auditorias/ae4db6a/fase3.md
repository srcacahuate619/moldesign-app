# Fase 3 — bitácora de corrección local

Fecha: 2026-09-24/25 (America/Mexico_City). Auditoría base: `ae4db6a7aef0f4c14af7b74da350578abbd80074`.

## Rama y alcance

- Rama: `codex/audit-phase-3`, worktree `D:\moldesign-build\.worktrees\audit-phase-3`.
- Padre local de fase 2: `65a9db3dc810499fe3b1e7b5a07c7259ebaa2c8e`.
- Commit local de fase 3: `33204b062313c2aa8ae40e70eff0e3b5dba4c0fe`.
- Árbol de trabajo limpio al cerrar. No hubo `push` ni integración a `main`; la decisión corresponde al auditor.
- Los temporales de las pruebas se dirigieron a `D:\moldesign-build\.worktrees\audit-phase-3\.tmp` mediante `TEMP`, `TMP`, `TMPDIR`, `XDG_CACHE_HOME` y `MPLCONFIGDIR`; se desactivó la escritura automática de bytecode. Se evitó otra suite monolítica después del reinicio del equipo.

## Cambios y motivos

### 3.1 SCORE-002

MM-GBSA ya había sido retirado del `total_score` en fase 0. Se comprobó que permanece informativo; no se reintrodujo el factor con signo errado.

### 3.2 SCORE-005, SCORE-009 y SCORE-013

- `backend/scoring/engine.py`: el producto `affinity_score × stacking_factor` se divide por 1.5 antes del total. Conserva la escala de 0–100 sin recortar artificialmente la cabeza del ranking. El contrato declara que `total_score` sólo es comparable con los mismos pesos efectivos.
- Batch y SAR ordenan primero las filas con stacking completo y después las degradadas. Batch expone `stacking_degraded`, pesos efectivos y aviso de mezcla. Para EF en un lote mixto se usa la señal común `affinity_score`, identificada en el resultado, en lugar de mezclar totales de escalas distintas.
- El multiplicador por hotspots sólo se aplica si la fuente es `curated_experimental`. El catálogo actual usa fuentes automáticas; sus residuos siguen siendo información de la pose, pero no alteran el ranking ni disparan avisos que los llamen críticos. El snapshot tolera receptores históricos sin `hotspots_source` mediante `None`.

### 3.3 SCORE-001: AD reconstruido y verificado

El artefacto anterior tenía 172 features y procedía de 263 filas; extraer un subbloque de su **matriz de precisión** no equivale a invertir la covarianza marginal de los siete descriptores evaluados. Se reemplazó por un artefacto 7D sobre el pool Fase A de 537 complejos. `rescoring/scripts/build_applicability_domain.py` reconstruye el archivo de forma determinista y tiene `--check`.

Se trató el informe de Gemini como hipótesis. Verificación independiente local:

1. SHA-256 del CSV recibido: `178e39247b80e6515e75962ded33b63395d087e1d1b5e301a0a95e02219ed501`; índice Fase A: `1c52a9b7631cc11a31c6b3344ececa3de8a9087c86ab3e6c5a30dc69861de02d`; partición `split_config.json`: `bbc57126e2306e087dcddb76478a8cddfbd36fb7de3f350806b6366ee3534f6f`.
2. El índice tiene 865 IDs únicos; el holdout, 328; el CSV, 537. Se comprobó igualdad exacta `CSV = índice − holdout`, sin duplicados ni intersección.
3. Se volvieron a calcular los siete descriptores de **las 537 estructuras** con RDKit 2025.09.6 y las funciones de `train_families.py`: cero estructuras ausentes y cero discrepancias numéricas. Los JSON de los modelos servidos también coinciden con sus hashes del manifiesto (`model_a_universal`: `d2041777857586065aa29dcc8b876a9c1e89394dacbf517e9c071e5cba27f0b2`; `classifier_binder`: `b83a936564036b196b53919c707250c441d49fbd1b9427b15f7ebe48850ea636`).
4. Ledoit-Wolf se ajusta en las siete columnas; el p99 de distancias en cinco pliegues fuera de muestra con semilla 42 fue **3.6725**. La aceptación pedida por el auditor reveló que ese umbral excluía 6 % de 5.000 muestras gaussianas generadas con la covarianza ajustada. Se fijó el umbral final como el máximo entre ese p99 y el referente analítico `sqrt(χ²₇,0.99)`: **4.2983**. Se guardan ambos valores y la regla. Con semilla 42, la fracción excluida del control gaussiano es **0.8 %**; aspirina queda dentro (`d=1.4172`). La prueba de aceptación quedó versionada para impedir la regresión.
5. Hash final de `rescoring/artifacts/applicability_domain.json` (4.925 bytes): `c1ab9adf7bc7c6d127a6e58cbe272eba67400d1ba57c48fbfdc1712a4a491698`. El manifiesto de modelos subió a v5, incluye y verifica este hash, el hash del CSV y los vínculos con ambos modelos. Hash del manifiesto: `75550d28c21bf2362ee3fc1e924ef6add22e3a2ef8af521be67fe06ef5e65bd2`. El runtime staged exige y sella AD como archivo crítico.
6. La carga real de `ModelManager` con los modelos JSON del worktree informó `has_ad=True`, el hash esperado y `status=evaluated` para el centroide.

Verificación adicional en un servidor Ubuntu propio: se copiaron CSV, índice, split, modelos JSON, AD y manifiesto a un directorio compartido [dirección y ruta del servidor omitidas en la copia publicada]. Un verificador Python sin dependencias externas volvió a comprobar hashes, partición, medias y `cov × cov_inv`; error máximo de identidad `1.4253e-15`. El Python base de ese servidor no tenía NumPy ni scikit-learn, de modo que el ajuste estadístico y la prueba gaussiana se repitieron localmente con el Python embebido, no en el servidor.

Matiz de procedencia: los metadatos de los modelos indican **429 filas de ajuste y 108 de validación** dentro del pool de desarrollo de 537. AD se ajustó con las 537, como pedía SCORE-001; los 328 del holdout congelado quedaron fuera. Por ello la validación de AD sobre esas 108 filas no sería independiente. No se afirma validez externa del dominio químico fuera de los controles indicados.

### 3.4 SCORE-012

Si el registro científico sellado no carga, el motor usa las constantes `STACKING_WEIGHTS` del código, registra un error y persiste `weights_source`, hash del registro (si existió) e ID de calibración. Ya no usa silenciosamente el espejo JSON sin sellar.

### 3.5 SCORE-014, SCORE-016, SCORE-017 y SCORE-019

- El aviso categórico de LLE se retiró: un pK derivado del score de Vina no tiene un corte experimental validado. La ambigüedad de poses requiere tanto energías casi iguales como separación RMSD >2 Å. Los hotspots automáticos no generan lenguaje de evidencia experimental.
- El contexto del informe IA usa los valores de score persistidos para no reinterpretar un total calculado con entradas diferentes.
- SHAP queda rotulado y trazado por hash como explicación del **Model A de delta-pKi**. El PDF dice explícitamente que no explica el clasificador ni `total_score`; no se atribuye falsamente al ranking.
- M5-Zn recibe el estado AD y la validez de features. Si XGBoost está fuera de dominio, no evaluado o sin 3D válido, su componente no entra y el protocolo se abstiene de producir `m5_score`.
- El fallo de extracción 3D deja de convertirse en un vector completo de ceros; la predicción se abstiene según el contrato de features. Esto atiende la ruta principal de SCORE-006, sin declarar cerradas aquí todas sus variantes históricas.

### 3.6 ORQ-002

`backend/scoring/enriquecimiento.py` concentra EF fraccional y ROC-AUC con rango medio en empates. Batch, cohortes y scripts lo usan. Las métricas se separan por diana, declaran exclusiones/fallos en el denominador y nunca forman un ranking global entre receptores. Una identidad `row_id` evita perder ligandos repetidos con nombres/SMILES iguales al calcular EF.

### 3.7 ENG-A09, ENG-A10 y ENG-A11

El panel normal, streaming e individual repite exhaustiveness, número de poses y semilla del protocolo Vina principal. Si falta ese protocolo, la corrida usa otro motor o es un ensemble no reproducible por el panel, se abstiene. Cada anti-diana registra protocolo, sitio/cadenas y procedencia de caja. Se persiste `ΔΔG` del margen exploratorio. El titular PDF usa ese margen y una banda de incertidumbre declarada en lugar del cociente obsoleto de dos scores negativos. Se advierte que scores Vina entre receptores distintos no son energías libres experimentales.

## Pruebas y puertas

- Pytest dirigido, con temporales en D:: AD/manifiesto/entrenador **50 pasaron**; batch/cohortes **143 pasaron, 1 omitida**; PDF/reporte/M5 **50 pasaron, 5 omitidas**; rescoring/contrato de features/API **52 pasaron**; selectividad/protocolo **47 pasaron**; dossier/pipeline/M5 **199 pasaron, 1 omitida** y un fallo de compatibilidad de fixture detectado, corregido y repetido (**3 pasaron**). Otros grupos dirigidos de API/esquema/scoring **61 pasaron**, y el grupo final de runtime/fase 3/manifiesto **22 pasaron**. Estos grupos se solapan; no son un total único de la suite.
- `generate_model_manifest.py --check`: manifiesto v5 verificado. `build_applicability_domain.py --check`: artefacto reproducido byte a byte. `generate_goldens.py --check`: **8 corridas doradas** verificadas. `check_stacking_weights_ui.py --check`: 7 familias verificadas. `git diff --check`: sin errores.
- El primer intento del gate de goldens señaló `m5_zn_replay.json` porque en el worktree faltaban tres checkpoints de datos ignorados por Git; el generador los declaraba ausentes. Se copiaron los tres archivos existentes de `D:\moldesign-build\data\` al worktree en D: (217 MB en total, ignorados por Git), se repitió el gate y pasó sin editar ningún golden.
- No se ejecutó la suite completa tras el reinicio ni se fabricó instalador. `frontend/` de este worktree no tiene `node_modules`, `out/` ni `src-tauri/resources`, por lo que `smoke:prod` no podría inspeccionar un artefacto de esta rama. La aceptación de empaquetado queda pendiente para el auditor cuando materialice el runtime y haga la build en un entorno con espacio. En particular, la nueva entrada crítica AD de `bundle_helper.py` fue revisada y sus pruebas de código pasaron, pero no se afirma verificación sobre un instalador.

## Decisiones abiertas para revisión

1. El AD 7D mide similitud fisicoquímica respecto al pool Fase A; no evalúa similitud estructural ni garantiza calibración de afinidad del clasificador. El holdout de 328 no se usó para ajustar AD.
2. En batch, si los componentes ML no son homogéneos, EF utiliza `affinity_score` y lo declara. Una evaluación externa por diana con señuelos controlados sigue siendo trabajo científico separado; esta fase corrige la mecánica de ranking y métricas.
3. SHAP sigue explicando Model A; se corrigió la atribución del PDF. No se calculó SHAP del clasificador, porque ese sería un nuevo resultado científico que necesita validación propia.
4. Las comparaciones anti-diana siguen siendo exploratorias, aun con protocolo Vina homogéneo; el margen no debe interpretarse como selectividad experimental.
