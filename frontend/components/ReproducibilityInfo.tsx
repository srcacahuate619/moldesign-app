
import { useLanguage } from "@/context/LanguageContext";
import type { EvaluationResult } from "../lib/types";
import { RespaldoDelReceptor } from "./science/RespaldoDelReceptor";

type Props = {
  result: EvaluationResult;
};

export function ReproducibilityInfo({ result }: Props) {
  const { t } = useLanguage();
  const hasInfo = result.vina_version || result.vina_random_seed !== null || result.parsing_source;

  if (!hasInfo) return null;

  return (
    <section className="space-y-2 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <h3 className="font-bold text-white">{t("pn_reproducibility_title")}</h3>
      {/* SC-9: el respaldo del receptor se lee JUNTO al resultado, no sólo
          antes de ejecutar. Es donde el investigador mira el número. */}
      <RespaldoDelReceptor calibracion={result.target_calibracion} mostrarAdvertencia />
      <p className="text-xs text-surface-400">
        {t("pn_reproducibilidad")}
      </p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <span className="text-surface-400">{t("pn_ml_rescore_label")}</span>
        <span className="text-brand-400 font-semibold">
          v6.9{" "}
          {/* SCI-D-001: la ρ respaldada, no la que trae la fila del receptor. */}
          {result.target_calibracion?.spearman_rho != null
            ? `(Spearman ρ = ${result.target_calibracion.spearman_rho.toFixed(3)})`
            : <span className="text-yellow-500/80 text-xs font-normal">{t("z_spearman_pendiente")}</span>
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
            <span className="text-surface-400">{t("se_gen_seed")}</span>
            <span className="text-gray-300">{result.vina_random_seed}</span>
          </>
        )}
        {result.evaluated_at && (
          <>
            <span className="text-surface-400">{t("pn_evaluated_label")}</span>
            <span className="text-gray-300">{new Date(result.evaluated_at).toLocaleString()}</span>
          </>
        )}
      </div>
    </section>
  );
}
