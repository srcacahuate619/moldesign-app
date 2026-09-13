"use client";

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
};

const ETIQUETA: Record<NivelDeCalibracion, string> = {
  calibrado: "Calibrado",
  pipeline_de_familia: "Pipeline de familia",
  curado_estructural: "Curado estructuralmente",
  sin_curar: "Sin curar",
};

const COLOR: Record<NivelDeCalibracion, string> = {
  calibrado: "#34D399",
  pipeline_de_familia: "#60A5FA",
  curado_estructural: "#F59E0B",
  sin_curar: "#F87171",
};

const SIN_COMPROBAR = "Respaldo sin comprobar";

export function nivelLegible(nivel: NivelDeCalibracion | null | undefined): string {
  if (!nivel || !(nivel in ETIQUETA)) return SIN_COMPROBAR;
  return ETIQUETA[nivel];
}

/** Sin dato del backend se advierte igual: el ausente no es un aprobado. */
export function necesitaAdvertencia(calibracion: Calibracion | null | undefined): boolean {
  if (!calibracion) return true;
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
  const color = colorDe(calibracion);
  const etiqueta = nivelLegible(calibracion?.nivel);
  const advierte = necesitaAdvertencia(calibracion);

  const detalle = calibracion
    ? calibracion.resumen
    : "El backend no informó el respaldo de este receptor.";

  const rho =
    calibracion && calibracion.spearman_rho !== null
      ? `ρ = ${calibracion.spearman_rho}`
      : "ρ no medido";

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
            "No se pudo comprobar si el ranking del motor está respaldado para " +
              "este receptor. Trata el resultado como una hipótesis: no cites " +
              "el score como evidencia de afinidad."}
        </p>
      )}
    </div>
  );
}
