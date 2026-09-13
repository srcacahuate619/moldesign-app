"use client";

import React from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, Info } from "lucide-react";

interface DrugLikenessProps {
  lipinski: boolean;
  veber: boolean;
  ghose?: boolean | null;
  egan?: boolean | null;
  muegge?: boolean | null;
  mueggeScore?: number | null;
  fsp3?: number | null;
  qed?: number | null;
  saScore?: number | null;
  isPains?: boolean | null;
  painsMatches?: Array<{ name: string; description: string }> | null;
  mode: "edu" | "pro";
}

const RuleBadge: React.FC<{ pass: boolean; label: string; detail?: string }> = ({ pass, label, detail }) => (
  <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium ${
    pass ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
         : "bg-red-500/10 text-red-400 border border-red-500/20"
  }`}>
    {pass ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
    <span>{label}</span>
    {detail && <span className="text-zinc-500 font-mono">{detail}</span>}
  </div>
);

export function DrugLikenessPanel({
  lipinski, veber, ghose, egan, muegge, mueggeScore,
  fsp3, qed, saScore, isPains, painsMatches, mode
}: DrugLikenessProps) {
  const eduScore = [lipinski, veber, ghose, egan, muegge].filter(Boolean).length;

  if (mode === "edu") {
    return (
      <div className="space-y-3 p-4 rounded-xl bg-zinc-800/50 border border-zinc-700/50">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
            eduScore >= 4 ? "bg-emerald-500/20" : eduScore >= 2 ? "bg-amber-500/20" : "bg-red-500/20"
          }`}>
            <span className={`text-sm font-bold ${
              eduScore >= 4 ? "text-emerald-400" : eduScore >= 2 ? "text-amber-400" : "text-red-400"
            }`}>{eduScore}/5</span>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-zinc-200">Perfil de reglas de drug-likeness</h4>
            <p className="text-xs text-zinc-400">
              {eduScore >= 4 ? "Alto — cumple la mayoría de estas reglas heurísticas" :
               eduScore >= 2 ? "Intermedio — cumple parte de estas reglas heurísticas" :
               "Bajo — varias reglas heurísticas no se cumplen"}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-zinc-400">
          <div>Peso molecular: se evalúa en Lipinski/Ghose</div>
          <div>LogP: {lipinski ? "dentro de Lipinski" : "fuera de Lipinski"}</div>
          <div>Flexibilidad: {veber ? "dentro de Veber" : "fuera de Veber"}</div>
          <div>Ro5 de Lipinski: {lipinski ? "dentro del umbral" : "fuera del umbral"}</div>
        </div>

        {isPains && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-red-400">Alerta PAINS</p>
              <p className="text-xs text-red-300/80">
                Esta molécula contiene subestructuras que suelen dar falsos positivos en experimentos.
                Se recomienda validación adicional antes de considerarla un hallazgo real.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── PRO mode: full breakdown ──────────────────────────────────────
  return (
    <div className="space-y-3">
      <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Drug-Likeness & Filtros</h4>

      <div className="flex flex-wrap gap-2">
        <RuleBadge pass={lipinski} label="Lipinski Ro5" detail="MW<=500, LogP<=5, HBD<=5, HBA<=10" />
        <RuleBadge pass={veber} label="Veber" detail="RotB<=10, TPSA<=140" />
        {ghose !== null && ghose !== undefined && <RuleBadge pass={ghose} label="Ghose" detail="MW 160-480, LogP -0.4/5.6, atoms 20-70" />}
        {egan !== null && egan !== undefined && <RuleBadge pass={egan} label="Egan" detail="TPSA<=132, LogP -1/5.88" />}
        {muegge !== null && muegge !== undefined && <RuleBadge pass={muegge} label="Muegge" detail={`Score ${mueggeScore}/9`} />}
      </div>

      {/* Fsp3 gauge */}
      {fsp3 !== null && fsp3 !== undefined && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-400">Fsp³ (carbonos sp³)</span>
            <span className="font-mono text-zinc-300">{fsp3.toFixed(3)}</span>
          </div>
          <div className="h-2 rounded-full bg-zinc-700 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                fsp3 > 0.45 ? "bg-emerald-500" : fsp3 > 0.35 ? "bg-amber-500" : "bg-red-500"
              }`}
              style={{ width: `${Math.min(fsp3 * 200, 100)}%` }}
            />
          </div>
          <p className="text-[10px] text-zinc-500">
            {fsp3 > 0.45 ? "Mayor proporción sp³ — descriptor de complejidad" :
             fsp3 > 0.35 ? "Proporción sp³ intermedia" :
             "Menor proporción sp³ — descriptor; no predice promiscuidad"}
            {" "}(Lovering 2009)
          </p>
        </div>
      )}

      {/* QED gauge */}
      {qed !== null && qed !== undefined && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-400">QED (drug-likeness cuantitativo)</span>
            <span className="font-mono text-zinc-300">{qed.toFixed(3)}</span>
          </div>
          <div className="h-2 rounded-full bg-zinc-700 overflow-hidden">
            <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${(qed || 0) * 100}%` }} />
          </div>
        </div>
      )}

      {/* SA Score */}
      {saScore !== null && saScore !== undefined && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-400">SA Score (accesibilidad sintetica)</span>
            <span className="font-mono text-zinc-300">{(saScore ?? 0).toFixed(1)}/10</span>
          </div>
          <div className="h-2 rounded-full bg-zinc-700 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                (saScore || 10) < 3 ? "bg-emerald-500" : (saScore || 10) < 6 ? "bg-amber-500" : "bg-red-500"
              }`}
              style={{ width: `${100 - ((saScore || 0) * 10)}%` }}
            />
          </div>
        </div>
      )}

      {/* PAINS Alert */}
      {isPains ? (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 space-y-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span className="text-xs font-semibold text-red-400">
              ALERTA PAINS — {painsMatches?.length || 0} patrones detectados
            </span>
          </div>
          {painsMatches && painsMatches.length > 0 && (
            <div className="space-y-1">
              {painsMatches.map((m, i) => (
                <div key={i} className="text-[10px] text-red-300/80 leading-relaxed">
                  <span className="font-mono text-red-400">{m.name}</span>: {m.description}
                </div>
              ))}
            </div>
          )}
          <p className="text-[10px] text-red-400/60">
            Los PAINS son falsos positivos frecuentes en ensayos biologicos (Baell & Holloway, 2010).
            Se recomienda validación experimental exhaustiva antes de considerar esta molécula como hit.
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-xs text-emerald-400">Sin patrón PAINS detectado (no descarta actividad ni riesgo)</span>
        </div>
      )}
    </div>
  );
}
