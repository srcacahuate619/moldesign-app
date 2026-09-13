"use client";

// =====================================================================
// StructuralEvidencePanel — generación, selección y validación de poses
// =====================================================================
//
// QUÉ OCUPA ESTE HUECO. La pestaña Evaluación enseñaba una afinidad y una
// lista de poses, y sobre la validación física decía literalmente «esta versión
// no ejecuta un validador geométrico de poses en producción». Desde P0-A y P0-B
// eso es falso: el validador corre, el selector corre, y los dos persisten un
// contrato. Este bloque los enseña.
//
// LAS CUATRO PREGUNTAS, EN ORDEN. Generación (qué salió), Selección (cuál se
// recomienda), Controles físicos (qué se comprobó) y Decisión (qué es
// justificable hacer). El orden importa: la recomendación no se puede leer sin
// saber si la pose que sugiere pasa los controles.
//
// LO QUE ESTE PANEL NO HACE:
//
//   · no puntúa — no hay ninguna nota 0-100, ni aquí ni en el detalle;
//   · no sustituye — si la pose sugerida falla, se declara revisión y se
//     listan las que pasan, sin elegir ninguna;
//   · no rellena — lo que la corrida no guardó se dice «no informado»;
//   · no promete — el próximo paso habla del protocolo, nunca de actividad;
//   · no navega a otra pantalla — el detalle se abre en este mismo expediente.
//
// COLOR NUNCA SOLO. Cada estado se dice con icono Y con texto. Un panel que
// distinga «superado» de «fallido» únicamente por verde y rojo no lo distingue
// para quien no separa esos dos colores.

import { useEffect, useId, useRef } from "react";
import {
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  CheckCircle2,
  CircleSlash,
  Layers,
  ListChecks,
  Loader2,
  ShieldAlert,
  ShieldQuestion,
  Target as TargetIcon,
} from "lucide-react";

import { useLanguage } from "../../../context/LanguageContext";
import { nombreDeControl } from "../../../lib/controlesFisicos";
import { Ayuda } from "../../ui/Ayuda";
import {
  deriveStructuralEvidence,
  type EvaluationResultWithEvidence,
  type PhysicalStatus,
  type SelectionStatus,
  type StructuralEvidenceView,
} from "../../../lib/structuralEvidence";

// ── Estados: icono + texto + color, en ese orden de importancia ──────

const PHYSICAL_STYLE: Record<PhysicalStatus, { cls: string; text: string; key: string }> = {
  passed: { cls: "border-emerald-500/30 text-emerald-300", text: "text-emerald-300", key: "se_phys_passed" },
  failed: { cls: "border-red-500/40 text-red-300", text: "text-red-300", key: "se_phys_failed" },
  review: { cls: "border-amber-500/40 text-amber-300", text: "text-amber-300", key: "se_phys_review" },
  not_evaluated: { cls: "border-surface-600 text-zinc-400", text: "text-zinc-400", key: "se_phys_not_evaluated" },
};

const SELECTION_STYLE: Record<SelectionStatus, { cls: string; key: string }> = {
  selected: { cls: "border-emerald-500/30 text-emerald-300", key: "se_sel_selected" },
  abstained: { cls: "border-amber-500/40 text-amber-300", key: "se_sel_abstained" },
  unavailable: { cls: "border-surface-600 text-zinc-400", key: "se_sel_unavailable" },
  error: { cls: "border-red-500/40 text-red-300", key: "se_sel_error" },
};

function PhysicalIcon({ status, className = "h-3.5 w-3.5 shrink-0" }: { status: PhysicalStatus; className?: string }) {
  if (status === "passed") return <CheckCircle2 className={className} aria-hidden="true" />;
  if (status === "failed") return <ShieldAlert className={className} aria-hidden="true" />;
  if (status === "review") return <AlertTriangle className={className} aria-hidden="true" />;
  return <CircleSlash className={className} aria-hidden="true" />;
}

function SelectionIcon({ status }: { status: SelectionStatus }) {
  const className = "h-3.5 w-3.5 shrink-0";
  if (status === "selected") return <CheckCircle2 className={className} aria-hidden="true" />;
  if (status === "abstained") return <ShieldQuestion className={className} aria-hidden="true" />;
  if (status === "error") return <ShieldAlert className={className} aria-hidden="true" />;
  return <CircleSlash className={className} aria-hidden="true" />;
}

function Badge({ cls, children }: { cls: string; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${cls}`}
    >
      {children}
    </span>
  );
}

/** Un dato con su etiqueta. `value` nulo se dice «no informado», no se omite. */
function Fact({
  label,
  value,
  title,
  ayuda,
}: {
  label: string;
  value: string | null;
  title?: string;
  /** El "?" opcional. Sólo lo llevan los datos que se malinterpretan. */
  ayuda?: React.ReactNode;
}) {
  const { t } = useLanguage();
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
        {label}
        {ayuda}
      </dt>
      <dd
        className={`truncate text-xs ${value == null ? "text-zinc-500 italic" : "text-zinc-200"}`}
        title={title ?? value ?? undefined}
      >
        {value ?? t("se_not_reported")}
      </dd>
    </div>
  );
}

function SectionHeading({
  id,
  index,
  title,
  lead,
  icon,
  badge,
}: {
  id: string;
  index: number;
  title: string;
  lead: string;
  icon: React.ReactNode;
  badge: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div className="min-w-0">
        <h3 id={id} className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-100">
          <span className="font-mono text-[10px] text-zinc-600">{index}</span>
          <span className="text-zinc-500">{icon}</span>
          {title}
        </h3>
        <p className="mt-1 max-w-[70ch] text-xs leading-5 text-zinc-500">{lead}</p>
      </div>
      {badge}
    </div>
  );
}

const num = (value: number | null, digits: number): string | null =>
  value == null ? null : value.toFixed(digits);

const shortHash = (hash: string | null): string | null =>
  hash ? `${hash.slice(0, 12)}…` : null;

/**
 * Detalle físico de una sola pose. Vive junto a "Poses generados" para que el
 * usuario pueda partir de la coordenada que está examinando, sin repetir esta
 * lista completa dentro del expediente narrativo.
 */
export function PosePhysicalDetails({
  result,
  rank,
}: {
  readonly result: EvaluationResultWithEvidence | null;
  readonly rank: number | null;
}) {
  const { t } = useLanguage();
  const physical = deriveStructuralEvidence(result).physical;
  const pose = rank == null ? null : physical.poses.find((entry) => entry.rank === rank) ?? null;
  const reasonText = (code: string): string => {
    const key = `se_reason_${code}`;
    const text = t(key);
    return text === key ? code : text;
  };
  const checkText = (code: string): string => nombreDeControl(t, code);

  return (
    <section
      aria-labelledby="pose-physical-detail-title"
      className="rounded-xl border border-white/[0.08] bg-black/20 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 id="pose-physical-detail-title" className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-200">
            {t("se_phys_per_pose")}{rank == null ? "" : ` #${rank}`}
          </h4>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">
            {t("se_s3_lead")}
          </p>
        </div>
        {pose && (
          <Badge cls={PHYSICAL_STYLE[pose.status].cls}>
            <PhysicalIcon status={pose.status} />
            {t(PHYSICAL_STYLE[pose.status].key)}
          </Badge>
        )}
      </div>

      {!pose ? (
        <p className="mt-3 text-xs leading-relaxed text-zinc-400">
          {t("se_phys_not_evaluated_meaning")}
        </p>
      ) : (
        <>
          <dl className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
            <Fact label={t("se_cmp_affinity")} value={pose.affinity == null ? null : `${num(pose.affinity, 2)} kcal/mol`} />
            <Fact label={t("se_phys_engine")} value={pose.engine} title={pose.engine ?? undefined} />
            <Fact
              label={t("se_phys_counts")}
              value={`${pose.passedCount} ${t("se_phys_count_pass")} · ${pose.failedCount} ${t("se_phys_count_fail")} · ${pose.notEvaluatedCount} ${t("se_phys_count_skip")}`}
            />
            {pose.reasonCode && (
              <Fact label={t("se_phys_reason")} value={reasonText(pose.reasonCode)} title={pose.reasonCode} />
            )}
          </dl>
          {pose.failingChecks.length > 0 ? (
            <p className="mt-3 break-words text-xs leading-relaxed text-red-300/85">
              <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                {t("se_phys_failing")}:
              </span>{" "}
              {/* El identificador de PoseBusters se conserva en el `title`: es
                  el que permite reproducir el control. Lo que se lee es la
                  frase; lo que se audita, el código. */}
              {pose.failingChecks.map((code, i) => (
                <span key={code}>
                  {i > 0 && ", "}
                  <span title={code}>{checkText(code)}</span>
                </span>
              ))}
            </p>
          ) : pose.status === "passed" ? (
            <p className="mt-3 text-xs leading-relaxed text-zinc-500">{t("se_phys_none_failing")}</p>
          ) : null}
          {pose.detail && <p className="mt-2 break-words text-xs leading-relaxed text-zinc-400">{pose.detail}</p>}
        </>
      )}
    </section>
  );
}

export interface StructuralEvidencePanelProps {
  readonly result: EvaluationResultWithEvidence | null;
  /** La corrida sigue en marcha o el resultado aún no se ha releído. */
  readonly loading?: boolean;
  /** Fallo al recuperar el resultado. No es un fallo de la evidencia. */
  readonly error?: string | null;
  /** Solicitud desde el resumen global para abrir la evidencia que lo sustenta. */
  readonly physicalFocusRequest?: number;
  /** Lleva al detalle físico de una pose desde la pestaña de estructura. */
  readonly onOpenPoseDetails?: (rank: number | null) => void;
  /** Variante compacta para integraciones antiguas; la evaluación usa el comparador dedicado. */
  readonly showInlineComparison?: boolean;
  /** Abre una comparación visual de dos coordenadas reales de esta corrida. */
  readonly onComparePoses?: (leftRank: number, rightRank: number) => void;
}

export function StructuralEvidencePanel({
  result,
  loading = false,
  error = null,
  physicalFocusRequest = 0,
  onOpenPoseDetails,
  showInlineComparison = false,
  onComparePoses,
}: StructuralEvidencePanelProps) {
  const { t } = useLanguage();
  const baseId = useId();
  const physicalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (physicalFocusRequest < 1) return;
    const frame = window.requestAnimationFrame(() => {
      physicalRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [physicalFocusRequest]);

  /**
   * Traduce un código de razón del backend, y si no está en el diccionario
   * devuelve el código crudo. Sin esto, un código nuevo se imprimiría como
   * `se_reason_LO_QUE_SEA`, que no le dice nada a nadie.
   */
  const reasonText = (code: string): string => {
    const key = `se_reason_${code}`;
    const text = t(key);
    return text === key ? code : text;
  };

  const view: StructuralEvidenceView = deriveStructuralEvidence(result);
  const { generation, selection, physical, decision, comparison } = view;

  const nextStepKey =
    decision.nextStep === "abstain"
      ? "se_dec_next_abstain"
      : decision.nextStep === "review"
        ? "se_dec_next_review"
        : "se_dec_next_proceed";
  const nextStepStyle =
    decision.nextStep === "abstain"
      ? "border-red-500/30 bg-red-500/[0.06] text-red-100"
      : decision.nextStep === "review"
        ? "border-amber-500/30 bg-amber-500/[0.06] text-amber-100"
        : "border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-100";

  const detailRank =
    selection.suggestedRank ??
    selection.vinaTop1Rank ??
    physical.poses.find((pose) => pose.rank != null)?.rank ??
    null;
  const comparisonPair = (() => {
    const left = comparison.find((row) => row.isVinaTop1) ?? comparison[0];
    if (!left) return null;
    const right =
      comparison.find((row) => row.isSuggested && row.rank !== left.rank) ??
      comparison.find((row) => row.isAlternative && row.rank !== left.rank) ??
      comparison.find((row) => row.rank !== left.rank);
    return right ? { leftRank: left.rank, rightRank: right.rank } : null;
  })();

  return (
    <section
      aria-labelledby={`${baseId}-title`}
      className="w-full max-w-[1600px] border-y border-surface-800 bg-surface-950/60 px-4 py-4 sm:px-6"
    >
      <div className="min-w-0">
        <h2 id={`${baseId}-title`} className="font-display text-lg font-bold tracking-tight text-zinc-100">
          {t("se_title")}
        </h2>
        <p className="mt-1 max-w-[78ch] text-xs leading-relaxed text-zinc-500">{t("se_subtitle")}</p>
        <p className="mt-1 max-w-[78ch] text-xs leading-relaxed text-zinc-600">{t("se_disclaimer")}</p>
      </div>

      {/* ── Estados de carga y error: la evidencia no se inventa mientras
             tanto, y un fallo de lectura no se disfraza de «no evaluada». ── */}
      {loading && (
        <p role="status" className="mt-4 inline-flex items-center gap-2 text-xs text-zinc-400">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          {t("se_loading")}
        </p>
      )}

      {error && (
        <p role="alert" className="mt-4 text-xs leading-relaxed text-amber-300">
          {t("se_error")} {error}
        </p>
      )}

      {!loading && !error && !view.hasAnything && (
        <p role="status" className="mt-4 text-xs leading-relaxed text-zinc-400">
          {t("se_empty")}
        </p>
      )}

      {!loading && !error && view.hasAnything && (
        <>
          {/* ── Corrida antigua: no falló nada, no llegó a ejecutarse ── */}
          {view.isLegacyRun && (
            <div className="mt-4 rounded-md border border-surface-700 bg-surface-900/40 p-3">
              <Badge cls="border-surface-600 text-zinc-400">
                <CircleSlash className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                {t("se_legacy")}
              </Badge>
              <p className="mt-2 max-w-[78ch] text-xs leading-relaxed text-zinc-400">{t("se_legacy_note")}</p>
            </div>
          )}

          {/* ── Resumen compacto: los cuatro estados de un vistazo ────── */}
          {/* ═══ 1. GENERACIÓN ═══════════════════════════════════════ */}
          <div className="mt-5 border-t border-surface-800 pt-4">
            <SectionHeading
              id={`${baseId}-s1`}
              index={1}
              title={t("se_s1_title")}
              lead={t("se_s1_lead")}
              icon={<Layers className="h-3.5 w-3.5" aria-hidden="true" />}
              badge={null}
            />

            {generation.posesProduced === 0 ? (
              <p className="mt-3 text-xs leading-relaxed text-red-300">{t("se_gen_no_poses")}</p>
            ) : (
              <>
                <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
                  <Fact label={t("se_gen_poses")} value={String(generation.posesProduced)} />
                  <Fact
                    label={t("se_gen_affinity")}
                    value={generation.topAffinity == null ? null : `${num(generation.topAffinity, 2)} kcal/mol`}
                    ayuda={
                      <Ayuda titulo={t("ayuda_afinidad_titulo")}>{t("ayuda_afinidad")}</Ayuda>
                    }
                  />
                  <Fact
                    label={t("se_gen_gap")}
                    value={generation.affinityGap == null ? null : `${num(generation.affinityGap, 2)} kcal/mol`}
                  />
                  <Fact label={t("se_gen_seed")} value={generation.seed == null ? null : String(generation.seed)} />
                </dl>
                <p className="mt-2 text-[11px] leading-relaxed text-zinc-600">{t("se_gen_affinity_note")}</p>

                <div id={`${baseId}-s1-detail`} className="mt-3 border-t border-surface-800 pt-3">
                    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-3">
                      <Fact
                        label={t("se_gen_protocol")}
                        value={
                          [generation.engine, generation.vinaVersion].filter(Boolean).join(" · ") || null
                        }
                      />
                      <Fact label={t("se_gen_parser")} value={generation.parsingSource} />
                      <Fact
                        label={t("se_gen_provenance")}
                        value={`${generation.provenancePresent} / ${generation.provenanceTotal}`}
                      />
                      <Fact
                        label={t("se_gen_receptor")}
                        value={generation.receptorSource}
                        title={generation.receptorSource ?? undefined}
                      />
                      <Fact
                        label="SHA-256"
                        value={shortHash(generation.receptorSha256)}
                        title={generation.receptorSha256 ?? undefined}
                      />
                      <Fact label={t("se_gen_conformers")} value={null} />
                    </dl>
                    {!generation.receptorSha256 && (
                      <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">{t("se_gen_receptor_absent")}</p>
                    )}
                    {/* Conformeros y restarts: la corrida no los guarda. Se
                        dice, en vez de rellenarlos con la configuración del
                        caso, que pertenece a otro objeto. */}
                    <p className="mt-2 max-w-[78ch] text-[11px] leading-relaxed text-zinc-600">
                      <span className="text-zinc-500">{t("se_gen_conformers_absent")}.</span>{" "}
                      {t("se_gen_conformers_note")}
                    </p>
                </div>
              </>
            )}
          </div>

          {/* ═══ 2. SELECCIÓN ════════════════════════════════════════ */}
          <div className="mt-5 border-t border-surface-800 pt-4">
            <SectionHeading
              id={`${baseId}-s2`}
              index={2}
              title={t("se_s2_title")}
              lead={t("se_s2_lead")}
              icon={<TargetIcon className="h-3.5 w-3.5" aria-hidden="true" />}
              badge={
                <Badge cls={SELECTION_STYLE[selection.status].cls}>
                  <SelectionIcon status={selection.status} />
                  {t(SELECTION_STYLE[selection.status].key)}
                </Badge>
              }
            />

            <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
              {/* Vina top-1 SIEMPRE, pase lo que pase con el selector. */}
              <Fact
                label={t("se_sel_vina_top1")}
                value={selection.vinaTop1Rank == null ? null : `#${selection.vinaTop1Rank}`}
              />
              <Fact
                label={selection.suggestedRank == null && selection.wouldHaveSuggestedRank != null ? t("se_sel_would_have") : t("se_sel_suggested")}
                value={
                  selection.suggestedRank != null
                    ? `#${selection.suggestedRank}`
                    : selection.wouldHaveSuggestedRank != null
                      ? `#${selection.wouldHaveSuggestedRank}`
                      : null
                }
              />
              <Fact
                ayuda={<Ayuda titulo={t("ayuda_margen_titulo")}>{t("ayuda_margen")}</Ayuda>}
                label={t("se_sel_confidence")}
                value={
                  selection.confidence == null
                    ? null
                    : `${num(selection.confidence, 4)}${
                        selection.abstentionThreshold == null
                          ? ""
                          : ` · ${t("se_sel_threshold")} ${num(selection.abstentionThreshold, 4)}`
                      }`
                }
              />
              <Fact
                label={t("se_sel_model")}
                value={selection.modelName ?? selection.modelVersion}
                title={selection.modelVersion ?? undefined}
              />
            </dl>

            {/* La divergencia no se esconde: es exactamente lo que el lector
                tiene que ver para decidir por su cuenta. */}
            {selection.divergesFromVinaTop1 && (
              <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/[0.06] p-3">
                <p className="flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-300">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {t("se_sel_diverge")}
                </p>
                <p className="mt-1.5 max-w-[78ch] text-xs leading-relaxed text-amber-100/80">
                  {t("se_sel_diverge_note")}
                </p>
              </div>
            )}
            {selection.status === "selected" && !selection.divergesFromVinaTop1 && (
              <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-zinc-400">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" aria-hidden="true" />
                {t("se_sel_agree")}
              </p>
            )}

            {/* Sin recomendación: se dice, y se dice que la referencia es un
                fallback — no un acierto del selector. */}
            {selection.status !== "selected" && (
              <div className="mt-3 rounded-md border border-surface-700 bg-surface-900/40 p-3">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-300">
                  <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-zinc-400">
                    {t("se_sel_no_recommendation")}
                  </span>
                  {selection.isFallback && <span className="text-zinc-400">· {t("se_sel_fallback")}</span>}
                </p>
                {selection.abstentionReason && (
                  <p className="mt-1.5 max-w-[78ch] text-xs leading-relaxed text-zinc-400">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                      {t("se_sel_abstain_reason")}:
                    </span>{" "}
                    {reasonText(selection.abstentionReason)}
                  </p>
                )}
                <p className="mt-1.5 max-w-[78ch] text-[11px] leading-relaxed text-zinc-600">
                  {t("se_sel_fallback_note")}
                </p>
              </div>
            )}

            {(selection.poseScores.length > 0 || selection.warnings.length > 0 || selection.detail) && (
              <div id={`${baseId}-s2-detail`} className="mt-3 border-t border-surface-800 pt-3">
                    {selection.detail && (
                      <p className="max-w-[78ch] text-xs leading-relaxed text-zinc-400">{selection.detail}</p>
                    )}
                    <p className="mt-2 max-w-[78ch] text-[11px] leading-relaxed text-zinc-600">
                      {t("se_sel_confidence_note")}
                    </p>

                    {selection.poseScores.length > 0 && (
                      <div className="mt-3">
                        <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                          {t("se_sel_scores")}
                        </p>
                        <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                          {selection.poseScores.map((entry) => (
                            <li key={entry.rank} className="font-mono text-[11px] text-zinc-300">
                              #{entry.rank} <span className="text-zinc-500">{num(entry.score, 4)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {selection.warnings.length > 0 && (
                      <div className="mt-3">
                        <p className="font-mono text-[10px] uppercase tracking-wider text-amber-300/70">
                          {t("se_sel_warnings")}
                        </p>
                        <ul className="mt-1.5 space-y-1">
                          {selection.warnings.map((warning) => (
                            <li key={warning} className="text-[11px] leading-relaxed text-amber-100/70">
                              {warning}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {selection.modelSha256 && (
                      <p className="mt-3 break-all font-mono text-[10px] text-zinc-600">
                        SHA-256 {selection.modelSha256}
                      </p>
                    )}
              </div>
            )}
          </div>

          {/* ═══ 3. CONTROLES FÍSICOS ════════════════════════════════ */}
          <div ref={physicalRef} className="mt-5 border-t border-surface-800 pt-4">
            <SectionHeading
              id={`${baseId}-s3`}
              index={3}
              title={t("se_s3_title")}
              lead={t("se_s3_lead")}
              icon={<ListChecks className="h-3.5 w-3.5" aria-hidden="true" />}
              badge={
                <span className="inline-flex items-center gap-1.5">
                  <Badge cls={PHYSICAL_STYLE[physical.stageStatus].cls}>
                    <PhysicalIcon status={physical.stageStatus} />
                    {t(PHYSICAL_STYLE[physical.stageStatus].key)}
                  </Badge>
                  <Ayuda titulo={t("ayuda_estados_titulo")}>{t("ayuda_estados")}</Ayuda>
                </span>
              }
            />

            <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-4">
              <Fact
                ayuda={<Ayuda titulo={t("ayuda_cobertura_titulo")}>{t("ayuda_cobertura")}</Ayuda>}
                label={t("se_phys_coverage")}
                value={`${physical.posesEvaluated} / ${physical.posesProduced} ${t("se_phys_poses_unit")}`}
              />
              <Fact label={t("se_phys_engine")} value={physical.engine} title={physical.engine ?? undefined} />
              <Fact
                label={t("se_phys_suggested_status")}
                value={physical.suggestedPoseStatus == null ? null : t(PHYSICAL_STYLE[physical.suggestedPoseStatus].key)}
              />
              {physical.reasonCode && (
                <Fact
                  label={t("se_phys_reason")}
                  value={reasonText(physical.reasonCode)}
                  title={physical.reasonCode}
                />
              )}
            </dl>

            {/* La regla que este sprint no puede romper: si la sugerida no
                está confirmada, se declara revisión y NO se cambia. */}
            {physical.needsReview && (
              <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/[0.06] p-3">
                <p className="flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-300">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {t("se_phys_review")}
                </p>
                <p className="mt-1.5 max-w-[78ch] text-xs leading-relaxed text-amber-100/80">
                  {t("se_phys_review_note")}
                </p>
              </div>
            )}

            {physical.stageStatus === "not_evaluated" && (
              <p className="mt-3 max-w-[78ch] text-xs leading-relaxed text-zinc-400">
                {t("se_phys_absent")} {t("se_phys_not_evaluated_meaning")}
              </p>
            )}
            {physical.stageStatus === "review" && (
              <p className="mt-3 max-w-[78ch] text-[11px] leading-relaxed text-zinc-500">
                {t("se_phys_review_meaning")}
              </p>
            )}

            {physical.poses.length > 0 && onOpenPoseDetails && detailRank != null && (
              <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-surface-800 pt-3">
                <button
                  type="button"
                  onClick={() => onOpenPoseDetails(detailRank)}
                  className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-purple-500/30 bg-purple-500/[0.06] px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-purple-200 transition-colors hover:bg-purple-500/12 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
                >
                  <Layers className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("se_phys_per_pose")} #{detailRank}
                </button>
                <p className="text-[11px] leading-relaxed text-zinc-500">
                  {t("se_phys_open_in_structure")}
                </p>
              </div>
            )}
          </div>

          {/* ═══ 4. DECISIÓN JUSTIFICABLE ════════════════════════════ */}
          <div className="mt-5 border-t border-surface-800 pt-4">
            <SectionHeading
              id={`${baseId}-s4`}
              index={4}
              title={t("se_s4_title")}
              lead={t("se_s4_lead")}
              icon={<ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />}
              badge={
                <Badge
                  cls={
                    decision.nextStep === "abstain"
                      ? "border-red-500/40 text-red-300"
                      : decision.nextStep === "review"
                        ? "border-amber-500/40 text-amber-300"
                        : "border-emerald-500/30 text-emerald-300"
                  }
                >
                  {decision.nextStep === "abstain" ? (
                    <ShieldAlert className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  ) : decision.nextStep === "review" ? (
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  )}
                  {t(nextStepKey)}
                </Badge>
              }
            />

            <div className="mt-3 grid gap-5 md:grid-cols-2">
              <div className="min-w-0">
                <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                  {t("se_dec_established")}
                </p>
                <ul className="mt-2 space-y-1.5">
                  {decision.established.map((code) => (
                    <li key={code} className="flex gap-2 text-xs leading-relaxed text-zinc-300">
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400/70" aria-hidden="true" />
                      <span>{t(`se_ev_${code}`)}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="min-w-0">
                <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-amber-300/70">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {t("se_dec_uncertainties")}
                </p>
                {decision.uncertainties.length > 0 ? (
                  <ul className="mt-2 space-y-1.5">
                    {decision.uncertainties.map((code) => (
                      <li key={code} className="flex gap-2 text-xs leading-relaxed text-amber-100/70">
                        <span className="text-amber-500/50" aria-hidden="true">
                          —
                        </span>
                        <span>{t(`se_unc_${code}`)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs leading-relaxed text-zinc-500">{t("se_dec_no_uncertainties")}</p>
                )}
              </div>
            </div>

            {/* Alternativas: se listan, no se eligen. */}
            <div className="mt-4">
              <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                {t("se_dec_alternatives")}
              </p>
              {decision.alternatives.length > 0 ? (
                <>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {decision.alternatives.map((rank) => (
                      <li key={rank}>
                        <Badge cls="border-emerald-500/30 text-emerald-300">
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />#{rank}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 max-w-[78ch] text-[11px] leading-relaxed text-zinc-600">
                    {t("se_dec_alternatives_note")}
                  </p>
                </>
              ) : (
                <p className="mt-2 text-xs leading-relaxed text-zinc-500">{t("se_dec_no_alternatives")}</p>
              )}
            </div>

            {/* La razón científica completa vive una sola vez: aquí, dentro de
                la decisión. El resumen superior sólo señala el foco y abre
                este detalle, en vez de repetir la misma conclusión. */}
            <div className={`mt-4 rounded-md border p-3 ${nextStepStyle}`}>
              <div className="flex items-start gap-2.5">
                <ArrowRight className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div className="min-w-0">
                  <p className="font-mono text-[10px] font-bold uppercase tracking-wider opacity-70">
                    {t("se_dec_next")}
                  </p>
                  <p className="mt-1 text-xs font-semibold">{t(nextStepKey)}</p>
                  <p className="mt-1.5 max-w-[78ch] text-[11px] leading-relaxed opacity-80">
                    {t(`${nextStepKey}_detail`)}
                  </p>
                  {decision.nextStep === "review" && onOpenPoseDetails && detailRank != null && (
                    <button
                      type="button"
                      onClick={() => onOpenPoseDetails(detailRank)}
                      className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-lg border border-amber-400/35 bg-black/10 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-100 transition-colors hover:bg-black/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-200"
                    >
                      <ListChecks className="h-3.5 w-3.5" aria-hidden="true" />
                      {t("se_phys_per_pose")} #{detailRank}
                    </button>
                  )}
                </div>
              </div>
            </div>

          </div>

          {/* ═══ COMPARADOR: top-1, sugerida y alternativas ══════════ */}
          {showInlineComparison && comparison.length > 0 && (
            <div className="mt-5 border-t border-surface-800 pt-4">
              <div className="min-w-0">
                <h3 className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-100">{t("se_cmp_title")}</h3>
                <p className="mt-1 max-w-[70ch] text-xs leading-5 text-zinc-500">{t("se_cmp_lead")}</p>
              </div>
              {comparisonPair && onComparePoses && (
                <button
                  type="button"
                  onClick={() => onComparePoses(comparisonPair.leftRank, comparisonPair.rightRank)}
                  className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-lg border border-purple-500/30 bg-purple-500/[0.06] px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-purple-200 transition-colors hover:bg-purple-500/12 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
                >
                  <ArrowLeftRight className="h-3.5 w-3.5" aria-hidden="true" />
                  Comparar pose #{comparisonPair.leftRank} y #{comparisonPair.rightRank} en 3D
                </button>
              )}
              <div id={`${baseId}-cmp`} className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[34rem] border-collapse text-xs">
                    <caption className="sr-only">{t("se_cmp_title")}</caption>
                    <thead>
                      <tr className="border-b border-surface-800 text-left font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                        <th scope="col" className="py-2 pr-3 font-normal">
                          {t("se_cmp_rank")}
                        </th>
                        <th scope="col" className="py-2 pr-3 font-normal">
                          {t("se_cmp_affinity")}
                        </th>
                        <th scope="col" className="py-2 pr-3 font-normal">
                          {t("se_cmp_selector")}
                        </th>
                        <th scope="col" className="py-2 pr-3 font-normal">
                          {t("se_cmp_physical")}
                        </th>
                        <th scope="col" className="py-2 font-normal">
                          {t("se_cmp_role")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.map((row) => (
                        <tr key={row.rank} className="border-b border-surface-800 last:border-b-0">
                          <th scope="row" className="py-2 pr-3 text-left font-mono text-zinc-300">
                            #{row.rank}
                          </th>
                          <td className="py-2 pr-3 font-mono text-zinc-400">{num(row.affinity, 2) ?? "—"}</td>
                          <td className="py-2 pr-3 font-mono text-zinc-400">{num(row.selectorScore, 4) ?? "—"}</td>
                          <td className="py-2 pr-3">
                            <span
                              className={`inline-flex items-center gap-1.5 ${PHYSICAL_STYLE[row.physicalStatus].text}`}
                            >
                              <PhysicalIcon status={row.physicalStatus} className="h-3 w-3 shrink-0" />
                              {t(PHYSICAL_STYLE[row.physicalStatus].key)}
                            </span>
                          </td>
                          <td className="py-2">
                            <span className="flex flex-wrap gap-1">
                              {row.isVinaTop1 && (
                                <Badge cls="border-surface-600 text-zinc-300">{t("se_cmp_role_top1")}</Badge>
                              )}
                              {row.isSuggested && (
                                <Badge cls="border-brand-500/40 text-brand-300">{t("se_cmp_role_suggested")}</Badge>
                              )}
                              {row.isAlternative && !row.isSuggested && (
                                <Badge cls="border-emerald-500/30 text-emerald-300">
                                  {t("se_cmp_role_alternative")}
                                </Badge>
                              )}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
