"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useEffect, useState } from "react";
import {
  Cpu, HardDrive, Monitor, Zap, Clock, Shield, Atom, ChevronDown,
  ChevronUp, AlertTriangle, CheckCircle2, Info, Layers, Sliders,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { getApiUrl } from "../../../lib/config";

interface HardwareInfo {
  cpu: { model: string; cores_physical: number; cores_logical: number };
  ram: { total_gb: number; available_gb: number };
  gpu: { available: boolean; name: string | null; vram_gb: number; cuda: boolean; opencl: boolean };
  recommendations: { workers: number; parallel_docks: number };
  warnings: string[];
}

interface TimeEstimate {
  total_description: string;
  total_seconds_min: number;
  total_seconds_max: number;
  conformer_docking: string;
  anti_targets: string;
  mmgbsa: string;
}

interface AntiTarget {
  pdb_id: string;
  name: string;
  category: string;
  risk: string;
  threshold_kcal: number;
  source?: string;
}

export interface ProConfig {
  numWorkers: number;
  parallelDocks: number;
  enableSelectivity: boolean;
  selectedAntiTargets: string[];
  enableMMGBSA: boolean;
  mmgbsaSteps: number;
  enableADMET: boolean;
}

interface ProConfigPanelProps {
  config: ProConfig;
  onChange: (config: ProConfig) => void;
  collapsed?: boolean;
}

export function ProConfigPanel({ config, onChange, collapsed: initialCollapsed }: ProConfigPanelProps) {
  const { t } = useLanguage();
  const [hw, setHw] = useState<HardwareInfo | null>(null);
  const [estimate, setEstimate] = useState<TimeEstimate | null>(null);
  const [antiTargets, setAntiTargets] = useState<AntiTarget[]>([]);
  const [expanded, setExpanded] = useState(!initialCollapsed);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHardware();
    fetchAntiTargets();
  }, []);

  useEffect(() => {
    if (hw) updateEstimate();
  }, [config.enableSelectivity, config.enableMMGBSA, config.selectedAntiTargets, hw]);

  const fetchHardware = async () => {
    for (let attempt = 1; attempt <= 10; attempt++) {
      try {
        const r = await fetch(`${await getApiUrl()}/hardware`);
        const data = await r.json();
        if (data.cpu?.cores_physical) {
          setHw(data);
          const rec = data.recommendations;
          onChange({
            ...config,
            numWorkers: rec.workers,
            parallelDocks: rec.parallel_docks,
          });
          return;
        }
      } catch (e) {
        // Backend not ready yet
      }
      if (attempt < 10) await new Promise(r => setTimeout(r, 2000));
    }
    setLoading(false);
  };

  const fetchAntiTargets = async () => {
    for (let attempt = 1; attempt <= 10; attempt++) {
      try {
        const r = await fetch(`${await getApiUrl()}/pro/anti-targets`);
        if (r.ok) {
          const data = await r.json();
          const list = data.anti_targets || [];
          setAntiTargets(list);
          // Select all by default if not already initialized
          if (config.selectedAntiTargets.length === 0) {
            onChange({
              ...config,
              selectedAntiTargets: list.map((a: AntiTarget) => a.pdb_id),
            });
          }
          return;
        }
      } catch (e) {
        // Backend not ready yet
      }
      if (attempt < 10) await new Promise(r => setTimeout(r, 2000));
    }
  };

  const updateEstimate = async () => {
    if (!hw) return;
    const targets = config.enableSelectivity ? config.selectedAntiTargets.length : 0;
    try {
      const r = await fetch(
        `${await getApiUrl()}/hardware/estimate?mode=pro&anti_targets=${targets}&mmgbsa=${config.enableMMGBSA}`
      );
      const data = await r.json();
      setEstimate(data);
    } catch (e) {}
  };

  const toggleAntiTarget = (pdbId: string) => {
    const next = config.selectedAntiTargets.includes(pdbId)
      ? config.selectedAntiTargets.filter((id) => id !== pdbId)
      : [...config.selectedAntiTargets, pdbId];
    onChange({ ...config, selectedAntiTargets: next });
  };

  const formatTime = (s: number) => {
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return sec > 0 ? `${m}min ${sec}s` : `${m}min`;
  };

  return (
    <div className="border border-zinc-200 dark:border-white/5 rounded-xl bg-zinc-50 dark:bg-black/40 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-zinc-100 dark:hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
            <Sliders className="w-4 h-4 text-violet-400" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Opciones Avanzadas</h3>
            <p className="text-[11px] text-zinc-500">
              {estimate ? formatTime(estimate.total_seconds_min) : "..."} - {estimate ? formatTime(estimate.total_seconds_max) : "..."} estimado
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
            <div className="px-4 pb-4 space-y-4 border-t border-zinc-200 dark:border-white/5 pt-4">
              
              {/* Hardware Status */}
              {hw && hw.cpu && (
                <div className="grid grid-cols-3 gap-2">
                  <HardwareChip
                    icon={<Cpu className="w-3 h-3" />}
                    label={(hw.cpu?.cores_physical || t("auto_5bab61eb5317")) + "C/" + (hw.cpu?.cores_logical || t("auto_5bab61eb5317")) + "T"}
                    color="blue"
                  />
                  <HardwareChip
                    icon={<HardDrive className="w-3 h-3" />}
                    label={hw.ram?.total_gb + " GB"}
                    color="emerald"
                  />
                  <HardwareChip
                    icon={<Monitor className="w-3 h-3" />}
                    label={hw.gpu?.available ? (hw.gpu?.cuda ? "CUDA" : "OpenCL") : "CPU only"}
                    color={hw.gpu?.available ? "violet" : "zinc"}
                  />
                </div>
              )}

              {/* Warnings */}
              {hw?.warnings?.map((w, i) => (
                <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/10">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                  <p className="text-[11px] text-amber-300/80">{w}</p>
                </div>
              ))}

              {/* Workers */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                    <Layers className="w-3 h-3" /> Workers
                  </span>
                  <span className="font-mono text-zinc-800 dark:text-zinc-300">{config.numWorkers}</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={hw?.cpu?.cores_physical || 4}
                  value={config.numWorkers}
                  onChange={(e) => onChange({ ...config, numWorkers: parseInt(e.target.value) })}
                  className="w-full h-1.5 rounded-full bg-zinc-300 dark:bg-zinc-700 appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
                    [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-violet-500"
                />
                <p className="text-[10px] text-zinc-500">
                  {config.numWorkers <= 2 ? t("auto_fb21ded85274") :
                   config.numWorkers <= 4 ? t("auto_324dd8981c4f") :
                   t("auto_f63ac70bacae")}
                </p>
              </div>

              {/* Parallel docks */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                    <Zap className="w-3 h-3" /> Docks paralelos
                  </span>
                  <span className="font-mono text-zinc-800 dark:text-zinc-300">{config.parallelDocks}</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={hw?.recommendations?.parallel_docks || 2}
                  value={config.parallelDocks}
                  onChange={(e) => onChange({ ...config, parallelDocks: parseInt(e.target.value) })}
                  className="w-full h-1.5 rounded-full bg-zinc-300 dark:bg-zinc-700 appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
                    [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-violet-500"
                />
              </div>

              {/* Selectivity Toggle */}
              <div className="space-y-3">
                <label className="flex items-center justify-between cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-amber-400" />
                    <div>
                      <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{t("z_panel_selectividad")}</span>
                      <p className="text-[10px] text-zinc-500">{t("z_dockea_antitargets")}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => onChange({ ...config, enableSelectivity: !config.enableSelectivity })}
                    className={`w-9 h-5 rounded-full transition-colors relative ${
                      config.enableSelectivity ? "bg-amber-500" : "bg-zinc-300 dark:bg-zinc-600"
                    }`}
                  >
                    <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                      config.enableSelectivity ? "translate-x-4" : "translate-x-0.5"
                    }`} />
                  </button>
                </label>

                {config.enableSelectivity && (
                  <div className="pl-6 space-y-1.5">
                    {antiTargets.map((at) => (
                      <label key={at.pdb_id} className="flex items-center gap-2 cursor-pointer group">
                        <input
                          type="checkbox"
                          checked={config.selectedAntiTargets.includes(at.pdb_id)}
                          onChange={() => toggleAntiTarget(at.pdb_id)}
                          className="w-3.5 h-3.5 rounded border-zinc-300 dark:border-zinc-600 bg-zinc-100 dark:bg-zinc-700 text-amber-500 focus:ring-0"
                        />
                        <span className="text-[11px] text-zinc-600 group-hover:text-zinc-800 dark:text-zinc-400 dark:group-hover:text-zinc-300 transition-colors">
                          {at.name}
                        </span>
                        <span className="text-[10px] text-zinc-450 dark:text-zinc-600">{at.category}</span>
                        {at.source === "user" && (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-violet-500/10 text-violet-400 font-mono">TUYO</span>
                        )}
                        {at.source === "default" && (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-zinc-200 dark:bg-zinc-700/50 text-zinc-500 font-mono">{t("pn_catalogo")}</span>
                        )}
                        <div className="relative group/tip">
                          <Info className="w-3 h-3 text-zinc-400 dark:text-zinc-600 group-hover/tip:text-zinc-800 dark:group-hover/tip:text-zinc-400" />
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 text-[10px] text-zinc-700 dark:text-zinc-300 shadow-lg opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-50">
                            {at.risk}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              {/* MM-GBSA Toggle */}
              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-2">
                  <Atom className="w-4 h-4 text-violet-400" />
                  <div>
                    <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{t("pn_reevaluacion_mmgbsa")}</span>
                    <p className="text-[10px] text-zinc-500">
                      {t("auto_e68b364d222e")}
                      {hw?.gpu?.available ? t("auto_e853b37ac881") : t("auto_3db55aa751bc")}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => onChange({ ...config, enableMMGBSA: !config.enableMMGBSA })}
                  className={`w-9 h-5 rounded-full transition-colors relative ${
                    config.enableMMGBSA ? "bg-violet-500" : "bg-zinc-300 dark:bg-zinc-600"
                  }`}
                >
                  <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                    config.enableMMGBSA ? "translate-x-4" : "translate-x-0.5"
                  }`} />
                </button>
              </label>

              {/* ADMET Toggle */}
              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-emerald-500/20 flex items-center justify-center">
                    <span className="text-[8px] font-bold text-emerald-400">AD</span>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Predicciones ADMET-AI</span>
                    {/* Mismo aviso que en Opciones (`ProOptionsModal`): los dos
                        interruptores encienden el mismo modelo, así que no
                        pueden prometer cosas distintas. «~90s extra» era una
                        cifra de una máquina con el modelo ya cargado. */}
                    <p className="text-[10px] text-zinc-500">
                      {t("pn_admet_optin")}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => onChange({ ...config, enableADMET: !config.enableADMET })}
                  className={`w-9 h-5 rounded-full transition-colors relative ${
                    config.enableADMET ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600"
                  }`}
                >
                  <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                    config.enableADMET ? "translate-x-4" : "translate-x-0.5"
                  }`} />
                </button>
              </label>

              {/* Time Estimate */}
              {estimate && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-zinc-100 dark:bg-zinc-700/30">
                  <Clock className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
                  <div>
                    <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300">{estimate.total_description}</p>
                    <p className="text-[11px] text-zinc-500">
                      {formatTime(estimate.total_seconds_min)} – {formatTime(estimate.total_seconds_max)}
                      {estimate.anti_targets && ` · ${estimate.anti_targets}`}
                      {estimate.mmgbsa && ` · ${estimate.mmgbsa}`}
                    </p>
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

function HardwareChip({ icon, label, color }: { icon: React.ReactNode; label: string; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-500/10 border-blue-500/20 text-blue-400",
    emerald: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
    violet: "bg-violet-500/10 border-violet-500/20 text-violet-400",
    zinc: "bg-zinc-500/10 border-zinc-500/20 text-zinc-400",
  };

  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-2 rounded-lg border text-[11px] font-mono ${colors[color] || colors.zinc}`}>
      {icon}
      {label}
    </div>
  );
}
