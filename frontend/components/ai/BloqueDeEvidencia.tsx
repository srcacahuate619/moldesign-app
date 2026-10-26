"use client";


import { useLanguage } from "@/context/LanguageContext";
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
  /** De qué molécula es el resultado («aspirina», «A=aspirina | B=ibuprofeno»), si el backend lo dice. */
  etiqueta?: string;
  texto: string;
  verificada: boolean;
};

/** Cabecera que el backend antepone al bloque de resultados. */
const CABECERA = /^\[Sistema: resultados de herramientas ejecutadas/;

/**
 * Cierre del bloque (`FIN_DE_EVIDENCIA` en `backend/services/ai/tool_registry.py`). Lo
 * que sigue es la respuesta. Sin él, la respuesta determinista o la del modelo quedaban
 * dentro del bloque y, si su primera línea no casaba, se perdían: MolChat contestaba en
 * blanco a «calcula las propiedades de la aspirina».
 */
const FIN = /^<!--__FIN_DE_EVIDENCIA__-->$/;

/**
 * `[clase · fuente] herramienta (etiqueta): texto` — la fuente puede llevar paréntesis
 * y la etiqueta es opcional; puede llevarlos también (un SMILES sin nombre conocido).
 */
const CON_CLASE = /^\[([^·\]]+)·([^\]]+)\]\s*([A-Za-z_][\w]*)(?:\s*\((.*?)\))?:\s*([\s\S]*)$/;

/** `[sin clasificar — …] herramienta (etiqueta): texto` */
const SIN_CLASE = /^\[sin clasificar[^\]]*\]\s*([A-Za-z_][\w]*)(?:\s*\((.*?)\))?:\s*([\s\S]*)$/;

/**
 * Separa la prosa de la evidencia. Un turno puede traer varios bloques; cada uno abre
 * con la cabecera y cierra con `FIN`, y lo que hay fuera de ellos es prosa. Un bloque
 * sin cierre (el de un mensaje anterior al marcador, o uno que aún se está escribiendo)
 * llega hasta el final.
 *
 * Ninguna línea se descarta: dentro de un bloque, lo que no se reconoce como resultado
 * ni como continuación se muestra como evidencia sin clasificar.
 */
export function separarEvidencia(contenido: string): {
  prosa: string;
  evidencias: Evidencia[];
} {
  const prosa: string[] = [];
  const evidencias: Evidencia[] = [];
  let enBloque = false;
  let ultima: Evidencia | null = null;

  for (const cruda of contenido.split("\n")) {
    const linea = cruda.trim();

    if (CABECERA.test(linea)) {
      enBloque = true;
      ultima = null;
      continue;
    }
    if (FIN.test(linea)) {
      enBloque = false;
      ultima = null;
      continue;
    }
    if (!enBloque) {
      prosa.push(cruda);
      continue;
    }
    if (!linea) continue;

    const conClase = linea.match(CON_CLASE);
    if (conClase) {
      ultima = {
        clase: conClase[1].trim(),
        fuente: conClase[2].trim(),
        herramienta: conClase[3].trim(),
        etiqueta: conClase[4]?.trim() || undefined,
        texto: conClase[5].trim(),
        verificada: true,
      };
      evidencias.push(ultima);
      continue;
    }

    const sinClase = linea.match(SIN_CLASE);
    if (sinClase) {
      ultima = {
        clase: "sin clasificar",
        fuente: "",
        herramienta: sinClase[1].trim(),
        etiqueta: sinClase[2]?.trim() || undefined,
        texto: sinClase[3].trim(),
        verificada: false,
      };
      evidencias.push(ultima);
      continue;
    }

    // Continuación de la línea anterior (una herramienta puede devolver varias
    // líneas). No se descarta: descartarla perdería parte del dato.
    if (ultima) {
      ultima.texto = `${ultima.texto}\n${linea}`;
      continue;
    }

    // Una línea que no declara qué es: se enseña, como no verificada.
    ultima = { clase: "sin clasificar", fuente: "", herramienta: "", texto: linea, verificada: false };
    evidencias.push(ultima);
  }

  return { prosa: prosa.join("\n").trim(), evidencias };
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
  const { t } = useLanguage();
  if (evidencias.length === 0) return null;

  return (
    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
      <div
        style={{
          fontSize: "0.75rem",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          color: "var(--text-dim, #94A3B8)",
        }}
      >
        {t("ia_evidencia_usada")}
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
            background: "var(--bg-secondary)",
            fontSize: "0.8125rem",
          }}
        >
          <div style={{ color: "var(--text)", marginBottom: 2 }}>
            {e.verificada
              ? `${e.clase} · ${e.fuente}`
              : t("auto_280145ccad5c")}
          </div>
          {e.herramienta && (
            <div style={{ color: "var(--text-secondary)", marginBottom: 2 }}>
              {e.etiqueta ? `${e.herramienta} (${e.etiqueta})` : e.herramienta}
            </div>
          )}
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
