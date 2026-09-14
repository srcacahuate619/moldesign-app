"use client";

import React, { createContext, useContext, useReducer, useCallback, useEffect, useRef } from "react";
import { getAuthHeaders } from "../lib/api";
import { getApiUrl } from "../lib/config";
import { useAuth } from "../lib/auth";
import { getUserItem, setUserItem } from "../lib/userStorage";
import { motivoDeRespuesta } from "./motivoDeTurno";

export type AIMessage = {
  role: "user" | "assistant";
  content: string;
  id: string;
};

export type AIProviderInfo = {
  id: string;
  name: string;
  description: string;
  requires_api_key: boolean;
  requires_base_url: boolean;
  default_base_url: string;
  default_model: string;
  available_models: string[];
  configured: boolean;
  active: boolean;
  env_key?: string;
};

export type AIProviderConfig = {
  provider_id: string;
  api_key: string;
  base_url: string;
  model: string;
  temperature: number;
  /**
   * Confirma explícitamente un cambio de destino de los datos.
   *
   * Sin esto el backend responde 409 si el `base_url` mueve el host
   * (MOLCHAT-BE-003). Está en el tipo para que no se cuele por un spread.
   */
  confirmar_destino?: boolean;
};

export type ConversationInfo = {
  id: string;
  preview: string;
  message_count: number;
  created_at: number;
  updated_at: number;
  active: boolean;
};

export type StartupMode = "loading" | "auto_start" | "notify_fallback" | "manual_only";

export type ResourceStatus = {
  pipeline_state: "idle" | "busy";
  llm_state: "unloaded" | "loading" | "loaded";
  ram_free_gb: number;
  ram_total_gb: number;
  idle_seconds: number;
  keep_loaded: boolean;
  using_gpu: boolean;
  gpu_name: string;
  gpu_vram_total_gb: number;
  vram_free_gb: number;
};

/**
 * A dónde salen los datos de un turno, y si esta cuenta lo autorizó.
 *
 * MOLCHAT-NET-005: el destino lo calcula el backend a partir del host resuelto
 * para la cuenta, no del nombre del proveedor. Un `ollama` apuntado al servidor
 * de otra persona sale de la máquina; un `openai` apuntado a `localhost`, no.
 * La interfaz no vuelve a decidir eso por su cuenta.
 */
export type DestinoInfo = {
  provider_id: string;
  name: string;
  host: string;
  url: string;
  es_remoto: boolean;
  huella: string;
  activo: boolean;
  consentido: boolean;
  otorgado_en: string | null;
};

/**
 * El turno que no llego a completarse, con lo justo para repetirlo.
 *
 * MOLCHAT-AUD-01 (FE/UX). `sendMessage` hacia `if (!res.ok) return;`: el
 * mensaje del investigador quedaba en la lista, no llegaba respuesta y nada
 * decia por que. Con las correcciones de esta pestana el backend ya contesta
 * motivos accionables —403 sin consentimiento del destino, 503 si el historial
 * local no acepta escribir— y ninguno llegaba a la pantalla.
 *
 * El reintento guarda el MISMO snapshot de mensajes, asi que repetir el turno
 * no duplica lo que el investigador escribio: es idempotente por construccion.
 */
export type TurnoFallido = {
  motivo: string;
  snapshot: { role: string; content: string }[];
};

/** Desenlace de un turno, para que quien lo escribio sepa si salio. */
export type ResultadoDeEnvio = { ok: boolean; motivo?: string };

export type CambioDeDestino = {
  mensaje: string;
  destino_actual: { host: string; es_remoto: boolean };
  destino_propuesto: { host: string; es_remoto: boolean };
};

type AIState = {
  providers: AIProviderInfo[];
  destinos: DestinoInfo[];
  activeProviderId: string;
  conversations: ConversationInfo[];
  activeConversationId: string | null;
  messages: AIMessage[];
  isStreaming: boolean;
  streamingContent: string;
  isPanelOpen: boolean;
  isSettingsOpen: boolean;
  providerConfigs: Record<string, AIProviderConfig>;
  startupMode: StartupMode;
  startupMessage: string;
  warningBanner: string | null;
  resourceStatus: ResourceStatus | null;
  moleculeContext: Record<string, unknown> | null;
  chatMode: "speed" | "reasoning";
  allowWeb: boolean;
  turnoFallido: TurnoFallido | null;
};

type AIAction =
  | { type: "SET_PROVIDERS"; providers: AIProviderInfo[] }
  | { type: "SET_DESTINOS"; destinos: DestinoInfo[] }
  | { type: "SET_ACTIVE_PROVIDER"; id: string }
  | { type: "SET_CONVERSATIONS"; conversations: ConversationInfo[] }
  | { type: "SET_ACTIVE_CONVERSATION"; id: string | null }
  | { type: "SET_MESSAGES"; messages: AIMessage[] }
  | { type: "ADD_MESSAGE"; message: AIMessage }
  | { type: "SET_STREAMING"; isStreaming: boolean }
  | { type: "SET_STREAMING_CONTENT"; content: string }
  | { type: "APPEND_STREAMING"; token: string }
  | { type: "SET_PANEL_OPEN"; open: boolean }
  | { type: "SET_SETTINGS_OPEN"; open: boolean }
  | { type: "SET_PROVIDER_CONFIG"; config: AIProviderConfig }
  | { type: "SET_STARTUP_MODE"; mode: StartupMode; message: string }
  | { type: "SET_WARNING_BANNER"; warning: string | null }
  | { type: "SET_RESOURCE_STATUS"; status: ResourceStatus | null }
  | { type: "SET_KEEP_LOADED"; keep: boolean }
  | { type: "SET_MOLECULE_CONTEXT"; context: Record<string, unknown> | null }
  | { type: "SET_CHAT_MODE"; mode: "speed" | "reasoning" }
  | { type: "SET_ALLOW_WEB"; allowWeb: boolean }
  | { type: "SET_TURNO_FALLIDO"; fallido: TurnoFallido | null }
  | { type: "RESET_SESSION" };

/**
 * Lo que se muestra ANTES de que el backend conteste, y si no contesta.
 *
 * `configured: false` a propósito. Antes decía `true`, y eso hacía que MolChat
 * declarara un proveedor local listo aunque el motor no hubiera respondido
 * nunca: la insignia decía «conectado» y el primer mensaje fallaba sin
 * explicación. Un proveedor sin comprobar se declara sin comprobar; en cuanto
 * `/ai/providers` contesta, este valor se sustituye por el real.
 */
export const FALLBACK_PROVIDER: AIProviderInfo = {
  id: "local",
  name: "Local (llama.cpp)",
  description: "Modelo local vía llama.cpp. Sin clave, 100 % privado. Estado sin comprobar.",
  requires_api_key: false,
  requires_base_url: false,
  default_base_url: "",
  default_model: "qwen2.5-1.5b-instruct",
  available_models: [],
  configured: false,
  active: false,
};

const initialState: AIState = {
  providers: [FALLBACK_PROVIDER],
  destinos: [],
  activeProviderId: "local",
  conversations: [],
  activeConversationId: null,
  messages: [],
  isStreaming: false,
  streamingContent: "",
  isPanelOpen: false,
  isSettingsOpen: false,
  providerConfigs: {},
  startupMode: "loading",
  startupMessage: "",
  warningBanner: null,
  resourceStatus: null,
  moleculeContext: null,
  chatMode: "speed",
  allowWeb: false,
  turnoFallido: null,
};

function aiReducer(state: AIState, action: AIAction): AIState {
  switch (action.type) {
    case "RESET_SESSION":
      return initialState;
    case "SET_PROVIDERS":
      return { ...state, providers: action.providers };
    case "SET_DESTINOS":
      return { ...state, destinos: action.destinos };
    case "SET_ACTIVE_PROVIDER":
      return { ...state, activeProviderId: action.id };
    case "SET_CONVERSATIONS":
      return { ...state, conversations: action.conversations };
    case "SET_ACTIVE_CONVERSATION":
      return { ...state, activeConversationId: action.id };
    case "SET_MESSAGES":
      return { ...state, messages: action.messages };
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };
    case "SET_STREAMING":
      return { ...state, isStreaming: action.isStreaming };
    case "SET_STREAMING_CONTENT":
      return { ...state, streamingContent: action.content };
    case "APPEND_STREAMING":
      return { ...state, streamingContent: state.streamingContent + action.token };
    case "SET_PANEL_OPEN":
      return { ...state, isPanelOpen: action.open };
    case "SET_SETTINGS_OPEN":
      return { ...state, isSettingsOpen: action.open };
    case "SET_PROVIDER_CONFIG":
      return {
        ...state,
        providerConfigs: { ...state.providerConfigs, [action.config.provider_id]: action.config },
      };
    case "SET_STARTUP_MODE":
      return { ...state, startupMode: action.mode, startupMessage: action.message };
    case "SET_TURNO_FALLIDO":
      return { ...state, turnoFallido: action.fallido };
    case "SET_WARNING_BANNER":
      return { ...state, warningBanner: action.warning };
    case "SET_RESOURCE_STATUS":
      return { ...state, resourceStatus: action.status };
    case "SET_KEEP_LOADED":
      return {
        ...state,
        resourceStatus: state.resourceStatus
          ? { ...state.resourceStatus, keep_loaded: action.keep }
          : null,
      };
    case "SET_MOLECULE_CONTEXT":
      return { ...state, moleculeContext: action.context };
    case "SET_CHAT_MODE":
      return { ...state, chatMode: action.mode };
    case "SET_ALLOW_WEB":
      return { ...state, allowWeb: action.allowWeb };
    default:
      return state;
  }
}

type AIContextType = {
  state: AIState;
  dispatch: React.Dispatch<AIAction>;
  loadProviders: () => Promise<void>;
  loadDestinos: () => Promise<void>;
  otorgarConsentimiento: (providerId: string, host: string) => Promise<boolean>;
  revocarConsentimiento: (providerId: string) => Promise<void>;
  detectStartup: () => Promise<void>;
  pollResources: () => Promise<void>;
  sendMessage: (content: string) => Promise<ResultadoDeEnvio>;
  retryLastTurn: () => Promise<ResultadoDeEnvio>;
  stopStreaming: () => void;
  setActiveProvider: (id: string) => Promise<void>;
  newConversation: () => Promise<void>;
  updateProviderConfig: (config: AIProviderConfig) => Promise<CambioDeDestino | null>;
  setKeepLoaded: (keep: boolean) => Promise<void>;
  fetchConversations: () => Promise<void>;
  loadConversation: (convId: string) => Promise<void>;
  setMoleculeContext: (ctx: Record<string, unknown> | null) => void;
};

const AIContext = createContext<AIContextType | null>(null);

function makeId() {
  return Math.random().toString(36).substring(2, 10);
}

export function AIProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [state, dispatch] = useReducer(aiReducer, initialState);
  const abortRef = useRef<AbortController | null>(null);
  const streamingRef = useRef("");

  const [loadedUserId, setLoadedUserId] = React.useState<string | null>(null);

  useEffect(() => {
    setLoadedUserId(null);
    dispatch({ type: "RESET_SESSION" });
    if (!user) return;
    const chatMode = getUserItem("moldesign_chat_mode", user.user_id);
    const allowWeb = getUserItem("moldesign_allow_web", user.user_id);
    if (chatMode === "speed" || chatMode === "reasoning") {
      dispatch({ type: "SET_CHAT_MODE", mode: chatMode });
    }
    dispatch({ type: "SET_ALLOW_WEB", allowWeb: allowWeb === "true" });
    setLoadedUserId(user.user_id);
  }, [user]);

  useEffect(() => {
    if (user && loadedUserId === user.user_id) {
      setUserItem("moldesign_chat_mode", state.chatMode, user.user_id);
    }
  }, [loadedUserId, state.chatMode, user]);

  useEffect(() => {
    if (user && loadedUserId === user.user_id) {
      setUserItem("moldesign_allow_web", String(state.allowWeb), user.user_id);
    }
  }, [loadedUserId, state.allowWeb, user]);

  const loadProviders = useCallback(async () => {
    const res = await fetch(`${await getApiUrl()}/ai/providers`, { headers: getAuthHeaders() });
    if (!res.ok) {
      throw new Error(`No se pudieron cargar los proveedores (HTTP ${res.status}).`);
    }
    const providers: AIProviderInfo[] = await res.json();
    if (providers.length > 0) {
      dispatch({ type: "SET_PROVIDERS", providers });
    }
    const active = providers.find((p) => p.active);
    if (active) {
      dispatch({ type: "SET_ACTIVE_PROVIDER", id: active.id });
    }
  }, []);

  useEffect(() => {
    void loadProviders().catch(() => {
      // El fallback permanece sin comprobar; la pantalla de ajustes muestra el
      // fallo cuando la persona la abre.
    });
  }, [loadProviders]);

  const detectStartup = useCallback(async () => {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/startup`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        dispatch({
          type: "SET_STARTUP_MODE",
          mode: data.mode,
          message: data.reason,
        });
        if (data.mode === "auto_start" || data.mode === "notify_fallback") {
          dispatch({ type: "SET_ACTIVE_PROVIDER", id: "local" });
          if (data.mode === "notify_fallback") {
            // FIX Bug A (BUILD_GUIDE.md seccion 4): antes del fix, este path
            // tambien abria el panel en "auto_start" y abria el panel en
            // cualquier error de red (catch). Eso hacia que MolChat apareciera
            // cuando el backend no estaba corriendo = distorsion cientifica.
            //
            // Ahora: panel SOLO se abre explicitamente en "notify_fallback"
            // (API keys sin saldo, fallback a local). El warning banner debe
            // ser visible para el usuario, y el banner solo se renderiza dentro
            // del panel cuando isPanelOpen=true (ver ChatPanel.tsx lineas 119
            // y 433). Sin esta dispatch, notify_fallback setea el banner PERO
            // el usuario nunca lo ve=bug silencioso.
            dispatch({ type: "SET_PANEL_OPEN", open: true });
            dispatch({
              type: "SET_WARNING_BANNER",
              warning: "Tus API keys no tienen saldo. MolChat usa el modo local.",
            });
          }
        }
      }
    } catch (err: any) {
      // FIX Bug A (BUILD_GUIDE.md seccion 4): el bloque catch NO debe abrir
      // el panel. Antes del fix, hacia dispatch({ type: "SET_PANEL_OPEN",
      // open: true }) y el panel se abria en cualquier error de red (backend
      // tarda ~5s en arrancar). Ahora solo actualiza el startupMode + mensaje
      // informativo dejando claro que no se pudo conectar.
      dispatch({
        type: "SET_STARTUP_MODE",
        mode: "auto_start",
        message: `No se pudo conectar con el backend (${err.message || "error de red"}). MolChat inicia igual.`,
      });
    }
  }, []);

  const setActiveProvider = useCallback(async (id: string) => {
    const res = await fetch(`${await getApiUrl()}/ai/providers/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ provider_id: id }),
    });
    if (!res.ok) {
      throw new Error(`No se pudo activar el proveedor (HTTP ${res.status}).`);
    }
    await loadProviders();
  }, [loadProviders]);

  const loadDestinos = useCallback(async () => {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/consent`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        dispatch({ type: "SET_DESTINOS", destinos: data.destinos || [] });
      }
    } catch {
      // Sin backend no se puede afirmar el destino; se deja vacío y la insignia
      // lo declara sin comprobar, en vez de decir «local» por optimismo.
    }
  }, []);

  const otorgarConsentimiento = useCallback(
    async (providerId: string, host: string) => {
      try {
        const res = await fetch(`${await getApiUrl()}/ai/consent`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAuthHeaders() },
          body: JSON.stringify({ provider_id: providerId, host }),
        });
        await loadDestinos();
        return res.ok;
      } catch {
        return false;
      }
    },
    [loadDestinos],
  );

  const revocarConsentimiento = useCallback(
    async (providerId: string) => {
      try {
        await fetch(`${await getApiUrl()}/ai/consent/${providerId}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        });
      } finally {
        await loadDestinos();
      }
    },
    [loadDestinos],
  );

  useEffect(() => {
    // El destino es un dato de cuenta: sin sesión no hay nada que declarar.
    // Va después de la declaración de `loadDestinos` a propósito: en el array
    // de dependencias, una `const` todavía en zona muerta rompe el render.
    if (user) loadDestinos();
  }, [user, loadDestinos]);

  /**
   * Guarda la configuración de un proveedor.
   *
   * Devuelve el detalle del 409 cuando el cambio movería el destino de los datos
   * sin confirmar (MOLCHAT-BE-003), para que quien llama lo enseñe y vuelva a
   * pedirlo con `confirmar_destino`. Devolver `null` significa que se aplicó.
   */
  const updateProviderConfig = useCallback(async (config: AIProviderConfig) => {
    const res = await fetch(`${await getApiUrl()}/ai/providers/configure`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify(config),
    });

    if (res.status === 409) {
      const cuerpo = await res.json();
      const detalle = cuerpo?.detail;
      if (detalle?.motivo === "cambio_de_destino") {
        return detalle as CambioDeDestino;
      }
    }

    if (!res.ok) {
      throw new Error(`No se pudo guardar la configuración (HTTP ${res.status}).`);
    }

    await loadProviders();
    dispatch({ type: "SET_PROVIDER_CONFIG", config });
    await loadDestinos();
    return null;
  }, [loadProviders, loadDestinos]);

  const fetchConversations = useCallback(async () => {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/conversations`, { headers: getAuthHeaders() });
      if (res.ok) {
        const convs: ConversationInfo[] = await res.json();
        dispatch({ type: "SET_CONVERSATIONS", conversations: convs });
      }
    } catch (err: any) {
      console.warn("fetchConversations failed:", err.message);
    }
  }, []);

  const loadConversation = useCallback(async (convId: string) => {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/conversations/${convId}`, { headers: getAuthHeaders() });
      if (!res.ok) {
        // MOLCHAT-BE-008 dejo de confundir «no existe o no es tuya» (404) con
        // «el historial local fallo» (503). La interfaz tiene que distinguirlos
        // igual, o el arreglo del backend no llega a nadie.
        dispatch({
          type: "SET_WARNING_BANNER",
          warning:
            res.status === 503
              ? "No se pudo leer el historial local. La conversacion sigue en disco; reintenta en unos segundos."
              : "Esa conversacion ya no esta disponible en esta cuenta.",
        });
        return;
      }
      if (res.ok) {
        const data = await res.json();
        const messages: AIMessage[] = (data.messages || []).map((m: any) => ({
          role: m.role,
          content: m.content,
          id: makeId(),
        }));
        dispatch({ type: "SET_MESSAGES", messages });
        dispatch({ type: "SET_ACTIVE_CONVERSATION", id: convId });
        dispatch({ type: "SET_PANEL_OPEN", open: true });
      }
    } catch (err: any) {
      console.warn("loadConversation failed:", err.message);
    }
  }, []);

  const pollResources = useCallback(async () => {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/status`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (data.resources) {
          dispatch({
            type: "SET_RESOURCE_STATUS",
            status: data.resources as ResourceStatus,
          });
        }
        if (data.providers && Array.isArray(data.providers)) {
          dispatch({ type: "SET_PROVIDERS", providers: data.providers });
        }
      }
    } catch (err: any) {
      console.warn("pollResources failed:", err.message);
    }
  }, []);

  const setKeepLoaded = useCallback(async (keep: boolean) => {
    const res = await fetch(`${await getApiUrl()}/ai/settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ keep_loaded: keep }),
    });
    if (!res.ok) {
      throw new Error(`No se pudo cambiar la carga persistente (HTTP ${res.status}).`);
    }
    dispatch({ type: "SET_KEEP_LOADED", keep });
  }, []);

  const setMoleculeContext = useCallback(
    (ctx: Record<string, unknown> | null) => {
      dispatch({ type: "SET_MOLECULE_CONTEXT", context: ctx });
    },
    []
  );

  const newConversation = useCallback(async () => {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: "{}",
      });
      if (!res.ok) {
        // El backend ya no devuelve un id de una conversacion que no llego al
        // disco (MOLCHAT-BE-008). Aqui se dice, en vez de no hacer nada.
        dispatch({
          type: "SET_WARNING_BANNER",
          warning:
            res.status === 503
              ? "No se pudo crear la conversacion: el historial local no acepto escribir."
              : "No se pudo crear la conversacion.",
        });
        return;
      }
      const data = await res.json();
      dispatch({ type: "SET_ACTIVE_CONVERSATION", id: data.id });
      dispatch({ type: "SET_MESSAGES", messages: [] });
      dispatch({ type: "SET_WARNING_BANNER", warning: null });
      dispatch({ type: "SET_TURNO_FALLIDO", fallido: null });
      await fetchConversations();
    } catch (err: any) {
      dispatch({
        type: "SET_WARNING_BANNER",
        warning: `No se pudo crear la conversacion (${err.message || "error de red"}).`,
      });
    }
  }, [fetchConversations]);

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    const finalContent = streamingRef.current;
    if (finalContent) {
      dispatch({
        type: "ADD_MESSAGE",
        message: { role: "assistant", content: finalContent, id: makeId() },
      });
    }
    dispatch({ type: "SET_STREAMING", isStreaming: false });
    dispatch({ type: "SET_STREAMING_CONTENT", content: "" });
    streamingRef.current = "";
  }, []);

  /**
   * Ejecuta UN turno a partir de un snapshot ya cerrado de mensajes.
   *
   * Vive aparte de `sendMessage` porque el reintento tiene que repetir
   * exactamente el mismo turno sin volver a anadir el mensaje del
   * investigador: eso es lo que lo hace idempotente.
   */
  const ejecutarTurno = useCallback(
    async (
      messagesSnapshot: { role: string; content: string }[],
    ): Promise<ResultadoDeEnvio> => {
      dispatch({ type: "SET_TURNO_FALLIDO", fallido: null });
      dispatch({ type: "SET_STREAMING", isStreaming: true });
      dispatch({ type: "SET_STREAMING_CONTENT", content: "" });
      streamingRef.current = "";

      abortRef.current = new AbortController();

      let motivo = "";

      try {
        const res = await fetch(`${await getApiUrl()}/ai/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAuthHeaders() },
          body: JSON.stringify({
            messages: messagesSnapshot,
            provider_id:
              state.activeProviderId === "local" ? null : state.activeProviderId,
            stream: true,
            molecule_context: state.moleculeContext,
            mode: state.chatMode,
            allow_web: state.allowWeb,
          }),
          signal: abortRef.current.signal,
        });

        if (!res.ok) {
          // MOLCHAT-AUD-01 (FE/UX): aqui se hacia `return` en silencio.
          motivo = await motivoDeRespuesta(res);
          dispatch({ type: "SET_STREAMING", isStreaming: false });
          dispatch({
            type: "SET_TURNO_FALLIDO",
            fallido: { motivo, snapshot: messagesSnapshot },
          });
          return { ok: false, motivo };
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          let buffer = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parser SSE correcto: un evento termina con una línea vacía ("\n\n").
            // Dentro de un evento, las líneas "data: " se unen con "\n" (spec SSE).
            // Esto preserva respuestas deterministas multi-línea que ANTES se
            // truncaban a la primera línea (bug: "Propiedades de aspirina:" sin
            // los valores porque las líneas "- MW: 180.2" no empezaban con "data: ").
            // OJO: sep se recalcula al INICIO de cada iteración — nunca depender
            // de continue con sep stale (causaba bucle infinito y página congelada).
            while (true) {
              const sep = buffer.indexOf("\n\n");
              if (sep === -1) break;
              const eventBlock = buffer.slice(0, sep);
              buffer = buffer.slice(sep + 2);

              const dataLines: string[] = [];
              let eventName = "message";
              for (const line of eventBlock.split("\n")) {
                if (line.startsWith("event: ")) {
                  eventName = line.slice(7).trim();
                } else if (line.startsWith("data: ")) {
                  dataLines.push(line.slice(6));
                }
              }
              if (dataLines.length === 0) continue;

              const eventData = dataLines.join("\n");
              if (eventData === "[DONE]") continue;
              if (eventName === "warning" || eventData.startsWith("__WARNING__:")) {
                const clean = eventData.replace(/^__WARNING__:/, "");
                dispatch({ type: "SET_WARNING_BANNER", warning: clean });
                // FIX: NO agregar el warning a streamingRef.current.
              } else {
                streamingRef.current += eventData;
                dispatch({ type: "APPEND_STREAMING", token: eventData });
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== "AbortError") {
          motivo =
            `No se pudo conectar con el motor (${err.message || "error de red"}).`;
          dispatch({
            type: "SET_TURNO_FALLIDO",
            fallido: { motivo, snapshot: messagesSnapshot },
          });
        }
      }

      const finalContent = streamingRef.current;
      if (finalContent) {
        dispatch({
          type: "ADD_MESSAGE",
          message: { role: "assistant", content: finalContent, id: makeId() },
        });
      }
      dispatch({ type: "SET_STREAMING", isStreaming: false });
      dispatch({ type: "SET_STREAMING_CONTENT", content: "" });
      streamingRef.current = "";
      await fetchConversations();

      // Un turno abortado por el investigador no es un fallo: conserva lo que
      // alcanzo a llegar y no ofrece reintento.
      if (motivo && !finalContent) return { ok: false, motivo };
      return { ok: true };
    },
    [
      state.activeProviderId,
      state.moleculeContext,
      state.chatMode,
      state.allowWeb,
      fetchConversations,
    ],
  );

  const sendMessage = useCallback(
    async (content: string): Promise<ResultadoDeEnvio> => {
      if (!content.trim() || state.isStreaming) {
        return { ok: false, motivo: "hay un turno en curso" };
      }

      const userMsg: AIMessage = { role: "user", content, id: makeId() };
      dispatch({ type: "ADD_MESSAGE", message: userMsg });

      const messagesSnapshot = [...state.messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      return ejecutarTurno(messagesSnapshot);
    },
    [state.isStreaming, state.messages, ejecutarTurno],
  );

  /**
   * Repite el ultimo turno fallido con su MISMO snapshot.
   *
   * Idempotente por construccion: no vuelve a anadir el mensaje del
   * investigador, asi que reintentar tres veces deja una sola pregunta en la
   * conversacion, no tres.
   */
  const retryLastTurn = useCallback(async (): Promise<ResultadoDeEnvio> => {
    const fallido = state.turnoFallido;
    if (!fallido || state.isStreaming) {
      return { ok: false, motivo: "no hay turno que reintentar" };
    }
    return ejecutarTurno(fallido.snapshot);
  }, [state.turnoFallido, state.isStreaming, ejecutarTurno]);

  return (
    <AIContext.Provider
      value={{
        state,
        dispatch,
        loadProviders,
        loadDestinos,
        otorgarConsentimiento,
        revocarConsentimiento,
        detectStartup,
        pollResources,
        sendMessage,
        retryLastTurn,
        stopStreaming,
        setActiveProvider,
        newConversation,
        updateProviderConfig,
        setKeepLoaded,
        fetchConversations,
        loadConversation,
        setMoleculeContext,
      }}
    >
      {children}
    </AIContext.Provider>
  );
}

export function useAI() {
  const ctx = useContext(AIContext);
  if (!ctx) throw new Error("useAI debe usarse dentro de AIProvider");
  return ctx;
}
