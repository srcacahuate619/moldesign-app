"use client";

// =====================================================================
// CaseReportView — el dossier del caso, dentro del caso
// =====================================================================
//
// QUÉ NO HACE ESTE ARCHIVO. No genera PDF, no reescribe el contenido
// científico del dossier y no inventa un segundo generador. El dossier lo
// produce el backend a partir de la PROYECCIÓN del caso y lo presenta
// `CaseDossierViewer`, que ya sabe tratar sus fallos. Aquí sólo se le da un
// sitio dentro del caso y se le antepone lo que el PDF todavía no puede decir:
// si esta corrida corresponde o no a los inputs de ahora.
//
// POR QUÉ NO ES `PDFReportViewer`. Aquel visor pide el CERTIFICADO por la ruta
// histórica de blockchain y conversa sobre el sello. Ese flujo sigue vivo en
// ProEvaluation y en Moldex y no se toca. El dossier del caso responde otra
// pregunta y viaja por otra ruta (POST, porque el caso vive en el cliente).
//
// TRES REGLAS:
//
// 1. NADA SE INVENTA. Un campo de contexto sin responder se OMITE de la
//    proyección, y el PDF lo imprime como «NO DEFINIDO». Rellenarlo con una
//    frase plausible convertiría un hueco declarado en una afirmación que nadie
//    hizo, y el dossier existe precisamente para distinguir esas dos cosas.
//
// 2. NO SE DUPLICA EL CONTEXTO SOBRE EL VISOR. El propósito, los supuestos y
//    las incertidumbres YA están dentro del PDF, que es el documento que
//    circula. Repetirlos encima obligaría a mantener dos redacciones del mismo
//    apartado, y la de la pantalla envejecería sin que nada la revalidara.
//
// 3. EL FALLO SE DICE, PERO NO AQUÍ. Esta vista sólo se abre con un
//    `molecule_id` real en la mano. Cuando el resultado guardado no se puede
//    recuperar —la tarea ya no existe en el backend, la sesión cambió— quien
//    lo declara es Evaluación, que es donde se aterriza. Si lo que falla es el
//    dossier, lo dice el propio visor, con reintento.

import { ArrowLeft } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";

import { CaseDossierViewer } from "./CaseDossierViewer";
import type { CaseRecord, ReportableResult, RunInputsRelation } from "../../lib/cases/types";

export interface CaseReportViewProps {
  /**
   * El caso ENTERO. No basta con el nombre y el contexto: la proyección que
   * viaja al backend necesita inputs, preflight, decisiones y corrida. Pasar
   * fragmentos obligaría a reconstruir el caso aquí, y un caso reconstruido a
   * trozos es justo el documento que no se puede afirmar que describa nada.
   */
  readonly caseRecord: CaseRecord;
  /**
   * Referencia mínima al resultado. NO es opcional: esta vista sólo se abre
   * cuando hay un `molecule_id` real con el que pedir el dossier. Un informe
   * sin resultado no es un informe vacío, es una promesa falsa; cuando no se
   * puede recuperar, quien lo dice es Evaluación, que es donde se aterriza.
   */
  readonly reportable: ReportableResult;
  readonly onBackToEvaluation: () => void;
  /**
   * Si la corrida de este informe corresponde a los inputs que hay AHORA.
   *
   * Un informe es evidencia de la hipótesis con la que se ejecutó, no de la
   * que esté en pantalla. Cuando dejan de coincidir hay que decirlo aquí
   * arriba: retirar el informe perdería trazabilidad, y dejarlo sin etiquetar
   * lo convertiría en evidencia de algo que nunca se calculó.
   */
  readonly runRelation: RunInputsRelation;
}

// Registrar la integridad en cadena NO se ofrece desde aquí, y el dossier del
// caso no la presenta como su función. Ese flujo vive en Evaluación, junto al
// resultado que lo alimenta; el dossier documenta qué se ejecutó y qué quedó
// sin evaluar, que es otra pregunta.

export function CaseReportView({
  caseRecord,
  reportable,
  onBackToEvaluation,
  runRelation,
}: CaseReportViewProps) {
  const { t } = useLanguage();
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="min-w-0 text-sm font-semibold tracking-tight text-zinc-100">
          {t("ca_informe_titulo")}
        </h2>
        <button
          type="button"
          onClick={onBackToEvaluation}
          className="inline-flex items-center gap-1.5 rounded-md border border-surface-700 px-2.5 py-1 text-xs text-zinc-300 transition-colors hover:border-surface-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          {t("ca_volver_evaluacion")}
        </button>
      </div>

      {runRelation !== "corresponde" && (
        <p
          role="status"
          className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-200"
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

      {/* ── Dossier ──────────────────────────────────────────────────── */}
      <section aria-labelledby="case-report-dossier" className="mt-6">
        <h3
          id="case-report-dossier"
          className="text-xs font-semibold uppercase tracking-wider text-zinc-400"
        >
          {t("ca_dossier_corrida")}
        </h3>
        <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">
          {t("ca_dossier_lo_redacta")}
        </p>

        <div className="mt-3">
          <p className="mb-2 break-all font-mono text-[11px] text-zinc-500">
            corrida {reportable.taskId.slice(0, 12)}… · molécula {reportable.moleculeId}
          </p>
          <div className="h-[70vh] min-h-[26rem]">
            <CaseDossierViewer
              caseRecord={caseRecord}
              reportable={reportable}
              runRelation={runRelation}
            />
          </div>
        </div>
      </section>
    </div>
  );
}

export default CaseReportView;
