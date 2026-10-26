"use client";

import { useLanguage } from "@/context/LanguageContext";

/**
 * «Beta» junto a una función: lo que ofrece funciona pero no está validado de punta a punta.
 * Decisión del propietario (2026-10-04) para Molcy: visible y marcada, no oculta. Depende de Blender
 * (programa externo) y su funcionamiento no está certificado en una máquina limpia.
 */
export function PildoraBeta() {
  const { t } = useLanguage();
  return (
    <span
      data-testid="pildora-beta"
      className="ml-1.5 rounded border border-amber-500/40 px-1 py-px align-middle text-[9px] font-bold tracking-wider text-amber-500 dark:text-amber-400"
    >
      {t("c_beta")}
    </span>
  );
}
