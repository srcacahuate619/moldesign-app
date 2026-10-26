"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { GitFork, ArrowUpRight, ArrowDownRight, Info, Loader2 } from "lucide-react";
import { getSarData, type SarCohort, type SarCohortInfo } from "../../../lib/proApi";
import type { CaseRun } from "../../../lib/cases/types";

interface SarAnalog {
  id: number | string;
  smiles: string;
  similarity: number | null;  // 0-100 (backend envía 0-1 Tanimoto → adapter *100)
  delta_score: number | null;   // SIEMPRE null: el score agregado no produce deltas SAR (SOL-04/AMP-02)
  delta_affinity: number | null; // kcal/mol; null = abstención de comparabilidad o ausencia
  qed: number | null;
  lipinski: boolean | null;
  highlight: string;     // cambio clave
  /**
   * SOL-04/AMP-02: `abstained` cuando la condición química (pH/protonación/
   * tautómero) o el protocolo estructural no coinciden con la base. El delta
   * no se fabrica; el motivo explica por qué nombrando ambos valores.
   */
  comparisonState: "descriptive" | "abstained" | null;
  comparisonReason: string | null;
}

function finiteNumberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

// ── Adapter: respuesta /sar/{id} → modelo visual del tab ──
// El backend devuelve similarity 0-1 (Tanimoto) y NO tiene qed/lipinski/highlight
// por análogo (solo smiles/similarity/total_score/affinity_kcal/ml_prob + delta_affinity).
export function mapSarAnalog(raw: any, index: number): SarAnalog {
  const similarity = finiteNumberOrNull(raw.similarity);
  return {
    // `task_id` antes que `molecule_id`: en una cohorte explícita la misma
    // molécula puede aparecer en dos corridas, y la clave tiene que ser única.
    id: raw.id ?? raw.task_id ?? raw.molecule_id ?? index,
    smiles: raw.smiles ?? "—",
    similarity: similarity == null ? null : similarity * 100,
    delta_score: finiteNumberOrNull(raw.delta_score),
    delta_affinity: finiteNumberOrNull(raw.delta_affinity),
    qed: finiteNumberOrNull(raw.qed),
    lipinski: raw.lipinski_pass === true ? true : raw.lipinski_pass === false ? false : null,
    highlight: raw.highlight ?? "—",
    comparisonState:
      raw.comparison_state === "abstained" || raw.comparison_state === "descriptive"
        ? raw.comparison_state
        : null,
    comparisonReason: raw.comparison_reason ?? null,
  };
}

/**
 * La cohorte histórica que el caso puede ofrecer para la corrida en pantalla
 * (CAS-02): las corridas TERMINADAS del caso con el mismo protocolo que ella,
 * una por corrida y no una por molécula. Con ≥2 es una alternativa real a la
 * proyección más reciente; con menos no hay nada que elegir. Sin protocolo
 * registrado en la corrida de referencia no se adivina cuál es «el mismo».
 */
export function cohorteDelProtocolo(
  taskId: string | null | undefined,
  caseRuns: readonly CaseRun[] | undefined,
): { taskIds: string[]; k: number } | null {
  if (!taskId || !caseRuns) return null;
  const referencia = caseRuns.find((run) => run.taskId === taskId);
  if (!referencia?.protocol) return null;
  const { dockingEngine, exhaustiveness, numPoses, conformers } = referencia.protocol;
  const taskIds = caseRuns
    .filter(
      (run) =>
        run.executionState === "completed" &&
        run.moleculeId &&
        run.protocol &&
        run.protocol.dockingEngine === dockingEngine &&
        run.protocol.exhaustiveness === exhaustiveness &&
        run.protocol.numPoses === numPoses &&
        run.protocol.conformers === conformers,
    )
    .map((run) => run.taskId);
  return taskIds.length >= 2 ? { taskIds, k: conformers } : null;
}

export function ProSarTab({
  moleculeId,
  taskId = null,
  caseRuns,
}: {
  moleculeId?: string | null;
  /** Corrida que la evaluación muestra. Base de la cohorte explícita. */
  taskId?: string | null;
  /** Libro de corridas del caso: de aquí sale la cohorte histórica. */
  caseRuns?: readonly CaseRun[];
}) {
  const { t } = useLanguage();
  const [selected, setSelected] = useState<SarAnalog | null>(null);
  const [analogs, setAnalogs] = useState<SarAnalog[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [cohortInfo, setCohortInfo] = useState<SarCohortInfo | null>(null);
  const [cohortError, setCohortError] = useState<string | null>(null);
  // CAS-02: por defecto, la proyección más reciente (lo de siempre). Si el caso
  // tiene una cohorte histórica del mismo protocolo, se puede elegir.
  const [usarCohorte, setUsarCohorte] = useState(false);
  const historica = useMemo(() => cohorteDelProtocolo(taskId, caseRuns), [taskId, caseRuns]);
  const cohorte: SarCohort | undefined =
    usarCohorte && historica && taskId
      ? { taskId, cohortTaskIds: historica.taskIds }
      : undefined;
  const claveDeCohorte = cohorte ? `${cohorte.taskId}|${cohorte.cohortTaskIds.join(",")}` : "";

  // Si cambia la corrida o el libro y la cohorte deja de existir, se vuelve al
  // valor por defecto en vez de consultar una cohorte que ya no aplica.
  useEffect(() => {
    if (!historica) setUsarCohorte(false);
  }, [historica]);

  useEffect(() => {
    if (!moleculeId) {
      setAnalogs(null);
      setCohortInfo(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setCohortError(null);
    getSarData(moleculeId, cohorte)
      .then((res: any) => {
        if (cancelled) return;
        const rows = res.results || res.analogs || [];
        setAnalogs(Array.isArray(rows) ? rows.map(mapSarAnalog) : null);
        setCohortInfo(res.cohort ?? null);
      })
      .catch((cause: unknown) => {
        // Sin SAR disponible → null-safe: queda el estado vacío, no el mock.
        // Si se pidió una cohorte explícita, el rechazo se DICE (una corrida
        // ajena, fallida o de otro receptor): cae en silencio a una tabla vacía
        // sería indistinguible de «no hay análogos».
        if (cancelled) return;
        setAnalogs([]);
        setCohortInfo(null);
        if (cohorte) setCohortError(cause instanceof Error ? cause.message : String(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
    // `claveDeCohorte` y no `cohorte`: el objeto se recrea en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moleculeId, claveDeCohorte]);

  const displayAnalogs = analogs ?? [];

  return (
    <div className="space-y-4 animate-in fade-in duration-200 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2 font-mono">
          <GitFork size={18} className="text-purple-400" />
          <span className="font-black uppercase tracking-wider text-zinc-200 text-sm sm:text-sm">
            {t("z_analisis_sar")}
          </span>
        </div>
        <span className="text-sm font-sans uppercase tracking-wider text-zinc-400 border border-white/10 rounded px-2 py-0.5">
          {loading ? t("auto_11febafc08d5") : `${displayAnalogs.length} análogos`}
        </span>
      </div>

      {/* CAS-02: de dónde sale la tabla. Por defecto, la evaluación más reciente
          de cada molécula (cambia al reevaluarla con otro protocolo); si el caso
          tiene una cohorte histórica del mismo protocolo, se puede elegir. */}
      {historica && (
        <fieldset className="rounded-xl border border-white/10 bg-black/30 px-3.5 py-3 font-sans text-sm text-zinc-300">
          <legend className="px-1 font-sans text-sm font-bold uppercase tracking-widest text-zinc-400">
            {t("pn_sar_cohorte")}
          </legend>
          <label className="flex cursor-pointer items-start gap-2 py-0.5">
            <input
              type="radio"
              name="sar-cohorte"
              checked={!usarCohorte}
              onChange={() => setUsarCohorte(false)}
              className="mt-0.5"
            />
            <span>{t("pn_sar_cohorte_reciente")}</span>
          </label>
          <label className="flex cursor-pointer items-start gap-2 py-0.5">
            <input
              type="radio"
              name="sar-cohorte"
              checked={usarCohorte}
              onChange={() => setUsarCohorte(true)}
              className="mt-0.5"
            />
            <span>{t("pn_sar_cohorte_protocolo", { n: historica.taskIds.length, k: historica.k })}</span>
          </label>
        </fieldset>
      )}
      {cohortInfo?.source === "explicit_runs" && (
        <p role="status" className="font-sans text-base leading-6 text-zinc-400">
          {t("pn_sar_cohorte_explicita", { n: cohortInfo.task_ids?.length ?? 0 })}
        </p>
      )}
      {cohortError && (
        <p
          role="alert"
          className="rounded-xl border border-amber-500/40 bg-amber-950/25 px-3 py-2 font-sans text-base leading-6 text-amber-100"
        >
          {t("pn_sar_cohorte_rechazada", { motivo: cohortError })}
        </p>
      )}

      {/* Summary card */}
      <div className="bg-black/40 p-4 rounded-xl border border-white/10 space-y-2 font-mono text-sm">
        <p className="text-base text-slate-300 leading-6 font-sans">
          {moleculeId
            ? t("auto_b5b351f33de7")
            : t("auto_51a229f168ca")}
        </p>
      </div>

      {/* Analog table */}
      <div className="space-y-2">
        <span className="block text-sm font-sans font-bold uppercase tracking-widest text-zinc-300">
          {t("pn_sar_comparables")}
        </span>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-14 gap-3 text-zinc-400">
            <Loader2 size={28} className="text-purple-400 animate-spin" />
            <p className="text-sm font-sans uppercase tracking-widest">{t("z_consultando_analogos")}</p>
          </div>
        ) : displayAnalogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 gap-2 text-zinc-400">
            <GitFork size={28} className="text-white/10" />
            <p className="text-base font-sans leading-6">{t("z_sin_analogos")}</p>
          </div>
        ) : displayAnalogs.map((a, idx) => {
          const isBetter = a.delta_score != null && a.delta_score > 0;
          const simColor = a.similarity == null ? "#94a3b8" : a.similarity > 85 ? "#10b981" : a.similarity > 70 ? "#f59e0b" : "#94a3b8";
          return (
            <motion.div
              key={a.id ?? idx}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: idx * 0.05 }}
              onClick={() => setSelected(a)}
              className={`p-3.5 rounded-xl border cursor-pointer transition-all hover:bg-white/[0.03] ${
                a.delta_score != null && a.delta_score > 1.5
                  ? "border-emerald-500/30 bg-emerald-950/20"
                  : a.delta_score != null && a.delta_score < -2
                  ? "border-rose-500/30 bg-rose-950/20"
                  : "border-white/10 bg-black/30"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                {/* Similarity */}
                <div className="flex items-center gap-3 shrink-0">
                  <div className="flex flex-col items-center">
                    <span className="text-lg font-black font-mono" style={{ color: simColor }}>
                      {a.similarity != null ? `${a.similarity.toFixed(1)}%` : "—"}
                    </span>
                    <span className="text-sm text-zinc-400 font-sans uppercase tracking-wider">Tanimoto</span>
                  </div>
                </div>

                {/* SMILES */}
                <div className="flex-1 min-w-0">
                  <p className={`text-base font-sans truncate leading-6 ${a.lipinski === false ? "text-rose-300" : "text-zinc-300"}`}>
                    {a.smiles}
                  </p>
                  {/* SOL-04/AMP-02: en abstención la línea enseña el motivo que
                      envía el backend — la abstención se lee como precaución,
                      no como decoración. */}
                  <p className={`text-base font-sans mt-0.5 truncate leading-6 ${a.comparisonState === "abstained" ? "text-amber-300" : "text-purple-300"}`}>
                    ✦ {a.highlight || "—"}
                  </p>
                </div>

                {/* Metrics */}
                <div className="flex items-center gap-4 shrink-0 font-mono text-sm">
                  <div className="text-right">
                    <span className="text-sm text-zinc-400 block uppercase tracking-wider">ΔScore</span>
                    <span className={`font-bold flex items-center gap-0.5 ${a.delta_score == null ? "text-zinc-400" : isBetter ? "text-emerald-400" : "text-rose-400"}`}>
                      {a.delta_score == null ? null : isBetter ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
                      {a.delta_score == null ? "—" : `${isBetter ? "+" : ""}${a.delta_score.toFixed(1)}`}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm text-zinc-400 block uppercase tracking-wider">{t("auto_b918b224065b")}</span>
                    <span className={`font-bold ${a.delta_affinity == null ? "text-zinc-400" : a.delta_affinity < 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {a.delta_affinity == null ? "—" : `${a.delta_affinity > 0 ? "+" : ""}${a.delta_affinity.toFixed(1)}`}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm text-zinc-400 block uppercase tracking-wider">QED</span>
                    <span className="font-bold text-white">{a.qed != null ? a.qed.toFixed(2) : "—"}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm text-zinc-400 block uppercase tracking-wider">Lipinski</span>
                    <span className={`font-bold ${a.lipinski === true ? "text-emerald-400" : a.lipinski === false ? "text-rose-400" : "text-zinc-400"}`}>
                      {a.lipinski === true ? "✓" : a.lipinski === false ? "✗" : "—"}
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Modal — detalle del análogo */}
      {selected && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setSelected(null)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-xl bg-[#0a0d16] border border-purple-500/15 rounded-2xl shadow-2xl overflow-hidden"
          >
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <h3 className="text-sm font-black uppercase tracking-wider text-purple-300 flex items-center gap-2">
                  <GitFork size={16} className="text-purple-400" />
                  {t("auto_6d710465e74b")}{selected.id}
                </h3>
                <span
                  className="text-sm font-mono font-bold px-2.5 py-1 rounded border"
                  style={{
                    color: selected.delta_score == null ? "#a1a1aa" : selected.delta_score > 0 ? "#34d399" : "#fb7185",
                    borderColor: selected.delta_score == null ? "rgba(161,161,170,0.3)" : selected.delta_score > 0 ? "rgba(16,185,129,0.3)" : "rgba(244,63,94,0.3)",
                    backgroundColor: selected.delta_score == null ? "rgba(161,161,170,0.08)" : selected.delta_score > 0 ? "rgba(16,185,129,0.08)" : "rgba(244,63,94,0.08)",
                  }}
                >
                  {selected.delta_score == null ? t("auto_85e292a64f4e") : selected.delta_score > 0 ? t("auto_61757f570214") : t("auto_dca3aacd35e5")}
                </span>
              </div>

              {/* SMILES full */}
              <div>
                <span className="text-sm font-sans uppercase tracking-wider text-zinc-400 block mb-1.5">SMILES</span>
                <p className="text-base font-sans text-zinc-200 bg-black/40 p-3 rounded-xl border border-white/5 break-all leading-6">
                  {selected.smiles}
                </p>
              </div>

              {/* Change highlight */}
              <div>
                <span className="text-sm font-sans uppercase tracking-wider text-purple-300 block mb-1.5">{t("pr_sar_key_change")}</span>
                <p className="text-base text-zinc-300 font-sans leading-6 bg-purple-950/20 p-3 rounded-xl border border-purple-500/15">
                  {selected.highlight || "—"}
                </p>
              </div>

              {/* SOL-04/AMP-02: por qué esta fila no lleva delta. El motivo lo
                  redacta el backend nombrando ambos valores en conflicto; la
                  abstención es parte del contrato, no un estado de error. */}
              {selected.comparisonState === "abstained" && selected.comparisonReason && (
                <div
                  role="note"
                  className="rounded-xl border border-amber-500/20 bg-amber-950/20 p-3 flex items-start gap-2"
                >
                  <Info size={14} className="shrink-0 mt-0.5 text-amber-400" />
                  <p className="text-base text-amber-200 font-sans leading-6">
                    {selected.comparisonReason}
                  </p>
                </div>
              )}

              {/* Metrics grid */}
              <div className="grid grid-cols-4 gap-3 font-mono">
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                    <span className="text-sm text-zinc-400 block uppercase tracking-wider mb-1">{t("pr_sar_similarity")}</span>
                  <span className="text-sm font-black text-white">{selected.similarity != null ? `${selected.similarity.toFixed(1)}%` : "—"}</span>
                </div>
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                  <span className="text-sm text-zinc-400 block uppercase tracking-wider mb-1">ΔScore</span>
                  <span className={`text-sm font-black ${selected.delta_score == null ? "text-zinc-400" : selected.delta_score > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {selected.delta_score == null ? "—" : `${selected.delta_score > 0 ? "+" : ""}${selected.delta_score.toFixed(1)}`}
                  </span>
                </div>
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                  <span className="text-sm text-zinc-400 block uppercase tracking-wider mb-1">{t("auto_b918b224065b")}</span>
                  <span className={`text-sm font-black ${selected.delta_affinity == null ? "text-zinc-400" : selected.delta_affinity < 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {selected.delta_affinity == null ? "—" : `${selected.delta_affinity > 0 ? "+" : ""}${selected.delta_affinity.toFixed(1)} kcal/mol`}
                  </span>
                </div>
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                  <span className="text-sm text-zinc-400 block uppercase tracking-wider mb-1">QED</span>
                  <span className="text-sm font-black text-white">{selected.qed != null ? selected.qed.toFixed(2) : "—"}</span>
                </div>
              </div>

              {/* Lipinski verdict */}
              <div className={`rounded-xl border p-3 flex items-center gap-2 font-mono text-sm ${
                selected.lipinski === false
                  ? "border-rose-500/20 bg-rose-950/30 text-rose-300"
                  : selected.lipinski === true
                  ? "border-emerald-500/20 bg-emerald-950/30 text-emerald-300"
                  : "border-white/10 bg-black/30 text-zinc-400"
              }`}>
                <Info size={14} />
                <span className="font-bold">
                  {selected.lipinski === true
                    ? t("auto_52e9ae29fb89")
                    : selected.lipinski === false
                    ? t("auto_6cb27c1bf686")
                    : t("auto_5cc2fcbbbc9d")}
                </span>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
