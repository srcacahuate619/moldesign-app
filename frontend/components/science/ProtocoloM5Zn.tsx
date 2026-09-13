"use client";

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
      "Esta corrida es anterior a que M5-Zn se conectara al pipeline. Se puntuó con M4 y los pesos por defecto del stacking.",
  },
  REVIEW_OUT_OF_VALIDATED_TARGET: {
    titulo: "Revisar · fuera de las dianas validadas",
    detalle:
      "Es una metaloenzima de zinc, pero su PDB no es ninguno de los tres perfiles validados. No se heredan los pesos de otra diana.",
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
      aria-label="Protocolo M5-Zn"
      className="rounded-xl border border-white/10 bg-white/[0.02] p-4"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-white/50">
          Protocolo M5-Zn · metaloenzimas de zinc
        </h3>
        {resultado.m5_protocol_id && (
          <span className="font-mono text-[11px] text-white/30">
            {resultado.m5_protocol_id}
          </span>
        )}
      </header>

      <p
        className={`mt-3 font-mono text-xs font-bold ${
          habilitado ? "text-emerald-300" : "text-amber-300"
        }`}
      >
        {explicacion.titulo}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-white/50">
        {explicacion.detalle}
      </p>

      {resultado.m5_missing_components && resultado.m5_missing_components.length > 0 && (
        <p className="mt-2 font-mono text-[11px] text-amber-300/80">
          Componentes ausentes: {resultado.m5_missing_components.join(", ")}
        </p>
      )}

      {resultado.m5_score != null && (
        <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3">
          <p className="font-mono text-[10px] uppercase tracking-wider text-white/30">
            {habilitado ? "Score compuesto" : "Evidencia de auditoría"}
          </p>
          <p className="mt-1 font-mono text-lg text-white/80">
            {resultado.m5_score.toFixed(4)}
          </p>
          {!habilitado && (
            <p className="mt-1 text-[11px] leading-relaxed text-amber-300/70">
              Este número no entra en el score total, ni en el ranking, ni en la
              recomendación, ni en el veredicto. Se muestra para que pueda
              auditarse.
            </p>
          )}
        </div>
      )}

      {resultado.ums_warhead != null && (
        <p className="mt-3 font-mono text-[11px] text-white/40">
          Señal · warheads de zinc (UMS, SMARTS):{" "}
          <span className="text-white/70">
            {resultado.ums_warhead.toFixed(4)}
          </span>{" "}
          — informativa, con peso 0 en el ranking
        </p>
      )}
    </section>
  );
}

export default ProtocoloM5Zn;
