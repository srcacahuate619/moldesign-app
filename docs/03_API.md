> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# API Reference — MolDesign Backend

## Base URL

- **Desktop:** `http://localhost:8000`
- **Cloud:** `http://192.168.1.64:8010` (via ngrok)

---

## Meta / Health

### `GET /`
Root — informacion de la API.

**Response:**
```json
{
  "name": "MolDesign API",
  "version": "1.0.0-mvp",
  "environment": "development",
  "mission": "pipeline cientifico reproducible para diseno molecular asistido"
}
```

### `GET /health`
Health check integral del sistema.

**Response (DESKTOP):**
```json
{
  "status": "healthy",
  "app_mode": "DESKTOP",
  "components": {
    "rdkit": {"status": "healthy", "rdkit_version": "2025.09.6"},
    "vina": {"status": "healthy", "path": "tools/vina/vina.exe"},
    "database": {"status": "healthy", "engine": "SQLite"},
    "storage": {"status": "healthy", "engine": "local_disk"},
    "redis": {"status": "not_required"}
  }
}
```

### `GET /hardware`
Hardware detection para configuracion adaptativa.

**Response:**
```json
{
  "cpu": {"model": "Ryzen 5 5500", "cores_physical": 6, "cores_logical": 12},
  "ram": {"total_gb": 32.0, "available_gb": 19.2},
  "gpu": {"available": true, "name": "RTX 1660 SUPER", "vram_gb": 6.0, "cuda": true, "opencl": false},
  "recommendations": {"workers": 6, "parallel_docks": 3},
  "warnings": []
}
```

### `GET /hardware/estimate`
Estimacion de tiempo de evaluacion.

**Params:** `mode` (edu/pro), `anti_targets` (int), `mmgbsa` (bool)

**Response:**
```json
{
  "total_seconds_min": 120, "total_seconds_max": 232,
  "total_description": "Evaluacion completa — tarda lo que un cafe",
  "conformer_docking": "35s",
  "anti_targets": "+5 targets en 2 batches (~70s)",
  "mmgbsa": "15s (GPU CUDA acelerado)"
}
```

---

## Chemistry

### `POST /chem/validate`
Validar un SMILES.

**Body:** `{"smiles": "CC(=O)Oc1ccccc1C(=O)O"}`

**Response:**
```json
{
  "is_valid": true,
  "canonical_smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "smiles_hash": "56de9fef...",
  "molecular_formula": "C9H8O4",
  "heavy_atom_count": 13,
  "errors": [], "warnings": []
}
```

---

## Evaluation

### `POST /evaluation/submit`
Enviar una molecula para evaluacion.

**Body:**
```json
{
  "smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "target_pdb_id": "7E2Y",
  "molecule_name": "Aspirina",
  "is_control": false,
  "grid_center": [103.03, 114.79, 108.36],
  "grid_size": [25.0, 25.0, 25.0],
  "custom_hotspots": ["ASP189", "TYR228"],
  "peptide_docking_engine": "esmfold",
  "pipeline_config": {
    "enabled_stages": ["validation", "properties", "conformer", "docking", "rescoring"],
    "stage_params": {},
    "pro_workers": 6,
    "pro_parallel_docks": 3,
    "pro_selectivity": true,
    "pro_anti_targets": ["5VA1", "4NY4"],
    "pro_mmgbsa": false,
    "docking_engine": "vina",
    "gnn_precision": "fp32"
  }
}
```

**Response:** `202 Accepted`
```json
{
  "task_id": "uuid",
  "status": "submitted",
  "target_pdb_id": "7E2Y",
  "smiles_hash": "56de9fef..."
}
```

### `GET /evaluation/status/{task_id}`
Consultar estado de una evaluacion.

**Response:**
```json
{
  "task_id": "uuid",
  "status": "SUCCESS",
  "progress": 100,
  "result": {
    "molecule_id": "uuid",
    "total_score": 58.4,
    "affinity_kcal": -6.85,
    "molecular_weight": 180.16,
    "log_p": 1.31,
    "tpsa": 63.6,
    "lipinski_pass": true,
    "veber_pass": true,
    "ghose_pass": false,
    "egan_pass": true,
    "muegge_pass": true,
    "muegge_score": 8,
    "fsp3": 0.111,
    "is_pains": false,
    "pains_matches": [],
    "blood_viability_score": 79.4,
    "blood_bbb_permeable": false,
    "druglikeness_score": 55.0,
    "adme_score": 68.0,
    "docking_poses": [...],
    "target_spearman_rho": 0.73,
    "specificity_score": 72.0,
    "selectivity_ratio": 4.2,
    "selectivity_ran": true,
    "anti_target_results": [...]
  },
  "error": null
}
```

### `GET /evaluation/ai-report/{molecule_id}`
Obtener reporte de IA (Gemini/Claude/Ollama).

### `GET /evaluation/files/poses/{molecule_id}`
Descargar archivo SDF de poses de docking.

### `GET /evaluation/files/protein/{molecule_id}`
Descargar archivo PDB del target.

### `GET /evaluation/files/complex/{molecule_id}`
Descargar complejo proteina-ligando en PDB.

---

## Batch Screening

### `POST /evaluation/batch`
Cribado virtual masivo.

**Form data:** `file` (.csv/.xlsx/.sdf/.smi), `target_pdb_id`, `num_workers`

**Response:**
```json
{
  "batch_id": "uuid",
  "total_molecules": 50,
  "invalid_skipped": 2,
  "target_pdb_id": "7E2Y",
  "status": "running",
  "estimated_seconds": 420
}
```

### `GET /evaluation/batch/{batch_id}`
Consultar progreso y resultados parciales.

### `GET /evaluation/batch/{batch_id}/export`
Descargar Excel con 22 columnas, ranqueado mejor→peor.

**Columnas:** Rank, Name, SMILES, Score, Affinity, MW, LogP, TPSA, HBD, HBA, Lipinski, Veber, Ghose, Egan, Muegge, Fsp3, QED, SA Score, PAINS, ADMET Score, BBB, hERG Alerts

### `GET /evaluation/batch/{batch_id}/csv`
Descargar CSV para pipelines externos.

---

## Interaction Analysis

### `GET /evaluation/interactions/{molecule_id}`
Protein-Ligand Interaction Fingerprint (PLIF).

**Params:** `pose_rank` (1-20, default 1)

**Response (v1.2):**
```json
{
  "molecule_id": "uuid",
  "target_pdb_id": "7E2Y",
  "pose_rank": 1,
  "total_interactions": 23,
  "summary": {"hbond": 8, "hydrophobic": 12, "pi_stacking": 3},
  "interactions_by_type": {
    "hbond": [
      {
        "residue": "ASP189A",
        "residue_name": "ASP",
        "residue_number": 189,
        "residue_chain": "A",
        "ligand_atom": "O4",
        "protein_atom": "OD2",
        "distance": 2.8,
        "angle": 162.5,
        "strength": "moderate",
        "ligand_coords": {"x": 12.3, "y": 45.6, "z": 23.1},
        "protein_coords": {"x": 10.1, "y": 43.2, "z": 25.0}
      }
    ],
    "hydrophobic": [...],
    "pi_stacking": [...]
  },
  "pharmacophore_features": {
    "donor": [[12.3, 45.6, 23.1]],
    "acceptor": [[10.1, 43.2, 25.0]]
  },
  "interactions": [
    {
      "type": "hbond",
      "residue": "ASP189A",
      "residue_name": "ASP",
      "residue_number": 189,
      "residue_chain": "A",
      "ligand_atom": "O4",
      "protein_atom": "OD2",
      "distance": 2.8,
      "angle": 162.5,
      "strength": "moderate",
      "ligand_coords": {"x": 12.3, "y": 45.6, "z": 23.1},
      "protein_coords": {"x": 10.1, "y": 43.2, "z": 25.0}
    }
  ]
}
```

**Nota v1.2:** Cada interacción ahora incluye `ligand_coords` y `protein_coords` (coordenadas 3D en Å)
para renderizado directo en el visor Molstar. El array plano `interactions` facilita el consumo
sin tener que aplanar `interactions_by_type`.

---

## PRO Features

### `GET /pro/anti-targets`
Listar anti-targets disponibles (defaults + usuario).

**Response:**
```json
{
  "anti_targets": [
    {"pdb_id": "5VA1", "name": "hERG", "category": "Cardiac", "threshold_kcal": -7.0, "source": "default"},
    {"pdb_id": "4NY4", "name": "CYP3A4", "category": "Metabolism", "threshold_kcal": -8.0, "source": "default"},
    {"pdb_id": "XYZ1", "name": "MiTarget", "category": "Custom", "threshold_kcal": -7.0, "source": "user"}
  ]
}
```

### `POST /pro/selectivity/{molecule_id}`
Ejecutar panel de selectividad multi-target.

**Params:** `num_workers`, `anti_targets` (comma-separated PDB IDs)

**Response:**
```json
{
  "molecule_id": "uuid",
  "on_target": {"pdb_id": "7E2Y", "affinity_kcal": -8.50},
  "selectivity_ratio": 4.2,
  "selectivity_verdict": "SELECTIVO — Buen margen terapeutico",
  "off_targets": [
    {"pdb_id": "5VA1", "name": "hERG", "affinity": -5.20, "status": "ok"},
    {"pdb_id": "4NY4", "name": "CYP3A4", "affinity": -6.80, "status": "ok"}
  ],
  "safety_flags": [],
  "execution_time_s": 72.5
}
```

### `POST /pro/mmgbsa/{molecule_id}`
Ejecutar MM-GBSA rescoring.

**Params:** `pose_rank` (1-5), `num_steps` (500-5000)

**Response:**
```json
{
  "molecule_id": "uuid",
  "pose_rank": 1,
  "delta_g_total_kcal": -12.45,
  "components": {"vdw": -38.2, "electrostatic": -15.3, "gb_polar": 28.1, "nonpolar_sasa": -5.1},
  "minimized": true,
  "platform": "CUDA",
  "execution_time_s": 15.3
}
```

### `GET /pro/gpu`
Estado de aceleracion GPU.

---

## Targets

### `GET /targets/`
Listar todos los targets.

### `POST /targets/resolve-name` (v1.2)
Buscar estructuras en RCSB PDB por nombre de proteína.

**Body:**
```json
{
  "query": "EGFR",
  "max_results": 10
}
```

**Response:**
```json
{
  "query": "EGFR",
  "total": 5,
  "source": "RCSB PDB (Search API v2)",
  "results": [
    {
      "pdb_id": "7AEM",
      "title": "Crystal structure of EGFR kinase domain in complex with...",
      "method": "X-RAY DIFFRACTION",
      "resolution": 1.94,
      "organism": "Homo sapiens"
    }
  ]
}
```

**Uso:** El usuario escribe "EGFR" en el frontend → obtiene PDB IDs reales → selecciona uno → se
dispara el pipeline de ingesta automática. Reemplaza la necesidad de memorizar códigos PDB.

### `POST /targets/upload`
Subir y curar un PDB personalizado.

**Form data:** `file` (.pdb/.sdf), `name`, `is_curated`, `chain_id`, grid params, `is_anti_target`, `anti_target_risk`

### `GET /targets/alphafold/lookup/{uniprot_id}`
Buscar estructura en AlphaFold DB.

---

## Auth

### `POST /auth/login`
Login con email/password → JWT token.

### `POST /auth/register`
Registro de nuevo usuario.

### `POST /auth/refresh`
Refrescar JWT token expirado.

---

## History / Stats / Blockchain

### `GET /history/evaluations`
Historial de evaluaciones del usuario (paginado).

### `GET /history/stats`
Estadisticas del usuario.

### `GET /moldex`
Catalogo de moleculas evaluadas (Pokedex).

### `POST /blockchain/certify`
Certificar molecula en Solana devnet.

### `GET /blockchain/certificate/{molecule_id}`
Descargar certificado PDF.

---

## SAR Analysis (v1.0)

### GET /sar/{molecule_id}
Structure-Activity Relationship table. Retorna todos los analogos evaluados contra el mismo target, ranqueados por score con delta vs baseline.

**Response:**
`json
{
  "base_molecule_id": "uuid",
  "target_pdb_id": "7E2Y",
  "target_name": "SARS-CoV-2 Protease",
  "total_analogs": 5,
  "base_score": 21.0,
  "base_affinity": -5.88,
  "best_of": {"score": 32, "affinity": -6.35, "admet": 82.1},
  "results": [
    {
      "name": "4-Me",
      "smiles": "CC(=O)Oc1ccc(C)cc1C(=O)O",
      "total_score": 32,
      "affinity_kcal": -6.35,
      "delta_score": 11.0,
      "delta_affinity": -0.47,
      "is_pains": false,
      "is_base": false
    }
  ]
}
`

---

## Selectivity Panel (v1.0)

### GET /pro/anti-targets
Lista anti-targets: 5 defaults + los subidos por el usuario desde la DB.

**Response:**
`json
{
  "anti_targets": [
    {"pdb_id": "5VA1", "name": "hERG", "category": "Cardiac", "threshold_kcal": -7.0, "source": "default"},
    {"pdb_id": "4NY4", "name": "CYP3A4", "category": "Metabolism", "threshold_kcal": -8.0, "source": "default"},
    {"pdb_id": "XYZ1", "name": "MiTarget", "category": "Custom", "threshold_kcal": -7.0, "source": "user"}
  ]
}
`

### POST /pro/selectivity/{molecule_id}
Ejecuta panel de selectividad multi-target. Los anti-targets custom del usuario se incluyen automaticamente.

**Params:** 
num_workers (1-6), anti_targets (comma-separated, optional — default: all)

**Response:**
`json
{
  "molecule_id": "uuid",
  "on_target": {"pdb_id": "7E2Y", "affinity_kcal": -8.50},
  "selectivity_ratio": 4.2,
  "selectivity_verdict": "SELECTIVO",
  "off_targets": [
    {"pdb_id": "5VA1", "name": "hERG", "affinity": -5.20, "status": "ok"},
    {"pdb_id": "XYZ1", "name": "MiTarget", "affinity": null, "status": "unpreparable"}
  ],
  "execution_time_s": 72.5
}
`

### POST /pro/mmgbsa/{molecule_id} (v1.0)
MM-GBSA rescoring via OpenMM. Auto-detecta GPU.

**Params:** pose_rank (1-5), 
num_steps (500-5000)

### GET /pro/gpu
Estado GPU para aceleracion.

---

## Blockchain (v1.0 � refactorizado)

### POST /blockchain/certify
Certifica molecula en Solana devnet via Memo Program. Memo v1 con CC0 license.

**Memo format:** MolDesign-v1|CC0|smiles_hash|score|target|iso8601|user_wallet?

La certificacion usa:
- Lazy RPC init (no conecta hasta que se usa)
- 3 retries con backoff exponencial
- Degradacion limpia si SOLANA_PRIVATE_KEY no esta configurada
- Timestamp parsing robusto (ISO 8601, dateutil, fallback UTC)

---

## Community Endpoints (v1.1)

### GET /targets/community
Targets publicos de la comunidad global. (Cloud + Desktop)

### POST /targets/community/download/{pdb_id}
Descarga un target de la comunidad e ingesta localmente. (Desktop)

### POST /targets/{target_id}/share
Comparte un target local con la comunidad cloud. (Desktop → Cloud)

### GET /stats/leaderboard
Top 10 scores globales de la comunidad.

### GET /auth/desktop-login
Auto-login para modo DESKTOP. Crea usuario local automaticamente.

---

## Batch Export (v1.0)

El Excel exportado incluye 22 columnas:
Rank, Name, SMILES, TotalScore, Affinity, MW, LogP, TPSA, HBD, HBA,
Lipinski, Veber, Ghose, Egan, Muegge, Fsp3, QED, SAScore, PAINS, ADMET, BBB, hERG

Filas PAINS resaltadas en rojo. Filtro automatico. Header congelado.
