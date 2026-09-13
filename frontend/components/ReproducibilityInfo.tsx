import type { EvaluationResult } from "../lib/types";
import { RespaldoDelReceptor } from "./science/RespaldoDelReceptor";

type Props = {
  result: EvaluationResult;
};

export function ReproducibilityInfo({ result }: Props) {
  const hasInfo = result.vina_version || result.vina_random_seed !== null || result.parsing_source;

  if (!hasInfo) return null;

  return (
    <section className="space-y-2 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <h3 className="font-bold text-white">Reproducibilidad</h3>
      {/* SC-9: el respaldo del receptor se lee JUNTO al resultado, no sólo
          antes de ejecutar. Es donde el investigador mira el número. */}
      <RespaldoDelReceptor calibracion={result.target_calibracion} mostrarAdvertencia />
      <p className="text-xs text-surface-400">
        Parámetros clave para reproducir este resultado.
      </p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <span className="text-surface-400">ML Rescore</span>
        <span className="text-brand-400 font-semibold">
          v6.9{" "}
          {result.target_spearman_rho != null && result.target_spearman_rho !== 0
            ? `(Spearman ρ = ${result.target_spearman_rho.toFixed(3)})`
            : <span className="text-yellow-500/80 text-xs font-normal">(Spearman: Pendiente de recálculo)</span>
          }
        </span>
        
        {result.vina_version && (
          <>
            <span className="text-surface-400">AutoDock Vina</span>
            <span className="text-gray-300">{result.vina_version}</span>
          </>
        )}
        {result.vina_random_seed !== null && result.vina_random_seed !== undefined && (
          <>
            <span className="text-surface-400">Random seed</span>
            <span className="text-gray-300">{result.vina_random_seed}</span>
          </>
        )}
        {result.evaluated_at && (
          <>
            <span className="text-surface-400">Evaluado</span>
            <span className="text-gray-300">{new Date(result.evaluated_at).toLocaleString()}</span>
          </>
        )}
      </div>
    </section>
  );
}
