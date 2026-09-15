
import { useLanguage } from "@/context/LanguageContext";
/**
 * Aviso breve reutilizable para cualquier vista que muestre señales del pipeline.
 * Mantiene la separación entre observaciones, interpretaciones y decisiones.
 */
export function MethodDisclaimer() {
  const { t } = useLanguage();
  return (
    <section className="rounded-xl border border-blue-800/30 bg-blue-950/20 p-5 text-xs">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-blue-300">
        <span aria-hidden="true">ℹ️</span> {t("pn_limitaciones")}
      </h3>
      <ul className="list-disc space-y-1.5 pl-4 leading-relaxed text-surface-400">
        <li>
          {t("pn_vina_devuelve")} <strong className="text-gray-300">{t("pn_score_empirico")}</strong> {t("pn_vina_no_equivale")}
        </li>
        <li>
          {t("pn_rescoring_dominio")}
        </li>
        <li>
          {t("pn_admet_descriptores")}
        </li>
        <li>
          {t("pn_ums_abstencion")}
        </li>
        <li>
          {t("pn_prioriza_no_sustituye")}
        </li>
      </ul>
    </section>
  );
}