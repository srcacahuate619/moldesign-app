"use client";

import { useEffect, useId, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { getEvaluationResult } from "../../lib/api";
import type { EvidenceMolecule } from "../../lib/cohorts";
import type { EvaluationResult } from "../../lib/types";
import { numeroOGuion } from "../../lib/formatoNumerico";
import { InsigniaDelCatalogo } from "../science/InsigniaDelCatalogo";
import { useCatalogoDeReceptores } from "../../hooks/useCatalogoDeReceptores";
import { receptorPorPdbId, seccionDelReceptor } from "../../lib/seccionCatalogo";

/** Sólo consulta el snapshot identificado. Una referencia antigua no abre la proyección actual. */
export function BatchRowResult({ row, pdbId }: { row: EvidenceMolecule; pdbId?: string }) {
  const { t } = useLanguage();
  const id = useId();
  const catalogo = useCatalogoDeReceptores(Boolean(pdbId));
  const verificado = seccionDelReceptor(receptorPorPdbId(pdbId, catalogo)) === "verificado";
  let identidad: string | null = null;
  try { identidad = window.localStorage.getItem("moldesign_auth"); } catch { /* Almacenamiento no disponible. */ }
  const [expanded, setExpanded] = useState(false);
  const consultar = expanded || verificado;
  const [savedDetail, setDetail] = useState<{ identidad: string | null; pdbId?: string; moleculeId: string; taskId: string; result?: EvaluationResult; error?: string | null } | null>(null);
  const taskId = row.task_id;
  const moleculeId = row.molecule_id;
  const detail = savedDetail?.identidad === identidad && savedDetail?.pdbId === pdbId && savedDetail?.moleculeId === moleculeId && savedDetail?.taskId === taskId ? savedDetail : null;
  useEffect(() => {
    if (!consultar || !taskId || !moleculeId) return;
    let alive = true;
    getEvaluationResult(moleculeId, taskId).then(
      (result) => { if (alive) setDetail({ identidad, pdbId, moleculeId, taskId, result }); },
      (error: unknown) => { if (alive) setDetail({ identidad, pdbId, moleculeId, taskId, error: error instanceof Error ? error.message : null }); },
    );
    return () => { alive = false; };
  }, [consultar, identidad, pdbId, moleculeId, taskId]);
  const motivo = detail && detail.error !== undefined ? detail.error || t("lo_operacion_fallida") : undefined;
  return <div className="mt-2">
    <InsigniaDelCatalogo compacta pdbId={pdbId} corrida={detail?.result} comprobando={!detail?.result} motivo={motivo} />
    <button type="button" disabled={!taskId || !moleculeId}
      title={!taskId ? t("lo_result_no_task") : undefined}
      aria-expanded={expanded} aria-controls={id}
      className="cursor-pointer text-xs underline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      onClick={() => { setExpanded((value) => !value); }}>
      {t("lo_view_run_result")}
    </button>
    {!taskId && <p className="mt-1 text-xs text-[var(--text-dim)]">{t("lo_result_no_task")}</p>}
    {expanded && <div id={id} className="mt-2 max-w-sm border border-[var(--border)] p-3">
      {detail === null ? <p role="status">{t("ca_recuperando_resultado")}</p> : motivo ?
        <p role="alert">{motivo}</p> : detail.result ? <>
          <InsigniaDelCatalogo pdbId={pdbId} corrida={detail.result} />
          <dl className="space-y-2">
            <div><dt>{t("lo_th_afinidad_vina")}</dt><dd>{numeroOGuion(detail.result.affinity_kcal, 2, " kcal/mol")}</dd></div>
            <div><dt>{t("ca_history_poses")}</dt><dd>{detail.result.docking_poses?.length ?? 0}</dd></div>
            <div><dt>{t("c_motor")}</dt><dd>{detail.result.vina_version ?? t("lo_no_disponible")}</dd></div>
            <div><dt>{t("se_gen_seed")}</dt><dd>{detail.result.vina_random_seed ?? t("lo_no_disponible")}</dd></div>
          </dl>
          <p className="mt-2 break-all font-mono">{taskId}</p>
          <p className="mt-2 text-xs">{t("lo_result_limit")}</p>
        </> : null}
    </div>}
  </div>;
}
