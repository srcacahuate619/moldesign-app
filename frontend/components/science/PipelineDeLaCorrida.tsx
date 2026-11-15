"use client";

import { useLanguage } from "@/context/LanguageContext";
import type { EvaluationResult } from "../../lib/types";
import { protocoloRegistrado } from "../../lib/procedenciaDeSenales";
import { Ayuda } from "../ui/Ayuda";
import { ProtocoloM5Zn } from "./ProtocoloM5Zn";

const GUIA_DEL_PROTOCOLO = {
  M4: {
    descripcion: "pr_pipeline_m4_description",
    senales: [
      ["AutoDock Vina", "pr_protocol_signal_vina"],
      ["XGBoost", "pr_protocol_signal_xgb"],
      ["GNN legacy (RTMScore)", "pr_protocol_signal_rtm"],
      ["CL-GNN", "pr_protocol_signal_clgnn"],
    ],
  },
  "M5-Zn": {
    descripcion: "pr_pipeline_m5_description",
    senales: [
      ["AutoDock Vina", "pr_protocol_signal_vina_norm"],
      ["XGBoost", "pr_protocol_signal_xgb_zn"],
      ["UMS-warhead", "pr_protocol_signal_ums_warhead"],
      ["GNN-D", "pr_protocol_signal_gnn_d"],
    ],
  },
  "ESMFold + Vina": {
    descripcion: "pr_pipeline_peptide_description",
    senales: [
      ["ESMFold", "pr_protocol_signal_esmfold"],
      ["pLDDT", "pr_protocol_signal_plddt"],
      ["AutoDock Vina", "pr_protocol_signal_vina"],
    ],
  },
} as const;

/** Una sola identidad de protocolo; los descartes no forman parte del resumen. */
export function PipelineDeLaCorrida({ resultado }: { resultado: EvaluationResult }) {
  const { t } = useLanguage();
  const protocolo = protocoloRegistrado(resultado);
  const guia = protocolo ? GUIA_DEL_PROTOCOLO[protocolo] : null;

  return (
    <section aria-label={t("pr_pipeline_run_label")} className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-base font-semibold text-zinc-100">
          {t(protocolo ? "pr_pipeline_used" : "pr_pipeline_not_recorded", { protocol: protocolo ?? "" })}
        </h3>
        {guia && (
          <Ayuda titulo={t("pr_protocol_signal_help")} etiqueta={t("pr_protocol_signal_help")}>
            <dl className="space-y-3 text-sm leading-6">
              {guia.senales.map(([nombre, detalle]) => (
                <div key={nombre}>
                  <dt className="font-semibold text-zinc-100">{nombre}</dt>
                  <dd>{t(detalle)}</dd>
                </div>
              ))}
            </dl>
          </Ayuda>
        )}
      </div>
      {guia && (
        <>
          <p className="mt-2 text-base leading-6 text-zinc-300 font-sans">{t(guia.descripcion)}</p>
          {protocolo === "M5-Zn" && resultado.m5_scientific_status !== "VALIDATED" && (
            <p className="mt-2 text-base leading-6 text-amber-300 font-sans">{t("pr_pipeline_audit_review")}</p>
          )}
        </>
      )}
      {protocolo === "M5-Zn" && (
        <details>
          <summary className="min-h-11 cursor-pointer py-3 text-sm text-zinc-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400">
            {t("pr_pipeline_details")}
          </summary>
          <ProtocoloM5Zn resultado={resultado} />
        </details>
      )}
    </section>
  );
}
