"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Check, Eye, EyeOff, RefreshCw, Zap, AlertTriangle, Monitor, Package, Wrench, Star, Download, CheckCircle2, XCircle, Globe, Server } from "lucide-react";
import { useAI, type AIProviderInfo, type CambioDeDestino } from "@/context/AIContext";
import { getApiUrl } from "../../lib/config";
import { FALLBACK_PROVIDER } from "@/context/AIContext";

export function AISettingsModal() {
  const { state, dispatch, setActiveProvider, updateProviderConfig, loadProviders, detectStartup, setKeepLoaded } = useAI();
  const [selectedProvider, setSelectedProvider] = useState<AIProviderInfo | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState(0.5);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  /** Detalle del 409 cuando el guardado cambiaría a dónde salen los datos. */
  const [cambioDestino, setCambioDestino] = useState<CambioDeDestino | null>(null);
  const [quantInfo, setQuantInfo] = useState<any>(null);

  // model browser
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [expandedModel, setExpandedModel] = useState<string | null>(null);
  const [localModels, setLocalModels] = useState<any[]>([]);
  const [downloading, setDownloading] = useState<Record<string, { status: string; progress: number }>>(
    {}
  );

  useEffect(() => {
    if (state.isSettingsOpen) {
      loadProviders();
    }
  }, [state.isSettingsOpen, loadProviders]);

  // Initialize selection when opening modal or changing active provider globally
  useEffect(() => {
    if (state.isSettingsOpen) {
      const active = state.providers.find((p) => p.id === state.activeProviderId);
      setSelectedProvider(active || null);
    }
  }, [state.isSettingsOpen, state.activeProviderId]);

  // Sync config fields when selectedProvider or global config loads
  useEffect(() => {
    if (selectedProvider) {
      const p = state.providers.find((prov) => prov.id === selectedProvider.id) || selectedProvider;
      const cfg = state.providerConfigs[p.id];
      setApiKey(cfg?.api_key || "");
      setBaseUrl(cfg?.base_url || p.default_base_url);
      setModel(cfg?.model || p.default_model);
      setTemperature(cfg?.temperature ?? 0.5);
    }
  }, [selectedProvider, state.providers, state.providerConfigs]);

  async function loadLocalModels() {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/models/local`);
      if (res.ok) {
        const data = await res.json();
        setLocalModels(data.models || []);
      }
    } catch {}
  }

  async function handleSearch() {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) return;
    setSearching(true);
    try {
      const res = await fetch(
        `${await getApiUrl()}/ai/models/search?q=${encodeURIComponent(searchQuery.trim())}&limit=12`
      );
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch {} finally {
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
        const res = await fetch(`${await getApiUrl()}/ai/models/download/${dlId}`);
        if (res.ok) {
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
              loadLocalModels();
            }
          }
        }
      } catch {
        clearInterval(interval);
        pollIntervalsRef.current.delete(interval);
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
    try {
      const res = await fetch(`${await getApiUrl()}/ai/models/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId, filename }),
      });
      if (res.ok) {
        const dl = await res.json();
        pollDownload(dl.id, dlKey);
      } else {
        setDownloading((prev) => ({ ...prev, [dlKey]: { status: "error", progress: 0 } }));
      }
    } catch {
      setDownloading((prev) => ({ ...prev, [dlKey]: { status: "error", progress: 0 } }));
    }
  }

  async function openModelsFolder() {
    try {
      await fetch(`${await getApiUrl()}/ai/models/open-folder`, { method: "POST" });
    } catch (err) {
      console.error("Error opening models folder:", err);
    }
  }

  function selectLocalModel(fname: string) {
    setModel(fname);
  }

  useEffect(() => {
    if (state.isSettingsOpen && selectedProvider?.id === "local") {
      loadLocalModels();
      loadQuantRecommendation();
    }
  }, [state.isSettingsOpen, selectedProvider]);

  async function loadQuantRecommendation() {
    try {
      const res = await fetch(`${await getApiUrl()}/ai/models/recommend-quant`);
      if (res.ok) {
        const data = await res.json();
        setQuantInfo(data);
      }
    } catch {}
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
    const cambio = await updateProviderConfig({
      provider_id: selectedProvider.id,
      api_key: apiKey,
      base_url: baseUrl,
      model: model,
      temperature: temperature,
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
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(0,0,0,0.5)",
              backdropFilter: "blur(4px)",
            }}
          />
          <motion.div
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
              <h2 style={{ margin: 0, fontSize: "1.05em", fontWeight: 600, color: "var(--text)" }}>
                Intérprete IA
              </h2>
              <button
                onClick={handleClose}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: "16px 20px" }}>
              {/* Modo: Local vs Online */}
              <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 6 }}>
                Modo
              </label>
              <div style={{ display: "flex", gap: 1, marginBottom: 20, padding: 2, background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, width: "fit-content" }}>
                <button
                  onClick={() => {
                    const local = state.providers.find(p => p.id === "local") || FALLBACK_PROVIDER;
                    setSelectedProvider(local);
                    setModel(localModels[0]?.filename || local.default_model);
                  }}
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
                  onClick={() => {
                    const ollama = state.providers.find(p => p.id === "ollama");
                    if (ollama) {
                      setSelectedProvider(ollama);
                      const cfg = state.providerConfigs[ollama.id];
                      setApiKey("");
                      setBaseUrl(cfg?.base_url || ollama.default_base_url);
                      setModel(cfg?.model || ollama.default_model);
                      setTemperature(cfg?.temperature ?? 0.1);
                    }
                  }}
                  style={{
                    padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer",
                    fontSize: "0.82em", fontWeight: 600,
                    background: selectedProvider?.id === "ollama" ? "var(--accent)" : "transparent",
                    color: selectedProvider?.id === "ollama" ? "#fff" : "var(--text-secondary)",
                    transition: "all 0.15s",
                  }}
                >
                  <Server size={14} className="inline-block mr-1.5" style={{ verticalAlign: "middle" }} />
                  Ollama
                </button>
                <button
                  onClick={() => {
                    const online = state.providers.find(p => p.id !== "local" && p.id !== "ollama") || state.providers[0] || FALLBACK_PROVIDER;
                    setSelectedProvider(online);
                    const cfg = state.providerConfigs[online.id];
                    setApiKey(cfg?.api_key || "");
                    setBaseUrl(cfg?.base_url || online.default_base_url);
                    setModel(cfg?.model || online.default_model);
                    setTemperature(cfg?.temperature ?? 0.5);
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
                  API Key
                </button>
              </div>

              {/* Dynamic config fields */}
              {/* OLLAMA MODE — local server, no API key */}
              {selectedProvider && selectedProvider.id === "ollama" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div style={{ padding: "8px 12px", borderRadius: 8, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)", fontSize: "0.8em", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                    <span><Server size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> Ollama debe estar instalado y corriendo en {baseUrl || "http://localhost:11434"}. Sin API key.</span>
                  </div>
                  {selectedProvider.requires_base_url && (
                    <div>
                      <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>URL del servidor</label>
                      <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={selectedProvider.default_base_url}
                        style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                      />
                    </div>
                  )}
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>Modelo</label>
                    <input type="text" value={model} onChange={(e) => setModel(e.target.value)}
                      placeholder={selectedProvider.default_model}
                      style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>Temperatura: {temperature.toFixed(1)}</label>
                    <input type="range" min="0" max="1" step="0.1" value={temperature} onChange={(e) => setTemperature(parseFloat(e.target.value))} style={{ width: "100%" }} />
                  </div>
                </div>
              )}

              {/* ONLINE MODE — cloud provider + API key */}
              {selectedProvider && selectedProvider.id !== "local" && selectedProvider.id !== "ollama" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 6 }}>
                      Proveedor cloud
                    </label>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {state.providers.filter(p => p.id !== "local" && p.id !== "ollama").map((p) => (
                        <button key={p.id} onClick={() => {
                          setSelectedProvider(p);
                          const cfg = state.providerConfigs[p.id];
                          setApiKey(cfg?.api_key || "");
                          setBaseUrl(cfg?.base_url || p.default_base_url);
                          setModel(cfg?.model || p.default_model);
                          setTemperature(cfg?.temperature ?? 0.5);
                        }}
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
                      <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>API Key</label>
                      <div style={{ position: "relative" }}>
                        <input type={showKey ? "text" : "password"} value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                          placeholder={selectedProvider.env_key || "sk-..."}
                          style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 36px 10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                        />
                        <button onClick={() => setShowKey(!showKey)} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer" }}>
                          {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>
                  )}
                  {selectedProvider.requires_base_url && (
                    <div>
                      <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>Base URL</label>
                      <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={selectedProvider.default_base_url}
                        style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                      />
                    </div>
                  )}
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>Modelo</label>
                    <input type="text" value={model} onChange={(e) => setModel(e.target.value)}
                      placeholder={selectedProvider.default_model}
                      style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text)", fontSize: "0.9em", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>Temperatura: {temperature.toFixed(1)}</label>
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
                        <span><Zap size={14} className="inline-block mr-1 text-amber-400" style={{ verticalAlign: "middle" }} /> GPU: {state.resourceStatus.gpu_name} ({state.resourceStatus.gpu_vram_total_gb?.toFixed(1) ?? "?"}GB, {state.resourceStatus.vram_free_gb >= 0 ? state.resourceStatus.vram_free_gb.toFixed(1) + "GB libre" : "?"})</span>
                      ) : state.resourceStatus.llm_state === "loaded" ? (
                        <span style={{ color: "#F59E0B" }}><AlertTriangle size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> GPU ({state.resourceStatus.gpu_name}) no usada — llama-cpp-python sin CUDA</span>
                      ) : (
                        <span><Monitor size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> GPU: {state.resourceStatus.gpu_name} ({state.resourceStatus.gpu_vram_total_gb?.toFixed(1) ?? "?"}GB). Se usará al cargar.</span>
                      )
                    ) : state.resourceStatus?.vram_free_gb !== undefined && state.resourceStatus.vram_free_gb >= 0 && state.resourceStatus.vram_free_gb < 2 ? (
                      <span>VRAM insuficiente ({state.resourceStatus.vram_free_gb.toFixed(1)}GB). CPU: {state.resourceStatus?.ram_free_gb?.toFixed(1) ?? "?"}GB RAM.</span>
                    ) : (
                      <span><Monitor size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> Sin GPU — CPU: {state.resourceStatus?.ram_free_gb?.toFixed(1) ?? "?"}GB RAM libre.</span>
                    )}
                  </div>

                  {/* Model selector */}
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 4 }}>
                      <Package size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> Modelo
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
                        Sin modelos descargados. Busca uno en HuggingFace abajo.
                      </div>
                    )}
                  </div>

                  {/* Recommended local models downloader */}
                  <div>
                    <label style={{ display: "block", fontSize: "0.85em", color: "var(--text-secondary)", marginBottom: 10 }}>
                      <Download size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> Modelos recomendados para descarga local
                    </label>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {[
                        {
                          id: "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
                          filename: "qwen2.5-1.5b-instruct-q4_k_m.gguf",
                          name: "Qwen2.5 1.5B (Recomendado)",
                          size: "1.1 GB",
                          desc: "Excelente balance entre velocidad y razonamiento científico local.",
                        },
                        {
                          id: "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                          filename: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
                          name: "Qwen2.5 0.5B (Ligero)",
                          size: "398 MB",
                          desc: "Modelo ultraligero ideal para PCs sin GPU y recursos muy limitados.",
                        },
                        {
                          id: "azure/Phi-3.5-mini-instruct-Q4_K_M",
                          filename: "Phi-3.5-mini-instruct-Q4_K_M.gguf",
                          name: "Phi-3.5 Mini 3.8B (Avanzado)",
                          size: "2.2 GB",
                          desc: "Razonamiento científico más avanzado, requiere mejor procesador/RAM.",
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
                                  <CheckCircle2 size={12} /> Disponible
                                </span>
                              ) : dl ? (
                                dl.status === "downloading" || dl.status === "starting" ? (
                                  <span style={{ color: "var(--accent)", fontSize: "0.78em", fontWeight: 600 }}>
                                    {dl.progress.toFixed(0)}%
                                  </span>
                                ) : dl.status === "completed" ? (
                                  <span style={{ color: "#22C55E", fontSize: "0.78em", fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                                    <CheckCircle2 size={12} /> Listo
                                  </span>
                                ) : (
                                  <span style={{ color: "#EF4444", fontSize: "0.78em", fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                                    <XCircle size={12} /> Error
                                  </span>
                                )
                              ) : (
                                <button
                                  onClick={() => handleDownload(m.id, m.filename)}
                                  style={{ padding: "4px 10px", borderRadius: 6, border: "none", background: "var(--accent)", color: "#fff", cursor: "pointer", fontSize: "0.78em", fontWeight: 600 }}
                                >
                                  Descargar
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
                      Abrir carpeta de modelos locales (Explorador)
                    </button>
                  </div>

                  {/* Quantization */}
                  {quantInfo && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <label style={{ fontSize: "0.82em", color: "var(--text-secondary)" }}>
                        <Wrench size={14} className="inline-block mr-1" style={{ verticalAlign: "middle" }} /> Cuantización
                      </label>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {quantInfo.options?.map((opt: any) => {
                          const localFile = localModels.find((m: any) => m.filename.includes(opt.quant.replace("_", "_")));
                          const isSelected = model.includes(opt.quant) || (localFile && model === localFile.filename);
                          return (
                            <button key={opt.quant} onClick={() => {
                              if (localFile) selectLocalModel(localFile.filename);
                              else if (opt.fits) handleDownload(opt.model_id || "Qwen/Qwen2.5-1.5B-Instruct-GGUF", opt.filename || "");
                            }}
                              disabled={!opt.fits}
                              title={`${opt.description}\n~${opt.model_size_gb}GB · ≥${opt.min_ram_gb}GB`}
                              style={{
                                padding: "5px 10px", borderRadius: 6, border: `1.5px solid ${opt.is_recommended ? "#22C55E" : "var(--border)"}`,
                                background: isSelected ? "var(--accent)" : opt.is_recommended ? "rgba(34,197,94,0.08)" : "var(--bg)",
                                color: isSelected ? "#fff" : opt.is_recommended ? "#22C55E" : opt.fits ? "var(--text-secondary)" : "var(--text-dim)",
                                cursor: opt.fits ? "pointer" : "default", fontSize: "0.74em", whiteSpace: "nowrap",
                                opacity: opt.fits ? 1 : 0.4, fontWeight: isSelected || opt.is_recommended ? 600 : 400,
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
                      onChange={async (e) => { await setKeepLoaded(e.target.checked); }}
                      style={{ accentColor: "var(--accent)" }}
                    />
                    <label htmlFor="keep-loaded" style={{ fontSize: "0.8em", color: "var(--text-secondary)", cursor: "pointer", lineHeight: 1.4 }}>
                      Mantener MolChat cargado durante evaluaciones
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
                      Cancelar
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
                      Cambiar el destino
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
                Cerrar
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
                    <Check size={14} /> Guardado
                  </>
                ) : (
                  "Guardar configuración"
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
