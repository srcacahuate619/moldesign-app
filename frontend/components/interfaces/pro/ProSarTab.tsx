"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { GitFork, ArrowUpRight, ArrowDownRight, Info, Loader2 } from "lucide-react";
import { getSarData } from "../../../lib/proApi";

interface SarAnalog {
  id: number | string;
  smiles: string;
  similarity: number | null;  // 0-100 (backend envía 0-1 Tanimoto → adapter *100)
  delta_score: number | null;   // + o - respecto al original; null = no comparable
  delta_affinity: number | null; // kcal/mol; null = no comparable
  qed: number | null;
  lipinski: boolean | null;
  highlight: string;     // cambio clave
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
    id: raw.id ?? raw.molecule_id ?? index,
    smiles: raw.smiles ?? "—",
    similarity: similarity == null ? null : similarity * 100,
    delta_score: finiteNumberOrNull(raw.delta_score),
    delta_affinity: finiteNumberOrNull(raw.delta_affinity),
    qed: finiteNumberOrNull(raw.qed),
    lipinski: raw.lipinski_pass === true ? true : raw.lipinski_pass === false ? false : null,
    highlight: raw.highlight ?? "—",
  };
}

export function ProSarTab({ moleculeId }: { moleculeId?: string | null }) {
  const [selected, setSelected] = useState<SarAnalog | null>(null);
  const [analogs, setAnalogs] = useState<SarAnalog[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!moleculeId) {
      setAnalogs(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    getSarData(moleculeId)
      .then((res: any) => {
        if (cancelled) return;
        const rows = res.results || res.analogs || [];
        setAnalogs(Array.isArray(rows) ? rows.map(mapSarAnalog) : null);
      })
      .catch(() => {
        // Sin SAR disponible → null-safe: queda el estado vacío, no el mock
        if (!cancelled) setAnalogs([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [moleculeId]);

  const displayAnalogs = analogs ?? [];

  return (
    <div className="space-y-4 animate-in fade-in duration-200 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2 font-mono">
          <GitFork size={18} className="text-purple-400" />
          <span className="font-black uppercase tracking-wider text-zinc-200 text-xs sm:text-sm">
            Análisis SAR — Estructura-Actividad
          </span>
        </div>
        <span className="text-[10px] font-mono uppercase tracking-wider text-white/20 border border-white/10 rounded px-2 py-0.5">
          {loading ? "cargando…" : `${displayAnalogs.length} análogos`}
        </span>
      </div>

      {/* Summary card */}
      <div className="bg-black/40 p-4 rounded-xl border border-white/10 space-y-2 font-mono text-xs">
        <p className="text-slate-300 leading-relaxed font-sans">
          {moleculeId
            ? "La tabla compara evaluaciones disponibles contra el mismo receptor. La similitud usa Tanimoto sobre el fingerprint topológico de RDKit; los deltas sólo aparecen cuando ambas corridas conservan la métrica correspondiente."
            : "Selecciona una evaluación persistida para consultar moléculas comparables contra el mismo receptor. No se muestran ejemplos ni resultados simulados."}
        </p>
      </div>

      {/* Analog table */}
      <div className="space-y-2">
        <span className="block text-xs font-mono font-bold uppercase tracking-widest text-zinc-300">
          Moléculas estructuralmente comparables
        </span>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-14 gap-3 text-white/40">
            <Loader2 size={28} className="text-purple-400 animate-spin" />
            <p className="text-xs font-mono uppercase tracking-widest">Consultando análogos estructurales...</p>
          </div>
        ) : displayAnalogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 gap-2 text-white/30">
            <GitFork size={28} className="text-white/10" />
            <p className="text-xs font-mono">Sin análogos disponibles aún — evaluá más moléculas contra el mismo receptor para poblar el SAR.</p>
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
                    <span className="text-[9px] text-zinc-500 font-mono uppercase tracking-wider">Tanimoto</span>
                  </div>
                </div>

                {/* SMILES */}
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-mono truncate ${a.lipinski === false ? "text-rose-300/70" : "text-zinc-300"}`}>
                    {a.smiles}
                  </p>
                  <p className="text-[10px] text-purple-300/80 font-sans mt-0.5 truncate">
                    ✦ {a.highlight || "—"}
                  </p>
                </div>

                {/* Metrics */}
                <div className="flex items-center gap-4 shrink-0 font-mono text-xs">
                  <div className="text-right">
                    <span className="text-[9px] text-zinc-500 block uppercase tracking-wider">ΔScore</span>
                    <span className={`font-bold flex items-center gap-0.5 ${a.delta_score == null ? "text-zinc-500" : isBetter ? "text-emerald-400" : "text-rose-400"}`}>
                      {a.delta_score == null ? null : isBetter ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
                      {a.delta_score == null ? "—" : `${isBetter ? "+" : ""}${a.delta_score.toFixed(1)}`}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-[9px] text-zinc-500 block uppercase tracking-wider">ΔAfinidad</span>
                    <span className={`font-bold ${a.delta_affinity == null ? "text-zinc-500" : a.delta_affinity < 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {a.delta_affinity == null ? "—" : `${a.delta_affinity > 0 ? "+" : ""}${a.delta_affinity.toFixed(1)}`}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-[9px] text-zinc-500 block uppercase tracking-wider">QED</span>
                    <span className="font-bold text-white">{a.qed != null ? a.qed.toFixed(2) : "—"}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-[9px] text-zinc-500 block uppercase tracking-wider">Lipinski</span>
                    <span className={`font-bold ${a.lipinski === true ? "text-emerald-400" : a.lipinski === false ? "text-rose-400" : "text-zinc-600"}`}>
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
                  Análogo #{selected.id}
                </h3>
                <span
                  className="text-xs font-mono font-bold px-2.5 py-1 rounded border"
                  style={{
                    color: selected.delta_score == null ? "#a1a1aa" : selected.delta_score > 0 ? "#34d399" : "#fb7185",
                    borderColor: selected.delta_score == null ? "rgba(161,161,170,0.3)" : selected.delta_score > 0 ? "rgba(16,185,129,0.3)" : "rgba(244,63,94,0.3)",
                    backgroundColor: selected.delta_score == null ? "rgba(161,161,170,0.08)" : selected.delta_score > 0 ? "rgba(16,185,129,0.08)" : "rgba(244,63,94,0.08)",
                  }}
                >
                  {selected.delta_score == null ? "Sin comparación" : selected.delta_score > 0 ? "Puntuación mayor" : "Puntuación menor"}
                </span>
              </div>

              {/* SMILES full */}
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 block mb-1.5">SMILES</span>
                <p className="text-xs font-mono text-zinc-200 bg-black/40 p-3 rounded-xl border border-white/5 break-all leading-relaxed">
                  {selected.smiles}
                </p>
              </div>

              {/* Change highlight */}
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-purple-300 block mb-1.5">Cambio clave</span>
                <p className="text-xs text-zinc-300 font-sans leading-relaxed bg-purple-950/20 p-3 rounded-xl border border-purple-500/15">
                  {selected.highlight || "—"}
                </p>
              </div>

              {/* Metrics grid */}
              <div className="grid grid-cols-4 gap-3 font-mono">
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                  <span className="text-[9px] text-zinc-400 block uppercase tracking-wider mb-1">Similitud</span>
                  <span className="text-sm font-black text-white">{selected.similarity != null ? `${selected.similarity.toFixed(1)}%` : "—"}</span>
                </div>
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                  <span className="text-[9px] text-zinc-400 block uppercase tracking-wider mb-1">ΔScore</span>
                  <span className={`text-sm font-black ${selected.delta_score == null ? "text-zinc-500" : selected.delta_score > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {selected.delta_score == null ? "—" : `${selected.delta_score > 0 ? "+" : ""}${selected.delta_score.toFixed(1)}`}
                  </span>
                </div>
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                  <span className="text-[9px] text-zinc-400 block uppercase tracking-wider mb-1">ΔAfinidad</span>
                  <span className={`text-sm font-black ${selected.delta_affinity == null ? "text-zinc-500" : selected.delta_affinity < 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {selected.delta_affinity == null ? "—" : `${selected.delta_affinity > 0 ? "+" : ""}${selected.delta_affinity.toFixed(1)} kcal/mol`}
                  </span>
                </div>
                <div className="bg-black/40 p-3 rounded-xl border border-white/10 text-center">
                  <span className="text-[9px] text-zinc-400 block uppercase tracking-wider mb-1">QED</span>
                  <span className="text-sm font-black text-white">{selected.qed != null ? selected.qed.toFixed(2) : "—"}</span>
                </div>
              </div>

              {/* Lipinski verdict */}
              <div className={`rounded-xl border p-3 flex items-center gap-2 font-mono text-xs ${
                selected.lipinski === false
                  ? "border-rose-500/20 bg-rose-950/30 text-rose-300"
                  : selected.lipinski === true
                  ? "border-emerald-500/20 bg-emerald-950/30 text-emerald-300"
                  : "border-white/10 bg-black/30 text-zinc-400"
              }`}>
                <Info size={14} />
                <span className="font-bold">
                  {selected.lipinski === true
                    ? "Lipinski pasado — cumple reglas de drug-likeness"
                    : selected.lipinski === false
                    ? "Lipinski fallado — molécula demasiado voluminosa o lipofílica"
                    : "Lipinski no calculado para este análogo"}
                </span>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
