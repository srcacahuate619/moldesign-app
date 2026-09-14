"use client";

/**
 * EmptyState — Panel para estados vacíos, bloqueados o en espera.
 *
 * Patrón visual cohesivo con /moldex y /history:
 *   - tokens de superficie con la apariencia oscura original en dark mode
 *   - ThinkingOrb (idle / complete / error) en el centro
 *   - ✦ headline con tracking-tight uppercase
 *   - ritual 1·2·3 adaptable
 *   - CTA épico purple (estilo del boton Play de ProEvaluation)
 *   - footer status mono sutil
 *
 * Uso:
 *   <EmptyState
 *     orbState="idle"
 *     title="Bioteca en espera"
 *     description="Tu colección molecular te espera."
 *     ritual={[{ n:"1", t:"Diseña", d:"con Ketcher" }, ...]}
 *     ctaHref="/evaluation"
 *     ctaLabel="Lanzar Pipeline"
 *     footerStatus="0 moléculas guardadas · bioteca local · v 2.0"
 *   />
 *
 * Composición con animaciones suaves: stagger fadeIn por secciones (orb →
 * headline → ritual → CTA → footer). Capaz de scrollear bien (min-h-screen).
 * Es puramente presentational + framer-motion.
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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--bg)] font-sans text-muted dark:bg-[#050508]">

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
              className="font-mono text-xs uppercase tracking-[0.4em] text-dim dark:text-white/60"
            >
              {subline}
            </motion.p>
          )}
        </motion.div>

        {/* Headline ✦ TÍTULO ✦ */}
        <motion.div variants={itemVariants} className="space-y-3">
          <div className="flex items-center justify-center gap-3 text-dim dark:text-white/45">
            <span className="font-mono text-xs uppercase tracking-[0.5em]">✦</span>
            <h1 className="text-3xl font-black uppercase tracking-tight text-theme md:text-4xl">
              {title}
            </h1>
            <span className="font-mono text-xs uppercase tracking-[0.5em]">✦</span>
          </div>
          {description && (
            <p className="mx-auto max-w-md text-sm leading-relaxed text-muted md:text-[15px]">
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
                className="group rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 backdrop-blur-sm transition-all hover:border-purple-500/30 dark:border-white/5 dark:bg-white/[0.015]"
              >
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{s.n}</span>
                  <span className="text-sm font-black uppercase tracking-tight text-theme">{s.t}</span>
                </div>
                <p className="font-mono text-xs uppercase tracking-wider text-dim">{s.d}</p>
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
            className="group relative inline-flex items-center gap-3 rounded-xl border border-purple-400/30 bg-purple-600 px-8 py-4 font-mono text-xs font-bold uppercase tracking-[0.2em] text-white shadow-lg shadow-purple-950/50 transition-all hover:bg-purple-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]"
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
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-dim">
            {footerStatus}
          </p>
        </motion.div>
      )}
    </div>
  );
}

export default EmptyState;
