"use client";


import { useLanguage } from "@/context/LanguageContext";
import React from "react";

/**
 * SC-9 — qué respaldo científico tiene el receptor, dicho en la pantalla.
 *
 * El catálogo tiene 387 receptores curados **estructuralmente** y ninguno
 * calibrado: `spearman_rho` existe en 2 de 387 y los dos valen `0.0` —el valor
 * por defecto, y que de ser real significaría que no hay correlación—. Aun así
 * la interfaz presentaba scores, tiers y rankings con el mismo aspecto para
 * todos, y «está en el catálogo» se leía como «está validado».
 *
 * El nivel lo calcula el backend en un solo sitio
 * (`services/targets/calibracion.py`) y llega en el contrato. Este componente
 * **no lo recalcula**: si lo dedujera del ρ tendríamos dos reglas, y la que se
 * quedara desactualizada sería la que el investigador ve.
 *
 * Regla del ausente: sin dato no se dice «calibrado», se dice «sin comprobar».
 * No saber qué respaldo hay no es lo mismo que saber que lo hay.
 */

export type NivelDeCalibracion =
  | "calibrado"
  | "pipeline_de_familia"
  | "curado_estructural"
  | "sin_curar";

export type Calibracion = {
  nivel: NivelDeCalibracion;
  spearman_rho: number | null;
  structural_family: string | null;
  tiene_pipeline_de_familia: boolean;
  resumen: string;
  advertencia: string;
  motivo: string;
  requiere_advertencia: boolean;
  /** La medida que respalda un «calibrado» (SCI-D-001). Un backend anterior no la envía. */
  respaldo?: { rho: number; ic95: [number, number]; n: number; panel: string } | null;
};

/** Un «calibrado» sólo cuenta con su medida: n entero e IC finito. */
function respaldoCompleto(calibracion: Calibracion): boolean {
  const r = calibracion.respaldo;
  return !!r && Number.isFinite(r.rho) && Array.isArray(r.ic95) && r.ic95.length === 2
    && r.ic95.every(Number.isFinite) && Number.isInteger(r.n) && r.n > 0;
}

const ETIQUETA: Record<NivelDeCalibracion, string> = {
  calibrado: "Calibrado",
  pipeline_de_familia: "Pipeline de familia",
  curado_estructural: "Curado estructuralmente",
  sin_curar: "Sin curar",
};

const ETIQUETA_EN: Record<NivelDeCalibracion, string> = {
  calibrado: "Calibrated",
  pipeline_de_familia: "Family pipeline",
  curado_estructural: "Structurally curated",
  sin_curar: "Uncurated",
};

const COLOR: Record<NivelDeCalibracion, string> = {
  calibrado: "#34D399",
  pipeline_de_familia: "#60A5FA",
  curado_estructural: "#F59E0B",
  sin_curar: "#F87171",
};

const SIN_COMPROBAR = "Respaldo sin comprobar";
const SUPPORT_NOT_ASSESSED = "Support not assessed";

export function nivelLegible(
  nivel: NivelDeCalibracion | null | undefined,
  idioma: "es" | "en" = "es",
): string {
  const etiquetas = idioma === "en" ? ETIQUETA_EN : ETIQUETA;
  if (!nivel || !(nivel in etiquetas)) {
    return idioma === "en" ? SUPPORT_NOT_ASSESSED : SIN_COMPROBAR;
  }
  return etiquetas[nivel];
}

export function rhoSinMedir(idioma: "es" | "en" = "es"): string {
  return idioma === "en" ? "ρ not measured" : "ρ no medido";
}

/** Sin dato del backend se advierte igual: el ausente no es un aprobado. */
export function necesitaAdvertencia(calibracion: Calibracion | null | undefined): boolean {
  if (!calibracion) return true;
  // SCI-D-001: un «calibrado» que no trae su medida tampoco suprime la reserva.
  if (calibracion.nivel === "calibrado" && !respaldoCompleto(calibracion)) return true;
  return calibracion.requiere_advertencia !== false;
}

function colorDe(calibracion: Calibracion | null | undefined): string {
  if (!calibracion || !(calibracion.nivel in COLOR)) return "#94A3B8";
  return COLOR[calibracion.nivel];
}

type Props = {
  calibracion: Calibracion | null | undefined;
  /** Muestra el párrafo completo, no sólo la insignia. */
  mostrarAdvertencia?: boolean;
  compacto?: boolean;
};

export function RespaldoDelReceptor({
  calibracion,
  mostrarAdvertencia = false,
  compacto = false,
}: Props) {
  const { t, locale } = useLanguage();
  const idioma = locale === "en" ? "en" : "es";
  const color = colorDe(calibracion);
  const etiqueta = nivelLegible(calibracion?.nivel, idioma);
  const advierte = necesitaAdvertencia(calibracion);

  const detalle = calibracion
    ? calibracion.resumen
    : idioma === "en"
      ? "The backend did not report this receptor's evidence status."
      : "El backend no informó el respaldo de este receptor.";

  const rho =
    calibracion && respaldoCompleto(calibracion) && calibracion.respaldo
      ? `ρ = ${calibracion.respaldo.rho.toFixed(2)} · ${idioma === "en" ? "95% CI" : "IC 95 %"} [${calibracion.respaldo.ic95[0].toFixed(2)}; ${calibracion.respaldo.ic95[1].toFixed(2)}] · n = ${calibracion.respaldo.n}`
      : rhoSinMedir(idioma);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span
        data-testid="respaldo-receptor"
        title={detalle}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          alignSelf: "flex-start",
          border: `1px solid ${color}`,
          borderRadius: 999,
          padding: compacto ? "1px 8px" : "3px 10px",
          fontSize: compacto ? "0.72em" : "0.78em",
          color,
          whiteSpace: "nowrap",
        }}
      >
        <span
          aria-hidden
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: color,
            flexShrink: 0,
          }}
        />
        {etiqueta}
        <span style={{ opacity: 0.75 }}>· {rho}</span>
        {!compacto && (
          <span style={{ opacity: 0.001, position: "absolute", left: -9999 }}>
            {detalle}
          </span>
        )}
      </span>

      {mostrarAdvertencia && advierte && (
        <p
          data-testid="advertencia-calibracion"
          role="note"
          style={{
            margin: 0,
            fontSize: "0.8em",
            lineHeight: 1.5,
            color: "var(--text-secondary)",
            borderLeft: `3px solid ${color}`,
            paddingLeft: 10,
          }}
        >
          {calibracion?.advertencia ||
            t("auto_ce72cf899871") +
              t("auto_dbfb7d741250") +
              t("auto_8a59609e15c0")}
        </p>
      )}
    </div>
  );
}
