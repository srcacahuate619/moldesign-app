
import { Translated, useLanguage } from "@/context/LanguageContext";
import React, { memo, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Microscope, Activity, ShieldCheck, ShieldAlert, Zap } from 'lucide-react';
import { getApiUrl } from '../lib/config';
import { leerSello, type MoldexMolecule } from '../lib/moldex';

interface MoldexCardProps {
  molecule: MoldexMolecule;
  onClick: (id: string) => void;
  isSelected: boolean;
  onCompareToggle: (id: string) => void;
  isComparing: boolean;
}

const MoldexCard: React.FC<MoldexCardProps> = memo(function MoldexCard({ molecule, onClick, isSelected, onCompareToggle, isComparing }) {
  const { t } = useLanguage();
  const [imgSrc, setImgSrc] = useState<string | undefined>(undefined);
  
  useEffect(() => {
    let active = true;
    let url: string | undefined = undefined;

    const headers: Record<string, string> = {
      "ngrok-skip-browser-warning": "true"
    };
    try {
      const stored = localStorage.getItem("moldesign_auth");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.token) {
          headers["Authorization"] = `Bearer ${parsed.token}`;
        }
      }
    } catch (e) {}

    getApiUrl()
      .then((base) => fetch(`${base}/chem/render/${molecule.id}`, { headers }))
      .then(res => {
        if (!res.ok) throw new Error("Image fetch failed");
        return res.blob();
      })
      .then(blob => {
        if (active) {
          url = URL.createObjectURL(blob);
          setImgSrc(url);
        }
      })
      .catch(() => {
        if (active) {
          setImgSrc("");
        }
      });

    return () => {
      active = false;
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [molecule.id]);

  const scoreBadgeClass = "text-indigo-300 border-indigo-500/30 bg-indigo-500/10";
  const score = molecule.metrics?.score ?? null;
  const targetBasedName = `MDX-${molecule.target?.pdb_id || "UKN"}-${molecule.smiles_hash.substring(0,4).toUpperCase()}`;
  const isDefaultName = !molecule.name || molecule.name.startsWith("Ligando ");
  const displayName = isDefaultName ? targetBasedName : molecule.name;

  return (
    <motion.div
      whileHover={{ y: -5, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => onClick(molecule.id)}
      className={`relative cursor-pointer rounded-2xl border p-4 transition-all duration-300 ${
        isSelected 
          ? 'border-indigo-500 bg-indigo-500/20 shadow-[0_0_20px_rgba(99,102,241,0.3)]' 
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/80'
      }`}
    >
      {/* El índice histórico no se convierte en un rango gamificado. */}
      <div className={`absolute top-3 left-3 flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-black tracking-widest border ${
        score !== null
          ? "text-indigo-300 border-indigo-500/30 bg-indigo-500/10"
          : "text-slate-500 border-slate-700 bg-slate-800/60"
      }`}>
        {score !== null ? t("auto_62b3b773ed35") : t("auto_a9b0c58ab88e")}
      </div>
      {/* Badge de Target */}
      <div className="absolute top-3 right-3 flex items-center gap-1 rounded-full bg-slate-950/80 px-2 py-0.5 text-[10px] font-bold tracking-wider text-slate-400 border border-slate-700">
        <Microscope size={10} />
        {molecule.target?.pdb_id || "N/A"}
      </div>

      <div className="mb-4 flex h-32 items-center justify-center rounded-xl bg-white p-4 shadow-inner relative overflow-hidden group/img">
        {/* Render 2D de la molécula real */}
        {imgSrc ? (
          <img 
            src={imgSrc}
            alt={molecule.name}
            className="h-full w-auto object-contain transition-transform duration-500 group-hover/img:scale-110"
            loading="lazy"
          />
        ) : imgSrc === undefined ? (
          <div className="flex flex-col items-center justify-center gap-1.5">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
            <span className="text-[8px] font-black uppercase tracking-wider text-slate-400">Generando 2D...</span>
          </div>
        ) : (
          <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider"><Translated id="z_sin_vista_previa" /></div>
        )}
        
        <div className="absolute bottom-2 right-2 bg-slate-900/80 backdrop-blur-md px-2 py-1 rounded text-[9px] font-mono font-bold text-slate-300 border border-slate-700/50 shadow-sm">
          {targetBasedName}
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="truncate text-sm font-bold text-slate-100">{displayName}</h3>
        
        <div className="flex items-center justify-between">
          {/* Un score ausente no es 0.0: se dice que falta. */}
          <div className={`flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold ${score !== null ? scoreBadgeClass : 'text-slate-500 border-slate-700 bg-slate-800/60'}`}>
            <Zap size={12} fill="currentColor" />
            {score !== null ? score.toFixed(1) : "—"}
          </div>
          
          {/* MOLDEX-SCI-001: la insignia sólo puede afirmar «certificado» a
              secas cuando el sello describe la corrida que la ficha muestra.
              Si la molécula se reevaluó después, o el sello es anterior al
              registro de procedencia, se dice exactamente eso. */}
          {(() => {
            const lectura = leerSello(molecule.blockchain);
            if (lectura === "sin-sello") return null;
            if (lectura === "vigente") {
              return (
                <div className="flex items-center gap-1 text-[10px] font-bold text-indigo-400">
                  <ShieldCheck size={12} />
                  CERTIFICADO
                </div>
              );
            }
            const esAnterior = lectura === "corrida-anterior";
            return (
              <div
                className="flex items-center gap-1 text-[10px] font-bold text-amber-400"
                title={
                  esAnterior
                    ? t("auto_57d409b275d3")
                    : t("auto_5a961ba823b3")
                }
              >
                <ShieldAlert size={12} />
                {esAnterior ? "SELLO DESFASADO" : t("auto_652200f9cc43")}
              </div>
            );
          })()}
        </div>

        <button 
          onClick={(e) => { e.stopPropagation(); onCompareToggle(molecule.id); }}
          className={`w-full mt-2 py-1 rounded-lg border text-[9px] font-black tracking-widest transition-all ${
            isComparing 
              ? 'bg-indigo-500 border-indigo-400 text-white' 
              : 'border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300'
          }`}
        >
          {isComparing ? t("auto_6f82b47554ca") : 'COMPARAR'}
        </button>
      </div>

      {isSelected && (
        <motion.div 
          layoutId="moldex-active-glow"
          className="absolute -inset-1 rounded-2xl bg-indigo-500/10 blur-xl -z-10"
        />
      )}
    </motion.div>
  );
});

export default MoldexCard;
