"use client";

/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 */

// La evidencia no desaparece: se agrupa por la pregunta que responde. Esto
// reduce la botonera heredada sin ocultar alertas, XAI, SAR, selectividad o la
// trazabilidad estructural de la corrida.

import React, { useEffect, useMemo, useState } from "react";
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
import type { JobStatus } from "../../../lib/types";
import {
  deriveStructuralEvidence,
  type EvaluationResultWithEvidence,
  type PhysicalStatus,
  type PoseComparisonRow,
} from "../../../lib/structuralEvidence";

type PrimaryTab = "structure" | "properties" | "advanced" | "compare" | "evidence";
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
    <div id="analysis-panel-compare" role="tabpanel" aria-labelledby="analysis-tab-compare" className="space-y-5">
      <header className="max-w-[78ch]">
        <h3 className="font-display text-lg font-bold tracking-tight text-zinc-100">Comparar poses</h3>
        <p className="mt-1.5 text-xs leading-5 text-zinc-500">
          Elige cualquier par de poses generado por esta corrida. La comparación conserva afinidad, señal del selector y estado físico; no convierte esos datos en una única calificación.
        </p>
      </header>

      {rows.length === 0 ? (
        <p className="rounded-xl border border-white/[0.08] bg-black/20 p-4 text-xs leading-relaxed text-zinc-400">
          No hay poses serializadas que comparar todavía.
        </p>
      ) : (
        <>
          <section aria-label="Elegir poses para comparar" className="rounded-xl border border-white/[0.08] bg-black/20 p-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="grid min-w-[12rem] gap-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                Pose A
                <select
                  value={leftRank ?? ""}
                  onChange={(event) => setLeft(Number(event.target.value))}
                  className="min-h-10 rounded-lg border border-white/[0.1] bg-surface-950 px-3 font-mono text-xs text-zinc-200 outline outline-2 outline-offset-1 outline-transparent transition-colors focus:border-purple-400 focus:outline-purple-400"
                >
                  {rows.map((row) => (
                    <option key={row.rank} value={row.rank}>
                      Pose #{row.rank} · {row.affinity?.toFixed(2) ?? "—"} kcal/mol
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid min-w-[12rem] gap-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                Pose B
                <select
                  value={rightRank ?? ""}
                  onChange={(event) => setRight(Number(event.target.value))}
                  className="min-h-10 rounded-lg border border-white/[0.1] bg-surface-950 px-3 font-mono text-xs text-zinc-200 outline outline-2 outline-offset-1 outline-transparent transition-colors focus:border-purple-400 focus:outline-purple-400"
                >
                  {rows.map((row) => (
                    <option key={row.rank} value={row.rank}>
                      Pose #{row.rank} · {row.affinity?.toFixed(2) ?? "—"} kcal/mol
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
                className="inline-flex min-h-10 whitespace-nowrap items-center gap-2 rounded-lg border border-purple-500/30 bg-purple-500/[0.1] px-4 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-purple-100 transition-colors hover:bg-purple-500/[0.18] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-45"
              >
                <ArrowLeftRight size={14} aria-hidden="true" />
                Abrir comparación 3D
              </button>
            </div>
            {rows.length < 2 && (
              <p className="mt-3 text-[11px] leading-relaxed text-zinc-500">
                Se necesitan al menos dos poses para abrir una comparación.
              </p>
            )}
          </section>

          <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
            <table className="w-full min-w-[42rem] border-collapse text-xs">
              <caption className="sr-only">Resumen comparable de todas las poses generadas</caption>
              <thead>
                <tr className="border-b border-white/[0.08] text-left font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                  <th scope="col" className="px-3 py-2.5 font-normal">Pose</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">Afinidad Vina</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">Selector</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">Controles físicos</th>
                  <th scope="col" className="px-3 py-2.5 font-normal">Papel</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const roles = [
                    row.isVinaTop1 ? "Vina top-1" : null,
                    row.isSuggested ? "Sugerida" : null,
                    row.isAlternative && !row.isSuggested ? "Alternativa" : null,
                  ].filter(Boolean);
                  return (
                    <tr key={row.rank} className="border-b border-white/[0.06] last:border-b-0">
                      <th scope="row" className="px-3 py-2.5 text-left font-mono text-zinc-200">#{row.rank}</th>
                      <td className="px-3 py-2.5 font-mono text-zinc-400">{row.affinity?.toFixed(2) ?? "—"}</td>
                      <td className="px-3 py-2.5 font-mono text-zinc-400">{row.selectorScore?.toFixed(4) ?? "—"}</td>
                      <td className={`px-3 py-2.5 ${PHYSICAL_STATUS[row.physicalStatus].className}`}>
                        {PHYSICAL_STATUS[row.physicalStatus].label}
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
  /** El pipeline lanzó el panel de selectividad en background. */
  enableSelectivity?: boolean;
  /** Abre el cálculo real de MM-GBSA en el contenedor que mantiene su estado. */
  onRequestMmgbsa?: () => void;
  mmgbsaRunning?: boolean;
  mmgbsaDone?: boolean;
  /**
   * Calcular el perfil ADMET sobre una corrida ya terminada.
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
  /** Navega desde el resumen global hacia Controles físicos. */
  physicalFocusRequest?: number;
  /** Abre una comparación 3D de los rangos elegidos por el usuario. */
  onComparePoses?: (leftRank: number, rightRank: number) => void;
}

export const ProAnalysisTabs: React.FC<ProAnalysisTabsProps> = ({
  status,
  selectivityResult,
  moleculeId,
  onUpdateSelectivityResult,
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
}) => {
  const [activeTab, setActiveTab] = useState<PrimaryTab>("structure");
  const [advancedTab, setAdvancedTab] = useState<AdvancedTab>("selectivity");
  const [selectedPoseRank, setSelectedPoseRank] = useState<number | null>(null);
  const result = (structuralEvidenceResult ?? status?.result ?? null) as EvaluationResultWithEvidence | null;
  const evidenceView = useMemo(() => deriveStructuralEvidence(result), [result]);
  const poseRanks = evidenceView.comparison.map((row) => row.rank);
  const poseRanksKey = poseRanks.join(",");
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
    if (physicalFocusRequest > 0) setActiveTab("evidence");
  }, [physicalFocusRequest]);

  const openPoseDetails = (rank: number | null) => {
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
    setActiveTab("evidence");
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
    sar: Boolean(moleculeId),
    xai:
      Boolean(result?.shap_values) ||
      Boolean(result?.gnn_attention) ||
      Boolean(result?.gnn_attention_svg),
  };
  const avanzadoDisponibles = Object.values(avanzadoConDatos).filter(Boolean).length;
  const advancedTabsTotal = Object.keys(avanzadoConDatos).length;

  const tabs: Array<{
    id: PrimaryTab;
    icon: typeof Boxes;
    label: string;
    badge?: number;
    /** Qué significa el número, para quien no ve el color. */
    badgeDescripcion?: string;
    /** `alerta` (ámbar) o `disponible` (verde). El color no informa solo. */
    badgeTono?: "alerta" | "disponible";
  }> = [
    { id: "structure", icon: Boxes, label: "Estructura y evidencia" },
    {
      id: "properties",
      icon: Sliders,
      label: "Propiedades",
      badge: warningsCount || undefined,
      badgeDescripcion:
        warningsCount === 1 ? "1 aviso que atender" : `${warningsCount} avisos que atender`,
      badgeTono: "alerta",
    },
    { id: "compare", icon: ArrowLeftRight, label: "Comparar poses" },
    { id: "evidence", icon: ListChecks, label: "Evidencia estructural" },
    {
      id: "advanced",
      icon: FlaskConical,
      label: "Análisis avanzado",
      badge: avanzadoDisponibles || undefined,
      badgeDescripcion: `${avanzadoDisponibles} de ${advancedTabsTotal} paneles con resultado`,
      badgeTono: "disponible",
    },
  ];
  const advancedTabs: Array<{ id: AdvancedTab; icon: typeof Activity; label: string }> = [
    { id: "selectivity", icon: ShieldCheck, label: "Selectividad" },
    { id: "mmgbsa", icon: FlaskConical, label: "MM-GBSA" },
    { id: "admet", icon: Gauge, label: "ADMET" },
    { id: "sar", icon: GitFork, label: "SAR" },
    { id: "xai", icon: Activity, label: "Explicabilidad" },
  ];

  return (
    <section className="space-y-5" aria-label="Análisis de la corrida">
      <div
        className="flex flex-wrap items-center justify-center gap-1 rounded-xl border border-white/[0.06] bg-black/10 p-1"
        role="tablist"
        aria-label="Áreas de análisis"
      >
        {tabs.map((tab) => {
          const active = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`analysis-tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={active}
              aria-label={tab.badge ? `${tab.label}: ${tab.badgeDescripcion}` : tab.label}
              aria-controls={`analysis-panel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              tabIndex={active ? 0 : -1}
              onKeyDown={(event) => {
                const index = tabs.findIndex((entry) => entry.id === tab.id);
                const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index - 1 + tabs.length) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
                if (next < 0) return;
                event.preventDefault();
                const nextId = tabs[next].id;
                setActiveTab(nextId);
                document.getElementById(`analysis-tab-${nextId}`)?.focus();
              }}
              className={`relative inline-flex min-h-10 whitespace-nowrap items-center gap-2 rounded-lg px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 ${
                active
                  ? "bg-purple-500/12 text-purple-200 shadow-[0_0_18px_rgba(139,92,246,0.12)]"
                  : "text-zinc-500 hover:bg-white/[0.03] hover:text-zinc-300"
              }`}
            >
              <Icon size={14} aria-hidden="true" />
              <span>{tab.label}</span>
              {/* El número es redundante para quien usa lector de pantalla: su
                  significado ya va en el `aria-label` del botón. Repetirlo aquí
                  haría que se leyera «Análisis avanzado 2 2». */}
              {tab.badge && (
                <span
                  aria-hidden="true"
                  className={`rounded border px-1.5 py-0.5 text-[9px] leading-none ${
                    tab.badgeTono === "disponible"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                      : "border-amber-500/30 bg-amber-500/10 text-amber-300"
                  }`}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {activeTab === "structure" && (
        <div id="analysis-panel-structure" role="tabpanel" aria-labelledby="analysis-tab-structure" className="space-y-4">
          <ProDockingTab
            poses={result?.docking_poses}
            hotspots={result?.target_hotspots}
            hotspots_hit={result?.hotspots_hit}
            activePose={selectedPoseRank ?? undefined}
            onSelectPose={setSelectedPoseRank}
            poseDetails={
              <div className="space-y-3">
                <PosePhysicalDetails result={result} rank={selectedPoseRank} />
                {estadoDeLaPoseActiva &&
                  (estadoDeLaPoseActiva.status === "failed" ||
                    estadoDeLaPoseActiva.status === "review") && (
                    <button
                      type="button"
                      onClick={abrirControlesDeLaPose}
                      className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 ${
                        estadoDeLaPoseActiva.status === "failed"
                          ? "border-red-500/30 bg-red-500/[0.08] text-red-100 hover:bg-red-500/[0.16]"
                          : "border-amber-500/30 bg-amber-500/[0.08] text-amber-100 hover:bg-amber-500/[0.16]"
                      }`}
                    >
                      <ListChecks size={14} aria-hidden="true" />
                      {estadoDeLaPoseActiva.status === "failed"
                        ? `Ver los ${estadoDeLaPoseActiva.failedCount} controles que fallan`
                        : "Ver por qué requiere revisión"}
                    </button>
                  )}
              </div>
            }
          />
        </div>
      )}

      {activeTab === "properties" && (
        <div id="analysis-panel-properties" role="tabpanel" aria-labelledby="analysis-tab-properties" className="space-y-7">
          {/* Va ANTES de los descriptores a propósito: MW, LogP y TPSA se
              calculan sobre la forma neutra que escribió el usuario, y la
              especie que se acopló puede ser otra. */}
          <EstadoDelLigando result={result} />
          <ProParametersTab result={result} />
          <section className="border-t border-white/[0.07] pt-5" aria-labelledby="analysis-alerts-title">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <AlertTriangle size={15} className="text-amber-300" aria-hidden="true" />
              <h3 id="analysis-alerts-title" className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-300">
                Alertas y reservas
              </h3>
              {warningsCount > 0 && (
                <span className="rounded border border-amber-500/30 px-1.5 py-0.5 font-mono text-[10px] text-amber-300">
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

      {activeTab === "advanced" && (
        <div id="analysis-panel-advanced" role="tabpanel" aria-labelledby="analysis-tab-advanced" className="space-y-5">
          <header className="max-w-[78ch]">
            <h3 className="font-display text-lg font-bold tracking-tight text-zinc-100">Análisis post-docking</h3>
            <p className="mt-1.5 text-xs leading-5 text-zinc-500">
              Estas acciones amplían la evidencia de la corrida; no convierten una afinidad de docking en actividad, eficacia o selectividad experimental.
            </p>
          </header>

          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Métodos de análisis avanzado">
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
                  aria-label={`${tab.label}: ${avanzadoConDatos[tab.id] ? "con resultado" : "sin resultado"}`}
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
                  className={`inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 ${
                    active
                      ? "border-purple-500/35 bg-purple-500/10 text-purple-200"
                      : "border-white/[0.08] text-zinc-500 hover:border-white/15 hover:text-zinc-300"
                  }`}
                >
                  <Icon size={13} aria-hidden="true" />
                  {tab.label}
                  {/* Un punto verde = este panel tiene resultado. Antes había
                      que entrar en los cuatro para saber cuál tenía algo. */}
                  {/* Decorativo: el estado va en el `aria-label` del botón, y
                      repetirlo aquí lo haría leerse dos veces. */}
                  <span
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      avanzadoConDatos[tab.id] ? "bg-emerald-400" : "bg-white/15"
                    }`}
                  />
                </button>
              );
            })}
          </div>

          {advancedTab === "selectivity" && (
            <div id="advanced-panel-selectivity" role="tabpanel" aria-labelledby="advanced-tab-selectivity">
              <ProSelectivityPanel
                moleculeId={moleculeId}
                // `result.best_affinity` estaba en esta cadena de respaldos y NO existe en
                // `EvaluationResult`: el `as any` lo ocultaba, así que era un eslabón
                // muerto que nunca aportó un valor. La afinidad de la diana principal
                // sale del campo persistido o, si falta, de la mejor pose.
                onTargetAffinity={result?.affinity_kcal ?? result?.docking_poses?.[0]?.affinity ?? null}
                initialResult={selectivityResult}
                onUpdateResult={onUpdateSelectivityResult}
                autoPoll={enableSelectivity}
              />
            </div>
          )}

          {advancedTab === "mmgbsa" && (
            <section id="advanced-panel-mmgbsa" role="tabpanel" aria-labelledby="advanced-tab-mmgbsa" className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.035] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 max-w-[70ch]">
                  <div className="flex items-center gap-2">
                    <FlaskConical size={16} className="text-emerald-300" aria-hidden="true" />
                    <h4 id="mmgbsa-post-title" className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-emerald-200">
                      Refinar una pose con MM-GBSA
                    </h4>
                  </div>
                  {/* La frase anterior era «Usa la pose real de docking y reporta
                      ΔG = G(complejo) − G(receptor) − G(ligando)». Describe la
                      aritmética, que es cierta, y al leerse sola invita a tomar
                      el número por una energía libre calculada con un campo de
                      fuerzas adecuado al ligando. No lo es: el ligando se tipa
                      sobre la biblioteca de PROTEÍNA de AMBER14. Lo que el
                      método sostiene —ordenar poses del mismo ligando— se dice
                      aquí, no en una nota que aparece después de calcular. */}
                  <p className="mt-2 text-xs leading-5 text-zinc-400">
                    Reminimiza la pose real del acoplamiento con OpenMM y resta
                    receptor y ligando aislados. Sirve para{" "}
                    <strong className="font-semibold text-zinc-300">ordenar poses de esta misma molécula</strong>{" "}
                    contra este mismo receptor.
                  </p>
                  <p className="mt-1.5 text-[11px] leading-5 text-amber-200/70">
                    No es comparable entre moléculas distintas ni con un ΔG experimental:
                    el ligando se parametriza con tipos de átomo de proteína (AMBER14), no
                    con un campo de fuerzas de molécula pequeña. Requiere C, H, O, N, S o P
                    — con halógenos el cálculo no puede ejecutarse.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onRequestMmgbsa}
                  disabled={!moleculeId || mmgbsaRunning || mmgbsaDone}
                  className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-emerald-100 transition-colors hover:bg-emerald-500/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <FlaskConical size={14} aria-hidden="true" />
                  {mmgbsaRunning ? "Calculando…" : mmgbsaDone ? "MM-GBSA disponible" : "Configurar MM-GBSA"}
                </button>
              </div>
              {!moleculeId && (
                <p className="mt-3 text-[11px] leading-5 text-zinc-500">Requiere una corrida terminada con una molécula identificable.</p>
              )}
            </section>
          )}

          {advancedTab === "admet" && (
            <section id="advanced-panel-admet" role="tabpanel" aria-labelledby="advanced-tab-admet" className="rounded-xl border border-sky-500/20 bg-sky-500/[0.035] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 max-w-[70ch]">
                  <div className="flex items-center gap-2">
                    <Gauge size={16} className="text-sky-300" aria-hidden="true" />
                    <h4 id="admet-post-title" className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-sky-200">
                      Calcular el perfil ADMET
                    </h4>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-zinc-400">
                    Predice solubilidad, absorción intestinal, permeabilidad BBB y unión a
                    proteínas plasmáticas con ADMET-AI, en esta máquina. Depende{" "}
                    <strong className="font-semibold text-zinc-300">sólo del SMILES</strong>:
                    no usa la pose ni el receptor, así que no hace falta repetir el acoplamiento.
                  </p>
                  {/* La misma advertencia que lleva el interruptor de Opciones.
                      Un modelo predictivo no es una medición, y el sitio donde
                      alguien pulsa el botón es donde tiene que leerlo. */}
                  <p className="mt-1.5 text-[11px] leading-5 text-amber-200/70">
                    Son predicciones de un modelo, no mediciones: se citan como tales. La
                    primera ejecución carga el ensamble y puede tardar —especialmente en una
                    máquina virtual o sin GPU—.
                  </p>
                  {admetDone && !admetError && (
                    <p className="mt-2 text-[11px] leading-5 text-sky-200/80">
                      El perfil está calculado y guardado con la corrida: aparece en{" "}
                      <strong className="font-semibold">Propiedades</strong> y viaja en el dossier.
                    </p>
                  )}
                  {admetError && (
                    <p role="alert" className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-[11px] leading-5 text-amber-200">
                      {admetError}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={onRequestAdmet}
                  disabled={!moleculeId || admetRunning || admetDone}
                  className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg border border-sky-400/30 bg-sky-500/15 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-sky-100 transition-colors hover:bg-sky-500/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Gauge size={14} aria-hidden="true" />
                  {admetRunning ? "Calculando…" : admetDone ? "ADMET disponible" : "Calcular ADMET"}
                </button>
              </div>
              {!moleculeId && (
                <p className="mt-3 text-[11px] leading-5 text-zinc-500">Requiere una corrida terminada con una molécula identificable.</p>
              )}
            </section>
          )}

          {advancedTab === "sar" && (
            <section id="advanced-panel-sar" role="tabpanel" aria-labelledby="advanced-tab-sar" className="space-y-3">
              <div>
                <h4 id="sar-available-title" className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-300">Evidencia SAR disponible</h4>
                <p className="mt-1 text-xs leading-5 text-zinc-500">
                  Consulta análogos que ya existen en el historial. Esta versión no genera actividad ni inventa una serie SAR cuando no hay mediciones comparables.
                </p>
              </div>
              <ProSarTab moleculeId={moleculeId} />
            </section>
          )}

          {advancedTab === "xai" && (
            <div id="advanced-panel-xai" role="tabpanel" aria-labelledby="advanced-tab-xai">
              <ProXaiTab
                shapValues={result?.shap_values}
                gnnAttention={result?.gnn_attention}
                gnnAttentionSvg={result?.gnn_attention_svg}
                gnnPharmacophores={result?.gnn_pharmacophores}
                moleculeId={moleculeId}
                inApplicabilityDomain={result?.in_applicability_domain}
                fallbackReason={result?.fallback_reason}
              />
            </div>
          )}
        </div>
      )}

      {activeTab === "compare" && (
        <PoseComparisonWorkspace rows={evidenceView.comparison} onComparePoses={onComparePoses} />
      )}

      {activeTab === "evidence" && (
        <div id="analysis-panel-evidence" role="tabpanel" aria-labelledby="analysis-tab-evidence">
          {/* Dos fuentes de foco, sumadas porque las dos son contadores que
              solo crecen: el resumen global de la corrida y el botón de la
              pose que se está mirando en «Estructura y evidencia». */}
          <StructuralEvidencePanel
            result={result}
            physicalFocusRequest={physicalFocusRequest + focoEnEvidencia}
            onOpenPoseDetails={openPoseDetails}
          />
        </div>
      )}
    </section>
  );
};
