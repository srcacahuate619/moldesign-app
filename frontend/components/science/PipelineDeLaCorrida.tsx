"use client";

import { useLanguage } from "@/context/LanguageContext";
import type { EvaluationResult } from "../../lib/types";
import { protocoloRegistrado } from "../../lib/procedenciaDeSenales";
import { ProtocoloM5Zn } from "./ProtocoloM5Zn";

/** Una sola identidad de protocolo; los descartes no forman parte del resumen. */
export function PipelineDeLaCorrida({ resultado }: { resultado: EvaluationResult }) {
  const { t } = useLanguage();
  const protocolo = protocoloRegistrado(resultado);
  const m5Calculado = protocolo === "M5-Zn";

  return (
    <section aria-label={t("pr_pipeline_run_label")} className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-base font-semibold text-zinc-100">
        {t(protocolo ? "pr_pipeline_used" : "pr_pipeline_not_recorded", { protocol: protocolo ?? "" })}
      </h3>
      {protocolo && (
        <p className="mt-2 text-base leading-6 text-zinc-300 font-sans">
          {t(protocolo === "M4" ? "pr_pipeline_m4_description" : "pr_pipeline_m5_description")}
        </p>
      )}
      {m5Calculado && (
        <>
          {resultado.m5_scientific_status !== "VALIDATED" && (
            <p className="mt-2 text-base leading-6 text-amber-300 font-sans">{t("pr_pipeline_audit_review")}</p>
          )}
          <details className="mt-2">
            <summary className="min-h-11 cursor-pointer py-3 text-sm text-zinc-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">
              {t("pr_pipeline_details")}
            </summary>
            <ProtocoloM5Zn resultado={resultado} />
          </details>
        </>
      )}
    </section>
  );
}
