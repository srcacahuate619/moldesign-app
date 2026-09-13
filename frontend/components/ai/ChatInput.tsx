"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, Square, Mic, MicOff } from "lucide-react";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

/** Lo que un turno devuelve al que lo escribió. */
export type ResultadoDeEnvio = { ok: boolean; motivo?: string };

type Props = {
  /**
   * MOLCHAT-AUD-01 (FE/UX): devuelve el desenlace del turno. Antes esto no
   * devolvia nada y el borrador se borraba al pulsar Enter, pasara lo que
   * pasara despues; un 403 sin consentimiento o un 503 del historial local se
   * llevaban por delante lo que el investigador habia escrito.
   */
  onSend: (message: string) => void | Promise<ResultadoDeEnvio | void>;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
};

export function ChatInput({ onSend, onStop, isStreaming, disabled }: Props) {
  const [input, setInput] = useState("");
  const [lang, setLang] = useState("es-ES");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleResult = useCallback(
    (transcript: string) => {
      setInput((prev) => {
        const newVal = prev ? `${prev} ${transcript}` : transcript;
        return newVal;
      });
    },
    []
  );

  const {
    state: micState,
    interimText,
    startListening,
    stopListening,
    isSupported,
    mode: voiceMode,
  } = useSpeechRecognition({
    lang,
    onResult: handleResult,
  });

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [input, interimText]);

  async function handleSubmit() {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || disabled) return;
    // El borrador se limpia de forma optimista para que la caja no se sienta
    // trabada, y vuelve intacto si el turno no llego a salir.
    setInput("");
    const resultado = await onSend(trimmed);
    if (resultado && resultado.ok === false) {
      setInput(trimmed);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  }

  const isListening = micState === "listening";
  const displayText = isListening && interimText ? `${input} ${interimText}` : input;

  return (
    <div
      style={{
        padding: "12px 16px",
        borderTop: "1px solid var(--border)",
        background: "var(--bg-secondary)",
      }}
    >
      {/* Voice indicator */}
      {isListening && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 0 8px",
            fontSize: "0.78em",
            color: "#EF4444",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#EF4444",
              animation: "blink 0.8s step-end infinite",
            }}
          />
          Escuchando...{" "}
          <span style={{ color: "var(--text-dim)" }}>
            (hablá claramente)
          </span>
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "flex-end",
        }}
      >
        {/* Language toggle */}
        <button
          onClick={() => setLang(lang === "es-ES" ? "en-US" : "es-ES")}
          title={lang === "es-ES" ? "Español" : "English"}
          style={{
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            width: 40,
            height: 40,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            color: "var(--text-secondary)",
            fontSize: "0.7em",
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {lang === "es-ES" ? "ES" : "EN"}
        </button>

        <textarea
          ref={textareaRef}
          value={displayText}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isListening
              ? "Escuchando..."
              : isStreaming
              ? "MolChat está respondiendo..."
              : "Preguntale a MolChat..."
          }
          rows={1}
          disabled={disabled || isListening}
          style={{
            flex: 1,
            background: isListening
              ? "rgba(239, 68, 68, 0.06)"
              : "var(--bg)",
            border: isListening
              ? "1px solid rgba(239, 68, 68, 0.3)"
              : "1px solid var(--border)",
            borderRadius: 10,
            padding: "10px 14px",
            color: isListening ? "#EF4444" : "var(--text)",
            fontSize: "0.92em",
            resize: "none",
            outline: "none",
            maxHeight: 120,
            lineHeight: 1.5,
            fontStyle: isListening && interimText ? "italic" : "normal",
          }}
        />

        {/* Mic button */}
        {isSupported && (
          <button
            onClick={() => {
              if (isListening) {
                stopListening();
              } else {
                startListening();
              }
            }}
            disabled={isStreaming}
            title={isListening ? "Detener grabación" : "Dictar por voz"}
            style={{
              background: isListening
                ? "#EF4444"
                : "rgba(255,255,255,0.08)",
              color: isListening ? "#fff" : "var(--text-secondary)",
              border: isListening
                ? "2px solid #EF4444"
                : "1px solid var(--border)",
              borderRadius: 10,
              width: 40,
              height: 40,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: isStreaming ? "default" : "pointer",
              flexShrink: 0,
              opacity: isStreaming ? 0.4 : 1,
              animation: isListening
                ? "pulse-mic 1.5s ease-in-out infinite"
                : "none",
            }}
          >
            {isListening ? <MicOff size={16} /> : <Mic size={16} />}
          </button>
        )}

        {isStreaming ? (
          <button
            onClick={onStop}
            title="Detener"
            style={{
              background: "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 10,
              width: 40,
              height: 40,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={() => void handleSubmit()}
            disabled={!input.trim() || disabled}
            title="Enviar"
            style={{
              background: input.trim()
                ? "var(--accent)"
                : "rgba(255,255,255,0.1)",
              color: "#fff",
              border: "none",
              borderRadius: 10,
              width: 40,
              height: 40,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: input.trim() ? "pointer" : "default",
              flexShrink: 0,
              opacity: input.trim() ? 1 : 0.4,
            }}
          >
            <Send size={16} />
          </button>
        )}
      </div>

      <div
        style={{
          fontSize: "0.75em",
          color: "var(--text-secondary)",
          marginTop: 6,
          textAlign: "center",
          display: "flex",
          justifyContent: "center",
          gap: 12,
        }}
      >
        <span>Enter · enviar</span>
        <span>Shift+Enter · nueva línea</span>
        {isSupported && (
          <span>
            🎤 · dictar
            {voiceMode === "local" ? " (local)" : voiceMode === "webapi" ? " (web)" : ""}
          </span>
        )}
      </div>
    </div>
  );
}
