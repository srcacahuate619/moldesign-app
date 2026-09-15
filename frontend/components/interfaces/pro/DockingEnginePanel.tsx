"use client";

import React, { useState } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import {
  Dna, Zap, Cpu, Brain, FlaskConical, ExternalLink,
  Info, AlertTriangle, ChevronDown, ChevronUp, Atom, Sparkles
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface DockingEngineConfig {
  engine: "vina" | "qvina2" | "diffdock";
  peptideEngine: "esmfold" | "esmfold-pro" | "esmfold-experimental" | "colabfold" | null;
  gnnPrecision: "fp32" | "fp16";
}

interface Props {
  config: DockingEngineConfig;
  onChange: (c: DockingEngineConfig) => void;
  gpuAvailable: boolean;
  gpuCuda: boolean;
  isPeptide: boolean;
  collapsed?: boolean;
}

export function DockingEnginePanel({ config, onChange, gpuAvailable, gpuCuda, isPeptide, collapsed: initialCollapsed }: Props) {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(!initialCollapsed);

  return (
    <div className="border border-zinc-200 dark:border-white/5 rounded-xl bg-zinc-50 dark:bg-black/40 overflow-hidden">
      {/* ── Header / Toggle ─────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-zinc-100 dark:hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
            <Dna className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-left">
            {/* Title: matches ScoreCard h3 — text-sm font-semibold */}
            <h3 className="text-sm font-semibold tracking-tight text-zinc-800 dark:text-zinc-200">
              {t("op_motor_docking")}
            </h3>
            {/* Subtitle: matches ScoreCard disclaimer — text-[11px] */}
            <p className="text-[11px] text-zinc-500 mt-0.5">
              {config.engine === "vina" ? "AutoDock Vina (FP64)" : config.engine === "qvina2" ? "QuickVina 2 (FP64)" : "DiffDock (FP32)"}
              {config.peptideEngine && isPeptide
                ? ` · ${config.peptideEngine === "esmfold" ? "ESMFold" : config.peptideEngine === "esmfold-pro" ? "ESMFold Pro" : config.peptideEngine === "esmfold-experimental" ? "RFdiffusion" : "ColabFold"}`
                : ""}
              {!isPeptide && ` · GNN: ${config.gnnPrecision === "fp32" ? "FP32" : "FP16"}`}
            </p>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-5 space-y-5 border-t border-zinc-200 dark:border-white/5 pt-4">

              {/* ── {t("op_moleculas_pequenas")} ───────────────────────────── */}
              <div className="space-y-2">
                {/* Section label: text-xs font-semibold — matches ScoreBar label scale */}
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                  <Atom className="w-3.5 h-3.5" />
                  {t("op_moleculas_pequenas")}
                </h4>

                <div className="grid grid-cols-1 gap-2.5">
                  {/* AutoDock Vina */}
                  <label className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                    config.engine === "vina"
                      ? "border-cyan-500/30 bg-cyan-500/5"
                      : "border-zinc-200 dark:border-zinc-700/30 hover:border-zinc-400 dark:hover:border-zinc-600/50"
                  }`}>
                    <input
                      type="radio"
                      name="engine"
                      checked={config.engine === "vina"}
                      onChange={() => onChange({ ...config, engine: "vina" })}
                      className="mt-0.5 w-4 h-4 text-cyan-500 focus:ring-0 accent-cyan-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Engine name: text-sm font-semibold — ScoreBar label scale */}
                        <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                          AutoDock Vina 1.2.7
                        </span>
                        <span className="text-[11px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 font-mono font-bold">
                          {t("pr_mot_clasico")}
                        </span>
                      </div>
                      {/* Description: text-xs — up from text-[11px], readable */}
                      <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
                        {t("pr_mot_clasico_d")}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-zinc-400">
                        <Cpu className="w-3 h-3" />
                        <span className="font-mono">~20s</span>
                      </div>
                    </div>
                  </label>

                  {/* QuickVina 2 */}
                  <label className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                    config.engine === "qvina2"
                      ? "border-amber-500/30 bg-amber-500/5"
                      : "border-zinc-200 dark:border-zinc-700/30 hover:border-zinc-400 dark:hover:border-zinc-600/50"
                  }`}>
                    <input
                      type="radio"
                      name="engine"
                      checked={config.engine === "qvina2"}
                      onChange={() => onChange({ ...config, engine: "qvina2" })}
                      className="mt-0.5 w-4 h-4 text-amber-500 focus:ring-0 accent-amber-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                          QuickVina 2
                        </span>
                        <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono font-bold flex items-center gap-1">
                          <Zap className="w-2.5 h-2.5" />
                          {t("pr_mot_rapido")}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
                        {t("pr_mot_rapido_d")}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-zinc-400">
                        <Zap className="w-3 h-3" />
                        <span className="font-mono">~8s</span>
                      </div>
                    </div>
                  </label>

                  {/* DiffDock */}
                  <label className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                    config.engine === "diffdock"
                      ? "border-violet-500/30 bg-violet-500/5"
                      : "border-zinc-200 dark:border-zinc-700/30 hover:border-zinc-400 dark:hover:border-zinc-600/50"
                  }`}>
                    <input
                      type="radio"
                      name="engine"
                      checked={config.engine === "diffdock"}
                      onChange={() => onChange({ ...config, engine: "diffdock" })}
                      className="mt-0.5 w-4 h-4 text-violet-500 focus:ring-0 accent-violet-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                          DiffDock
                        </span>
                        <span className="text-[11px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 font-mono font-bold flex items-center gap-1">
                          <Sparkles className="w-2.5 h-2.5" />
                          {t("pr_mot_difusion")}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
                        {t("pr_mot_difusion_d")}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-zinc-400">
                        <Sparkles className="w-3 h-3" />
                        <span className="font-mono">~1–5 min</span>
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              {/* ── Péptidos ─────────────────────────────────────── */}
              <div className="space-y-2 pt-3 border-t border-zinc-200 dark:border-zinc-700/30">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                  <Brain className="w-3.5 h-3.5" />
                  {t("auto_7987f4801c2c")}
                  {/* Auto-detect badge */}
                  <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-zinc-200 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 font-mono">
                    auto-detecta
                  </span>
                  {!isPeptide && (
                    <span className="relative group/tip ml-auto">
                      <span className="w-4 h-4 rounded-full bg-zinc-200 dark:bg-zinc-700 inline-flex items-center justify-center text-[9px] font-bold text-zinc-500 dark:text-zinc-400 cursor-help">
                        {t("auto_5bab61eb5317")}
                      </span>
                      <div className="absolute bottom-full right-0 mb-2 px-3 py-2 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 text-xs text-zinc-600 dark:text-zinc-300 shadow-xl opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-50 w-64 text-left leading-relaxed">
                        {t("pr_mot_peptido")}
                        <br />
                        <span className="text-zinc-400 text-[11px]">{t("pr_mot_aviso_vina")}</span>
                      </div>
                    </span>
                  )}
                </h4>

                <div className="grid grid-cols-1 gap-2.5">
                  {/* `as const` fija los ids al union de `peptideEngine`: si se
                      añade un motor que el tipo no contempla, falla aquí y no
                      en tiempo de ejecución. Antes iba con `p.id as any`. */}
                  {([
                    {
                      id: "esmfold",
                      label: "ESMFold",
                      badge: t("pr_mot_rapido"),
                      badgeStyle: { bg: "rgba(14,165,233,0.12)", text: "#38bdf8" },
                      desc: t("auto_14578be07d4d"),
                      gpu: false,
                    },
                    {
                      id: "esmfold-pro",
                      label: "ESMFold Pro",
                      badge: "PRECISO",
                      badgeStyle: { bg: "rgba(168,85,247,0.12)", text: "#a78bfa" },
                      desc: "Plegamiento completo + refinamiento OpenMM.",
                      gpu: false,
                    },
                    {
                      id: "colabfold",
                      label: "ColabFold",
                      badge: "PREDICTIVO",
                      badgeStyle: { bg: "rgba(52,211,153,0.12)", text: "#34d399" },
                      desc: t("auto_0ec637ca2747"),
                      gpu: false,
                    },
                    {
                      id: "esmfold-experimental",
                      label: "RFdiffusion",
                      badge: "EXPERIMENTAL",
                      badgeStyle: { bg: "rgba(251,191,36,0.12)", text: "#fbbf24" },
                      desc: t("auto_9331807fc431"),
                      gpu: true,
                    },
                  ] as const).map((p) => {
                    const disabled = !isPeptide || (p.gpu && gpuAvailable === false);
                    const isSelected = config.peptideEngine === p.id;
                    return (
                      <label
                        key={p.id}
                        className={`flex items-start gap-3 p-3.5 rounded-xl border transition-all ${
                          disabled
                            ? "opacity-30 cursor-not-allowed"
                            : "cursor-pointer"
                        }`}
                        style={{
                          borderColor: disabled
                            ? "rgba(255,255,255,0.05)"
                            : isSelected
                            ? "rgba(14,165,233,0.3)"
                            : "var(--border, rgba(255,255,255,0.08))",
                          background: disabled
                            ? "transparent"
                            : isSelected
                            ? "rgba(14,165,233,0.05)"
                            : "transparent",
                        }}
                      >
                        <input
                          type="radio"
                          name="peptide"
                          checked={isSelected}
                          onChange={() => onChange({ ...config, peptideEngine: p.id })}
                          disabled={disabled}
                          className="mt-0.5 w-4 h-4 focus:ring-0 accent-cyan-500"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`text-sm font-semibold ${
                              disabled
                                ? "text-zinc-400 dark:text-zinc-600"
                                : "text-zinc-800 dark:text-zinc-200"
                            }`}>
                              {p.label}
                            </span>
                            <span
                              className="text-[11px] px-1.5 py-0.5 rounded font-mono font-bold"
                              style={{ background: p.badgeStyle.bg, color: p.badgeStyle.text }}
                            >
                              {p.badge}
                            </span>
                          </div>
                          <p className={`text-xs mt-1 leading-relaxed ${
                            disabled ? "text-zinc-400 dark:text-zinc-700" : "text-zinc-500"
                          }`}>
                            {p.desc}
                          </p>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* ── {t("op_precision_gnn")} ────────────────────────────────── */}
              {!isPeptide && (
                <div className="space-y-3 pt-3 border-t border-zinc-200 dark:border-zinc-700/30">
                  <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-violet-400" />
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                      {t("op_precision_gnn")}
                    </h4>
                    {!gpuAvailable && (
                      <span className="text-[11px] text-zinc-500 ml-auto font-mono">Requiere GPU</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2.5">
                    <button
                      disabled={!gpuAvailable}
                      onClick={() => onChange({ ...config, gnnPrecision: "fp32" })}
                      className={`p-3 rounded-xl border text-sm font-semibold transition-all ${
                        config.gnnPrecision === "fp32"
                          ? "border-violet-500/30 bg-violet-500/10 text-violet-400"
                          : "border-zinc-200 dark:border-zinc-700/30 text-zinc-500 hover:border-zinc-400 dark:hover:border-zinc-600"
                      } disabled:opacity-30 disabled:cursor-not-allowed`}
                    >
                      <div className="font-mono mb-1">FP32</div>
                      <div className="text-xs text-zinc-500 font-normal">{t("pr_mot_precision_completa")}</div>
                    </button>
                    <button
                      disabled={!gpuAvailable || !gpuCuda}
                      onClick={() => onChange({ ...config, gnnPrecision: "fp16" })}
                      className={`p-3 rounded-xl border text-sm font-semibold transition-all ${
                        config.gnnPrecision === "fp16"
                          ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
                          : "border-zinc-200 dark:border-zinc-700/30 text-zinc-500 hover:border-zinc-400 dark:hover:border-zinc-600"
                      } disabled:opacity-30 disabled:cursor-not-allowed`}
                    >
                      <div className="flex items-center gap-1 font-mono mb-1">
                        FP16 <Zap className="w-3 h-3 text-amber-400" />
                      </div>
                      <div className="text-xs text-zinc-500 font-normal">{t("pr_mot_precision_media")}</div>
                    </button>
                  </div>
                </div>
              )}

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
