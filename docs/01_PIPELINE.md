> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Pipeline Cientifico de MolDesign AI

## Diagrama de Flujo Principal

```mermaid
flowchart TD
    A[Usuario ingresa SMILES] --> B{Modo?}
    B -->|EDU| C[Evaluacion simplificada]
    B -->|PRO| D[Evaluacion completa]
    
    C --> E[01. Validacion + PAINS]
    D --> E
    
    E --> F{SMILES valido?}
    F -->|No| G[Rechazar: error de valencia/quimica]
    F -->|Si| H[02. Propiedades + Drug-likeness]
    
    H --> I[03. ADMET Real]
    I --> J[04. Conformer 3D + Protonacion]
    
    J --> K{Es peptido?}
    K -->|Si| L[Nivel 3: ESMFold / ColabFold]
    K -->|No| M[Nivel 1: AutoDock Vina]
    
    L -->|Exito| N[Poses peptidicas]
    L -->|Fallo| M
    
    M --> O[Nivel 2: Rescoring ML]
    O --> P[XGBoost corrige afinidad]
    O --> Q[GNN RTMScore valida geometria]
    
    P --> R[06. Scoring Compuesto]
    Q --> R
    
    R --> S{PRO: Selectividad?}
    S -->|Si| T[Docking contra anti-targets]
    T --> U[Ratio de selectividad]
    S -->|No| V[Scoring final]
    U --> V
    
    V --> W{PRO: MM-GBSA?}
    W -->|Si| X[OpenMM rescoring GPU/CPU]
    W -->|No| Y[08. PDF + DB persist]
    X --> Y
    
    Y --> Z[Resultado final]
```

---

## Pipeline Detallado por Etapa

### 01 — Validacion Quimica + PAINS

```mermaid
flowchart LR
    A[SMILES] --> B[RDKit: Canonicalizacion]
    B --> C[Validacion estructural]
    C --> D{Filtros PAINS}
    D -->|480 patrones| E[Sin PAINS?]
    E -->|Si| F[Pasar]
    E -->|No| G[ALERTA: marcar molecula]
    
    C --> H{Lipinski}
    C --> I{Veber}
    C --> J{Ghose}
    C --> K{Egan}
    C --> L{Muegge}
    C --> M[Fsp3]
    C --> N[QED]
    C --> O[SA Score]
```

**Tecnologias:**
- RDKit: MolFromSmiles, canonicalizacion, validacion de valencias
- FilterCatalog: 480 patrones PAINS (Baell & Holloway 2010)
- 6 reglas de drug-likeness: Lipinski, Veber, Ghose, Egan, Muegge, Fsp3

**Archivos:** `chem/validator.py`, `chem/pains.py`, `chem/properties.py`

---

### 02 — ADMET Real (NO mock)

```mermaid
flowchart TD
    A[SMILES canonico] --> B[ADMET-AI 2.0]
    A --> C[TabPFN 8.0]
    
    B --> D[Solubilidad LogS]
    B --> E[Union proteinas PPB]
    B --> F[BBB permeability]
    B --> G[HIA absorcion]
    B --> H[hERG cardiotoxicidad]
    B --> I[CYP3A4 inhibicion]
    B --> J[CYP2D6 inhibicion]
    B --> K[CYP2C9 inhibicion]
    B --> L[Clearance hepatico]
    
    C --> M[Toxicidad sistemica]
    
    D & E & F & G & H & I & J & K & L --> N[MPO Score]
    M --> N
    N --> O[Blood Viability Score 0-100]
```

**Tecnologias:**
- ADMET-AI: Ensamble Chemprop (D-MPNN) de Swanson et al.
- TabPFN: Transformer para clasificacion tabular in-context
- MPO: Multi-Parameter Optimization score geometrico

**Archivos:** `chem/blood_viability.py`, `chem/properties.py`

---

### 03 — Conformer 3D + Protonacion

```mermaid
flowchart LR
    A[SMILES] --> B[ETKDG v3]
    B --> C[MMFF94 minimizacion]
    C --> D[dimorphite-DL]
    D --> E[Protonacion pH 7.4]
    E --> F[Conformer 3D listo]
```

**Archivos:** `chem/conformer.py`

---

### 04 — Docking Molecular (Nivel 1)

```mermaid
flowchart TD
    A[Target PDB] --> B[Descarga RCSB]
    B --> C[Cache local]
    C --> D[Meeko: filtrar cadena]
    D --> E[Meeko: agregar H + cargas]
    E --> F[Meeko: PDBQT preparado]
    
    G[Ligando SDF] --> H[Meeko: preparar ligando]
    H --> I[Ligando PDBQT]
    
    F --> J[AutoDock Vina]
    I --> J
    
    J --> K[5 poses ranqueadas]
    K --> L[Meeko: exportar SDF]
    L --> M[Hotspot analysis]
```

**Tecnologias:**
- AutoDock Vina 1.2.5: Iterated Local Search, exhaustiveness=8
- **Vina-GPU Hybrid** (opcional, v1.5+): GPU search (OpenCL, 2s) + CPU refine fp64 (0.06s) = 30× speedup
- Meeko: preparacion de receptor y ligando, exportacion SDF
- ProDy: parseo mejorado de PDB (opcional)

**Archivos:** `services/docking/vina_service.py`, `services/docking/preparer.py`
**Modulo GPU:** `D:\ad-gpu-project\` — Ver [10_VINA_GPU_HYBRID.md](10_VINA_GPU_HYBRID.md)

---

### 05 — Rescoring ML (Nivel 2)

```mermaid
flowchart TD
    A[Poses de Vina] --> B[Extraer features Shell]
    A --> C[Extraer features ECIF]
    
    B & C --> D{XGBoost}
    D --> D2[¿Familia detectada?]
    D2 -->|GPCR| D3[XGBoost gpcr-trained]
    D2 -->|kinase| D4[XGBoost kinase-trained]
    D2 -->|protease| D5[XGBoost protease-trained]
    D2 -->|soluble_enzyme| D6[XGBoost soluble-trained]
    D2 -->|unknown| D7[XGBoost universal fallback]
    D3 & D4 & D5 & D6 & D7 --> E[Afinidad corregida]
    
    B & C --> F[GNN RTMScore]
    F --> G[Score geometrico]
    
    E --> H[Clasificador Binario]
    H --> I[Probabilidad binder pKi>7]
    
    E --> J[SHAP: explicabilidad]
    F --> K[GNN attention map]
    
    I --> L[Factor de concordancia]
    G --> L
    L --> M[Farmacoforos]
```

**NOTA (fix #3):** Las interacciones ProLIF (puentes H, pi-stacking, etc.)
ya NO se usan como features de regresion (daban ρ=-0.035 en GPCRs).
Se extraen pero solo se exponen en la respuesta API para visualizacion
en el visor 3D (Molstar).

**Tecnologias:**
- XGBoost 2.1: modelos por familia estructural (gpcr, kinase, protease, nuclear_receptor, soluble_enzyme) + universal fallback
- RTMScore GNN (PyG): red neuronal de grafos geometrica — **PyTorch Geometric** (nativo en Windows sin DGL)
- SHAP 0.46: valores de explicabilidad por feature
- ProLIF 2.1: interaction fingerprints (reemplaza ODDT)

**Clasificacion por familia:** `structural_family.py` clasifica cada receptor PDBbind en 6 familias via
`family_map.json` (865 complejos curados). Si la familia tiene ≥15 complejos, se usa su modelo
entrenado especificamente. Caso contrario → fallback al modelo universal.

**GPU:** PyTorch Geometric detecta CUDA automaticamente (`torch.cuda.is_available()`). Para una sola
molecula, CPU es mas rapido (~1.7s vs 3.0s por overhead de GPU). Para batch ≥2, GPU gana 3-7x.
El sidecar usa CPU por defecto para single-molecule inference.

**Archivos:** `rescoring/app.py`, `rescoring/feature_extractor.py`, `rescoring/model_manager.py`
(family routing), `rescoring/structural_family.py`, `rescoring/gnn_service.py`,
`rescoring/RTMScore/model/model2_pyg.py` (PyG), `rescoring/RTMScore/feats/mol2graph_pyg.py` (PyG),
`services/docking/rescoring_client.py`

---

### 06 — Scoring: Ranking vs Flags (fix #2 Spearman)

```mermaid
flowchart LR
    subgraph "RANKING (total_score)"
        A[Afinidad Vina] --> B[Factor GNN]
        B --> C[Afinidad ajustada]
        C --> D[Factor especificidad]
        D --> E[total_score 0-100]
    end
    
    subgraph "FLAGS (no afectan ranking)"
        F[ADME profile] --> G[Flag Rojo/Verde]
        H[Drug-likeness] --> I[Flag Rojo/Verde]
        J[SA Score] --> K[Penalizacion informativa]
        L[Blood Viability] --> M[Flag Rojo/Verde]
    end
    
    E --> N[Ranking de afinidad pura]
    G & I & K & M --> O[Panel de perfil farmacocinetico]
```

**IMPORTANTE (fix #2):** `total_score` = SOLO afinidad de union.
ADME, Drug-likeness, SA, Blood Viability son flags informativos que
el quimico medicinal consulta en el panel, no variables de ranking.

**Benchmark**: El composite original (mezclando ADME) daba ρ=-0.11 en 5-HT1A.
Vina solo daba ρ=+0.19. Al desacoplar, el ranking refleja afinidad pura.

**Archivos:** `scoring/engine.py`, `scoring/normalizer.py`

---

### 07 — Selectividad Multi-Target (PRO)

```mermaid
flowchart TD
    A[Molecula evaluada] --> B{PRO + selectividad ON?}
    B -->|Si| C[Panel anti-targets]
    B -->|No| Z[Skip]
    
    C --> D[Dock vs hERG]
    C --> E[Dock vs CYP3A4]
    C --> F[Dock vs 5-HT2B]
    C --> G[Dock vs PDE3A]
    C --> H[Dock vs NaV1.5]
    C --> I[Dock vs user anti-targets]
    
    D & E & F & G & H & I --> J[Ratio = ON / maxOFF]
    J --> K{Veredicto}
    K -->|> 10x| L[ALTAMENTE SELECTIVO]
    K -->|> 3x| M[SELECTIVO]
    K -->|> 1.5x| N[MODERADO]
    K -->|> 1x| O[BAJA SELECTIVIDAD]
    K -->|< 1x| P[NO SELECTIVO — ALTO RIESGO]
```

**Anti-targets default:**
- hERG (5VA1): canal de potasio cardiaco — arritmia
- CYP3A4 (4NY4): metabolismo hepatico — interacciones droga-droga
- 5-HT2B (4NC3): receptor de serotonina — valvulopatia
- PDE3A (1SO2): fosfodiesterasa — contractilidad
- NaV1.5 (6MVW): canal de sodio — conduccion

**Anti-targets del usuario:** cualquier PDB subido con `is_anti_target=true`

**Archivos:** `services/docking/selectivity.py`, `api/routers/pro_features.py`

---

### 08 — MM-GBSA Rescoring (PRO)

```mermaid
flowchart TD
    A[Top pose de Vina] --> B[PDB crudo de RCSB]
    B --> C[PDBFixer: remover aguas/ligandos]
    C --> D[PDBFixer: agregar atomos faltantes]
    D --> E[PDBFixer: agregar H a pH 7.4]
    E --> F[Complejo reparado proteina-ligando]
    F --> G[OpenMM: ForceField AMBER14SB]
    G --> H[Solvente implicito OBC2 GBSA]
    H --> I[Minimizacion 1000 pasos]
    I --> J{GPU disponible?}
    J -->|CUDA| K[~15s en GPU]
    J -->|OpenCL| L[~30s en GPU]
    J -->|CPU| M[~120s en CPU]
    K & L & M --> N[deltaG total]
    N --> O[Componentes: vdW + elec + GB + SASA]
```

**PDBFixer (fix #4):** Los PDBs cristalograficos del RCSB no tienen H y a veces
faltan atomos de cadena lateral. PDBFixer (autores de OpenMM) repara el PDB
antes de pasarlo al motor de fisica. Sin este paso, OpenMM crashea con
`No template found for residue... Missing H atoms`.

**Archivos:** `scoring/mmgbsa.py`

---

### 09 — Visualización de Interacciones ProLIF (v1.2)

```mermaid
flowchart LR
    A[Molecule ID] --> B[GET /evaluation/interactions/{id}]
    B --> C[ProLIF: detecta interacciones]
    C --> D[Coords 3D: lig_x/y/z + prot_x/y/z]
    D --> E[Frontend: buildInteractionsPdb]
    E --> F[Molstar: midpoint spheres]
    F --> G{H Bond?}
    G -->|Si| H[Esfera roja - puente H]
    G -->|No| I{Hidrofobico?}
    I -->|Si| J[Esfera gris]
    I -->|No| K{Pi stacking?}
    K -->|Si| L[Esfera azul]
    K -->|No| M{Puente salino?}
    M -->|Si| N[Esfera amarilla]
    M -->|No| O[Esfera verde - cation pi]
```

Cada interacción se renderiza como una esfera coloreada en el punto medio (midpoint)
entre el átomo del ligando y el átomo de la proteína. El color codifica el tipo:

| Tipo de interacción | Elemento | Color | Visualización |
|--------------------|----------|-------|---------------|
| Puente de H | O | Rojo | `#ff4d4d` |
| Hidrofóbica | C | Gris | `#808080` |
| Pi-stacking | N | Azul | `#4d4dff` |
| Puente salino | S | Amarillo | `#ffff4d` |
| Pi-catión | F | Verde | `#4dff4d` |

**Datos incluidos en API (v1.2):** `ligand_coords` y `protein_coords` en cada interacción.

**Archivos:** `frontend/components/interfaces/pro/AdvancedMolstarViewer.tsx` (buildInteractionsPdb),
`backend/api/routers/interactions.py`, `backend/services/interactions/analyzer.py`

---

### 10 — Búsqueda e Ingesta de Targets (v1.2)

```mermaid
flowchart TD
    A[Usuario escribe nombre] --> B["Ej: 'EGFR', 'CDK4'"]
    B --> C[POST /targets/resolve-name]
    C --> D[RCSB Search API v2]
    D --> E[Resultados: PDB IDs + metadata]
    E --> F[Frontend: tabla seleccionable]
    F --> G[Usuario clickea resultado]
    G --> H[POST /targets/ingest]
    H --> I[Descarga PDB de RCSB]
    I --> J[Cura: pocket, hotspots, cofactores]
    J --> K[Prepara PDBQT]
    K --> L[Target listo para docking]
```

**Arquitectura de búsqueda:**
1. `search_rcsb_by_name()` consulta RCSB Search API v2 (`text` + `contains_phrase`)
2. Para cada resultado, `_fetch_rcsb_entry_detail()` obtiene metadata de RCSB Data API
3. Resultados ordenados por resolución (mejor primero)
4. Al seleccionar, se dispara el pipeline de ingesta existente (`POST /targets/ingest`)

**Archivos:** `backend/utils/file_handlers.py`, `backend/api/routers/targets.py`,
`frontend/components/interfaces/pro/TargetSelectorModal.tsx`

---

## Niveles de Evaluacion

| Nivel | Tecnologia | Que hace | Cuando se usa |
|-------|-----------|----------|---------------|
| **1** | AutoDock Vina | Docking fisico | Siempre (default) |
| **2** | XGBoost + GNN (PyG) | Correccion ML de afinidad + validacion geometrica | Siempre (si sidecar disponible) |
| **2b** | XGBoost por familia | Modelo especifico GPCR/kinase/protease/etc | Siempre (si family_map detecta la familia) |
| **3** | ESMFold / ColabFold | Docking de peptidos por difusion | Molecula con >=3 enlaces peptidicos |
| **PRO** | Panel anti-targets | Safety profiling | Modo PRO activado |
| **PRO** | MM-GBSA | Rescoring con dinamica molecular | Modo PRO + toggle activado |

---

## Metricas de Calidad

| Metrica | Implementacion |
|---------|---------------|
| Spearman rho | Pipeline de benchmark contra PDBbind/ChEMBL (21 targets) |
| RMSD re-docking | Validacion de grid box contra ligando co-cristalizado |
| PAINS coverage | 480 patrones de Baell & Holloway 2010 |
| ADMET accuracy | Modelos Chemprop entrenados en datos curados (ADMET-AI) |
| Uncertainty | Desviacion estandar del ensemble de poses de Vina |

---

## ADMET-AI: Predictivo vs Cache (v1.0)

```mermaid
flowchart TD
    A[SMILES] --> B{ADMET toggle ON?}
    B -->|No| C[ADMET=None — modo rapido ~70s]
    B -->|Si| D{SMILES en cache?}
    D -->|Si| E[Cache hit: ~3s]
    D -->|No| F[ADMET-AI predict: ~140s]
    F --> G[Guardar en cache]
    G --> H[Resultado ADMET real]
    E --> H
    C --> I[Pipeline sin ADMET]
    H --> I
```

### Cache Strategy

| Cache | Key | Lifetime | Impacto |
|-------|-----|----------|---------|
| ADMET | SMILES hash | Hasta reinicio del backend | -140s en 2da+ evaluacion |
| Vina | SMILES + Target | Hasta reinicio del backend | -15s en 2da+ evaluacion |
| PDB | Target PDB ID | Disco (persistente) | -10s preparacion receptor |

---

## Drug-Likeness Completo (v1.0)

6 reglas implementadas:

| Regla | Parametros | Referencia |
|-------|-----------|------------|
| Lipinski Ro5 | MW<=500, LogP<=5, HBD<=5, HBA<=10 | Lipinski 1997 |
| Veber | RotB<=10, TPSA<=140 | Veber 2002 |
| Ghose | MW 160-480, LogP -0.4/5.6, atoms 20-70 | Ghose 1999 |
| Egan | TPSA<=132, LogP -1/5.88 | Egan 2000 |
| Muegge | Score 0-9 (>=2 passes) | Muegge 2001 |
| Fsp3 | Fraccion carbonos sp3 | Lovering 2009 |

---

## SAR: Structure-Activity Relationship (v1.0)

Endpoint: GET /sar/{molecule_id}

Retorna todos los analogos evaluados contra el MISMO target, ranqueados por score.
Incluye delta (?) vs baseline para cada metrica.

Ver [03_API.md](03_API.md) para el detalle del endpoint.

---

## ADMET Toggle + Cache (v1.1)

El usuario puede desactivar ADMET-AI para evaluaciones rapidas (~70s vs ~210s).

Cache por SMILES: misma molecula = mismo resultado ADMET. 2a evaluacion = 3s.

## Login Desktop (v1.1)

Auto-login sin credenciales. El usuario nunca ve pantalla de login.
Cuenta cloud opcional solo para comunidad/atribucion.

## Community (v1.1)

Targets compartidos globalmente. Download con un click. Leaderboard de scores.
Arquitectura hibrida: desktop local + cloud opcional.
