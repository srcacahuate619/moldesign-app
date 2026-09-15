"use client";

import { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { Check, CircleSlash, Flag } from "lucide-react";

import type { CaseDisposition, CaseDispositionKind, RunInputsRelation } from "../../lib/cases/types";

const LABELS: Record<CaseDispositionKind, string> = {
  accept: "Aceptar evidencia",
  limit: "Aceptar con límites",
  abstain: "Abstenerse",
};

export interface CaseDispositionPanelProps {
  readonly disposition?: CaseDisposition;
  readonly runRelation: RunInputsRelation;
  readonly onSubmit: (kind: CaseDispositionKind, rationale: string) => boolean;
}

export function CaseDispositionPanel({ disposition, runRelation, onSubmit }: CaseDispositionPanelProps) {
  const { t } = useLanguage();
  const relationOk = runRelation === "corresponde";
  const [kind, setKind] = useState<CaseDispositionKind>(
    disposition?.kind ?? (relationOk ? "limit" : "abstain"),
  );
  const [rationale, setRationale] = useState(disposition?.rationale ?? "");
  const [error, setError] = useState<string | null>(null);
  const locked = Boolean(disposition);

  const submit = () => {
    if (!relationOk && kind !== "abstain") {
      setError("La corrida no corresponde a los inputs actuales. Corrige la hipótesis o abstente.");
      return;
    }
    const ok = onSubmit(kind, rationale);
    if (ok) setError(null);
    else setError("La disposición no se pudo guardar. Revisa la justificación.");
  };

  return (
    <section aria-labelledby="case-disposition-title" className="border-b border-surface-800 bg-surface-950 px-4 py-4 sm:px-6">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3">
        <div className="flex items-start gap-3">
          <Flag className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" aria-hidden="true" />
          <div className="min-w-0">
            <h2 id="case-disposition-title" className="text-sm font-semibold text-zinc-100">
              {t("ca_disposicion_titulo")}
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-zinc-500">
              {t("ca_disposicion_descripcion")}
            </p>
          </div>
        </div>

        {locked ? (
          <div className="rounded-md border border-brand-500/20 bg-brand-500/5 px-3 py-2 text-xs leading-relaxed text-zinc-300">
            <span className="font-medium text-zinc-100">{LABELS[disposition!.kind]}.</span>{" "}
            {disposition!.rationale}
            <span className="ml-2 font-mono text-[11px] text-zinc-500">{new Date(disposition!.at).toLocaleString()}</span>
          </div>
        ) : (
          <>
            {!relationOk && (
              <p role="status" className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-200">
                {t("ca_disposicion_sin_huella")}
              </p>
            )}
            {relationOk ? (
              <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label={t("ca_disposicion_titulo")}>
                {(Object.keys(LABELS) as CaseDispositionKind[]).map((option) => {
                  const selected = kind === option;
                  return (
                    <label key={option} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs transition-colors focus-within:ring-2 focus-within:ring-brand-400 ${selected ? "border-brand-500/50 bg-brand-500/10 text-zinc-100" : "border-surface-700 text-zinc-300 hover:border-surface-600"}`}>
                      <input type="radio" name="case-disposition" value={option} checked={selected} onChange={() => setKind(option)} className="accent-brand-500" />
                      {option === "accept" ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : option === "abstain" ? <CircleSlash className="h-3.5 w-3.5" aria-hidden="true" /> : <Flag className="h-3.5 w-3.5" aria-hidden="true" />}
                      <span>{LABELS[option]}</span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <div className="flex min-h-11 items-center gap-2 rounded-md border border-brand-500/40 bg-brand-500/10 px-3 py-2 text-xs text-zinc-100">
                <CircleSlash className="h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" />
                <span><strong>Abstenerse.</strong> {t("ca_disposicion_abstencion")}</span>
              </div>
            )}
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <label className="min-w-0 flex-1 text-xs text-zinc-400">
                {t("ca_justificacion")}
                <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} rows={2} maxLength={4000} placeholder={t("ca_justificacion_ejemplo")} className="mt-1 block w-full resize-y rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-xs leading-relaxed text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20" />
              </label>
              <button type="button" onClick={submit} className="min-h-11 shrink-0 whitespace-nowrap rounded-md bg-brand-600 px-4 text-xs font-medium text-white transition-colors hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400">
                {relationOk ? "Guardar disposición" : "Guardar abstención"}
              </button>
            </div>
            {error && <p role="alert" className="text-xs text-amber-300">{error}</p>}
          </>
        )}
      </div>
    </section>
  );
}

export default CaseDispositionPanel;
