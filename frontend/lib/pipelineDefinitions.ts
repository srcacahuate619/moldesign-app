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
  // structural_family mostraba "M4 GPCR · Vina + XGB + CL-GNN" con stacking
  // weights de GPCR que NO aplican a ese target → resultados engañosos.
  // Ahora el default es un stacking NEUTRO explícito, marcado como no-curado
  // (family-gating no validado). Ver docs/36 UI-8.
  default: {
    id: "m4_default_uncured",
    label: "Pipeline por defecto · target no curado",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.0 kcal/mol", sub: "v1.2.7", weight: 0.25, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.60", sub: "500 trees", weight: 0.75, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.50", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true, note: "target sin familia curada — CL-GNN no validado" },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true, note: "sin peso en los pesos por defecto" },
      { id: "mmgbsa", label: "MM-GBSA", value: "-6.0 kcal/mol", sub: "OpenMM OBC2", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Target sin curación científica: familia estructural desconocida, Spearman ρ no calibrado. Interpreta los scores con precaución — no aplica family-gating validado.",
  },
  // ── Los pesos son los EFECTIVOS del backend, no una narrativa ──────────
  //
  // All named M4 families intentionally resolve to the same conservative
  // alpha contract (Vina 0.25 + XGBoost 0.75). A family-specific weight may
  // return only after preregistered, sealed validation of the exact artifact.
  // Historical metrics from different CL-GNN bytes are provenance, not a
  // license to influence current rankings.
  gpcr: {
    id: "m4_gpcr",
    label: "M4 GPCR · Vina + XGB",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-9.4 kcal/mol", sub: "v1.2.7", weight: 0.25, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.81", sub: "500 trees", weight: 0.75, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.68", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true, note: "el artefacto vigente no le asigna peso en GPCR" },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true, note: "deprecada; no participa en el contrato de release" },
      { id: "mmgbsa", label: "MM-GBSA", value: "-8.2 kcal/mol", sub: "OpenMM OBC2", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato alpha: Vina 0.25 + XGBoost 0.75; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  protease: {
    id: "m4_protease",
    label: "M4 Proteasa · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.8 kcal/mol", sub: "v1.2.7", weight: 0.25, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.55", sub: "500 trees", weight: 0.75, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.74", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "-7.1 kcal/mol", sub: "OpenMM OBC2", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato alpha: Vina 0.25 + XGBoost 0.75; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  kinase: {
    id: "m4_kinase",
    label: "M4 Kinasa · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.6 kcal/mol", sub: "v1.2.7", weight: 0.25, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.83", sub: "500 trees", weight: 0.75, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.55", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "-6.5 kcal/mol", sub: "OpenMM OBC2", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato alpha: Vina 0.25 + XGBoost 0.75; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  nuclear_receptor: {
    id: "m4_nuclear",
    label: "M4 Nuclear Receptor · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-8.2 kcal/mol", sub: "v1.2.7", weight: 0.25, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.91", sub: "500 trees", weight: 0.75, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.45", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "-9.1 kcal/mol", sub: "OpenMM OBC2", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato alpha: Vina 0.25 + XGBoost 0.75; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  soluble_enzyme: {
    id: "m4_soluble",
    label: "M4 Soluble Enzyme · pesos por defecto",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-7.4 kcal/mol", sub: "v1.2.7", weight: 0.25, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.62", sub: "500 trees", weight: 0.75, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.61", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "mmgbsa", label: "MM-GBSA", value: "-6.8 kcal/mol", sub: "OpenMM OBC2", weight: 0.0, color: "#10b981", post_hoc: true },
    ],
    note: "Contrato alpha: Vina 0.25 + XGBoost 0.75; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
  },
  metaloenzyme: {
    id: "m4_metal_sin_m5",
    label: "M4 · pesos por defecto · M5-Zn se registra aparte",
    stages: [
      { id: "vina", label: "Docking Vina", value: "-5.1 kcal/mol", sub: "v1.2.7", weight: 0.25, color: "#a78bfa" },
      { id: "xgb", label: "XGBoost", value: "p = 0.60", sub: "500 trees", weight: 0.75, color: "#60a5fa" },
      { id: "clgnn", label: "CL-GNN", value: "0.59", sub: "v3.1 - senal experimental - w=0", weight: 0.0, color: "#34d399", degraded: true },
      { id: "quantum", label: "Quantum", value: "0.55", sub: "xTB + MMFF94", weight: 0.0, color: "#22d3ee", post_hoc: true },
      { id: "gnn", label: "GNN legacy", value: "—", sub: "RTMScore, deprecada", weight: 0.0, color: "#94a3b8", degraded: true },
      { id: "ums", label: "UMS Metal", value: "0.78", sub: "señal informativa", weight: 0.0, color: "#f59e0b", post_hoc: true, note: "no entra en el ranking: el ADR 75 retiró el empujón aditivo de 0.06" },
      { id: "molchamb", label: "MolChamb", value: "0.71", sub: "GFN2-xTB", weight: 0.0, color: "#ec4899", post_hoc: true, note: "participa dentro del UMS histórico, no en el stacking" },
      { id: "mmgbsa", label: "MM-GBSA", value: "—", sub: "n/a metal", weight: 0.0, color: "#10b981", post_hoc: true, degraded: true },
    ],
    note: "M4 usa el contrato alpha conservador. M5-Zn se ejecuta y persiste aparte con sus estados de abstencion o revision; UMS y MolChamb siguen como senales informativas.",
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
