import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleDashed,
  ListChecks,
  ShieldAlert,
} from "lucide-react";
import type { Target } from "../../../lib/api";
import type { EvaluationResult, ValidationResult } from "../../../lib/types";
import {
  deriveEvaluationEvidence,
  deriveEvaluationReadiness,
  type CheckStatus,
  type EvidenceStatus,
} from "../../../lib/evaluationEvidence";

// Hallmark · genre: modern-minimal · macrostructure: Workbench · theme: existing MolDesign · enrichment: none
// Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4 · slop: pass · contrast: pass · responsive: pass

const STATUS_STYLES: Record<EvidenceStatus, string> = {
  ready: "border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-200",
  review: "border-amber-500/25 bg-amber-500/[0.06] text-amber-200",
  incomplete: "border-rose-500/25 bg-rose-500/[0.06] text-rose-200",
};

const CHECK_STYLES: Record<CheckStatus, string> = {
  available: "text-emerald-300",
  review: "text-amber-300",
  missing: "text-rose-300",
  not_evaluated: "text-zinc-400",
};

const NEXT_ACTION_STYLES = {
  proceed: "border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-100",
  review: "border-amber-500/25 bg-amber-500/[0.06] text-amber-100",
  abstain: "border-rose-500/25 bg-rose-500/[0.06] text-rose-100",
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
  const readiness = deriveEvaluationReadiness(smiles, target, validation);

  return (
    <section className="w-full max-w-[1600px] border-y border-zinc-800 bg-zinc-950/55 px-4 py-5 md:px-6" aria-labelledby="evaluation-readiness-title">
      <div className="grid gap-5 lg:grid-cols-[minmax(220px,0.72fr)_minmax(0,1.8fr)] lg:items-start">
        <div className="min-w-0">
          <div className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 font-mono text-xs font-bold uppercase tracking-wider ${STATUS_STYLES[readiness.status]}`}>
            <StatusIcon status={readiness.status === "ready" ? "available" : readiness.status === "review" ? "review" : "missing"} />
            {readiness.label}
          </div>
          <h2 id="evaluation-readiness-title" className="mt-3 font-display text-xl font-bold tracking-tight text-white">
            Preparación de la corrida
          </h2>
          <p className="mt-2 max-w-[58ch] text-sm leading-6 text-zinc-400">{readiness.summary}</p>
        </div>

        <div className="grid min-w-0 gap-x-6 sm:grid-cols-2">
          {readiness.checks.map((check) => (
            <div key={check.id} className="flex min-w-0 gap-3 border-b border-white/[0.07] py-3 first:pt-0 sm:[&:nth-child(2)]:pt-0">
              <span className={`mt-0.5 shrink-0 ${CHECK_STYLES[check.status]}`}>
                <StatusIcon status={check.status} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-bold text-zinc-100">{check.label}</p>
                <p className="mt-1 text-xs leading-5 text-zinc-500">{check.detail}</p>
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
}: {
  result: EvaluationResult;
  target: Target | null;
  /** Lleva al detalle exacto que sustenta una reserva física. */
  onOpenPhysicalControls?: () => void;
}) {
  const evidence = deriveEvaluationEvidence(result, target);
  const statusIcon: CheckStatus = evidence.status === "ready" ? "available" : evidence.status === "review" ? "review" : "missing";
  const physicalNeedsReview = evidence.physicalValidity.status !== "passed";
  const focusLabel = physicalNeedsReview
    ? evidence.physicalValidity.label
    : evidence.status === "ready"
      ? "Evidencia estructural disponible"
      : "Reservas documentadas";
  const focusDetail = physicalNeedsReview
    ? evidence.physicalValidity.detail
    : evidence.status === "ready"
      ? "La decisión justificable y sus límites se conservan en el expediente de la corrida."
      : "Consulta la matriz de evidencia antes de comparar o encadenar cálculos posteriores.";
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
      ? `exhaustividad ${protocol.exhaustiveness}`
      : null,
    typeof protocol?.num_poses === "number" ? `${protocol.num_poses} poses` : null,
    typeof protocol?.seed === "number" ? `seed ${protocol.seed}` : null,
  ].filter((fact): fact is string => Boolean(fact));

  return (
    <section className="border-b border-white/[0.07] pb-6" aria-labelledby="evidence-summary-title">
      <div className="grid gap-7 lg:grid-cols-[minmax(260px,0.78fr)_minmax(0,1.72fr)]">
        <div className="min-w-0">
          <div className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 font-mono text-xs font-bold uppercase tracking-wider ${STATUS_STYLES[evidence.status]}`}>
            <StatusIcon status={statusIcon} />
            {evidence.label}
          </div>
          <h2 id="evidence-summary-title" className="mt-4 font-display text-2xl font-bold tracking-tight text-white">
            Expediente de la corrida
          </h2>
          <p className="mt-2 max-w-[52ch] text-sm leading-6 text-zinc-400">{evidence.summary}</p>

          <div className="mt-5 border-l-2 border-purple-400/50 pl-4">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-purple-300/70">Pregunta del dossier</p>
            <p className="mt-2 text-sm leading-6 text-zinc-200">
              ¿Qué evidencia produjo esta corrida, qué controles superó, qué incertidumbres permanecen y qué es justificable hacer después?
            </p>
            <p className="mt-2 text-xs leading-5 text-zinc-500">
              No califica si la molécula es un buen fármaco ni estima una probabilidad de éxito.
            </p>
          </div>

          <div className={`mt-5 rounded-xl border p-4 ${NEXT_ACTION_STYLES[evidence.nextAction.status]}`}>
            <div className="flex items-start gap-3">
              <ArrowRight size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
              <div className="min-w-0">
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] opacity-70">Foco inmediato</p>
                <p className="mt-1 text-sm font-bold">{focusLabel}</p>
                <p className="mt-2 text-xs leading-5 opacity-75">{focusDetail}</p>
                {physicalNeedsReview && onOpenPhysicalControls && (
                  <button
                    type="button"
                    onClick={onOpenPhysicalControls}
                    className="mt-3 inline-flex min-h-9 items-center rounded-lg border border-current/30 px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider transition-colors hover:bg-white/[0.07] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
                  >
                    Revisar controles físicos y poses
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="min-w-0 border-t border-white/[0.07] pt-5 lg:border-t-0 lg:pt-0">
          <div className="flex items-center gap-2 border-b border-white/[0.07] pb-3">
            <ListChecks size={16} className="text-purple-300" aria-hidden="true" />
            <h3 className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-300">Matriz de evidencia</h3>
          </div>
          <div>
            {evidence.dimensions.map((dimension) => (
              <div key={dimension.id} className="grid min-w-0 gap-2 border-b border-white/[0.07] py-3 sm:grid-cols-[minmax(150px,0.72fr)_minmax(0,1.4fr)] sm:gap-5">
                <div className="flex min-w-0 items-start gap-2.5">
                  <span className={`mt-0.5 shrink-0 ${CHECK_STYLES[dimension.status]}`}>
                    <StatusIcon status={dimension.status} size={15} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-zinc-200">{dimension.label}</p>
                    <p className={`mt-1 break-words font-mono text-[10px] font-bold uppercase tracking-wider ${CHECK_STYLES[dimension.status]}`}>
                      {dimension.statusLabel}
                    </p>
                  </div>
                </div>
                <p className="min-w-0 break-words text-xs leading-5 text-zinc-500">{dimension.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 border-t border-white/[0.07] pt-5" aria-labelledby="run-provenance-title">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 id="run-provenance-title" className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-300">
            Procedencia reproducible
          </h3>
          <p className="text-[11px] leading-5 text-zinc-500">Identidad y protocolo sellados con esta corrida</p>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="min-w-0 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-zinc-500">Receptor exacto</p>
            {result.receptor_sha256 ? (
              <details className="mt-2 min-w-0">
                <summary className="cursor-pointer break-all font-mono text-xs text-emerald-200 marker:text-zinc-600">
                  sha256:{result.receptor_sha256.slice(0, 16)}…
                </summary>
                <code className="mt-2 block break-all rounded-md bg-black/25 p-2 font-mono text-[11px] leading-5 text-zinc-300">
                  {result.receptor_sha256}
                </code>
              </details>
            ) : (
              <p className="mt-2 text-xs leading-5 text-amber-200/75">No registrado en esta corrida.</p>
            )}
            <p className="mt-2 text-xs leading-5 text-zinc-500">
              {result.receptor_path
                ? "Snapshot content-addressed conservado; la ruta local permanece privada."
                : "No se registró un snapshot content-addressed para esta corrida."}
            </p>
          </div>

          <div className="min-w-0 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-zinc-500">Protocolo ejecutado</p>
            {protocol ? (
              <>
                <p className="mt-2 text-sm font-bold text-zinc-200">
                  {hasConformerCounts
                    ? `${generatedConformers} de ${requestedConformers} conformaciones`
                    : "Conteo de conformaciones no registrado"}
                </p>
                <p className="mt-1 break-words text-xs leading-5 text-zinc-500">
                  {protocolFacts.length > 0 ? protocolFacts.join(" · ") : "Parámetros del motor no registrados"}
                </p>
                {(protocol.conformer_warnings?.length ?? 0) > 0 && (
                  <p className="mt-2 text-xs leading-5 text-amber-200/70">
                    {protocol.conformer_warnings!.length} advertencia(s) de generación; consulta el dossier para el detalle.
                  </p>
                )}
              </>
            ) : (
              <p className="mt-2 text-xs leading-5 text-amber-200/75">No registrado en esta corrida.</p>
            )}
          </div>
        </div>
      </div>

      {peptideTransfer && (
        <div
          className={`mt-6 rounded-xl border p-4 ${peptideTransfer.status === "completed" ? "border-emerald-500/25 bg-emerald-500/[0.05]" : "border-amber-500/25 bg-amber-500/[0.05]"}`}
          role="status"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-zinc-300">
              Frontera ESMFold → ligando
            </p>
            <span className={`font-mono text-[10px] font-bold uppercase tracking-wider ${peptideTransfer.status === "completed" ? "text-emerald-300" : "text-amber-300"}`}>
              {peptideTransfer.status === "completed" ? "COMPLETADA" : "ABSTENCIÓN"}
            </span>
          </div>
          {peptideTransfer.status === "completed" ? (
            <p className="mt-2 text-xs leading-5 text-zinc-400">
              Grafo del SMILES conservado; {peptideTransfer.coordinates_transferred ?? 0} átomo(s) con coordenadas de ESMFold y {peptideTransfer.coordinates_completed ?? 0} completado(s) con {peptideTransfer.completion_method ?? "método no registrado"}.
            </p>
          ) : (
            <p className="mt-2 text-xs leading-5 text-amber-100/75">
              No se generó un ligando acoplable{peptideTransfer.failure_code ? ` (${peptideTransfer.failure_code})` : ""}. La estructura plegada se conserva como evidencia, sin afinidad.
            </p>
          )}
        </div>
      )}
      <div className="mt-6 grid gap-6 border-t border-white/[0.07] pt-5 md:grid-cols-2">
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-zinc-500">Supuestos registrados</p>
          <ul className="mt-3 space-y-2 text-xs leading-5 text-zinc-500">
            {evidence.assumptions.map((assumption) => (
              <li key={assumption} className="flex gap-2"><span className="text-zinc-700" aria-hidden="true">—</span><span>{assumption}</span></li>
            ))}
          </ul>
        </div>
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-amber-300/70">
            <AlertTriangle size={14} aria-hidden="true" /> Incertidumbres abiertas
          </p>
          <ul className="mt-3 space-y-2 text-xs leading-5 text-amber-100/65">
            {evidence.uncertainties.map((uncertainty) => (
              <li key={uncertainty} className="flex gap-2"><span className="text-amber-500/50" aria-hidden="true">—</span><span>{uncertainty}</span></li>
            ))}
          </ul>
          {evidence.uncertainties.length === 0 && (
            <p className="mt-3 text-xs leading-5 text-zinc-500">No se registraron incertidumbres adicionales a las limitaciones generales del protocolo.</p>
          )}
        </div>
      </div>
    </section>
  );
}
