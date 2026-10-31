"use client";

import { appLocale } from "../../lib/formatoNumerico";

import { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { Check, CircleSlash, Flag } from "lucide-react";

import type { CaseDisposition, CaseDispositionKind, RunInputsRelation } from "../../lib/cases/types";

const LABEL_KEYS: Record<CaseDispositionKind, string> = {
  accept: "ca_disposition_accept",
  limit: "ca_disposition_limit",
  abstain: "ca_disposition_abstain",
};

export interface CaseDispositionPanelProps {
  readonly disposition?: CaseDisposition;
  readonly dispositions?: readonly CaseDisposition[];
  readonly runRelation: RunInputsRelation;
  readonly onSubmit?: (kind: CaseDispositionKind, rationale: string) => boolean | Promise<boolean>;
  readonly embedded?: boolean;
  /** Controlled fields let the workspace place the only save action after all questions. */
  readonly draftKind?: CaseDispositionKind;
  readonly draftRationale?: string;
  readonly onDraftKindChange?: (kind: CaseDispositionKind) => void;
  readonly onDraftRationaleChange?: (rationale: string) => void;
  readonly saving?: boolean;
  readonly submitError?: string | null;
  readonly submitPlacement?: "inside" | "external";
}

export function CaseDispositionPanel({
  disposition,
  dispositions,
  runRelation,
  onSubmit,
  embedded = false,
  draftKind,
  draftRationale,
  onDraftKindChange,
  onDraftRationaleChange,
  saving = false,
  submitError,
  submitPlacement = "inside",
}: CaseDispositionPanelProps) {
  const { t, locale } = useLanguage();
  const relationOk = runRelation === "corresponde";
  const [localKind, setLocalKind] = useState<CaseDispositionKind>(
    disposition?.kind ?? (relationOk ? "limit" : "abstain"),
  );
  const [localRationale, setLocalRationale] = useState(disposition?.rationale ?? "");
  const [localError, setLocalError] = useState<string | null>(null);
  const [localSaving, setLocalSaving] = useState(false);
  const kind = draftKind ?? localKind;
  const rationale = draftRationale ?? localRationale;
  const locked = Boolean(disposition);
  const retiradas = (dispositions ?? []).filter((entry) => !disposition || entry.at !== disposition.at);
  const error = submitError !== undefined ? submitError : localError;
  const isSaving = saving || localSaving;

  const submit = async () => {
    if (!onSubmit || isSaving) return;
    if (!relationOk && kind !== "abstain") {
      setLocalError(t("auto_66c8de9b17f6"));
      return;
    }
    setLocalSaving(true);
    setLocalError(null);
    try {
      if (!(await onSubmit(kind, rationale))) setLocalError(t("auto_471ce73812dc"));
    } catch {
      setLocalError(t("auto_471ce73812dc"));
    } finally {
      setLocalSaving(false);
    }
  };

  return (
    <section aria-labelledby="case-disposition-title" className={embedded ? "border-b border-surface-800 px-4 py-4" : "border-b border-surface-800 bg-surface-950 px-4 py-4 sm:px-6"}>
      <div className={embedded ? "flex w-full flex-col gap-3" : "mx-auto flex w-full max-w-5xl flex-col gap-3"}>
        <div className="flex items-start gap-3">
          <Flag className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" aria-hidden="true" />
          <div className="min-w-0">
            <h2 id="case-disposition-title" className="text-base font-semibold text-zinc-100">
              {t("ca_disposicion_titulo")}
            </h2>
            <p className="mt-1 text-sm leading-5 text-zinc-500">
              {t("ca_disposicion_descripcion")}
            </p>
          </div>
        </div>

        {locked ? (
          <div className="rounded-md border border-brand-500/20 bg-brand-500/5 px-3 py-2 text-sm leading-5 text-zinc-300">
            <span className="font-medium text-zinc-100">{t(LABEL_KEYS[disposition!.kind])}.</span>{" "}
            {disposition!.rationale}
            <span className="ml-2 font-mono text-[11px] text-zinc-500">{new Date(disposition!.at).toLocaleString(appLocale(locale))}</span>
          </div>
        ) : (
          <>
            {!relationOk && (
              <p role="status" className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm leading-5 text-amber-200">
                {t("ca_disposicion_sin_huella")}
              </p>
            )}
            {relationOk ? (
              <div className={embedded ? "grid gap-2" : "grid gap-2 sm:grid-cols-3"} role="radiogroup" aria-label={t("ca_disposicion_titulo")}>
                {(Object.keys(LABEL_KEYS) as CaseDispositionKind[]).map((option) => {
                  const selected = kind === option;
                  return (
                    <label key={option} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors focus-within:ring-2 focus-within:ring-brand-400 ${selected ? "border-brand-500/50 bg-brand-500/10 text-zinc-100" : "border-surface-700 text-zinc-300 hover:border-surface-600"}`}>
                      <input
                        type="radio"
                        name="case-disposition"
                        value={option}
                        checked={selected}
                        onChange={() => (onDraftKindChange ? onDraftKindChange(option) : setLocalKind(option))}
                        className="accent-brand-500"
                      />
                      {option === "accept" ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : option === "abstain" ? <CircleSlash className="h-3.5 w-3.5" aria-hidden="true" /> : <Flag className="h-3.5 w-3.5" aria-hidden="true" />}
                      <span>{t(LABEL_KEYS[option])}</span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <div className="flex min-h-11 items-center gap-2 rounded-md border border-brand-500/40 bg-brand-500/10 px-3 py-2 text-sm text-zinc-100">
                <CircleSlash className="h-4 w-4 shrink-0 text-brand-300" aria-hidden="true" />
                <span><strong>{t("ca_abstain_label")}</strong> {t("ca_disposicion_abstencion")}</span>
              </div>
            )}
            <label className="min-w-0 text-sm text-zinc-400">
              {t("ca_justificacion")}
              <textarea
                value={rationale}
                onChange={(event) => (onDraftRationaleChange ? onDraftRationaleChange(event.target.value) : setLocalRationale(event.target.value))}
                rows={embedded ? 3 : 2}
                maxLength={4000}
                placeholder={t("ca_justificacion_ejemplo")}
                className="mt-1 block w-full resize-y rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm leading-5 text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20"
              />
            </label>
            {submitPlacement === "inside" && onSubmit && (
              <button
                type="button"
                onClick={() => void submit()}
                disabled={isSaving}
                className={`min-h-11 shrink-0 whitespace-nowrap rounded-md bg-brand-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-wait disabled:opacity-70 ${embedded ? "w-full" : ""}`}
              >
                {isSaving ? t("ca_disposition_saving") : kind === "abstain" ? t("auto_fc11ec3c0679") : t("auto_b579df9fd203")}
              </button>
            )}
            {error && <p role="alert" className="text-sm text-amber-300">{error}</p>}
          </>
        )}

        {retiradas.length > 0 && (
          <div className="mt-1">
            <p className="text-xs font-semibold text-zinc-400">{t("ca_disposicion_anteriores")}</p>
            <ul className="mt-1 space-y-1">
              {retiradas.map((entry) => (
                <li key={entry.at} className="rounded-md border border-surface-700 bg-black/20 px-3 py-2 text-sm leading-5 text-zinc-400">
                  <span className="font-medium text-zinc-300">{t(LABEL_KEYS[entry.kind])}.</span>{" "}
                  {entry.rationale}
                  <span className="ml-2 font-mono text-[11px] text-zinc-600">{new Date(entry.at).toLocaleString(appLocale(locale))}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

export default CaseDispositionPanel;
