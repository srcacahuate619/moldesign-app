"use client";

import React, { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  X,
  Settings,
  Plus,
  MessageSquare,
  Trash2,
  ChevronLeft,
  AlertTriangle,
  Info,
  Cpu,
  PieChart,
  Coins,
  Globe,
  ShieldAlert,
} from "lucide-react";
import { useAI } from "@/context/AIContext";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { ProviderBadge } from "./ProviderBadge";
import { AISettingsModal } from "./AISettingsModal";
import { AvisoDeIAGenerativa } from "./AvisoDeIAGenerativa";
import { useDownload } from "@/hooks/useDownload";

export function ChatPanel() {
  const {
    state,
    dispatch,
    detectStartup,
    pollResources,
    sendMessage,
    retryLastTurn,
    stopStreaming,
    newConversation,
    fetchConversations,
    loadConversation,
    otorgarConsentimiento,
  } = useAI();
  const { models, startDownload } = useDownload();
  const llmMissing = models["llm-qwen15"] === "missing" || models["llm-qwen15"] === "error";
  // El aviso se puede cerrar. Antes no: si el estado del modelo se quedaba
  // desfasado, la banda se quedaba fija encima de la conversacion para siempre.
  const [avisoLlmCerrado, setAvisoLlmCerrado] = React.useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showSidebar, setShowSidebar] = React.useState(false);
  const startupDetected = useRef(false);

  useEffect(() => {
    if (!startupDetected.current) {
      startupDetected.current = true;
      detectStartup();
    }
  }, [detectStartup]);

  useEffect(() => {
    if (state.isPanelOpen) {
      fetchConversations();
    }
  }, [state.isPanelOpen, fetchConversations]);

  useEffect(() => {
    if (!state.isPanelOpen) return;
    pollResources();
    const interval = setInterval(pollResources, 8000);
    return () => clearInterval(interval);
  }, [state.isPanelOpen, pollResources]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages, state.streamingContent]);

  function handleStop() {
    stopStreaming();
  }

  function handleTogglePanel() {
    dispatch({ type: "SET_PANEL_OPEN", open: !state.isPanelOpen });
  }

  const activeProvider = state.providers.find(
    (p) => p.id === state.activeProviderId
  );

  // MOLCHAT-NET-005: a dónde salen los datos con el proveedor activo. Lo calcula
  // el backend; la interfaz sólo lo declara.
  const destinoActivo =
    state.destinos.find((d) => d.provider_id === state.activeProviderId) || null;

  const allMessages = [
    ...state.messages,
    ...(state.isStreaming && state.streamingContent
      ? [
          {
            role: "assistant" as const,
            content: state.streamingContent,
            id: "streaming",
          },
        ]
      : []),
  ];

  // Mock Metrics Calculation
  const isLocal = activeProvider?.id === "local" || activeProvider?.id === "ollama";
  const maxTokens = isLocal ? 8192 : 128000;
  const estimatedTokens = Math.floor(allMessages.reduce((acc, m) => acc + (m.content?.length || 0) / 4, 0));
  const contextPercent = Math.min(100, (estimatedTokens / maxTokens) * 100).toFixed(1);
  const sessionCost = isLocal ? 0 : (estimatedTokens / 1000) * 0.0015; // $0.0015 per 1k tokens (mock)

  return (
    <>
      {/* Floating button */}
      <button
        onClick={handleTogglePanel}
        title="MolChat - Intérprete IA"
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          zIndex: 50,
          width: 52,
          height: 52,
          borderRadius: 16,
          background: "var(--accent)",
          color: "#fff",
          border: "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
        }}
      >
        <Bot size={24} />
      </button>

      {/* Side panel */}
      <AnimatePresence>
        {state.isPanelOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 55,
              pointerEvents: "none",
            }}
          >
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={handleTogglePanel}
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(0,0,0,0.4)",
                backdropFilter: "blur(2px)",
                pointerEvents: "auto",
              }}
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              style={{
                position: "absolute",
                right: 0,
                top: 76,
                bottom: 0,
                width: 420,
                maxWidth: "100vw",
                background: "var(--bg-secondary)",
                borderLeft: "1px solid var(--border)",
                display: "flex",
                flexDirection: "column",
                pointerEvents: "auto",
                boxShadow: "-8px 0 40px rgba(0,0,0,0.2)",
              }}
            >
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 16px",
                  borderBottom: "1px solid var(--border)",
                  flexShrink: 0,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button
                    onClick={() => setShowSidebar(!showSidebar)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                      padding: 4,
                    }}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <Bot size={18} color="var(--accent)" />
                  <span
                    style={{
                      fontWeight: 600,
                      fontSize: "0.95em",
                      color: "var(--text)",
                    }}
                  >
                    MolChat
                  </span>
                  {/* Speed vs Reasoning toggle */}
                  <div
                    style={{
                      display: "flex",
                      background: "var(--bg)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      overflow: "hidden",
                      marginLeft: 12,
                    }}
                  >
                    <button
                      onClick={() =>
                        dispatch({ type: "SET_CHAT_MODE", mode: "speed" })
                      }
                      style={{
                        padding: "3px 8px",
                        fontSize: "0.7em",
                        fontWeight: state.chatMode === "speed" ? 600 : 400,
                        background:
                          state.chatMode === "speed"
                            ? "var(--accent)"
                            : "transparent",
                        color:
                          state.chatMode === "speed"
                            ? "#fff"
                            : "var(--text-secondary)",
                        border: "none",
                        cursor: "pointer",
                      }}
                    >
                      Faster
                    </button>
                    <button
                      onClick={() =>
                        dispatch({
                          type: "SET_CHAT_MODE",
                          mode: "reasoning",
                        })
                      }
                      style={{
                        padding: "3px 8px",
                        fontSize: "0.7em",
                        fontWeight:
                          state.chatMode === "reasoning" ? 600 : 400,
                        background:
                          state.chatMode === "reasoning"
                            ? "var(--accent)"
                            : "transparent",
                        color:
                          state.chatMode === "reasoning"
                            ? "#fff"
                            : "var(--text-secondary)",
                        border: "none",
                        cursor: "pointer",
                      }}
                    >
                      Deep
                    </button>
                  </div>

                  {/* Modo web toggle (offline/online) */}
                  <button
                    onClick={() =>
                      dispatch({
                        type: "SET_ALLOW_WEB",
                        allowWeb: !state.allowWeb,
                      })
                    }
                    title={
                      state.allowWeb
                        ? "Modo web activo: enriquece con PubChem/ChEMBL (puede tardar 2-3s extra)"
                        : "Modo offline: activar modo web para enriquecer con PubChem/ChEMBL"
                    }
                    aria-label="Toggle modo web"
                    style={{
                      background: state.allowWeb
                        ? "rgba(59, 130, 246, 0.15)"
                        : "var(--bg)",
                      border: state.allowWeb
                        ? "1px solid rgba(59, 130, 246, 0.5)"
                        : "1px solid var(--border)",
                      borderRadius: 8,
                      padding: "3px 8px",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      cursor: "pointer",
                      marginLeft: 8,
                      color: state.allowWeb ? "#3B82F6" : "var(--text-dim)",
                      fontSize: "0.7em",
                      fontWeight: state.allowWeb ? 600 : 400,
                      transition: "all 0.15s",
                    }}
                  >
                    <Globe size={13} />
                    {state.allowWeb ? "Web" : "Offline"}
                  </button>
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    onClick={() =>
                      dispatch({ type: "SET_SETTINGS_OPEN", open: true })
                    }
                    title="Configuración"
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                      padding: 6,
                    }}
                  >
                    <Settings size={16} />
                  </button>
                  <button
                    onClick={handleTogglePanel}
                    title="Cerrar"
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                      padding: 6,
                    }}
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* Conversation history sidebar */}
              <AnimatePresence>
                {showSidebar && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    style={{
                      overflow: "hidden",
                      borderBottom: "1px solid var(--border)",
                      background: "var(--bg)",
                    }}
                  >
                    <div style={{ padding: "8px", maxHeight: 200, overflow: "auto" }}>
                      <div
                        style={{
                          fontSize: "0.75em",
                          color: "var(--text-secondary)",
                          padding: "4px 8px 8px",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                        }}
                      >
                        Historial
                      </div>
                      {state.conversations.length === 0 ? (
                        <div
                          style={{
                            padding: "12px 8px",
                            fontSize: "0.82em",
                            color: "var(--text-dim)",
                            textAlign: "center",
                          }}
                        >
                          Sin conversaciones
                        </div>
                      ) : (
                        state.conversations.map((conv) => (
                          <div
                            key={conv.id}
                            onClick={() => {
                              loadConversation(conv.id);
                              setShowSidebar(false);
                            }}
                            style={{
                              padding: "8px",
                              borderRadius: 6,
                              cursor: "pointer",
                              fontSize: "0.82em",
                              background:
                                conv.active ? "rgba(255,255,255,0.05)" : "transparent",
                              borderBottom: "1px solid var(--border)",
                              transition: "background 0.1s",
                            }}
                            onMouseEnter={(e) => {
                              if (!conv.active)
                                (e.currentTarget as HTMLDivElement).style.background =
                                  "rgba(255,255,255,0.03)";
                            }}
                            onMouseLeave={(e) => {
                              if (!conv.active)
                                (e.currentTarget as HTMLDivElement).style.background =
                                  "transparent";
                            }}
                          >
                            <div
                              style={{
                                color: conv.active ? "var(--accent)" : "var(--text)",
                                marginBottom: 2,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {conv.preview || "Nueva conversación"}
                            </div>
                            <div
                              style={{
                                fontSize: "0.82em",
                                color: "var(--text-dim)",
                                display: "flex",
                                gap: 8,
                              }}
                            >
                              <span>{conv.message_count} mensajes</span>
                              <span>
                                ·{" "}
                                {new Date(conv.updated_at * 1000).toLocaleDateString(undefined, {
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Provider badge */}
              <div
                style={{
                  padding: "8px 16px",
                  borderBottom: "1px solid var(--border)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <ProviderBadge
                  provider={activeProvider || null}
                  isStreaming={state.isStreaming}
                  resourceStatus={state.resourceStatus}
                  destino={destinoActivo}
                  onClick={() =>
                    dispatch({ type: "SET_SETTINGS_OPEN", open: true })
                  }
                />

                <div className="flex flex-col items-end gap-1" style={{ fontSize: "0.65rem", fontFamily: "var(--font-mono)" }}>
                  <div className="flex items-center gap-3 text-white/50">
                    <span title="Tokens estimados" className="flex items-center gap-1">
                      <Cpu size={10} /> {estimatedTokens.toLocaleString()} / {(maxTokens/1000).toFixed(0)}k tok
                    </span>
                    <span title="Porcentaje de contexto" className="flex items-center gap-1">
                      <PieChart size={10} /> {contextPercent}%
                    </span>
                  </div>
                  <div className={`font-bold tracking-wider flex items-center gap-1 ${isLocal ? "text-emerald-400" : "text-sky-400"}`}>
                    <Coins size={10} /> ${sessionCost.toFixed(4)} USD
                  </div>
                </div>

                <button
                  onClick={newConversation}
                  title="Nueva conversación"
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: "0.82em",
                    padding: "4px 8px",
                    borderRadius: 6,
                  }}
                >
                  <Plus size={14} />
                  Nuevo chat
                </button>
              </div>

              {/* MOLCHAT-NET-005: el destino sin autorizar se declara antes de
                  escribir, no después de que el turno no salga. */}
              {destinoActivo?.es_remoto && !destinoActivo.consentido && (
                <div
                  data-testid="barra-consentimiento"
                  style={{
                    padding: "8px 16px",
                    background: "rgba(239, 68, 68, 0.1)",
                    borderBottom: "1px solid rgba(239, 68, 68, 0.3)",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    fontSize: "0.82em",
                    color: "#EF4444",
                  }}
                >
                  <ShieldAlert size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                  <span>
                    Lo que escribas saldrá de tu máquina hacia{" "}
                    <strong>{destinoActivo.host}</strong>, con el contexto de caso y molécula.
                    Esta cuenta todavía no autorizó ese destino.
                  </span>
                  <button
                    onClick={() =>
                      otorgarConsentimiento(destinoActivo.provider_id, destinoActivo.host)
                    }
                    style={{
                      background: "none",
                      border: "1px solid rgba(239, 68, 68, 0.5)",
                      borderRadius: 4,
                      color: "#EF4444",
                      cursor: "pointer",
                      marginLeft: "auto",
                      flexShrink: 0,
                      padding: "2px 8px",
                    }}
                  >
                    Autorizar
                  </button>
                </div>
              )}

              {/* Turno fallido: el motivo, y el reintento idempotente.
                  MOLCHAT-AUD-01 (FE/UX): antes un turno que no salia no dejaba
                  rastro en pantalla — ni el motivo ni forma de repetirlo. */}
              {state.turnoFallido && (
                <div
                  data-testid="turno-fallido"
                  style={{
                    padding: "8px 16px",
                    background: "rgba(239, 68, 68, 0.1)",
                    borderBottom: "1px solid rgba(239, 68, 68, 0.3)",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    fontSize: "0.82em",
                    color: "#F87171",
                  }}
                >
                  <ShieldAlert size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                  <span style={{ flex: 1 }}>
                    No pude responder: {state.turnoFallido.motivo}
                  </span>
                  <button
                    onClick={() => void retryLastTurn()}
                    disabled={state.isStreaming}
                    style={{
                      background: "rgba(239, 68, 68, 0.15)",
                      border: "1px solid rgba(239, 68, 68, 0.4)",
                      borderRadius: 6,
                      color: "#F87171",
                      cursor: state.isStreaming ? "default" : "pointer",
                      padding: "2px 10px",
                      flexShrink: 0,
                    }}
                  >
                    Reintentar
                  </button>
                  <button
                    onClick={() =>
                      dispatch({ type: "SET_TURNO_FALLIDO", fallido: null })
                    }
                    style={{
                      background: "none",
                      border: "none",
                      color: "#F87171",
                      cursor: "pointer",
                      flexShrink: 0,
                      padding: 2,
                    }}
                  >
                    <X size={12} />
                  </button>
                </div>
              )}

              {/* Warning banner */}
              {state.warningBanner && (
                <div
                  style={{
                    padding: "8px 16px",
                    background: "rgba(234, 179, 8, 0.1)",
                    borderBottom: "1px solid rgba(234, 179, 8, 0.3)",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    fontSize: "0.82em",
                    color: "#EAB308",
                  }}
                >
                  <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                  <span>{state.warningBanner}</span>
                  <button
                    onClick={() =>
                      dispatch({ type: "SET_WARNING_BANNER", warning: null })
                    }
                    style={{
                      background: "none",
                      border: "none",
                      color: "#EAB308",
                      cursor: "pointer",
                      marginLeft: "auto",
                      flexShrink: 0,
                      padding: 2,
                    }}
                  >
                    <X size={12} />
                  </button>
                </div>
              )}

              {/* Download model banner */}
              {/* El aviso solo aparece si ese modelo es el que hace falta.
                  `llm-qwen15` es el checkpoint del interprete LOCAL: con un
                  proveedor online activo, MolChat responde perfectamente y
                  anunciar «modelo no descargado» es ruido que ademas no se
                  podia quitar. Se conserva el aviso donde SI bloquea. */}
              {llmMissing && activeProvider?.id === "local" && !avisoLlmCerrado && (
                <div
                  style={{
                    padding: "10px 16px",
                    background: "rgba(255, 107, 53, 0.1)",
                    borderBottom: "1px solid rgba(255, 107, 53, 0.3)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    fontSize: "0.82em",
                    color: "#FF6B35",
                  }}
                >
                  <span>Modelo LLM no descargado</span>
                  <button
                    onClick={() => startDownload("llm-qwen15")}
                    style={{
                      background: "#FF6B35",
                      color: "#fff",
                      border: "none",
                      borderRadius: 4,
                      padding: "4px 12px",
                      fontSize: "0.82em",
                      fontWeight: 600,
                      cursor: "pointer",
                      flexShrink: 0,
                    }}
                  >
                    Descargar
                  </button>
                  <button
                    onClick={() => setAvisoLlmCerrado(true)}
                    title="Ocultar este aviso"
                    style={{
                      background: "transparent",
                      color: "#FF6B35",
                      border: "none",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      flexShrink: 0,
                    }}
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

              {/* Startup message — welcome + reason */}
              {allMessages.length === 0 && state.startupMessage && state.startupMode !== "manual_only" && (
                <div
                  style={{
                    padding: "8px 16px",
                    background: "rgba(59, 130, 246, 0.08)",
                    borderBottom: "1px solid rgba(59, 130, 246, 0.2)",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    fontSize: "0.82em",
                    color: "var(--text-secondary)",
                    lineHeight: 1.5,
                  }}
                >
                  <Info size={14} style={{ flexShrink: 0, marginTop: 3, color: "#3B82F6" }} />
                  <span>{state.startupMessage}</span>
                </div>
              )}

              {/* Messages */}
              <div
                style={{
                  flex: 1,
                  overflow: "auto",
                  padding: "8px 0",
                }}
              >
                {allMessages.length === 0 ? (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      height: "100%",
                      padding: 32,
                      textAlign: "center",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Bot size={40} style={{ marginBottom: 16, opacity: 0.3 }} />
                    <p style={{ margin: 0, fontSize: "0.95em" }}>
                      Pregúntame sobre la molécula actual
                    </p>
                    <p style={{ margin: "8px 0 0", fontSize: "0.82em" }}>
                      o analiza evaluaciones anteriores
                    </p>
                  </div>
                ) : (
                  allMessages.map((msg) => (
                    <ChatMessage
                      key={msg.id}
                      message={msg}
                      isStreaming={msg.id === "streaming"}
                    />
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Divulgación de IA generativa. Va aquí, pegada al campo de
                  escritura, y no arriba con los avisos que se cierran: describe
                  lo que este panel es, no un estado que pasa. */}
              <AvisoDeIAGenerativa />

              {/* Input */}
              <ChatInput
                onSend={sendMessage}
                onStop={handleStop}
                isStreaming={state.isStreaming}
                disabled={false}
              />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Settings modal */}
      <AISettingsModal />
    </>
  );
}
