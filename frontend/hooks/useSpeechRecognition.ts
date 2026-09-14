"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { getAuthHeaders } from "../lib/api";
import { getApiUrl } from "../lib/config";

type SpeechState = "idle" | "listening" | "processing" | "error" | "unsupported";

type UseSpeechRecognitionOptions = {
  lang?: string;
  onResult?: (transcript: string) => void;
};

export function useSpeechRecognition(options: UseSpeechRecognitionOptions = {}) {
  const { lang = "es-ES", onResult } = options;
  const [state, setState] = useState<SpeechState>("idle");
  const [mode, setMode] = useState<"local" | "unsupported">("unsupported");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // ── Detect available mode on mount ────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function detect() {
      try {
        const res = await fetch(`${await getApiUrl()}/ai/speech-to-text/status`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        if (data.available && !cancelled) {
          setMode("local");
          return;
        }
      } catch {}

      if (!cancelled) {
        setMode("unsupported");
        setState("unsupported");
      }
    }

    detect();
    return () => { cancelled = true; };
  }, []);

  // ── Local mode (faster-whisper on backend) ────────────────────
  const startLocal = useCallback(async () => {
    if (state === "listening" || mode !== "local") return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstart = () => setState("listening");

      recorder.onstop = async () => {
        setState("processing");
        stream.getTracks().forEach((t) => t.stop());
        mediaRecorderRef.current = null;

        const blob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];

        try {
          const langCode = lang.startsWith("es") ? "es" : "en";
          const res = await fetch(
            `${await getApiUrl()}/ai/speech-to-text?lang=${langCode}`,
            { method: "POST", body: blob, headers: getAuthHeaders() }
          );
          if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
          }
          const data = await res.json();
          if (data.text) {
            onResult?.(data.text);
          }
        } catch {
          setState("error");
          return;
        }
        setState("idle");
      };

      recorder.onerror = () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("error");
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
    } catch {
      setState("error");
    }
  }, [lang, onResult, state, mode]);

  const stopLocal = useCallback(() => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      mediaRecorderRef.current.stop();
    }
  }, []);

  // ── Public API ────────────────────────────────────────────────
  const startListening = useCallback(() => {
    if (mode === "local") startLocal();
  }, [mode, startLocal]);

  const stopListening = useCallback(() => {
    if (mode === "local") stopLocal();
  }, [mode, stopLocal]);

  return {
    state,
    interimText: "",
    startListening,
    stopListening,
    isSupported: mode === "local",
    mode,
  };
}
