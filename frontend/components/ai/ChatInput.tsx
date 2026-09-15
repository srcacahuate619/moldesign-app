"use client";


import { useLanguage } from "@/context/LanguageContext";
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
  const { t } = useLanguage();
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
  const canSend = Boolean(input.trim()) && !disabled;

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
            fontSize: "0.8125rem",
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
            {t("auto_98a41efc81b2")}
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
        {/* Language toggle only configures the local transcription engine. */}
        {isSupported && (
          <button
            type="button"
            onClick={() => setLang(lang === "es-ES" ? "en-US" : "es-ES")}
            title={lang === "es-ES" ? t("auto_2001ca082b2d") : t("auto_2001ca082b2d")}
            aria-label={lang === "es-ES" ? t("auto_eeb11cc0b66e") : t("auto_dda6b46d3faf")}
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
              fontSize: "0.75rem",
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            {lang === "es-ES" ? t("auto_9debabbaa01a") : t("auto_9debabbaa01a")}
          </button>
        )}

        <textarea
          ref={textareaRef}
          value={displayText}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isListening
              ? "Escuchando..."
              : isStreaming
              ? t("auto_6be8b77110ff")
              : "Pregunta a MolChat..."
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
        <button
            type="button"
            onClick={() => {
              if (isListening) {
                stopListening();
              } else {
                startListening();
              }
            }}
            disabled={isStreaming || !isSupported}
            title={
              isSupported
                ? isListening
                  ? t("auto_b6ade7ce617a")
                  : t("auto_1416d9865ffd")
                : t("auto_e53d65c119b2")
            }
            aria-label={
              isSupported
                ? isListening
                  ? t("auto_b6ade7ce617a")
                  : t("auto_1416d9865ffd")
                : "Dictado no disponible"
            }
            aria-describedby={!isSupported ? "dictado-no-disponible" : undefined}
            style={{
              background: isListening
                ? "#EF4444"
                : "var(--bg)",
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
              cursor: isStreaming || !isSupported ? "not-allowed" : "pointer",
              flexShrink: 0,
              opacity: isStreaming || !isSupported ? 0.45 : 1,
              animation: isListening
                ? "pulse-mic 1.5s ease-in-out infinite"
                : "none",
            }}
          >
            {isListening ? <MicOff size={16} /> : <Mic size={16} />}
          </button>

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
            type="button"
            onClick={() => void handleSubmit()}
            disabled={!canSend}
            title="Enviar"
            aria-label="Enviar mensaje"
            style={{
              background: canSend
                ? "var(--accent)"
                : "var(--bg)",
              color: canSend ? "#fff" : "var(--text-secondary)",
              border: canSend ? "none" : "1px solid var(--border)",
              borderRadius: 10,
              width: 40,
              height: 40,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: canSend ? "pointer" : "default",
              flexShrink: 0,
              opacity: canSend ? 1 : 0.7,
            }}
          >
            <Send size={16} aria-hidden="true" />
          </button>
        )}
      </div>

      <div
        style={{
          fontSize: "0.75rem",
          color: "var(--text-secondary)",
          marginTop: 6,
          textAlign: "center",
          display: "flex",
          justifyContent: "center",
          gap: 12,
        }}
      >
        <span>{t("auto_8ddc10621717")}</span>
        <span>{t("ia_shift_enter")}</span>
        {isSupported ? (
          <span>{t("ia_microfono")}</span>
        ) : (
          <span id="dictado-no-disponible" role="status">
            {t("ia_dictado_no_disponible")}
          </span>
        )}
        {micState === "error" && (
          <span role="alert">{t("ia_dictado_fallo")}</span>
        )}
      </div>
    </div>
  );
}
