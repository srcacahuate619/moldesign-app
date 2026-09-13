"use client";

import React from "react";
import { Sparkles, Flag } from "lucide-react";

import { useAI } from "@/context/AIContext";
import { useLanguage } from "@/context/LanguageContext";
import { openExternal } from "@/lib/openExternal";
import { construirMailtoDeReporte } from "@/lib/reporteDeIA";

/**
 * La divulgación de IA generativa y su canal de reporte.
 *
 * Microsoft pide las dos cosas juntas para cualquier aplicación que entregue
 * texto escrito por un modelo: que el usuario sepa que lo es, y que pueda
 * reportar una respuesta dañina o inapropiada.
 *
 * NO SE PUEDE CERRAR, y esa es la diferencia con los otros avisos de este
 * panel. El del modelo local se oculta porque describe un estado que pasa; éste
 * describe lo que el panel es. Una divulgación que se esconde al segundo turno
 * deja de divulgar nada.
 *
 * La tercera frase del aviso es la que importa en este producto: MolChat habla
 * de moléculas y receptores a un centímetro de una pantalla que sí calcula, y
 * confundir las dos superficies es el error caro. Los números del expediente
 * salen de Vina y del rescoring; los de aquí, de un modelo de lenguaje.
 */
export function AvisoDeIAGenerativa() {
  const { t } = useLanguage();

  return (
    <div
      role="note"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 8,
        padding: "8px 16px",
        borderTop: "1px solid var(--border)",
        background: "var(--bg-secondary)",
        fontSize: "0.76em",
        lineHeight: 1.5,
        color: "var(--text-dim, var(--text-secondary))",
      }}
    >
      <Sparkles size={13} style={{ flexShrink: 0, marginTop: 3 }} aria-hidden="true" />
      <span>{t("ia_aviso_generativa")}</span>
    </div>
  );
}

/**
 * Reporta una respuesta concreta.
 *
 * Abre el programa de correo de la persona con todo escrito y no envía nada:
 * este producto acaba de cerrar tres caminos que salían a la red sin permiso, y
 * mandar la conversación por detrás para cumplir una obligación de
 * transparencia sería contradecir el aviso que está justo encima.
 */
export function BotonDeReporte({ respuesta }: { respuesta: string }) {
  const { t } = useLanguage();
  const { state } = useAI();
  const [fallo, setFallo] = React.useState(false);

  const proveedor =
    state.providers.find((p) => p.id === state.activeProviderId)?.name ||
    state.activeProviderId;

  async function reportar() {
    setFallo(false);
    try {
      await openExternal(
        construirMailtoDeReporte(
          { respuesta, proveedor },
          {
            asunto: t("ia_reportar_asunto"),
            cabecera: t("ia_reportar_cuerpo_cabecera"),
            etiquetaRespuesta: t("ia_reportar_cuerpo_respuesta"),
            etiquetaProveedor: t("ia_reportar_cuerpo_proveedor"),
          },
        ),
      );
    } catch {
      // Un canal de reporte que falla en silencio no es un canal de reporte.
      setFallo(true);
    }
  }

  return (
    <div style={{ marginTop: 8 }}>
      <button
        type="button"
        onClick={reportar}
        title={`${t("ia_reportar_titulo")}. ${t("ia_reportar_aviso")}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 8px",
          background: "transparent",
          color: "var(--text-dim, var(--text-secondary))",
          border: "1px solid var(--border)",
          borderRadius: 6,
          fontSize: "0.78em",
          cursor: "pointer",
        }}
      >
        <Flag size={11} aria-hidden="true" />
        {t("ia_reportar")}
      </button>
      {fallo && (
        <p style={{ margin: "6px 0 0", fontSize: "0.78em", color: "#EAB308" }}>
          {t("ia_reportar_sin_correo")}
        </p>
      )}
    </div>
  );
}
