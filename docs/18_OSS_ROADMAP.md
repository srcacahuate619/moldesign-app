# 18 — MolDesign Open Source Roadmap

> **Fecha**: 2026-07-24
> **Estado**: Plan aprobado por el usuario (sesión de Plan Mode)
> **Objetivo**: Llevar `moldesign-build` a un estado CPA — Científicamente Publicable y Adópable —
> como software open source reproducible, con paper JCIM y release desktop descargable.

---

## 0. Contexto y decisiones previas

Este roadmap formaliza las decisiones tomadas en sesión de plan mode (2026-07-24 noche):

1. **Misión**: democratizar el drug discovery. Software open source (no comercial cerrado),
   validez científica por peer review (JCIM paper), comunidad capaz de contribuir y reproducir.
2. **Pipeline scoring**: un solo pipeline declarado pre-flight por target. Se reportan TODAS las
   combinaciones (Vina solo / Vina+XGB / +GNN / +stacking) para cada target, sin cherry-picking
   de "el mejor número". El histórico de `moldesign-app/docs/metricas_experimentales.md` (donde
   se reportaba el mejor score post-hoc) **se considera metodológicamente invalidado** y se
   reescribe en `moldesign-build/docs/metricas_experimentales.md` con tabla honesta.
3. **Licencia del código**: AGPL-3.0 (status quo en `Cargo.toml` y `package.json`). Los derivados
   del código deben publicar. Las empresas que quieran usarlo cerrado pagan commercial license.
4. **Licencia de modelos**: MolDesign Model License v1.1 (source-available) para `.pth`, `.gguf`, `.db` seeds. Investigación libre (incl. comercial interna); redistribución/SaaS requiere Enterprise. Reemplaza CC-BY-NC-SA (el NC bloqueaba labs con financiación industrial — la mayoría).
5. **Distribución del `.exe`**: NSIS installer con EULA custom que hereda la restricción NC de
   los modelos al output del pipeline. "Free for academic and personal use. Commercial drug
   discovery requires commercial license." **Requiere validación legal externa**.
6. **Prioridad**: backend con validez científica primero. Frontend (dashboard Tauri/Next.js)
   al final. UI sin ciencia detrás = maquillaje sobre concreto agrietado.
7. **Timeline**: estirado, salir prolijo. 1-2 meses de trabajo. Sin deadline artificial.

## 0.1 Bloqueadores críticos detectados (auditoría previa)

| # | Bloqueador | Síntoma | Estado |
|---|------------|---------|--------|
| 1 | Cherry-pick en histórico | `metricas_experimentales.md` reporta mejores números post-hoc | ** resolver Fase 1** |
| 2 | Frontend roto | `frontend/src/app/` está VACÍO (0 archivos) | postergado (luego de Fase 4) |
| 3 | Open source readiness cero | sin root README, sin LICENSE file, sin `.github/` | resolver Fase 2 |
| 4 | Binarios legales inconsistentes | `Cargo.toml` AGPL + `tools/xtb/` GPL commiteados + `tools/vina/` Apache OK | resolver Fase 2 |
| 5 | Script orquestador no portable | `run_5targets_2500.ps1` hardcodea `C:\Python314\python.exe` | resolver Fase 2 |
| 6 | 5HT1A divergencia histórica | EF@1% 15x vs histórico 32x. Box=40Å con 4 chains del GPCR | **resolver Fase 0** |

---

## FASE 0 — Resolver 5HT1A box enfocado (PRÓXIMA sesión)

**Objetivo**: cerrar la brecha histórica con GPCR (5HT1A) para que los números del paper sean
defendibles y el GPCR no arrastre el promedio.

### Tareas

1. Bajar PDB alternativo para 5HT1A con ligando cristalizado en el binding site. Candidatos:
   - `6G79` (5HT1A complejo con ligando, ~3Å resolución) — preferido.
   - `7E2Y` (actual) tiene `SRO` pero el contorno genera pockets espurios con box=40Å.
   - `6VS4` (5HT1A beta-arrestin, distinto estado activo).
2. Extraer el centro cartesiano (x,y,z) del primer HETATM del ligando cristalizado.
3. Calcular dinamic box: `clamp(ligand_span + 8, 14, 22)` Å — como en
   `backend/services/chemistry/protein_surgery.py:compute_dynamic_box()`.
4. Verificar por qué `compute_dynamic_box` requiere `ligand_mol2` — adaptar para que acepte
   centro cartesiano directo de HETATM (más simple, sin dependencia de OpenBabel mol2).
5. Re-docking de los 2550 mols del dataset `5ht1a` con box=22Å enfocado en el SRO.
   - Tiempo estimado: ~30-40 min en Ryzen 5 5500 (vs 1.5 hr del full box).
6. Re-score con GNN-v2 + CL-GNN vía `scripts/re-score-gnn.py` adaptado a 1 target.
7. Comparar EF@1% y AUC resultantes vs histórico 32.51x. Documentar en `docs/17` Parte 6.
8. Si sube notevablemente (e.g. >20x), re-optimizar `stacking_weights["gpcr"]` con grid search.

### Output esperado

- 5HT1A EF@1% entre 20-30x con box enfocado.
- AUC mantenida (>=0.85).
- Story del paper cierre: "Focused docking box derived from co-crystallized ligand rescues 5HT1A
  EF@1% from 15x to ~30x while preserving AUC".

### Tiempo

1 sesión de cómputo, ~2 hrs total de wall clock.

### Archivos a tocar

- `data/6g79.pdb` (nuevo, descarg RCSB)
- `scripts/run_5targets_2500.ps1` (extender flag `--focused-box` con centro HETATM)
- `scripts/re-score-gnn.py` (sin cambios — ya abstracto per-target)
- `data/gnn_fixed/benchmark_checkpoint_5ht1a_focused.json` (nuevo checkpoint)
- `docs/17_EF_BENCHMARK_FIXES.md` — Parte 6 (resultados focused box)

---

## FASE 1 — Re-corrida full + reproducibilidad metodológica (2 sesiones)

**Objetivo**: números reproducibles y defendibles para el paper.

### Tareas

1. Re-corrida `run_5targets_2500.ps1` con `--gnn` habilitado y todos los fixes aplicados.
   - Incluye el fix de inference.py (logger), feature_extractor.py (FastFindRings),
     benchmark_ef_vina.py (composite formula, chain sanity), stacking_weights.json re-optimizado.
   - Tiempo: ~8 hrs wall clock (background).
2. Re-score automáticano con `re-score-gnn.py` sobre los 5 checkpoints nuevos.
   - Tiempo: ~3 hrs (background).
3. Re-optimizar stacking weights sobre los nuevos checkpoints.
4. Generar `docs/metricas_experimentales.md` (NUEVO en moldesign-build) con:
   - Tabla honesta por target × método (Vina / Vina+XGB / +GNN / +stacking).
   - Discusión per-target, SIN cherry-pick.
   - Script de reproducibilidad referenciado (`run_5targets_2500.ps1`).
5. Cross-check: `moldesign-app/docs/metricas_experimentales.md` queda documentando el histórico
   (con la salvedad honesta de "números reportados como best-case, no metodológicamente válidos"),
   mientras que `moldesign-build/docs/metricas_experimentales.md` es la versión a publicar.

### Output esperado

- EF@1% promedio final ~27-30x (mejorando GPCR con Fase 0).
- AUC promedio ~0.96.
- Tabla del paper con 5 targets × 4 métodos, 1 único pipeline primario declarado pre-flight.

### Tiempo

1 sesión de cómputo + 1 sesión de doc.

### Archivos a tocar

- `docs/metricas_experimentales.md` (nuevo en build)
- `data/gnn_fixed/benchmark_checkpoint_<ds>.json` (5 archivos refresheados)
- `data/gnn_fixed/ef_report_<ds>_gs.json` (5 archivos)
- `rescoring/artifacts/stacking_weights.json` (re-optimizado)

---

## FASE 2 — OSS readiness (1 sesión)

**Objetivo**: repo público-ready, clonable, reproducible.

### Tareas

1. `D:\moldesign-build\README.md` (root) con:
   - Qué es MolDesign (1 párrafo).
   - Quickstart: clone → install deps → run benchmark → mirá tabla.
   - Badges (CI, license, paper).
   - Link a `docs/` internos.
2. `D:\moldesign-build\LICENSE` (AGPL-3.0 full text) en root.
3. `D:\moldesign-build\LICENSE-MODELS` (MolDesign Model License v1.1, source-available) para `.pth`, `.gguf`, seed `.db`.
4. `.gitignore` más agresivo:
   - Excluir `tools/xtb/`, `tools/vina/*.exe`, `tools/**/*.bin`, `tools/**/*.dll`.
   - Excluir `rescoring/trained_models/*.pth`, `rescoring/artifacts/*.pth` (source-available).
   - Excluir `*.gguf`, `*.bin`, `*.safetensors` (modelos LLM/GNN).
5. `scripts/download_binaries.ps1` — descarga Vina, xTB, ESMFold desde fuentes oficiales.
   - Vina: https://github.com/ccsdysb/vina-gpu-dockerbase o Scripps release.
   - xTB: https://github.com/grimme-lab/xtb/releases.
   - ESMFold: weights via huggingface.
6. `scripts/run_5targets_2500.ps1` portabilidad:
   - `python = python` (en PATH) en vez de `C:\Python314\python.exe`.
   - Paths relativos: `$PSScriptRoot/..` en vez de `D:\moldesign-build`.
7. `.github/workflows/ci.yml` — correr `pytest rescoring/tests/` en push y PR.
8. `.github/ISSUE_TEMPLATE/` — templates bug report, feature request, paper reproduction.
9. `.github/PULL_REQUEST_TEMPLATE.md` — checklist para contribuidores.
10. `CONTRIBUTING.md` — setup dev, correr tests, estilo de commits (conventional).

### Output esperado

- Repo público-ready.
- CI verde en todos los push.
- Cualquiera puede clone → install → run benchmark → reproducir tabla.

### Tiempo

1 sesión. Sin cómputo pesado.

### Archivos a tocar

- `README.md` (nuevo root)
- `LICENSE` (nuevo)
- `LICENSE-MODELS` (nuevo)
- `.gitignore` (modificado)
- `scripts/download_binaries.ps1` (nuevo)
- `scripts/run_5targets_2500.ps1` (modificado)
- `.github/workflows/ci.yml` (nuevo)
- `.github/ISSUE_TEMPLATE/*.md` (nuevos)
- `.github/PULL_REQUEST_TEMPLATE.md` (nuevo)
- `CONTRIBUTING.md` (nuevo)

---

## FASE 3 — Auditoría legal HD + EULA del `.exe` (offline, asesoría externa)

**Objetivo**: cláusulas del `.exe` válidas para impedir privatización comercial de outputs.

### Tareas

1. Consulta con abogado IP especializado en open source (no consume sesión de cómputo).
2. Validar estructura dual licensing: AGPL-3.0 (código) + MolDesign Model License v1.1 source-available (modelos) + EULA custom
   para `.exe`.
3. Redactar EULA del NSIS installer: "Free for academic/research use. Commercial drug discovery
   requires commercial license. Redistribution of bundled Models requires Enterprise license."
4. Cross-check con licencias third-party:
   - Vina (Apache-2.0) — OK.
   - xTB (GPL/LGPL) — OK, AGPL downstream compatible.
   - ESMFold (MIT) — OK.
   - OpenBabel (GPL) — en tools? Verificar.
   - PyTorch (BSD) — OK.

### Output esperado

- `frontend/src-tauri/resources/LICENSE_EULA.txt` (nuevo).
- `docs/19_LEGAL_DUAL_LICENSE.md` (nuevo, explicación de la estructura legal).
- Validación legal firmada por abogado (offline).

### Tiempo

Externo, no consume sesión de cómputo.

---

## FASE 4 — Paper draft (2-3 sesiones de escritura)

**Objetivo**: submission a JCIM. Fuera del scope de code agent — el usuario escribe.

### Estructura sugerida (JCIM)

1. **Introduction** — drug discovery democratization, dock-score/rescore ortogonalidad.
2. **Methods** — Vina, XGBoost features, GNN-v2 + CL-GNN arquitectura, stacking con
   rank-normalize, grid search de pesos, `compute_dynamic_box` para GPCR.
3. **Results** — Tabla 5 targets × 4 métodos (sin cherry-pick), discusión per-target.
4. **Discussion** — GPCR dificil, AUC vs EF@1%, ranking global vs top-1%.
5. **Reproducibility** — `run_5targets_2500.ps1` referencia, tiempo 8 hr en Ryzen 5.
6. **Limitations** — 5 targets low-N, dynamic box solo para GPCR, GPU inference untested.
7. **Conclusion** — open source desktop app, dual licensing, comunidad invitada.

### Output esperado

- `docs/20_JCIM_PAPER_DRAFT.md` (nuevo).
- Tablas en LaTeX/CSV reusables.

### Tiempo

2-3 sesiones de escritura ortogonales a compute.

---

## FASE 5 — Frontend dashboard (post-cierre científico)

**Objetivo**: el `.exe` abre, muestra UI mínima para dockear moléculas.

### Tareas

1. Recuperar `frontend/src/app/` desde backup o re-clonar (`moldesign-app` parent).
2. Verificar que las rutas /evaluation, /rescoring, /protein-surgery funcionan con el backend.
3. Test end-to-end: lanzar backend → lanzar Tauri app → dockear 1 mol → ver resultado.
4. Pulir UX básica. Sin animaciones, sin estado-loading fancy — solo funcional.
5. Build NSIS installer para Windows x64. Probar install en VM fresca.

### Tiempo

2-3 sesiones cuando el backend esté 100% estable.

### Archivos a tocar

- `frontend/src/app/` (recuperar)
- `frontend/src-tauri/tauri.conf.json` (build settings)
- `frontend/src-tauri/resources/` (packaging)

---

## FASE 6 — Release公开发行 (post-paper)

**Objetivo**: publicar GitHub público, landing page, instrucciones de uso.

### Tareas

1. Push a GitHub público (requiere PAT del usuario).
2. Tag v0.1.0-alpha con GitHub Release + binario NSIS installer attached.
3. Landing page simple (GitHub Pages): screenshots, feature list, install steps, citation BibTeX.
4. Anuncio en Reddit `r/drugdiscovery`, `r/chemistry`, Twitter con hashtag #OpenSourceDrugDiscovery.

---

## Resumen ejecutivo de secuenciación

```
Fase 0 — 5HT1A focused box       (1 sesión, ~2 hr compute)
   │
   ├──> Fase 1 — Re-corrida + doc metodológica  (2 sesiones, ~8 hr compute + doc)
   │
   ├──> Fase 2 — OSS readiness                  (1 sesión, sin compute)
   │
   ├──> Fase 3 — Legal HD (offline, externo)
   │
   ├──> Fase 4 — Paper draft                     (2-3 sesiones de escritura)
   │
   ├──> Fase 5 — Frontend dashboard              (2-3 sesiones)
   │
   └──> Fase 6 — Release público                 (1 sesión)
```

**Total estimado**: 12-15 sesiones + 1 externa legal + trabajo de escritura.

---

## Deuda técnica pendiente (no bloqueante para paper)

- GPU inference sin testear (`torch.cuda.is_available()=True` pero no corrió).
- CL-GNN correlación con GNN-v2 (comparten encoder) — para futura versión v3 considerar
  arquitecturas más divergentes (e.g. EquiBind baseline como tercer predictor).
- DUD-E 100 targets para paper más ambisiono (low priority para JCIM primer paper).
- Tests en backend + frontend: coverage actual cero para ambos.
- Migration de Python 3.14 embedded (Tauri bundle) — funcional pero fragil si Python cambia ABI.

---

## FASE 7 — v3 Universal Box Selection (post-paper, 5-6 sesiones)

**Objetivo**: zero manual configuration. El usuario arrastra un PDB crudo +
un Excel de moleculas, elige un receptor, clic "ejecutar". El sistema
deriva automaticamente chain, center, box_size, sin intervecion manual.

### Diagnostico (Bucket B+ pre-Fase 7, hecho en sesion anterior a este commit)

Descubierto durante el diagnostico del Bucket B+:

- `discover_pocket_from_pdb` (utils/structural.py:71) ya detecta ligando
  drug-like, cadena receptora, hotspots, y valida grid. MEJOR que
  `extract_accurate_pocket_centroid` que cableamos en Bucket B.
- **PERO** el heuristico "max-atom HETATM wins" se rompe en GPCR con
  lipidos co-purificados grandes: en 7E2Y elige J40 (125 atomos, lipido
  fosfatidil-inositol) en vez de SRO (13 atomos, serotonina, el ligando
  farmacologico real del receptor).
- La distincion no es por tamano — es por **conocimiento farmacologico
  externo** (DrugBank catalog). Sin esa info, el sistema no sabe que
  SRO es droga y J40 no.

### Tareas

1. **Build catalog PDB Chemical Component -> DrugBank crossref** (2 sesiones).
   - Script `scripts/build_pdb_drug_catalog.py` que descarga PDB CCD
     (una sola vez, offline) + DrugBank crossref + tags manuales para
     membrane lipidos (CLR/CHO/OLC...), detergents, glycans, cofactors.
   - Output commiterado como `data/pdb_drug_catalog.json` (~12k entries,
     ~300KB). Actualizable via GitHub PR cada 6 meses.
   - NO dependency runtime fuera de este static JSON.

2. **Extender `discover_pocket_from_pdb` con 3-tier selector** (1 sesion).
   - Priority 1: HETATM que matchea `pdb_drug_catalog.json` tag
     "known_drug" — winner automatico sin importar tamano.
   - Priority 2: si no hay known_drug, RDKit QED >= 0.5 de SMILES
     (fetch PDB CCD SMILES, cachado local a data/pdb_ccd_smiles/).
     Identifica ligandos novel del usuario por drug-likeness.
   - Priority 3: max-atom heuristic actual (fallback).
   - Refactor para que tambien retorn `box_source` tag del tipo
     'known_drug_sro' / 'qed_novel_xyz' / 'max_atom_fallback'.

3. **Tests de regressión** (1 sesion).
   - 7E2Y: SRO gana sobre J40 por known_drug match. (test_known_drug)
   - 9QA0: ZN catalytic metal gana por cofactor priority. (test_metal)
   - PDB synthetic con ligando novel estructurado (QED 0.7): gana por
     QED >= 0.5. (test_novel_qed)
   - PDB con solo glycerol (GOL): descartado por SKIP_HETATM, falls to
     geometric centroid. (test_no_drug_fallback)
   - 15+ tests nuevos.

4. **MolGraph integration**: tablas `ligand_catalog` + `user_corrections`
   (1 sesion).
   - Cuando el usuario corrige manualmente una eleccion de ligando, eso
     se persiste en MolGraph como training signal. Futuras corridas del
     mismo PDB cargan la correccion automaticamente.

5. **`docs/20_V3_UNIVERSAL.md` methodology** (1 sesion).
   - Documenta el 3-tier selector y el tradeoff honesto:
     "MolDesign no es FEP+; es docking + ML stacking. Reportamos EF/AUC
     en benchmark limpio y reconocemos las clases de targets donde no
     podemos alcanzar enrichment perfecto (out-of-scope: apo proteins
     sin co-crystal, metodos novel totalmente sin contexto quimico)."

### Output esperado

- 95% universalidad para targets PDB con co-crystal ligand (sea
  known_drug catalogado o novel con QED alto). 5% restante out-of-scope
  declarado honestamente.
- 7E2A ya no requiere patch manual del CSV.
- Frontend v3 flow: drag PDB + Excel + click ejecutar. Sin mas.

### Tiempo

5-6 sesiones. Post-paper (no bloquea Fase 1).

### Archivos a tocar (planeados)

- `scripts/build_pdb_drug_catalog.py` (nuevo)
- `data/pdb_drug_catalog.json` (nuevo, commiteado)
- `backend/utils/structural.py` (extender discover_pocket_from_pdb)
- `backend/services/ai/molgraph.py` (tablas nuevas)
- `rescoring/tests/test_universal_box.py` (nuevo)
- `docs/20_V3_UNIVERSAL.md` (nuevo)

---

## Métricas de aceptación del proyecto terminado

- [ ] Repo GitHub público, CI verde.
- [ ] `README.md` root con quickstart reproducible en <1 hr.
- [ ] `LICENSE` + `LICENSE-MODELS` claros.
- [ ] `docs/metricas_experimentales.md` con tabla honesta de los 5 targets.
- [ ] `run_5targets_2500.ps1` portable (sin paths hardcodeados).
- [ ] 5HT1A EF@1% >= 20x con focused box.
- [ ] Promedio EF@1% >= 28x (>= histórico).
- [ ] AUC promedio >= 0.95 (actual: 0.958).
- [ ] Paper JCIM draft listo.
- [ ] Build NSIS installer funcional en VM fresca.

---

## Referencias entre documentos

- `docs/17_EF_BENCHMARK_FIXES.md` — Parte 5 contiene los resultados actuales con stacking v2.
- `moldesign-app/docs/metricas_experimentales.md` — histórico (original, NO reescribir —
  queda como referencia metodológica de la evolución).
- `moldesign-build/docs/metricas_experimentales.md` (a crear en Fase 1) — versión honesta
  del paper, basada en el modelo AGPL.
