"use client";

/**
 * EmptyState — Panel cinematográfico para estados "vacíos" / "blocked" / "idle".
 *
 * Patrón visual cohesivo con /moldex y /history:
 *   - bg #050508 + glow radial purple
 *   - ThinkingOrb (idle / complete / error) en el centro
 *   - ✦ headline con tracking-tight uppercase
 *   - ritual 1·2·3 adaptable
 *   - CTA épico purple (estilo del boton Play de ProEvaluation)
 *   - footer status mono sutil
 *
 * Uso:
 *   <EmptyState
 *     orbState="idle"
 *     title="Bioteca en Stand-By"
 *     description="Tu colección molecular te espera."
 *     ritual={[{ n:"1", t:"Diseña", d:"con Ketcher" }, ...]}
 *     ctaHref="/evaluation"
 *     ctaLabel="Lanzar Pipeline"
 *     footerStatus="0 moléculas guardadas · bioteca local · v 2.0"
 *   />
 *
 * Composición con animaciones suaves: stagger fadeIn por secciones (orb →
 * headline → ritual → CTA → footer). Capaz de scrollear bien (min-h-screen).
 * No requiere build, es puramente presentational +客户端 framer-motion.
 */

import { ReactNode } from "react";
import { motion } from "framer-motion";
import { Play, ChevronRight } from "lucide-react";
import { ThinkingOrb, OrbState } from "./ThinkingOrb";

export interface RitualStep {
  n: string;
  t: string;
  d: string;
}

export interface EmptyStateProps {
  /** Estado del ThinkingOrb: idle (inerte), processing (animado loader), complete, error */
  orbState?: OrbState;
  /** Título principal, uppercase automáticamente */
  title: string;
  /** Sub-headline descriptivo debajo del título */
  description?: ReactNode;
  /** Pasos rituales numerados. Si es undefined, no se renderiza la grilla */
  ritual?: RitualStep[];
  /** href del CTA principal */
  ctaHref?: string;
  /** Texto del CTA principal */
  ctaLabel?: string;
  /** ¿Mostrar el CTA con el icono Play + ChevronRight? default true */
  showCta?: boolean;
  /** Estado del footer mono sutil abajo (ej: "0 moléculas guardadas") */
  footerStatus?: string;
  /** Sub-line decorativa bajo el ThinkingOrb (ej: "sincronizando bioteca") */
  subline?: string;
}

/**
 * Animaciones base — stagger suave sobre el contenedor central.
 */
const containerStagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12, delayChildren: 0.1 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" as const } },
};

export function EmptyState({
  orbState = "idle",
  title,
  description,
  ritual,
  ctaHref,
  ctaLabel,
  showCta = true,
  footerStatus,
  subline,
}: EmptyStateProps) {
  return (
    <div className="relative min-h-screen bg-[#050508] text-white/70 font-sans flex items-center justify-center overflow-hidden">

      {/* ── Glow ambiental purple radial (estático desde el fondo) ── */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 38%, rgba(147,51,234,0.08) 0%, transparent 55%)," +
            "radial-gradient(circle at 50% 100%, rgba(99,102,241,0.04) 0%, transparent 60%)",
        }}
      />

      {/* ── Stars decorativas oben, animadas con framer-motion ── */}
      <div className="absolute inset-x-0 top-0 h-1/3 pointer-events-none">
        {Array.from({ length: 8 }).map((_, i) => (
          <motion.span
            key={i}
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.5, 0] }}
            transition={{
              duration: 3 + (i % 3),
              repeat: Infinity,
              delay: i * 0.6,
              ease: "easeInOut",
            }}
            className="absolute h-px w-px bg-purple-300 rotate-45 shadow-[0_0_6px_rgba(216,180,254,0.7)]"
            style={{ left: `${15 + i * 9}%`, top: `${8 + (i % 4) * 6}%` }}
          />
        ))}
      </div>

      {/* ── Contenido central, stagger animado ── */}
      <motion.div
        variants={containerStagger}
        initial="hidden"
        animate="show"
        className="relative z-10 flex flex-col items-center gap-8 max-w-2xl px-6 text-center"
      >
        {/* ThinkingOrb + subline */}
        <motion.div variants={itemVariants} className="flex flex-col items-center gap-6">
          <ThinkingOrb state={orbState} size="lg" />
          {subline && (
            <motion.p
              animate={{ opacity: [0.4, 0.75, 0.4] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
              className="text-[10px] font-mono tracking-[0.4em] uppercase text-white/45"
            >
              {subline}
            </motion.p>
          )}
        </motion.div>

        {/* Headline ✦ TÍTULO ✦ */}
        <motion.div variants={itemVariants} className="space-y-3">
          <div className="flex items-center justify-center gap-3 text-white/30">
            <span className="text-[10px] font-mono tracking-[0.5em] uppercase">✦</span>
            <h1 className="text-3xl md:text-4xl font-black tracking-tight text-white uppercase">
              {title}
            </h1>
            <span className="text-[10px] font-mono tracking-[0.5em] uppercase">✦</span>
          </div>
          {description && (
            <p className="text-sm md:text-[15px] text-white/40 leading-relaxed max-w-md mx-auto">
              {description}
            </p>
          )}
        </motion.div>

        {/* Ritual 1·2·3 (opcional) */}
        {ritual && ritual.length > 0 && (
          <motion.div
            variants={itemVariants}
            className="grid grid-cols-1 sm:grid-cols-3 gap-2 w-full max-w-xl py-2"
          >
            {ritual.map(s => (
              <div
                key={s.n}
                className="rounded-xl border border-white/5 bg-white/[0.015] p-4 backdrop-blur-sm hover:border-purple-500/30 transition-all group"
              >
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-[10px] font-mono font-bold text-purple-400">{s.n}</span>
                  <span className="text-sm font-black text-white tracking-tight uppercase">{s.t}</span>
                </div>
                <p className="text-[10px] font-mono text-white/30 uppercase tracking-wider">{s.d}</p>
              </div>
            ))}
          </motion.div>
        )}

        {/* CTA épico purple */}
        {showCta && ctaHref && ctaLabel && (
          <motion.a
            variants={itemVariants}
            href={ctaHref}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="group relative inline-flex items-center gap-3 px-8 py-4 rounded-xl font-mono text-xs font-bold uppercase tracking-[0.2em] text-white bg-purple-600 hover:bg-purple-500 shadow-lg shadow-purple-950/50 border border-purple-400/30 transition-all"
          >
            <Play size={14} className="fill-white" />
            {ctaLabel}
            <ChevronRight size={14} className="group-hover:translate-x-1 transition-transform" />
          </motion.a>
        )}
      </motion.div>

      {/* ── Footer mono sutil abajo ── */}
      {footerStatus && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9, duration: 0.6 }}
          className="absolute bottom-6 left-0 right-0 z-10 flex justify-center"
        >
          <p className="text-[10px] font-mono tracking-[0.3em] uppercase text-white/15">
            {footerStatus}
          </p>
        </motion.div>
      )}
    </div>
  );
}

export default EmptyState;
