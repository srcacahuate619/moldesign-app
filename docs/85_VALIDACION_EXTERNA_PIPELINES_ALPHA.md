# 85 — Validación externa de los pipelines M4, M5-Zn y Péptidos (alpha)

## PILOT-0

**Commit auditado:** `16d04521bfcac5a9ef8ad68da3c52376655368b6`
**Rama:** `claude/embedded-controls`
**Fecha:** 2026-09-10
**Protocolo prerregistrado:** `validation/protocols/alpha-controls-v1.json`
**SHA-256 del protocolo:** `7082e96154825ad3d6a07a4a0ac18d95981f4d6a78b9c38f1d2ff48aa4b26dcd`

Este conjunto de resultados se llama **PILOT-0**. Es un piloto: sirvió para
ejercitar el arnés y el protocolo, y **terminó bloqueado**. No es la corrida
cualificante.

> **NO EJECUTADO EN VM.** No hay hipervisor en este host (Hyper-V ausente, sin
> VirtualBox, sin VMware, WSL sin distribuciones). Lo ejecutado fue una copia
> íntegra del bundle fuera del árbol fuente (`D:\moldesign-audit\bundle-copy`,
> 35 051 ficheros, 1,754 GB). El §2 dice qué prueba y qué no prueba ese sustituto.

---

## 0. Resultado en una línea

**PILOT-0 terminó en `FALLO_TECNICO_DEL_RUNTIME`.** `queue_handler.py:368` llama
a `asyncio.to_thread(...)` y `asyncio` no está importado a nivel de módulo. Toda
corrida muere con `NameError` a ~0,2 s, antes de calcular propiedades y mucho
antes de docking. Lo introdujo `3f20933`, el commit inmediatamente anterior a
HEAD, titulado *«fix(evaluation): restore clean-VM runtime performance»*.

No corregí el defecto aquí: el encargo prohíbe mezclar validación con
implementación. (La corrección va en `claude/default-runtime-contract`.)

### Dos veredictos distintos, que no deben confundirse

| | Estado |
|---|---|
| **PILOT-0 como ejecución** | `FALLO_TECNICO_DEL_RUNTIME` |
| **M4 — veredicto científico** | **`NO_EVALUADO`** |
| **M5-Zn — veredicto científico** | **`NO_EVALUADO`** |
| **Péptidos — veredicto científico** | **`NO_EVALUADO`** |

`FALLO_TECNICO_DEL_RUNTIME` describe **esta ejecución**, no los pipelines. Los
pipelines no quedaron evaluados: no se midió su capacidad discriminativa, su
calibración, su dominio ni su abstención. `NO_EVALUADO` no es uno de los seis
veredictos permitidos del protocolo precisamente porque el protocolo asume que
hubo medición; aquí no la hubo, y forzar uno de los seis sería afirmar de más.

---

## 1. Qué se congeló antes de mirar nada

El protocolo se escribió y se selló **antes** de ejecutar el primer caso con
etiqueta. Su hash está en `validation/protocols/alpha-controls-v1.sha256` y
`scripts/qa_embedded_controls.py` lo recomprueba en cada arranque: si el fichero
cambió después de congelarse, el arnés aborta.

> **Límite honesto del prerregistro de PILOT-0.** El congelado por hash precede
> al piloto **según los timestamps locales** (protocolo sellado 19:39:40 UTC;
> primer caso con etiqueta después), pero el protocolo se **incorporó a Git
> después** de ejecutar el piloto. Un tercero que sólo mire el historial no puede
> verificar el orden. **La siguiente repetición será la primera prerregistrada en
> historial inmutable**, y por eso PILOT-0 no puede presentarse como evidencia
> ciega frente a terceros.

### 1.1 Auditoría de fuga

`validation/build_leakage_inventory.py` → `validation/leakage/seen_inventory.json`.

**760 identificadores PDB marcados SEEN**, leídos de 15 fuentes versionadas:

| Fuente | Qué aporta |
|---|---|
| `split_config.json` | 328 en CV + 328 en holdout congelado |
| `pdbbind_audit_report.json` | 752 complejos evaluados en curación (de 865 de PDBBind v2020 refined) |
| `m5_zn_manifest.json` | perfiles 1GKC, 1O86, 3DC3 |
| `data/benchmark_checkpoint_*.json` | 10 checkpoints que **seleccionaron pesos** |
| **`model-manifest.json`** | **dianas held-out nombradas en `metrics`** |
| `backend/tests/goldens/*.json` | salidas fijadas, memorizables |

Tres niveles, y la distinción importa: **complejo** (PDB exacto → `SEEN`),
**diana** (otro PDB de la misma proteína → `RELATED`), **familia** (se declara
siempre, no descalifica: enrutar por familia *es* el producto).

Dianas excluidas a nivel-diana: CA2, MMP9, ACE, 5HT1A, CDK2, ER-α, Factor Xa,
proteasa del VIH, trombina.

**No cubierto**, y por tanto no afirmado: preentrenamiento de ESM/ESMFold sobre
el PDB completo, PDBBind general fuera de los 865 refinados, y similitud de
scaffold ligando-ligando.

### 1.2 Corrección al propio inventario: `model-manifest.json` era una fuente de fuga

La primera versión del inventario no leía `model-manifest.json`. Sus `metrics`
nombran las dianas held-out con las que se evaluó CL-GNN:

```
gnn_v2_cl.auc_held_out_por_familia:
  gpcr_5HT1A_7E2Y = 0.8496      kinase_CDK2_3PP0 = 0.5942
  metalloenzyme_CA2_3dc3 = 0.5883   nuclear_receptor_ERalpha_3ERT = 0.6581
  protease_HIV_1HSG = 0.9491    protease_factorXa_3CYX = 0.7394
  protease_thrombin_1e66 = None
```

Una diana usada para **reportar** una AUC está expuesta aunque no se entrenara
sobre ella. Al añadir la fuente, SEEN pasó de 754 a **760** — y **3PP0 dejó de
ser EXTERNAL**. La sonda de runtime de PILOT-0 se corrió sobre 3PP0 creyéndolo
externo; no lo era. Como esa sonda no produjo resultado ni entró en ninguna
métrica, el error no contamina ninguna cifra, pero corrige la conclusión de
disponibilidad del §4.

*(Aparte: la etiqueta dice `kinase_CDK2_3PP0`, pero 3PP0 es el dominio quinasa de
HER2/ErbB2, no CDK2. La etiqueta del manifiesto está mal puesta.)*

### 1.3 Dos incoherencias en la procedencia del entrenamiento

1. **`split_config.json` describe 328 complejos en CV; `training_report.json`
   declara `train_pool = 537`.** Los folds enumeran 328 identificadores únicos,
   disjuntos del holdout. Faltan 209 por trazar. El número que sí cuadra es el de
   `pdbbind_audit_report.json`: 656 aceptados = 328 + 328.
2. **`/rescoring/info` devuelve `model_version: "unknown"` y `training_date`,
   `training_samples`, `ndcg_at_10`, `spearman` todos `null`**, aunque
   `training_report.json` viaja en el bundle con esos valores. El log lo confirma:
   `training_report_loaded version=unknown`.

---

## 2. Entorno

Registro completo en `validation/env/entorno-2026-09-10.json`.

**Sí prueba** — el bundle arranca sin ningún fichero del árbol fuente en
`sys.path`; el intérprete embebido no toma paquetes del *site-packages* del
usuario (`python311._pth` lo impide aunque `site.ENABLE_USER_SITE` sea `True`);
`resources/` es reubicable; y **el bundle no escribe dentro de `resources/`**
(huella de 35 051 ficheros idéntica antes y después: 0 nuevos, 0 modificados,
0 borrados).

**No prueba** — instalación limpia de Windows, ausencia de dependencias de
desarrollo, ausencia de runtimes de sistema, recursos limitados, ni arranque en
frío real de disco.

> **Agravante:** el host de esta auditoría **es el host de entrenamiento**.
> `training_report.json` declara 6 núcleos físicos / 12 lógicos y 31,9 GB —
> exactamente esta máquina. «Reproduce fuera del entorno de desarrollo» no es
> verificable aquí ni en principio.

**Medido:** Windows 11 Pro 10.0.26200 · AMD Ryzen 5 5500 (6C/12T) · 31,9 GB ·
GTX 1660 SUPER · Python embebido 3.11.9 · **AutoDock Vina 1.2.7** · Open Babel
3.1.1.23 · RDKit 2025.09.6 · arranque en frío **4,71 s** · 112 rutas en OpenAPI.

**Sin aceleración gráfica.** Hay GPU física, pero `/hardware` devuelve
`gpu.available = false`, `cuda = false`. Todo tiempo medido aquí es de CPU.

### 2.1 El arnés casi fabrica un defecto

En el primer intento `/health` devolvía **503** y `vina: {exists: false}` para un
binario que acababa de ejecutar. El fallo era **mío**:
`settings.vina_executable_path` vale `"tools/vina/vina.exe"` —relativo— y el CWD
es `<resources>/backend`. La aplicación de escritorio pasa
`VINA_EXECUTABLE_PATH` absoluto (`src-tauri/src/backend.rs`, ~L680). Corregido el
entorno, `/health` pasa a **200 healthy** y Vina a `healthy`.

`entorno_de_produccion()` es hoy traducción literal de `spawn_backend`, y
`--verificar-contrato-de-arranque` avisa si el lanzador cambia y el arnés no.
Estado: **OK**, sin variables divergentes.

> **Afecta también a `scripts/qa_vm_audit.py`**, que arranca sin
> `VINA_EXECUTABLE_PATH`, `APP_MODE` ni `ENVIRONMENT`. Su docstring dice que Vina
> ausente «es un fallo real si no está»; tal como está, reporta Vina ausente en
> bundles sanos. No lo toqué.

---

## 3. El defecto bloqueante

```
File "backend/services/docking/queue_handler.py", line 368, in _run_full_evaluation_async
    properties = await asyncio.to_thread(
                       ^^^^^^^
NameError: name 'asyncio' is not defined
```

El módulo importa `json`, `threading`, `uuid`, `ThreadPoolExecutor`… pero **no
`asyncio`**. Hay cinco `import asyncio as _asyncio` **locales** en otras
funciones (L175, L1004, L1402, L1431, L1566) que no ligan el nombre en
`_run_full_evaluation_async`.

```
3f20933 fix(evaluation): restore clean-VM runtime performance
-    properties = calculate_properties(smiles, run_admet_ai=run_admet_ai)
+    properties = await asyncio.to_thread(
+        calculate_properties, smiles, run_admet_ai=run_admet_ai
```

### 3.1 Paridad desarrollo / bundle: idénticos, y ambos rotos

`queue_handler.py` es **byte a byte idéntico** en el árbol fuente y en el bundle
(`sha256 9ccbb27a…3f0168`). Mismo caso en los dos entornos:

| | Árbol fuente + `python-embed` | Bundle aislado |
|---|---|---|
| preflight | 200 | 200 |
| submit | 202 | 202 |
| `smiles_hash` | `76003f2212a5…dec4bba` | `76003f2212a5…dec4bba` |
| desenlace | `FAILURE` | `FAILURE` |
| error | `name 'asyncio' is not defined` | `name 'asyncio' is not defined` |

La invariante *«desarrollo y embebido coinciden salvo reloj y rutas»* se
**cumple**. Coinciden en estar rotos: el defecto es de código fuente, no de
empaquetado.

### 3.2 Invariantes comprobables

| Invariante | Estado | Evidencia |
|---|---|---|
| Ningún error produce un valor fabricado | **CUMPLE** | `result: null` + `error` explícito; nunca un número |
| Las corridas terminan con causa explícita | **CUMPLE con reserva** | terminan, pero `name 'asyncio' is not defined` no es causa accionable para el usuario |
| El bundle no escribe en `resources/` | **CUMPLE** | huella idéntica; la BD va a `~\MolDesign\data` |
| Desarrollo y embebido coinciden | **CUMPLE** | §3.1 |
| Ningún `REVIEW_*` altera ranking | **NO COMPROBABLE** | ningún `REVIEW_*` alcanzable |
| Controles físicos sobre toda pose | **NO COMPROBABLE** | no se generó ninguna pose |
| Ausencia de modelo se informa | **CUMPLE parcialmente** | §5 |
| No se cambia la caja para pasar un control | **NO APLICA** | no se tocó ninguna caja |

`%SUCCESS = 0/5` frente al umbral prerregistrado `≥ 0,95`. **Bloqueante.**

---

## 4. Estructuras distribuidas ≠ cohorte EXTERNAL

> **Corrección a la primera versión de este informe.** Afirmaba que «sólo tres
> estructuras viajan en el bundle». **Era falso**: el conteo buscó `*.pdb` y no
> vio los `*.pdb.gz`, que son el 99 % del catálogo. La conclusión de
> disponibilidad que se derivó de ahí queda anulada.

Inventario en `validation/build_bundle_structure_inventory.py` →
`validation/leakage/bundle_structures.json`.

### 4.1 Conteos físicos — `resources/data/targets`

| Extensión | Ficheros |
|---|---|
| `.pdb` | 4 |
| `.pdb.gz` | 407 |
| `.pdbqt` / `.pdbqt.gz` | 0 |
| `.cif` / `.cif.gz` | 0 |
| **Total de estructura** | **411** |
| **PDB IDs distintos** | **407** |

**Confirmación específica:**

| PDB | ¿Distribuida? | Ficheros | Nivel de fuga |
|---|---|---|---|
| **1GKC** | **Sí** | `1gkc.pdb.gz`, `1gkc_chainA.pdb` | `SEEN` |
| **1O86** | **Sí** | `1o86.pdb.gz` | `SEEN` |
| **3DC3** | **Sí** | `3dc3.pdb.gz` | `SEEN` |
| 3PP0 | Sí | `3PP0.pdb.gz`, `3pp0_chainB.pdb` | `SEEN` (§1.2) |
| 7E2Y | Sí | `7E2Y.pdb.gz`, `7e2y_chainB/R.pdb` | `SEEN` |

> Consecuencia directa: **los tres controles de contrato de M5-Zn (1GKC, 1O86,
> 3DC3) sí pueden ejecutarse sin red.** La primera versión decía lo contrario
> para 1O86 y 3DC3; era falso.

### 4.2 Las dos propiedades son independientes

- **DISTRIBUIDA** — el fichero viaja; se puede abrir sin red. Propiedad del
  **empaquetado**.
- **EXTERNAL** — el complejo no aparece en ninguna fuente de exposición.
  Propiedad de la **procedencia científica**.

Una estructura puede ser ambas cosas a la vez o ninguna. **1GKC es DISTRIBUIDA y
SEEN.** Deducir independencia científica de la presencia en disco fue
exactamente el error de la primera versión, y por eso el inventario ahora emite
las dos columnas por separado y nunca una sola cifra.

De los 407 IDs distribuidos: **SEEN = 15**, **RELATED = 27**,
**EXTERNAL = 365 (cota superior)**.

> **365 es una cota superior, no una cohorte.** `RELATED` se calcula emparejando
> el `name` de `curated_targets.json` contra una lista corta de 9 dianas. Un PDB
> sin nombre curado, o cuyo nombre no menciona la diana, queda EXTERNAL siendo
> RELATED. La cifra **no sustituye a la curación manual** y no debe citarse como
> «hay 365 casos externos disponibles».

### 4.3 Lo que sigue faltando

La disponibilidad de estructura **no era el cuello de botella**; lo son las
**etiquetas experimentales**. El protocolo exige positivos, intermedios medidos e
**inactivos confirmados en el mismo ensayo**, con *property-matching*. Nada de eso
está aprovisionado. `data/dude_5ht1a_decoys.smi` —lo único parecido— es de una
diana RELATED y son decoys, admisibles sólo como estrés.

**No existe hoy cohorte externa curada**, y este informe no la simula. Lo que sí
cambia respecto a la primera versión: el trabajo pendiente es de **curación de
etiquetas**, no de empaquetado de estructuras.

---

## 5. CL-GNN: declarado en el manifiesto, ausente del bundle

**Formulación exacta**, porque la primera versión fue imprecisa:

- El **esquema** (`model-manifest.schema.json`) exige a nivel raíz
  `["manifest_version", "models"]`; es decir, exige que **exista la entrada**.
- El **manifiesto** (`model-manifest.json`) declara para `gnn_v2_cl` los campos
  `file: "gnn_v2_cl_best.pt"`, `metadata_file: "contrastive_v31_pretrained.pt"` y
  `metadata_sha256: 42df1158…`.
- **El bundle no contiene esos ficheros.** El verificador de integridad los
  reporta ausentes y `/health` marca `model_manifest: degraded`.
- **No existe ningún campo literal `required=true`.** La cadena `"required"`
  aparece **0 veces** en `model-manifest.json`. La obligatoriedad viene de que el
  esquema exige la entrada y ésta declara ficheros y hashes; no de una bandera.

Los pesos existen en `rescoring/artifacts/` del árbol fuente. No viajan porque
`.gitignore:224` excluye `rescoring/artifacts/*.pt` y el bundle copia rescoring
con política `git-tracked-only` (`runtime-manifest.json`). **Ningún bundle
construido así puede contenerlos.**

**Consecuencia científica.** `stacking_weights.json` define el perfil por defecto
como `{vina 0.2, xgb 0.6, clgnn 0.2}`. Sin CL-GNN, `scoring/engine.py`
renormaliza a `{vina 0.25, xgb 0.75}`, marca `stacking_degraded = True`, registra
`effective_weights` y emite `stacking_degraded_renormalized`.

- La invariante *«una ausencia de modelo se informa, nunca se sustituye»* se
  **cumple en la forma**: se informa, se marca, no se sustituye por otro modelo.
- Pero **el producto distribuido nunca ejecuta la función de puntuación cuyos
  pesos se seleccionaron**. Los `_auc` de `stacking_weights.json` se midieron con
  CL-GNN presente.

Esto es **lectura de código, no medida**: la renormalización no pudo observarse
en ejecución porque ninguna corrida llega al scoring. Queda como hipótesis
fundada, pendiente de confirmar.

---

## 6. Fase 3 — M5-Zn: contrato no verificable en PILOT-0

| Caso | Estado esperado | Observado |
|---|---|---|
| MMP9 / 1GKC | `REVIEW_INVALID_BENCHMARK_SITE` | `FAILURE` — `name 'asyncio' is not defined` |
| ACE / 1O86 | `REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING` | `FAILURE` — ídem |
| CA2 / 3DC3 | `NOT_EVALUATED_MISSING_COMPONENT` | `FAILURE` — ídem |

En los tres: preflight 200, submit 202, `result: null`. **No es que los estados
sean incorrectos: son inalcanzables.** Las tres estructuras están distribuidas
(§4.1), así que la repetición podrá hacerse sin red.

Se mantiene sin cambios lo ya declarado: **M5-Zn no está calibrado y ningún
perfil es científicamente liberable.** Nada aquí lo modifica.

### 6.1 Experimento para recuperar M5 — ciencia nueva, no corrección de M5-V1

Diseño, no ejecución. **No debe mezclarse con el perfil existente ni usarse para
reponderar M5-V1.**

1. **Caja anclada al Zn catalítico.** Centro en el ion catalítico identificado por
   su esfera de coordinación cristalográfica, no por el centroide del ligando.
   Semilado que garantice el zinc dentro **por criterio por eje** — el fallo de
   1GKC fue exactamente ése: `dz = −17,34` con semilado 12,5. Registrar la caja
   efectiva como artefacto; hoy ninguno la registra.
2. **Inhibidores con coordinación cristalográfica conocida**, con átomo donante y
   distancia al metal anotados desde la estructura.
3. **Activos e inactivos experimentales por diana**, del mismo ensayo,
   *property-matched*.
4. **Distancia mínima donante N/O/S–Zn** como observable de primera clase, umbral
   de coordinación **2,6 Å**, con el criterio laxo **4,0 Å** del corrigendum en
   paralelo.
5. **Coordinación en top-1 y top-N.** El checkpoint de ACE guardó sólo la top-1;
   hoy es imposible saber si alguna pose descartada coordinaba. Persistir top-N es
   requisito, no mejora.
6. **Ablación de UMS frente a features dependientes de pose.** En MMP9 el 0,75 del
   score depende de features de una pose fuera del sitio.
7. **Reconstrucción completa del benchmark** desde procedencia trazable, con el
   complejo cristalográfico incluido.
8. **Revisar si el zinc sobrevive a la preparación del receptor.** La preparación
   sí llegó a ejecutarse antes del `NameError`, y su log para 1GKC dice:
   `HETATM excluidos de la preparación del receptor — excluded: {"CA": 5,
   "NFH": 22, "ZN": 2}`. Los dos iones de zinc se excluyen como HETATM. Habría
   que determinar si el protocolo M5-Zn recupera el metal más adelante o si
   puntúa sobre un receptor sin él; con el runtime roto no se pudo comprobar, y
   la respuesta condiciona todo el punto 4.

La entrada genérica `metaloenzyme` se retiró de `stacking_weights.json` el
2026-09-04 y **no debe volver**. M5 va por perfil exacto o se abstiene.

---

## 7. Fase 4 — Péptidos: `NO_APROVISIONADO / NO_EJECUTADO`

> **Corrección.** La primera versión clasificaba la ausencia de pesos de ESMFold
> como defecto del bundle (T4). **Era incorrecto.**

`launcher-manifest.json` declara el módulo `esmfold-weights` con
**`required: false`**, `size_bytes: 8 442 062 570` (8,44 GB), destino
`esmfold/models/`, feature `peptide_docking`. **Es una descarga opt-in bajo
demanda.** Que una instalación base contenga sólo tokenizador y configuración
(4 ficheros, 2 336 bytes) es **comportamiento esperado**, no un defecto de
empaquetado.

Clasificación correcta de la fase:

- **Brazo A** (secuencia → ESMFold → transferencia → Vina):
  **`NO_APROVISIONADO`** — los pesos no se descargaron en este host.
- **Brazo B** (conformación cristalográfica → preparación → Vina):
  **`NO_EJECUTADO`** — bloqueado por el `NameError`, y sin cohorte LEADS-PEP
  aprovisionada.

Sin el brazo B no hay cota superior estructural, y sin ella no se puede separar
un fallo de plegamiento de uno de docking o ranking — el objetivo declarado de la
fase. Nada de pLDDT, RMSD, contactos de interfaz ni validez física es medible en
PILOT-0.

**Para la repetición:** aprovisionar ESMFold es una decisión de 8,44 GB, no un
arreglo de código.

---

## 8. Métricas

**No se reporta ninguna.** No hay ROC-AUC, PR-AUC, EF1 %, BEDROC, Spearman,
Kendall, RMSD, PoseBusters, MAE ni pendiente de calibración, porque no hay una
sola corrida con resultado. El bootstrap prerregistrado (10 000 réplicas, IC 95 %,
remuestreo por caso) queda sin sustrato. Las secciones se dejan vacías a
propósito: rellenarlas exigiría inventarlas.

De las tres semillas prerregistradas (42, 20260910, 7) **no se usó ninguna**. El
único determinismo observable es que el `smiles_hash` fue idéntico en las cuatro
sumisiones y en los dos entornos.

---

## 9. Veredictos

**PILOT-0 como ejecución: `FALLO_TECNICO_DEL_RUNTIME`.**

**M4, M5-Zn y Péptidos: `NO_EVALUADO`.** No se midió su capacidad
discriminativa, calibración, dominio ni abstención. La palabra «validado» no
aparece en este informe aplicada a ningún pipeline.

Que M5-Zn siga sin perfil científicamente liberable **no** es conclusión de
PILOT-0: es lo ya documentado en el corrigendum del sitio del benchmark, y se
mantiene intacto.

---

## 10. Recomendaciones, separadas por naturaleza

### 10.1 Defectos técnicos

| # | Defecto | Evidencia |
|---|---|---|
| **T1** | `import asyncio` ausente en `queue_handler.py`; rompe el 100 % de las evaluaciones. Introducido por `3f20933`. | §3 |
| **T2** | Ninguna prueba cubre `_run_full_evaluation_async` de extremo a extremo: un `NameError` en la ruta principal llegó a HEAD. Es el defecto de proceso, y es más grave que T1. | §3 |
| **T3** | CL-GNN: el manifiesto declara ficheros y hashes que ningún bundle puede contener (`.gitignore:224` + `git-tracked-only`). | §5 |
| **T5** | `/rescoring/info` sirve `model_version: "unknown"` y métricas `null` teniendo `training_report.json` en el bundle. | §1.3 |
| **T6** | `runtime-manifest.json` dice `1.0.0`; la API dice `1.0.0-alpha.2`. | §2 |
| **T7** | `scripts/qa_vm_audit.py` no fija `VINA_EXECUTABLE_PATH`/`APP_MODE`/`ENVIRONMENT`: reporta Vina ausente en bundles sanos. | §2.1 |
| **T8** | `curated_targets.json` declara cadena A para 3PP0; el fichero empaquetado es `3pp0_chainB.pdb`. | §4 |
| **T9** | `split_config.json` (328 en CV) contradice `training_report.json` (`train_pool = 537`); 209 complejos sin trazar. | §1.3 |
| **T10** | `model-manifest.json` etiqueta `kinase_CDK2_3PP0`, pero 3PP0 es HER2/ErbB2, no CDK2. | §1.2 |

**T4 (ESMFold) se retira:** era comportamiento esperado, no defecto (§7).

### 10.2 Falta de datos

- **D1** — No hay cohorte externa **curada**. Las estructuras no son el cuello de
  botella (365 IDs distribuidos son EXTERNAL como cota superior); lo son las
  etiquetas.
- **D2** — No hay inactivos experimentales aprovisionados para ninguna diana. Sin
  ellos no hay ROC-AUC, PR-AUC, EF1 % ni BEDROC honestos.
- **D3** — LEADS-PEP no está aprovisionada; sin ella no hay brazo B.
- **D4** — Para M5-Zn falta el complejo cristalográfico de ACE y la caja efectiva
  de ambos benchmarks; el checkpoint sólo guardó la top-1.
- **D5** — ESMFold (8,44 GB) no está descargado. Decisión de aprovisionamiento.

### 10.3 Recalibración

**Ninguna, y es deliberado.** No se midió nada; recalibrar sobre esta ejecución
sería recalibrar sobre el vacío. El protocolo además prohíbe usar esta cohorte
para ajustar.

Lo que sí queda pendiente, y es política y no recalibración: **qué significa
distribuir un producto cuyo perfil de stacking por defecto nunca puede
ejecutarse tal como se validó** (§5). Empaquetar CL-GNN o declarar el perfil
degradado como el real y revalidarlo son excluyentes, y ambas son decisión de
producto.

### 10.4 Ciencia nueva

- **C1** — Experimento de recuperación de M5 (§6.1), como línea separada.
- **C2** — Cohorte externa curada para M4: tres receptores de familias distintas,
  con activos/intermedios/inactivos del mismo ensayo y *property-matching*. Debe
  pasar por `build_leakage_inventory.py` **antes** de docking — y ese inventario
  debe incluir `model-manifest.json`, que en PILOT-0 faltaba (§1.2).
- **C3** — Cohorte de péptidos con los dos brazos.

---

## 11. Entregables de PILOT-0

| # | Entregable | Ruta | Estado |
|---|---|---|---|
| 1 | Protocolo prerregistrado + hash | `validation/protocols/alpha-controls-v1.json{,.sha256}` | Completo; historial en §1 |
| 2 | Manifiesto de controles y fuentes | `validation/cohorts/*.json`, `validation/leakage/*.json` | Parcial — sondas y contrato; sin cohorte externa curada (§4.3) |
| 3 | Arnés reproducible | `scripts/qa_embedded_controls.py`, `validation/run_case.py`, `validation/build_*.py` | Completo |
| 4 | Resultados crudos | `validation/results/*.json` | Completo para lo ejecutado |
| 5 | Logs del backend embebido | `validation/results/logs/*.log` | Completo |
| 6 | Tabla desarrollo vs VM | §3.1 | Parcial — **desarrollo vs copia aislada**; no hay VM |
| 7 | Métricas con IC | §8 | **Vacío**, justificado |
| 8 | Lista de fugas | `validation/leakage/seen_inventory.json` (760 SEEN) | Completo |
| 9 | Informe | este documento | Completo |
| 10 | Veredicto por pipeline | §9 | Completo (`NO_EVALUADO` ×3) |
| 11 | Recomendaciones separadas | §10 | Completo |

### Cómo reproducir

```bash
robocopy frontend\src-tauri\resources D:\moldesign-audit\bundle-copy /E /MT:8

python validation/build_leakage_inventory.py
python validation/build_bundle_structure_inventory.py

python scripts/qa_embedded_controls.py --modo COPIA_AISLADA \
    --bundle D:/moldesign-audit/bundle-copy --fase 0

python validation/run_case.py --modo COPIA_AISLADA \
    --bundle D:/moldesign-audit/bundle-copy \
    --casos validation/cohorts/fase3_m5zn_contrato.json \
    --out validation/results/fase3_m5zn.json
```

---

## 12. Qué haría falta para la corrida cualificante

1. Corregir **T1** en otra rama, con una prueba de extremo a extremo que falle
   antes del arreglo (**T2**).
2. Decidir **T3**: empaquetar CL-GNN o revalidar el perfil degradado.
3. Aprovisionar una **VM Windows limpia** de verdad, y aislar la red durante las
   corridas científicas.
4. Curar la cohorte externa (**D1**, **D2**) y pasarla por el inventario de fuga
   —incluido `model-manifest.json`— antes de tocar el docking.
5. Decidir sobre **D5** (ESMFold, 8,44 GB) si se quiere el brazo A.
6. Volver a ejecutar **este mismo protocolo**, sin editarlo, con el prerregistro
   ya en historial inmutable. Su hash (`7082e961…4b26dcd`) es lo que hace
   comparables las dos ejecuciones.

El protocolo, el arnés y los inventarios son reutilizables tal cual. Falta un
runtime que ejecute y una cohorte curada.
