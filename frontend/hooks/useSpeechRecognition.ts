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
  const [interimText, setInterimText] = useState("");
  const [mode, setMode] = useState<"local" | "webapi" | "unsupported">("unsupported");
  const recognitionRef = useRef<InstanciaSpeechRecognition | null>(null);
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
        if (res.ok) {
          const data = await res.json();
          if (data.available && !cancelled) {
            setMode("local");
            return;
          }
        }
      } catch {}

      const speechAPI =
        window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!cancelled) {
        setMode(speechAPI ? "webapi" : "unsupported");
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
          const formData = new FormData();
          formData.append("audio", blob, "recording.webm");

          const res = await fetch(
            `${await getApiUrl()}/ai/speech-to-text?lang=${langCode}`,
            { method: "POST", body: blob, headers: getAuthHeaders() }
          );
          if (res.ok) {
            const data = await res.json();
            if (data.text) {
              onResult?.(data.text);
            }
          }
        } catch {
          setState("idle");
          return;
        }
        setState("idle");
      };

      recorder.onerror = () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("idle");
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
    } catch {
      setState("unsupported");
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

  // ── Web Speech API mode (fallback) ────────────────────────────
  const startWebAPI = useCallback(() => {
    if (state === "listening" || mode !== "webapi") return;

    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setMode("unsupported");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setState("listening");
      setInterimText("");
    };

    recognition.onresult = (event: EventoDeReconocimientoDeVoz) => {
      let interim = "";
      let final = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) final += result[0].transcript;
        else interim += result[0].transcript;
      }

      if (interim) setInterimText(interim);
      if (final) {
        setState("processing");
        setInterimText("");
        onResult?.(final.trim());
        setTimeout(() => setState("idle"), 300);
      }
    };

    recognition.onerror = () => setState("idle");
    recognition.onend = () => {
      setState("idle");
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [lang, onResult, state, mode]);

  const stopWebAPI = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.abort();
      recognitionRef.current = null;
    }
    setState("idle");
    setInterimText("");
  }, []);

  // ── Public API ────────────────────────────────────────────────
  const startListening = useCallback(() => {
    if (mode === "local") startLocal();
    else if (mode === "webapi") startWebAPI();
  }, [mode, startLocal, startWebAPI]);

  const stopListening = useCallback(() => {
    if (mode === "local") stopLocal();
    else if (mode === "webapi") stopWebAPI();
  }, [mode, stopLocal, stopWebAPI]);

  return {
    state,
    interimText,
    startListening,
    stopListening,
    isSupported: mode !== "unsupported",
    mode,
  };
}
