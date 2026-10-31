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
  labelKey?: string; valueKey?: string; subKey?: string; noteKey?: string;
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
  labelKey?: string; noteKey?: string;
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
    label: "Pipeline por defecto · target no curado", labelKey: "pr_pipeline_label_default",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.0 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.60", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.50", sub: "v3.1 - senal experimental - w=0", subKey: "pr_pipeline_sub_clgnn", weight: 0.0, color: "#34d399", degraded: true, note: "target sin familia curada — CL-GNN no validado", noteKey: "pr_pipeline_node_uncurated_clgnn" },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", subKey: "pr_pipeline_sub_legacy_gnn", weight: 0.0, color: "#94a3b8", degraded: true, note: "sin peso en los pesos por defecto", noteKey: "pr_pipeline_node_no_default_weight" },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", valueKey: "pr_pipeline_value_unavailable", sub: "Motor legacy invalidado", subKey: "pr_pipeline_sub_invalidated_legacy", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Target sin curación científica: familia estructural desconocida, Spearman ρ no calibrado. XGBoost se muestra sin peso de release. Interpreta los scores con precaución — no aplica family-gating validado.", noteKey: "pr_pipeline_note_default",
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
      { id: "clgnn", label: "CL-GNN", value: "0.68", sub: "v3.1 - senal experimental - w=0", subKey: "pr_pipeline_sub_clgnn", weight: 0.0, color: "#34d399", degraded: true, note: "el artefacto vigente no le asigna peso en GPCR", noteKey: "pr_pipeline_node_gpcr_zero_weight" },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", subKey: "pr_pipeline_sub_legacy_gnn", weight: 0.0, color: "#94a3b8", degraded: true, note: "deprecada; no participa en el contrato de release", noteKey: "pr_pipeline_node_deprecated" },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", valueKey: "pr_pipeline_value_unavailable", sub: "Motor legacy invalidado", subKey: "pr_pipeline_sub_invalidated_legacy", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.", noteKey: "pr_pipeline_note_provisional",
  },
  protease: {
    id: "m4_protease",
    label: "M4 Proteasa · pesos por defecto", labelKey: "pr_pipeline_label_protease",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.8 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.55", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.74", sub: "v3.1 - senal experimental - w=0", subKey: "pr_pipeline_sub_clgnn", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", subKey: "pr_pipeline_sub_legacy_gnn", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", valueKey: "pr_pipeline_value_unavailable", sub: "Motor legacy invalidado", subKey: "pr_pipeline_sub_invalidated_legacy", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.", noteKey: "pr_pipeline_note_provisional",
  },
  kinase: {
    id: "m4_kinase",
    label: "M4 Kinasa · pesos por defecto", labelKey: "pr_pipeline_label_kinase",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.6 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.83", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.55", sub: "v3.1 - senal experimental - w=0", subKey: "pr_pipeline_sub_clgnn", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", subKey: "pr_pipeline_sub_legacy_gnn", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", valueKey: "pr_pipeline_value_unavailable", sub: "Motor legacy invalidado", subKey: "pr_pipeline_sub_invalidated_legacy", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.", noteKey: "pr_pipeline_note_provisional",
  },
  nuclear_receptor: {
    id: "m4_nuclear",
    label: "M4 Nuclear Receptor · pesos por defecto", labelKey: "pr_pipeline_label_nuclear_receptor",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-8.2 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.91", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.45", sub: "v3.1 - senal experimental - w=0", subKey: "pr_pipeline_sub_clgnn", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", subKey: "pr_pipeline_sub_legacy_gnn", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", valueKey: "pr_pipeline_value_unavailable", sub: "Motor legacy invalidado", subKey: "pr_pipeline_sub_invalidated_legacy", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.", noteKey: "pr_pipeline_note_provisional",
  },
  soluble_enzyme: {
    id: "m4_soluble",
    label: "M4 Soluble Enzyme · pesos por defecto", labelKey: "pr_pipeline_label_soluble_enzyme",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.4 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.62", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.61", sub: "v3.1 - senal experimental - w=0", subKey: "pr_pipeline_sub_clgnn", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", subKey: "pr_pipeline_sub_legacy_gnn", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", valueKey: "pr_pipeline_value_unavailable", sub: "Motor legacy invalidado", subKey: "pr_pipeline_sub_invalidated_legacy", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.", noteKey: "pr_pipeline_note_provisional",
  },
  metaloenzyme: {
    id: "m4_metal_sin_m5",
    label: "M4 · pesos por defecto · M5-Zn se registra aparte",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-5.1 kcal/mol", sub: "v1.2.7", weight: 1.0, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.60", sub: "500 trees", weight: 0.0, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.59", sub: "v3.1 - senal experimental - w=0", subKey: "pr_pipeline_sub_clgnn", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", subKey: "pr_pipeline_sub_legacy_gnn", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "ums", label: "UMS Metal", value: "0.78", sub: "señal informativa", subKey: "pr_pipeline_sub_informative", weight: 0.0, color: "#f59e0b", post_hoc: true, note: "no entra en el ranking: el ADR 75 retiró el empujón aditivo de 0.06", noteKey: "pr_pipeline_node_ums_excluded" },
      { id: "molchamb", label: "MolChamb", value: "0.71", sub: "GFN2-xTB", weight: 0.0, color: "#ec4899", post_hoc: true, note: "participa dentro del UMS histórico, no en el stacking", noteKey: "pr_pipeline_node_molchamb_historical" },
      { id: "mmgbsa", label: "MM-GBSA", value: "No disponible", valueKey: "pr_pipeline_value_unavailable", sub: "Motor legacy invalidado", subKey: "pr_pipeline_sub_invalidated_legacy", weight: 0.0, color: "#10b981", post_hoc: true, degraded: true },
    ],
    note: "M4 usa el contrato provisional Vina solo. M5-Zn se ejecuta y persiste aparte con sus estados de abstencion o revision; UMS y MolChamb siguen como senales informativas.", noteKey: "pr_pipeline_note_m4_m5",
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

/** Traducción por identidad estructurada; los valores originales no se modifican. */
export function localizePipeline(pipeline: Pipeline, t: (key: string) => string): Pipeline {
  return { ...pipeline, label: pipeline.labelKey ? t(pipeline.labelKey) : pipeline.label,
    note: pipeline.noteKey ? t(pipeline.noteKey) : pipeline.note,
    stages: pipeline.stages.map(stage => ({ ...stage,
      label: stage.labelKey ? t(stage.labelKey) : stage.label,
      value: stage.valueKey ? t(stage.valueKey) : stage.value,
      sub: stage.subKey ? t(stage.subKey) : stage.sub,
      note: stage.noteKey ? t(stage.noteKey) : stage.note,
    })),
  };
}
export const FAMILY_LABEL_KEYS: Readonly<Record<string, string>> = {
  protease: "pr_pipeline_family_protease", kinase: "pr_pipeline_family_kinase", metaloenzyme: "pr_pipeline_family_metalloenzyme",
};
