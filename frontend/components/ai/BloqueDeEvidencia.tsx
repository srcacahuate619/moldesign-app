"use client";

import React from "react";

/**
 * MOLCHAT-AUD-01, eje FE/UX — la mitad de pantalla del eje científico.
 *
 * El backend inyecta y emite los resultados de herramientas dentro del mismo
 * texto del turno. Hasta la auditoría SCI todos llegaban con el mismo formato,
 * así que un descriptor calculado con RDKit, la salida de un modelo ADMET y un
 * valor traído de PubChem se leían con la misma autoridad. Ahora cada bloque
 * llega etiquetado —`[clase · fuente] herramienta: texto`— y aquí se conserva
 * esa distinción: la prosa del modelo se separa de la evidencia, y cada
 * evidencia se pinta con su clase y su fuente a la vista.
 *
 * La interfaz **no vuelve a clasificar por su cuenta**: si un bloque llega sin
 * clase, se muestra como no verificado en vez de suponerle una.
 */

export type Evidencia = {
  clase: string;
  fuente: string;
  herramienta: string;
  texto: string;
  verificada: boolean;
};

/** Cabecera que el backend antepone al bloque de resultados. */
const CABECERA = /^\[Sistema: resultados de herramientas ejecutadas/;

/** `[clase · fuente] herramienta: texto` — la fuente puede llevar paréntesis. */
const CON_CLASE = /^\[([^·\]]+)·([^\]]+)\]\s*([A-Za-z_][\w]*):\s*([\s\S]*)$/;

/** `[sin clasificar — …] herramienta: texto` */
const SIN_CLASE = /^\[sin clasificar[^\]]*\]\s*([A-Za-z_][\w]*):\s*([\s\S]*)$/;

export function separarEvidencia(contenido: string): {
  prosa: string;
  evidencias: Evidencia[];
} {
  const lineas = contenido.split("\n");
  const inicio = lineas.findIndex((l) => CABECERA.test(l.trim()));
  if (inicio === -1) {
    return { prosa: contenido.trim(), evidencias: [] };
  }

  const prosa = lineas.slice(0, inicio).join("\n").trim();
  const evidencias: Evidencia[] = [];

  for (const cruda of lineas.slice(inicio + 1)) {
    const linea = cruda.trim();
    if (!linea) continue;

    const conClase = linea.match(CON_CLASE);
    if (conClase) {
      evidencias.push({
        clase: conClase[1].trim(),
        fuente: conClase[2].trim(),
        herramienta: conClase[3].trim(),
        texto: conClase[4].trim(),
        verificada: true,
      });
      continue;
    }

    const sinClase = linea.match(SIN_CLASE);
    if (sinClase) {
      evidencias.push({
        clase: "sin clasificar",
        fuente: "",
        herramienta: sinClase[1].trim(),
        texto: sinClase[2].trim(),
        verificada: false,
      });
      continue;
    }

    // Continuación de la línea anterior (una herramienta puede devolver varias
    // líneas). No se descarta: descartarla perdería parte del dato.
    if (evidencias.length > 0) {
      const ultima = evidencias[evidencias.length - 1];
      ultima.texto = `${ultima.texto}\n${linea}`;
    }
  }

  return { prosa, evidencias };
}

/** Color por clase. La inferencia se distingue a propósito del cálculo. */
function colorDe(clase: string, verificada: boolean): string {
  if (!verificada) return "#F59E0B";
  if (/inferencia/i.test(clase)) return "#A78BFA";
  if (/recuperaci/i.test(clase)) return "#38BDF8";
  if (/persistido/i.test(clase)) return "#34D399";
  return "#94A3B8";
}

export function BloqueDeEvidencia({ evidencias }: { evidencias: Evidencia[] }) {
  if (evidencias.length === 0) return null;

  return (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
      <div
        style={{
          fontSize: "0.72em",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          color: "var(--text-dim, #94A3B8)",
        }}
      >
        Evidencia usada en esta respuesta
      </div>
      {evidencias.map((e, i) => (
        <div
          key={`${e.herramienta}-${i}`}
          data-testid="evidencia"
          style={{
            border: "1px solid var(--border)",
            borderLeft: `3px solid ${colorDe(e.clase, e.verificada)}`,
            borderRadius: 6,
            padding: "6px 10px",
            background: "rgba(255,255,255,0.03)",
            fontSize: "0.82em",
          }}
        >
          <div style={{ color: colorDe(e.clase, e.verificada), marginBottom: 2 }}>
            {e.verificada
              ? `${e.clase} · ${e.fuente}`
              : "sin clasificar — trátalo como no verificado"}
          </div>
          <div style={{ color: "var(--text-secondary)", marginBottom: 2 }}>
            {e.herramienta}
          </div>
          <pre
            style={{
              margin: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontFamily: "inherit",
              color: "var(--text)",
            }}
          >
            {e.texto}
          </pre>
        </div>
      ))}
    </div>
  );
}
