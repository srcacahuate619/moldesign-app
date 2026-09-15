"use client";


import { useLanguage } from "@/context/LanguageContext";
import React from "react";
import { motion } from "framer-motion";
import { User, Bot, Globe, X } from "lucide-react";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { BloqueDeEvidencia, separarEvidencia } from "./BloqueDeEvidencia";
import { BotonDeReporte } from "./AvisoDeIAGenerativa";
import { useAI } from "@/context/AIContext";
import type { AIMessage } from "@/context/AIContext";

type Props = {
  message: AIMessage;
  isStreaming?: boolean;
};

const PENDING_MARKER_RE = /<!--__PENDING_WEB_ASK__\s+smiles=(\S+?)-->/;

export function ChatMessage({ message, isStreaming }: Props) {
  const { t } = useLanguage();
  const { sendMessage } = useAI();
  const isUser = message.role === "user";

  // Detectar si este mensaje de assistant tiene un marcador de permiso web.
  // Extraerlo ANTES de renderizar para que el user no lo vea.
  const markerMatch = !isUser ? message.content.match(PENDING_MARKER_RE) : null;
  const sinMarcador = markerMatch
    ? message.content.replace(PENDING_MARKER_RE, "").trim()
    : message.content;

  // MOLCHAT-AUD-01 (FE/UX): la evidencia sale de la prosa. El bloque de
  // resultados de herramientas llega etiquetado con la clase y la fuente de
  // cada dato, y mezclarlo con el texto redactado borra justo esa distincion.
  const { prosa, evidencias } = isUser
    ? { prosa: sinMarcador, evidencias: [] }
    : separarEvidencia(sinMarcador);
  const displayContent = prosa;

  function handleAccept() {
    sendMessage("sí");
  }

  function handleDecline() {
    sendMessage("no");
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{
        display: "flex",
        gap: 12,
        padding: "12px 16px",
        alignItems: "flex-start",
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          background: isUser ? "var(--accent)" : "rgba(255,255,255,0.1)",
        }}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: "0.85em",
            color: "var(--text-secondary)",
            marginBottom: 4,
          }}
        >
          {isUser ? t("auto_e0b8ada702a2") : "MolChat"}
        </div>
        <div
          style={{
            fontSize: "0.92em",
            lineHeight: 1.6,
            color: "var(--text)",
          }}
        >
          <MarkdownRenderer content={displayContent} />
          {!isUser && <BloqueDeEvidencia evidencias={evidencias} />}
          {/* El canal de reporte va por respuesta y no sólo en el panel: lo que
              se reporta es una respuesta concreta, y pedirle a alguien que la
              copie a mano es un canal que nadie usa. Mientras se escribe no
              aparece: todavía no hay respuesta que reportar. */}
          {!isUser && !isStreaming && displayContent.trim() !== "" && (
            <BotonDeReporte respuesta={displayContent} />
          )}
          {isStreaming && (
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 16,
                background: "var(--accent)",
                marginLeft: 2,
                animation: "blink 0.8s step-end infinite",
              }}
            />
          )}

          {/* Botones clickeables de permiso web — solo en mensajes con marcador */}
          {markerMatch && (
            <div
              style={{
                display: "flex",
                gap: 8,
                marginTop: 12,
                flexWrap: "wrap",
              }}
            >
              <button
                onClick={handleAccept}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 16px",
                  background: "var(--accent)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 8,
                  fontSize: "0.85em",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background =
                    "var(--accent-hover, #3B82F6)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background =
                    "var(--accent)";
                }}
              >
                <Globe size={14} />
                {t("ia_si_consultar")}
              </button>
              <button
                onClick={handleDecline}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 16px",
                  background: "rgba(255,255,255,0.05)",
                  color: "var(--text-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  fontSize: "0.85em",
                  cursor: "pointer",
                }}
              >
                <X size={14} />
                {t("ia_no_gracias")}
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
