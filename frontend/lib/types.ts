import type { AvisoDeclarado } from "./avisos";

import type { Calibracion } from "../components/science/RespaldoDelReceptor";
import type {
  PoseSelectionContract,
  StructuralEvidenceContract,
} from "./structuralEvidence";

export type ValidationResult = {
  is_valid: boolean;
  canonical_smiles: string | null;
  smiles_hash: string | null;
  errors: string[];
  warnings: string[];
  heavy_atom_count: number | null;
  molecular_formula: string | null;
};

export type EvaluationSubmitResponse = {
  task_id: string;
  status: string;
  target_pdb_id: string;
  smiles_hash: string;
};

export type DockingPose = {
  rank: number;
  affinity: number; // backend truth: JSON key "affinity" (DockingPose, not top-level result)
  rmsd_lb: number;
  rmsd_ub: number;
};

/** Protocolo 3D sellado con la corrida; campos opcionales para datos legacy. */
export type DockingProtocol = {
  contract?: string | null;
  conformers_requested?: number | null;
  conformers_generated?: number | null;
  conformer_warnings?: string[] | null;
  engine?: string | null;
  exhaustiveness?: number | null;
  num_poses?: number | null;
  seed?: number | null;
};

export type EvaluationResult = {
  id: string;
  molecule_id: string;
  target_name: string | null;
  target_spearman_rho: number | null;
  /**
   * SC-9: el respaldo del receptor **en el momento de la corrida**, congelado
   * con el resultado. La reapertura y el dossier dicen lo que se sabía al
   * ejecutar, no lo que se sepa hoy.
   */
  target_calibracion?: Calibracion | null;

  // Docking
  /**
   * El score de AutoDock Vina, SIN transformar. Antes del 2026-09-04 este campo
   * podía contener `-1.36 · pKi` de la regresión de XGBoost, escrita encima; en
   * las corridas anteriores a esa fecha no hay forma de distinguirlo.
   */
  affinity_kcal: number | null;
  affinity_score: number | null;

  // ── Interpretación de ML, en su propia columna ───────────────────────────
  /**
   * Regresión de XGBoost en unidades de pKi. NO es `affinity_kcal` y no la
   * sustituye: son dos cantidades con distinto error y distinto dominio.
   * `null` en corridas anteriores a SCHEMA 16, donde el valor se perdió al
   * sobrescribir la afinidad.
   */
  ml_pki: number | null;
  /**
   * Si esa predicción cayó DENTRO del dominio de aplicabilidad del modelo.
   * `false` significa que se muestra como referencia, no como predicción.
   * `null` = la corrida no lo registró, así que no se puede afirmar que sí.
   */
  ml_pki_aplicada: boolean | null;

  // ── Eficiencia por átomo, derivada de Vina (nunca de la regresión) ───────
  /** |afinidad| / HA^0.3 — Nissink, J. Chem. Inf. Model. 49 (2009) 1617. Sin umbral publicado. */
  sile_vina: number | null;
  /**
   * LE / LE_scale(HA) con el ajuste cúbico de Reynolds (J. Med. Chem. 51, 2008).
   * PROXY: la escala está ajustada contra Ki experimental, no contra scores de
   * acoplamiento. No es probabilidad de unión ni calidad de pose.
   */
  fq_vina_proxy: number | null;
  docking_poses: DockingPose[] | null;
  /** Ruta lógica content-addressed. Nunca debe mostrarse como ruta local cruda. */
  receptor_path: string | null;
  /** SHA-256 de los bytes exactos del receptor preparado usado por esta corrida. */
  receptor_sha256: string | null;
  parsing_source: string | null;
  vina_version: string | null;
  vina_random_seed: number | null;
  /**
   * Avisos científicos. `string` en corridas anteriores a la severidad
   * declarada; `AvisoDeclarado` desde que la emite el backend. Ver
   * `lib/avisos.ts` — y no deduzcas la severidad del texto.
   */
  scientific_warnings: (string | AvisoDeclarado)[] | null;
  /**
   * Evidencia física por pose (P0-A). `null` en corridas anteriores a la
   * etapa: significa «no se validó», nunca «la pose falló».
   * Contrato: `backend/services/chemistry/structural_evidence.py`.
   */
  structural_evidence?: StructuralEvidenceContract | null;

  /**
   * Qué se le hizo al SMILES antes de acoplarlo: tautómero canónico elegido,
   * estado de protonación a pH 7.4 y carga formal neta de la especie que de
   * verdad entró al acoplamiento. `null` en corridas anteriores a esta etapa.
   * Contrato: `backend/chem/conformer.py`.
   */
  ligand_state?: {
    smiles_entrada?: string | null;
    smiles_acoplado?: string | null;
    cambio_respecto_a_la_entrada?: boolean | null;
    carga_formal_neta?: number | null;
    formula_acoplada?: string | null;
    tautomeria?: { aplicada?: boolean; motor?: string | null; alternativas?: number | null; motivo?: string | null } | null;
    protonacion?: { aplicada?: boolean; motor?: string | null; ph?: number | null; alternativas?: number | null; motivo?: string | null } | null;

    /** Manifiesto de la frontera ESMFold -> ligando; null en corridas no peptidicas. */
    peptide_transfer?: {
      protocol_version?: string;
      status?: string;
      failure_code?: string | null;
      failure_message?: string | null;
      chemical_graph_source?: string;
      coordinate_source?: string;
      coordinates_transferred?: number;
      coordinates_completed?: number;
      completed_atom_names?: string[];
      completion_method?: string | null;
      mapping_version?: string | null;
      input_isomeric_smiles?: string | null;
      output_isomeric_smiles?: string | null;
      input_graph_hash?: string | null;
      output_graph_hash?: string | null;
      fold_plddt?: number | null;
      esmfold_model?: string | null;
    } | null;
  } | null;
  /**
   * Recomendación del selector de pose (P0-B). El backend nunca la manda
   * `null`: una corrida anterior abre como `unavailable`, con Vina top-1
   * declarado como fallback.
   * Contrato: `backend/services/chemistry/pose_selection.py`.
   */
  pose_selection?: PoseSelectionContract | null;
  /** Configuración de generación 3D y docking realmente ejecutada. */
  docking_protocol?: DockingProtocol | null;
  task_id: string | null;
  /** @deprecated Alias temporal del backend para clientes anteriores a schema v3. */
  celery_task_id?: string | null;

  // Properties
  molecular_weight: number | null;
  log_p: number | null;
  tpsa: number | null;
  hbd: number | null;
  hba: number | null;
  rotatable_bonds: number | null;
  heavy_atom_count: number | null;
  ring_count: number | null;
  lipinski_pass: boolean | null;
  veber_pass: boolean | null;
  // Drug-likeness (calculados por RDKit, persistidos por WS2)
  ghose_pass: boolean | null;
  egan_pass: boolean | null;
  muegge_pass: boolean | null;
  muegge_score: number | null;
  fsp3: number | null;
  is_pains: boolean | null;
  pains_matches: string[] | null;
  qed: number | null;
  sa_score: number | null;
  sa_reasons: string[] | null;

  // Scores
  adme_score: number | null;
  druglikeness_score: number | null;
  blood_viability_score: number | null;
  blood_solubility_logs: number | null;
  blood_ppb_category: string | null;
  blood_bbb_permeable: boolean | null;
  // Qué regla del consenso decidió la permeabilidad, y el CNS MPO que la
  // acompaña. Ver `backend/chem/bbb_consenso.py`: el booleano solo no distingue
  // un veredicto del modelo de uno de una heurística que lo contradijo.
  blood_bbb_motivo: string | null;
  blood_cns_mpo: number | null;
  blood_hia_permeable: boolean | null;
  blood_systemic_reactivity: string[] | null;
  /** "evaluado" | "fallo" | "no_evaluado". Una lista de alertas vacia tiene dos
   *  causas y hasta el 2026-09-04 la interfaz las pintaba iguales, en verde. */
  blood_tabpfn_estado: string | null;
  total_score: number | null;
  gnn_score: number | null;
  // ML (family-gated stacking, serializados por WS2)
  xgb_score: number | null;
  clgnn_score: number | null;
  quantum_score: number | null;
  ums_score: number | null;
  mmgbsa_score: number | null;
  target_family: string | null;
  stacking_vina_weight: number | null;
  stacking_xgb_weight: number | null;
  /** Pesos efectivos usados tras renormalizar componentes disponibles. */
  stacking_effective_weights: Record<string, number> | null;
  stacking_degraded: boolean | null;
  stacking_missing_components: string[] | null;

  // ── M5-Zn (SCHEMA 20) ────────────────────────────────────────────────────
  /** Perfil resuelto por PDB exacto, o `null` si el caso no es de metal. */
  m5_protocol_id: string | null;
  /**
   * Score compuesto M5-Zn. Puede conservarse en REVIEW como evidencia auditable;
   * solo VALIDATED habilita una conclusion. Es ranking derivado, no afinidad.
   */
  m5_score: number | null;
  /** Por qué el score es lo que es: VALIDATED, NOT_EVALUATED_MISSING_COMPONENT, … */
  m5_scientific_status: string | null;
  /** Componentes requeridos por el perfil que faltaron en esta corrida. */
  m5_missing_components: string[] | null;
  /**
   * UMS SMARTS-only, la señal autorizada de los tres perfiles. NO es
   * `ums_score`, que es el UMS histórico con donantes y MolChamb.
   */
  ums_warhead: number | null;

  /** Peso de la GNN LEGACY (RTMScore, deprecada). NO es el de CL-GNN. */
  stacking_gnn_weight: number | null;
  /**
   * Peso de CL-GNN. `null` en corridas anteriores a SCHEMA 17 significa «no se
   * registró por separado», nunca «cero»: hasta entonces sólo se guardaba el
   * peso de la GNN legacy y se mostraba bajo la etiqueta de CL-GNN.
   */
  stacking_clgnn_weight: number | null;
  // Transparencia del modelo usado (F-21)
  engine_used: string | null;
  fallback_reason: string | null;
  in_applicability_domain: boolean | null;
  model_used: string | null;
  specificity_score: number | null;
  hotspots_hit: string[] | null;
  target_hotspots: { name: string; importance: number }[] | null;
  affinity_threshold: number | null;
  affinity_multiplier: number | null;
  specificity_multiplier: number | null;
  ligand_efficiency: number | null;
  ligand_lipophilicity_efficiency: number | null;

  // XAI
  shap_values: Record<string, number> | null;
  gnn_attention: number[] | null;
  gnn_attention_svg: string | null;
  gnn_pharmacophores: Record<string, number> | null;

  // Selectividad (anti-targets, v1.7.3+)
  /**
   * Cociente ΔG_on/ΔG_off. Se conserva porque hay corridas guardadas con él,
   * pero NO tiene sentido termodinámico y no decide nada: el margen es
   * `selectivity_delta_delta_g`. Ver `lib/selectividadMargen.ts`.
   */
  selectivity_ratio: number | null;
  /** ΔΔG = ΔG_off − ΔG_on, en kcal/mol. `null` en corridas anteriores. */
  selectivity_delta_delta_g?: number | null;
  selectivity_verdict: string | null;
  anti_target_results: { pdb_id: string; affinity: number | null; threshold?: number | null; name?: string; status?: string }[] | null;
  selectivity_ran: boolean | null;

  // Files
  poses_file_path: string | null;
  is_control: boolean;

  // Report
  ai_report: string | null;

  // Blockchain
  blockchain_tx_id: string | null;

  error_message: string | null;
  evaluated_at: string;
};

export type JobStatus = {
  task_id: string;
  status: string;
  progress: number;
  result: EvaluationResult | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  logs?: string[];
};

// ── History Types ────────────────────────────────────────────────

export type EvaluationSummary = {
  molecule_id: string;
  smiles: string;
  name: string | null;
  status: string;
  target_pdb_id: string;
  total_score: number | null;
  affinity_kcal: number | null;
  affinity_score: number | null;
  adme_score: number | null;
  druglikeness_score: number | null;
  molecular_weight: number | null;
  log_p: number | null;
  lipinski_pass: boolean | null;
  qed: number | null;
  sa_score: number | null;
  blockchain_tx_id: string | null;
  evaluated_at: string | null;
  created_at: string;
  /**
   * Identidad de la corrida que produjo estas cifras. `evaluation_runs` guarda el
   * snapshot inmutable por `task_id` (EVAL-P0-02): es lo que distingue ESTA corrida
   * de la última evaluación de la misma molécula. `null` en filas anteriores a v11.
   */
  task_id: string | null;
  /** Promovida a Moldex. El historial lista todo; esto dice qué además está allí. */
  is_saved: boolean;
};

export type HistoryResponse = {
  items: EvaluationSummary[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
};

export type UserStats = {
  total_evaluations: number;
  completed_evaluations: number;
  failed_evaluations: number;
  best_score: number | null;
  avg_score: number | null;
  unique_targets: number;
};

// ── Suggestion Types ─────────────────────────────────────────────

export type MolecularSuggestion = {
  smiles: string;
  name: string;
  description: string;
  rationale: string;
  modification_type: string;
  expected_effect: string;
  confidence: string;
  ml_score?: number | null;
  source: string;
  warnings: string[];
};

export type SuggestionResponse = {
  success: boolean;
  suggestions: MolecularSuggestion[];
  method: string;
  warnings: string[];
  disclaimer: string;
};

// ── AlphaFold Types ──────────────────────────────────────────────

export type AlphaFoldEntry = {
  uniprot_id: string;
  gene: string | null;
  organism: string | null;
  model_url: string;
  mean_plddt: number | null;
  high_confidence_residues: number | null;
  total_residues: number | null;
  warnings: string[];
};

export interface GlobalStats {
  total_molecules: number;
  total_certifications: number;
  best_affinity?: number | null;
  /** @deprecated Alias de compatibilidad; contiene afinidad observada. */
  best_score: number | null;
  best_molecule_name: string | null;
  best_molecule_smiles: string | null;
  best_user_name: string | null;
  best_target_pdb: string | null;
  hot_target: {
    pdb_id: string;
    name: string;
    spearman_rho: number;
    family: string;
  } | null;
  community_status: string;
}

// ── Model Download Types ──────────────────────────────────────────

export type ModelStatus = "NotDownloaded" | "Downloading" | "Downloaded" | "Error" | "missing" | "ready" | "downloading" | "extracting" | "error";

export interface ModuleEntry {
  id: string;
  name: string;
  category?: string;
  description?: string;
  type?: string;
  filename?: string;
  size_bytes?: number;
  size_mb?: number;
  sha256?: string;
  urls?: string[];
  required?: boolean;
  destination?: string;
  features?: string[];
  /**
   * Motor que esta descarga habilita, si habilita alguno.
   *
   * Es lo que une el gestor de modelos con el catálogo del backend
   * (`services/motores`): descargar `esmfold-weights` es lo que hace que el
   * motor `esmfold` pase de «no instalado» a «instalado y apagado».
   */
  engine_id?: string;
  /** Librerías que el runtime necesita para poder cargar lo descargado. */
  requires_python?: string[];
  /** Lo que hay que saber del módulo y no cabe en la descripción. */
  notes?: string;
  /** Por qué la revisión es un commit y no `main`. */
  revision_nota?: string;
  status?: ModelStatus;
  progress_pct?: number;
  download_speed_mbps?: number;
  eta_seconds?: number;
  downloaded_bytes?: number;
  total_bytes?: number;
  file_path?: string;
  checksum_sha256?: string;
  error?: string;
  license?: string;
  source_url?: string;
  license_url?: string;
  /** Commit inmutable del que se descarga. Nunca una rama: `main` se mueve. */
  revision?: string;
}

export interface DownloadProgressEvent {
  model_id: string;
  downloaded_bytes: number;
  bytes_downloaded?: number;
  total_bytes: number;
  progress_pct: number;
  speed_mbps: number;
  speed_bytes_per_sec?: number;
  eta_seconds: number;
}

export interface DownloadCompleteEvent {
  model_id: string;
  file_path: string;
  checksum_valid: boolean;
}

// Una interacción no-covalente ligando-proteína (PLIF, endpoint
// /evaluation/interactions/{molecule_id}). Las coordenadas son de los dos
// átomos en contacto (frame del receptor — mismas que las poses del SDF).
export type InteractionDatum = {
  type: string; // hbond | hydrophobic | pistacking | saltbridge | cationpi | halogen ...
  residue: string;
  distance: number;
  angle: number | null;
  strength: number | null;
  ligand_coords: { x: number; y: number; z: number };
  protein_coords: { x: number; y: number; z: number };
};

export type InteractionsReport = {
  molecule_id: string;
  target_pdb_id: string;
  pose_rank: number;
  total_interactions: number;
  interactions: InteractionDatum[];
};
