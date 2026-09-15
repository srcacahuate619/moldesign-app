
import { useLanguage } from "@/context/LanguageContext";
import React from "react";
import { Check, Info, Settings, Play, CheckCircle2, Circle, AlertCircle, Loader2, ChevronUp, ChevronDown } from "lucide-react";

export interface StageInfo {
  id: string;
  label: string;
  description: string;
  required: boolean;
  enabled: boolean;
  cost_estimate: string;
  params: Record<string, any>;
}

export type StageStatus = "idle" | "running" | "done" | "error";

interface StageCardProps {
  stage: StageInfo;
  status: StageStatus;
  progress?: number; 
  durationMs?: number;
  error?: string;
  onToggle: () => void;
  onParamChange: (paramName: string, value: any) => void;
  disabled?: boolean;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  isFirst?: boolean;
  isLast?: boolean;
  showReorderControls?: boolean;
}

export function StageCard({
  stage,
  status,
  progress,
  durationMs,
  error,
  onToggle,
  onParamChange,
  disabled,
  onMoveUp,
  onMoveDown,
  isFirst = false,
  isLast = false,
  showReorderControls = false
}: StageCardProps) {
  const { t } = useLanguage();
  return (
    <div className={`border ${status === 'running' ? 'border-indigo-500/50 bg-indigo-500/5' : status === 'error' ? 'border-red-500/50 bg-red-500/5' : 'border-zinc-800 bg-black'} rounded-xl p-3.5 transition-all duration-300 relative group/card`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3 flex-1">
          {/* Checkbox Toggle */}
          <button 
            disabled={stage.required || disabled}
            onClick={onToggle}
            className={`mt-0.5 w-4 h-4 flex items-center justify-center rounded-md border transition-all duration-200 ${
              stage.enabled 
                ? 'border-indigo-500/60 bg-indigo-500/20 text-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.15)]' 
                : 'border-zinc-700 hover:border-zinc-500 text-transparent'
            } ${(stage.required || disabled) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            {stage.enabled && <Check size={12} strokeWidth={2.5} />}
          </button>
          
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className={`text-[13px] font-bold uppercase tracking-wider transition-colors duration-200 ${stage.enabled ? 'text-zinc-200 font-mono' : 'text-zinc-600'}`}>
                {stage.label}
              </span>
              {stage.required && (
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-indigo-950/40 border border-indigo-500/20 text-indigo-400">
                  Obligatorio
                </span>
              )}
            </div>
            <span className="text-xs text-zinc-500 mt-1 max-w-[320px] leading-relaxed">
              {stage.description}
            </span>
          </div>
        </div>

        {/* Reordering Controls (Only in Manual Mode, if showReorderControls is true) */}
        {showReorderControls && !disabled && (
          <div className="flex items-center gap-1 border border-zinc-800 bg-zinc-950/60 p-0.5 rounded-lg opacity-40 group-hover/card:opacity-100 transition-opacity">
            <button
              onClick={onMoveUp}
              disabled={isFirst}
              title="Mover arriba"
              className={`p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-800 disabled:opacity-20 disabled:hover:bg-transparent transition-all cursor-pointer`}
            >
              <ChevronUp size={12} />
            </button>
            <button
              onClick={onMoveDown}
              disabled={isLast}
              title="Mover abajo"
              className={`p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-800 disabled:opacity-20 disabled:hover:bg-transparent transition-all cursor-pointer`}
            >
              <ChevronDown size={12} />
            </button>
          </div>
        )}

        <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
          <span className={`text-[11px] font-mono uppercase px-1.5 py-0.5 rounded-sm border ${
            stage.cost_estimate === 'Alto' || stage.cost_estimate === 'Muy Alto' 
              ? 'border-orange-500/30 text-orange-400 bg-orange-500/10' 
              : 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
          }`}>
            {t("auto_88219203d937")} {stage.cost_estimate}
          </span>
          {status === 'running' && (
            <span className="flex items-center gap-1 text-xs font-mono text-indigo-400 font-bold animate-pulse">
              <Loader2 size={10} className="animate-spin" /> PROCESANDO
            </span>
          )}
          {status === 'done' && (
            <span className="flex items-center gap-1 text-xs font-mono text-emerald-400 font-bold">
              <CheckCircle2 size={10} /> {durationMs ? `${(durationMs/1000).toFixed(1)}s` : 'OK'}
            </span>
          )}
          {status === 'error' && (
            <span className="flex items-center gap-1 text-xs font-mono text-red-400 font-bold">
              <AlertCircle size={10} /> FALLO
            </span>
          )}
        </div>
      </div>
      
      {/* Parameters configuration if enabled and has params */}
      {stage.enabled && Object.keys(stage.params).length > 0 && (
        <div className="mt-3.5 pt-3.5 border-t border-zinc-900/60">
          <div className="flex items-center gap-1.5 mb-2.5">
            <Settings size={10} className="text-zinc-500" />
            <span className="text-[11px] uppercase tracking-widest text-zinc-500 font-bold font-mono">{t("z_config_parametros")}</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(stage.params).map(([k, v]) => (
              <div key={k} className="flex flex-col gap-1">
                <label className="text-[11px] font-mono text-zinc-500 uppercase">{k.replace('_', ' ')}</label>
                <input 
                  type={typeof v === 'number' ? 'number' : 'text'}
                  disabled={disabled}
                  value={v}
                  onChange={(e) => onParamChange(k, typeof v === 'number' ? Number(e.target.value) : e.target.value)}
                  className="bg-[#03060c] border border-white/5 text-xs px-2.5 py-1.5 font-mono text-zinc-300 w-full focus:border-indigo-500/40 outline-none rounded-lg transition-all"
                />
              </div>
            ))}
          </div>
        </div>
      )}
      
      {error && (
        <div className="mt-3.5 text-[10px] font-mono text-red-400 bg-red-950/20 p-2 border border-red-900/30 rounded-lg">
          {error}
        </div>
      )}
    </div>
  );
}

