"use client";


import { useLanguage } from "@/context/LanguageContext";
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
  const { t } = useLanguage();
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
            <h4 className="text-sm font-semibold text-zinc-200">{t("pn_drug_likeness")}</h4>
            <p className="text-xs text-zinc-400">
              {eduScore >= 4 ? t("auto_f3837875dab4") :
               eduScore >= 2 ? t("auto_ed428b8dc80c") :
               t("auto_32e8785f56fe")}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-zinc-400">
          <div>{t("pn_peso_molecular_lipinski")}</div>
          <div>LogP: {lipinski ? t("auto_9a3561c18fde") : t("auto_b05b976cbc9e")}</div>
          <div>{t("auto_2eeb74fb3700")} {veber ? t("auto_4696a2a82a01") : t("auto_715e0e63b8f6")}</div>
          <div>{t("auto_ccc606b7ab22")} {lipinski ? t("auto_0e4b9698dddb") : t("auto_2ccc163e69dd")}</div>
        </div>

        {isPains && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-red-400">Alerta PAINS</p>
              <p className="text-xs text-red-300/80">
                {t("pn_pains_detectado")}
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
      <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">{t("auto_b328f2a763d4")}</h4>

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
            <span className="text-zinc-400">{t("auto_15ba7664a979")}</span>
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
            {fsp3 > 0.45 ? t("auto_a9b6fb847654") :
             fsp3 > 0.35 ? t("auto_6a63c09b0f68") :
             t("auto_60cb989d5e68")}
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
              {t("auto_0f9586a7aac1")} {painsMatches?.length || 0} patrones detectados
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
            {t("auto_cd20267c5ed3")}
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-xs text-emerald-400">{t("pn_sin_pains")}</span>
        </div>
      )}
    </div>
  );
}
