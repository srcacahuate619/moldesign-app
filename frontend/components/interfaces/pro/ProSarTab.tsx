"use client";

import { presentError } from "../../../lib/frontendError";


import { useLanguage } from "@/context/LanguageContext";
import React, { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { GitFork, Info, Loader2 } from "lucide-react";
import { getSarData, type SarCohort, type SarCohortInfo } from "../../../lib/proApi";
import type { CaseRun } from "../../../lib/cases/types";
import { ComparacionDePosesEntreCorridas, otrasCorridasDeLaMolecula } from "./ComparacionDePosesEntreCorridas";
import { PoseComparisonDialog } from "./PoseComparisonDialog";
import { etiquetaDeCorrida, fuentesDelCaso } from "../../../lib/comparadorDePoses";

/**
 * Convención de presentación, no una afirmación científica: por debajo de este Tanimoto (ECFP4) una molécula no se
 * presenta como análogo. Pasa a «otras moléculas del caso», plegado.
 */
export const UMBRAL_ANALOGO_PCT = 40;

interface CambioEstructural {
  core_heavy_atoms: number;
  base_heavy_atoms: number;
  analog_heavy_atoms: number;
  formula_delta: Array<{ element: string; delta: number }>;
  core_complete: boolean;
}

interface SarAnalog {
  id: number | string;
  /**
   * La fila es la propia molécula de referencia (el backend la entrega primera, con `is_base`, y no ocupa una de las
   * comparaciones). No es un análogo: no se cuenta como tal ni lleva un delta contra sí misma.
   */
  isBase: boolean;
  name: string | null;
  /** Corrida de la que sale la fila; sin ella no se pueden comparar poses. */
  taskId: string | null;
  moleculeId: string | null;
  structuralChange: CambioEstructural | null;
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
    isBase: raw.is_base === true,
    taskId: typeof raw.task_id === "string" && raw.task_id ? raw.task_id : null,
    moleculeId: typeof raw.molecule_id === "string" && raw.molecule_id ? raw.molecule_id : null,
    name: typeof raw.name === "string" && raw.name.trim() ? raw.name : null,
    structuralChange: raw.structural_change && typeof raw.structural_change === "object" ? raw.structural_change : null,
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

/**
 * Color del Δ de afinidad. Negativo (Vina la puntúa más baja que la base): verde; positivo: rosa; sin delta o delta
 * exactamente cero: neutro. Un cero no es «peor que la base», y antes salía en el color de lo peor.
 */
export function claseDelta(delta: number | null): string {
  if (delta == null) return "text-zinc-400";
  if (delta < 0) return "text-emerald-400";
  if (delta > 0) return "text-rose-400";
  return "text-zinc-300";
}

function descripcionDelCambio(a: SarAnalog, t: (key: string, params?: Record<string, string | number>) => string): string {
  if (a.comparisonState === "abstained") return a.highlight || "—";
  const c = a.structuralChange;
  if (!c) return t("pn_sar_cambio_sin_medir");
  const delta = c.formula_delta
    .map((d) => `${d.delta > 0 ? "+" : "\u2212"}${Math.abs(d.delta)} ${d.element}`)
    .join(", ");
  const nucleo = t("pn_sar_cambio_nucleo", { core: c.core_heavy_atoms, base: c.base_heavy_atoms });
  return [nucleo + (c.core_complete ? "" : ` (${t("pn_sar_cambio_incompleto")})`), delta ? t("pn_sar_cambio_formula", { delta }) : ""]
    .filter(Boolean)
    .join(" \u00b7 ");
}

/**
 * Lo que se sabe de un análogo frente a la base: estructura, qué cambia, cuánto cambia la afinidad y las propiedades.
 * Vive dentro del comparador 3D (el análogo se abre ahí directamente); sólo cuando la fila no trae una evaluación
 * distinta de la que se ve —y no hay pose que comparar— se enseña sola, en un modal.
 */
function FichaDelAnalogo({ a, t }: { a: SarAnalog; t: (key: string, params?: Record<string, string | number>) => string }) {
  return (
    <div className="space-y-4">
      <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-wider text-purple-300">
        <GitFork size={16} className="text-purple-400" aria-hidden="true" />
        {a.name ?? `${t("auto_6d710465e74b")}${a.id}`}
      </h3>

      <div>
        <span className="mb-1.5 block text-sm font-sans uppercase tracking-wider text-zinc-400">SMILES</span>
        <p className="break-all rounded-xl border border-white/5 bg-black/40 p-3 text-base font-sans leading-6 text-zinc-200">
          {a.smiles}
        </p>
      </div>

      <div>
        <span className="mb-1.5 block text-sm font-sans uppercase tracking-wider text-purple-300">{t("pr_sar_key_change")}</span>
        <p className="rounded-xl border border-purple-500/15 bg-purple-950/20 p-3 text-base font-sans leading-6 text-zinc-300">
          {descripcionDelCambio(a, t)}
        </p>
      </div>

      {/* SOL-04/AMP-02: por qué esta fila no lleva delta. El motivo lo redacta el backend nombrando ambos valores en
          conflicto; la abstención es parte del contrato, no un estado de error. */}
      {a.comparisonState === "abstained" && a.comparisonReason && (
        <div role="note" className="flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-950/20 p-3">
          <Info size={14} className="mt-0.5 shrink-0 text-amber-400" aria-hidden="true" />
          <p className="text-base font-sans leading-6 text-amber-200">{a.comparisonReason}</p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 font-mono">
        <div className="rounded-xl border border-white/10 bg-black/40 p-3 text-center">
          <span className="mb-1 block text-sm uppercase tracking-wider text-zinc-400">{t("pr_sar_similarity")}</span>
          <span className="text-sm font-black text-white">{a.similarity != null ? `${a.similarity.toFixed(1)}%` : "—"}</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/40 p-3 text-center">
          <span className="mb-1 block text-sm uppercase tracking-wider text-zinc-400">{t("auto_b918b224065b")}</span>
          <span className={`text-sm font-black ${a.isBase ? "text-zinc-400" : claseDelta(a.delta_affinity)}`}>
            {a.isBase ? t("pn_sar_baseline") : a.delta_affinity == null ? "—" : `${a.delta_affinity > 0 ? "+" : ""}${a.delta_affinity.toFixed(1)} kcal/mol`}
          </span>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/40 p-3 text-center">
          <span className="mb-1 block text-sm uppercase tracking-wider text-zinc-400">QED</span>
          <span className="text-sm font-black text-white">{a.qed != null ? a.qed.toFixed(2) : "—"}</span>
        </div>
      </div>

      <div className={`flex items-center gap-2 rounded-xl border p-3 font-mono text-sm ${
        a.lipinski === false
          ? "border-rose-500/20 bg-rose-950/30 text-rose-300"
          : a.lipinski === true
          ? "border-emerald-500/20 bg-emerald-950/30 text-emerald-300"
          : "border-white/10 bg-black/30 text-zinc-400"
      }`}>
        <Info size={14} aria-hidden="true" />
        <span className="font-bold">
          {a.lipinski === true ? t("auto_52e9ae29fb89") : a.lipinski === false ? t("auto_6cb27c1bf686") : t("auto_5cc2fcbbbc9d")}
        </span>
      </div>
    </div>
  );
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
  const { t, locale } = useLanguage();
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
        if (cohorte) setCohortError(cause instanceof Error ? presentError(cause, t) : String(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
    // `claveDeCohorte` y no `cohorte`: el objeto se recrea en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moleculeId, claveDeCohorte, t]);

  const displayAnalogs = analogs ?? [];
  // La referencia va aparte: no es un análogo de sí misma, ni se cuenta, ni se agrupa por su similitud.
  const referencia = displayAnalogs.filter((a) => a.isBase);
  const comparaciones = displayAnalogs.filter((a) => !a.isBase);
  // Más parecidos primero. Sin similitud medible no hay base para llamarlo análogo.
  const porSimilitud = [...comparaciones].sort((x, y) => (y.similarity ?? -1) - (x.similarity ?? -1));
  const analogosReales = porSimilitud.filter((a) => a.similarity != null && a.similarity >= UMBRAL_ANALOGO_PCT);
  const otras = porSimilitud.filter((a) => !(a.similarity != null && a.similarity >= UMBRAL_ANALOGO_PCT));
  const otrasCorridas = useMemo(() => otrasCorridasDeLaMolecula(moleculeId, taskId, caseRuns), [moleculeId, taskId, caseRuns]);
  // Todas las corridas del caso: el comparador 3D deja cambiar de corrida en cada lado (mismo receptor sellado).
  const delCaso = useMemo(
    () => fuentesDelCaso(caseRuns, taskId, (run) => etiquetaDeCorrida(run, t, locale)),
    [caseRuns, taskId, t, locale],
  );

  // Una fila: nombre y estructura, qué cambia frente a la base y cuánto cambia la afinidad.
  // QED y Lipinski son propiedades, no SAR: viven en el detalle.
  const filaAnalogo = (a: SarAnalog, idx: number) => {
    const simColor = a.similarity == null ? "#94a3b8" : a.similarity > 85 ? "#10b981" : a.similarity > 70 ? "#f59e0b" : "#94a3b8";
    return (
      <motion.div
        key={a.id ?? idx}
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, delay: idx * 0.05 }}
        onClick={() => setSelected(a)}
        className="cursor-pointer rounded-xl border border-white/10 bg-black/30 p-3.5 transition-all hover:bg-white/[0.03]"
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex shrink-0 flex-col items-center">
            <span className="text-lg font-black font-mono" style={{ color: simColor }}>
              {a.similarity != null ? `${a.similarity.toFixed(1)}%` : "—"}
            </span>
            <span className="text-sm text-zinc-400 font-sans uppercase tracking-wider">Tanimoto</span>
          </div>
          <div className="min-w-0 flex-1">
            {a.name && <p className="truncate text-base font-semibold leading-6 text-zinc-100">{a.name}</p>}
            <p className="truncate font-mono text-sm leading-6 text-zinc-400" title={a.smiles}>{a.smiles}</p>
            <p className={`mt-0.5 text-base font-sans leading-6 ${a.comparisonState === "abstained" ? "text-amber-300" : "text-purple-300"}`}>
              ✦ {descripcionDelCambio(a, t)}
            </p>
          </div>
          {a.isBase ? (
            // La referencia no se mide contra sí misma: en vez de un «0.0» (que se leía como «peor que la base») se
            // dice qué es.
            <div className="shrink-0 text-right font-mono text-sm">
              <span className="block text-sm font-bold uppercase tracking-wider text-zinc-400">{t("pn_sar_baseline")}</span>
            </div>
          ) : (
            <div className="shrink-0 text-right font-mono text-sm" title={t("pn_sar_delta_ayuda")}>
              <span className="block text-sm uppercase tracking-wider text-zinc-400">{t("pn_sar_delta_vs_base")}</span>
              <span className={`font-bold ${claseDelta(a.delta_affinity)}`}>
                {a.delta_affinity == null ? "—" : `${a.delta_affinity > 0 ? "+" : ""}${a.delta_affinity.toFixed(1)}`}
              </span>
            </div>
          )}
        </div>
      </motion.div>
    );
  };

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
          {loading ? t("auto_11febafc08d5") : t("pr_frontend_093", { v0: analogosReales.length })}
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

      {taskId && moleculeId && otrasCorridas.length > 0 && (
        <ComparacionDePosesEntreCorridas moleculeId={moleculeId} taskId={taskId} otras={otrasCorridas} delCaso={delCaso} />
      )}

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
        ) : comparaciones.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 gap-2 text-zinc-400">
            <GitFork size={28} className="text-white/10" />
            <p className="text-base font-sans leading-6">{t("z_sin_analogos")}</p>
          </div>
        ) : (
          <>
            {referencia.map(filaAnalogo)}
            {analogosReales.map((a, i) => filaAnalogo(a, i + referencia.length))}
            {otras.length > 0 && (
              <details className="rounded-xl border border-white/10 bg-black/20 p-3">
                <summary className="cursor-pointer text-base text-zinc-300">
                  {t("pn_sar_otras_moleculas", { umbral: UMBRAL_ANALOGO_PCT, n: otras.length })}
                </summary>
                <div className="mt-2 space-y-2">
                  {otras.map(filaAnalogo)}
                </div>
              </details>
            )}
          </>
        )}
      </div>

      {/* Un análogo se abre directamente en el comparador 3D (base a la izquierda, análogo a la derecha) y su ficha
          —lo que antes era un modal— vive dentro del comparador. Sólo una fila sin evaluación propia distinta de la
          que se ve, que no tiene pose que comparar, enseña la ficha sola. */}
      {selected && taskId && moleculeId && selected.taskId && selected.moleculeId && selected.taskId !== taskId ? (
        <PoseComparisonDialog
          key={selected.taskId}
          moleculeId={moleculeId}
          taskId={taskId}
          leftRank={1}
          rightRank={1}
          rightSource={{ taskId: selected.taskId, moleculeId: selected.moleculeId, etiqueta: selected.name ?? selected.smiles }}
          runs={delCaso}
          ficha={
            <div className="px-4 pb-4">
              <section
                aria-label={t("pn_sar_ficha_del_analogo")}
                className="rounded-xl border border-white/10 bg-black/30 p-4"
              >
                <FichaDelAnalogo a={selected} t={t} />
              </section>
            </div>
          }
          onClose={() => setSelected(null)}
        />
      ) : selected ? (
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
              <FichaDelAnalogo a={selected} t={t} />
              <p role="note" className="text-base font-sans leading-6 text-zinc-400">
                {t("pn_sar_sin_pose_que_comparar")}
              </p>
            </div>
          </motion.div>
        </div>
      ) : null}
    </div>
  );
}
