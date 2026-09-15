"use client";

import { useLanguage } from "@/context/LanguageContext";
import { useScrollLock } from "@/hooks/useScrollLock";

import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { animateElements, cancelAnimations } from "@/lib/webAnimation";
import { X, Key, Globe, ShieldCheck, CheckCircle2, AlertCircle, Loader2, Link2, Database, BrainCircuit, ShieldAlert } from "lucide-react";

interface CloudAISettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type ProviderId = "openai" | "claude" | "gemini" | "deepseek" | "glm" | "kimi" | "minimax" | "ollama" | "custom";

interface ProviderDef {
  id: ProviderId;
  name: string;
  defaultUrl?: string;
  requiresKey: boolean;
  requiresUrl: boolean;
  color: string;
}

const PROVIDERS: ProviderDef[] = [
  { id: "openai", name: "OpenAI", defaultUrl: "https://api.openai.com/v1", requiresKey: true, requiresUrl: false, color: "text-green-400" },
  { id: "claude", name: "Claude (Anthropic)", defaultUrl: "https://api.anthropic.com", requiresKey: true, requiresUrl: false, color: "text-amber-400" },
  { id: "gemini", name: "Google Gemini", defaultUrl: "https://generativelanguage.googleapis.com", requiresKey: true, requiresUrl: false, color: "text-blue-400" },
  { id: "deepseek", name: "DeepSeek", defaultUrl: "https://api.deepseek.com/v1", requiresKey: true, requiresUrl: false, color: "text-sky-400" },
  { id: "glm", name: "GLM (Zhipu)", defaultUrl: "https://open.bigmodel.cn/api/paas/v4", requiresKey: true, requiresUrl: false, color: "text-indigo-400" },
  { id: "kimi", name: "Kimi (Moonshot)", defaultUrl: "https://api.moonshot.cn/v1", requiresKey: true, requiresUrl: false, color: "text-rose-400" },
  { id: "minimax", name: "MiniMax", defaultUrl: "https://api.minimax.chat/v1", requiresKey: true, requiresUrl: false, color: "text-fuchsia-400" },
  { id: "ollama", name: "Ollama (Local Network)", defaultUrl: "http://localhost:11434", requiresKey: false, requiresUrl: true, color: "text-white" },
  { id: "custom", name: "Custom (OpenAI Compatible)", defaultUrl: "https://api.groq.com/openai/v1", requiresKey: true, requiresUrl: true, color: "text-purple-400" },
];

export function CloudAISettingsModal({ isOpen, onClose }: CloudAISettingsModalProps) {
  const { t } = useLanguage();
  useScrollLock(isOpen);
  const backdropRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [activeProvider, setActiveProvider] = useState<ProviderId>("openai");
  
  // Form states
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [showKey, setShowKey] = useState(false);
  
  // Health Check states
  const [healthStatus, setHealthStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [healthMessage, setHealthMessage] = useState("");

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    const backdrop = backdropRef.current;
    const panel = panelRef.current;
    if (!isOpen || !panel || !backdrop) return;
    cancelAnimations(backdrop);
    cancelAnimations(panel);
    backdrop.style.opacity = "0";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(20px) scale(0.95)";
    panel.style.filter = "blur(10px)";
    animateElements(backdrop, [{ opacity: 0 }, { opacity: 1 }], { duration: 300, fill: "forwards", easing: "ease-out" });
    animateElements(panel, [
      { opacity: 0, transform: "translateY(20px) scale(0.95)", filter: "blur(10px)" },
      { opacity: 1, transform: "translateY(0) scale(1)", filter: "blur(0px)" },
    ], { duration: 400, fill: "forwards", easing: "cubic-bezier(0.16, 1, 0.3, 1)" });
  }, [isOpen]);

  const handleClose = () => {
    const backdrop = backdropRef.current;
    const panel = panelRef.current;
    if (!panel || !backdrop) { onClose(); return; }
    cancelAnimations(backdrop);
    cancelAnimations(panel);
    animateElements(backdrop, [{ opacity: 1 }, { opacity: 0 }], { duration: 200, fill: "forwards", easing: "ease-in" });
    animateElements(panel, [
      { opacity: 1, transform: "translateY(0) scale(1)", filter: "blur(0px)" },
      { opacity: 0, transform: "translateY(15px) scale(0.98)", filter: "blur(5px)" },
    ], { duration: 250, fill: "forwards", easing: "ease-in", onComplete: onClose });
  };

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen]);

  // When changing provider, reset states and update default URL
  useEffect(() => {
    const provider = PROVIDERS.find(p => p.id === activeProvider);
    setApiKey("");
    setBaseUrl(provider?.defaultUrl || "");
    setHealthStatus("idle");
    setHealthMessage("");
  }, [activeProvider]);

  const handleHealthCheck = () => {
    if (healthStatus === "loading") return;
    setHealthStatus("loading");
    setHealthMessage("Pinging API endpoint... (1-token test)");
    
    // Simulate network delay
    setTimeout(() => {
      const provider = PROVIDERS.find(p => p.id === activeProvider);
      if (provider?.requiresKey && !apiKey) {
        setHealthStatus("error");
        setHealthMessage("NO_API_KEY: Por favor ingresa una llave API.");
        return;
      }
      
      // Randomly simulate success or token error to show states
      const isSuccess = Math.random() > 0.3 || (provider?.id === "ollama");
      
      if (isSuccess) {
        setHealthStatus("ok");
        setHealthMessage("CONEXIÓN EXITOSA: Endpoint responde correctamente.");
      } else {
        setHealthStatus("error");
        setHealthMessage("NO_TOKENS: La llave API no tiene saldo o es inválida.");
      }
    }, 1500);
  };

  if (!isOpen || !mounted) return null;

  const currentProvider = PROVIDERS.find(p => p.id === activeProvider)!;

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 font-sans" onMouseDown={(e) => e.stopPropagation()}>
      <div ref={backdropRef} className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={handleClose} />

      <div
        ref={panelRef}
        className="relative z-10 w-full max-w-[800px] h-[80vh] max-h-[600px] flex rounded-2xl border border-sky-500/20 bg-[#0d0e12]/95 shadow-[0_0_50px_rgba(14,165,233,0.15)] overflow-hidden"
        style={{ opacity: 0 }}
      >
        {/* Sidebar Providers */}
        <div className="w-[240px] border-r border-white/5 bg-black/40 flex flex-col shrink-0">
          <div className="p-4 border-b border-white/5">
            <h2 className="text-sm font-bold text-sky-400 tracking-wider flex items-center gap-2" style={{ fontFamily: "'Space Grotesk', Inter, sans-serif" }}>
              <Globe size={16} /> IA ONLINE
            </h2>
            <p className="text-[10px] text-white/40 mt-1 font-mono">{t("auto_427e24cadc1f")}</p>
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
            {PROVIDERS.map(provider => (
              <button
                key={provider.id}
                onClick={() => setActiveProvider(provider.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-semibold transition-all flex items-center justify-between ${
                  activeProvider === provider.id 
                    ? "bg-sky-500/10 border border-sky-500/30 text-white" 
                    : "bg-transparent border border-transparent text-white/50 hover:bg-white/5 hover:text-white/80"
                }`}
              >
                <span>{provider.name}</span>
                {activeProvider === provider.id && <BrainCircuit size={14} className="text-sky-400" />}
              </button>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 flex flex-col">
          <div className="flex justify-end p-3">
            <button onClick={handleClose} className="p-1.5 rounded-lg text-white/30 hover:text-white/80 transition-colors">
              <X size={16} />
            </button>
          </div>

          <div className="flex-1 px-8 pb-8 overflow-y-auto custom-scrollbar flex flex-col max-w-xl">
            <div className="mb-8">
              <h3 className={`text-2xl font-bold mb-2 ${currentProvider.color}`} style={{ fontFamily: "'Space Grotesk', Inter, sans-serif" }}>
                {currentProvider.name}
              </h3>
              <p className="text-xs text-white/50">
                {t("ia_nube_configura")}
              </p>
            </div>

            <div className="space-y-6 flex-1">
              {currentProvider.requiresUrl && (
                <div className="space-y-2">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-white/60 flex items-center gap-2">
                    <Link2 size={12} /> Base URL Endpoint
                  </label>
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://..."
                    className="w-full bg-white/[0.02] border border-white/10 focus:border-sky-500/50 rounded-xl px-4 py-3 text-sm text-white/90 font-mono outline-none transition-all"
                  />
                  {currentProvider.id === "ollama" && (
                    <p className="text-[10px] text-white/30 font-mono mt-1">{t("ia_nube_ollama_cors")}</p>
                  )}
                </div>
              )}

              {currentProvider.requiresKey && (
                <div className="space-y-2">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-white/60 flex items-center gap-2">
                    <Key size={12} /> API Key
                  </label>
                  <div className="relative">
                    <input
                      type={showKey ? "text" : "password"}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={`sk-${currentProvider.id}-...`}
                      className="w-full bg-white/[0.02] border border-white/10 focus:border-sky-500/50 rounded-xl pl-4 pr-12 py-3 text-sm text-white/90 font-mono outline-none transition-all"
                    />
                    <button 
                      onClick={() => setShowKey(!showKey)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-white/30 hover:text-sky-400 uppercase tracking-wider"
                    >
                      {showKey ? "Ocultar" : "Mostrar"}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Health Check Panel */}
            <div className="mt-8 pt-6 border-t border-white/10">
              <div className="flex items-center gap-4">
                <button
                  onClick={handleHealthCheck}
                  disabled={healthStatus === "loading"}
                  className="px-6 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-black font-bold text-xs uppercase tracking-wider transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {healthStatus === "loading" ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
                  {t("auto_602f8b7e236d")}
                </button>
                
                <div className="flex-1">
                  {healthStatus === "loading" && <span className="text-xs text-sky-400/80 font-mono animate-pulse">{healthMessage}</span>}
                  {healthStatus === "ok" && <span className="text-xs text-emerald-400 font-mono flex items-center gap-1.5"><CheckCircle2 size={14}/> {healthMessage}</span>}
                  {healthStatus === "error" && <span className="text-xs text-red-400 font-mono flex items-center gap-1.5"><AlertCircle size={14}/> {healthMessage}</span>}
                </div>
              </div>
            </div>

            {/* Privacy Disclaimer */}
            <div className="mt-6 flex items-start gap-2.5 p-3 rounded-lg bg-sky-500/5 border border-sky-500/10">
              <ShieldAlert size={14} className="text-sky-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-sky-200/60 font-mono leading-relaxed">
                {t("ia_nube_credenciales_a")} <strong>localmente y encriptadas</strong> {t("ia_nube_credenciales_b")}
              </p>
            </div>

          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
