"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

export type OrbState = "idle" | "processing" | "complete" | "error";

interface ThinkingOrbProps {
  state?: OrbState;
  size?: "sm" | "md" | "lg";
  label?: string;
}

const DOT_COUNT = 12;

const STATE_COLORS: Record<OrbState, { dot: string; glow: string; text: string }> = {
  idle:       { dot: "bg-white/20",          glow: "transparent",                                 text: "text-white/30" },
  processing: { dot: "bg-purple-400",        glow: "rgba(168,85,247,0.15)",                      text: "text-purple-400" },
  complete:   { dot: "bg-white",             glow: "rgba(255,255,255,0.08)",                     text: "text-white/70" },
  error:      { dot: "bg-red-400",           glow: "rgba(248,113,113,0.12)",                     text: "text-red-400" },
};

const DOTS = Array.from({ length: DOT_COUNT });

export function ThinkingOrb({ state = "idle", size = "md", label }: ThinkingOrbProps) {
  const dotRefs = useRef<(HTMLDivElement | null)[]>([]);

  const sizeMap = { sm: 36, md: 56, lg: 88 };
  const dotSizeMap = { sm: 3, md: 4, lg: 6 };
  const orbitR = { sm: 13, md: 22, lg: 36 };
  const px = sizeMap[size];
  const dotPx = dotSizeMap[size];
  const r = orbitR[size];
  const colors = STATE_COLORS[state];

  // EFICIENCIA (2026-09-01). Este bucle era un `setInterval` a 16 ms que escribia
  // `width` y `height` en cada punto: dos propiedades que fuerzan LAYOUT, sesenta
  // veces por segundo, en una pantalla de carga. Y un `setInterval` no se frena
  // cuando la ventana pasa a segundo plano, asi que seguia recalculando con la
  // aplicacion minimizada.
  //
  // Ahora es `requestAnimationFrame` —que el navegador pausa solo cuando la
  // ventana no se ve— y unicamente escribe `transform` y `opacity`, que el
  // compositor resuelve sin volver a medir nada. La escala va dentro del
  // `transform`, no en el tamano de la caja. Se ve igual y no toca el layout.
  useEffect(() => {
    if (state !== "processing") return;
    let angle = 0;
    let frame = 0;
    const paso = () => {
      angle += 0.035;
      for (let i = 0; i < dotRefs.current.length; i += 1) {
        const dot = dotRefs.current[i];
        if (!dot) continue;
        const offset = (i / DOT_COUNT) * Math.PI * 2;
        const x = Math.cos(angle + offset) * r;
        const y = Math.sin(angle + offset) * r;
        const opacity = Math.max(
          0.2,
          0.35 + (Math.sin(angle * 2 + offset * 3) * 0.5 + 0.5) * 0.65,
        );
        const scale = 0.6 + opacity * 0.8;
        dot.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
        dot.style.opacity = String(opacity);
      }
      frame = requestAnimationFrame(paso);
    };
    frame = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(frame);
  }, [state, r]);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative flex items-center justify-center" style={{ width: px, height: px }}>
        <motion.div
          className="absolute inset-0 rounded-full"
          animate={{
            background: `radial-gradient(circle, ${colors.glow} 0%, transparent 70%)`,
          }}
          transition={{ duration: 0.5 }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="relative" style={{ width: 0, height: 0 }}>
            {DOTS.map((_, i) => {
              const angle = (i / DOT_COUNT) * Math.PI * 2;
              const x = Math.cos(angle) * r;
              const y = Math.sin(angle) * r;
              return (
                <div
                  key={i}
                  ref={(el) => { dotRefs.current[i] = el; }}
                  className={`absolute rounded-full transition-all duration-500 ${colors.dot}`}
                  style={{
                    width: dotPx,
                    height: dotPx,
                    transform: `translate(${x}px, ${y}px)`,
                    opacity: state === "processing" ? 0.6 : state === "idle" ? 0.12 : 0.85,
                  }}
                />
              );
            })}
          </div>
        </div>
        <AnimatePresence>
          {state === "complete" && (
            <motion.svg
              key="check"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 15 }}
              className="absolute text-white"
              width={px * 0.35} height={px * 0.35} viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2.5"
              strokeLinecap="round" strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </motion.svg>
          )}
          {state === "error" && (
            <motion.svg
              key="x"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 15 }}
              className="absolute text-red-400"
              width={px * 0.35} height={px * 0.35} viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2.5"
              strokeLinecap="round" strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </motion.svg>
          )}
        </AnimatePresence>
      </div>
      {label && (
        <motion.span
          key={state}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className={`text-[10px] font-mono tracking-wider uppercase ${colors.text}`}
        >
          {label}
        </motion.span>
      )}
    </div>
  );
}
