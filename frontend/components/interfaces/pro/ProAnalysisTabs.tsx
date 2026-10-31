"use client";

/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 */

// La evidencia no desaparece: se agrupa por la pregunta que responde. Esto
// reduce la botonera heredada sin ocultar alertas, XAI, SAR, selectividad o la
// trazabilidad estructural de la corrida.

import React, { useEffect, useMemo, useState } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import { useKeepAliveActive } from "../../../context/KeepAliveContext";
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  Boxes,
  FlaskConical,
  Gauge,
  GitFork,
  ListChecks,
  ShieldCheck,
  Sliders,
} from "lucide-react";
import { ProParametersTab } from "./ProParametersTab";
import { EstadoDelLigando } from "./EstadoDelLigando";
import { ProAlertsTab } from "./ProAlertsTab";
import { cuentaQueImporta, normalizarAvisos } from "../../../lib/avisos";
import { ProXaiTab } from "./ProXaiTab";
import { ProSelectivityPanel } from "./ProSelectivityPanel";
import { ProSarTab } from "./ProSarTab";
import { ProDockingTab } from "./ProDockingTab";
import { PosePhysicalDetails, StructuralEvidencePanel } from "./StructuralEvidencePanel";
import { ResultAreaLayout } from "./ResultAreaLayout";
import { ReadingHelp } from "./ResultReadingPresentation";
import readingStyles from "./ResultReadingPresentation.module.css";
import { RunDataExplorer } from "./RunDataExplorer";
import type { JobStatus } from "../../../lib/types";
import type { CaseRun } from "../../../lib/cases/types";
import {
  deriveStructuralEvidence,
  type EvaluationResultWithEvidence,
  type PhysicalStatus,
  type PoseComparisonRow,
} from "../../../lib/structuralEvidence";

type PrimaryTab = "structure" | "properties" | "advanced" | "provenance";
type AdvancedTab = "xai" | "selectivity" | "sar" | "mmgbsa" | "admet";

const PHYSICAL_STATUS: Record<PhysicalStatus, { label: string; className: string }> = {
  passed: { label: "Controles superados", className: "text-emerald-300" },
  failed: { label: "Controles fallidos", className: "text-red-300" },
  review: { label: "Requiere revisión", className: "text-amber-300" },
  not_evaluated: { label: "No evaluada", className: "text-zinc-400" },
};

function PoseComparisonWorkspace({
  rows,
  onComparePoses,
}: {
  readonly rows: PoseComparisonRow[];
  readonly onComparePoses?: (leftRank: number, rightRank: number) => void;
}) {
  const { t } = useLanguage();
  const ranks = rows.map((row) => row.rank);
  const ranksKey = ranks.join(",");
  const [leftRank, setLeftRank] = useState<number | null>(null);
  const [rightRank, setRightRank] = useState<number | null>(null);

  useEffect(() => {
    setLeftRank((current) => (current != null && ranks.includes(current) ? current : ranks[0] ?? null));
    setRightRank((current) => (current != null && ranks.includes(current) ? current : ranks[1] ?? null));
  }, [ranksKey]);

  const setLeft = (rank: number) => {
    setLeftRank(rank);
    if (rank === rightRank) setRightRank(ranks.find((candidate) => candidate !== rank) ?? null);
  };
  const setRight = (rank: number) => {
    setRightRank(rank);
    if (rank === leftRank) setLeftRank(ranks.find((candidate) => candidate !== rank) ?? null);
  };
  const canCompare =
    leftRank != null && rightRank != null && leftRank !== rightRank && rows.length >= 2 && onComparePoses != null;

  return (
    <div className="space-y-5">
      <header className="max-w-[78ch]">
        <h3 className="font-display text-lg font-bold tracking-tight text-zinc-100">{t("se_cmp_title")}</h3>
        <p className="mt-1.5 text-base leading-6 text-zinc-300 font-sans">
          {t("pr_comparar_explicacion")}
        </p>
      </header>

      {rows.length === 0 ? (
        <p className="rounded-xl border border-white/[0.08] bg-black/20 p-4 text-base leading-6 text-zinc-400 font-sans">
          {t("pr_sin_poses")}
        </p>
      ) : (
        <>
          <section aria-label={t("pr_elegir_poses")} className="rounded-xl border border-white/[0.08] bg-black/20 p-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="grid w-full min-w-0 gap-1.5 sm:w-auto sm:min-w-[12rem] font-sans text-sm uppercase tracking-wider text-zinc-400">
                {t("pr_pose_a")}
                <select
                  value={leftRank ?? ""}
                  onChange={(event) => setLeft(Number(event.target.value))}
                  className="min-h-10 w-full min-w-0 rounded-lg border border-white/[0.1] bg-surface-950 px-3 font-mono text-sm text-zinc-200 outline outline-2 outline-offset-1 outline-transparent transition-colors focus:border-purple-400 focus:outline-purple-400"
                >
                  {rows.map((row) => (
                    <option key={row.rank} value={row.rank}>
                      {t("ev_mmgbsa_pose_numero", { rank: row.rank })} · {row.affinity?.toFixed(2) ?? "—"} kcal/mol
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid w-full min-w-0 gap-1.5 sm:w-auto sm:min-w-[12rem] font-sans text-sm uppercase tracking-wider text-zinc-400">
                {t("pr_pose_b")}
                <select
                  value={rightRank ?? ""}
                  onChange={(event) => setRight(Number(event.target.value))}
                  className="min-h-10 w-full min-w-0 rounded-lg border border-white/[0.1] bg-surface-950 px-3 font-mono text-sm text-zinc-200 outline outline-2 outline-offset-1 outline-transparent transition-colors focus:border-purple-400 focus:outline-purple-400"
                >
                  {rows.map((row) => (
                    <option key={row.rank} value={row.rank}>
                      {t("ev_mmgbsa_pose_numero", { rank: row.rank })} · {row.affinity?.toFixed(2) ?? "—"} kcal/mol
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                disabled={!canCompare}
                onClick={() => {
                  if (canCompare && leftRank != null && rightRank != null) onComparePoses(leftRank, rightRank);
                }}
                className="inline-flex min-h-10 whitespace-nowrap items-center gap-2 rounded-lg border border-purple-500/30 bg-purple-500/[0.1] px-4 py-2 font-sans text-sm font-bold uppercase tracking-wider text-purple-100 transition-colors hover:bg-purple-500/[0.18] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-45"
              >
                <ArrowLeftRight size={14} aria-hidden="true" />
                {t("pr_abrir_comparacion")}
              </button>
            </div>
            {rows.length < 2 && (
              <p className="mt-3 text-base leading-6 text-zinc-300 font-sans">
                {t("pr_minimo_dos_poses")}
              </p>
            )}
          </section>

          <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
            <table className="w-full min-w-[42rem] border-collapse text-sm">
              <caption className="sr-only">{t("pr_resumen_poses")}</caption>
              <thead>
                <tr className="border-b border-white/[0.08] text-left font-sans text-sm uppercase tracking-wider text-zinc-400">
                  <th scope="col" className="px-3 py-2.5 font-normal">{t("pr_pose_label")}</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">{t("se_cmp_affinity")}</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">{t("pr_selector_label")}</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">{t("pr_controles_fisicos")}</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">{t("se_cmp_role")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const roles = [
                    row.isVinaTop1 ? "Vina top-1" : null,
                    row.isSuggested ? t("se_cmp_role_suggested") : null,
                    row.isAlternative && !row.isSuggested ? t("se_cmp_role_alternative") : null,
                  ].filter(Boolean);
                  return (
                    <tr key={row.rank} className="border-b border-white/[0.06] last:border-b-0">
                      <th scope="row" className="px-3 py-2.5 text-left font-mono text-zinc-200">#{row.rank}</th>
                      <td className="px-3 py-2.5 font-mono text-zinc-400">{row.affinity?.toFixed(2) ?? "—"}</td>
                      <td className="px-3 py-2.5 font-mono text-zinc-400">{row.selectorScore?.toFixed(4) ?? "—"}</td>
                      <td className={`px-3 py-2.5 ${PHYSICAL_STATUS[row.physicalStatus].className}`}>
                        {t(PHYSICAL_STATUS[row.physicalStatus].label)}
                      </td>
                      <td className="px-3 py-2.5 text-zinc-400">{roles.join(" · ") || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

interface ProAnalysisTabsProps {
  status: JobStatus | null;
  selectivityResult: any;
  moleculeId: string | null;
  onUpdateSelectivityResult?: (res: any) => void;
  onSelectivityWorkChange?: (active: boolean) => void;
  /** El pipeline lanzó el panel de selectividad en background. */
  enableSelectivity?: boolean;
  /** Abre el cálculo real de MM-GBSA en el contenedor que mantiene su estado. */
  onRequestMmgbsa?: () => void;
  mmgbsaRunning?: boolean;
  mmgbsaDone?: boolean;
  /**
   * {t("pr_calcular_admet")} sobre una corrida ya terminada.
   *
   * ADMET-AI es opt-in y se decide en Opciones ANTES de ejecutar. Sin esta
   * puerta, quien no lo marcó tenía que volver a acoplar la molécula entera
   * para obtener algo que sólo depende del SMILES.
   */
  onRequestAdmet?: () => void;
  admetRunning?: boolean;
  admetDone?: boolean;
  /** Un fallo, o el aviso de que se calculó pero no se pudo guardar. */
  admetError?: string | null;
  /** Resultado completo que alimenta la evidencia estructural y sus poses. */
  structuralEvidenceResult?: EvaluationResultWithEvidence | null;
  /** Navega desde el resumen global hacia {t("pr_controles_fisicos")}. */
  physicalFocusRequest?: number;
  /** Abre una comparación 3D de los rangos elegidos por el usuario. */
  onComparePoses?: (leftRank: number, rightRank: number) => void;
  /** Corrida que la evaluación muestra: base de una cohorte SAR explícita (CAS-02). */
  taskId?: string | null;
  /** Libro de corridas del caso: de aquí sale la cohorte histórica del SAR. */
  caseRuns?: readonly CaseRun[];

  signalsSlot?: React.ReactNode;
  provenanceSlot?: React.ReactNode;
}

export const ProAnalysisTabs: React.FC<ProAnalysisTabsProps> = ({
  status,
  selectivityResult,
  moleculeId,
  onUpdateSelectivityResult,
  onSelectivityWorkChange,
  enableSelectivity = false,
  onRequestMmgbsa,
  mmgbsaRunning = false,
  mmgbsaDone = false,
  onRequestAdmet,
  admetRunning = false,
  admetDone = false,
  admetError = null,
  structuralEvidenceResult,
  physicalFocusRequest = 0,
  onComparePoses,
  taskId = null,
  caseRuns,

  signalsSlot,
  provenanceSlot,
}) => {
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState<PrimaryTab>("structure");
  const [physicalOpen, setPhysicalOpen] = useState(false);
  const [advancedTab, setAdvancedTab] = useState<AdvancedTab>("selectivity");
  const evaluationKey = `${moleculeId ?? "sin-molecula"}:${taskId ?? "sin-corrida"}`;
  const [openedSelectivityKey, setOpenedSelectivityKey] = useState<string | null>(null);
  const selectivityActive = activeTab === "advanced" && advancedTab === "selectivity";
  const evaluationVisible = useKeepAliveActive();
  // Montar al abrirlo y conservarlo durante esta corrida: selección, scroll y tanda en curso.
  // Una corrida distinta recibe una instancia nueva, incluso si comparte molécula.
  useEffect(() => {
    if (selectivityActive) setOpenedSelectivityKey(evaluationKey);
  }, [evaluationKey, selectivityActive]);
  const [selectedPoseRank, setSelectedPoseRank] = useState<number | null>(null);
  const [poseDetailsExpanded, setPoseDetailsExpanded] = useState(false);
  const result = (structuralEvidenceResult ?? status?.result ?? null) as EvaluationResultWithEvidence | null;
  const evidenceView = useMemo(() => deriveStructuralEvidence(result), [result]);
  const poseRanks = evidenceView.comparison.map((row) => row.rank);
  const poseRanksKey = poseRanks.join(",");
  useEffect(() => { setPoseDetailsExpanded(false); }, [evaluationKey]);

  const selectOrTogglePose = (rank: number) => {
    setPoseDetailsExpanded(open => rank === selectedPoseRank ? !open : true);
    setSelectedPoseRank(rank);
  };

  // El badge contaba TODOS los avisos, así que una corrida con cinco notas de
  // procedencia y ninguna alerta enseñaba un «5» tan llamativo como una con
  // cinco fallos. Ahora cuenta las que exigen atención —crítica o precaución—;
  // el resto sigue estando en la pestaña, sin gritar desde la botonera.
  const avisosDeLaCorrida = normalizarAvisos(result?.scientific_warnings);
  const warningsCount = cuentaQueImporta(avisosDeLaCorrida);

  useEffect(() => {
    setSelectedPoseRank((current) => (current != null && poseRanks.includes(current) ? current : poseRanks[0] ?? null));
  }, [poseRanksKey]);

  useEffect(() => {
    if (physicalFocusRequest > 0) { setActiveTab("structure"); setPhysicalOpen(true); }
  }, [physicalFocusRequest]);

  const openPoseDetails = (rank: number | null) => {
    setPoseDetailsExpanded(true);
    setSelectedPoseRank(rank ?? poseRanks[0] ?? null);
    setActiveTab("structure");
  };

  // ── El camino de vuelta: de una pose a sus controles ───────────────────
  //
  // «Estructura y evidencia» y «Evidencia estructural» son dos pestañas
  // distintas, y para ver POR QUÉ falla la pose que estás mirando había que
  // cambiar de una a otra y volver a buscarla. El foco ya existía en el otro
  // sentido (`physicalFocusRequest` lleva de la evidencia a la pose); esto es
  // el mismo mecanismo al revés.
  const [focoEnEvidencia, setFocoEnEvidencia] = useState(0);
  const abrirControlesDeLaPose = () => {
    setFocoEnEvidencia((n) => n + 1);
    setActiveTab("structure");
    setPhysicalOpen(true);
  };

  /** El veredicto físico de la pose que se está mirando, si lo hay. */
  const estadoDeLaPoseActiva =
    selectedPoseRank == null
      ? null
      : evidenceView.physical.poses.find((pose) => pose.rank === selectedPoseRank) ?? null;

  // ── Qué hay REALMENTE dentro de «Análisis avanzado» ────────────────────
  //
  // Los cuatro paneles avanzados viven detrás de dos clics, y desde fuera no
  // había forma de saber cuáles tenían resultado y cuáles estaban vacíos: se
  // entraba a los cuatro para averiguarlo. Se calcula aquí una vez y se enseña
  // en los dos sitios —en la pestaña principal y en cada sub-botón—, que es lo
  // que el informe pedía sin tener que reestructurar la navegación.
  const avanzadoConDatos: Record<AdvancedTab, boolean> = {
    selectivity: Boolean(selectivityResult) || Boolean(result?.selectivity_ran),
    mmgbsa: mmgbsaDone || result?.mmgbsa_score != null,
    // El índice es lo que decide: si hay perfil, hay número; si no, no lo hay.
    admet: admetDone || result?.blood_viability_score != null,
    // SAR consulta la base por `moleculeId`; sin corrida no hay nada que
    // comparar, y con corrida el propio panel dice si encontró análogos.
    sar: false, // A consultation is available; it is not a recorded SAR result.
    xai:
      Boolean(result?.shap_values) ||
      Boolean(result?.gnn_attention) ||
      Boolean(result?.gnn_attention_svg),
  };
  const avanzadoDisponibles = Object.values(avanzadoConDatos).filter(Boolean).length;
  const advancedTabsTotal = Object.keys(avanzadoConDatos).length;

  const advancedTabs: Array<{ id: AdvancedTab; icon: typeof Activity; label: string }> = [
    { id: "selectivity", icon: ShieldCheck, label: t("pn_flow_selectivity") },
    { id: "mmgbsa", icon: FlaskConical, label: "MM-GBSA" },
    { id: "admet", icon: Gauge, label: "ADMET" },
    { id: "sar", icon: GitFork, label: "SAR" },
    { id: "xai", icon: Activity, label: t("pr_tab_explainability") },
  ];

  const areas = [
    { id: "structure", label: t("rx_poses"), description: t("rx_poses_desc") },
    { id: "properties", label: t("rx_propiedades"), description: t("rx_propiedades_desc"), badge: warningsCount || undefined },
    { id: "advanced", label: t("rx_analisis"), description: t("rx_analisis_desc") },
    { id: "provenance", label: t("rx_procedencia"), description: t("rx_procedencia_desc") },
  ];
  return <section className="min-w-0" aria-label={t("pr_analisis_corrida")}>
    <ResultAreaLayout areas={areas} active={activeTab} onSelect={id => setActiveTab(id as PrimaryTab)}>
      {activeTab === "structure" && (
<div className="space-y-6">
          <ReadingHelp area="structure"/>
          <ProDockingTab
            poses={result?.docking_poses}
            poseSummary={evidenceView.comparison}
            hotspots={result?.target_hotspots}
            hotspots_hit={result?.hotspots_hit}
            referenceResidues={result?.docking_protocol?.reference_residues ?? null}
            activePose={selectedPoseRank ?? undefined}
            onSelectPose={selectOrTogglePose}
            detailsExpanded={poseDetailsExpanded}
            poseDetails={
              <div className="space-y-3">
                <PosePhysicalDetails result={result} rank={selectedPoseRank} />
                {estadoDeLaPoseActiva &&
                  (estadoDeLaPoseActiva.status === "failed" ||
                    estadoDeLaPoseActiva.status === "review") && (
                    <button
                      type="button"
                      onClick={abrirControlesDeLaPose}
                      className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 py-2 font-sans text-sm font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 ${
                        estadoDeLaPoseActiva.status === "failed"
                          ? "border-red-500/30 bg-red-500/[0.08] text-red-100 hover:bg-red-500/[0.16]"
                          : "border-amber-500/30 bg-amber-500/[0.08] text-amber-100 hover:bg-amber-500/[0.16]"
                      }`}
                    >
                      <ListChecks size={14} aria-hidden="true" />
                      {estadoDeLaPoseActiva.status === "failed"
                        ? t("rx_open_failed_checks", { count: estadoDeLaPoseActiva.failedCount })
                        : t("auto_2e80694bf926")}
                    </button>
                  )}
              </div>
            }
          />
          <details className="border-t border-white/10 pt-3">
            <summary className="min-h-12 cursor-pointer py-3 text-base font-semibold text-zinc-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-400">{t("se_cmp_title")}</summary>
            <PoseComparisonWorkspace rows={evidenceView.comparison} onComparePoses={onComparePoses} />
          </details>
          <details open={physicalOpen} onToggle={event => setPhysicalOpen(event.currentTarget.open)} className="border-t border-white/10 pt-3">
            <summary className="min-h-12 cursor-pointer py-3 text-base font-semibold text-zinc-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-400">{t("se_title")}</summary>
          <StructuralEvidencePanel
            result={result}
            physicalFocusRequest={physicalFocusRequest + focoEnEvidencia}
            onOpenPoseDetails={openPoseDetails}
          />
          </details>
        </div>
      )}
      {activeTab === "properties" && (
<div className="space-y-4">
          <ReadingHelp area="properties"/>
          {/* Va ANTES de los descriptores a propósito: MW, LogP y TPSA se
              calculan sobre la forma neutra que escribió el usuario, y la
              especie que se acopló puede ser otra. */}
          <EstadoDelLigando result={result} />
          <ProParametersTab result={result} />
          <section className="border-t border-white/[0.07] pt-5" aria-labelledby="analysis-alerts-title">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <AlertTriangle size={15} className="text-amber-300" aria-hidden="true" />
              <h3 id="analysis-alerts-title" className="font-sans text-base font-bold uppercase tracking-[0.14em] text-zinc-300">
                {t("pr_analysis_alerts_reservations")}
              </h3>
              {warningsCount > 0 && (
                <span className="rounded border border-amber-500/30 px-1.5 py-0.5 font-mono text-sm text-amber-300">
                  {warningsCount}
                </span>
              )}
            </div>
            <ProAlertsTab
              warnings={result?.scientific_warnings}
              inApplicabilityDomain={result?.in_applicability_domain}
              modelUsed={result?.model_used}
            />
          </section>
        </div>
      )}
      <div hidden={activeTab !== "advanced"}>
<div className="space-y-5">
          <ReadingHelp area="advanced"/>
          {signalsSlot && <details className="border-b border-white/10 pb-4"><summary className="min-h-12 cursor-pointer py-3 text-base font-semibold text-zinc-200">{t("rx_senales")}</summary>{signalsSlot}</details>}
          <header className="max-w-[78ch]">
            <h3 className="font-display text-lg font-bold tracking-tight text-zinc-100">{t("pr_post_docking")}</h3>
            <p className="mt-1.5 text-base leading-6 text-zinc-300 font-sans">
              {t("pr_post_docking_limite")}
            </p>
          </header>

          <div className={readingStyles.analysisTabs} role="tablist" aria-label={t("pr_metodos_avanzados")}>
            {advancedTabs.map((tab) => {
              const active = advancedTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  id={`advanced-tab-${tab.id}`}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-label={`${tab.label}: ${t(avanzadoConDatos[tab.id] ? "ux_analysis_available" : "ux_analysis_absent")}${tab.id === "mmgbsa" ? ` · ${t("ux_method_unavailable")}` : ""}`}
                  aria-controls={`advanced-panel-${tab.id}`}
                  onClick={() => setAdvancedTab(tab.id)}
                  tabIndex={active ? 0 : -1}
                  onKeyDown={(event) => {
                    const index = advancedTabs.findIndex((entry) => entry.id === tab.id);
                    const next = event.key === "ArrowRight" ? (index + 1) % advancedTabs.length : event.key === "ArrowLeft" ? (index - 1 + advancedTabs.length) % advancedTabs.length : event.key === "Home" ? 0 : event.key === "End" ? advancedTabs.length - 1 : -1;
                    if (next < 0) return;
                    event.preventDefault();
                    const nextId = advancedTabs[next].id;
                    setAdvancedTab(nextId);
                    document.getElementById(`advanced-tab-${nextId}`)?.focus();
                  }}
                  className={readingStyles.analysisTab}
                >
                  <Icon size={16} aria-hidden="true" />
                  <span className="min-w-0"><span className={readingStyles.analysisTabName}>{tab.label}</span>
                    <span className={readingStyles.analysisTabState} data-result={avanzadoConDatos[tab.id]}>{t(avanzadoConDatos[tab.id]?"ux_analysis_available":"ux_analysis_absent")}</span>
                    {tab.id === "mmgbsa" && <span className={readingStyles.analysisTabState}>{t("ux_method_unavailable")}</span>}
                  </span>
                </button>
              );
            })}
          </div>

          {(selectivityActive || openedSelectivityKey === evaluationKey) && (
            <div id="advanced-panel-selectivity" role="tabpanel" aria-labelledby="advanced-tab-selectivity" hidden={!selectivityActive}>
              <ProSelectivityPanel
                key={evaluationKey}
                isActive={evaluationVisible && selectivityActive}
                moleculeId={moleculeId}
                taskId={taskId}
                // `result.best_affinity` estaba en esta cadena de respaldos y NO existe en
                // `EvaluationResult`: el `as any` lo ocultaba, así que era un eslabón
                // muerto que nunca aportó un valor. La afinidad de la diana principal
                // sale del campo persistido o, si falta, de la mejor pose.
                onTargetAffinity={result?.affinity_kcal ?? result?.docking_poses?.[0]?.affinity ?? null}
                initialResult={selectivityResult}
                onUpdateResult={onUpdateSelectivityResult}
                onWorkStateChange={onSelectivityWorkChange}
                autoPoll={enableSelectivity}
              />
            </div>
          )}

          {activeTab === "advanced" && advancedTab === "mmgbsa" && (
            <section id="advanced-panel-mmgbsa" role="tabpanel" aria-labelledby="advanced-tab-mmgbsa" className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.035] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 max-w-[70ch]">
                  <div className="flex items-center gap-2">
                    <FlaskConical size={16} className="text-emerald-300" aria-hidden="true" />
                    <h4 id="mmgbsa-post-title" className="font-sans text-base font-bold uppercase tracking-[0.14em] text-emerald-200">
                      {t("pr_refinar_mmgbsa")}
                    </h4>
                  </div>
                  <p className="mt-2 text-base leading-6 text-amber-200 font-sans">
                    {t("pr_mmgbsa_retirado")}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onRequestMmgbsa}
                  disabled
                  className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-3 py-2 font-sans text-sm font-bold uppercase tracking-wider text-emerald-100 transition-colors hover:bg-emerald-500/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <FlaskConical size={14} aria-hidden="true" />
                  {t("pr_mmgbsa_indisponible")}
                </button>
              </div>
              {!moleculeId && (
                <p className="mt-3 text-base leading-6 text-zinc-300 font-sans">{t("ev_admet_requiere_corrida")}</p>
              )}
            </section>
          )}

          {activeTab === "advanced" && advancedTab === "admet" && (
            <section id="advanced-panel-admet" role="tabpanel" aria-labelledby="advanced-tab-admet" className="rounded-xl border border-sky-500/20 bg-sky-500/[0.035] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 max-w-[70ch]">
                  <div className="flex items-center gap-2">
                    <Gauge size={16} className="text-sky-300" aria-hidden="true" />
                    <h4 id="admet-post-title" className="font-sans text-base font-bold uppercase tracking-[0.14em] text-sky-200">
                      {t("pr_calcular_admet")}
                    </h4>
                  </div>
                  <p className="mt-2 text-base leading-6 text-zinc-400 font-sans">
                    {t("pr_admet_predice")}{" "}
                    <strong className="font-semibold text-zinc-300">{t("pr_solo_smiles")}</strong>{t("pr_admet_no_repite")}
                  </p>
                  {/* La misma advertencia que lleva el interruptor de Opciones.
                      Un modelo predictivo no es una medición, y el sitio donde
                      alguien pulsa el botón es donde tiene que leerlo. */}
                  <p className="mt-1.5 text-base leading-6 text-amber-200 font-sans">
                    {t("pr_admet_predicciones")}
                  </p>
                  {admetDone && !admetError && (
                    <p className="mt-2 text-base leading-6 text-sky-200 font-sans">
                      {t("auto_1171a79e25ba")}{" "}
                      <strong className="font-semibold">{t("pr_tab_properties")}</strong> {t("pr_viaja_en_dossier")}
                    </p>
                  )}
                  {admetError && (
                    <p role="alert" className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-base leading-6 text-amber-200 font-sans">
                      {admetError}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={onRequestAdmet}
                  disabled={!moleculeId || admetRunning || admetDone}
                  className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg border border-sky-400/30 bg-sky-500/15 px-3 py-2 font-sans text-sm font-bold uppercase tracking-wider text-sky-100 transition-colors hover:bg-sky-500/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Gauge size={14} aria-hidden="true" />
                  {admetRunning ? t("c_calculando") : admetDone ? t("pr_admet_available") : t("pr_admet_calculate")}
                </button>
              </div>
              {!moleculeId && (
                <p className="mt-3 text-base leading-6 text-zinc-300 font-sans">{t("ev_admet_requiere_corrida")}</p>
              )}
            </section>
          )}

          {activeTab === "advanced" && advancedTab === "sar" && (
            <section id="advanced-panel-sar" role="tabpanel" aria-labelledby="advanced-tab-sar" className="space-y-3">
              <div>
                <h4 id="sar-available-title" className="font-sans text-base font-bold uppercase tracking-[0.14em] text-zinc-300">{t("pr_sar_evidence_available")}</h4>
                <p className="mt-1 text-base leading-6 text-zinc-300 font-sans">
                  {t("pr_sar_explicacion")}
                </p>
              </div>
              <ProSarTab moleculeId={moleculeId} taskId={taskId} caseRuns={caseRuns} />
            </section>
          )}

          {activeTab === "advanced" && advancedTab === "xai" && (
            <div id="advanced-panel-xai" role="tabpanel" aria-labelledby="advanced-tab-xai">
              <ProXaiTab
                shapValues={result?.shap_values}
                gnnAttention={result?.gnn_attention}
                gnnAttentionSvg={result?.gnn_attention_svg}
                gnnPharmacophores={result?.gnn_pharmacophores}
                moleculeId={moleculeId}
                inApplicabilityDomain={result?.in_applicability_domain}
                taskId={result?.task_id??taskId}
                poses={result?.docking_poses}
                fallbackReason={result?.fallback_reason}
              />
            </div>
          )}
        </div>
      </div>
      {activeTab === "provenance" && <div className="space-y-8"><ReadingHelp area="provenance"/>{provenanceSlot}{result && <RunDataExplorer result={result} />}</div>}
    </ResultAreaLayout>
  </section>;
};
