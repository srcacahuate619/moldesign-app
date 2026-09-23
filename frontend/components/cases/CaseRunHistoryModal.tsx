"use client";

// =====================================================================
// CaseRunHistoryModal — el libro de corridas de ESTE caso
// =====================================================================
//
// POR QUÉ EXISTE. Hasta el esquema v7 el caso guardaba una sola corrida y cada
// evaluación nueva pisaba el puntero a la anterior. El informe seguía intacto
// —`evaluation_runs` conserva en el backend el snapshot inmutable de cada
// `task_id`— pero desde el caso ya no se llegaba a él: para recuperarlo había
// que buscarlo en Moldex o en el historial global y repetir la corrida desde
// cero. Lo que faltaba no era el dato: era la puerta.
//
// QUÉ SE ENSEÑA SIN BACKEND Y QUÉ NO. La lista se pinta con lo que el propio
// `case.json` guarda de cada corrida —fecha, ligando, afinidad, protocolo— así
// que el libro se lee aunque el motor esté apagado. El DETALLE no: se pide con
// `getEvaluationResult(moleculeId, taskId)`, que es el mismo endpoint que usa
// la recuperación al reabrir un caso y devuelve el snapshot de ESA corrida, no
// la última evaluación de esa molécula.
//
// LO QUE ESTE PANEL NO HACE. No cambia la corrida activa del caso ni reabre el
// dossier como si fuera la corrida vigente. Abrir una corrida anterior es
// mirarla, no adoptarla: el dossier se arma con los inputs del caso, y armarlo
// con los de ahora sobre el resultado de otra hipótesis sería exactamente la
// atribución falsa que el resto del modelo se dedica a impedir.

import { useCallback, useEffect, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { useScrollLock } from "@/hooks/useScrollLock";
import {
  AlertTriangle,
  Download,
  FileText,
  History,
  Loader2,
  X,
} from "lucide-react";

import { downloadCertificate, downloadComplexFile, getEvaluationResult } from "../../lib/api";
import { numeroOGuion } from "../../lib/formatoNumerico";
import type { EvaluationResult } from "../../lib/types";
import {
  describeRunProtocol,
  runMatchesInputs,
  runProtocolRelation,
  type CaseRun,
  type CaseStructuralSystem,
  type RunExecutionState,
} from "../../lib/cases/types";

export interface CaseRunHistoryModalProps {
  readonly runs: readonly CaseRun[];
  /** Sistema del caso. Sirve para señalar qué corrida usó otro protocolo. */
  readonly structuralSystem?: CaseStructuralSystem;
  /** Huella del preflight vigente, para situar cada corrida frente a él. */
  readonly currentFingerprint: string | null;
  /** `taskId` de la corrida que la pestaña de evaluación está mostrando. */
  readonly activeTaskId?: string;
  readonly onClose: () => void;
}

const STATE_LABELS: Record<RunExecutionState, string> = {
  idle: "Sin arrancar",
  submitted: "Enviada",
  running: "Ejecutando",
  interrupted: "Seguimiento perdido",
  completed: "Terminada",
  failed: "Fallida",
  cancelled: "Cancelada",
};

const STATE_TONES: Record<RunExecutionState, string> = {
  idle: "border-zinc-700 bg-zinc-900 text-zinc-400",
  submitted: "border-sky-500/30 bg-sky-500/[0.07] text-sky-200",
  running: "border-sky-500/30 bg-sky-500/[0.07] text-sky-200",
  interrupted: "border-amber-500/30 bg-amber-500/[0.07] text-amber-200",
  completed: "border-emerald-500/30 bg-emerald-500/[0.07] text-emerald-200",
  failed: "border-rose-500/30 bg-rose-500/[0.07] text-rose-200",
  cancelled: "border-zinc-600 bg-zinc-900 text-zinc-400",
};

/** Fecha legible sin inventar zona: se muestra la local del equipo. */
export function formatRunMoment(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "Fecha no legible";
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Por qué una corrida NO se puede reabrir, o `null` si sí se puede.
 *
 * Se dice la razón en vez de esconder el botón: una corrida que falló y una
 * cuyo resultado se perdió son cosas distintas, y el usuario que vuelve a
 * buscar su informe necesita saber cuál de las dos le ha tocado.
 */
export function whyRunCannotOpen(run: CaseRun): string | null {
  if (run.executionState === "failed") {
    return "Esta corrida falló, así que no produjo ningún informe.";
  }
  if (run.executionState === "cancelled") {
    return "Esta corrida se canceló antes de terminar.";
  }
  if (run.executionState === "submitted" || run.executionState === "running") {
    return "Esta corrida todavía se está ejecutando.";
  }
  if (run.executionState === "interrupted") {
    return "Se perdió el seguimiento de esta corrida y no se sabe cómo terminó.";
  }
  if (!run.moleculeId) {
    return "Esta corrida terminó antes de que el caso guardara la referencia a su resultado.";
  }
  return null;
}

export default function CaseRunHistoryModal({
  runs,
  structuralSystem,
  currentFingerprint,
  activeTaskId,
  onClose,
}: CaseRunHistoryModalProps) {
  const { t } = useLanguage();
  useScrollLock(true);
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);
  const [detail, setDetail] = useState<
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "ready"; result: EvaluationResult }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const openRun = useCallback(
    (run: CaseRun) => {
      if (openTaskId === run.taskId) {
        setOpenTaskId(null);
        setDetail({ kind: "idle" });
        return;
      }
      setOpenTaskId(run.taskId);
      if (!run.moleculeId) {
        setDetail({ kind: "idle" });
        return;
      }
      setDetail({ kind: "loading" });
      // El `taskId` viaja SIEMPRE. Sin él el backend devuelve la proyección más
      // reciente de esa molécula, que puede ser la de otra corrida posterior:
      // eso convertiría «ver la evaluación anterior» en ver otra cosa.
      getEvaluationResult(run.moleculeId, run.taskId)
        .then((result) => setDetail({ kind: "ready", result }))
        .catch((cause: unknown) =>
          setDetail({
            kind: "error",
            message:
              cause instanceof Error
                ? cause.message
                : "El motor no devolvió el resultado guardado de esta corrida.",
          }),
        );
    },
    [openTaskId],
  );

  // Más reciente arriba: quien abre el historial viene a buscar lo último que
  // hizo. El libro se guarda en orden de arranque y ese orden no se toca.
  const ordered = [...runs].reverse();

  return (
    <div
      className="fixed inset-0 z-[135] flex items-center justify-center overflow-hidden bg-black/80 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="case-run-history-title"
        className="flex max-h-full w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-surface-700 bg-surface-950 shadow-2xl"
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-surface-800 px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-purple-300">
              <History size={17} aria-hidden="true" />
              <h2
                id="case-run-history-title"
                className="font-mono text-xs font-bold uppercase tracking-[0.14em]"
              >
                {t("ca_historial_titulo")}
              </h2>
            </div>
            <p className="mt-1.5 text-xs leading-5 text-zinc-500">
              {runs.length === 1
                ? "1 corrida registrada."
                : `${runs.length} corridas registradas.`}{" "}
              {t("auto_4d2183484683")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] text-zinc-400 transition-colors hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
            aria-label={t("ca_historial_cerrar")}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {ordered.length === 0 ? (
            <p className="p-8 text-center text-xs leading-5 text-zinc-500">
              {t("ca_sin_evaluaciones")}
            </p>
          ) : (
            <ul className="divide-y divide-surface-800">
              {ordered.map((run) => {
                const blocked = whyRunCannotOpen(run);
                const expanded = openTaskId === run.taskId;
                const protocolRelation = runProtocolRelation(run, structuralSystem);
                const inputsRelation = runMatchesInputs(run, currentFingerprint);
                return (
                  <li key={run.taskId} className="px-5 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-md border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${STATE_TONES[run.executionState]}`}
                          >
                            {STATE_LABELS[run.executionState]}
                          </span>
                          <span className="font-mono text-[11px] text-zinc-400">
                            {formatRunMoment(run.startedAt)}
                          </span>
                          {run.taskId === activeTaskId && (
                            <span className="rounded-md border border-purple-500/30 bg-purple-500/[0.07] px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-purple-200">
                              En pantalla
                            </span>
                          )}
                          {inputsRelation === "corrida_anterior" && (
                            <span className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                              {t("ca_otra_hipotesis")}
                            </span>
                          )}
                          {/* El protocolo que se salió del sistema se marca en
                              vez de prohibirse: es lo que permite repetir un
                              ligando con más muestreo sin comparar a ciegas. */}
                          {protocolRelation === "otro_protocolo" && (
                            <span className="rounded-md border border-amber-500/30 bg-amber-500/[0.07] px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-200">
                              {t("ca_otro_protocolo")}
                            </span>
                          )}
                        </div>
                        <p className="mt-2 truncate font-mono text-xs text-zinc-200">
                          {run.ligandSmiles ?? t("auto_6ed63fc9cfbb")}
                        </p>
                        <p className="mt-1 font-mono text-[11px] text-zinc-500">
                          {run.protocol
                            ? describeRunProtocol(run.protocol)
                            : "Protocolo no registrado"}
                          {" · "}
                          {run.taskId.slice(0, 12)}…
                        </p>
                      </div>

                      <div className="flex shrink-0 items-center gap-3">
                        <div className="text-right">
                          <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                            {t("c_afinidad")}
                          </p>
                          <p className="font-mono text-sm font-bold text-zinc-100">
                            {numeroOGuion(run.affinityKcal, 2, " kcal/mol")}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => openRun(run)}
                          disabled={blocked !== null}
                          aria-expanded={expanded}
                          title={blocked ?? undefined}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <FileText size={13} aria-hidden="true" />
                          {expanded ? "Ocultar" : "Ver resultado"}
                        </button>
                      </div>
                    </div>

                    {blocked && (
                      <p className="mt-2 font-mono text-[11px] leading-5 text-zinc-500">
                        {blocked}
                        {run.lastError ? ` ${run.lastError}` : ""}
                      </p>
                    )}

                    {expanded && !blocked && (
                      <RunDetail
                        detail={detail}
                        moleculeId={run.moleculeId ?? ""}
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

function RunDetail({
  detail,
  moleculeId,
}: {
  detail:
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "ready"; result: EvaluationResult }
    | { kind: "error"; message: string };
  moleculeId: string;
}) {
  const { t } = useLanguage();
  if (detail.kind === "loading") {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-xl border border-surface-800 bg-black/40 p-4 text-zinc-400" role="status">
        <Loader2 className="h-4 w-4 animate-spin text-purple-300" aria-hidden="true" />
        <p className="text-xs">{t("ca_recuperando_resultado")}</p>
      </div>
    );
  }

  if (detail.kind === "error") {
    return (
      <div className="mt-3 flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4 text-amber-100" role="alert">
        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-300" aria-hidden="true" />
        <p className="text-xs leading-5">
          {detail.message} {t("auto_dae68ac9b41e")}
        </p>
      </div>
    );
  }

  if (detail.kind !== "ready") return null;

  const { result } = detail;
  return (
    <div className="mt-3 rounded-xl border border-surface-800 bg-black/40 p-4">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Field label={t("se_cmp_affinity")} value={numeroOGuion(result.affinity_kcal, 2, " kcal/mol")} />
        <Field label="Poses" value={String(result.docking_poses?.length ?? 0)} />
        <Field label="Receptor" value={result.target_name ?? t("c_no_definido")} />
        <Field label="Motor" value={result.vina_version ?? t("c_no_registrado")} />
      </dl>
      {/* La regresión de ML NO se presenta junto a la afinidad como si fueran
          la misma cantidad: tienen distinto error y distinto dominio. */}
      {typeof result.ml_pki === "number" && (
        <p className="mt-3 font-mono text-[11px] leading-5 text-zinc-500">
          {t("auto_62cbf7d98351")} {numeroOGuion(result.ml_pki, 2, " pKi")}
          {result.ml_pki_aplicada === false
            ? t("auto_5bcd0dc46b99")
            : result.ml_pki_aplicada === null
              ? t("auto_e3213d2976ba")
              : ""}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void downloadCertificate(moleculeId)}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
        >
          <Download size={13} aria-hidden="true" />
          Dossier PDF
        </button>
        <button
          type="button"
          onClick={() => void downloadComplexFile(moleculeId)}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
        >
          <Download size={13} aria-hidden="true" />
          Complejo 3D
        </button>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">{label}</dt>
      <dd className="mt-0.5 truncate font-mono text-xs text-zinc-100">{value}</dd>
    </div>
  );
}
