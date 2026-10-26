"use client";

/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V5 */
import { useMemo, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { ProAnalysisTabs } from "@/components/interfaces/pro/ProAnalysisTabs";
import { EvaluationEvidencePanel } from "@/components/interfaces/pro/EvaluationEvidencePanel";
import { RESULT_FIELD_KEYS } from "@/lib/resultFieldKeys";
import { EvaluationActionBar } from "@/components/interfaces/pro/EvaluationActionBar";
import { ResultReadingPresentation } from "@/components/interfaces/pro/ResultReadingPresentation";
import realSample from "./lectura-qa.json";
import type { EvaluationResult } from "@/lib/types";

function sample(scenario: string, criticalText: string): EvaluationResult {
  if (scenario === "real") return realSample as unknown as EvaluationResult;
  const result: Record<string, unknown> = Object.fromEntries(RESULT_FIELD_KEYS.map(key => [key, null]));
  Object.assign(result, {
    id: "muestra-interfaz", molecule_id: null, task_id: "MUESTRA-INTERFAZ",
    smiles: "CC(=O)Oc1ccccc1C(=O)O", target_name: "Receptor de muestra", engine_used: "vina", is_control: false,
    molecular_weight: 180.16, log_p: 1.31, tpsa: 63.6, hbd: 1, hba: 4, rotatable_bonds: 2,
    heavy_atom_count: 13, ring_count: 1, lipinski_pass: true, veber_pass: true, is_pains: false,
    ligand_lipophilicity_efficiency: 2.1, affinity_kcal: -6.3,
    scientific_warnings: [], docking_poses: [
      { rank: 1, affinity: -6.3, rmsd_lb: 0, rmsd_ub: 0 },
      { rank: 2, affinity: -6.1, rmsd_lb: 1.8, rmsd_ub: 2.4 },
      { rank: 3, affinity: -5.4, rmsd_lb: 3.4, rmsd_ub: 4.2 },
    ],
    docking_protocol: { engine: "vina", seed: 42, exhaustiveness: 8, num_poses: 9, conformers_requested: 5, conformers_generated: 5 },
    ligand_state: { smiles_entrada: "CC(=O)Oc1ccccc1C(=O)O", smiles_acoplado: "CC(=O)Oc1ccccc1C(=O)[O-]" },
    structural_evidence: { stage_status: "not_evaluated", poses_produced: 3, poses_evaluated: 0, poses: [] },
    model_used: "universal", in_applicability_domain: null,
    fallback_reason: "Muestra controlada de interfaz; sin evidencia científica.", selectivity_ran: false,
  });
  if (scenario === "critico") result.scientific_warnings = [{ codigo: "MUESTRA_CRITICA", severidad: "critica", mensaje: criticalText }];
  if (scenario === "incompleto") {
    delete result.docking_protocol; delete result.structural_evidence; delete result.ligand_state;
    result.is_pains = null; result.lipinski_pass = null; result.ligand_lipophilicity_efficiency = null;
  }
  if (scenario === "minimo") {
    for (const key of Object.keys(result)) if (!["id","task_id","molecule_id","scientific_warnings","is_control"].includes(key)) result[key] = null;
  }
  return result as unknown as EvaluationResult;
}
export default function EvaluationLab() {
  const { t } = useLanguage();
  const [scenario, setScenario] = useState("real");
  const [focus, setFocus] = useState(0);
  const result = useMemo(() => sample(scenario, t("rr_sample_critical")), [scenario, t]);
  return <main className="mx-auto w-full max-w-[1500px] space-y-7 px-4 pb-16 pt-8 sm:px-8">
    <header className="max-w-[90ch]"><h1 className="font-display text-3xl font-semibold text-zinc-100">{t("rr_lab_title")}</h1><p className="mt-3 text-base leading-7 text-zinc-300">{t("rr_lab_note")}</p></header>
    <ResultReadingPresentation>
    <div className="grid max-w-md content-center gap-2 text-sm text-zinc-300"><label htmlFor="reading-scenario">{t("rx_lab_escenario")}</label><select id="reading-scenario" value={scenario} onChange={e => setScenario(e.target.value)} className="min-h-11 min-w-0 rounded-lg border border-white/15 bg-surface-900 px-3">{["real","revisar","incompleto","minimo","critico"].map(id => <option key={id} value={id}>{t(id === "real" ? "rr_lab_real" : id === "critico" ? "rr_lab_critical" : `rx_lab_${id}`)}</option>)}</select></div>
    {scenario === "real" && <p className="my-5 max-w-[95ch] text-sm leading-6 text-zinc-400">{t("rr_lab_real_note")}</p>}
    <EvaluationEvidencePanel result={result} target={null} compact onOpenPhysicalControls={() => setFocus(value => value + 1)}/>
    <ProAnalysisTabs status={null} structuralEvidenceResult={result} selectivityResult={null} moleculeId={null} taskId={result.task_id} physicalFocusRequest={focus} provenanceSlot={<EvaluationEvidencePanel result={result} target={null} provenanceOnly/>} />
    <EvaluationActionBar unavailableReason={t("rr_lab_actions_unavailable")}/>
  </ResultReadingPresentation></main>;
}
