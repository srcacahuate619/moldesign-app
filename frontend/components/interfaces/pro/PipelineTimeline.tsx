"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useEffect, useRef } from "react";

export type StageState = "pending" | "running" | "done" | "error" | "skipped";

export interface Stage {
  id: string;
  label: string;
  color: string;
  optional?: boolean; // se atenúa visualmente (no siempre corre en el pipeline)
}

/** Etiqueta del orb `properties` cuando la corrida NO pidió ADMET-AI. */
export const PROPERTIES_LABEL = "Propiedades";
/** Etiqueta del orb `properties` cuando la corrida SÍ pidió ADMET-AI. */
export const PROPERTIES_ADMET_LABEL = "Propiedades / ADMET";

// Orbs por defecto. `id` es el ID del ORB (no el stage_id SSE del backend);
// ProEvaluation mapea stage_id SSE → orb id (docking → vina, etc.).
//
// El orb `properties` va ANTES de `conformer` porque ése es su sitio en el
// registro del backend (`registry.py`: conformer depende de properties) y
// porque es donde de verdad se gasta el tiempo cuando ADMET-AI está activo.
// La etiqueta por defecto es la que NO afirma nada: sin una configuración que
// pida ADMET explícitamente, esta etapa es sólo el cálculo local de
// descriptores, y decir «ADMET» ahí sería atribuirle a la corrida un modelo
// que no llegó a cargarse.
export const DEFAULT_STAGES: Stage[] = [
  { id: "validation",  label: "Curación",         color: "#94a3b8" },
  { id: "properties",  label: PROPERTIES_LABEL,   color: "#818cf8" },
  { id: "conformer",   label: "3D ETKDG",         color: "#22d3ee" },
  { id: "vina",        label: "Vina",             color: "#a78bfa" },
  { id: "xgb",         label: "XGBoost",          color: "#60a5fa" },
  { id: "clgnn",       label: "CL-GNN",           color: "#34d399" },
  { id: "openmm",      label: "OpenMM",           color: "#f59e0b" },
  { id: "mmgbsa",      label: "MM-GBSA",          color: "#ec4899" },
];

export function stagesForPipeline(config?: {
  readonly enabled_stages?: readonly string[];
  readonly pro_mmgbsa?: boolean;
  readonly stage_params?: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
}): Stage[] {
  const enabled = new Set(
    config?.enabled_stages ??
      ["validation", "properties", "conformer", "docking", "xgb", "clgnn"],
  );
  // ADMET es opt-in, y aquí se lee igual que lo lee el backend
  // (`queue_handler.py`: `stage_params.properties.run_admet_ai`, ausente →
  // False). Sólo un `true` explícito cambia la etiqueta; cualquier otra cosa
  // —ausente, false, basura de un manifiesto viejo— deja «Propiedades».
  const admet = config?.stage_params?.properties?.run_admet_ai === true;
  return DEFAULT_STAGES.filter((stage) => {
    if (stage.id === "vina") return enabled.has("docking");
    if (stage.id === "mmgbsa") return config?.pro_mmgbsa === true;
    return enabled.has(stage.id);
  }).map((stage) =>
    stage.id === "properties"
      ? { ...stage, label: admet ? PROPERTIES_ADMET_LABEL : PROPERTIES_LABEL }
      : stage,
  );
}

interface Props {
  stages?: Stage[];
  /** Estado por orb id: pending | running | done | error | skipped */
  stageStates?: Record<string, StageState>;
  /** Mensaje por orb id: error del stage o razón del skip */
  stageMessages?: Record<string, string>;
  isDone?: boolean;
  failed?: boolean;
  statusLabel?: string;
}

const PARTICLES_PER_NODE = 8;

export function PipelineTimeline({
  stages = DEFAULT_STAGES,
  stageStates = {},
  stageMessages = {},
  isDone = false,
  failed = false,
  statusLabel,
}: Props) {
  const { t } = useLanguage();
  const nodeRefs = useRef<(HTMLDivElement | null)[]>([]);
  const barRef = useRef<HTMLDivElement>(null);
  const angleRef = useRef(0);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      angleRef.current += 0.025;
      const angle = angleRef.current;

      // Orbit particles around each node
      stages.forEach((_, i) => {
        const node = nodeRefs.current[i];
        if (!node) return;
        const particles = node.querySelectorAll<HTMLElement>(".particle");
        particles.forEach((p, j) => {
          const offset = (j / PARTICLES_PER_NODE) * Math.PI * 2;
          const r = 22 + Math.sin(angle * 1.5 + offset) * 3; // 19-25px breathing
          const x = Math.cos(angle + offset) * r;
          const y = Math.sin(angle + offset) * r;
          const opacity = 0.25 + (Math.sin(angle * 2 + offset * 3) * 0.5 + 0.5) * 0.6;
          const scale = 0.5 + opacity * 0.8;
          p.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
          p.style.opacity = String(Math.max(0.15, opacity));
        });
      });

      // Animate progress bar sweep (solo mientras corre; se apaga al terminar)
      if (barRef.current) {
        if (isDone || failed) {
          barRef.current.style.background = "transparent";
        } else {
          const sweep = ((Math.sin(angle * 0.8) * 0.5 + 0.5) * 100).toFixed(2);
          barRef.current.style.background = `linear-gradient(90deg, transparent 0%, transparent ${Math.max(0, (parseFloat(sweep) - 25)).toFixed(2)}%, rgba(168,85,247,0.55) ${sweep}%, transparent ${Math.min(100, (parseFloat(sweep) + 15)).toFixed(2)}%, transparent 100%)`;
        }
      }

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [isDone, failed, stages]);

  const finishedCount = stages.filter((s) => stageStates[s.id] === "done" || stageStates[s.id] === "error" || stageStates[s.id] === "skipped").length;

  return (
    <div className="w-full max-w-[1100px] flex flex-col items-center gap-10 py-16">
      {/* Timeline */}
      <div className="w-full flex items-center justify-between relative px-8">
        {/* Connector line under all nodes (static base) */}
        <div className="absolute left-8 right-8 top-1/2 -translate-y-1/2 h-px bg-white/[0.06] z-0" />

        {/* Animated sweep bar */}
        <div
          ref={barRef}
          className="absolute left-8 right-8 top-1/2 -translate-y-1/2 h-px z-0"
          style={{ background: "transparent" }}
        />

        {/* Nodes */}
        {stages.map((s, i) => {
          const state = stageStates[s.id] ?? "pending";
          const isRunning = state === "running";
          const isDoneNode = state === "done";
          const isError = state === "error";
          const isSkipped = state === "skipped";
          const message = stageMessages[s.id];

          return (
            <div
              key={s.id}
              ref={(el) => { nodeRefs.current[i] = el; }}
              className="relative z-10 flex flex-col items-center gap-3"
              style={{
                opacity: isSkipped ? 0.5 : 1,
                transition: "opacity 300ms",
              }}
            >
              {/* Orbiting particles container */}
              <div className="relative w-[56px] h-[56px] flex items-center justify-center">
                {/* Glow halo */}
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    background: isError
                      ? "radial-gradient(circle, #ef444422 0%, transparent 65%)"
                      : isSkipped
                      ? "radial-gradient(circle, #64748b22 0%, transparent 65%)"
                      : `radial-gradient(circle, ${s.color}22 0%, transparent 65%)`,
                  }}
                />

                {/* Orbit particles — se apagan en done/error/skipped */}
                {!isDoneNode && !isError && !isSkipped &&
                  Array.from({ length: PARTICLES_PER_NODE }).map((_, j) => (
                    <span
                      key={j}
                      className="particle absolute rounded-full"
                      style={{
                        width: 3,
                        height: 3,
                        backgroundColor: s.color,
                        boxShadow: `0 0 6px ${s.color}80`,
                      }}
                    />
                  ))
                }

                {/* Central dot (node core) — estado visual */}
                {isDoneNode ? (
                  <div className="relative w-6 h-6 rounded-full z-10 flex items-center justify-center bg-emerald-500/15 border border-emerald-400/40">
                    <span className="text-emerald-400 font-black text-sm leading-none">✓</span>
                  </div>
                ) : isError ? (
                  <div className="relative w-6 h-6 rounded-full z-10 flex items-center justify-center bg-rose-500/15 border border-rose-400/40">
                    <span className="text-rose-400 font-black text-sm leading-none">✕</span>
                  </div>
                ) : isSkipped ? (
                  <div className="relative w-2.5 h-2.5 rounded-full z-10" style={{ backgroundColor: "#64748b", boxShadow: "0 0 8px #64748b60" }} />
                ) : (
                  <div
                    className={`relative w-2 h-2 rounded-full z-10 ${isRunning ? "animate-pulse" : ""}`}
                    style={{
                      backgroundColor: s.color,
                      boxShadow: isRunning
                        ? `0 0 12px ${s.color}, 0 0 24px ${s.color}90`
                        : `0 0 8px ${s.color}, 0 0 16px ${s.color}60`,
                    }}
                  />
                )}
              </div>

              {/* Label + estado */}
              <span
                className="text-xs font-mono font-bold uppercase tracking-wider whitespace-nowrap"
                style={{
                  color: isDoneNode ? "#6ee7b7" : isError ? "#f87171" : isSkipped ? "#64748b" : isRunning ? s.color : `${s.color}`,
                }}
              >
                {isRunning ? t("auto_bbaf37d0b894") : t(s.label)}
              </span>

              {/* Mensaje de error / razón de skip */}
              {(isError || isSkipped) && message && (
                <span
                  className="text-[10px] font-mono leading-tight max-w-[140px] text-center"
                  style={{ color: isError ? "#f87171" : "#94a3b8" }}
                >
                  {isSkipped && !message.toLowerCase().includes(t("auto_47083d99db42")) ? `no se calculó por ${message.toLowerCase()}` : message}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Status pill */}
      <div
        className={`flex items-center gap-2 px-4 py-1.5 rounded-full border ${
          failed
            ? "bg-rose-500/5 border-rose-500/20"
            : isDone
            ? "bg-emerald-500/5 border-emerald-500/20"
            : "bg-purple-500/5 border-purple-500/15"
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${!isDone && !failed ? "bg-purple-400 animate-pulse" : failed ? "bg-rose-400" : "bg-emerald-400"}`}
        />
        <span className={`text-[10px] font-mono uppercase tracking-widest ${failed ? "text-rose-300/80" : isDone ? "text-emerald-300/80" : "text-purple-300/80"}`}>
          {statusLabel ?? (failed ? t("auto_68203f940913") : isDone ? "Pipeline completado" : t("auto_7f1be5e1eb6d"))}
        </span>
        {!isDone && !failed && finishedCount > 0 && (
          <span className="text-[9px] font-mono text-white/25">
            {finishedCount}/{stages.length} etapas
          </span>
        )}
      </div>
    </div>
  );
}
