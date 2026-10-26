import {useId} from "react";

import { ReadingHelp, ReadingReservations, useResultReading, type ReadingReservation } from "./ResultReadingPresentation";
import readingStyles from "./ResultReadingPresentation.module.css";
import { InsigniaDelCatalogo } from "@/components/science/InsigniaDelCatalogo";
import { useLanguage } from "@/context/LanguageContext";
import {
  AlertTriangle,
  ChevronDown,
  CheckCircle2,
  CircleDashed,
  ShieldAlert,
} from "lucide-react";
import type { Target } from "../../../lib/api";
import type { EvaluationResult, ValidationResult } from "../../../lib/types";
import { normalizarAvisos, ordenarPorSeveridad } from "../../../lib/avisos";
import {
  deriveEvaluationEvidence,
  deriveEvaluationReadiness,
  fraseDeMuestreoTraducida,
  type CheckStatus,
  type EvidenceStatus,
} from "../../../lib/evaluationEvidence";

// Hallmark · genre: modern-minimal · macrostructure: Workbench · theme: existing MolDesign · enrichment: none

const STATUS_STYLES: Record<EvidenceStatus, string> = {
  ready: "border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-800 dark:text-emerald-200",
  review: "border-amber-500/25 bg-amber-500/[0.06] text-amber-800 dark:text-amber-200",
  incomplete: "border-rose-500/25 bg-rose-500/[0.06] text-rose-800 dark:text-rose-200",
};

const CHECK_STYLES: Record<CheckStatus, string> = {
  available: "text-emerald-800 dark:text-emerald-300",
  review: "text-amber-800 dark:text-amber-300",
  missing: "text-rose-800 dark:text-rose-300",
  not_evaluated: "text-zinc-400",
};

const NEXT_ACTION_STYLES = {
  proceed: "border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-800 dark:text-emerald-100",
  review: "border-amber-500/25 bg-amber-500/[0.06] text-amber-800 dark:text-amber-100",
  abstain: "border-rose-500/25 bg-rose-500/[0.06] text-rose-800 dark:text-rose-100",
} as const;

function StatusIcon({ status, size = 16 }: { status: CheckStatus; size?: number }) {
  if (status === "available") return <CheckCircle2 size={size} aria-hidden="true" />;
  if (status === "review") return <AlertTriangle size={size} aria-hidden="true" />;
  if (status === "missing") return <ShieldAlert size={size} aria-hidden="true" />;
  return <CircleDashed size={size} aria-hidden="true" />;
}

/**
 * ESTADO ACTUAL: el workspace ya NO lo monta.
 *
 * Respondía a «¿qué va a entrar en la corrida?» conjeturando desde el
 * navegador —«SMILES presente; se validará al ejecutar»— sin abrir el receptor
 * ni conocer la política de preparación. Desde el sprint de preflight, ese
 * hueco lo ocupa `components/evaluation/PreparationPanel`, que enseña lo que
 * el backend midió sobre los archivos reales. Dos respuestas a la misma
 * pregunta, y ésta era la que no había mirado.
 *
 * Se conserva —con `deriveEvaluationReadiness` y sus pruebas— porque sigue
 * siendo la lectura correcta cuando no hay backend con el que comprobar nada.
 */
export function EvaluationReadinessPanel({
  smiles,
  target,
  validation,
}: {
  smiles: string;
  target: Target | null;
  validation?: ValidationResult | null;
}) {
  const { t } = useLanguage();
  const readiness = deriveEvaluationReadiness(smiles, target, validation);

  return (
    <section className="w-full max-w-[1600px] border-y border-zinc-800 bg-zinc-950/55 px-4 py-5 md:px-6" aria-labelledby="evaluation-readiness-title">
      <div className="grid gap-5 lg:grid-cols-[minmax(220px,0.72fr)_minmax(0,1.8fr)] lg:items-start">
        <div className="min-w-0">
          <div className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 font-sans text-sm font-bold uppercase tracking-wider ${STATUS_STYLES[readiness.status]}`}>
            <StatusIcon status={readiness.status === "ready" ? "available" : readiness.status === "review" ? "review" : "missing"} />
            {readiness.label}
          </div>
          <h2 id="evaluation-readiness-title" className="mt-3 font-display text-xl font-bold tracking-tight text-white">
            {t("pr_preparacion_titulo")}
          </h2>
          <p className="mt-2 max-w-[58ch] text-base leading-6 text-zinc-400 font-sans">{readiness.summary}</p>
        </div>

        <div className="grid min-w-0 gap-x-6 sm:grid-cols-2">
          {readiness.checks.map((check) => (
            <div key={check.id} className="flex min-w-0 gap-3 border-b border-white/[0.07] py-3 first:pt-0 sm:[&:nth-child(2)]:pt-0">
              <span className={`mt-0.5 shrink-0 ${CHECK_STYLES[check.status]}`}>
                <StatusIcon status={check.status} />
              </span>
              <div className="min-w-0">
                <p className="text-base font-bold text-zinc-100 font-sans leading-6">{check.label}</p>
                <p className="mt-1 text-base leading-6 text-zinc-300 font-sans">{check.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function EvaluationEvidencePanel({
  result,
  target,
  onOpenPhysicalControls,
  compact = false,
  provenanceOnly = false,
}: {
  result: EvaluationResult;
  target: Target | null;
  compact?: boolean;
  /** Protocol and records only; the result overview remains above the area index. */
  provenanceOnly?: boolean;
  /** Lleva al detalle exacto que sustenta una reserva física. */
  onOpenPhysicalControls?: () => void;
}) {
  const { t } = useLanguage();
  const reading = useResultReading();
  const summaryId = useId();
  const evidence = deriveEvaluationEvidence(result, target, t);
  const physicalNeedsReview = evidence.physicalValidity.status !== "passed";
  const notices = ordenarPorSeveridad(normalizarAvisos(result.scientific_warnings));
  const reservations: ReadingReservation[] = evidence.dimensions.flatMap((dimension) => {
    const fallback = dimension.id === "model" ? evidence.modelContext.fallbackReason : null;
    if (dimension.status !== "review" && dimension.status !== "missing" &&
        !(dimension.id === "physical" && physicalNeedsReview) && !fallback) return [];
    const status: CheckStatus = dimension.id === "physical" && evidence.physicalValidity.status === "failed"
      ? "missing"
      : dimension.status === "available" ? "review" : dimension.status;
    return [{
      id: dimension.id as string,
      label: fallback
        ? t(result.model_used === "universal" ? "pr_ev_overview_universal" : "pr_ev_overview_fallback")
        : dimension.id === "sampling" && evidence.nearTieCount > 1
          ? t("pr_ev_overview_sampling")
          : dimension.label,
      detail: fallback
        ? `${fallback}${evidence.modelContext.inDomain === false ? ` ${t("pr_ev_uncertainty_outside_domain")}` : ""}`
        : dimension.id === "sampling" && evidence.nearTieCount > 1
          ? t("pr_ev_uncertainty_near_tie", { count: evidence.nearTieCount })
          : dimension.id === "reproducibility"
            ? t("pr_ev_overview_trace_incomplete")
            : dimension.id === "model" && evidence.modelContext.inDomain === false
              ? t("pr_ev_uncertainty_outside_domain")
              : dimension.id === "physicochemical"
                ? t(dimension.status === "missing" ? "pr_ev_overview_descriptors_missing" : "pr_ev_overview_descriptors_partial")
                : dimension.id === "selectivity"
                  ? t("pr_ev_overview_selectivity_missing_results")
                  : dimension.detail,
      status,
    }];
  });
  // La severidad viene del contrato; las notas informativas se conservan en
  // el detalle. No se interpreta la redacción para decidir un color.
  for (const [index, notice] of notices.entries()) {
    if (notice.severidad === "info" || notice.severidad === "positiva") continue;
    if (notice.codigo && reservations.some((item) => item.code === notice.codigo && item.detail === notice.mensaje)) continue;
    reservations.push({
      id: `notice-${index}`,
      code: notice.codigo,
      label: t(notice.severidad === "critica" ? "pr_ev_overview_critical"
        : notice.severidad === "precaucion" ? "pr_ev_overview_caution" : "pr_ev_overview_legacy"),
      detail: notice.mensaje,
      status: notice.severidad === "critica" ? "missing"
        : notice.severidad === "precaucion" ? "review" : "not_evaluated",
    });
  }
  reservations.sort((a, b) => Number(b.status === "missing") - Number(a.status === "missing"));
  const summaryStatus: EvidenceStatus = evidence.status === "incomplete" ? "incomplete"
    : reservations.length > 0 ? "review" : evidence.status;
  const statusIcon: CheckStatus = summaryStatus === "ready" ? "available" : summaryStatus === "review" ? "review" : "missing";
  const recordedFacts = [
    ...(evidence.poseCount > 0 ? [t("pr_ev_overview_poses", { count: evidence.poseCount })] : []),
    ...(evidence.physicalValidity.status === "passed" ? [t("pr_ev_overview_physical", {
      evaluated: result.structural_evidence?.poses_evaluated ?? 0,
      produced: result.structural_evidence?.poses_produced ?? 0,
    })] : []),
    ...(evidence.dimensions.find((item) => item.id === "reproducibility")?.status === "available"
      ? [t("pr_ev_overview_trace")] : []),
  ];
  const limits = [
    ...(!result.selectivity_ran ? [t("pr_ev_overview_selectivity")] : []),
    ...(evidence.modelContext.inDomain == null ? [t("pr_ev_uncertainty_domain_unreported")] : []),
    // SCI-A-023: el ensemble se dice si el protocolo lo registra; las réplicas, nunca.
    ...(evidence.poseCount >= 2 ? [fraseDeMuestreoTraducida(evidence.conformersGenerated, t)] : []),
    t("pr_ev_overview_transfer"),
  ];
  const protocol = result.docking_protocol;
  const requestedConformers = protocol?.conformers_requested;
  const generatedConformers = protocol?.conformers_generated;
  const hasConformerCounts =
    typeof requestedConformers === "number" &&
    typeof generatedConformers === "number";
  const peptideTransfer = result.ligand_state?.peptide_transfer;
  const protocolFacts = [
    protocol?.engine ?? null,
    typeof protocol?.exhaustiveness === "number"
      ? t("pr_ev_protocol_exhaustiveness", { value: protocol.exhaustiveness })
      : null,
    typeof protocol?.num_poses === "number"
      ? `${protocol.num_poses} ${t(protocol.num_poses === 1 ? "pr_ev_protocol_pose_one" : "pr_ev_protocol_pose_many")}`
      : null,
    typeof protocol?.seed === "number"
      ? t("pr_ev_protocol_seed", { value: protocol.seed })
      : null,
  ].filter((fact): fact is string => Boolean(fact));

  const legacyReservations = reservations.filter(item => item.id.startsWith("notice-") && item.status === "not_evaluated");
  const prominentReservations = reservations.filter(item => !legacyReservations.includes(item));

  if (provenanceOnly) return <section className={readingStyles.provenance} aria-labelledby={`${summaryId}-title`} data-run-provenance="true">
    <h4 id={`${summaryId}-title`}>{t("ux_provenance_title")}</h4>
    <p className={readingStyles.provenanceIntro}>{t("ux_provenance_scope")}</p>
        <div className="min-w-0">
          <div className="mt-6 border-t border-white/[0.07] pt-5" aria-labelledby={`${summaryId}-protocol`}>
            <p className={readingStyles.provenanceIntro}>{t("pn_identidad_sellada")}</p>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="min-w-0 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
                <p className="font-sans text-sm font-bold uppercase tracking-[0.16em] text-zinc-300">{t("pr_ev_exact_receptor")}</p>
                {result.receptor_sha256 ? (
                  <details className="mt-2 min-w-0">
                    <summary className="cursor-pointer break-all font-sans text-sm text-emerald-800 dark:text-emerald-200 marker:text-zinc-400">
                      sha256:{result.receptor_sha256.slice(0, 16)}…
                    </summary>
                    <code className="mt-2 block break-all rounded-md bg-black/25 p-2 font-mono text-sm leading-6 text-zinc-300">
                      {result.receptor_sha256}
                    </code>
                  </details>
                ) : (
                  <p className="mt-2 text-base leading-6 text-amber-800 dark:text-amber-200 font-sans">{t("pn_no_registrado_corrida")}</p>
                )}
                <p className="mt-2 text-base leading-6 text-zinc-300 font-sans">
                  {result.receptor_path
                    ? t("auto_396af15df54e")
                    : t("auto_7d87ae35f871")}
                </p>
              </div>

              <div className="min-w-0 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
                <p className="font-sans text-sm font-bold uppercase tracking-[0.16em] text-zinc-300">{t("pr_ev_protocol_executed")}</p>
                {protocol ? (
                  <>
                    <p className="mt-2 text-base font-bold text-zinc-200 font-sans leading-6">
                      {hasConformerCounts
                        ? t("pr_ev_protocol_conformers", {
                            generated: generatedConformers,
                            requested: requestedConformers,
                          })
                        : t("auto_c359f0cd7a14")}
                    </p>
                    <p className="mt-1 break-words text-base leading-6 text-zinc-300 font-sans">
                      {protocolFacts.length > 0 ? protocolFacts.join(" · ") : t("auto_f2cfe47391ae")}
                    </p>
                    {(protocol.conformer_warnings?.length ?? 0) > 0 && (
                      <p className="mt-2 text-base leading-6 text-amber-800 dark:text-amber-200 font-sans">
                        {protocol.conformer_warnings!.length} {t("auto_6cb48f8ad846")}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="mt-2 text-base leading-6 text-amber-800 dark:text-amber-200 font-sans">{t("pn_no_registrado_corrida")}</p>
                )}
              </div>
            </div>
          </div>

          <details className="mt-5 border-t border-white/10 pt-2">
            <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">{t("ux_assumptions_limits")} · {evidence.assumptions.length + evidence.uncertainties.length}</summary>
          <div className="mt-6 grid gap-6 border-t border-white/[0.07] pt-5 md:grid-cols-2">
            <div className="min-w-0">
              <p className="font-sans text-sm font-bold uppercase tracking-[0.16em] text-zinc-300">{t("pr_ev_assumptions_registered")}</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-zinc-300">
                {evidence.assumptions.map((assumption) => (
                  <li key={assumption} className="flex gap-2"><span className="text-zinc-700" aria-hidden="true">—</span><span>{assumption}</span></li>
                ))}
              </ul>
            </div>
            <div className="min-w-0">
              <p className="flex items-center gap-2 font-sans text-sm font-bold uppercase tracking-[0.16em] text-amber-800 dark:text-amber-300">
                <AlertTriangle size={14} aria-hidden="true" /> {t("se_dec_uncertainties")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-800 dark:text-amber-100">
                {evidence.uncertainties.map((uncertainty) => (
                  <li key={uncertainty} className="flex gap-2"><span className="text-amber-500/50" aria-hidden="true">—</span><span>{uncertainty}</span></li>
                ))}
              </ul>
              {evidence.uncertainties.length === 0 && (
                <p className="mt-3 text-base leading-6 text-zinc-300 font-sans">{t("pn_sin_incertidumbres")}</p>
              )}
            </div>
          </div>
          </details>
        <details className="mt-6 border-t border-white/10 pt-3">
          <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">{t("ux_dimensions")}</summary>
          <div className="divide-y divide-white/10">
            {evidence.dimensions.map((dimension) => (
              <details key={dimension.id} className="group/dimension min-w-0">
                <summary className="flex min-h-14 cursor-pointer list-none items-center gap-3 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 [&::-webkit-details-marker]:hidden">
                  <span className={`shrink-0 ${CHECK_STYLES[dimension.status]}`}>
                    <StatusIcon status={dimension.status} size={18} />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                    <span className="text-sm font-semibold text-zinc-100">{dimension.label}</span>
                    <span className={`text-sm ${CHECK_STYLES[dimension.status]}`}>{dimension.statusLabel}</span>
                  </span>
                  <ChevronDown size={18} className="shrink-0 text-zinc-400 transition-transform group-open/dimension:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
                </summary>
                <p className="break-words pb-4 pl-7 text-base leading-6 text-zinc-300 font-sans">{dimension.detail}</p>
              </details>
            ))}
          </div>
        </details>
        </div>
  </section>;

  if (compact && reading.enabled) {
    const posesRecorded = Array.isArray(result.docking_poses) ? result.docking_poses.length
      : typeof result.structural_evidence?.poses_produced === "number" ? result.structural_evidence.poses_produced : null;
    const evaluated = result.structural_evidence?.poses_evaluated;
    const produced = result.structural_evidence?.poses_produced;
    return <section data-evidence-summary="true" aria-labelledby={summaryId} className={readingStyles.overview}>
      <div className={readingStyles.overviewHeader}>
        <h2 id={summaryId}>{t("rr_what_obtained")}</h2>
        <div className={readingStyles.overviewDecision}>
          <span className={readingStyles.overviewStatus} data-status={summaryStatus}><StatusIcon status={statusIcon}/>{t(`pr_ev_status_${summaryStatus === "ready" ? "available" : summaryStatus}`)}</span>
          <p className={readingStyles.nextAction}>{evidence.nextAction.status === "abstain" ? evidence.nextAction.detail : summaryStatus === "review" ? t("pr_ev_overview_review") : t("pr_ev_overview_available")}</p>
        </div>
      </div>
      <dl className={readingStyles.facts}>
        <div className={readingStyles.fact}><dt>{t("rr_poses_label")}</dt><dd>{posesRecorded ?? t("rr_not_recorded")}</dd></div>
        <div className={readingStyles.fact}><dt>{t("rr_vina_label")}</dt><dd>{typeof result.affinity_kcal === "number" && Number.isFinite(result.affinity_kcal) ? `${result.affinity_kcal.toFixed(2)} kcal/mol` : t("rr_not_recorded")}</dd><small>{t("ux_vina_scope")}</small></div>
        <div className={readingStyles.fact}><dt>{t("rr_physical_label")}</dt><dd>{typeof evaluated === "number" && typeof produced === "number" ? `${evaluated} / ${produced}` : t("rr_not_recorded")}</dd><small>{t("rr_physical_scope")} · {evidence.physicalValidity.label}</small></div>
      </dl>
      <ReadingHelp area="overview"/>
      {reservations.length > 0 && <ReadingReservations items={prominentReservations} legacy={legacyReservations} onOpenPhysicalControls={onOpenPhysicalControls}/>}
      <p className={readingStyles.limits}>{limits.join(" · ")}</p>
      {peptideTransfer && <p className={readingStyles.limits}>{t("pr_pep_experimental_aviso")} · {peptideTransfer.status === "completed" ? t("pr_ev_completed") : t("auto_12653c32366a")}</p>}
      <p className={readingStyles.scope}>{t("pr_ev_overview_scope")} · {t("rr_run_identity")}: <span className="font-mono break-words">{result.task_id ?? t("pn_no_registrado_corrida")}</span></p>
      
    </section>;
  }

  if (compact) return <section aria-labelledby={summaryId} className="min-w-0 space-y-4 border-b border-white/10 pb-6">
    <div className="flex flex-wrap items-baseline justify-between gap-3">
      <div><p className="mb-1 font-mono text-sm text-zinc-400">{result.task_id ?? t("pn_no_registrado_corrida")}</p><h2 id={summaryId} className="font-display text-2xl font-semibold text-zinc-100">{t("pr_ev_overview_title")}</h2></div>
      <span className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 text-sm font-semibold ${STATUS_STYLES[summaryStatus]}`}><StatusIcon status={statusIcon} />{t(`pr_ev_status_${summaryStatus === "ready" ? "available" : summaryStatus}`)}</span>
    </div>
    <p className="max-w-[85ch] text-base leading-6 text-zinc-300">{evidence.nextAction.status === "abstain" ? evidence.nextAction.detail : summaryStatus === "review" ? t("pr_ev_overview_review") : t("pr_ev_overview_available")}</p>
    <div className="flex flex-wrap items-baseline gap-x-5 gap-y-2 text-sm text-zinc-300"><InsigniaDelCatalogo target={target} corrida={result} />{recordedFacts.map(fact => <span key={fact}>{fact}</span>)}{result.affinity_kcal != null && <span className="font-mono">Vina: {result.affinity_kcal.toFixed(2)} kcal/mol</span>}</div>
    {reservations.length > 0 && <div className={`border-l-2 px-4 py-2 ${NEXT_ACTION_STYLES[evidence.nextAction.status === "abstain" ? "abstain" : "review"]}`}>
      <h3 className="text-sm font-semibold">{t("pr_ev_overview_reservations")}</h3>
      {prominentReservations.length > 0 && <ul className="mt-2 space-y-2">{prominentReservations.map(item => <li key={item.id} className="text-sm leading-6 text-zinc-200"><span className="font-semibold">{item.label}: </span>{item.detail}{item.id === "physical" && onOpenPhysicalControls && <button type="button" onClick={onOpenPhysicalControls} className="ml-3 min-h-11 underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-400">{t("pn_revisar_controles")}</button>}</li>)}</ul>}
      {legacyReservations.length > 0 && <details className="mt-3 border-t border-current/15 pt-1">
        <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-400">{t(legacyReservations.length === 1 ? "rx_heredados_one" : "rx_heredados_count", {count: legacyReservations.length})}</summary>
        <p className="mb-3 text-sm leading-6 text-zinc-300">{t("rx_heredados_desc")}</p>
        <ul className="space-y-3 pb-3">{legacyReservations.map(item => <li key={item.id} className="text-sm leading-6 text-zinc-200">{item.detail}</li>)}</ul>
      </details>}
    </div>}
    <p className="text-sm leading-6 text-zinc-400">{limits.join(" · ")}</p>
    {peptideTransfer && <p className="text-sm leading-6 text-amber-300">{t("pr_pep_experimental_aviso")} · {peptideTransfer.status === "completed" ? t("pr_ev_completed") : t("auto_12653c32366a")}</p>}
    <p className="text-sm leading-6 text-zinc-400">{t("pr_ev_overview_scope")}</p>
  </section>;

  return (
    <section className="border-b border-white/[0.07] pb-6" aria-labelledby={summaryId}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={summaryId} className="font-display text-2xl font-bold tracking-tight text-white">
            {t("pr_ev_overview_title")}
          </h2>
          <InsigniaDelCatalogo pdbId={target?.pdb_id} target={target} corrida={result} />
        </div>
        <span className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 text-sm font-semibold ${STATUS_STYLES[summaryStatus]}`}>
          <StatusIcon status={statusIcon} />
          {t(`pr_ev_status_${summaryStatus === "ready" ? "available" : summaryStatus}`)}
        </span>
      </div>
      <p className="mt-2 text-base leading-6 text-zinc-300 font-sans">
        {evidence.nextAction.status === "abstain" ? evidence.nextAction.detail
          : summaryStatus === "review" ? t("pr_ev_overview_review") : t("pr_ev_overview_available")}
      </p>

      {reservations.length > 0 && (
        <div className={`mt-5 rounded-xl border px-4 py-4 sm:px-5 ${NEXT_ACTION_STYLES[evidence.nextAction.status === "abstain" ? "abstain" : "review"]}`}>
          <h3 className="text-base font-bold">{t("pr_ev_overview_reservations")}</h3>
          <ul className="mt-2 divide-y divide-white/10">
            {reservations.map((item) => (
              <li key={item.id} className="flex min-w-0 gap-3 py-3">
                <span className={`mt-0.5 shrink-0 ${CHECK_STYLES[item.status]}`}>
                  <StatusIcon status={item.status} size={20} />
                </span>
                <div className="min-w-0">
                  <p className="text-base font-semibold text-zinc-100 font-sans leading-6">{item.label}</p>
                  <p className="mt-1 break-words text-base leading-6 text-zinc-200 font-sans">{item.detail}</p>
                  {item.id === "physical" && onOpenPhysicalControls && (
                    <button type="button" onClick={onOpenPhysicalControls}
                      className="mt-3 inline-flex min-h-11 items-center rounded-lg border border-current/30 px-3 py-2 text-sm font-semibold transition-colors hover:bg-white/[0.07] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300">
                      {t("pn_revisar_controles")}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.025] p-4 sm:px-5">
        <h3 className="text-base font-bold text-zinc-100">{t("pr_ev_overview_recorded")}</h3>
        {recordedFacts.length > 0 ? (
          <ul className="mt-3 grid gap-3 md:grid-cols-3">
            {recordedFacts.map((fact) => (
              <li key={fact} className="flex min-w-0 items-start gap-2.5 text-base leading-6 text-zinc-200 font-sans">
                <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-emerald-800 dark:text-emerald-300" aria-hidden="true" />
                <span>{fact}</span>
              </li>
            ))}
          </ul>
        ) : <p className="mt-2 text-base leading-6 text-zinc-300 font-sans">{t("pr_ev_overview_no_evidence")}</p>}
      </div>

      <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.025] p-4 sm:px-5">
        <h3 className="text-base font-bold text-zinc-100">{t("pr_ev_overview_limits")}</h3>
        <ul className="mt-3 grid gap-3 md:grid-cols-2">
          {limits.map((limit) => (
            <li key={limit} className="flex min-w-0 items-start gap-2.5 text-base leading-6 text-zinc-300 font-sans">
              <CircleDashed size={18} className="mt-1 shrink-0 text-zinc-400" aria-hidden="true" />
              <span>{limit}</span>
            </li>
          ))}
        </ul>
      </div>

      {peptideTransfer && (
        <div
          className={`mt-6 rounded-xl border p-4 ${peptideTransfer.status === "completed" ? "border-emerald-500/25 bg-emerald-500/[0.05]" : "border-amber-500/25 bg-amber-500/[0.05]"}`}
          role="status"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-sans text-sm font-bold uppercase tracking-[0.16em] text-zinc-300">
              {t("auto_26ab89fd58f1")}
            </p>
            <p data-testid="peptido-experimental" className="basis-full text-base leading-6 text-amber-800 dark:text-amber-300 font-sans">
              {t("pr_pep_experimental_aviso")}
            </p>
            <span className={`font-sans text-sm font-bold uppercase tracking-wider ${peptideTransfer.status === "completed" ? "text-emerald-800 dark:text-emerald-300" : "text-amber-800 dark:text-amber-300"}`}>
              {peptideTransfer.status === "completed" ? t("pr_ev_completed") : t("auto_12653c32366a")}
            </span>
          </div>
          {peptideTransfer.status === "completed" ? (
            <p className="mt-2 text-base leading-6 text-zinc-400 font-sans">
              {t("auto_887c159b9e2f")} {peptideTransfer.coordinates_transferred ?? 0} {t("auto_7f2537d04d9e")} {peptideTransfer.coordinates_completed ?? 0} {t("auto_c0a10228aed3")} {peptideTransfer.completion_method ?? t("auto_a6c6215f575a")}.
            </p>
          ) : (
            <p className="mt-2 text-base leading-6 text-amber-800 dark:text-amber-100 font-sans">
              {t("auto_632d94f6b658")}{peptideTransfer.failure_code ? ` (${peptideTransfer.failure_code})` : ""}{t("auto_dc0b31771c0b")}
            </p>
          )}
        </div>
      )}
      <details className="group/evidence mt-5 min-w-0 rounded-xl border border-white/10 bg-white/[0.025]">
        <summary className="flex min-h-16 cursor-pointer list-none items-center gap-3 rounded-xl p-4 sm:px-5 hover:bg-white/[0.025] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 [&::-webkit-details-marker]:hidden">
          <span className="min-w-0 flex-1">
            <span className="block text-base font-bold text-zinc-100">{t("pr_ev_overview_details")}</span>
            <span className="mt-1 block text-sm leading-6 text-zinc-300">{t("pr_ev_overview_details_description")}</span>
          </span>
          <span className="hidden text-sm text-zinc-300 sm:block">{t("pr_ev_overview_areas", { count: evidence.dimensions.length })}</span>
          <ChevronDown size={20} className="shrink-0 text-purple-300 transition-transform group-open/evidence:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
        </summary>
        <div className="min-w-0 border-t border-white/10 px-4 pb-5 sm:px-5">
          <div className="divide-y divide-white/10">
            {evidence.dimensions.map((dimension) => (
              <details key={dimension.id} className="group/dimension min-w-0">
                <summary className="flex min-h-14 cursor-pointer list-none items-center gap-3 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 [&::-webkit-details-marker]:hidden">
                  <span className={`shrink-0 ${CHECK_STYLES[dimension.status]}`}>
                    <StatusIcon status={dimension.status} size={18} />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                    <span className="text-sm font-semibold text-zinc-100">{dimension.label}</span>
                    <span className={`text-sm ${CHECK_STYLES[dimension.status]}`}>{dimension.statusLabel}</span>
                  </span>
                  <ChevronDown size={18} className="shrink-0 text-zinc-400 transition-transform group-open/dimension:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
                </summary>
                <p className="break-words pb-4 pl-7 text-base leading-6 text-zinc-300 font-sans">{dimension.detail}</p>
              </details>
            ))}
          </div>
          <div className="mt-6 border-t border-white/[0.07] pt-5" aria-labelledby={`${summaryId}-protocol`}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 id={`${summaryId}-protocol`} className="font-sans text-sm font-bold uppercase tracking-[0.14em] text-zinc-300">
                {t("pr_ev_reproducible_provenance")}
              </h3>
              <p className="text-base leading-6 text-zinc-300 font-sans">{t("pn_identidad_sellada")}</p>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="min-w-0 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
                <p className="font-sans text-sm font-bold uppercase tracking-[0.16em] text-zinc-300">{t("pr_ev_exact_receptor")}</p>
                {result.receptor_sha256 ? (
                  <details className="mt-2 min-w-0">
                    <summary className="cursor-pointer break-all font-sans text-sm text-emerald-800 dark:text-emerald-200 marker:text-zinc-400">
                      sha256:{result.receptor_sha256.slice(0, 16)}…
                    </summary>
                    <code className="mt-2 block break-all rounded-md bg-black/25 p-2 font-mono text-sm leading-6 text-zinc-300">
                      {result.receptor_sha256}
                    </code>
                  </details>
                ) : (
                  <p className="mt-2 text-base leading-6 text-amber-800 dark:text-amber-200 font-sans">{t("pn_no_registrado_corrida")}</p>
                )}
                <p className="mt-2 text-base leading-6 text-zinc-300 font-sans">
                  {result.receptor_path
                    ? t("auto_396af15df54e")
                    : t("auto_7d87ae35f871")}
                </p>
              </div>

              <div className="min-w-0 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
                <p className="font-sans text-sm font-bold uppercase tracking-[0.16em] text-zinc-300">{t("pr_ev_protocol_executed")}</p>
                {protocol ? (
                  <>
                    <p className="mt-2 text-base font-bold text-zinc-200 font-sans leading-6">
                      {hasConformerCounts
                        ? t("pr_ev_protocol_conformers", {
                            generated: generatedConformers,
                            requested: requestedConformers,
                          })
                        : t("auto_c359f0cd7a14")}
                    </p>
                    <p className="mt-1 break-words text-base leading-6 text-zinc-300 font-sans">
                      {protocolFacts.length > 0 ? protocolFacts.join(" · ") : t("auto_f2cfe47391ae")}
                    </p>
                    {(protocol.conformer_warnings?.length ?? 0) > 0 && (
                      <p className="mt-2 text-base leading-6 text-amber-800 dark:text-amber-200 font-sans">
                        {protocol.conformer_warnings!.length} {t("auto_6cb48f8ad846")}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="mt-2 text-base leading-6 text-amber-800 dark:text-amber-200 font-sans">{t("pn_no_registrado_corrida")}</p>
                )}
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-6 border-t border-white/[0.07] pt-5 md:grid-cols-2">
            <div className="min-w-0">
              <p className="font-sans text-sm font-bold uppercase tracking-[0.16em] text-zinc-300">{t("pr_ev_assumptions_registered")}</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-zinc-300">
                {evidence.assumptions.map((assumption) => (
                  <li key={assumption} className="flex gap-2"><span className="text-zinc-700" aria-hidden="true">—</span><span>{assumption}</span></li>
                ))}
              </ul>
            </div>
            <div className="min-w-0">
              <p className="flex items-center gap-2 font-sans text-sm font-bold uppercase tracking-[0.16em] text-amber-800 dark:text-amber-300">
                <AlertTriangle size={14} aria-hidden="true" /> {t("se_dec_uncertainties")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-800 dark:text-amber-100">
                {evidence.uncertainties.map((uncertainty) => (
                  <li key={uncertainty} className="flex gap-2"><span className="text-amber-500/50" aria-hidden="true">—</span><span>{uncertainty}</span></li>
                ))}
              </ul>
              {evidence.uncertainties.length === 0 && (
                <p className="mt-3 text-base leading-6 text-zinc-300 font-sans">{t("pn_sin_incertidumbres")}</p>
              )}
            </div>
          </div>
        </div>
      </details>
      <p className="mt-4 text-base leading-6 text-zinc-300 font-sans">{t("pr_ev_overview_scope")}</p>
    </section>
  );
}
