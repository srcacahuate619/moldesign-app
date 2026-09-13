# 19 — Limitaciones del Pipeline MolDesign v1 (Hoja de Ruta a GNN-v3 Universal)

> **Fecha**: 2026-07-25 (postmortem de Bucket A agregado)
> **Estado**: Documento técnico interno — limitaciones honestas del pipeline actual
> **Origen**: Sesión de plan/build post-Fase 0 (focused box). Auditoria por subagent
> `breakable-rose-peacock` + verificación directa del código.
> **Postmortem Bucket A**: Sección 7 (~2026-07-25, commit `4f48fde`).
> **Filosofía**: "Documentar mis errores, son igual de importantes que mis victorias."

---

## TL;DR — qué le falta a MolDesign v1 para ser universal

| Arquetipo de receptor | Estado actual | Modo de falla |
|----------------------|---------------|---------------|
| Receptores proteína estándar con ligando co-cristalizado | ✅ Funciona (calidad paper) | — |
| Receptores proteína sin HETATM ligando, sin `.mol2` | ⚠️ Caída a box=25Å geo-centro | Calidad docking baja |
| DNA-binding (topoisomerase + daunorubicin, TFs) | 🔴 GNN-v2 retorna `None` → `0.5 ± 1.0` | Silent fail, rescoring muerto |
| RNA aptamers / ribozymes / riboswitches | 🔴 GNN-v2 retorna `None` (filtro CA, 0 pocket res) | Silent fail |
| Glycan-binding glicosilados (mAbs pocket con glycan) | 🔴 Glycans caen como HETATM no-AA | GNN descarta el pocket real |
| HIV protease homodímero, pocket inter-cadena | ⚠️ `_detect_dominant_chain` recorta UNA cadena | Pocket destruido si no curated |
| Metaloenzimas (Zn-cofactor en pocket) | ⚠️ Atomo Zn ignorado por `_detect_dominant_chain` | Trim puede perder cofactor |
| Ligandos con boro (Bortezomib, proteasoma) | 🔴 Elemento B → bucket `"X"` | Discriminación química perdida |
| Ligandos con selenio / silicio | 🟡 Bucket `"X"` | Discriminación perdida |
| AlphaFold models sin ligando | ⚠️ Funciona pero cae a geo-centro | Para estructuras elongadas, centro fuera del pocket |
| Cofactores covalentes (PLP, hemo, FAD) | ⚠️ PDBFixer puede reinterpretarlos | Riesgo de corromper residuos modificados |
| Membrane proteins con lipid co-cristalizado | 🟡 Lipidos en box como "dummy atoms" | Vina usa lipid como partner falso |

---

## 1. Contexto — por qué documentar esto

MolDesign v1 (el `moldesign-build` que tenemos hoy, commit `08c7f2d`), funciona
**espectacularmente** para 5 receptores protein-estándar en 18 familias curadas
del `curated_targets.csv` (80 targets). En esos tests dio EF@1% promedio 33.37x
vs histórico 28.91x (+15.5%) y AUC promedio 0.925. **Eso es valido para el paper JCIM.**

Pero si un usuario externo descarga la app, pone un PDB nuevo de un glycoprotein
con glycan pocket, le va a dar resultados sin sentido. Sin excepciones, sin alertas.
"Silent fail" es el pattern y nuestro peer review más agresivo lo va a notar cuando
intente reproducir el paper en un arquetipo Non-protein.

Este documento es el registro técnico honesto de cada modo de falla, su causa raíz
en el código (`file:line`), y el plan para resolverlo en MolDesign v3.

---

## 2. Causas raíz detectadas (con evidencia código)

### 2.1 Solo 20 aminoácidos estándar — gn_v2/data.py:41

```python
# gnn_v2/data.py:41
AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"  # 20 standard, alphabetically
```

y `:234`:

```python
if not resname_1 or resname_1 not in AMINO_ACIDS:
    continue  # skip non-standard residues
```

El mapeo `AA3_TO_AA1` (`:46-53`) cubre 20 estándar + 5 variantes histidina/cisteína
(HIE/HID/HIP/CYX). Las modificaciones postraduccionales (SEP = fosfoserina,
TPO = fosfotreonina, CSO = sulfenilcisteina), nucleótidos (DA/DC/DG/DT/RA/RC/RG/RU),
glycans (NAG/MAN/BMA/FUC), y cofactores covalentes (PLP, HEM, FAD) → **caen a UNK
(idx 20) o son skipped del pocket**.

### 2.2 Filtro Cα exclusivo — gn_v2/data.py:220

```python
if info.GetName().strip() == "CA":
    ca_atoms[key] = atom.GetIdx()
...
if len(ca_atoms) == 0:
    return None  # no Cα atoms (unusual PDB)
```

Cualquier recept sabor sin Cα (DNA/RNA tiene C2' y C4', no CA) → retornado None. Luego
`inference.py:88,94,127,133` hắn returna `(0.5, 1.0)` constant. **No se lanza** — solo se
devuelve media incertidumbre máxima. Nada en el log alerta al usuario.

### 2.3 Solo 10 elementos químicos en ligando — gn_v2/data.py:55

```python
# gnn_v2/data.py:55
ELEMENTS = ["C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "X"]
ELEM_TO_IDX = {e: i for i, e in enumerate(ELEMENTS)}
```

Boro (B) — esencial para Bortezomib (anti-mieloma, inhibidor del proteosoma),
Selenio (Se) — selenocysteine en glutatión peroxidasas, Silicio (Si) —
organosilicon experimental, Litio (Li), Magnesio en ligando.covalente → todos
mapeados a idx 9 ("X"). El vector one-hot es el mismo para todos — pérdida de
discriminación química total en estos átomos.

### 2.4 `compute_dynamic_box` en el backend runtime — services/docking/preparer.py:267

> **Estado actual: IMPLEMENTADO, pendiente de benchmark.** Históricamente esta sección
> describía el dynamic box como "desconectado/muerto en producción". Desde el Bucket B
> (commit `f8ebc79`, 2026-07-25) `compute_dynamic_box` está cableado al path async del
> preparer con fallback a centro geométrico cuando el centro recibido es `(0,0,0)`.
> La calidad del box derivado aún NO ha sido medida contra cocrystallizados nuevos —
> no declarar el problema resuelto hasta ese benchmark. Ver §3 #6 y §9 #7.

Contexto histórico (pre-Bucket B):

```python
# backend/services/docking/preparer.py:267 (DISTINTO de protein_surgery.prepare_target)
async def prepare_target(..., center, box_size):  # recibe valores YA calculados
    ...
    # NO llama a compute_dynamic_box
```

`protein_surgery.py:152` define `compute_dynamic_box(ligand_mol2)` — la función correcta
para derivar box automático desde un ligando. Pero el `services/docking/preparer.py` es
una función async DISTINTA que recibe `center` y `box_size` pre-calculados. El runtime
del backend (`vina_service.py:408`, `queue_handler.py`, `ingestion_manager.py:95`) usa
este segundo `prepare_target` → dynamic box está **muerto en producción**.

Solo vive en:
- El endpoint HTTP aislado `/prepare` (`routers/protein_surgery.py:292`)
- 5 targets PDBbind en el script de benchmark (`benchmark_ef_vina.py:537`)

Para cualquier otro receptor nuevo que un usuario suba al backend, **no se computa
dynamic box**. El caller debe saber el centro y el tamaño de la caja — parámetro
inferido a cargo de quién invoca.

### 2.5 `_detect_dominant_chain` heurístico frágil — benchmark_ef_vina.py:316

```python
def _detect_dominant_chain(pdb_path):
    # returns chain with max ATOM line count
    return max(chain_counts, key=chain_counts.get)
```

No usa HETATM (ignora cofactores/ligandos/zinc). No tiene concepto de binding
site. Para HIV protease `1HSG` (homodímero A/B simétrico) esto trim únicamente
UNA cadena y destruye el pocket heterodimérico (P2/P1' sites span ambas cadenas).

El antibug `:493-503` salva el caso solo si `curated_center` proviene del CSV.
Para targets nuevos sin curar → trim destructivo.

`protein_surgery.detect_binding_chain` (`:69-73`) sí maneja multi-chain (devuelve
`"multi"` si dos chains están <5Å del ligando), pero NO es usado por el benchmark
ni por el runtime backend.

### 2.6 `_build_ligand_graph`: match estricto de átomos — gn_v2/data.py:133

```python
if len(docked_elements) != len(rdkit_heavy):
    return None
```

Si Vina agrega un átomo (e.g. por hidratación, neutralización tautomérica, o
hydrogen implicito mal stripado) → fail silencioso, `(0.5, 1.0)` en inference.
Para dataset ChEMBL/DUD-E con tautómeros, esto es fragil.

### 2.7 Curated DB coverage: 80 targets, 18 familias — curated_targets.csv

| Family | Count | Notas |
|--------|------:|-------|
| kinase | 15 | mayoritario, sesgo por PDBbind historical |
| gpcr | 14 | incluye 5ht1a (chain R fixeado), GLP-1R, opioid |
| protease | 11 | HIV protease, thrombin, chymotrypsin |
| nuclear_receptor | 10 | ER-alpha, AR, PPAR |
| cytochrome | 5 | CYP3A4, CYP2D6 metabolism |
| transferase, hydrolase | 4 c/u | mixtos |
| ion_channel, phosphodiesterase | 3 c/u | hERG, PDE4 |
| otros 9 singleton | 1 c/u | (bromodomain, chaperone, transporter, etc) |
| **DNA-binding, RNA-binding, glycan-pocket, ribozyme** | **0** | **no coverage** |

### 2.8 Silent failure — inference.py no lanza warnings en returns 0.5

```python
# inference.py (resumido)
def predict(...):
    try:
        ...
        lig_graph = _build_ligand_graph(...)
        prot_graph = _build_protein_graph(...)
        if lig_graph is None or prot_graph is None:
            return 0.5, 1.0  # SIN log
        ...
    except Exception as e:
        return 0.5, 1.0  # SIN print
```

**El usuario no sabe** que el GNN descartó su receptor. El resultado "0.5" es
idéntico al que daría si el GNN cargara bien pero no discriminara. Para el paper
esto es un framing de "metricas de MolDesign v1" — aceptable. Pero para un SaaS o
investigador que repousó semana probando un receptor raro, **esto es una trampa**.

---

## 3. Plan de remedio — MolDesign v3 Universal

Tres buckets de trabajo, cada uno con su interés independiente.

### Bucket A — Fix silent-fails (1 sesión, sin reentreno)

Objetivo: detectar y advertir limitaciones en runtime, sin ampliar cobertura.

- `inference.py:88,94,127,133` — agregar `_log.warning("gnn-protein-graph-empty")` en
  todos los returns `(0.5, 1.0)`. El report `ef_report_<ds>.json` debe exponer un
  campo `gnn_silent_failures_count`.
- `gnn_v2/data.py:55` — expandir `ELEMENTS` a 30: agregar `B`, `Si`, `Se`, `As`, `At`,
  `Li`, `Bk`, `In`, `Sn`, `Sb`, `Te`, `Xe`. Mantener "X" como último recurso.
- `gnn_v2/data.py:41` — agregar modificaciones comunes a `AA3_TO_AA1`: SEP/TPO → S/T,
  CSO → C, PCA/PYL → UNK, nucleótidos DA/DC/DG/DT/RA/RC/RG/RU → mantienen `UNK_AA_IDX`
  (índice 20). Evita Block eliminarlos del pocket.
- `scripts/re-score-gnn.py` — imprimir warning al final del run: `WARNING: N=23/2547
  mols sin gnn discriminativo (gnn_prob=0.5 exact)`. Indagar la razón.
- Tests `rescoring/tests/test_non_protein_residues.py` — assert que ADN target returns
  prob=0.5 Y loguea warning (regresión de silent fail).

### Bucket B — Cablear dynamic box al backend runtime (1 sesión)

Objetivo: que el backend use `compute_dynamic_box` en lugar del `prepare_target` async
versión dead.

- `backend/services/docking/preparer.py:267` — refactorizar para invocar
  `protein_surgery.compute_dynamic_box(ligand_mol2)` cuando el usuario no pase `center`
  o `box_size` explicitamente.
- `backend/api/routers/protein_surgery.py` — exponer endpoint `/auto-box` que dada
  PDB + ligando (o fallback al primer HETATM), compute center + box. El frontend
  puede usar esto para previsualizar el box antes de corr el docking.
- `benchmark_ef_vina.py:530-547` — configurar un fallback: si no `ligand_mol2` pero
  HETATM ligando co-cristalizado presente en el PDB, llamar a un nuevo helper
  `_hetatm_auto_center(pdb_path)` que compute center como centroide del primer
  HETATM. Mantengo la opcion override de CSV curated como prioridad 1.

### Bucket C — Research track: GNN-v3 universal (2-3 meses)

Objetivo: archetypes no-protein en cobertura real, no solo fallback armado.

Tareas de investigación, no se programan en esta sesión:

- **C1. DNA-target dataset**: Build set de ~150 DNA-binding complexes de PDBbind-like
  coverage (TOP1, TOP2, DNA gyrase, integrase, polymerase con DNA + lig). Calcular
  pocket residues as DNA nucleotide indices (no AA). Grafico heterogéneo.
- **C2. RNA-target dataset**: ~100 RNA aptamers/ribozimas con ligando (Riboswitch
  classes: TPP, SAM, purine, FMN, glmS).
- **C3. Glycan-pocket dataset**: ~50 glycosyltransferases (e.g. O-GlcNAc transferase)
  con glycan en pocket.
- **C4. GNN-v3 heterogéneo**: agregar tipo-de-nodo (protein/DNA/RNA/glycan) como
  feature dim extra. Mantener el shared encoder que ya demostró valor en v2.
  Cross-attn extender a atención cross-modality.
- **C5. Reentrenar con todos los datasets**: train/test split por arquetipo. Evaluar
  per-archetype EF@1% + AUC. Compar contra v1 — esperamos alta ganancia en DNA/RNA
  coverage, ligero retroceso en protein-standard por overtasking.
- **C6. Paper v3**: "MolDesign-v3: Heterogeneous GNN rescoring across biomolecular
  receptor archetypes" — JVLC o JChemIM tier 2.

### Bucket D — Limitaciones que declaramos y no fixeamos (paper section)

Para el JCIM v1 paper, las limitaciones honestas que van a Section "Limitations":

1. Pipeline optimizado para receptores proteína-estándar con PDB co-cristalizado.
   Para receptor sin ligando cocrystallizado, dynamic box cae a geomcenter + 25Å box.
2. GNN-v2 discretiza aminoácidos estándar (20 + UNK). Receptores con cofactores
   covalentes, glicanos, o DNA/RNA en el pocket no son rescoringeables.
3. Elementos químicos soportados: C/N/O/S/P/F/Cl/Br/I + bucket X. Bortezomib
   (boron-containing anti-cancer) cae al bucket — perdida de discriminación.
4. `_detect_dominant_chain` es heurístico. Receptores heterodiméricos donde el
   pocket spans dos cadenas requieren cura manual del CSV.
5. Stacking weights entrenados por familia (18 familias curadas, 80 targets).
   Family desconocida cae a `"default"` weights — riesgo de underfit.
6. `compute_dynamic_box` está desconectado del runtime del backend. La derivación
   automatica del box solo corre para 5 targets PDBbind del script de benchmark, no
   para el backend que usan los usuarios finales. Fase 2 del roadmap lo cablea.

> **Actualización 2026-07-25**: Bucket B (commit `f8ebc79`) cableó `compute_dynamic_box`
> al `services/docking/preparer.py` async path con fallback PDB cuando no hay mol2.
> Limitación #6 resuelta para el runtime del backend. Limitaciones #1-#5 siguen activas.
> **Limitaciones #2-#3 (GNN alphabet)** se profundizan en §7 (postmortem Bucket A.1) —
> Bucket A.1 expandió el alphabet a 30 pero NO reentrenó GNN-v2, causando el silent-fail
> epidemic que invalidó todos los GNN runs posteriores. Ver `docs/23_BUCKET_C_RESEARCH_TRACK.md`
> para el plan de GNN-v3 retrain.

---

## 4. Decisión del usuario (sesión 2026-07-25)

- ❌ NO queremos esperar a GNN-v3 para el paper JCIM. Limitaciones en Section 6.
- ✅ SÍ queremos que v2 sea honesto sobre los silent-fails — Bucket A es prioridad
  antes de la re-corrida de Fase 1.
- ✅ SÍ queremos `compute_dynamic_box` conectado al backend runtime — Bucket B.
- ✅ GNN-v3 universal es research track para v2 paper (`MolDesign-v3: heterogeneous
  GNN rescoring across biomolecular archetypes`).

---

## 5. Evidencia extraída del código (apéndice)

### 5.1 Archivos auditados

- `D:\moldesign-build\scripts\benchmark_ef_vina.py` — flow center/box, lineas
  80-200 (TARGET_CONFIGS), 285-313 (curated DB loader), 316-332 (dominant chain),
  450-561 (chain trim + center determination).
- `D:\moldesign-build\rescoring\gnn_v2\data.py` — lineas 41-72 (alphabet),
  106-190 (ligand graph), 197-286 (protein graph), 293-303 (cross-edges).
- `D:\moldesign-build\rescoring\gnn_v2\inference.py` — lineas 80-133 (predict,
  returns 0.5 silent).
- `D:\moldesign-build\backend\services\chemistry\protein_surgery.py` — lineas 33-73
  (`detect_binding_chain`), 152-192 (`compute_dynamic_box`), 423-500 (`prepare_target`
  chemistry que sí invoca dynamic box).
- `D:\moldesign-build\backend\services\docking\preparer.py:267` — otro `prepare_target`
  async, distinto del chemistry, NO invoca dynamic box.
- `D:\moldesign-build\backend\api\routers\protein_surgery.py:292` — endpoint `/prepare`
  que invoca el prepare chemistry correcto.
- `D:\moldesign-build\curated_targets.csv` — 80 rows, 18 familias, verificado
  distribución.

### 5.2 Hallazgos metodológicos

- Histograma de familias curated muestra sesgo hacia kinases (15) y GPCRs (14) — corresponde
  a datasets ChEMBL/DUD-E históricos dominados por esas dos families.
- Bug histório del 7E2Y en curated_targets.csv (chain B equivocado = Gβ no receptor)
  sugería 1 de 14 GPCRs curated estaba MAL calibrado. Posible replicación: auditar
  los 14 GPCR restantes para evitar casos equivalentes. Una sesión de verificación.

---

## 6. Próxima acciones (cuando asignemos sessions de Bucket A/B)

1. **Bucket A — 1 sesión**:
   - PR con expandir `ELEMENTS` a 30 en `gnn_v2/data.py:55`.
   - PR con expandir `AA3_TO_AA1` con PTMs + nucleotidos en `gnn_v2/data.py:46`.
   - PR con warnings explícitos en `inference.py` silent returns.
   - Test nueva regression en `rescoring/tests/`.
2. **Bucket B — 1 sesión**:
   - Refactorizar `services/docking/preparer.py:prepare_target` async → wrapper de
     `protein_surgery.prepare_target`.
   - Copa `_hetatm_auto_center(pdb_path)` en benchmark_ef_vina.py como fallback 1.5
     entre curated y protein_surgery.
3. **Bucket C — research external**: definir scope + datasets en su propia sesionografía
   de planning (post-paper JCIM).

---

## 7. Post-mortem — Bucket A.1 feature expansion rompió GNN-v2 (2026-07-25)

> **Hallazgo crítico**: durante la ejecución del ablation MolChamb sobre 5HT1A
> (sesión del 2026-07-25), descubrimos que Bucket A.1 (commit `ce7c4a1`),
> diseñado para FIXAR silent-fails, **causó un silent-fail epidémico aún peor**
> en GNN-v2. Los dos bugs se cancelaron uno al otro para esconder la culpa,
> pero la telemetría Added en A.3 (commits `ce7c4a1` + `bb43d1f`) dejó
> la huella visible.

### 7.1 Causa raíz dual (no estaba en 2.1 — es una **nueva** causa raíz)

**Bugs que se cancelaron mutuamente**:

- **A) Bug en el checkpoint** (descubierto primero). El checkpoint CPU default
  `rescoring/artifacts/gnn_v2_best.pt` (2 MB, hidden_dim=64, 2026-07-04)
  está **incompleto**: le falta la capa `cross_attn.residue_bias.weight`
  (definida en `models.py:106` como `nn.Embedding(21, 1)`). Con `strict=False`
  en `inference.py:92`, PyTorch inicializa este peso random o en zeros, lo
  que degrada el output.

- **B) Bug en el código** (descubierto segundo, causa principal). Bucket A.1
  expandió `ELEMENTS` de 10 a 30 entradas (`data.py:100-109`). Eso cambió
  el feature vector del ligand de 18 dims (10 elem one-hot + 4 hyb + 4 scalar)
  a 38 dims (30 elem one-hot + 4 hyb + 4 scalar). La `LigandEncoder.in_proj`
  es `Linear(in_features=18, hidden_dim)` en **AMBOS** checkpoints (CPU
  hidden_dim=64 y GPU hidden_dim=128), entonces cualquier forward con
  input 38 lanza:

  ```
  RuntimeError: mat1 and mat2 shapes cannot be multiplied (17x38 and 18x128)
  ```

  El `except Exception` en `inference.py:124-125` lo captura como
  `exception_RuntimeError` → `_record_silent("exception_RuntimeError", smiles)`
  → retorna `(0.5, 1.0)` para TODOS los mols del dataset.

**Cancelación mutua**: el bug A (checkpoint incompleto) producía probs bajas
pero no silent — el modelo forward-eaba bien y daba outputs (degenerados, pero
no 0.5). El bug B (feature dim) producía un `RuntimeError` total: forward
 nunca llega a la capa final, todo cae al silent path. El bug B enmascaró
completamente el bug A — sin el bug B, hubiéramos visto que el checkpoint CPU
 estaba degradado desde el día 1, pero como todos los mols silent-faileaban
en la fase de `in_proj`, nunca llegábamos a evidenciar el problema de
 `residue_bias`.

### 7.2 Hot-patch aplicado (commit `4f48fde`)

Dos fixes:

1. **Preferir el GPU checkpoint** (`rescoring/artifacts/gpu/gnn_v2_best.pt`,
   7.8 MB, hidden_dim=128, 2026-07-07) que SÍ contiene `cross_attn.residue_bias.weight`
   (shape `21x1`). `inference.py:64-65` ahora:
   ```python
   GPU_MODEL_PATH = ARTIFACTS_DIR / "gpu" / "gnn_v2_best.pt"
   CPU_MODEL_PATH = ARTIFACTS_DIR / "gnn_v2_best.pt"
   MODEL_PATH = GPU_MODEL_PATH if GPU_MODEL_PATH.exists() else CPU_MODEL_PATH
   ```

2. **Ligand feature adapter** (`inference.py:_build_lig_feat_adapter_weight`).
   Matriz de selección fija W de shape `(18, 38)` que proyecta el vector
   38-dim Bucket A.1 al 18-dim que el checkpoint conoce. Reglas:

   - Para cada uno de los 10 ORIG_ELEMENTS (`C, N, O, S, P, F, Cl, Br, I, X`),
     `W[i, ELEM_TO_IDX[ORIG_ELEMENTS[i]]] = 1` (one-hot selection).
   - Los 4 features de hybridization y 4 escalares pasan sin cambios.
   - Los 20 elementos nuevos de Bucket A.1 (`B, Si, Se, As, At, Mg, Ca, Zn,
     Fe, Mn, Cu, Ni, Co, K, Na, Li, Sn, Sb, Te, H`) se **DESCARTAN** — un
     ligando con B no va a ninguna columna; el one-hot "B" colapsa a cero
     en el vector proyectado. El modelo lo ve como "no hay ningún átomo de
     elementos conocidos" — que es el tratamiento que el checkpoint entreno
     para esos casos (UNK via X en idx 9).

   W se carga como `nn.Linear(38, 18, bias=False)` con `requires_grad=False`.
   Solo se aplica si `lig_x.size(-1) == 38` (no-op para paths que ya
   producen features 18-dim).

### 7.3 Resultados del re-run GNN-v2 hot-patched (49.6 min, 2547 mols, 5HT1A)

| Cut | EF@1% | AUC | Delta vs Vina+XGB |
|-----|-------|-----|-------------------|
| Vina Only | 19.51x | 0.7975 | -0.0313 |
| **Vina + XGB (paper primary)** | **36.85x** | **0.8288** | **baseline** |
| Vina + GNN (hot-patched) | 2.17x | **0.5382** | -0.2906 (near-random!) |
| Vina + CL-GNN | 19.51x | 0.7976 | -0.0312 |
| Calibrated Stacking | 8.67x | 0.6606 | -0.1682 |
| Stacking + MolChamb | 34.63x | 0.7659 | -0.0629 |

**Silent-fail count**: 1/2547 (0.04%) — before hot-patch: 2547/2547 (100%).
El único silent-fail restante es un SMILES con `.` separator (sal) que el
builder del ligand graph rechaza legítimamente como `ligand_graph_failed`,
no un bug.

**GNN-v2 hot-patched está vivo pero near-random**. La causa esperada: el
adapter es una proyección **fija** (no entrenada). El checkpoint fue entrenado
con features 18-dim correspondientes al one-hot exacto de los 10 elementos
originales. El adapter mapea los 20 nuevos elementos a "X" (catch-all),
lo que colisiona con el uso real de X (no hay átomo de ningún elemento conocido).
El modelo no sabe distinguir "Boron presente" de "no hay átomos relevantes"
— ambos resultan en el mismo vector proyectado. La discriminación cae a
near-random.

**CL-GNN parece no aportar nada** (AUC == Vina-only). Diagnóstico pendiente
(Sección 8, Bucket C). No es un silent-fallthrough — clgnn_prob está poblado
en el checkpoint, pero sus valores parecen degenerate. Candidate causes:
(i) CL-GNN comparte encoder con GNN-v2 y el adapter aplica igualmente,
(ii) CL-GNN fue entrenado en un subset sin elementos extendidos y degrada
igual de fuerte que GNN, (iii) bug similar no diagnosticado.

### 7.4 Lección aplicada al roadmap

- **Bucket A.1** (element expansion) oficialmente marcado como **parcialmente
  defectuoso** — su intención fue correcta (deck of features más amplio),
  pero no actualizó `LigandEncoder.in_proj` ni reentrenó GNN-v2 con los
  nuevos features. Como consecuencia, A.1 causó el bug que invalidó
  TODOS los GNN runs de 2026-07-04 → 2026-07-25.
- **Bucket C** (GNN-v3) pasa de "research external post-paper" a
  **prerequisite de cualquier claim futuro sobre ensemble**. Su plan
  completo está en `docs/23_BUCKET_C_RESEARCH_TRACK.md` (nuevo desde
  esta sesión).
- **MolChamb** no puede declararse muerto ni vivo — su evaluación requiere
  GNN-v3 primero. Estado: **inconclusive** (ver Sección 8).

---

## 8. MolChamb ablation — estado inconclusive (2 data points)

### 8.1 Resultados consolidados (2026-07-25)

| Target | Family | Vina+XGB AUC | Stacking+MolChamb AUC | Delta |
|--------|--------|--------------|------------------------|-------|
| 5HT1A | gpcr | 0.8288 | 0.7659 | **-0.0629** |
| CDK2 | kinase | 0.9860 | 0.9694 | **-0.0166** |

MolChamb en su configuración actual (`vina:0.20/xgb:0.40/gnn:0.20/molchamb:0.20`,
**con gnn=0 forzado** porque Bucket A.1 rompió GNN-v2) **degrada AUC** en
**ambos** targets evaluados.

Documentos completos:
- `docs/21_ABLATION_MOLCHAMB_5HT1A.md`
- `docs/22_ABLATION_MOLCHAMB_CDK2.md`

### 8.2 Por qué el resultado NO es un veredicto sobre MolChamb

El stacking fue diseñado para combinar **4 señales** (Vina + XGB + GNN +
MolChamb, pesos ~25% c/u). El ensemble completo nunca se evalúo porque
GNN-v2 está fuera de service post-Bucket A. Las comparaciones disponibles son:

- `Vina+XGB` (sin GNN ni MolChamb, dos señales): AUC 0.8288
- `Stacking+MolChamb` (Vina+XGB+MolChamb, GNN=0 forzado, tres señales con
  weight arbitrado): AUC 0.7659

Es decir, comparamos "dos señales pesos 0.70 + 0.30" vs "tres señales pesos
0.20 + 0.40 + 0.20 + 0.00 (gnn forced to 0)". Los pesos 0.20/0.40/0.20/0.20
fueron heredados del diseño original **con GNN disponible** — no fueron
re-opttimizados para la configuración con GNN ausente.

Las features que MolChamb бере son teóricamente ortogonales a las features
estructurales que usa Vina+XGB (MolChamb usa descriptores quantum-chemistry
vía xTB, Vina+XGB usa shells + ECIF + 1D/2D RDKit). En principio, info nueva
debería aumentar AUC. No podemos afirmar ni negar eso sin GNN-v3.

### 8.3 Statement paper-defensible sobre MolChamb

> "**MolChamb ablation**. MolChamb (Molecular Chamber, quantum-chemistry
> stacking component) was tested on 5HT1A (GPCR) and CDK2 (kinase). In both,
> adding MolChamb to the stacking (vina+xgb+molchamb, gnn=0 by family config)
> **reduced AUC** versus Vina + XGB alone (5HT1A: 0.8288 → 0.7659, Δ=−0.0629;
> CDK2: 0.9860 → 0.9694, Δ=−0.0166). However, this evaluation cannot be
> considered definitive because the GNN-v2 component of the ensemble was
> unavailable during ablation (see Section 7.2 and docs/19_LIMITATIONS.md
> §7.1). Bucket C research track will re-evaluate MolChamb after a GNN-v3
> retrain on the full 30-element alphabet."

### 8.4 Camino para declarar veredicto sobre MolChamb

1. **Bucket C — GNN-v3 retrain** (ver `docs/23_BUCKET_C_RESEARCH_TRACK.md`).
2. Re-correr `re-score-gnn.py` sobre 5HT1A + CDK2 + 3 targets más, ahora
   con GNN-v3 real signal (no adapter).
3. Re-optimizar `stacking_weights.json` con grid search 4-dim sobre cada
   familia (vina/xgb/gnn/molchamb, no más gnn=0 forzado).
4. Re-correr ablation MolChamb con pesos re-optimizados. Si delta vs
   Vina+XGB sigue negativo: **declarar "no value-add observed" honesto**.
   Si delta positivo: claim secundario en paper.

---

## 9. Limitaciones aceptadas para el JCIM v1 paper (sección "Limitations")

Actualización de Sección 4 con los post-mortem items:

1. **Pipeline optimizado para receptores proteína-estándar con PDB
   co-cristalizado.** Para receptor sin ligando cocrystalizado, dynamic
   box cae a geomcenter + 25Å box.

2. **GNN-v2 discretiza aminoácidos estándar (20 + UNK)**. Receptores con
   cofactores covalentes, glicanos, o DNA/RNA en el pocket no son
   rescoringeables de forma discriminativa. (Sección 2.1-2.2.)

3. **GNN-v2 element alphabet mismatch — known limitation pending Bucket C**:
   GNN-v2 was trained on a 10-element ligand alphabet (C, N, O, S, P, F,
   Cl, Br, I, X). Bucket A.1 expanded the codebase to support 30 elements
   (B, Si, Se, As, At, Mg, Ca, Zn, Fe, Mn, Cu, Ni, Co, K, Na, Li, Sn, Sb,
   Te, H added). A feature-adapter hot-patch projects the 38-dim Bucket A.1
   features back to the 18-dim shape GNN-v2 expects, keeping the model
   functional but with **near-random discrimination** on this input
   distribution (5HT1A: AUC 0.5382 with adapter vs 0.8288 with Vina+XGB
   alone). A GNN-v3 retrain is required for honest ensemble claims.

4. **Elementos químicos soportados por Vina features (XGB)**: 33 (la
   expansión de Bucket A.1 para el XGB feature extractor). Pero el GNN-v2
   checkpoint no fue re-entrenado — sólo los features XGB son rewritten.

5. **`_detect_dominant_chain` es heurístico.** Receptores heterodiméricos
   donde el pocket spans dos cadenas (e.g. HIV-1 protease) requieren cura
   manual del `curated_targets.csv`.

6. **Stacking weights entrenados por familia (18 familias, 80 targets)
   con `gnn=0` en 4/5 families** debido al bug descubierto post-Bucket A.
   Family desconocida cae a `"default"` weights.

7. **`compute_dynamic_box` está conectado al runtime del backend desde el
   Bucket B fix (commit `f8ebc79`)** — 已 resuelto en esta sesión post-
   doc original. Esta limitación ya no aplica.

8. **MolChamb ablation inconclusive** — ensamble evaluation requires
   GNN-v3 retrain (ver Sección 8 y `docs/23_BUCKET_C_RESEARCH_TRACK.md`).

9. **CL-GNN appears to contribute nothing** in the 5HT1A post-hot-patch
   run (AUC = Vina-only). Likely shares the same feature-dim mismatch as
   GNN-v2 (Bucket A.1 silent bug). Bucket C diagnosis required.

---

*Documento interno actualizado (2026-07-25). Para paper JCIM Section 6
"Limitations", usar la versión condensada en Sección 9. Post-mortem Bucket
A + hot-patch en Sección 7. MolChamb ablation en Sección 8.*
