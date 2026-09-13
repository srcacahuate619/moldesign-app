# DESIGN — Campaña 2: cascada física v0.6 → decidibilidad → strain → MM/GBSA-like selectivo

**Fecha:** 2026-08-16 (revisión IT1 — decisiones definitivas del maintainer)
**Rama:** `experimentos/ruta-c-molflex`
**Tipo de artefacto:** diseño preliminar + preregistros base + decisiones IT1. **NADA se ejecuta
en este entregable** (0 cómputo físico, 0 inferencia, 0 entrenamiento).
**Manifest:** `CAMPANA-2-PLAN` (status `created`, sin seal, sin finish).
**Protocolo:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §14 Campaña 2 +
RS-01B sellada (NO_GO) como evidencia de entrada + IT1/DECISIONS (§7).

---

## 1. Orden de Campaña 2 — decisión del maintainer (aplicado)

`docs/49` §14 lista la Campaña 2 como: (1) auditar charge_source/probe
xTB/OpenMM, (2) RS-03 MM-GBSA top-K, (3) RS-04 strain, (4) RS-08
decidibilidad. **El maintainer decide otro orden** y este diseño lo respeta:

0. **RS-04-QC** — etapa técnica previa a RS-04 (train-only, sin labels):
   mapeo atómico, H, cobertura MMFF, determinismo y coste cold-start.
1. **RS-04 strain** — señal barata: ¿la penalización conformacional
   (energía docked vs mínimo aislado) ayuda a seleccionar poses?
2. **RS-08 decidibilidad** — router de escalamiento (control
   presupuestario), entrenado/evaluado dentro de los 5 folds sellados.
3. **RS-03-PARAM** — PRERREQUISITO OBLIGATORIO de RS-03: parametrización
   de ligando validada (OpenFF Sage + NAGL congelado; referencia AM1-BCC).
4. **RS-03 MM/GBSA-like top-K** — solo donde tenga oportunidad de aportar,
   con coste y fallos parametrizados (nomenclatura: "rescoring MM/GBSA-like
   de pose única" hasta completar RS-03-PARAM).
5. **Cascada integrada** — v0.6 → decidibilidad → strain → MM/GBSA-like
   selectivo, con los gates de cada etapa.

Justificación del orden (maintainer): la señal más barata (strain MMFF,
milisegundos por pose) se evalúa primero porque su gate incremental OOF
decide si merece la pena escalar; la decidibilidad define el contrato de
escalamiento como control presupuestario; MM/GBSA-like (el componente caro,
minutos por pose) solo entra en top-K del 30% de mayor riesgo y tras la
parametrización validada. Evita comenzar por el componente más caro
(principio docs/49:353).

---

## 2. Cascada integrada (diagrama de flujo)

```
          complejo + poses (unión ORIGINAL 3469 — IT1/QA-1)
                           │
                           ▼
                 ┌─────────────────────┐
                 │   v0.6 CONGELADO     │  checkpoint pose_selector_v06.xgb
                 │  (XGBRanker 233 feats)│  sha 9827DDB9… (NO se entrena)
                 └──────────┬──────────┘
                            │ top-1 + margen + 18 agregados
                            ▼
                 ┌─────────────────────┐
                 │ RS-08 ROUTER (riesgo)│  entrenado/evaluado DENTRO de los
                 │ P(riesgo) por fold   │  5 folds sellados RS-01B; umbral
                 └──────┬───────┬──────┘  SOLO del outer-train (IT1/QA-3)
            70% menor  │       │ 30% mayor riesgo (política primaria)
             riesgo    │       ▼
                 │     │  ┌──────────────────────────┐
                 │     │  │ RS-04 STRAIN (tras RS-04-QC)│
                 │     │  │  N1: MMFF94s docked−iso    │  ms/pose; solo H optimizados
                 │     │  │  (xTB-strain = experimento │  en la pose; pesados fijos
                 │     │  │   selectivo aparte, NO     │  (IT1/QA-5)
                 │     │  │   fallback de MMFF)        │
                 │     │  └──────────┬────────────────┘
                 │     │             │ señal OOF incremental sobre v0.6
                 │     │             ▼
                 │     │  ┌──────────────────────────┐
                 │     │  │ RS-03-PARAM (prerrequisito)│  OpenFF Sage + NAGL
                 │     │  │ validada → habilita RS-03  │  congelado por versión+sha
                 │     │  └──────────┬────────────────┘
                 │     │             ▼
                 │     │  ┌──────────────────────────┐
                 │     │  │ RS-03 MM/GBSA-like SELECTIVO│
                 │     │  │  top-2 (600 s/complejo) o   │  single-trajectory,
                 │     │  │  top-3 ablación (900 s)     │  maxIterations=200,
                 │     │  │  solo escalados; fallo →    │  timeout 300 s/pose
                 │     │  │  conserva v0.6 (ITT)        │  (IT1/QA-4)
                 │     │  └──────────┬────────────────┘
                 │     │             │
                 ▼     ▼             ▼
                 ┌──────────────────────────────────┐
                 │  SELECCIÓN FINAL por complejo     │
                 │  v0.6 directa (70% menor riesgo)  │
                 │  o con desempate físico (escalados)│
                 └──────────────────────────────────┘
```

**Regla de escalamiento (IT1/QA-3):**
- Política primaria: escala el **30% de mayor riesgo** (por P del router).
- Dentro de cada outer fold, el umbral sale EXCLUSIVAMENTE del outer-train.
- Tras OOF: se congela un `t_router*` full-train que reproduzca el
  presupuesto del 30%.
- El margen de v0.6 es **FEATURE del riesgo**, no un segundo umbral
  ajustado en val.
- Reportar curva de sensibilidad a 10%, 20% y 40%.
- La decidibilidad es **control presupuestario**: "en qué casos vale la
  pena gastar física adicional", no "confío/no confío".

**Nota crítica heredada de Fase 3.5:** la abstención por decidibilidad fue
REFUTADA (SIN_MEJORA_HONESTA, artifacts_ruta_c_fase3_5.json). RS-08 NO la
reabre como abstención (docs/49 RS-08: "debe disparar más muestreo, no
sólo abstención"). Los umbrales históricos 0.24158/0.399889 quedan SOLO
como comparadores descriptivos, jamás gates primarios (IT1/QA-3a).

---

## 3. Preregistros base (SIN ejecutar)

### 3.1 RS-04 — Strain de pose (MMFF94s primario; xTB-strain selectivo aparte)

- **Hipótesis:** la energía conformacional de la pose docked penaliza
  falsos mínimos que v0.6 no distingue; la señal es OOF incremental sobre
  v0.6 (docs/49:204).
- **Feature primaria (por pose):** `strain_mmff = E_MMFF94s(pose docked,
  solo H optimizados) − E_MMFF94s(mínimo aislado)`.
- **Contrato químico (IT1/QA-5):**
  - topología, órdenes de enlace, estereoquímica y cargas formales desde
    **SDF/SMILES sanitizado** (nunca inferidas de PDBQT);
  - mapeo heavy-atom **biyectivo y verificado** contra la pose;
  - `AddHs(addCoords=True)`;
  - en la pose docked se optimizan **SOLO los H** (pesados fijados);
  - fuerza **MMFF94s**;
  - referencia aislada: `Nconfs = min(200, max(50, 10×rotatable_bonds))`,
    ETKDGv3, seed 42, optimización completa, mínimo energético;
  - `MMFFHasAllMoleculeParams == false` → `unsupported_mmff` (NO se mezcla
    UFF en la feature primaria — energías no comparables);
  - halógenos NO se excluyen por nombre: decide la cobertura real de MMFF;
  - strain negativo NO se trunca a cero: dispara UNA ampliación del search
    de referencia, y si persiste, fallo QC;
  - resultados separados **neutros vs ionizados** (MMFF frágil en
    cargadas);
  - **xTB-strain = segundo experimento selectivo, NO fallback de MMFF.**
- **Gate operacional RS-04 (IT1/QA-6):**
  - cross-fitting COMPLETO (no leave-complex-out parcial): mismos 5 folds
    sellados de RS-01B (sha `9d97ad70…`); baseline v0.6 y modelo aumentado
    sobre exactamente los mismos complejos; preprocesamiento/imputación/
    coeficientes ajustados DENTRO del outer-train;
  - val40 y D-RC-CONFIRM CERRADAS;
  - configuración XGBoost congelada (aislar el efecto del strain);
  - Top-1 OOF ≥ **50/116** (47+3);
  - mediana pareada ΔRMSD ≤ **+0.1 Å**;
  - cobertura química ≥ **95%**;
  - MMFF cold-start P95 ≤ **5 s/ligando**; cacheado P95 ≤ **100 ms/pose** y
    ≤ **3 s/complejo**;
  - sin regresión grave por estrato hard/control.
  - GO de desarrollo posible; "mejora científicamente demostrada" exigiría
    además que el intervalo agrupado excluya cero o una ejecución única
    sobre cohorte confirmatoria intacta.
- **Entradas:** unión ORIGINAL 3469 (IT1/QA-1), checkpoint v0.6 congelado
  (sha `9827DDB9…`), extractor de 224 features v0.5 (no reentrenar).

### 3.2 RS-04-QC — etapa técnica previa (train-only, SIN labels)

- Alcance: las **2739 poses train** de la unión original.
- Verificaciones: mapeo atómico biyectivo, manejo de H, cobertura MMFF
  (`MMFFHasAllMoleculeParams`), determinismo (2 corridas byte-idénticas),
  coste cold-start P50/P95.
- Si pasa → RS-04 OOF completo. Si falla → corregir el pipeline antes de
  gastar evaluación.

### 3.3 RS-08 — Decidibilidad como router de escalamiento (IT1/QA-3)

- **Hipótesis:** un router de riesgo entrenado/evaluado dentro de los folds
  identifica el 30% de complejos donde la física adicional tiene más
  oportunidad de aportar; la decidibilidad es control presupuestario.
- **Contrato (decidido):**
  - umbrales históricos 0.24158/0.399889 → SOLO comparadores descriptivos;
    jamás gates primarios ni recalculados en val40 (cohorte consumida);
  - router entrenado/evaluado DENTRO de los 5 folds sellados
    (scaffold+receptor agrupados);
  - política primaria: escala el **30% de mayor riesgo**;
  - sensibilidad reportada a 10%, 20% y 40%;
  - dentro de cada outer fold, el umbral sale EXCLUSIVAMENTE del
    outer-train;
  - tras OOF, se congela un `t_router*` full-train que reproduzca el
    presupuesto del 30%;
  - el margen de v0.6 es FEATURE del riesgo, no un segundo umbral ajustado
    en val.
- **Reutilización SIN reentrenar v0.6:** los 18 agregados se calculan a
  partir de scores v0.6 y features congeladas sobre la unión original; el
  checkpoint NO se toca. El clasificador de riesgo se reajusta por fold
  (LogReg de Fase 3.5 como referencia de arquitectura; coeficientes
  históricos NO se reutilizan como gates).
- **Costo:** agregados + entrenamiento LogReg por fold sobre ~116
  complejos: minutos.

### 3.4 RS-03-PARAM — parametrización de ligando validada (PRERREQUISITO de RS-03)

- **Objetivo (IT1/QA-2e):** reemplazar el tipado heurístico de
  `molchamb_v2.py:65` (aproxima éteres como hidroxilos) por una
  parametrización de ligando validada.
- **Objetivo desktop:** OpenFF Sage + modelo NAGL congelado por versión y
  SHA-256; referencia de validación AM1-BCC en subconjunto estratificado.
- **Hasta completar RS-03-PARAM**, la implementación se llama **"rescoring
  MM/GBSA-like de pose única"** (nomenclatura del maintainer); NO se usa
  el término "MM-GBSA validado" en Campaña 2.
- **Provenance de cargas (IT1/QA-2a, reemplaza `has_molchamb`):**
  `charge_method, formal_charge, uhf, engine_version, model_hash,
  atom_order_hash, charge_sum, runtime, fallback_reason`.
- **Reglas de carga (IT1/QA-2b-d):**
  - la carga formal proviene del ligando sanitizado; NUNCA se presupone
    cero (`--chrg 0` actual en scripts/compute_quantum_features.py:118 es
    incorrecto para ionizadas);
  - si xTB falla, el resultado primario es **missing/failed**; cargas
    Gasteiger solo como sensibilidad secundaria, nunca sustituto
    silencioso;
  - verificar que la suma de cargas corresponda a la carga formal.

### 3.5 RS-03 — MM/GBSA-like selectivo top-K (IT1/QA-4)

- **Hipótesis:** `compute_mmgbsa_from_pose` (OpenMM, amber14-all +
  implicit/gbn2, docs/49:203) desempata el top-K de los complejos del 30%
  de mayor riesgo, donde la señal v0.6 es ambigua (docs/48:97 E-REUSE-2).
- **Alcance estricto:** SOLO complejos escalados por el router (RS-08).
  Primario **top-2** con presupuesto máximo **600 s/complejo**; **top-3**
  ablación secundaria con máximo **900 s/complejo**.
- **Contrato por pose (decidido):**
  - `maxIterations = 200`;
  - tolerancia de convergencia **10 kJ/mol/nm**;
  - timeout duro **300 s/pose**;
  - fallo físico → **conserva la selección v0.6** y se contabiliza ITT
    (nunca energía cero);
  - SDF de pose real obligatorio (docs/48:93);
  - elementos fuera de C/H/O/N/S/P → missing/failed parametrizado;
  - provenance de cargas IT1/QA-2a (ver §3.4).
- **PROTOCOLO single-trajectory (cambio principal):**
  - minimizar UNA vez el complejo;
  - calcular complejo, receptor y ligando sobre ESAS mismas coordenadas;
  - NO re-minimizar receptor/ligando por separado (el código actual lo
    hace en `molchamb_v2.py:571` — introduce energía de reorganización);
  - registrar desplazamiento RMSD por minimización; si una pose se deforma
    excesivamente, no puede "ganar" por dejar de ser la pose evaluada.
- **Gate (preregistro base):** mejora OOF/val del Top-1 solo en los
  complejos escalados, con costo total y fallos ITT parametrizados; sin
  mejora → NO se extiende el MM/GBSA-like (principio "no costo
  indiscriminado").
- **Restricción de sistema:** OpenMM + pdbfixer + rdkit (runtime
  verificado); GPU GTX 1660 SUPER auto-detectada; CPU-only estimado
  >180 s por complejo (queue_handler comment).

---

## 4. Nota narrativa corregida del maintainer (rama dedup)

> **"La deduplicación preserva el oráculo y no mostró degradación de la
> mediana pareada, pero no se demostró equivalencia ni mejora del
> rescoring."**

Contexto sellado (RS-01B, NO_GO): Top-1 OOF dedup 43/116 vs original
47/116 (Δ −4 < +3); mediana pareada de RMSD 0.000 Å (lectura exacta: "sin
evidencia de degradación en la mediana pareada", NO compatibilidad ni
equivalencia); McNemar p = 0.4807; BCa por 38 componentes [−8.80, 4.00].
Consecuencia para Campaña 2 (IT1/QA-1, decidida): **la unión ORIGINAL
(3469) es el brazo primario**; la dedup (2413) queda solo como **ablación
de coste** secundaria. Ningún preregistro asume ventaja de la dedup.

---

## 5. Métricas comunes (todos los experimentos)

- **Primarias:** Top-1 OOF por cross-fitting COMPLETO (5 folds sellados
  RS-01B), mediana PAREADA de RMSD (guardia dura del maintainer; nunca
  diferencia de medianas ni suma como gate).
- **Costo:** costo por complejo y por pose por etapa; gates de coste de
  RS-04 (cold-start P95 ≤5 s/ligando; cacheado P95 ≤100 ms/pose y ≤3
  s/complejo); presupuestos por complejo de RS-03 (600/900 s).
- **Fallos:** fallos ITT por etapa (unsupported_mmff, xTB missing/failed,
  MM/GBSA-like timeout/elemento no soportado; nunca energía cero).
- **Estratos:** hard/control de D-MF-HARD SIEMPRE por separado (congelado
  3 de Campaña 1); cohorte de evaluación = D-MF-HARD (22+22).
- **Cuarentena:** D-RC-CONFIRM (FND-05) SELLADA INTOCADA; val40 CERRADA
  para recalibración (cohorte consumida, IT1/QA-3a/QA-6); test histórico
  de Ruta C no se toca para elegir (docs/48 salvaguardas).
- **Label-blind:** las etiquetas solo evalúan (práctica de Campaña 1).
- **Determinismo:** seed 42, corridas reproducibles, hashes de inputs y
  outputs; RS-04-QC exige 2 corridas byte-idénticas.

---

## 6. Restricciones de este entregable

- 0 cómputo físico (MM/GBSA-like/xTB/strain), 0 inferencia, 0
  entrenamiento, 0 docking, 0 red, 0 pip.
- Sin commits, sin seal, sin finish. Manifest `CAMPANA-2-PLAN` en
  `created` + `validate` OK.
- Nada sellado se edita: solo lectura y referencias con hash.

---

## 7. IT1/DECISIONS — decisiones definitivas del maintainer

**QA-1 (decidida):** unión ORIGINAL 3469 primaria; dedup 2413 solo
ablación de coste.

**QA-2 — Cargas y parametrización:** (a) sustituir `has_molchamb` por
provenance estructurada: `charge_method, formal_charge, uhf,
engine_version, model_hash, atom_order_hash, charge_sum, runtime,
fallback_reason`; (b) la carga formal proviene del ligando sanitizado,
NUNCA se presupone cero (`--chrg 0` actual en
scripts/compute_quantum_features.py:118 es incorrecto para ionizadas);
(c) PROHIBIDO cargas Gasteiger a modo de sustituto silencioso: si xTB
falla, el resultado primario es missing/failed; Gasteiger = sensibilidad
secundaria; (d) verificar que la suma de cargas corresponda a la carga
formal; (e) **RS-03-PARAM como PRERREQUISITO OBLIGATORIO de RS-03**:
reemplazar el tipado heurístico de molchamb_v2.py:65 por parametrización
de ligando validada — objetivo desktop: OpenFF Sage + modelo NAGL
congelado por versión y SHA-256, referencia de validación AM1-BCC en
subconjunto estratificado; hasta completar RS-03-PARAM, la implementación
se llama "rescoring MM/GBSA-like de pose única".

**QA-3 — Decidibilidad:** (a) umbrales históricos 0.24158/0.399889 SOLO
comparadores descriptivos, jamás gates primarios ni recalculados en val40
(cohorte consumida); (b) el router se entrena/evalúa DENTRO de los 5 folds
sellados (scaffold+receptor agrupados); (c) política primaria escala el
30% de mayor riesgo; (d) reportar sensibilidad a 10%, 20% y 40%; (e)
dentro de cada outer fold, el umbral sale EXCLUSIVAMENTE del outer-train;
(f) tras OOF, se congela un t_router* full-train que reproduzca el
presupuesto del 30%; (g) el margen de v0.6 es FEATURE del riesgo, no un
segundo umbral ajustado en val. La decidibilidad es control
presupuestario: "en qué casos vale la pena gastar física adicional", no
"confío/no confío".

**QA-4 — MM/GBSA-like:** maxIterations=200; tolerancia 10 kJ/mol/nm;
timeout duro 300 s/pose; primario top-2 con presupuesto máx 600
s/complejo; top-3 ablación secundaria máx 900 s/complejo; fallo físico →
conserva selección v0.6 y se contabiliza ITT (nunca energía cero).
**PROTOCOLO single-trajectory (cambio principal):** minimizar UNA vez el
complejo; calcular complejo, receptor y ligando sobre ESAS mismas
coordenadas; NO re-minimizar receptor/ligando por separado (el código
actual lo hace en molchamb_v2.py:571 — introduce energía de
reorganización). Registrar desplazamiento RMSD por minimización; si una
pose se deforma excesivamente, no puede "ganar" por dejar de ser la pose
evaluada.

**QA-5 — Strain MMFF:** topología, órdenes de enlace, estereoquímica y
cargas formales desde SDF/SMILES SANITIZADO (nunca inferidas de PDBQT);
mapeo heavy-atom biyectivo y verificado contra la pose;
AddHs(addCoords=True); en la pose docked se optimizan SOLO los H (pesados
fijados); fuerza MMFF94s; referencia aislada: Nconfs = min(200, max(50,
10×rotatable_bonds)), ETKDGv3, seed 42, optimización completa, mínimo
energético; MMFFHasAllMoleculeParams == false → unsupported_mmff (NO se
mezcla UFF en la feature primaria — energías no comparables); halógenos NO
se excluyen por nombre (decide la cobertura real de MMFF); strain negativo
NO se trunca a cero — dispara UNA ampliación del search de referencia, y
si persiste, fallo QC; resultados separados neutros vs ionizados (MMFF
frágil en cargadas); xTB-strain = segundo experimento selectivo, NO
fallback de MMFF.

**QA-6 — Validación OOF:** cross-fitting COMPLETO (no leave-complex-out
parcial): mismos 5 folds sellados de RS-01B; baseline v0.6 y modelo
aumentado sobre exactamente los mismos complejos;
preprocesamiento/imputación/coeficientes ajustados DENTRO del
outer-train; val40 y D-RC-CONFIRM cerradas; configuración XGBoost
congelada (aislar el efecto del strain). **Gate operacional RS-04:**
Top-1 OOF ≥ 50/116 (47+3); mediana pareada ΔRMSD ≤ +0.1 Å; cobertura
química ≥95%; MMFF cold-start P95 ≤5 s/ligando; cacheado P95 ≤100 ms/pose
y ≤3 s/complejo; sin regresión grave por estrato hard/control. GO de
desarrollo posible; "mejora científicamente demostrada" exigiría además
que el intervalo agrupado excluya cero o una ejecución única sobre cohorte
confirmatoria intacta.

**RS-04-QC (nueva etapa previa a RS-04 OOF, técnica, train-only, SIN
labels):** mapeo atómico biyectivo, manejo de H, cobertura MMFF
(MMFFHasAllMoleculeParams), determinismo (2 corridas byte-idénticas) y
coste cold-start P50/P95 sobre las 2739 poses train de la unión original.
Si pasa → RS-04 OOF completo.

**RS-03-PARAM:** nodo del plan entre RS-08 y RS-03 (prerrequisito); ver
QA-2(e) y §3.4.

**Correcciones documentales (aplicadas):** eliminadas de DESIGN,
INVENTORY y FORECAST toda redacción contradictoria con estas decisiones:
recalibración de umbrales sobre la cohorte consumida, uso de UFF como
fallback energético, mezcla de cargas sin provenance, y cualquier lectura
que contradiga IT1.
