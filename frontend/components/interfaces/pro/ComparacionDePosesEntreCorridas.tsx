"use client";

// Comparar la pose de ESTA molécula entre la evaluación en pantalla y otra suya. Lo que predomina es lo visual: el
// botón abre el comparador 3D, donde cada lado elige su evaluación y su pose entre las que cada una conservó. Las
// distancias y las diferencias de protocolo las mide el backend y se enseñan allí, junto a lo que se ve.

import { useMemo, useState } from "react";
import { GitCompareArrows } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { etiquetaDeCorrida, type FuenteDeCorrida } from "../../../lib/comparadorDePoses";
import type { CaseRun } from "../../../lib/cases/types";
import { PoseComparisonDialog } from "./PoseComparisonDialog";

/** Las otras evaluaciones terminadas de la misma molécula, la más reciente primero. */
export function otrasCorridasDeLaMolecula(
  moleculeId: string | null | undefined,
  taskId: string | null | undefined,
  caseRuns: readonly CaseRun[] | undefined,
): CaseRun[] {
  if (!moleculeId || !taskId || !caseRuns) return [];
  return caseRuns
    .filter((run) => run.moleculeId === moleculeId && run.taskId !== taskId && run.executionState === "completed")
    .slice()
    .reverse();
}

export function ComparacionDePosesEntreCorridas({
  moleculeId,
  taskId,
  otras,
  delCaso,
}: {
  moleculeId: string;
  taskId: string;
  otras: readonly CaseRun[];
  /** Todas las corridas del caso: el comparador deja cambiar de lado a cualquiera de ellas. */
  delCaso: readonly FuenteDeCorrida[];
}) {
  const { t, locale } = useLanguage();
  const [elegida, setElegida] = useState<string>(otras[0]?.taskId ?? "");
  const [abierto, setAbierto] = useState(false);

  const derecha = useMemo<FuenteDeCorrida | undefined>(() => {
    const run = otras.find((r) => r.taskId === elegida) ?? otras[0];
    return run
      ? { taskId: run.taskId, moleculeId: run.moleculeId as string, etiqueta: etiquetaDeCorrida(run, t, locale) }
      : undefined;
  }, [otras, elegida, t, locale]);

  if (otras.length === 0 || !derecha) return null;

  return (
    <section aria-label={t("pn_cmp_titulo")} className="space-y-3 rounded-xl border border-white/10 bg-black/30 p-4 font-sans">
      <div>
        <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-zinc-300">
          <GitCompareArrows size={16} className="text-purple-400" aria-hidden="true" />
          {t("pn_cmp_titulo")}
        </h3>
        <p className="mt-1 text-base leading-6 text-zinc-400">{t("pn_cmp_ayuda")}</p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="block min-w-0 flex-1 space-y-1.5 text-sm font-medium text-zinc-200">
          <span>{t("pn_cmp_elegir")}</span>
          <select
            value={derecha.taskId}
            onChange={(event) => setElegida(event.target.value)}
            className="min-h-11 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 text-base text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400"
          >
            {otras.map((run) => (
              <option key={run.taskId} value={run.taskId}>{etiquetaDeCorrida(run, t, locale)}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => setAbierto(true)}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-purple-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
        >
          <GitCompareArrows size={16} aria-hidden="true" />
          {t("pn_cmp3d_abrir")}
        </button>
      </div>
      {abierto && (
        <PoseComparisonDialog
          moleculeId={moleculeId}
          taskId={taskId}
          leftRank={1}
          rightRank={1}
          rightSource={derecha}
          runs={delCaso}
          onClose={() => setAbierto(false)}
        />
      )}
    </section>
  );
}
