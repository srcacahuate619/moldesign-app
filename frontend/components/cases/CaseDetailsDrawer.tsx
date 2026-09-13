"use client";

// =====================================================================
// CaseDetailsDrawer — el contexto científico, sin ser un peaje de entrada
// =====================================================================
//
// POR QUÉ DEJA DE SER UNA PESTAÑA. «Contexto» era el primer destino del caso:
// al crear uno, lo primero que aparecía era un cuestionario de siete preguntas
// que nadie había pedido y que no desbloqueaba nada. El producto se presentaba
// como un formulario, no como un instrumento.
//
// Las preguntas NO se eliminan —alimentan el dossier y son lo que permite
// declarar supuestos— pero pasan a estar donde corresponde: a un botón de
// distancia desde la evaluación, abiertas cuando alguien quiere responderlas.
//
// LO QUE ESTE PANEL NO HACE:
//   · no bloquea la ejecución;
//   · no convierte los huecos en alarma — «5 detalles pendientes» es un
//     recuento, no una advertencia roja;
//   · no rellena nada por su cuenta: lo que falta se declara «No definido».
//
// Accesibilidad: `role="dialog"` + `aria-modal`, foco inicial dentro, trampa
// de foco con Tab/Shift+Tab, Escape cierra y el foco vuelve al abridor. El
// botón que lo abre lleva `aria-expanded` y `aria-controls` apuntando aquí.

import { useCallback, useEffect, useRef } from "react";
import { X } from "lucide-react";

import { CaseContextPanel } from "./CaseContextPanel";
import type { SaveState } from "../../context/CaseContext";
import {
  summarizePendingContext,
  type CaseContext as CaseContextData,
} from "../../lib/cases/types";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Texto del recuento. En singular cuando toca; «ninguno» cuando no falta nada. */
export function describePendingDetails(context: CaseContextData): string {
  const { total } = summarizePendingContext(context);
  if (total === 0) return "Sin detalles pendientes";
  return `${total} ${total === 1 ? "detalle pendiente" : "detalles pendientes"}`;
}

export interface CaseDetailsDrawerProps {
  readonly id: string;
  readonly open: boolean;
  readonly onClose: () => void;
  readonly context: CaseContextData;
  readonly saveState: SaveState;
  readonly onChange: (patch: Partial<CaseContextData>) => void;
  readonly onRetry?: () => void | Promise<void>;
}

export function CaseDetailsDrawer({
  id,
  open,
  onClose,
  context,
  saveState,
  onChange,
  onRetry,
}: CaseDetailsDrawerProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = `${id}-title`;

  useEffect(() => {
    if (!open) {
      // El foco vuelve a quien abrió, no al principio del documento: perderlo
      // obliga a rehacer toda la navegación por teclado.
      openerRef.current?.focus?.();
      openerRef.current = null;
      return;
    }
    openerRef.current = (document.activeElement as HTMLElement) ?? null;
    const first = panelRef.current?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
  }, [open]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const root = panelRef.current;
      if (!root) return;
      const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onKeyDown={handleKeyDown}>
      <div className="absolute inset-0 bg-black/60" onClick={onClose} aria-hidden="true" />
      <div
        id={id}
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 flex h-full w-full max-w-md flex-col border-l border-surface-800 bg-surface-900 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-surface-800 px-4 py-3">
          <div className="min-w-0">
            <h2 id={titleId} className="text-sm font-semibold tracking-tight text-zinc-100">
              Detalles del caso
            </h2>
            <p className="mt-0.5 font-mono text-[11px] text-zinc-500">
              {describePendingDetails(context)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar detalles del caso"
            className="shrink-0 rounded p-1.5 text-zinc-500 transition-colors hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <CaseContextPanel
            context={context}
            saveState={saveState}
            onChange={onChange}
            onRetry={onRetry}
            embedded
          />
        </div>
      </div>
    </div>
  );
}

export default CaseDetailsDrawer;
