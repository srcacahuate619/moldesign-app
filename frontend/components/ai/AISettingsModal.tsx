"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Check, Eye, EyeOff, RefreshCw, Zap, AlertTriangle, Monitor, Package, Wrench, Star, Download, CheckCircle2, XCircle, Globe, Server } from "lucide-react";
import { useAI, type AIProviderInfo, type CambioDeDestino } from "@/context/AIContext";
import { fetchBackend } from "../../lib/backendFetch";
import { authorizeNetworkDestination, getAuthHeaders } from "../../lib/api";
import { motivoDeRespuesta } from "@/context/motivoDeTurno";
import { FALLBACK_PROVIDER } from "@/context/AIContext";

function mensajeDeError(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/** Temperatura por defecto de los paneles que la muestran (el local no la muestra). */
function temperaturaPorDefecto(providerId: string): number {
  return providerId === "ollama" ? 0.1 : 0.5;
}

export function AISettingsModal() {
  const { t } = useLanguage();
  const { state, dispatch, setActiveProvider, updateProviderConfig, loadProviders, detectStartup, setKeepLoaded } = useAI();
  // Se guarda el id, no el objeto. El chat sondea `/ai/status` cada 8 s y cada
  // sondeo trae una lista de proveedores nueva; un efecto que reinicializaba la
  // selección con cada lista devolvía el modal a llama.cpp al elegir Ollama o
  // Clave de API, y borraba lo que se estuviera escribiendo.
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const selectedProvider: AIProviderInfo | null =
    state.providers.find((p) => p.id === selectedProviderId)
    ?? (selectedProviderId === "local" ? FALLBACK_PROVIDER : null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState(0.5);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  /** Detalle del 409 cuando el guardado cambiaría a dónde salen los datos. */
  const [cambioDestino, setCambioDestino] = useState<CambioDeDestino | null>(null);
  const [quantInfo, setQuantInfo] = useState<any>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // model browser
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [expandedModel, setExpandedModel] = useState<string | null>(null);
  const [localModels, setLocalModels] = useState<any[]>([]);
  const [downloading, setDownloading] = useState<Record<string, { status: string; progress: number }>>(
    {}
  );
  /** Descarga parada porque la cuenta no autorizó el destino (huggingface.co). */
  const [permisoDescarga, setPermisoDescarga] = useState<
    { modelId: string; filename: string; mensaje: string; servicio: string; host: string } | null
  >(null);

  useEffect(() => {
    if (state.isSettingsOpen) {
      setSettingsError(null);
      void loadProviders().catch((error) => {
        setSettingsError(mensajeDeError(error, "No se pudieron cargar los proveedores."));
      });
    }
  }, [state.isSettingsOpen, loadProviders]);

  useEffect(() => {
    if (!state.isSettingsOpen) return;

    previousFocusRef.current = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();

    function handleDialogKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        dispatch({ type: "SET_SETTINGS_OPEN", open: false });
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
        )
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleDialogKeyDown);
    return () => {
      document.removeEventListener("keydown", handleDialogKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [state.isSettingsOpen, dispatch]);

  // Proveedor cuyos campos ya se cargaron en esta apertura del modal.
  const camposDeRef = useRef<string | null>(null);

  // Al abrir, el modal parte del proveedor activo. Sólo al abrir: el proveedor
  // activo no cambia mientras se elige otro en el modal (se aplica al guardar).
  useEffect(() => {
    if (state.isSettingsOpen) {
      setSelectedProviderId(state.activeProviderId);
      camposDeRef.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sólo en la apertura
  }, [state.isSettingsOpen]);

  // Los campos se cargan una vez por proveedor elegido, no con cada sondeo. Si
  // la lista de proveedores llega después de abrir, se cargan cuando llega.
  useEffect(() => {
    if (!state.isSettingsOpen || !selectedProvider) return;
    if (camposDeRef.current === selectedProvider.id) return;
    camposDeRef.current = selectedProvider.id;
    const cfg = state.providerConfigs[selectedProvider.id];
    // Lo que la cuenta tiene aplicado, no el valor por defecto: al reabrir, el
    // modal enseñaba `localhost` en vez del Ollama guardado, y «Guardar»
    // proponía cambiar el destino de vuelta. Para Ollama, el backend sugiere un
    // modelo instalado si el aplicado no lo está.
    const modeloAplicado = selectedProvider.id === "ollama"
      ? selectedProvider.default_model
      : selectedProvider.model || selectedProvider.default_model;
    setApiKey(cfg?.api_key || "");
    setBaseUrl(cfg?.base_url || selectedProvider.base_url || selectedProvider.default_base_url);
    setModel(cfg?.model || modeloAplicado);
    setTemperature(cfg?.temperature ?? temperaturaPorDefecto(selectedProvider.id));
    setShowKey(false);
    setCambioDestino(null);
  }, [state.isSettingsOpen, selectedProvider, state.providerConfigs]);

  async function loadLocalModels() {
    try {
      const res = await fetchBackend(`/ai/models/local`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        throw new Error(`No se pudieron cargar los modelos locales (HTTP ${res.status}).`);
      }
      const data = await res.json();
      setLocalModels(data.models || []);
    } catch (error) {
      setSettingsError(mensajeDeError(error, "No se pudieron cargar los modelos locales."));
    }
  }

  async function handleSearch() {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) return;
    setSearching(true);
    setSettingsError(null);
    try {
      const res = await fetchBackend(
        `/ai/models/search?q=${encodeURIComponent(searchQuery.trim())}&limit=12`,
        { headers: getAuthHeaders() }
      );
      if (!res.ok) {
        throw new Error(`No se pudo buscar modelos (HTTP ${res.status}).`);
      }
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (error) {
      setSettingsError(mensajeDeError(error, "No se pudo buscar modelos."));
    } finally {
      setSearching(false);
    }
  }

  const pollIntervalsRef = useRef<Set<ReturnType<typeof setInterval>>>(new Set());

  useEffect(() => {
    const ref = pollIntervalsRef.current;
    return () => { ref.forEach(clearInterval); };
  }, []);

  function pollDownload(dlId: string, dlKey: string) {
    const interval = setInterval(async () => {
      try {
        const res = await fetchBackend(`/ai/models/download/${dlId}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) {
          throw new Error(`No se pudo consultar la descarga (HTTP ${res.status}).`);
        }
        const dl = await res.json();
        setDownloading((prev) => ({
          ...prev,
          [dlKey]: { status: dl.status, progress: dl.progress_pct },
        }));
        if (dl.status === "completed" || dl.status === "failed") {
          clearInterval(interval);
          pollIntervalsRef.current.delete(interval);
          if (dl.status === "completed") {
            setModel(dl.filename || filenameFromKey(dlKey));
            void loadLocalModels();
          } else {
            setSettingsError(dl.error ? `La descarga del modelo falló: ${dl.error}` : "La descarga del modelo falló.");
          }
        }
      } catch (error) {
        clearInterval(interval);
        pollIntervalsRef.current.delete(interval);
        setDownloading((prev) => ({ ...prev, [dlKey]: { status: "error", progress: 0 } }));
        setSettingsError(mensajeDeError(error, "No se pudo consultar la descarga."));
      }
    }, 1500);
    pollIntervalsRef.current.add(interval);
  }

  function filenameFromKey(key: string) {
    return key.split("::").pop() || "";
  }

  async function handleDownload(modelId: string, filename: string) {
    const dlKey = `${modelId}::${filename}`;
    setDownloading((prev) => ({ ...prev, [dlKey]: { status: "starting", progress: 0 } }));
    setSettingsError(null);
    try {
      const res = await fetchBackend(`/ai/models/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ model_id: modelId, filename }),
      });
      if (res.status === 403) {
        // Descargar sale a huggingface.co, y eso lo autoriza la cuenta. Antes
        // sólo se leía «HTTP 403» y ninguna pantalla de MolChat permitía
        // autorizarlo: estos botones no podían funcionar.
        const cuerpo = await res.json().catch(() => null);
        const d = cuerpo?.detail;
        setDownloading((prev) => {
          const resto = { ...prev };
          delete resto[dlKey];
          return resto;
        });
        if (d && typeof d === "object" && d.motivo === "sin_permiso" && d.servicio && d.host) {
          setPermisoDescarga({ modelId, filename, mensaje: d.mensaje, servicio: d.servicio, host: d.host });
          return;
        }
        throw new Error(typeof d === "string" ? d : d?.mensaje || "No se pudo iniciar la descarga (HTTP 403).");
      }
      if (!res.ok) {
        throw new Error(`No se pudo iniciar la descarga: ${await motivoDeRespuesta(res)}`);
      }
      const dl = await res.json();
      pollDownload(dl.id, dlKey);
    } catch (error) {
      setDownloading((prev) => ({ ...prev, [dlKey]: { status: "error", progress: 0 } }));
      setSettingsError(mensajeDeError(error, "No se pudo iniciar la descarga."));
    }
  }

  async function autorizarYDescargar() {
    if (!permisoDescarga) return;
    const { modelId, filename, servicio, host } = permisoDescarga;
    setSettingsError(null);
    try {
      await authorizeNetworkDestination(servicio, host);
    } catch (error) {
      setSettingsError(mensajeDeError(error, "No se pudo autorizar el destino."));
      return;
    }
    setPermisoDescarga(null);
    await handleDownload(modelId, filename);
  }

  async function openModelsFolder() {
    setSettingsError(null);
    try {
      const res = await fetchBackend(`/ai/models/open-folder`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        throw new Error(`No se pudo abrir la carpeta de modelos (HTTP ${res.status}).`);
      }
    } catch (error) {
      setSettingsError(mensajeDeError(error, "No se pudo abrir la carpeta de modelos."));
    }
  }

  function selectLocalModel(fname: string) {
    setModel(fname);
  }

  useEffect(() => {
    if (state.isSettingsOpen && selectedProviderId === "local") {
      loadLocalModels();
      loadQuantRecommendation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- una vez por apertura y modo, no por sondeo
  }, [state.isSettingsOpen, selectedProviderId]);

  async function loadQuantRecommendation() {
    try {
      const res = await fetchBackend(`/ai/models/recommend-quant`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        throw new Error(`No se pudo recomendar una cuantización (HTTP ${res.status}).`);
      }
      const data = await res.json();
      setQuantInfo(data);
    } catch (error) {
      setSettingsError(mensajeDeError(error, "No se pudo recomendar una cuantización."));
    }
  }

  if (!state.isSettingsOpen) return null;

  /**
   * Guarda, y si el cambio movería el destino de los datos, lo pregunta antes.
   *
   * MOLCHAT-BE-003: el `base_url` no es un ajuste más. El backend responde 409
   * cuando el host cambia sin confirmar, así que aquí no hay forma de aplicarlo
   * en silencio aunque alguien olvide preguntar.
   */
  async function handleSave(confirmarDestino = false) {
    if (!selectedProvider) return;
    setSettingsError(null);
    // Sólo se envía lo que el panel enseña. Una clave vacía no se envía: el
    // campo sale vacío al reabrir (la clave no vuelve del backend), y enviarlo
    // así sobrescribía la clave guardada con una vacía. El modo local no tiene
    // temperatura en pantalla, y enviar la del deslizador oculto le imponía 0,5.
    const muestraTemperatura = selectedProvider.id !== "local";
    const claveEscrita = apiKey.trim();
    try {
      const cambio = await updateProviderConfig({
        provider_id: selectedProvider.id,
        ...(selectedProvider.requires_api_key && claveEscrita ? { api_key: claveEscrita } : {}),
        ...(selectedProvider.requires_base_url ? { base_url: baseUrl.trim() } : {}),
        model: model.trim(),
        ...(muestraTemperatura ? { temperature } : {}),
        ...(confirmarDestino ? { confirmar_destino: true } : {}),
      });

      if (cambio) {
        setCambioDestino(cambio);
        return;
      }

      setCambioDestino(null);
      await setActiveProvider(selectedProvider.id);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      setTimeout(() => detectStartup(), 500);
    } catch (error) {
      setSaved(false);
      setSettingsError(mensajeDeError(error, "No se pudo guardar la configuración."));
    }
  }

  function handleClose() {
    dispatch({ type: "SET_SETTINGS_OPEN", open: false });
  }

  return (
    <AnimatePresence>
      {state.isSettingsOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 60,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            aria-hidden="true"
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(0,0,0,0.5)",
              backdropFilter: "blur(4px)",
            }}
          />
          <motion.div
            ref={dialogRef}
            data-ai-settings-dialog="true"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-settings-title"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.15 }}
            style={{
              position: "relative",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: 16,
              width: 480,
              maxWidth: "90vw",
              maxHeight: "85vh",
              overflow: "auto",
              padding: 0,
              boxShadow: "0 24px 80px rgba(0,0,0,0.4)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 20px",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <h2 id="ai-settings-title" style={{ margin: 0, fontSize: "1.05em", fontWeight: 600, color: "var(--text)" }}>
                {t("ia_interprete")}
              </h2>
              <button
                ref={closeButtonRef}
                type="button"
                onClick={handleClose}
                aria-label={t("ia_cerrar_configuracion")}
                className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div style={{ padding: "16px 20px" }}>
              {settingsError && (
                <div
                  role="alert"
                  style={{
                    marginBottom: 16,
                    padding: "10px 12px",
                    borderRadius: 8,
                    border: "1px solid rgba(239, 68, 68, 0.4)",
                    background: "rgba(239, 68, 68, 0.08)",
                    color: "var(--text)",
                    fontSize: "0.8125rem",
                    lineHeight: 1.5,
                  }}
                >
                  {settingsError}
                </div>
              )}
              {/* Modo: Local vs Online */}
              <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 6 }}>
                {t("ia_cfg_mode")}
              </label>
              <div style={{ display: "flex", gap: 1, marginBottom: 20, padding: 2, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, width: "fit-content" }}>
                <button
                  type="button"
                  aria-pressed={selectedProvider?.id === "local"}
                  onClick={() => setSelectedProviderId("local")}
                  style={{
                    padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer",
                    fontSize: "0.82em", fontWeight: 600,
                    background: selectedProvider?.id === "local" ? "var(--accent)" : "transparent",
                    color: selectedProvider?.id === "local" ? "#fff" : "var(--text-secondary)",
                    transition: "all 0.15s",
                  }}
                >
                  <Package size={14} className="inline-block mr-1.5" style={{ verticalAlign: "middle" }} />
                  llama.cpp
                </button>
                <button
                  type="button"
                  aria-pressed={selectedProvider?.id === "ollama"}
                  disabled={!state.providers.some((p) => p.id === "ollama")}
                  onClick={() => setSelectedProviderId("ollama")}
                  style={{
                    padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer",
                    fontSize: "0.82em", fontWeight: 600,
                    background: selectedProvider?.id === "ollama" ? "var(--accent)" : "transparent",
                    color: selectedProvider?.id === "ollama" ? "#fff" : "var(--text-secondary)",
                    transition: "all 0.15s",
                  }}
                >
                  <Server size={14} className="inline-block mr-1.5" style={{ verticalAlign: "middle" }} />
                  {t("ia_cfg_ollama")}
                </button>
                <button
                  type="button"
                  aria-pressed={!!selectedProvider && selectedProvider.id !== "local" && selectedProvider.id !== "ollama"}
                  disabled={!state.providers.some((p) => p.requires_api_key)}
                  onClick={() => {
                    // El configurado primero; si no hay ninguno, el primero de la lista.
                    const nube = state.providers.filter((p) => p.requires_api_key);
                    const elegido = nube.find((p) => p.configured) || nube[0];
                    if (elegido) setSelectedProviderId(elegido.id);
                  }}
                  style={{
                    padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer",
                    fontSize: "0.82em", fontWeight: 600,
                    background: (selectedProvider && selectedProvider.id !== "local" && selectedProvider.id !== "ollama") ? "var(--accent)" : "transparent",
                    color: (selectedProvider && selectedProvider.id !== "local" && selectedProvider.id !== "ollama") ? "#fff" : "var(--text-secondary)",
                    transition: "all 0.15s",
                  }}
                >
                  <Globe size={14} className="inline-block mr-1.5" style={{ verticalAlign: "middle" }} />
                  {t("ia_cfg_api_key")}
                </button>
              </div>

              {/* Dynamic config fields */}
              {/* OLLAMA MODE — local server, no API key */}
              {selectedProvider && selectedProvider.id === "ollama" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {/* Estado medido por el backend sobre la URL guardada, no un
                      texto fijo: antes decía «debe estar en ejecución en …»
                      tanto si respondía como si no. */}
                  <div
                    data-testid="estado-ollama"
                    role="status"
                    style={{
                      padding: "8px 12px", borderRadius: 8, fontSize: "0.8em", lineHeight: 1.5,
                      background: selectedProvider.configured ? "rgba(34,197,94,0.06)" : "rgba(245,158,11,0.06)",
                      border: `1px solid ${selectedProvider.configured ? "rgba(34,197,94,0.25)" : "rgba(245,158,11,0.25)"}`,
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Server size={14} className="inline-block mr-1" style={{ verticalAlign: "middle", color: selectedProvider.configured ? "#22C55E" : "#F59E0B" }} />
                    {selectedProvider.configured
                      ? t(selectedProvider.available_models.length === 1 ? "ia_ollama_responde_uno" : "ia_ollama_responde_varios", {
                          url: selectedProvider.base_url || selectedProvider.default_base_url,
                          n: selectedProvider.available_models.length,
                        })
                      : selectedProvider.estado || t("ia_ollama_sin_comprobar")}
                    {baseUrl.trim() && baseUrl.trim() !== (selectedProvider.base_url || selectedProvider.default_base_url) && (
                      <div style={{ marginTop: 4 }}>{t("ia_ollama_url_sin_guardar")}</div>
                    )}
                  </div>
                  {selectedProvider.requires_base_url && (
                    <div>
                      <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>{t("ia_url_servidor")}</label>
                      <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={selectedProvider.default_base_url}
                        style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                      />
                    </div>
                  )}
                  <div>
                    <label htmlFor="modelo-ollama" style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>{t("se_sel_model")}</label>
                    {selectedProvider.available_models.length > 0 && (
                      <div role="group" aria-label={t("ia_ollama_instalados")} style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
                        {selectedProvider.available_models.map((m) => (
                          <button key={m} type="button" aria-pressed={model === m} onClick={() => setModel(m)}
                            style={{
                              padding: "4px 10px", borderRadius: 6, fontSize: "0.78em", cursor: "pointer",
                              border: model === m ? "2px solid var(--accent)" : "1px solid var(--border)",
                              background: model === m ? "var(--accent)" : "var(--bg)",
                              color: model === m ? "#fff" : "var(--text)",
                            }}
                          >
                            {m}
                          </button>
                        ))}
                      </div>
                    )}
                    <input id="modelo-ollama" type="text" value={model} onChange={(e) => setModel(e.target.value)}
                      placeholder={selectedProvider.default_model}
                      style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>{t("auto_301a6a824758")} {temperature.toFixed(1)}</label>
                    <input type="range" min="0" max="1" step="0.1" value={temperature} onChange={(e) => setTemperature(parseFloat(e.target.value))} style={{ width: "100%" }} />
                  </div>
                </div>
              )}

              {/* ONLINE MODE — cloud provider + API key */}
              {selectedProvider && selectedProvider.id !== "local" && selectedProvider.id !== "ollama" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 6 }}>
                      {t("ia_cfg_cloud_provider")}
                    </label>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {state.providers.filter(p => p.id !== "local" && p.id !== "ollama").map((p) => (
                        <button key={p.id} type="button" aria-pressed={selectedProvider?.id === p.id} onClick={() => setSelectedProviderId(p.id)}
                          style={{
                            padding: "6px 12px", borderRadius: 6, border: selectedProvider?.id === p.id ? "2px solid var(--accent)" : "1px solid var(--border)",
                            background: selectedProvider?.id === p.id ? "var(--accent)" : "var(--bg)",
                            color: selectedProvider?.id === p.id ? "#fff" : "var(--text)",
                            cursor: "pointer", fontSize: "0.78em", transition: "all 0.15s",
                          }}
                        >
                          {p.name}
                          {!p.configured && <span style={{ marginLeft: 4, color: "#EF4444" }}>⚠</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                  {selectedProvider.requires_api_key && (
                    <div>
                      <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>{t("ia_cfg_api_key")}</label>
                      <div style={{ position: "relative" }}>
                        <input type={showKey ? "text" : "password"} value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                          placeholder={selectedProvider.configured ? t("ia_cfg_api_key_guardada") : selectedProvider.env_key || t("ia_cfg_api_key_example")}
                          style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 36px 10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                        />
                        <button type="button" onClick={() => setShowKey(!showKey)} aria-label={showKey ? t("ia_cfg_hide_api_key") : t("ia_cfg_show_api_key")} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer" }}>
                          {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>
                  )}
                  {selectedProvider.requires_base_url && (
                    <div>
                      <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>{t("ia_cfg_base_url")}</label>
                      <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={selectedProvider.default_base_url}
                        style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                      />
                    </div>
                  )}
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>{t("se_sel_model")}</label>
                    <input type="text" value={model} onChange={(e) => setModel(e.target.value)}
                      placeholder={selectedProvider.default_model}
                      style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>{t("auto_301a6a824758")} {temperature.toFixed(1)}</label>
                    <input type="range" min="0" max="1" step="0.1" value={temperature} onChange={(e) => setTemperature(parseFloat(e.target.value))} style={{ width: "100%" }} />
                  </div>
                </div>
              )}

              {/* LOCAL MODE — GPU + model selector + HuggingFace */}
              {selectedProvider && selectedProvider.id === "local" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {/* GPU status */}
                  <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)", fontSize: "0.8em", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                    {state.resourceStatus?.gpu_name ? (
                      state.resourceStatus.using_gpu ? (
                        <span><Zap size={14} className="inline-block mr-1 text-amber-400" style={{ verticalAlign: "middle" }} /> GPU: {state.resourceStatus.gpu_name} ({state.resourceStatus.gpu_vram_total_gb?.toFixed(1) ?? t("auto_5bab61eb5317")} GB, {state.resourceStatus.vram_free_gb >= 0 ? `${state.resourceStatus.vram_free_gb.toFixed(1)} ${t("ia_cfg_vram_free")}` : t("auto_5bab61eb5317")})</span>
                      ) : state.resourceStatus.llm_state === "loaded" ? (
                        <span style={{ color: "#F59E0B" }}><AlertTriangle size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> GPU ({state.resourceStatus.gpu_name}{t("auto_0ce6ec21b144")}</span>
                      ) : (
                        <span><Monitor size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> GPU: {state.resourceStatus.gpu_name} ({state.resourceStatus.gpu_vram_total_gb?.toFixed(1) ?? t("auto_5bab61eb5317")}{t("auto_ce040e015442")}</span>
                      )
                    ) : state.resourceStatus?.vram_free_gb !== undefined && state.resourceStatus.vram_free_gb >= 0 && state.resourceStatus.vram_free_gb < 2 ? (
                      <span>{t("ia_cfg_vram_insufficient", { vram: state.resourceStatus.vram_free_gb.toFixed(1), ram: state.resourceStatus?.ram_free_gb?.toFixed(1) ?? t("auto_5bab61eb5317") })}</span>
                    ) : (
                      <span><Monitor size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> {t("auto_94135ee04adb")} {t("ia_cfg_ram_free", { gb: state.resourceStatus?.ram_free_gb?.toFixed(1) ?? t("auto_5bab61eb5317") })}</span>
                    )}
                  </div>

                  {/* Model selector */}
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>
                      <Package size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> {t("se_sel_model")}
                    </label>
                    {localModels.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 160, overflow: "auto" }}>
                        {localModels.map((m: any) => (
                          <button key={m.filename} onClick={() => selectLocalModel(m.filename)}
                            style={{
                              display: "flex", alignItems: "center", justifyContent: "space-between",
                              padding: "8px 12px", borderRadius: 6, border: model === m.filename ? "2px solid var(--accent)" : "1px solid var(--border)",
                              background: model === m.filename ? "var(--accent)" : "var(--bg)",
                              color: model === m.filename ? "#fff" : "var(--text)",
                              cursor: "pointer", fontSize: "0.78em", width: "100%", textAlign: "left",
                              transition: "all 0.15s",
                            }}
                          >
                            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, marginRight: 8 }}>
                              {m.quant ? `[${m.quant}] ` : ""}{m.filename}
                            </span>
                            <span style={{ opacity: 0.7, fontSize: "0.85em", whiteSpace: "nowrap" }}>{m.size_display}</span>
                            {model === m.filename && <Check size={14} style={{ marginLeft: 8 }} />}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div style={{ padding: "10px 12px", borderRadius: 6, border: "1px dashed var(--border)", fontSize: "0.78em", color: "var(--text-dim)", textAlign: "center" }}>
                        {t("ia_sin_modelos")}
                      </div>
                    )}
                  </div>

                  {/* Recommended local models downloader */}
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 10 }}>
                      <Download size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> {t("ia_modelos_recomendados")}
                    </label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {[
                        {
                          id: "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
                          filename: "qwen2.5-1.5b-instruct-q4_k_m.gguf",
                          name: `${t("ia_cfg_qwen15_model")} (${t("ia_cfg_recommended")})`,
                          size: "1.1 GB",
                          desc: t("auto_7786e423c133"),
                        },
                        {
                          id: "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                          filename: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
                          name: `${t("ia_cfg_qwen05_model")} (${t("ia_cfg_lightweight")})`,
                          size: "398 MB",
                          desc: t("auto_3c11e2b8db88"),
                        },
                        {
                          // Sustituye a Phi-3.5 Mini (decisión del propietario,
                          // 2026-10-10): el Qwen más reciente de tamaño parecido
                          // con uso de herramientas. Apache-2.0. Piensa por
                          // defecto y MolChat se lo apaga (`local_llm.py`).
                          id: "unsloth/Qwen3.5-4B-GGUF",
                          filename: "Qwen3.5-4B-Q4_K_M.gguf",
                          name: `${t("ia_cfg_qwen35_4b_model")} (${t("ia_cfg_advanced")})`,
                          size: "2.7 GB",
                          desc: t("ia_cfg_qwen35_4b_desc"),
                        }
                      ].map((m) => {
                        const isDownloaded = localModels.some((lm) => lm.filename === m.filename);
                        const dlKey = `${m.id}::${m.filename}`;
                        const dl = downloading[dlKey];
                        
                        return (
                          <div key={m.filename} style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "10px 14px", background: "var(--bg)", display: "flex", flexDirection: "column", gap: 6 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <div>
                                <span style={{ fontWeight: 600, fontSize: "0.82em", color: "var(--text)" }}>{m.name}</span>
                                <span style={{ fontSize: "0.75em", color: "var(--text-secondary)", marginLeft: 6 }}>({m.size})</span>
                              </div>
                              {isDownloaded ? (
                                <span style={{ color: "#22C55E", fontSize: "0.78em", fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                                  <CheckCircle2 size={12} /> {t("ia_cfg_available")}
                                </span>
                              ) : dl ? (
                                dl.status === "downloading" || dl.status === "starting" ? (
                                  <span style={{ color: "var(--accent)", fontSize: "0.78em", fontWeight: 600 }}>
                                    {dl.progress.toFixed(0)}%
                                  </span>
                                ) : dl.status === "completed" ? (
                                  <span style={{ color: "#22C55E", fontSize: "0.78em", fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                                    <CheckCircle2 size={12} /> {t("pn_prep_listo")}
                                  </span>
                                ) : (
                                  <span style={{ color: "#EF4444", fontSize: "0.78em", fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                                    <XCircle size={12} /> {t("error")}
                                  </span>
                                )
                              ) : (
                                <button
                                  onClick={() => handleDownload(m.id, m.filename)}
                                  style={{ padding: "4px 10px", borderRadius: 6, border: "none", background: "var(--accent)", color: "#fff", cursor: "pointer", fontSize: "0.78em", fontWeight: 600 }}
                                >
                                  {t("c_descargar")}
                                </button>
                              )}
                            </div>
                            <div style={{ fontSize: "0.75em", color: "var(--text-dim)", lineHeight: 1.3 }}>
                              {m.desc}
                            </div>
                            {dl && (dl.status === "downloading" || dl.status === "starting") && (
                              <div style={{ height: 4, borderRadius: 2, background: "var(--border)", overflow: "hidden", marginTop: 4 }}>
                                <div style={{ height: "100%", width: `${dl.progress}%`, background: "var(--accent)", transition: "width 0.3s" }} />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {permisoDescarga && (
                    <div
                      data-testid="permiso-descarga"
                      role="alert"
                      style={{
                        padding: "10px 12px", borderRadius: 8, fontSize: "0.8em", lineHeight: 1.5,
                        background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.35)",
                        color: "var(--text)", display: "flex", flexDirection: "column", gap: 8,
                      }}
                    >
                      <span>{permisoDescarga.mensaje}</span>
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <button type="button" onClick={() => setPermisoDescarga(null)}
                          style={{ padding: "4px 10px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", cursor: "pointer" }}
                        >
                          {t("c_cancelar")}
                        </button>
                        <button type="button" onClick={() => void autorizarYDescargar()}
                          style={{ padding: "4px 10px", borderRadius: 6, border: "none", background: "var(--accent)", color: "#fff", cursor: "pointer", fontWeight: 600 }}
                        >
                          {t("ia_autorizar_y_descargar", { host: permisoDescarga.host })}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Open models directory explorer */}
                  <div style={{ marginTop: 6, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
                    <button
                      onClick={openModelsFolder}
                      style={{
                        width: "100%",
                        padding: "10px",
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                        background: "var(--bg)",
                        color: "var(--text-secondary)",
                        cursor: "pointer",
                        fontSize: "0.85em",
                        fontWeight: 600,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 8,
                        transition: "all 0.15s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "var(--bg-secondary)";
                        e.currentTarget.style.borderColor = "var(--text-secondary)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "var(--bg)";
                        e.currentTarget.style.borderColor = "var(--border)";
                      }}
                    >
                      <Wrench size={14} />
                      {t("ia_abrir_carpeta_modelos")}
                    </button>
                  </div>

                  {/* Quantization */}
                  {quantInfo && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <label style={{ fontSize: "0.82em", color: "var(--text-secondary)" }}>
                        <Wrench size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> {t("ia_cuantizacion")}
                      </label>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {quantInfo.options?.map((opt: any) => {
                          // El botón elige TU modelo de esa cuantización. No
                          // descarga: el backend no dice qué archivo sería, y el
                          // botón lanzaba una descarga con nombre vacío (400).
                          // Antes además buscaba «Q4_K_M» en nombres en minúscula
                          // y nunca encontraba el archivo que sí estaba.
                          const conEsta = localModels.filter((m: any) => m.quant === opt.quant);
                          const unico = conEsta.length === 1 ? conEsta[0] : null;
                          const isSelected = localModels.find((m: any) => m.filename === model)?.quant === opt.quant;
                          const porQue = conEsta.length === 0 ? t("ia_cuant_sin_modelo") : conEsta.length > 1 ? t("ia_cuant_varios") : "";
                          return (
                            <button key={opt.quant} type="button" aria-pressed={isSelected} onClick={() => {
                              if (unico) selectLocalModel(unico.filename);
                            }}
                              disabled={!unico}
                              title={`${opt.description}\n~${opt.model_size_gb}GB · ≥${opt.min_ram_gb}GB${porQue ? `\n${porQue}` : ""}`}
                              style={{
                                padding: "5px 10px", borderRadius: 6, border: `1.5px solid ${opt.is_recommended ? "#22C55E" : "var(--border)"}`,
                                background: isSelected ? "var(--accent)" : opt.is_recommended ? "rgba(34,197,94,0.08)" : "var(--bg)",
                                color: isSelected ? "#fff" : opt.is_recommended ? "#22C55E" : opt.fits ? "var(--text-secondary)" : "var(--text-dim)",
                                cursor: unico ? "pointer" : "default", fontSize: "0.75rem", whiteSpace: "nowrap",
                                opacity: unico || isSelected ? 1 : 0.4, fontWeight: isSelected || opt.is_recommended ? 600 : 400,
                              }}
                            >
                              {opt.label}
                              {opt.is_recommended && !isSelected && <span style={{ fontSize: "0.85em", marginLeft: 3 }}>★</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Keep loaded toggle */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input type="checkbox" id="keep-loaded" checked={state.resourceStatus?.keep_loaded || false}
                      onChange={async (e) => {
                        setSettingsError(null);
                        try {
                          await setKeepLoaded(e.target.checked);
                        } catch (error) {
                          setSettingsError(mensajeDeError(error, "No se pudo cambiar la carga persistente."));
                        }
                      }}
                      style={{ accentColor: "var(--accent)" }}
                    />
                    <label htmlFor="keep-loaded" style={{ fontSize: "0.8em", color: "var(--text-secondary)", cursor: "pointer", lineHeight: 1.4 }}>
                      {t("ia_cfg_keep_loaded")}
                    </label>
                  </div>
                </div>
              )}
            </div>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                padding: "12px 20px",
                borderTop: "1px solid var(--border)",
              }}
            >
              {cambioDestino && (
                <div
                  data-testid="confirmar-destino"
                  style={{
                    padding: "10px 12px",
                    borderRadius: 8,
                    border: "1px solid rgba(239, 68, 68, 0.4)",
                    background: "rgba(239, 68, 68, 0.08)",
                    color: "#EF4444",
                    fontSize: "0.82em",
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <span>{cambioDestino.mensaje}</span>
                  <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    <button
                      onClick={() => setCambioDestino(null)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: "1px solid var(--border)",
                        background: "var(--bg)",
                        color: "var(--text)",
                        cursor: "pointer",
                      }}
                    >
                      {t("c_cancelar")}
                    </button>
                    <button
                      onClick={() => handleSave(true)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: "1px solid rgba(239, 68, 68, 0.5)",
                        background: "rgba(239, 68, 68, 0.15)",
                        color: "#EF4444",
                        cursor: "pointer",
                      }}
                    >
                      {t("ia_cambiar_destino")}
                    </button>
                  </div>
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                onClick={handleClose}
                style={{
                  padding: "8px 16px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--bg)",
                  color: "var(--text)",
                  cursor: "pointer",
                  fontSize: "0.85em",
                }}
              >
                {t("c_cerrar")}
              </button>
              <button
                onClick={() => handleSave()}
                style={{
                  padding: "8px 16px",
                  borderRadius: 8,
                  border: "none",
                  background: saved ? "#22C55E" : "var(--accent)",
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: "0.85em",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  transition: "background 0.2s",
                }}
              >
                {saved ? (
                  <>
                    <Check size={14} /> {t("ia_cfg_saved")}
                  </>
                ) : (
                  t("auto_ca034f0fac8f")
                )}
              </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
