"use client";

// =====================================================================
// LUNA-05 — la tarjeta con la que el investigador APRUEBA un docking
// =====================================================================
//
// MolChat no lanza evaluaciones: las PROPONE. El texto de la propuesta (receptor,
// cadena, motor, protocolo efectivo, caja, coste aproximado, advertencias) llega
// como prosa en el mensaje; esta tarjeta es lo único que puede convertirla en una
// corrida, y lo hace por una llamada AUTENTICADA y distinta del chat:
//
//   · aprobar → POST /ai/proposals/{id}/approve con la sesión de la cuenta. El
//     cuerpo lleva sólo la huella que se vio; la petición que se ejecuta sale del
//     servidor, nunca de aquí.
//   · NO envía «sí» por el chat. Un mensaje de texto no es una aprobación, y el
//     permiso web de más arriba —que sí lo hace— es de otra naturaleza: dejar salir
//     un SMILES no encola una corrida de Vina.
//
// Y dice la verdad cuando la propuesta ya no existe (se aprobó, se rechazó o
// caducó): en un historial recargado las tarjetas viejas siguen ahí, y un botón que
// parece vivo sobre algo muerto es una promesa falsa.

import React, { useEffect, useState } from "react";
import { Rocket, X } from "lucide-react";

import { useLanguage } from "@/context/LanguageContext";
import {
  ApiError,
  aprobarPropuestaDeDocking,
  consultarPropuestaDeDocking,
  mensajeDelError,
  rechazarPropuestaDeDocking,
} from "@/lib/api";

/**
 * El marcador que el backend añade al final de una propuesta. Va en un comentario
 * HTML: sin esta tarjeta (otro cliente, el historial en bruto) el texto sigue
 * leyéndose entero.
 */
export const MARCADOR_DE_PROPUESTA =
  /<!--__DOCKING_PROPOSAL__\s+id=(\w+)\s+hash=(sha256:[0-9a-f]{64})-->/;

type Fase =
  | { tipo: "pendiente" }
  | { tipo: "enviando" }
  | { tipo: "lanzada"; taskId: string }
  | { tipo: "cancelada" }
  | { tipo: "ya_no_pendiente" }
  | { tipo: "error"; motivo: string };

/** 404 y 410: la propuesta no existe o ya no es de esta sesión; para la tarjeta es lo mismo. */
function esPropuestaAusente(causa: unknown): boolean {
  return causa instanceof ApiError && (causa.status === 404 || causa.status === 410);
}

type Props = {
  id: string;
  hash: string;
};

export function PropuestaDeDocking({ id, hash }: Props) {
  const { t } = useLanguage();
  const [fase, setFase] = useState<Fase>({ tipo: "pendiente" });

  // Al montar se pregunta si sigue pendiente. Si la consulta falla por otra razón
  // (sin red, sin sesión) se deja la tarjeta como está: quien decide es el servidor
  // en el momento de aprobar, que repite todas las comprobaciones.
  useEffect(() => {
    let vivo = true;
    consultarPropuestaDeDocking(id).catch((causa: unknown) => {
      if (vivo && esPropuestaAusente(causa)) setFase({ tipo: "ya_no_pendiente" });
    });
    return () => {
      vivo = false;
    };
  }, [id]);

  async function aprobar() {
    setFase({ tipo: "enviando" });
    try {
      const lanzada = await aprobarPropuestaDeDocking(id, hash);
      setFase({ tipo: "lanzada", taskId: lanzada.task_id });
    } catch (causa) {
      setFase(
        esPropuestaAusente(causa)
          ? { tipo: "ya_no_pendiente" }
          : { tipo: "error", motivo: mensajeDelError(causa) },
      );
    }
  }

  async function cancelar() {
    setFase({ tipo: "enviando" });
    try {
      await rechazarPropuestaDeDocking(id);
      setFase({ tipo: "cancelada" });
    } catch (causa) {
      setFase(
        esPropuestaAusente(causa)
          ? { tipo: "ya_no_pendiente" }
          : { tipo: "error", motivo: mensajeDelError(causa) },
      );
    }
  }

  const abierta = fase.tipo === "pendiente" || fase.tipo === "enviando" || fase.tipo === "error";

  return (
    <div
      role="group"
      aria-label={t("ia_propuesta_grupo")}
      style={{
        marginTop: 12,
        padding: 12,
        border: "1px solid var(--border)",
        borderRadius: 10,
        background: "rgba(255,255,255,0.03)",
      }}
    >
      {abierta && (
        <>
          <p style={{ margin: "0 0 10px", fontSize: "0.82em", color: "var(--text-secondary)" }}>
            {t("ia_propuesta_nota")}
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={aprobar}
              disabled={fase.tipo === "enviando"}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                minHeight: 44,
                padding: "8px 16px",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                fontSize: "0.85em",
                fontWeight: 600,
                cursor: fase.tipo === "enviando" ? "progress" : "pointer",
                opacity: fase.tipo === "enviando" ? 0.7 : 1,
              }}
            >
              <Rocket size={14} aria-hidden="true" />
              {fase.tipo === "enviando" ? t("ia_propuesta_aprobando") : t("ia_propuesta_aprobar")}
            </button>
            <button
              type="button"
              onClick={cancelar}
              disabled={fase.tipo === "enviando"}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                minHeight: 44,
                padding: "8px 16px",
                background: "rgba(255,255,255,0.05)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: "0.85em",
                cursor: "pointer",
              }}
            >
              <X size={14} aria-hidden="true" />
              {t("ia_propuesta_cancelar")}
            </button>
          </div>
        </>
      )}

      <div aria-live="polite">
        {fase.tipo === "lanzada" && (
          <p style={{ margin: 0, fontSize: "0.88em" }}>
            {t("ia_propuesta_lanzada")} <code>task_id={fase.taskId}</code>
          </p>
        )}
        {fase.tipo === "cancelada" && (
          <p style={{ margin: 0, fontSize: "0.88em" }}>{t("ia_propuesta_cancelada")}</p>
        )}
        {fase.tipo === "ya_no_pendiente" && (
          <p style={{ margin: 0, fontSize: "0.88em" }}>{t("ia_propuesta_ya_no_pendiente")}</p>
        )}
        {fase.tipo === "error" && (
          <p role="alert" style={{ margin: "8px 0 0", fontSize: "0.85em", color: "var(--danger, #ef4444)" }}>
            {t("ia_propuesta_error")}: {fase.motivo}
          </p>
        )}
      </div>
    </div>
  );
}
