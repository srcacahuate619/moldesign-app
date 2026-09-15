
import { useLanguage } from "@/context/LanguageContext";
import { Save, ShieldCheck, FileText, Download, Eye } from "lucide-react";
import { useState } from "react";

import { ExternalLink } from "@/components/ui/ExternalLink";
type ScoreBarProps = {
  label: string;
  value: number | null;
  weight?: string;
  color: string;
  onClick?: () => void;
};

function ScoreBar({ label, value, weight, color, onClick }: ScoreBarProps) {
  const display = value !== null && value !== undefined ? value.toFixed(1) : "—";
  const pct = value !== null && value !== undefined ? Math.max(0, Math.min(100, value)) : 0;

  const content = (
    <div className="space-y-1.5 w-full text-left group">
      <div className="flex items-center justify-between text-sm">
        <span>
          <span className="font-semibold text-zinc-900 dark:text-zinc-200 transition-colors group-hover:text-zinc-950 dark:group-hover:text-white">{label}</span>
          {weight && <span className="ml-1 text-zinc-400">({weight})</span>}
        </span>
        <span className="tabular-nums font-mono text-zinc-500 dark:text-zinc-400">{display}/100</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
        <div
          className="score-bar-fill h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );

  if (onClick) {
    return (
      <button 
        type="button" 
        onClick={onClick} 
        className="block w-full hover:bg-zinc-50 dark:hover:bg-zinc-900/50 p-2.5 -mx-2.5 rounded-lg transition-colors"
      >
        {content}
      </button>
    );
  }

  return content;
}

type ScoreCardProps = {
  totalScore: number | null;
  affinity: number | null;
  affinityKcal: number | null;
  adme: number | null;
  druglikeness: number | null;
  ligandEfficiency?: number | null;
  onCertify?: () => void;
  onSave?: (customName?: string) => void;
  isSaved?: boolean;
  solanaSignature?: string | null;
  onDownloadCertificate?: () => void;
  onViewCertificate?: () => void;
  onDownloadComplex?: () => void;
  isControl?: boolean;
  saScore?: number | null;
  saReasons?: string[] | null;
  rawVinaKcal?: number | null;
  rawXgboostKcal?: number | null;
  lipophilicEfficiency?: number | null;
  specificity?: number | null;
  affinityMultiplier?: number | null;
  specificityMultiplier?: number | null;
  gnnScore?: number | null;
  quantumScore?: number | null;
  bloodViabilityScore?: number | null;
  bloodSystemicReactivity?: string[] | null;
  gnnFactor?: number | null;
  saFactor?: number | null;
  bloodFactor?: number | null;
  [key: string]: any;
};

export function ScoreCard({
  totalScore,
  affinity,
  affinityKcal,
  adme,
  druglikeness,
  ligandEfficiency,
  onCertify,
  onSave,
  isSaved = false,
  solanaSignature,
  onDownloadCertificate,
  onViewCertificate,
  onDownloadComplex,
  isControl = false,
  saScore,
  saReasons,
  rawVinaKcal,
  rawXgboostKcal,
  lipophilicEfficiency,
  specificity,
  affinityMultiplier,
  specificityMultiplier,
  gnnScore,
  quantumScore,
  bloodViabilityScore,
  bloodSystemicReactivity,
  gnnFactor,
  saFactor,
  bloodFactor,
}: ScoreCardProps) {
  const { t } = useLanguage();
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  const [customName, setCustomName] = useState("");
  const [selectedEducationalMetric, setSelectedEducationalMetric] = useState<{title: string, desc: React.ReactNode, icon?: string, math?: React.ReactNode} | null>(null);

  const totalDisplay =
    totalScore !== null && totalScore !== undefined
      ? totalScore.toFixed(1)
      : "—";

  const scoreColor =
    totalScore !== null && totalScore >= 70
      ? "text-zinc-900 dark:text-white"
      : totalScore !== null && totalScore >= 40
        ? "text-zinc-600 dark:text-zinc-300"
        : "text-zinc-400 dark:text-zinc-500";

  let tier = "D";
  let tierStyle = "border-zinc-200 dark:border-zinc-800 text-zinc-500 bg-zinc-50 dark:bg-zinc-900";
  
  if (totalScore !== null) {
    if (totalScore >= 85) {
      tier = "S";
      tierStyle = "border-zinc-900 dark:border-zinc-100 text-zinc-900 dark:text-zinc-100 font-bold bg-zinc-100 dark:bg-zinc-800";
    } else if (totalScore >= 70) {
      tier = "A";
      tierStyle = "border-zinc-500 dark:border-zinc-400 text-zinc-700 dark:text-zinc-300 font-semibold bg-zinc-50 dark:bg-zinc-900";
    } else if (totalScore >= 55) {
      tier = "B";
      tierStyle = "border-zinc-300 dark:border-zinc-600 text-zinc-600 dark:text-zinc-400 bg-transparent";
    } else if (totalScore >= 40) {
      tier = "C";
      tierStyle = "border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-500 bg-transparent";
    }
  }

  return (
    <section className="flex flex-col border-b border-zinc-100 dark:border-zinc-850 pb-6">
      <div className="p-6 sm:p-8 flex-1 space-y-8">
        <header className="space-y-2 border-b border-zinc-100 dark:border-zinc-900 pb-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-white">{t("pn_puntuacion")}</h3>
            <span className={`text-4xl font-mono tracking-tighter tabular-nums ${scoreColor}`}>
              {totalDisplay}
            </span>
          </div>
          <div className="flex items-center gap-3">
            {totalScore !== null && (
              <span className={`inline-flex items-center justify-center h-6 w-6 rounded border text-[11px] uppercase ${tierStyle}`}>
                {tier}
              </span>
            )}
            <p className="text-[11px] leading-relaxed text-zinc-500 max-w-[280px]">
              {t("pn_heuristica_compuesta")}
            </p>
          </div>
        </header>

        <div className="space-y-4">
          <ScoreBar 
            label="Afinidad" 
            value={affinity} 
            weight="45%" 
            color="#52525b" // zinc-600
            onClick={() => setSelectedEducationalMetric({
              title: t("auto_73dfe1bf7b4c"),
              icon: "🧲",
              desc: t("auto_383ad4c4bf5b"),
              math: t("auto_703e06c21c31")
            })}
          />
          
          {!isControl ? (
            <>
              {/* Auditoría 2026-09-04. Se llamaba «Viabilidad Sanguínea» y
                  la explicación decía «qué tan probable es que tu molécula
                  sobreviva en la sangre y órganos sin causar toxicidad fatal».
                  No es eso: es la media geométrica de tres factores con
                  constantes elegidas a mano, sin ajuste contra datos clínicos.
                  Ver `chem/blood_viability.py`. */}
              {bloodViabilityScore !== undefined && (
                <ScoreBar 
                  label={t("z_perfil_sanguineo")}
                  value={bloodViabilityScore} 
                  color="#5f5f68" 
                  onClick={() => setSelectedEducationalMetric({
                    title: t("auto_52fba8403909"),
                    icon: "🩸",
                    desc: t("auto_2528775f013b")
                  })}
                />
              )}
              <ScoreBar 
                label="ADME" 
                value={adme} 
                weight="30%" 
                color="#71717a" // zinc-500
                onClick={() => setSelectedEducationalMetric({
                  title: "Perfil ADME",
                  icon: "🩸",
                  desc: t("auto_29368dd6d018")
                })}
              />
              <ScoreBar 
                label="Drug-likeness" 
                value={druglikeness} 
                weight="25%" 
                color="#a1a1aa" // zinc-400
                onClick={() => setSelectedEducationalMetric({
                  title: t("auto_e9d629f451ad"),
                  icon: "💊",
                  desc: t("auto_15eb472d4323"),
                  math: t("auto_b3db787af1a3")
                })}
              />
              {specificity !== null && specificity !== undefined && (
                <ScoreBar 
                  label="Especificidad" 
                  value={specificity} 
                  color="#d4d4d8" // zinc-300
                  onClick={() => setSelectedEducationalMetric({
                    title: t("auto_4cce270ad33f"),
                    icon: "🎯",
                    desc: t("auto_29f1a0264265")
                  })}
                />
              )}
            </>
          ) : (
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 p-4 text-center">
              <div className="text-xs font-bold text-zinc-900 dark:text-white uppercase tracking-widest mb-1.5">Control Mode</div>
              <p className="text-[11px] text-zinc-500 leading-relaxed max-w-xs mx-auto">
                {t("auto_c2644ddf403e")}
              </p>
            </div>
          )}
        </div>

        {/* Detailed Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-zinc-100 dark:border-zinc-900">
          {affinityKcal !== null && affinityKcal !== undefined && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Afinidad Bruta</span>
              <span className="text-sm font-mono text-zinc-900 dark:text-zinc-300">{affinityKcal.toFixed(3)} kcal/mol</span>
            </div>
          )}
          {ligandEfficiency !== null && ligandEfficiency !== undefined && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">{t("pn_ef_ligando")}</span>
              <span className="text-sm font-mono text-zinc-900 dark:text-zinc-300">{ligandEfficiency.toFixed(3)}</span>
            </div>
          )}
          {lipophilicEfficiency !== null && lipophilicEfficiency !== undefined && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Lipophilic Eff.</span>
              <span className="text-sm font-mono text-zinc-900 dark:text-zinc-300">{lipophilicEfficiency.toFixed(3)}</span>
            </div>
          )}
          {gnnScore !== null && gnnScore !== undefined && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">GNN RTMScore</span>
              <span className="text-sm font-mono text-zinc-900 dark:text-zinc-300">{gnnScore.toFixed(2)}</span>
            </div>
          )}
          {quantumScore !== null && quantumScore !== undefined && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">QUANTUM (xTB)</span>
              <span className="text-sm font-mono text-zinc-900 dark:text-zinc-300">{quantumScore.toFixed(2)}</span>
            </div>
          )}
          {saScore !== null && saScore !== undefined && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-400">Synth. Access</span>
              <span className="text-sm font-mono text-zinc-900 dark:text-zinc-300">{saScore.toFixed(2)} {saScore > 6.0 ? t("auto_9ed23929f2df") : ""}</span>
            </div>
          )}
        </div>

        {/* Warnings */}
        {(saScore && saScore > 6.0 && saReasons && saReasons.length > 0 || bloodSystemicReactivity && bloodSystemicReactivity.length > 0) && (
          <div className="space-y-3 pt-4 border-t border-zinc-100 dark:border-zinc-900">
            {saScore && saScore > 6.0 && saReasons && saReasons.length > 0 && (
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 p-3">
                <div className="text-[10px] font-bold text-zinc-900 dark:text-white uppercase tracking-widest mb-2">Synth Invalid</div>
                <ul className="space-y-1.5">
                  {saReasons.map((reason, idx) => (
                    <li key={idx} className="text-[11px] text-zinc-600 dark:text-zinc-400">• {reason}</li>
                  ))}
                </ul>
              </div>
            )}
            {bloodSystemicReactivity && bloodSystemicReactivity.length > 0 && (
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 p-3">
                <div className="text-[10px] font-bold text-zinc-900 dark:text-white uppercase tracking-widest mb-2">Tox Alert</div>
                <ul className="space-y-1.5">
                  {bloodSystemicReactivity.map((reason, idx) => (
                    <li key={idx} className="text-[11px] text-zinc-600 dark:text-zinc-400">• {reason}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Actions Footer */}
      <div className="bg-zinc-50 dark:bg-zinc-900/30 p-6 sm:p-8 border-t border-zinc-200 dark:border-zinc-800">
        {isSavingPrompt ? (
          <div className="space-y-4">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-widest text-zinc-500 mb-2">Identifier</label>
              <input 
                type="text" 
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="MDX-7E2Y-51D1"
                className="w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-2.5 text-sm text-zinc-900 dark:text-white focus:border-zinc-900 dark:focus:border-zinc-100 focus:outline-none focus:ring-1 focus:ring-zinc-900 dark:focus:ring-zinc-100 transition-colors"
              />
            </div>
            <div className="flex gap-3">
              <button 
                onClick={() => setIsSavingPrompt(false)}
                className="flex-1 rounded-xl py-3 text-xs font-semibold text-zinc-600 dark:text-zinc-400 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 hover:text-zinc-900 dark:hover:text-white transition-colors"
              >
                {t("c_cancelar")}
              </button>
              <button 
                onClick={() => {
                  if (onSave) onSave(customName.trim() || undefined);
                  setIsSavingPrompt(false);
                }}
                className="flex-1 rounded-xl bg-zinc-900 dark:bg-white py-3 text-xs font-semibold text-white dark:text-zinc-900 transition-transform active:scale-[0.98]"
              >
                Save Protocol
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 pt-2.5">
            {/* 1. View Report */}
            {onDownloadCertificate && onViewCertificate && (
              <button
                onClick={onViewCertificate}
                className="flex items-center justify-center rounded-lg border border-white/5 bg-black/40 hover:bg-slate-800/80 text-slate-300 h-9 text-[9px] font-bold uppercase tracking-wider font-mono transition-all duration-150 active:scale-[0.98]"
              >
                <Eye size={12} className="mr-1.5" />
                {t("z_ver_informe")}
              </button>
            )}

            {/* 2. Download Report PDF */}
            {onDownloadCertificate && (
              <button
                onClick={onDownloadCertificate}
                className="flex items-center justify-center rounded-lg border border-indigo-500/20 bg-[#090b14]/50 hover:bg-indigo-950/20 hover:border-indigo-500/40 text-indigo-300 h-9 text-[9px] font-bold uppercase tracking-wider font-mono transition-all duration-150 active:scale-[0.98]"
              >
                <FileText size={12} className="mr-1.5" />
                {t("z_descargar_pdf")}
              </button>
            )}

            {/* 3. Save Protocol / Moldex */}
            {onSave && (
              <button
                onClick={() => setIsSavingPrompt(true)}
                disabled={isSaved}
                className={`flex items-center justify-center rounded-lg border h-9 text-[9px] font-bold uppercase tracking-wider font-mono transition-all duration-150 ${
                  isSaved
                    ? "cursor-not-allowed bg-zinc-900/40 text-slate-500 border-white/5 opacity-60"
                    : "bg-[#090b14]/50 border-indigo-500/20 hover:border-indigo-500/40 text-indigo-300 hover:text-indigo-200 hover:bg-indigo-950/20 active:scale-[0.98]"
                }`}
              >
                <Save size={12} className="mr-1.5" />
                {isSaved ? t("z_guardado_moldex") : t("z_guardar_moldex")}
              </button>
            )}

            {/* 4. Certify in Blockchain */}
            {solanaSignature ? (
              <ExternalLink
                href={`https://explorer.solana.com/tx/${solanaSignature}?cluster=devnet`}
                className="flex items-center justify-center gap-1.5 rounded-lg border border-emerald-500/25 bg-emerald-950/20 hover:bg-emerald-900/25 text-emerald-400 h-9 text-[9px] font-bold uppercase tracking-wider font-mono transition-all duration-150"
              >
                <ShieldCheck size={12} />
                {t("z_verificado_solana")}
              </ExternalLink>
            ) : onCertify ? (
              <button
                onClick={onCertify}
                className="flex items-center justify-center rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white h-9 text-[9px] font-bold uppercase tracking-wider font-mono border border-indigo-500/40 hover:border-indigo-400/60 shadow-[0_0_15px_rgba(99,102,241,0.25)] hover:shadow-[0_0_20px_rgba(99,102,241,0.35)] transition-all duration-150 active:scale-[0.98]"
              >
                <ShieldCheck size={12} className="mr-1.5" />
                {t("z_registrar_blockchain")}
              </button>
            ) : null}

            {/* 5. Download PDB Complex (Full width, col-span-2) */}
            {onDownloadComplex && (
              <button
                onClick={onDownloadComplex}
                className="col-span-2 flex items-center justify-center rounded-lg border border-white/5 bg-black/55 hover:bg-slate-800/90 text-slate-400 hover:text-slate-200 h-9 text-[9px] font-bold uppercase tracking-wider font-mono transition-all duration-150 active:scale-[0.98]"
              >
                <Download size={12} className="mr-1.5" />
                {t("z_descargar_complejo_pdb")}
              </button>
            )}

            {!onSave && !onCertify && !solanaSignature && (
              <p className="text-[11px] text-zinc-500 text-center mt-2">
                <a href="/login" className="font-semibold text-zinc-900 dark:text-white hover:underline underline-offset-4">{t("pn_inicia_sesion")}</a> {t("pn_para_guardar")}
              </p>
            )}
          </div>
        )}
      </div>

      {selectedEducationalMetric && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-white/80 dark:bg-[#0a0a0a]/80 backdrop-blur-md"
          onClick={() => setSelectedEducationalMetric(null)}
        >
          <div 
            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 max-w-md w-full shadow-2xl relative text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedEducationalMetric(null)}
              className="absolute top-6 right-6 text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="mb-6">
              <h3 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-white">{selectedEducationalMetric.title}</h3>
            </div>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
              {selectedEducationalMetric.desc}
            </p>
            {selectedEducationalMetric.math && (
              <div className="mt-6 bg-zinc-50 dark:bg-zinc-950 rounded-xl p-4 border border-zinc-100 dark:border-zinc-800 text-[11px] font-mono leading-relaxed text-zinc-700 dark:text-zinc-300">
                {selectedEducationalMetric.math}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
