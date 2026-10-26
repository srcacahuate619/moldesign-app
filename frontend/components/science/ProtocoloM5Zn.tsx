"use client";


import { useLanguage } from "@/context/LanguageContext";
/**
 * El resultado de M5-Zn tal como la corrida lo persistió. Sin recalcular nada.
 *
 * ═══════════════════════════════════════════════════════════════════════
 * LA REGLA QUE ESTE COMPONENTE OBEDECE
 * ═══════════════════════════════════════════════════════════════════════
 *
 *   Sólo un resultado con estado explícito VALIDATED puede alimentar una
 *   decisión derivada. Cualquier otro estado queda excluido.
 *
 * Aquí eso significa dos cosas concretas:
 *
 *   1. **El estado se pinta, no se deduce.** Si el backend manda
 *      `REVIEW_INVALID_BENCHMARK_SITE`, esto muestra exactamente eso —aunque
 *      haya un número al lado y aunque el número sea alto—. La interfaz no
 *      "mejora" el estado, no lo interpreta y no lo oculta.
 *
 *   2. **El número no se presenta como conclusión.** Se muestra bajo un
 *      encabezado de auditoría, con su estado y su motivo pegados. Ocultarlo
 *      sería peor: dejaría de poder auditarse justo cuando hace falta.
 *
 * `m5_score` NO entra en `total_score`, ni en el ranking, ni en la
 * recomendación, ni en el veredicto — eso lo garantiza el backend y lo fija
 * `tests/test_invariante_solo_validated_decide.py`.
 */

import type { EvaluationResult } from "../../lib/types";

/** El único estado que habilita una conclusión. Lista blanca de un elemento. */
const ESTADO_HABILITANTE = "VALIDATED";

/** Qué decir de cada estado. La clave es el valor persistido, sin transformar. */
const EXPLICACION: Record<string, { titulo: string; detalle: string }> = {
  VALIDATED: {
    titulo: "Perfil validado",
    detalle:
      "El score compuesto se calculó con el perfil exacto de esta diana. Es un score de ranking derivado, no una afinidad ni una medida experimental.",
  },
  NOT_EVALUATED_MISSING_COMPONENT: {
    titulo: "No evaluado · falta un componente",
    detalle:
      "Faltó al menos un componente con peso distinto de cero en la fórmula del perfil. No se renormalizan pesos ni se sustituye un modelo por otro.",
  },
  NOT_EVALUATED_PROTOCOL_NOT_EXECUTED: {
    titulo: "No evaluado · el protocolo no se ejecutó",
    detalle:
      "La corrida registró que el protocolo M5-Zn no se ejecutó. Los pesos de las señales se muestran por separado, cuando están registrados.",
  },
  REVIEW_OUT_OF_VALIDATED_TARGET: {
    titulo: "Revisar · fuera de las dianas validadas",
    // QA1-009: el estado se dispara con CUALQUIER ion observado en la estructura (Mg, Na, K, Ca…)
    // o con la etiqueta de metaloenzima del catálogo, y no dice cuál de los dos. Afirmar «es una
    // metaloenzima de zinc» era falso en 90 de los 134 receptores que lo reciben sin zinc alguno
    // (BACE1: un Na⁺ del tampón). Se dice sólo lo que es cierto en todos los casos.
    detalle:
      "No se aplicó ningún perfil de M5-Zn a esta diana. La estructura contiene un ion metálico, o el catálogo la declara metaloenzima, y su PDB no es ninguno de los tres perfiles de M5-Zn (implementados y en revisión: ninguno produce hoy VALIDATED). No se heredan los pesos de otra diana. Un ion presente no implica un sitio de unión metálico: puede ser parte del tampón de cristalización.",
  },
  REVIEW_OUT_OF_VALIDATED_STRUCTURE: {
    titulo: "Revisar · otra estructura de la misma proteína",
    detalle:
      "El nombre de la proteína no hereda el perfil: otra estructura puede cambiar cadena, bolsillo, metal, cofactores y caja.",
  },
  REVIEW_INVALID_BENCHMARK_SITE: {
    titulo: "Revisar · el benchmark evaluó el sitio incorrecto",
    detalle:
      "Ningún zinc cae dentro de la caja del benchmark que validó este perfil, y el único metal próximo al centro es un ion de calcio. El número es reproducible y no es evidencia de acoplamiento metaloproteico.",
  },
  REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE: {
    titulo: "Revisar · procedencia del benchmark incompleta",
    detalle:
      "No se ha demostrado que el sitio sea incorrecto, pero tampoco se puede verificar la configuración exacta con la que se validó el perfil.",
  },
  REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING: {
    titulo: "Revisar · la pose puntuada no coordina el metal",
    detalle:
      "La caja sí contenía el zinc, y aun así ninguna pose top-1 de los activos del benchmark acerca un átomo donante al metal. Esas top-1 son las que sostienen el AUC. No se sabe si alguna pose descartada sí coordinaba.",
  },
  BLOCKED_PROTOCOL_NOT_AVAILABLE: {
    titulo: "Bloqueado · sin protocolo para este metal",
    detalle:
      "La diana es metálica y este producto no tiene protocolo validado para ese metal. Se declara en vez de degradarse a M4 en silencio.",
  },
};

export function ProtocoloM5Zn({ resultado }: { resultado: EvaluationResult }) {
  const { t } = useLanguage();
  const estado = resultado.m5_scientific_status;
  // Sin estado no hay bloque: la corrida no ejecutó M5-Zn.
  if (!estado) return null;

  const habilitado = estado === ESTADO_HABILITANTE;
  const explicacion = EXPLICACION[estado] ?? {
    titulo: `Revisar · ${estado}`,
    // Un estado que este cliente no conoce NO se presenta como bueno. Es la
    // misma regla del backend: cerrado por defecto.
    detalle:
      "Este cliente no conoce este estado. Por defecto no habilita ninguna conclusión: consulta el dossier, que lleva el motivo completo.",
  };

  return (
    <section
      aria-label={t("pr_m5_protocol_label")}
      className="rounded-xl border border-white/10 bg-white/[0.02] p-4"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-bold text-zinc-200">
          {t(habilitado ? "pr_m5_applied_profile" : "pr_m5_applicability_check")}
        </h3>
        {resultado.m5_protocol_id && (
          <span className="break-all font-mono text-sm text-zinc-300">
            {resultado.m5_protocol_id}
          </span>
        )}
      </header>

      <p
        className={`mt-3 font-sans text-base font-bold leading-6 ${
          habilitado ? "text-emerald-300" : "text-amber-300"
        }`}
      >
        {explicacion.titulo}
      </p>
      <p className="mt-1 text-base leading-6 text-zinc-300 font-sans">
        {explicacion.detalle}
      </p>

      {resultado.m5_missing_components && resultado.m5_missing_components.length > 0 && (
        <p className="mt-2 font-sans text-base text-amber-300 leading-6">
          {t("auto_ae7a55091885")} {resultado.m5_missing_components.join(", ")}
        </p>
      )}

      {resultado.m5_score != null && (
        <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="font-sans text-sm uppercase tracking-wider text-zinc-400">
            {habilitado ? t("pr_m5_composite_score") : t("auto_0d93be49ed45")}
          </p>
          <p className="mt-1 font-sans text-lg text-white/80">
            {resultado.m5_score.toFixed(4)}
          </p>
          {!habilitado && (
            <p className="mt-1 text-base leading-6 text-amber-300 font-sans">
              {t("pn_m5zn_no_entra")}
            </p>
          )}
        </div>
      )}

      {resultado.ums_warhead != null && (
        <p className="mt-3 font-sans text-base text-zinc-300 leading-6">
          {t("auto_ff7cabb9c513")}{" "}
          <span className="text-white/70">
            {resultado.ums_warhead.toFixed(4)}
          </span>{" "}
          {t("auto_c8b9d71daaca")}
        </p>
      )}
    </section>
  );
}

export default ProtocoloM5Zn;
