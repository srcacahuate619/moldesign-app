"use client";

// =====================================================================
// CaseContextPanel — las preguntas científicas, como ficha editable
// =====================================================================
//
// NO es un interrogatorio obligatorio. Cada respuesta puede quedar en "No
// definido" y el caso sigue funcionando. El objetivo es que el dossier pueda
// declarar despues QUE se preguntaba y QUE supuestos se hicieron; obligar a
// contestar antes de dejar trabajar produciria respuestas de relleno, que es
// peor que un hueco declarado.
//
// CLASIFICACION VISUAL. Tres niveles, y en este sprint solo se usan dos:
//   · Advertencia científica  el dossier quedará incompleto sin esto
//   · Contexto opcional       no afecta a ninguna afirmación
// El nivel `blocker` existe en el tipo pero NO se asigna a ningun campo: no se
// inventan reglas cientificas nuevas en este sprint.
//
// Autosave discreto: "Guardando… / Guardado / Error al guardar". Sin toast
// celebratorio por cada tecla.

import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";

import {
  CASE_CONTEXT_SPECS,
  CASE_STUDY_KIND_LABELS,
  summarizePendingContext,
  type CaseContext,
  type CaseContextField,
  type CaseFieldSeverity,
} from "../../lib/cases/types";
import type { SaveState } from "../../context/CaseContext";

export interface CaseContextPanelProps {
  readonly context: CaseContext;
  readonly saveState: SaveState;
  readonly onChange: (patch: Partial<CaseContext>) => void;
  /** Reintenta la escritura que falló. El cambio sigue en la cola. */
  readonly onRetry?: () => void | Promise<void>;
  /**
   * Dentro de «Detalles del caso»: el contenedor ya pone título y recuento.
   *
   * Sin esto el panel repetía su propio encabezado «Contexto» debajo del del
   * drawer, y dos títulos seguidos para la misma cosa hacen que un lector de
   * pantalla anuncie dos secciones donde sólo hay una.
   */
  readonly embedded?: boolean;
}

const SEVERITY_LABEL: Record<CaseFieldSeverity, string> = {
  blocker: "Bloqueante técnico",
  warning: "Advertencia científica",
  info: "Contexto opcional",
};

const SEVERITY_CLASS: Record<CaseFieldSeverity, string> = {
  blocker: "border-red-500/40 text-red-300",
  warning: "border-amber-500/40 text-amber-300",
  info: "border-surface-600 text-zinc-400",
};

function SaveIndicator({ state }: { state: SaveState }) {
  const text =
    state === "saving" ? "Guardando…"
    : state === "saved" ? "Guardado."
    : state === "error" ? "Error al guardar."
    : "";
  if (!text) return null;
  return (
    <span
      role="status"
      aria-live="polite"
      className={`font-mono text-[11px] ${state === "error" ? "text-red-400" : "text-zinc-500"}`}
    >
      {text}
    </span>
  );
}

/**
 * Campo con borrador local.
 *
 * El valor se mantiene aqui mientras se escribe y se propaga al contexto en
 * cada cambio; el debounce del autosave vive en `CaseContext`. Sin borrador
 * local, cada re-render del provider podria devolver el cursor al final del
 * textarea a mitad de una frase.
 */
function ContextField({
  field,
  question,
  severity,
  hint,
  value,
  onCommit,
}: {
  field: CaseContextField;
  question: string;
  severity: CaseFieldSeverity;
  hint: string;
  value: string | undefined;
  onCommit: (field: CaseContextField, value: string) => void;
}) {
  const { t } = useLanguage();
  const [draft, setDraft] = useState(value ?? "");
  const lastExternal = useRef(value ?? "");

  // Sincroniza si el valor cambia POR FUERA (cambio de caso, recarga).
  useEffect(() => {
    const incoming = value ?? "";
    if (incoming !== lastExternal.current) {
      lastExternal.current = incoming;
      setDraft(incoming);
    }
  }, [value]);

  const answered = draft.trim().length > 0;
  const fieldId = `case-context-${field}`;

  return (
    <div className="border-b border-surface-800 py-4 last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor={fieldId} className="text-sm font-medium text-zinc-200">
          {question}
        </label>
        <span
          className={`shrink-0 whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${SEVERITY_CLASS[severity]}`}
        >
          {SEVERITY_LABEL[severity]}
        </span>
      </div>

      <p className="mt-1 text-xs leading-relaxed text-zinc-500">{hint}</p>

      <textarea
        id={fieldId}
        rows={2}
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
          lastExternal.current = event.target.value;
          onCommit(field, event.target.value);
        }}
        placeholder={t("c_no_definido")}
        className="mt-2 w-full resize-y rounded-md border border-surface-800 bg-surface-950 px-3 py-2 text-sm leading-relaxed text-zinc-100 placeholder:text-zinc-600 focus-visible:border-brand-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500"
      />

      {!answered && (
        <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
          {t("c_no_definido")}
        </p>
      )}
    </div>
  );
}

export function CaseContextPanel({
  context,
  saveState,
  onChange,
  onRetry,
  embedded = false,
}: CaseContextPanelProps) {
  const { t } = useLanguage();
  const pending = summarizePendingContext(context);

  const commit = (field: CaseContextField, value: string) => {
    // Una cadena en blanco vuelve a "No definido": borrar una respuesta debe
    // poder devolver el campo a su estado sin respuesta, no dejar un "".
    onChange({ [field]: value.trim().length > 0 ? value : undefined } as Partial<CaseContext>);
  };

  return (
    <section
      {...(embedded ? { "aria-label": "Contexto científico" } : { "aria-labelledby": "case-context-heading" })}
      className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        {!embedded && (
          <h2 id="case-context-heading" className="text-sm font-semibold tracking-tight text-zinc-100">
            Contexto
          </h2>
        )}
        <span className="flex items-center gap-2">
          <SaveIndicator state={saveState} />
          {saveState === "error" && onRetry && (
            <button
              type="button"
              onClick={() => void onRetry()}
              className="rounded border border-red-500/40 px-2 py-0.5 text-[11px] text-red-300 hover:text-red-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
            >
              Reintentar
            </button>
          )}
        </span>
      </div>

      <p className="mt-2 text-xs leading-relaxed text-zinc-500">
        {t("ca_nada_bloquea")}
      </p>

      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 border-y border-surface-800 py-2 font-mono text-[11px] text-zinc-500">
        <div className="flex gap-1.5">
          <dt>Tipo:</dt>
          <dd className="text-zinc-400">
            {context.studyKind ? CASE_STUDY_KIND_LABELS[context.studyKind] : t("c_no_definido")}
          </dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Pendientes:</dt>
          <dd className="text-zinc-400">
            {pending.total === 0
              ? "ninguna"
              : `${pending.warnings} advertencia${pending.warnings === 1 ? "" : "s"}, ${pending.info} opcional${pending.info === 1 ? "" : "es"}`}
          </dd>
        </div>
      </dl>

      <div className="mt-2">
        {CASE_CONTEXT_SPECS.map((spec) => (
          <ContextField
            key={spec.field}
            field={spec.field}
            question={spec.question}
            severity={spec.severity}
            hint={spec.hint}
            value={context[spec.field]}
            onCommit={commit}
          />
        ))}
      </div>
    </section>
  );
}

export default CaseContextPanel;
