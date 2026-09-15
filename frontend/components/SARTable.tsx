"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Minus, Trophy, AlertTriangle,
  CheckCircle2, XCircle, ArrowUp, ArrowDown, Zap,
} from "lucide-react";
import { getApiUrl } from "../lib/config";

interface SARResult {
  molecule_id: string;
  name: string;
  smiles: string;
  total_score: number | null;
  affinity_kcal: number | null;
  delta_score: number;
  delta_affinity: number;
  molecular_weight: number | null;
  log_p: number | null;
  tpsa: number | null;
  lipinski_pass: boolean | null;
  ghose_pass: boolean | null;
  is_pains: boolean | null;
  is_base: boolean;
}

interface SARData {
  base_molecule_id: string;
  target_pdb_id: string;
  target_name: string;
  total_analogs: number;
  base_score: number;
  base_affinity: number;
  best_of: { score: number; affinity: number; admet: number };
  results: SARResult[];
}

interface Props {
  moleculeId: string;
  compact?: boolean;
}

export function SARTable({ moleculeId, compact }: Props) {
  const { t } = useLanguage();
  const [data, setData] = useState<SARData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    // La base se resuelve antes de pedir: en escritorio el puerto lo elige
    // Rust y una constante congelada apuntaría al puerto equivocado.
    getApiUrl()
      .then((base) => fetch(`${base}/sar/${moleculeId}`, { signal: controller.signal }))
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.detail) throw new Error(d.detail);
        setData(d);
      })
      .catch((e) => {
        if (cancelled || e.name === "AbortError") return;
        setError(e.message);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, [moleculeId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
      </div>
    );
  }

  if (error || !data || data.results.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-zinc-500">
        {error || t("auto_271fb52e9981")}
      </div>
    );
  }

  const bestScore = data.best_of.score;
  const bestAffinity = data.best_of.affinity;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">
            SAR: {data.total_analogs} analogos contra {data.target_pdb_id}
          </h3>
          <p className="text-[11px] text-zinc-500">
            {data.target_name} {t("auto_988351833ce1")}
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
          <span className="flex items-center gap-1">
            <Trophy className="w-3 h-3 text-amber-400" /> {t("auto_57c0f9e92135")} {(bestScore ?? 0).toFixed(0)}
          </span>
          <span className="flex items-center gap-1">
            <Zap className="w-3 h-3 text-cyan-400" /> {t("auto_468deba59306")} {(bestAffinity ?? 0).toFixed(1)}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-zinc-700/30">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-zinc-800/50 text-zinc-400">
              <th className="px-3 py-2 text-left font-medium w-6">#</th>
              <th className="px-3 py-2 text-left font-medium">Molecula</th>
              <th className="px-3 py-2 text-right font-medium">Score</th>
              <th className="px-3 py-2 text-right font-medium">&Delta;</th>
              <th className="px-3 py-2 text-right font-medium">Afinidad</th>
              <th className="px-3 py-2 text-right font-medium">&Delta;</th>
              {!compact && (
                <>
                  <th className="px-3 py-2 text-right font-medium">MW</th>
                  <th className="px-3 py-2 text-right font-medium">LogP</th>
                  <th className="px-3 py-2 text-center font-medium">Drug</th>
                  <th className="px-3 py-2 text-center font-medium">PAINS</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {data.results.map((r, i) => {
              const isBestScore = r.total_score === bestScore && r.total_score !== null;
              const isBestAff = r.affinity_kcal === bestAffinity && r.affinity_kcal !== null;
              const deltaGood = r.delta_score > 0;

              return (
                <tr
                  key={r.molecule_id}
                  className={`border-t border-zinc-700/20 transition-colors ${
                    r.is_base
                      ? "bg-violet-500/5 border-violet-500/10"
                      : i % 2 === 0
                      ? "bg-zinc-800/10"
                      : ""
                  } ${r.is_pains ? "bg-red-500/5" : ""}`}
                >
                  <td className="px-3 py-2 text-zinc-500 font-mono">
                    {i + 1}
                    {r.is_base && (
                      <span className="ml-1 text-[9px] text-violet-400 font-sans">base</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-zinc-300 max-w-[160px] truncate">
                    {r.name}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono font-semibold ${
                    isBestScore ? "text-amber-400" : "text-zinc-300"
                  }`}>
                    {r.total_score?.toFixed(0) || "—"}
                    {isBestScore && <Trophy className="w-3 h-3 text-amber-400 inline ml-1" />}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {r.is_base ? (
                      <Minus className="w-3 h-3 text-zinc-600 mx-auto" />
                    ) : (
                      <span className={`font-mono flex items-center justify-end gap-0.5 ${
                        deltaGood ? "text-emerald-400" : "text-red-400"
                      }`}>
                        {deltaGood ? "+" : ""}{r.delta_score.toFixed(0)}
                        {deltaGood ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />}
                      </span>
                    )}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono ${
                    isBestAff ? "text-cyan-400 font-semibold" : "text-zinc-400"
                  }`}>
                    {r.affinity_kcal?.toFixed(1) || "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {r.is_base ? (
                      <Minus className="w-3 h-3 text-zinc-600 mx-auto" />
                    ) : (
                      <span className={`font-mono ${
                        r.delta_affinity < 0 ? "text-emerald-400" :
                        r.delta_affinity > 0 ? "text-red-400" : "text-zinc-500"
                      }`}>
                        {r.delta_affinity > 0 ? "+" : ""}{r.delta_affinity.toFixed(1)}
                      </span>
                    )}
                  </td>
                  {!compact && (
                    <>
                      <td className="px-3 py-2 text-right font-mono text-zinc-500">
                        {r.molecular_weight?.toFixed(0) || "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-zinc-500">
                        {r.log_p?.toFixed(1) || "—"}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.lipinski_pass ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mx-auto" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-red-400 mx-auto" />
                        )}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {r.is_pains ? (
                          <AlertTriangle className="w-3.5 h-3.5 text-red-400 mx-auto" />
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] text-zinc-500">
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-violet-500/20 border border-violet-500/20" /> Baseline
        </span>
        <span className="flex items-center gap-1">
          <Trophy className="w-3 h-3 text-amber-400" /> Best in class
        </span>
        <span className="flex items-center gap-1 text-emerald-400">
          <ArrowUp className="w-2.5 h-2.5" /> Mejora vs baseline
        </span>
        <span className="flex items-center gap-1 text-red-400">
          <ArrowUp className="w-2.5 h-2.5 rotate-180" /> Empeora vs baseline
        </span>
      </div>
    </div>
  );
}
