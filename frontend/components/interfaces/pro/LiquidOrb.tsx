"use client";

import React, { useEffect, useRef, useState } from "react";

interface LiquidOrbProps {
  /** Valor 0-100 (porcentaje del líquido) */
  value: number;
  /** Texto centrado dentro del orbe (p. ej. "88 / 100" o "-4.20 logS") */
  absolute: string;
  /** Label inferior */
  label: string;
  /** Source tertiary label */
  source?: string;
  /**
   * El modelo no produjo este valor.
   *
   * NO ES LO MISMO QUE CERO, y hasta ahora se dibujaba igual: quien llamaba
   * ponía `value={score ?? 0}` y el orbe salía vacío y en rojo —el color de
   * «malo»— para una molécula sobre la que nadie había medido nada. Con esto
   * el orbe se queda gris, sin líquido y con el motivo escrito debajo: un
   * hueco declarado, que es lo que de verdad hay.
   */
  unavailable?: boolean;
  /** Por qué no hay valor. Se muestra en lugar de `source` cuando falta. */
  unavailableNote?: string;
}

export function LiquidOrb({ value, absolute, label, source, unavailable = false, unavailableNote }: LiquidOrbProps) {
  const numRef = useRef<HTMLSpanElement>(null);
  const orbRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  const [hasAnimated, setHasAnimated] = useState(false);

  const v = unavailable ? 0 : Math.max(0, Math.min(100, value));
  // Gris neutro cuando no hay dato: ni verde ni rojo, porque no se midió nada.
  const color = unavailable ? "#64748b" : v >= 70 ? "#34d399" : v >= 40 ? "#fbbf24" : "#f87171";
  const colorDark = unavailable ? "#334155" : v >= 70 ? "#059669" : v >= 40 ? "#b45309" : "#b91c1c";

  // IntersectionObserver — dispara la animación solo cuando el orb entra en viewport
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasAnimated) {
            setInView(true);
            setHasAnimated(true);
          }
        });
      },
      { threshold: 0.2, rootMargin: "0px 0px -10% 0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasAnimated]);

  // Animación: se dispara solo cuando inView === true
  useEffect(() => {
    if (!inView) return;

    let frame = 0;
    const m = absolute.match(/-?\d+\.?\d*/);
    if (m && m[0] && numRef.current) {
      const final = parseFloat(m[0]);
      const decimals = m[0].includes(".") ? 2 : 0;
      const startedAt = performance.now();
      const tick = (now: number) => {
        const progress = Math.min(1, (now - startedAt) / 1400);
        const eased = 1 - Math.pow(1 - progress, 2);
        const formatted = (eased * final).toFixed(decimals);
        if (numRef.current) numRef.current.textContent = absolute.replace(/-?\d+\.?\d*/, formatted);
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    }

    if (orbRef.current) {
      const node = orbRef.current;
      node.style.setProperty("--liquid", "0%");
      node.style.transition = "height 1.8s cubic-bezier(0.16, 1, 0.3, 1) 0.15s";
      requestAnimationFrame(() => node.style.setProperty("--liquid", `${v}%`));
    }

    return () => {
      if (frame) cancelAnimationFrame(frame);
      if (orbRef.current) orbRef.current.style.transition = "";
    };
  }, [inView, absolute, v]);

  return (
    <div ref={wrapperRef} className="flex flex-col items-center gap-3">
      {/* ── Liquid Orb Container (relativo para el overlay del número) ── */}
      <div className="relative w-[150px] h-[150px]">
        {/* Halo radius (box-shadow del color del líquido) */}
        <div
          className="absolute inset-0 rounded-full"
          style={{ boxShadow: `0 0 32px ${color}30, inset 0 0 24px ${color}20` }}
        />

        {/* Recipiente circular (glass background, overflow recorta líquido al círculo) */}
        <div
          className="absolute inset-1 rounded-full overflow-hidden"
          style={{
            background:
              "radial-gradient(circle at 50% 22%, rgba(255,255,255,0.06), transparent 60%), #05080f",
            border: `1px solid ${color}30`,
          }}
        >
          {/* Líquido con altura vía CSS variable --liquid (animada por CSS) */}
          <div
            ref={orbRef}
            className="absolute inset-x-0 bottom-0"
            style={{
              height: "var(--liquid, 0%)",
              background: `linear-gradient(180deg, ${color}90 0%, ${colorDark} 100%)`,
            }}
          >
            {/* Ola 1: glow radial blando que simula el borde suave del agua */}
            <div
              className="absolute top-0 left-0 right-0 h-[18px]"
              style={{
                background: `radial-gradient(circle at 50% 100%, ${color} 0%, transparent 70%)`,
                opacity: 0.6,
                transform: "translateY(-8px)",
              }}
            />
            {/* Ola 2: gradiente horizontal pulsante para sugerir movimiento */}
            <div
              className="absolute -top-1 left-[-50%] w-[200%] h-3 opacity-30 animate-pulse"
              style={{
                background: `linear-gradient(90deg, transparent 0%, ${color}cc 50%, transparent 100%)`,
                borderRadius: "50%",
              }}
            />
          </div>

          {/* Glass highlight: brillo elíptico superior (glassmorphism) */}
          <div
            className="absolute top-2 left-1/2 -translate-x-1/2 w-[60%] h-[16%] rounded-full"
            style={{
              background:
                "linear-gradient(180deg, rgba(255,255,255,0.10) 0%, transparent 100%)",
              filter: "blur(2px)",
            }}
          />
        </div>

        {/* ── Número DENTRO del orb (overlay absoluto dentro del contenedor 150x150) ── */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <span
            ref={numRef}
            className="text-lg font-black font-mono"
            style={{
              color: "#fff",
              textShadow:
                "0 1px 4px rgba(0,0,0,0.95), 0 0 8px rgba(0,0,0,0.7), 0 0 2px rgba(0,0,0,1)",
            }}
          >
            {absolute}
          </span>
        </div>
      </div>

      {/* ── Label inferior ── */}
      <div className="flex flex-col items-center gap-0.5">
        <span
          className="text-xs font-bold font-mono uppercase tracking-wider"
          style={{ color }}
        >
          {label}
        </span>
        {unavailable ? (
          <span className="max-w-[16rem] text-center text-[10px] font-mono leading-relaxed text-slate-500">
            {unavailableNote ?? "sin dato en esta corrida"}
          </span>
        ) : (
          source && <span className="text-[10px] font-mono text-slate-500">{source}</span>
        )}
      </div>
    </div>
  );
}
