// Contract shown by the result DOT. Release weights come from
// backend/artifacts/sci_config_registry.json and are checked against the
// compatibility mirror, effective backend resolution, and this UI by
// scripts/check_stacking_weights_ui.py.
//
// CL-GNN is bundled and runs on the docked pose. The exact checkpoint SHA has
// no sealed external validation yet, so alpha reports it as an experimental
// signal with release weight 0. The deprecated legacy GNN also has weight 0.
// M5-Zn is a separate protocol and never enters this generic M4 stack.
export type PipelineStage = {
  id: string;
  label: string;
  value: string;
  sub: string;
  weight: number;       // 0 = desactivado, se atenúa visualmente
  color: string;
  post_hoc?: boolean;   // si true, no aporta al stacking
  degraded?: boolean;   // si true, atenúa (silente fail, etc.)
  note?: string;
};
export type Pipeline = {
  id: string;
  label: string;
  stages: PipelineStage[];
  note: string;
};

export const PIPELINES_BY_FAMILY: Record<string, Pipeline> = {
  // ── FIX UI-8 (2026-08-04): pipeline "default" para targets NO curados ──
  // Antes no existía key "default": familia desconocida caía al fallback
  // `?? PIPELINES_BY_FAMILY.gpcr` → un target auto-ingestado sin
  // structural_family mostraba "M4 GPCR · Vina + CL-GNN" con stacking
  // weights de GPCR que NO aplican a ese target → resultados engañosos.
  // Ahora el default es un stacking NEUTRO explícito, marcado como no-curado
  // (family-gating no validado). Ver docs/36 UI-8.
  default: {
    id: "m4_default_uncured",
    label: "Pipeline por defecto · target no curado",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.0 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.60", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.50", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true, note: "target sin familia curada — CL-GNN no validado" },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true, note: "sin peso en los pesos por defecto" },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", sub: "Motor legacy invalidado", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Target sin curación científica: familia estructural desconocida, Spearman ρ no calibrado. XGBoost se muestra sin peso de release. Interpreta los scores con precaución — no aplica family-gating validado.",
  },
  // ── Los pesos son los EFECTIVOS del backend, no una narrativa ──────────
  //
  // All named M4 families intentionally resolve to the same conservative
  // provisional contract (Vina 1.00; XGBoost 0.00). A family-specific weight may
  // return only after preregistered, sealed validation of the exact artifact.
  // Historical metrics from different CL-GNN bytes are provenance, not a
  // license to influence current rankings.
  gpcr: {
    id: "m4_gpcr",
    label: "M4 GPCR · Vina",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-9.4 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.81", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.68", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true, note: "el artefacto vigente no le asigna peso en GPCR" },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true, note: "deprecada; no participa en el contrato de release" },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", sub: "Motor legacy invalidado", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  protease: {
    id: "m4_protease",
    label: "M4 Proteasa · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.8 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.55", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.74", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", sub: "Motor legacy invalidado", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  kinase: {
    id: "m4_kinase",
    label: "M4 Kinasa · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.6 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.83", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.55", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", sub: "Motor legacy invalidado", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  nuclear_receptor: {
    id: "m4_nuclear",
    label: "M4 Nuclear Receptor · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-8.2 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.91", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.45", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", sub: "Motor legacy invalidado", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  soluble_enzyme: {
    id: "m4_soluble",
    label: "M4 Soluble Enzyme · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.4 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.62", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.61", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", sub: "Motor legacy invalidado", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  metaloenzyme: {
    id: "m4_metal_sin_m5",
    label: "M4 · pesos por defecto · M5-Zn se registra aparte",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-5.1 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.60", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.59", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "ums", label: "UMS Metal", value: "0.78", sub: "señal informativa", weight: 0.0, color: "#f59e0b", post_hoc: true, note: "no entra en el ranking: el ADR 75 retiró el empujón aditivo de 0.06" },
      { id: "molchamb", label: "MolChamb", value: "0.71", sub: "GFN2-xTB", weight: 0.0, color: "#ec4899", post_hoc: true, note: "participa dentro del UMS histórico, no en el stacking" },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", sub: "Motor legacy invalidado", weight: 0.0, color: "#10b981", post_hoc: true, degraded: true },
    ],
    note: "M4 usa el contrato provisional Vina solo. M5-Zn se ejecuta y persiste aparte con sus estados de abstencion o revision; UMS y MolChamb siguen como senales informativas.",
  },
};

export const FAMILY_LABELS: Record<string, string> = {
  gpcr: "GPCR",
  protease: "Proteasa",
  kinase: "Kinasa",
  nuclear_receptor: "Nuclear Receptor",
  soluble_enzyme: "Soluble Enzyme",
  metaloenzyme: "Metaloenzima",
  default: "Default",
};

/** Translate only fixed labels and notes owned by this pipeline definition. */
export function localizePipelineText(
  value: string,
  translate: (key: string) => string,
): string {
  const keys: Record<string, string> = {
    "de esta corrida": "pr_pipeline_sub_this_run",
    "Pipeline por defecto · target no curado": "pr_pipeline_label_default",
    "M4 Proteasa · pesos por defecto": "pr_pipeline_label_protease",
    "M4 Kinasa · pesos por defecto": "pr_pipeline_label_kinase",
    "M4 Nuclear Receptor · pesos por defecto": "pr_pipeline_label_nuclear_receptor",
    "M4 Soluble Enzyme · pesos por defecto": "pr_pipeline_label_soluble_enzyme",
    "M4 Metaloenzima · pesos por defecto": "pr_pipeline_label_metalloenzyme",
    "Target sin curación científica: familia estructural desconocida, Spearman ρ no calibrado. XGBoost se muestra sin peso de release. Interpreta los scores con precaución — no aplica family-gating validado.": "pr_pipeline_note_default",
    "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.": "pr_pipeline_note_provisional",
    "M4 usa el contrato provisional Vina solo. M5-Zn se ejecuta y persiste aparte con sus estados de abstencion o revision; UMS y MolChamb siguen como senales informativas.": "pr_pipeline_note_m4_m5",
    "target sin familia curada — CL-GNN no validado": "pr_pipeline_node_uncurated_clgnn",
    "sin peso en los pesos por defecto": "pr_pipeline_node_no_default_weight",
    "el artefacto vigente no le asigna peso en GPCR": "pr_pipeline_node_gpcr_zero_weight",
    "deprecada; no participa en el contrato de release": "pr_pipeline_node_deprecated",
    "no entra en el ranking: el ADR 75 retiró el empujón aditivo de 0.06": "pr_pipeline_node_ums_excluded",
    "participa dentro del UMS histórico, no en el stacking": "pr_pipeline_node_molchamb_historical",
    "v3.1 - senal experimental - w=0": "pr_pipeline_sub_clgnn",
    "RTMScore, deprecada": "pr_pipeline_sub_legacy_gnn",
    "No disponible": "pr_pipeline_value_unavailable",
    "Motor legacy invalidado": "pr_pipeline_sub_invalidated_legacy",
    "señal informativa": "pr_pipeline_sub_informative",
    Proteasa: "pr_pipeline_family_protease",
    Kinasa: "pr_pipeline_family_kinase",
    Metaloenzima: "pr_pipeline_family_metalloenzyme",
    "no disponible": "pr_pipeline_value_unavailable",
    "motor legacy invalidado": "pr_pipeline_sub_invalidated_legacy",
  };
  const key = keys[value];
  return key ? translate(key) : value;
}
