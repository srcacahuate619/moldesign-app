# FORECAST — Campaña 2 (CAMPANA-2-PLAN): costos por etapa

**Fecha:** 2026-08-16 (revisión IT1 — decisiones definitivas del maintainer)
**Rama:** `experimentos/ruta-c-molflex`
**Tipo:** planificación (rango con base). 0 cómputo ejecutado; todos los
números son estimaciones ancladas en artefactos sellados o código
verificado.

## 0. Resumen

| Etapa | Alcance | Costo por unidad | Total CPU | Wall (4/6 workers) |
|---|---|---|---|---|
| RS-04-QC (técnica previa) | 2739 poses train unión ORIGINAL | ms/pose (cacheado) | minutos | minutos |
| RS-04 N1 (MMFF94s, RDKit) | 2739 poses (unión original) | 1–50 ms/pose (cacheado) | 2 s–3 min | minutos |
| RS-08 router (riesgo) | 116 complejos × 5 folds | LogReg por fold | minutos | 10–30 min |
| RS-03-PARAM (prerrequisito) | ligandos únicos + subconjunto AM1-BCC | s/ligando; min/ligando AM1-BCC | 0.3–10 h | 10 min–2.5 h |
| RS-03 MM/GBSA-like top-K | 35 complejos (30%) × top-2 | 0.5–3 min/pose; cap 600 s/complejo | 0.6–5.8 h | P50 10–40 min / 7–25 min; P90 0.5–1.5 h / 0.3–1 h |
| **Cascada integrada** | v0.6 + router + strain + MM/GBSA-like selectivo | — | — | **P50 ≈ 0.5–1.5 h · P90 ≈ 1.5–4 h (4 workers); P50 ≈ 0.3–1 h · P90 ≈ 1–2.7 h (6 workers)** |

Anclas: CPU 12 cores, GPU GTX 1660 SUPER (manifests Campaña 1);
prohibido 12 workers por oversubscription histórica (docs/40; FORECAST
D-MF-HARD-EXH4 §3.3).

---

## 1. RS-04 strain — N1 MMFF94s (RDKit) + RS-04-QC previa

**Base:** RDKit MMFF94 `MMFFGetMoleculeForceField` + `CalcEnergy` es
evaluación de energía estática; sin precedente sellado de timing, orden de
magnitud milisegundos por molécula pequeña. Contrato IT1/QA-5: topología
desde SDF/SMILES sanitizado, mapeo heavy-atom biyectivo,
AddHs(addCoords=True), en la pose docked se optimizan SOLO los H (pesados
fijos), fuerza MMFF94s; referencia aislada con Nconfs = min(200, max(50,
10×rotatable_bonds)), ETKDGv3 seed 42, optimización completa.

Denominador (IT1/QA-1): **2739 poses train de la unión ORIGINAL**
(`union_candidates_train.jsonl`, sha `61ab0e26…`). RS-04-QC (IT1) ejecuta
primero sobre esas 2739 poses: mapeo, H, cobertura MMFF, determinismo (2
corridas byte-idénticas) y coste cold-start P50/P95; solo si pasa → RS-04
OOF completo.

**Gates de coste (IT1/QA-6):** cold-start P95 ≤ **5 s/ligando** (Embed +
MMFF optimize de la referencia aislada, por ligando único, cacheable);
cacheado P95 ≤ **100 ms/pose** y ≤ **3 s/complejo**.

| Magnitud | Valor |
|---|---|
| Costo por pose (docked, MMFF, cacheado) | 1–50 ms (gate P95 ≤ 100 ms) |
| Costo mínimo aislado (por ligando único, cold-start) | 0.1–1 s (gate P95 ≤ 5 s) |
| Total CPU (2739 poses + ligandos únicos) | **2 s–3 min** |
| Fallos esperados | `MMFFHasAllMoleculeParams == false` → `unsupported_mmff` (sin mezclar UFF — energías no comparables); halógenos NO excluidos por nombre (decide la cobertura real); strain negativo no truncado (ampliación única del search; si persiste, fallo QC); neutros vs ionizados separados |

## 2. xTB-strain — segundo experimento selectivo (NO fallback de MMFF)

**Base:** `scripts/compute_quantum_features.py:112-120` (patrón
reutilizable con coords de pose); binario verificado
`tools/xtb/xtb-6.7.1/bin/xtb.exe`; timeout 120 s/molécula. **IT1/QA-5:**
experimento selectivo aparte, no sustituto del MMFF. **IT1/QA-2b:** la
carga formal debe provenir del ligando sanitizado (el `--chrg 0` actual de
la línea 118 es incorrecto para ionizadas). Sin timings sellados de xTB;
rango por tamaño molecular (drug-like PDBbind: 10–60 átomos pesados).

| Magnitud | Valor |
|---|---|
| Costo por molécula (rango por tamaño) | P50 ≈ 1–20 s; P90 ≈ 60 s; peor 120 s (timeout) |
| Total CPU cobertura completa (2739 poses) | P50 ≈ **1–4 h** · P90 ≈ **8–20 h** |
| Escenario SELECTIVO (30% mayor riesgo ≈ 35 complejos, ~820 poses) | P50 ≈ **0.3–1.2 h** · P90 ≈ **2.4–6 h** |
| Fallos esperados | timeout 120 s → missing/failed ITT por molécula; sin sustituto silencioso de cargas (IT1/QA-2c) |

## 3. RS-08 router de riesgo (reuso Fase 3.5, sin reentrenar v0.6)

**Base:** Fase 3.5 completa quedó en escala de minutos
(`artifacts_ruta_c_fase3_5.json`). El router (IT1/QA-3) recalcula los 18
agregados por complejo sobre scores v0.6 congelados y reajusta un LogReg
**dentro de cada uno de los 5 folds sellados** (umbral de cada outer fold
exclusivamente del outer-train; política primaria: 30% de mayor riesgo;
sensibilidad 10/20/40%; umbrales históricos 0.24158/0.399889 SOLO
comparadores descriptivos). Tras OOF: un `t_router*` full-train congelado
que reproduce el presupuesto del 30%.

| Magnitud | Valor |
|---|---|
| Agregados + 5× LogReg (116 complejos) | minutos |
| Total wall | **10–30 min** |
| Fallos esperados | ~0 (todo CPU, sin binarios externos) |

## 4. RS-03 MM/GBSA-like selectivo top-K (tras RS-03-PARAM)

**Base (precedentes verificados):**
- `queue_handler.py:823-826`: "OpenMM MM-GBSA tarda >180 s en CPU (sin
  GPU)" — ancla CPU por complejo;
- `docs/40_MOLFLEX_PROTOCOL.md:104`: minimización OpenMM en el pocket
  "~K × 30 s" (MIN_STEPS 300) — ancla ~30 s por minimización;
- contrato IT1/QA-4: **single-trajectory** (UNA minimización del complejo;
  complejo/receptor/ligando sobre las mismas coordenadas; sin
  re-minimización separada de molchamb_v2.py:571) → una sola
  minimización por pose en lugar de tres;
- maxIterations=200; tolerancia 10 kJ/mol/nm; timeout duro 300 s/pose;
  primario **top-2** cap **600 s/complejo**; **top-3** ablación secundaria
  cap **900 s/complejo**; fallo físico conserva v0.6 (ITT, nunca energía
  cero).

Alcance (IT1/QA-3c): política primaria = 30% de mayor riesgo de los 116
train ≈ **35 complejos**; sensibilidad 12/23/46 (10/20/40%). Primario
top-2 → **70 poses**; ablación top-3 → **105 poses**.

| Magnitud | Valor |
|---|---|
| Poses MM/GBSA-like | 70 (top-2 primario) / 105 (top-3 ablación) |
| Total CPU primario | P50 ≈ **0.6–2 h** · P90 ≈ **2–5.8 h** (cap duro 35 × 600 s = 5.8 h) |
| Total CPU ablación top-3 | P50 ≈ **0.9–3 h** · P90 ≈ **3–8.8 h** (cap 35 × 900 s = 8.8 h) |
| Wall 4 workers (primario) | P50 ≈ 10–40 min · P90 ≈ 0.5–1.5 h |
| Wall 6 workers (primario) | P50 ≈ 7–25 min · P90 ≈ 0.3–1 h |
| Fallos ITT parametrizados | timeout 300 s/pose; elementos fuera de C/H/O/N/S/P → missing/failed (riesgo real: F/Cl comunes); no convergencia; fallo físico conserva v0.6 |
| Cargas | provenance IT1/QA-2a (charge_method, formal_charge, uhf, engine_version, model_hash, atom_order_hash, charge_sum, runtime, fallback_reason); sin sustituto silencioso (IT1/QA-2c) |

## 5. RS-03-PARAM (prerrequisito — estimación con supuestos)

**Alcance (IT1/QA-2e):** OpenFF Sage + modelo NAGL congelado por versión y
SHA-256 para parametrizar el ligando (reemplaza el tipado heurístico de
molchamb_v2.py:65); referencia de validación AM1-BCC en subconjunto
estratificado. Sin precedente sellado de timing en el repo; estimación por
tamaño de tarea.

| Magnitud | Valor (supuestos explícitos) |
|---|---|
| Parametrización Sage+NAGL por ligando único | 1–60 s (NAGL en GPU; ~300–600 ligandos únicos esperados) |
| Total CPU parametrización | P50 ≈ **0.3–1.5 h** · P90 ≈ **1–5 h** |
| Referencia AM1-BCC (subconjunto estratificado ~50–100 ligandos) | 1–5 min/ligando → **1–8 h CPU** |
| **Riesgo documentado** | el backend de AM1-BCC (antechamber/OpenEye) NO está en el repo hoy (evidencia molflex.py:16-19: "no hay antechamber") → auditoría de dependencias ANTES de ejecutar esta etapa; sin backend validado, la referencia no puede computarse localmente |
| Wall total (4/6 workers) | 10 min–2.5 h / 7 min–1.7 h |

Sin RS-03-PARAM no se ejecuta RS-03; hasta completarla, el componente se
denomina **"rescoring MM/GBSA-like de pose única"**.

## 6. Cascada integrada (totales)

Suma con política primaria (router 30% → strain MMFF sobre escalados +
MM/GBSA-like top-2; RS-04 OOF corre aparte sobre 2739 poses por
cross-fitting completo):

| Escenario | CPU total | Wall 4 workers | Wall 6 workers |
|---|---|---|---|
| P50 | ≈ 1.5–4 h | **≈ 0.5–1.5 h** | **≈ 0.3–1 h** |
| P90 (colas MM/GBSA-like + RS-03-PARAM AM1-BCC) | ≈ 6–16 h | **≈ 1.5–4 h** | **≈ 1–2.7 h** |
| Peor caso (ablación top-3 + xTB-strain selectivo + AM1-BCC completa) | ≈ 15–35 h | ≈ 8–15 h | ≈ 5–10 h |

## 7. Almacenamiento y reanudación

- Salidas por etapa: JSONL por complejo/pose (strain MMFF con
  unsupported_mmff, P(riesgo) del router, MM/GBSA-like con provenance
  IT1/QA-2a y RMSD de desplazamiento por minimización) — < 10 MB.
- Identidad de reanudación: `split|pid|source|file_stem|model_idx`
  (formato MF-01-UNION) + etapa; cache del mínimo aislado por ligando
  (SMILES hash) reutilizable; RS-04-QC exige 2 corridas byte-idénticas.
- 0 red, 0 pip: todo con el runtime ya instalado (openmm, pdbfixer, rdkit,
  xgboost verificados en Campaña 1); excepción de auditoría: backend de
  AM1-BCC para RS-03-PARAM (ver §5).

## 8. Notas de honestidad

- xTB per-molécula es el componente de mayor incertidumbre (sin timings
  sellados): el rango 0.5–120 s cubre ligando pequeño vs drug-like grande
  al timeout.
- MM/GBSA-like sobre GPU no tiene precedente de timing sellado en este
  repo; el rango usa las anclas CPU (180–300 s) y minimización (30 s/300
  pasos) como cotas, corregido a la baja por el protocolo
  single-trajectory (una minimización en lugar de tres).
- El alcance de RS-03 queda FIJADO por la política primaria del 30%
  (IT1/QA-3c); la curva de sensibilidad 10/20/40% reporta el costo
  alternativo sin tocar el gate.
- RS-03-PARAM es la etapa de mayor riesgo de calendario (backend AM1-BCC
  ausente del repo); los rangos son de planificación, no gates.
