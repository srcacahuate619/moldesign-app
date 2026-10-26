"use client";

import { useLanguage } from "@/context/LanguageContext";
export function GpuControls() {
  const { t } = useLanguage();
  return <div className="mt-4 border border-[var(--border)] bg-[var(--bg-card)] p-3 text-base leading-6">
    <p className="font-semibold">{t("cy_gpu_memory_auto")}</p>
    <p className="mt-2 text-[var(--text-muted)]">{t("cy_gpu_memory_auto_help")}</p>
  </div>;
}
