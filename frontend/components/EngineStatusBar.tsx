"use client";

// =====================================================================
// EngineStatusBar — el motor dice qué le pasa, y se puede reintentar
// =====================================================================
//
// LO QUE SUSTITUYE. El arranque del backend se envolvía en `catch {}`. Cuando
// fallaba, lo único que veía el usuario era el aviso de «modelos pendientes»
// del launcher: un diagnóstico falso: con el motor instalado y un fallo de
// arranque, invitaba a descargar de nuevo casi un gigabyte que ya estaba en
// disco. Y cuando el problema era el contrato de salud —el caso real de este
// sprint— no había absolutamente ninguna señal.
//
// LO QUE NO ES. No es una consola técnica ni un panel de diagnóstico. Es una
// franja: el estado, la razón exacta cuando la hay, y «Reintentar».
//
// No aparece cuando el motor está listo. Un indicador permanente de que todo va
// bien es ruido, y además entrena a ignorar la franja el día que diga algo.

import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";

import { useDownload } from "../hooks/useDownload";
import { ENGINE_LABELS, type EngineState } from "../context/DownloadProvider";

/** Qué significa cada fallo para quien lo está leyendo, sin jerga de proceso. */
const ENGINE_EXPLANATION: Partial<Record<EngineState, string>> = {
  not_installed:
    "Falta una parte del runtime de cálculo en disco (Python, el backend o Vina). Repara o reinstala MolDesign; los modelos opcionales no sustituyen este runtime.",
  spawn_failed:
    "El proceso del motor no llegó a ejecutarse. Suele ser un permiso o un ejecutable que falta.",
  health_failed:
    "El proceso arrancó pero no se identificó como el backend de MolDesign. Suele significar que se está ejecutando una copia desactualizada del backend.",
  disconnected:
    "El motor estaba disponible y dejó de responder. La evaluación no podrá continuar hasta que vuelva.",
};

export function EngineStatusBar() {
  const { engine, retryEngine } = useDownload();
  const [retrying, setRetrying] = useState(false);

  // Sin nada que decir, no se dice nada.
  if (engine.state === "ready" || engine.state === "idle") return null;

  const starting = engine.state === "starting";
  const tone = starting
    ? "border-surface-700 bg-surface-900 text-zinc-300"
    : "border-amber-500/30 bg-amber-500/10 text-amber-200";

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-wrap items-center gap-2 border-b px-4 py-2 text-xs leading-relaxed sm:px-6 ${tone}`}
    >
      {starting ? (
        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
      ) : (
        <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      )}

      <span className="min-w-0 flex-1">
        <strong className="font-medium">{ENGINE_LABELS[engine.state]}.</strong>{" "}
        {ENGINE_EXPLANATION[engine.state] ??
          "El motor está preparándose. La evaluación estará disponible en cuanto responda."}
        {/* La razón EXACTA que dio Rust. Es lo que convierte «no arranca» en algo
            accionable, y es también lo que se pega en un informe de fallo. */}
        {engine.detail && (
          <span className="mt-1 block break-words font-mono text-[11px] opacity-80">
            {engine.detail}
          </span>
        )}
      </span>

      {!starting && (
        <button
          type="button"
          disabled={retrying}
          onClick={async () => {
            setRetrying(true);
            try {
              await retryEngine();
            } finally {
              setRetrying(false);
            }
          }}
          className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded border border-amber-500/40 px-2 py-0.5 text-[11px] transition-colors hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw
            className={`h-3 w-3 ${retrying ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          {retrying ? "Reintentando…" : "Reintentar"}
        </button>
      )}
    </div>
  );
}

export default EngineStatusBar;
