"use client";
import { useScrollLock } from "@/hooks/useScrollLock";

import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { animateElements, cancelAnimations } from "@/lib/webAnimation";
import {
  X, Brain, HardDrive, DownloadCloud, Activity, Cpu, Settings2, FolderOpen, Trash2, Search, Download, CheckCircle2, AlertCircle, Zap, Thermometer, Box, Hash
} from "lucide-react";

type TabId = "dashboard" | "library" | "hub";

interface LocalAISettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function LocalAISettingsModal({ isOpen, onClose }: LocalAISettingsModalProps) {
  useScrollLock(isOpen);
  const backdropRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");

  // Mock states
  const [gpuLayers, setGpuLayers] = useState(14);
  const [keepLoaded, setKeepLoaded] = useState(true);
  const [aggressiveUnload, setAggressiveUnload] = useState(false);
  const [engine, setEngine] = useState("auto");
  const [contextSize, setContextSize] = useState("8192");
  const [cpuThreads, setCpuThreads] = useState(8);
  const [temperature, setTemperature] = useState(0.2);
  
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadingModel, setDownloadingModel] = useState<string | null>(null);

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

  const handleSimulateDownload = (modelName: string) => {
    if (isDownloading) return;
    setIsDownloading(true);
    setDownloadingModel(modelName);
    setDownloadProgress(0);
    
    // Simulate download progress
    const interval = setInterval(() => {
      setDownloadProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(() => {
            setIsDownloading(false);
            setDownloadingModel(null);
          }, 1000);
          return 100;
        }
        return prev + Math.floor(Math.random() * 15);
      });
    }, 400);
  };

  const handleLocalFileSelect = () => {
    // Mocking file selection dialog
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".gguf";
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) alert(`Simulando carga del modelo: ${file.name}`);
    };
    input.click();
  };

  if (!isOpen || !mounted) return null;

  const renderDashboard = () => (
    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300 h-full flex flex-col overflow-y-auto custom-scrollbar pr-2 pb-4">
      <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 relative overflow-hidden group shrink-0">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-500 to-emerald-400 opacity-50" />
        <div className="flex items-start justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400/80 mb-1 block">Modelo Activo</span>
            <h3 className="text-lg font-bold text-white/90" style={{ fontFamily: "'Space Grotesk', Inter, sans-serif" }}>
              Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
            </h3>
            <p className="text-xs text-white/40 mt-1 font-mono">1.04 GB · 28 Capas · Contexto 16K</p>
          </div>
          <div className="px-2.5 py-1 rounded border border-emerald-500/20 bg-emerald-500/10 flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] font-mono text-emerald-300">Cargado</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 shrink-0">
        <div className="p-4 rounded-xl bg-[#0a0b0f] border border-white/5">
          <div className="flex items-center gap-2 mb-4">
            <Cpu size={14} className="text-purple-400" />
            <span className="text-xs font-semibold text-white/70 uppercase tracking-widest">Asignación GPU (VRAM)</span>
          </div>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-[10px] font-mono mb-1">
                <span className="text-white/40">Uso VRAM Estimado</span>
                <span className="text-purple-300">1.5 GB / 8.0 GB</span>
              </div>
              <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden flex">
                <div className="h-full bg-purple-500 w-[18%] transition-all" />
              </div>
            </div>
            
            <div className="pt-2 border-t border-white/5">
              <div className="flex justify-between text-xs mb-2">
                <span className="text-white/60">Capas en GPU (Offload)</span>
                <span className="font-mono text-white/90">{gpuLayers} / 28</span>
              </div>
              <input 
                type="range" 
                min="0" max="28" 
                value={gpuLayers} 
                onChange={(e) => setGpuLayers(parseInt(e.target.value))}
                className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
                style={{ accentColor: "#a78bfa" }}
              />
            </div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#0a0b0f] border border-white/5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Activity size={14} className="text-blue-400" />
              <span className="text-xs font-semibold text-white/70 uppercase tracking-widest">Memoria Sistema (RAM)</span>
            </div>
            <div>
              <div className="flex justify-between text-[10px] font-mono mb-1">
                <span className="text-white/40">Uso Actual Sistema</span>
                <span className="text-blue-300">12.4 GB / 32.0 GB</span>
              </div>
              <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden flex">
                <div className="h-full bg-blue-500 w-[38%] transition-all" />
              </div>
            </div>
          </div>
          
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-white/5 cursor-pointer hover:bg-white/[0.04] transition-colors" onClick={() => setKeepLoaded(!keepLoaded)}>
              <div className="flex items-center gap-2">
                <Settings2 size={13} className="text-white/50" />
                <span className="text-[10px] text-white/70">Mantener en Pipeline</span>
              </div>
              <div className={`w-7 h-3.5 rounded-full border transition-colors flex items-center px-0.5 ${keepLoaded ? "bg-purple-500/20 border-purple-500/40 justify-end" : "bg-white/5 border-white/10 justify-start"}`}>
                <div className={`w-2.5 h-2.5 rounded-full ${keepLoaded ? "bg-purple-400" : "bg-white/40"}`} />
              </div>
            </div>
            
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-red-500/10 cursor-pointer hover:bg-red-500/5 transition-colors" onClick={() => setAggressiveUnload(!aggressiveUnload)}>
              <div className="flex items-center gap-2">
                <AlertCircle size={13} className={aggressiveUnload ? "text-red-400" : "text-white/40"} />
                <span className={`text-[10px] ${aggressiveUnload ? "text-red-300" : "text-white/60"}`}>Descarga Agresiva</span>
              </div>
              <div className={`w-7 h-3.5 rounded-full border transition-colors flex items-center px-0.5 ${aggressiveUnload ? "bg-red-500/20 border-red-500/40 justify-end" : "bg-white/5 border-white/10 justify-start"}`}>
                <div className={`w-2.5 h-2.5 rounded-full ${aggressiveUnload ? "bg-red-400" : "bg-white/40"}`} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced Settings */}
      <div className="grid grid-cols-2 gap-3 shrink-0">
        <div className="p-4 rounded-xl bg-white/[0.01] border border-white/5 space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={14} className="text-amber-400" />
            <span className="text-xs font-semibold text-white/70 uppercase tracking-widest">Motor & Contexto</span>
          </div>
          
          <div>
            <span className="text-[10px] text-white/50 block mb-1">Hardware Engine</span>
            <div className="grid grid-cols-3 gap-1 p-1 bg-black/40 rounded-lg border border-white/5">
              {['auto', 'cuda', 'cpu'].map(e => (
                <button 
                  key={e}
                  onClick={() => setEngine(e)}
                  className={`text-[10px] py-1 rounded-md capitalize font-mono transition-colors ${engine === e ? 'bg-amber-500/20 text-amber-300 border border-amber-500/20' : 'text-white/40 hover:text-white/80'}`}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          <div>
            <span className="text-[10px] text-white/50 block mb-1">Context Window (Tokens)</span>
            <select 
              value={contextSize} 
              onChange={(e) => setContextSize(e.target.value)}
              className="w-full bg-black/40 border border-white/5 rounded-lg p-1.5 text-[11px] font-mono text-white/80 outline-none"
            >
              <option value="4096">4K (Bajo consumo)</option>
              <option value="8192">8K (Recomendado)</option>
              <option value="16384">16K (Consumo alto)</option>
              <option value="32768">32K (Experimental)</option>
            </select>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white/[0.01] border border-white/5 space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Settings2 size={14} className="text-white/60" />
            <span className="text-xs font-semibold text-white/70 uppercase tracking-widest">Ajustes Base</span>
          </div>

          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-white/50 flex items-center gap-1"><Hash size={10}/> CPU Threads</span>
              <span className="font-mono text-white/80">{cpuThreads} / 16</span>
            </div>
            <input 
              type="range" min="1" max="16" value={cpuThreads} 
              onChange={(e) => setCpuThreads(parseInt(e.target.value))}
              className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
              style={{ accentColor: "#a78bfa" }}
            />
          </div>

          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-white/50 flex items-center gap-1"><Thermometer size={10}/> Temperatura</span>
              <span className="font-mono text-white/80">{temperature.toFixed(2)}</span>
            </div>
            <input 
              type="range" min="0" max="1" step="0.05" value={temperature} 
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
              style={{ accentColor: "#f87171" }}
            />
            <span className="text-[9px] text-white/30 mt-1 block">0 = Analítico (Química), 1 = Creativo</span>
          </div>
        </div>
      </div>
    </div>
  );

  const renderLibrary = () => (
    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300 h-full flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-white/70 uppercase tracking-widest">Modelos Instalados (.gguf)</h3>
        <button 
          onClick={handleLocalFileSelect}
          className="flex items-center gap-2 px-3 py-1.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300 text-[11px] hover:bg-purple-500/20 transition-colors"
        >
          <FolderOpen size={12} />
          <span>Importar GGUF Local</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-2">
        {[
          { name: "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf", size: "1.04 GB", active: true },
          { name: "Phi-3-mini-4k-instruct-q4.gguf", size: "2.30 GB", active: false },
          { name: "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf", size: "4.92 GB", active: false }
        ].map(model => (
          <div key={model.name} className={`flex items-center justify-between p-3 rounded-lg border transition-all ${model.active ? "bg-purple-500/5 border-purple-500/30" : "bg-white/[0.02] border-white/5 hover:border-white/10"}`}>
            <div className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${model.active ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]" : "bg-white/20"}`} />
              <div>
                <p className={`text-sm font-medium font-sans ${model.active ? "text-purple-300" : "text-white/80"}`}>{model.name}</p>
                <p className="text-[10px] font-mono text-white/40 mt-0.5">{model.size}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {!model.active && (
                <button className="px-3 py-1 rounded border border-white/10 bg-white/5 text-xs text-white/70 hover:bg-white/10 transition-colors">
                  Cargar
                </button>
              )}
              <button className="p-1.5 rounded border border-white/5 bg-transparent text-white/20 hover:text-red-400 hover:border-red-400/30 transition-colors" title="Eliminar modelo">
                <Trash2 size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderHub = () => (
    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300 h-full flex flex-col">
      <div className="flex items-center gap-3 p-3 rounded-xl bg-black/40 border border-white/10 focus-within:border-purple-500/40 transition-colors">
        <Search size={15} className="text-white/30" />
        <input 
          type="text" 
          placeholder="Buscar modelos en HuggingFace (ej. mistral, qwen, llama-3)..." 
          className="bg-transparent border-none outline-none text-xs text-white/90 w-full placeholder-white/30 font-sans"
        />
      </div>

      <div className="grid grid-cols-2 gap-3 flex-1 overflow-y-auto custom-scrollbar pr-2 pb-2">
        {[
          { id: "Qwen/Qwen2.5-3B-Instruct-GGUF", tags: ["3B", "Chat", "Code"], size: "2.1 GB", rec: true },
          { id: "microsoft/Phi-3-mini-4k-GGUF", tags: ["3.8B", "Fast", "Logic"], size: "2.3 GB", rec: true },
          { id: "MaziyarPanahi/Llama-3-8B-Instruct-GGUF", tags: ["8B", "General", "High VRAM"], size: "4.9 GB", rec: false },
          { id: "NousResearch/Hermes-2-Pro-Llama-3-8B-GGUF", tags: ["8B", "Roleplay", "Tool Use"], size: "4.9 GB", rec: false },
        ].map(model => (
          <div key={model.id} className="p-4 rounded-xl bg-white/[0.02] border border-white/5 hover:border-white/15 transition-all flex flex-col relative overflow-hidden group">
            {model.rec && (
              <div className="absolute top-0 right-0 px-2 py-0.5 bg-emerald-500/20 border-b border-l border-emerald-500/30 rounded-bl-lg">
                <span className="text-[8px] font-bold uppercase tracking-wider text-emerald-300">Recomendado</span>
              </div>
            )}
            <h4 className="text-[13px] font-bold text-white/90 break-words pr-12 font-sans">{model.id.split('/')[1]}</h4>
            <p className="text-[10px] text-white/40 mt-1 font-mono">{model.id.split('/')[0]}</p>
            
            <div className="flex flex-wrap gap-1.5 mt-3 mb-4">
              {model.tags.map(tag => (
                <span key={tag} className="px-1.5 py-0.5 rounded-md border border-white/10 bg-white/5 text-[9px] font-mono text-white/50">{tag}</span>
              ))}
            </div>

            <div className="mt-auto pt-3 border-t border-white/5 flex items-center justify-between">
              <span className="text-[11px] font-mono text-white/40">{model.size} (Q4_K_M)</span>
              
              {isDownloading && downloadingModel === model.id ? (
                <div className="w-1/2 h-1 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-400 transition-all duration-300" style={{ width: `${downloadProgress}%` }} />
                </div>
              ) : (
                <button 
                  onClick={() => handleSimulateDownload(model.id)}
                  className="p-1.5 rounded border border-purple-500/30 bg-purple-500/10 text-purple-300 hover:bg-purple-500/20 transition-colors" 
                  title="Descargar GGUF"
                >
                  <DownloadCloud size={13} strokeWidth={2} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 font-sans" onMouseDown={(e) => e.stopPropagation()}>
      <div ref={backdropRef} className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={handleClose} />

      <div
        ref={panelRef}
        className="relative z-10 w-full max-w-[700px] h-[80vh] max-h-[550px] flex flex-col rounded-2xl border border-white/10 bg-[#0d0e12]/95 shadow-[0_0_40px_rgba(0,0,0,0.5)] overflow-hidden"
        style={{ opacity: 0 }}
      >
        {/* Header Tabs */}
        <div className="flex items-end justify-between px-2 pt-2 border-b border-white/10 bg-black/20 shrink-0">
          <div className="flex items-center gap-1">
            <TabButton 
              id="dashboard" active={activeTab === "dashboard"} onClick={() => setActiveTab("dashboard")} 
              icon={<Activity size={14} />} label="Estado & Recursos" 
            />
            <TabButton 
              id="library" active={activeTab === "library"} onClick={() => setActiveTab("library")} 
              icon={<HardDrive size={14} />} label="Biblioteca Local" 
            />
            <TabButton 
              id="hub" active={activeTab === "hub"} onClick={() => setActiveTab("hub")} 
              icon={<DownloadCloud size={14} />} label="HuggingFace Hub" 
            />
          </div>
          <button onClick={handleClose} className="p-2 mb-1.5 mr-2 rounded-lg text-white/30 hover:text-white/80 transition-colors">
            <X size={15} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 overflow-hidden">
          {activeTab === "dashboard" && renderDashboard()}
          {activeTab === "library" && renderLibrary()}
          {activeTab === "hub" && renderHub()}
        </div>

      </div>
    </div>,
    document.body
  );
}

function TabButton({ id, active, onClick, icon, label }: { id: string, active: boolean, onClick: () => void, icon: React.ReactNode, label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-3 rounded-t-lg text-xs font-semibold uppercase tracking-wider transition-all duration-200 border-b-2 ${
        active 
          ? "border-purple-400 text-purple-300 bg-white/[0.03]" 
          : "border-transparent text-white/40 hover:text-white/70 hover:bg-white/[0.02]"
      }`}
    >
      <span className={active ? "text-purple-400" : "text-white/30"}>{icon}</span>
      <span style={{ fontFamily: "'Space Grotesk', Inter, sans-serif" }}>{label}</span>
    </button>
  );
}
