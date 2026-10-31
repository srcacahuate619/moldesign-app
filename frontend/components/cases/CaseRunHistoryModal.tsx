"use client";

import { frontendMessage, type Translate } from "../../lib/frontendError";

import { appLocale } from "../../lib/formatoNumerico";

import { presentError } from "../../lib/frontendError";

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

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { InsigniaDelCatalogo } from "@/components/science/InsigniaDelCatalogo";
import { TRANSLATIONS, useLanguage } from "../../context/LanguageContext";
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
  NO_RUN_FILTER,
  describeRunProtocol,
  filterRuns,
  runMatchesInputs,
  runMode,
  runProtocolDifferences,
  runProtocolRelation,
  type CaseRun,
  type CaseStructuralSystem,
  type RunExecutionState,
  type RunFilter,
  type RunModeFilter,
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
  /** Selección efímera de un clic en Actividad; nunca cambia el libro. */
  readonly requestedTaskId?: string;
  readonly onRequestedRunSelected?: (taskId: string) => void;
}

// Claves, no textos: en castellano fijo, la etiqueta salía «TERMINADA» con la interfaz en inglés.
const STATE_LABELS: Record<RunExecutionState, string> = {
  idle: "ca_estado_corrida_idle",
  submitted: "ca_estado_corrida_submitted",
  running: "ca_estado_corrida_running",
  interrupted: "ca_estado_corrida_interrupted",
  completed: "ca_estado_corrida_completed",
  failed: "ca_estado_corrida_failed",
  cancelled: "ca_estado_corrida_cancelled",
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
/** En el idioma de la interfaz: con `undefined` mandaba el del sistema y salía «25 oct 2026, 05:15 p.m.» en inglés. */
export function formatRunMoment(iso: string, locale = "es", t?: Translate): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return t ? t("ca_run_invalid_date") : TRANSLATIONS[locale === "en" ? "en" : "es"].ca_run_invalid_date;
  }
  return parsed.toLocaleString(appLocale(locale), {
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
export function whyRunCannotOpen(run: CaseRun, t: Translate = (key, values) => String(frontendMessage(key, values))): string | null {
  if (run.executionState === "failed") {
    return t("ca_run_no_report");
  }
  if (run.executionState === "cancelled") {
    return t("ca_run_was_cancelled");
  }
  if (run.executionState === "submitted" || run.executionState === "running") {
    return t("ca_run_still_running");
  }
  if (run.executionState === "interrupted") {
    return t("ca_run_lost");
  }
  if (!run.moleculeId) {
    return t("ca_run_no_reference");
  }
  return null;
}

export default function CaseRunHistoryModal({
  runs,
  structuralSystem,
  currentFingerprint,
  activeTaskId,
  onClose,
  requestedTaskId,
  onRequestedRunSelected,
}: CaseRunHistoryModalProps) {
  const { t, locale } = useLanguage();
  useScrollLock(true);
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);
  const rowElements = useRef(new Map<string, HTMLLIElement>());
  const consumedRequest = useRef<string | null>(null);
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

  const openRun = useCallback((run: CaseRun) => {
    setOpenTaskId(current => current === run.taskId ? null : run.taskId);
  }, []);
  useEffect(() => {
    if (!requestedTaskId || consumedRequest.current === requestedTaskId || !runs.some(run => run.taskId === requestedTaskId)) return;
    consumedRequest.current = requestedTaskId;
    setOpenTaskId(requestedTaskId);
    setFilter(NO_RUN_FILTER);
  }, [requestedTaskId, runs]);
  const openedRun = runs.find(run => run.taskId === openTaskId);
  useEffect(() => {
    if (!openedRun?.moleculeId || whyRunCannotOpen(openedRun, t)) {
      setDetail({ kind: "idle" });
      return;
    }
    let current = true;
    setDetail({ kind: "loading" });
    getEvaluationResult(openedRun.moleculeId, openedRun.taskId).then(result => {
      if (current) setDetail({ kind: "ready", result });
    }).catch((cause: unknown) => {
      if (current) setDetail({ kind: "error", message: cause instanceof Error ? presentError(cause, t)
        : t("ca_frontend_051") });
    });
    return () => { current = false; };
  }, [openedRun?.taskId, openedRun?.moleculeId, openedRun?.executionState, t]);
  useEffect(() => {
    if (!requestedTaskId || openTaskId !== requestedTaskId) return;
    const row = rowElements.current.get(requestedTaskId);
    if (!row) return;
    row.scrollIntoView?.({ block: "nearest" });
    row.focus();
    onRequestedRunSelected?.(requestedTaskId);
  }, [openTaskId, requestedTaskId, onRequestedRunSelected]);

  // CAS-03. Con decenas de corridas del mismo ligando reconocer una fila por su
  // SMILES truncado no alcanza: se filtra por modo (única/ensemble), por estado y
  // por texto. El libro no cambia; sólo lo que se muestra.
  const [filter, setFilter] = useState<RunFilter>(NO_RUN_FILTER);
  const statesPresent = useMemo(
    () => [...new Set(runs.map((run) => run.executionState))],
    [runs],
  );
  const counts = useMemo(
    () => ({
      all: runs.length,
      single: runs.filter((run) => run.protocol && runMode(run.protocol).mode === "single").length,
      ensemble: runs.filter((run) => run.protocol && runMode(run.protocol).mode === "ensemble").length,
    }),
    [runs],
  );
  const filtered = useMemo(() => filterRuns(runs, filter), [runs, filter]);
  const filterActive =
    filter.mode !== "all" || filter.state !== "all" || filter.query.trim() !== "";

  // Más reciente arriba: quien abre el historial viene a buscar lo último que
  // hizo. El libro se guarda en orden de arranque y ese orden no se toca.
  const ordered = [...filtered].reverse();

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
              {t(runs.length === 1 ? "ca_history_one_run" : "ca_history_many_runs", { n: runs.length })}{" "}
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

        {runs.length > 1 && (
          <div
            role="search"
            aria-label={t("ca_history_filtros")}
            className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-surface-800 px-5 py-3"
          >
            <div role="group" aria-label={t("ca_history_filtro_modo")} className="flex items-center gap-1.5">
              {(["all", "single", "ensemble"] as const).map((mode: RunModeFilter) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={filter.mode === mode}
                  onClick={() => setFilter({ ...filter, mode })}
                  className={`rounded-md border px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 ${
                    filter.mode === mode
                      ? "border-purple-500/40 bg-purple-500/[0.12] text-purple-100"
                      : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:text-white"
                  }`}
                >
                  {t(
                    mode === "all"
                      ? "ca_history_modo_todas"
                      : mode === "single"
                        ? "ca_history_modo_unicas"
                        : "ca_history_modo_ensembles",
                    { n: counts[mode] },
                  )}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-zinc-500">
              {t("ca_history_filtro_estado")}
              <select
                value={filter.state}
                onChange={(event) =>
                  setFilter({ ...filter, state: event.target.value as RunFilter["state"] })
                }
                className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] normal-case tracking-normal text-zinc-200"
              >
                <option value="all">{t("ca_history_todos_estados")}</option>
                {statesPresent.map((state) => (
                  <option key={state} value={state}>
                    {t(STATE_LABELS[state])}
                  </option>
                ))}
              </select>
            </label>
            <input
              type="search"
              value={filter.query}
              onChange={(event) => setFilter({ ...filter, query: event.target.value })}
              aria-label={t("ca_history_buscar")}
              placeholder={t("ca_history_buscar")}
              className="min-w-[10rem] flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-2.5 py-1 font-mono text-[11px] text-zinc-200 placeholder:text-zinc-600"
            />
            <p role="status" className="font-mono text-[11px] text-zinc-500">
              {t("ca_history_mostrando", { n: filtered.length, total: runs.length })}
            </p>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          {ordered.length === 0 && runs.length > 0 && filterActive ? (
            <div className="p-8 text-center text-xs leading-5 text-zinc-500">
              <p>{t("ca_history_sin_coincidencias")}</p>
              <button
                type="button"
                onClick={() => setFilter(NO_RUN_FILTER)}
                className="mt-3 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-zinc-300 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
              >
                {t("ca_history_quitar_filtros")}
              </button>
            </div>
          ) : ordered.length === 0 ? (
            <p className="p-8 text-center text-xs leading-5 text-zinc-500">
              {t("ca_sin_evaluaciones")}
            </p>
          ) : (
            <ul className="divide-y divide-surface-800">
              {ordered.map((run) => {
                const blocked = whyRunCannotOpen(run, t);
                const expanded = openTaskId === run.taskId;
                const protocolRelation = runProtocolRelation(run, structuralSystem);
                const differences = runProtocolDifferences(run, structuralSystem);
                const inputsRelation = runMatchesInputs(run, currentFingerprint);
                return (
                  <li key={run.taskId} data-case-run-task={run.taskId}
                    ref={element => { if (element) rowElements.current.set(run.taskId, element); else rowElements.current.delete(run.taskId); }}
                    tabIndex={run.taskId === requestedTaskId ? -1 : undefined}
                    className={`px-5 py-4 ${run.taskId === requestedTaskId ? "bg-purple-500/10 ring-1 ring-inset ring-purple-400/40" : ""}`}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-md border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${STATE_TONES[run.executionState]}`}
                          >
                            {t(STATE_LABELS[run.executionState])}
                          </span>
                          <span className="font-mono text-[11px] text-zinc-400">
                            {formatRunMoment(run.startedAt, locale, t)}
                          </span>
                          {run.taskId === activeTaskId && (
                            <span className="rounded-md border border-purple-500/30 bg-purple-500/[0.07] px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-purple-200">
                              {t("ca_history_on_screen")}
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
                            ? `${describeRunProtocol(run.protocol)} · ${t(
                                runMode(run.protocol).mode === "ensemble"
                                  ? "ca_history_modo_ensemble"
                                  : "ca_history_modo_unico",
                                { k: run.protocol.conformers },
                              )}`
                            : t("ca_history_protocol_unregistered")}
                          {" · "}
                          {run.taskId.slice(0, 12)}…
                        </p>
                        {/* CAS-01: «Otro protocolo» decía que algo cambió sin
                            decir qué. Aquí se nombra cada campo y el valor del
                            sistema inicial. */}
                        {protocolRelation === "otro_protocolo" && differences.length > 0 && (
                          <p className="mt-1 font-mono text-[11px] text-amber-200/80">
                            {t("ca_history_difiere", {
                              detalle: differences
                                .map((d) =>
                                  t(`ca_history_dif_${d.field}`, { run: d.run, sistema: d.system }),
                                )
                                .join("; "),
                            })}
                          </p>
                        )}
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
                          {expanded ? t("ca_history_hide") : t("ca_history_view_result")}
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
                        taskId={run.taskId}
                        pdbId={runMatchesInputs(run, structuralSystem?.inputFingerprint ?? null) === "corresponde" ? structuralSystem?.receptor.pdbId : undefined}
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
  taskId,
  pdbId,
}: {
  detail:
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "ready"; result: EvaluationResult }
    | { kind: "error"; message: string };
  moleculeId: string;
  /** La corrida abierta: sus descargas son las de ESTA evaluación, no las de la última. */
  taskId: string;
  pdbId?: string;
}) {
  const { t } = useLanguage();
  // CAS-06: la descarga puede fallar — el PDF de un ensemble reventaba la
  // composición con HTTP 500 — y el rechazo de la promesa vivía en la
  // consola: el botón parecía no responder. El fallo se declara junto al
  // botón, sin destruir el resultado que ya está abierto, y reintentar
  // limpia el error anterior.
  const [descargaError, setDescargaError] = useState<string | null>(null);
  const descargar = (accion: () => Promise<unknown>) => {
    setDescargaError(null);
    void accion().catch((cause: unknown) => {
      setDescargaError(cause instanceof Error ? presentError(cause, t) : String(cause));
    });
  };
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
      <InsigniaDelCatalogo pdbId={pdbId} corrida={result} />
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Field label={t("se_cmp_affinity")} value={numeroOGuion(result.affinity_kcal, 2, " kcal/mol")} />
        <Field label={t("ca_history_poses")} value={String(result.docking_poses?.length ?? 0)} />
        <Field label={t("ca_history_receptor")} value={result.target_name ?? t("c_no_definido")} />
        <Field label={t("c_motor")} value={result.vina_version ?? t("c_no_registrado")} />
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
          onClick={() => descargar(() => downloadCertificate(moleculeId, "general", taskId))}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
        >
          <Download size={13} aria-hidden="true" />
          {t("ca_history_informe")}
        </button>
        <button
          type="button"
          onClick={() => descargar(() => downloadComplexFile(moleculeId, "general", taskId))}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider text-zinc-300 transition-colors hover:border-purple-500/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
        >
          <Download size={13} aria-hidden="true" />
          {t("ca_history_3d_complex")}
        </button>
      </div>
      {descargaError && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3 text-amber-100"
        >
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-300" aria-hidden="true" />
          <span className="text-xs leading-5">{descargaError}</span>
        </p>
      )}
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
