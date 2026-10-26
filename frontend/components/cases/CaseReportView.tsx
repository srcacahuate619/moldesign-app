"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import type { SaveState } from "../../context/CaseContext";

import { CaseContextPanel } from "./CaseContextPanel";
import { CaseDispositionPanel } from "./CaseDispositionPanel";
import { CaseDossierViewer } from "./CaseDossierViewer";
import type {
  CaseContext,
  CaseDisposition,
  CaseDispositionKind,
  CaseRecord,
  ReportableResult,
  RunInputsRelation,
} from "../../lib/cases/types";

export interface CaseReportViewProps {
  readonly caseRecord: CaseRecord;
  readonly reportable: ReportableResult;
  readonly runRelation: RunInputsRelation;
  readonly pendingDetails: string;
  readonly context: CaseContext;
  readonly contextSaveState: SaveState;
  readonly onContextChange: (patch: Partial<CaseContext>) => void;
  readonly onRetryContextSave: () => void | Promise<void>;
  readonly disposition?: CaseDisposition;
  readonly dispositions?: readonly CaseDisposition[];
  readonly showDisposition: boolean;
  readonly onDispositionSubmit: (kind: CaseDispositionKind, rationale: string) => Promise<boolean>;
}

export function CaseReportView({
  caseRecord,
  reportable,
  runRelation,
  pendingDetails,
  context,
  contextSaveState,
  onContextChange,
  onRetryContextSave,
  disposition,
  dispositions,
  showDisposition,
  onDispositionSubmit,
}: CaseReportViewProps) {
  const { t } = useLanguage();
  const [draftKind, setDraftKind] = useState<CaseDispositionKind>(
    disposition?.kind ?? (runRelation === "corresponde" ? "limit" : "abstain"),
  );
  const [draftRationale, setDraftRationale] = useState(disposition?.rationale ?? "");
  const [dispositionSaving, setDispositionSaving] = useState(false);
  const [dispositionError, setDispositionError] = useState<string | null>(null);

  useEffect(() => {
    setDraftKind(disposition?.kind ?? (runRelation === "corresponde" ? "limit" : "abstain"));
    setDraftRationale(disposition?.rationale ?? "");
    setDispositionError(null);
  }, [caseRecord.id, disposition?.at, disposition?.kind, disposition?.rationale, runRelation]);

  const saveDisposition = async () => {
    if (dispositionSaving || disposition || !showDisposition) return;
    if (runRelation !== "corresponde" && draftKind !== "abstain") {
      setDispositionError(t("auto_66c8de9b17f6"));
      return;
    }
    setDispositionSaving(true);
    setDispositionError(null);
    try {
      if (!(await onDispositionSubmit(draftKind, draftRationale))) {
        setDispositionError(t("auto_471ce73812dc"));
      }
    } catch {
      setDispositionError(t("auto_471ce73812dc"));
    } finally {
      setDispositionSaving(false);
    }
  };

  return (
    <main className="flex h-full min-h-0 w-full flex-col overflow-hidden px-4 py-3 font-sans sm:px-6">
      <div className="grid h-full min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1.1fr)_minmax(0,0.9fr)] gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] xl:grid-rows-1 xl:items-stretch">
        <section aria-labelledby="case-report-title" className="flex min-h-0 min-w-0 flex-col">
          <header className="shrink-0 border-b border-surface-800 pb-3">
            <h2 id="case-report-title" className="text-2xl font-semibold tracking-tight text-zinc-100">
              {t("ca_dossier_caso")}
            </h2>
            <p className="mt-1 max-w-[100ch] text-sm leading-6 text-zinc-400">
              {t("ca_dossier_lo_redacta")}
            </p>
          </header>

          {runRelation !== "corresponde" && (
            <p
              role="status"
              className="mt-3 shrink-0 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm leading-5 text-amber-200"
            >
              {runRelation === "corrida_anterior" ? (
                <>
                  <strong>{t("ca_informe_anterior")}</strong> {t("ca_informe_anterior_detalle")}
                </>
              ) : (
                <>
                  <strong>{t("ca_informe_sin_huella")}</strong> {t("ca_informe_sin_huella_detalle")}
                </>
              )}
            </p>
          )}

          <div className="mt-2 flex min-w-0 shrink-0 flex-wrap items-center gap-x-5 gap-y-1 text-xs text-zinc-500">
            <span className="break-all font-mono">{t("ca_run_id_label", { id: reportable.taskId })}</span>
            <span>
              {t("auto_384a1af1c5dc")} <span className="break-all font-mono">{reportable.moleculeId}</span>
            </span>
          </div>

          <div className="mt-3 min-h-0 min-w-0 flex-1">
            <CaseDossierViewer
              caseRecord={caseRecord}
              reportable={reportable}
              runRelation={runRelation}
            />
          </div>
        </section>

        <aside
          aria-label={t("ca_dossier_review_sidebar")}
          className="h-full min-h-0 min-w-0 overflow-y-auto rounded-lg border border-surface-800 bg-surface-950"
        >
          {showDisposition && (
            <CaseDispositionPanel
              disposition={disposition}
              dispositions={dispositions}
              runRelation={runRelation}
              embedded
              draftKind={draftKind}
              draftRationale={draftRationale}
              onDraftKindChange={setDraftKind}
              onDraftRationaleChange={setDraftRationale}
              submitPlacement="external"
            />
          )}

          <section aria-labelledby="case-context-sidebar-title" className="min-w-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-surface-800 px-4 py-3">
              <h3 id="case-context-sidebar-title" className="text-base font-semibold text-zinc-100">
                {t("ca_context_questions_heading")}
              </h3>
              <span className="text-xs text-zinc-400">{pendingDetails}</span>
            </div>
            <CaseContextPanel
              context={context}
              saveState={contextSaveState}
              onChange={onContextChange}
              onRetry={onRetryContextSave}
              embedded
              variant="panel"
            />
          </section>

          {showDisposition && !disposition && (
            <footer className="border-t border-surface-800 bg-surface-900/50 px-4 py-4">
              <p className="mb-3 text-sm leading-5 text-zinc-400">{t("ca_disposition_save_all_hint")}</p>
              {dispositionError && <p role="alert" className="mb-3 text-sm text-amber-300">{dispositionError}</p>}
              <button
                type="button"
                onClick={() => void saveDisposition()}
                disabled={dispositionSaving}
                className="min-h-11 w-full rounded-md bg-brand-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-wait disabled:opacity-70"
              >
                {dispositionSaving
                  ? t("ca_disposition_saving")
                  : draftKind === "abstain"
                    ? t("auto_fc11ec3c0679")
                    : t("auto_b579df9fd203")}
              </button>
            </footer>
          )}
        </aside>
      </div>
    </main>
  );
}

export default CaseReportView;
