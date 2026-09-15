"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useState } from "react";
import { Boxes, Target, Crosshair } from "lucide-react";

interface DockingPose {
  rank: number;
  affinity: number;
  rmsd_lb: number;
  rmsd_ub: number;
}

interface Hotspot {
  name: string;
  importance: number;
}

interface Props {
  poses: DockingPose[] | null | undefined;
  hotspots: Hotspot[] | null | undefined;
  hotspots_hit: string[] | null | undefined;
  activePose?: number;
  onSelectPose?: (rank: number) => void;
  poseDetails?: React.ReactNode;
}

export function ProDockingTab({
  poses,
  hotspots,
  hotspots_hit,
  activePose,
  onSelectPose,
  poseDetails,
}: Props) {
  const { t } = useLanguage();
  const [internalPose, setInternalPose] = useState<number | undefined>(undefined);
  const active = activePose ?? internalPose;
  const hitList = hotspots_hit ?? [];

  const selectPose = (rank: number) => {
    if (onSelectPose) onSelectPose(rank);
    else setInternalPose(rank);
  };

  return (
    <div className="space-y-5 animate-in fade-in duration-200 font-sans">
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2 font-mono">
          <Boxes size={18} className="text-purple-400" />
          <span className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-200">
            {t("auto_0c93a3c8d352")}
          </span>
        </div>
        <span className="text-[10px] font-mono uppercase tracking-wider text-white/20 border border-white/10 rounded px-2 py-0.5">
          {poses?.length ?? 0} poses · {hotspots?.length ?? 0} hotspots
        </span>
      </div>

      {/* ─── Docking Poses ─── */}
      <div className="space-y-2">
        <div>
          <span className="flex items-center gap-1.5 font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-300">
            <Target size={13} className="text-purple-400" /> Poses generados
          </span>
          <p className="mt-1 text-xs leading-5 text-zinc-500">
            {t("pn_selecciona_pose")}
          </p>
        </div>

        {(poses && poses.length > 0) ? (
          <div className="space-y-2">
            {poses.map((p) => {
              const isActive = active === p.rank;
              return (
                <React.Fragment key={p.rank}>
                  <button
                    type="button"
                    onClick={() => selectPose(p.rank)}
                    aria-pressed={isActive}
                    aria-label={t("z_ver_controles_pose", { rank: p.rank })}
                    className={`flex w-full items-center justify-between rounded-xl border px-3 py-3 text-left transition-[background-color,border-color,box-shadow] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 ${
                      isActive
                        ? "bg-purple-500/5 border-purple-500/30 shadow-[0_0_15px_rgba(139,92,246,0.08)]"
                        : "bg-white/[0.02] border-white/5 hover:border-white/15"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded font-mono ${
                          isActive
                            ? "bg-purple-500/25 text-purple-200 border border-purple-500/40"
                            : "bg-white/5 text-white/40"
                        }`}
                      >
                        #{p.rank}
                      </span>
                      <span className="text-sm font-mono font-bold text-white/90">
                        {p.affinity.toFixed(1)} kcal/mol
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-white/30">
                      RMSD {p.rmsd_lb.toFixed(1)}/{p.rmsd_ub.toFixed(1)} Å
                    </span>
                  </button>
                  {isActive && poseDetails && <div className="mt-3">{poseDetails}</div>}
                </React.Fragment>
              );
            })}
          </div>
        ) : (
          <div className="rounded-xl border border-white/5 bg-black/20 py-6 text-center font-mono text-xs text-slate-500">
            {t("pn_sin_poses_aun")}
          </div>
        )}
      </div>

      <div className="space-y-2 border-t border-white/10 pt-4">
        <span className="flex items-center gap-1.5 font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-300">
          <Crosshair size={13} className="text-purple-400" /> {t("pn_hotspots_sitio")}
        </span>

        <p className="font-sans text-xs leading-5 text-slate-500">
          {t("pn_hotspots_explicacion")}
        </p>

        {(hotspots && hotspots.length > 0) ? (
          <div className="space-y-1.5">
            {hotspots.map((h) => {
              const isHit = hitList.includes(h.name);
              return (
                <div
                  key={h.name}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg border transition-[background-color,border-color] ${
                    isHit
                      ? "bg-purple-500/5 border-purple-500/20"
                      : "bg-white/[0.02] border-white/5"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 rounded-full transition-colors ${
                        isHit ? "bg-purple-400 shadow-[0_0_8px_rgba(168,85,247,0.5)]" : "bg-white/10"
                      }`}
                    />
                    <span className="text-xs font-mono text-white/70">{h.name}</span>
                  </div>
                  <span className="text-[11px] font-mono font-bold text-white/40">
                    imp={h.importance.toFixed(1)}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-xl border border-white/5 bg-black/20 py-6 text-center font-mono text-xs text-slate-500">
            {t("pn_sin_hotspots")}
          </div>
        )}
      </div>
    </div>
  );
}
