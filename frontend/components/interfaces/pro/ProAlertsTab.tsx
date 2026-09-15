"use client";


import { useLanguage } from "@/context/LanguageContext";
import React from "react";
import { CheckCircle2, AlertTriangle, AlertCircle, Info, HelpCircle } from "lucide-react";
import {
  normalizarAvisos,
  ordenarPorSeveridad,
  type AvisoDeclarado,
  type Severidad,
} from "../../../lib/avisos";

interface Props {
  /** `string[]` en corridas heredadas; `{codigo, severidad, mensaje}[]` desde
   *  que la severidad se declara en el backend. Ver `lib/avisos.ts`. */
  warnings: unknown;
  /** F-21: dominio de aplicabilidad del modelo (Mahalanobis). */
  inApplicabilityDomain?: boolean | null;
  /** F-21: "family" | "universal" | null (evaluaciones viejas). */
  modelUsed?: string | null;
}

interface EstiloDeAviso {
  cardStyle: string;
  icon: React.ReactNode;
  badge: string;
  badgeStyle: string;
  /** Explica la etiqueta cuando la etiqueta sola no basta. */
  pie?: string;
}

// ── Un estilo por severidad. Ni una sola búsqueda de subcadena ──────────
//
// Esto era `getAlertStyle(text)`, cuarenta líneas de `lower.includes(...)`.
// El fallo y su medición están documentados en `lib/avisos.ts`.
const ESTILO: Record<Severidad, EstiloDeAviso> = {
  positiva: {
    cardStyle: "bg-emerald-950/40 border-emerald-500/40 text-emerald-200 shadow-[0_0_15px_rgba(16,185,129,0.08)]",
    icon: <CheckCircle2 size={18} className="text-emerald-400 shrink-0 mt-0.5" />,
    badge: "DESTACADO POSITIVO",
    badgeStyle: "bg-emerald-500/25 text-emerald-300 border-emerald-500/40",
  },
  critica: {
    cardStyle: "bg-rose-950/40 border-rose-500/40 text-rose-200 shadow-[0_0_15px_rgba(244,63,94,0.08)]",
    icon: <AlertCircle size={18} className="text-rose-400 shrink-0 mt-0.5" />,
    badge: "ALERTA CRÍTICA",
    badgeStyle: "bg-rose-500/25 text-rose-300 border-rose-500/40",
  },
  precaucion: {
    cardStyle: "bg-amber-950/40 border-amber-500/40 text-amber-200 shadow-[0_0_15px_rgba(245,158,11,0.08)]",
    icon: <AlertTriangle size={18} className="text-amber-400 shrink-0 mt-0.5" />,
    badge: "PRECAUCIÓN",
    badgeStyle: "bg-amber-500/25 text-amber-300 border-amber-500/40",
  },
  info: {
    cardStyle: "bg-indigo-950/40 border-indigo-500/40 text-indigo-200 shadow-[0_0_15px_rgba(99,102,241,0.08)]",
    icon: <Info size={18} className="text-indigo-400 shrink-0 mt-0.5" />,
    badge: "NOTA CIENTÍFICA",
    badgeStyle: "bg-indigo-500/25 text-indigo-300 border-indigo-500/40",
  },
  // Sin color: una corrida anterior a la severidad declarada no dice cuánto
  // importa su aviso, y pintarlo de azul sería volver a decidirlo por ella.
  heredada: {
    cardStyle: "bg-white/[0.03] border-white/10 text-zinc-300",
    icon: <HelpCircle size={18} className="text-zinc-500 shrink-0 mt-0.5" />,
    badge: "Sin severidad declarada",
    badgeStyle: "bg-white/[0.06] text-zinc-400 border-white/15",
    pie: "Corrida anterior a la etapa que declara la severidad de cada aviso. El texto es el que emitió el motor; su importancia no se dedujo de él.",
  },
};

export function ProAlertsTab({ warnings, inApplicabilityDomain, modelUsed }: Props) {
  const { t } = useLanguage();
  // ── Alertas derivadas de los campos nuevos (F-21) ──────────────────────
  // NO duplican scientific_warnings: se derivan de la metadata del modelo
  // (in_applicability_domain / model_used) que no viaja en las warnings.
  const derivados: AvisoDeclarado[] = [];
  if (inApplicabilityDomain === false) {
    derivados.push({
      codigo: "FUERA_DE_DOMINIO",
      severidad: "precaucion",
      mensaje: "Fuera del dominio de aplicabilidad — interpretar con cautela.",
    });
  }
  if (modelUsed != null && modelUsed !== "family") {
    derivados.push({
      codigo: "MODELO_UNIVERSAL",
      severidad: "info",
      mensaje: "Modelo universal usado (familia con datos insuficientes).",
    });
  }

  const avisos = ordenarPorSeveridad([...derivados, ...normalizarAvisos(warnings)]);

  const renderAviso = (aviso: AvisoDeclarado, idx: number) => {
    const estilo = ESTILO[aviso.severidad];
    return (
      <div
        key={`${aviso.codigo}-${idx}`}
        className={`rounded-xl border p-4 leading-relaxed flex gap-3.5 items-start transition-all ${estilo.cardStyle}`}
      >
        {estilo.icon}
        <div className="space-y-1.5 flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${estilo.badgeStyle}`}
            >
              {t(estilo.badge)}
            </span>
            {/* El código va a la vista: es lo que permite reconocer el mismo
                aviso entre versiones aunque cambie su redacción. */}
            {aviso.codigo !== "HEREDADO" && aviso.codigo !== "SIN_CODIGO" && (
              <span className="font-mono text-[10px] text-white/25">{aviso.codigo}</span>
            )}
          </div>
          <p className="text-xs sm:text-sm font-medium leading-relaxed text-slate-200 break-words font-sans">
            {aviso.mensaje}
          </p>
          {estilo.pie && (
            <p className="text-[11px] leading-relaxed text-zinc-500 font-sans">{t(estilo.pie)}</p>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-3 animate-in fade-in duration-200 font-sans text-xs">
      {avisos.length > 0 ? (
        avisos.map(renderAviso)
      ) : (
        <div className="text-center text-slate-400 text-xs py-12 font-mono">
          {t("pn_sin_advertencias_simulacion")}
        </div>
      )}
    </div>
  );
}
