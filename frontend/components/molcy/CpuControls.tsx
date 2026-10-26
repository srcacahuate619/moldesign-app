"use client";

import { useLanguage } from "@/context/LanguageContext";
import type { MolcyRenderer } from "@/lib/molcy";

type Props = {
  renderer: MolcyRenderer;
  threads: number;
  onThreads: (value: number) => void;
  busy: boolean;
};

/** Hilos de CPU para las fotos con Cycles en CPU. El tiempo se estima en el estudio de fotos, con fotos ya hechas en este equipo. */
export function CpuControls({ renderer, threads, onThreads, busy }: Props) {
  const { t } = useLanguage();
  const available = renderer.cpu_hilos_disponibles || 1;
  const maximum = renderer.cpu_hilos_maximos ?? Math.max(1, Math.floor(available * 0.75));
  const recommended = Math.min(maximum, renderer.cpu_hilos || 1);
  return <div className="mt-4 border border-[var(--border)] bg-[var(--bg-card)] p-3 text-base leading-6">
    <p>{t("cy_cpu_available", { count: available })}</p>
    <p className="mt-2">{t("cy_cpu_safe_limit", { count: maximum })}</p>
    <p className="mt-1 text-[var(--text-muted)]">{renderer.cpu_uso_actual_pct == null ? t("cy_cpu_load_unknown") : t("cy_cpu_load", { percent: Math.round(renderer.cpu_uso_actual_pct) })}</p>
    <label htmlFor="molcy-cpu-threads" className="mt-3 block font-semibold">{t("cy_cpu_threads", { count: threads })}</label>
    <input id="molcy-cpu-threads" type="range" min={1} max={maximum} step={1} value={threads}
      aria-describedby="molcy-cpu-help" disabled={busy}
      onChange={event => onThreads(Number(event.target.value))}
      className="min-h-11 w-full cursor-pointer accent-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-not-allowed" />
    <button type="button" disabled={busy || threads === recommended} onClick={() => onThreads(recommended)}
      className="min-h-11 border border-[var(--border)] px-3 py-2 disabled:opacity-50">{t("cy_cpu_threads_recommended", { count: recommended })}</button>
    <p id="molcy-cpu-help" className="mt-3 border-l-2 border-amber-400 pl-3 text-[var(--text)]">{t("cy_cpu_threads_help")}</p>
    {busy && <p role="status" aria-live="polite" className="mt-3">{t("cy_cpu_busy")}</p>}
  </div>;
}
