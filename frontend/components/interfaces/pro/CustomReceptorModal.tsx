"use client";

import React, { useState, useRef, useEffect } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import { X, Upload, Info, FileText, CheckCircle2, Zap } from "lucide-react";
import { uploadCustomTarget } from "../../../lib/api";

interface CustomReceptorModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export function CustomReceptorModal({ onClose, onSuccess }: CustomReceptorModalProps) {
  const { t } = useLanguage();
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [chainId, setChainId] = useState("A");
  
  // Manual coords
  const [gridX, setGridX] = useState("");
  const [gridY, setGridY] = useState("");
  const [gridZ, setGridZ] = useState("");
  
  // Manual size
  const [gridSizeX, setGridSizeX] = useState("20.0");
  const [gridSizeY, setGridSizeY] = useState("20.0");
  const [gridSizeZ, setGridSizeZ] = useState("20.0");
  
  // Cofactors
  const [cofactors, setCofactors] = useState("");
  const [isCommunity, setIsCommunity] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [loading, onClose]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      const ext = selected.name.split(".").pop()?.toLowerCase();
      const allowed = mode === "manual" ? ["pdbqt"] : ["pdb"];
      if (!allowed.includes(ext || "")) {
        setError(`Archivo inválido. Se esperaba .${allowed.join(" o .")} para el modo seleccionado.`);
        e.target.value = "";
        return;
      }
      setError(null);
      setFile(selected);
    }
  };

  const pendingSubmitRef = useRef(false);

  useEffect(() => {
    if (pendingSubmitRef.current && file) {
      pendingSubmitRef.current = false;
      const syntheticEvent = { preventDefault: () => {} } as React.FormEvent;
      handleSubmit(syntheticEvent);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      pendingSubmitRef.current = true;
      fileInputRef.current?.click();
      return;
    }
    if (!name.trim()) {
      setError("Por favor, dale un nombre a tu receptor.");
      return;
    }
    if (mode === "manual" && (!gridX || !gridY || !gridZ)) {
      setError("En modo manual debes proveer las coordenadas (X, Y, Z) del centro del sitio activo.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", name);
      formData.append("is_curated", mode === "manual" ? "true" : "false");
      formData.append("chain_id", chainId);
      
      if (gridX && gridY && gridZ) {
        formData.append("grid_center_x", gridX);
        formData.append("grid_center_y", gridY);
        formData.append("grid_center_z", gridZ);
      }
      
      if (mode === "manual" && gridSizeX && gridSizeY && gridSizeZ) {
        formData.append("grid_size_x", gridSizeX);
        formData.append("grid_size_y", gridSizeY);
        formData.append("grid_size_z", gridSizeZ);
      }
      
      if (cofactors) {
        formData.append("cofactors_whitelist", cofactors);
      }
      formData.append("is_community", isCommunity ? "true" : "false");

      await uploadCustomTarget(formData);
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Ocurrió un error inesperado al subir el receptor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-xl animate-in fade-in duration-300 overflow-hidden" role="presentation">
      
      {/* Modal Window con Soft Glassglow Shadow */}
      <div className="relative w-full max-w-3xl bg-zinc-950/95 border border-purple-500/20 rounded-2xl shadow-[0_0_40px_-15px_rgba(168,85,247,0.18)] backdrop-blur-2xl flex flex-col max-h-[88vh] overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="custom-receptor-title">
        
        {/* Header */}
        <div className="relative flex items-center justify-between p-5 border-b border-zinc-800 bg-black/60">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-300">
              <Upload size={18} />
            </div>
            <div>
              <h2 id="custom-receptor-title" className="text-base font-mono font-bold text-white uppercase tracking-wider">
                Subir Receptor Personalizado
              </h2>
              <p className="text-xs font-mono text-zinc-400 mt-0.5">
                {t("pr_receptor_intro")}
              </p>
            </div>
          </div>
          <button 
            type="button"
            onClick={onClose}
            aria-label={t("pr_cerrar_subida")}
            className="p-2 text-zinc-400 hover:text-white bg-zinc-900 hover:bg-zinc-800 rounded-xl border border-zinc-800 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6 overflow-y-auto flex-1 font-mono">
          
          {/* Mode Selector */}
          <div className="flex bg-black p-1 rounded-xl border border-zinc-800 gap-1">
            <button
              type="button"
              onClick={() => setMode("auto")}
              className={`flex-1 py-2.5 px-3 rounded-lg flex items-center justify-center gap-2 font-mono text-xs font-bold uppercase transition-all cursor-pointer ${
                mode === "auto" 
                  ? "bg-zinc-900 border border-purple-500/30 text-purple-300 shadow-sm" 
                  : "bg-transparent text-zinc-400 hover:text-white"
              }`}
            >
              <Zap className="w-4 h-4 text-purple-400/80" />
              {t("pr_modo_automatico")}
            </button>
            <button
              type="button"
              onClick={() => setMode("manual")}
              className={`flex-1 py-2.5 px-3 rounded-lg flex items-center justify-center gap-2 font-mono text-xs font-bold uppercase transition-all cursor-pointer ${
                mode === "manual" 
                  ? "bg-zinc-900 border border-purple-500/30 text-purple-300 shadow-sm" 
                  : "bg-transparent text-zinc-400 hover:text-white"
              }`}
            >
              <CheckCircle2 className="w-4 h-4 text-purple-400/80" />
              Modo Manual (.PDBQT)
            </button>
          </div>

          {/* Mode Instructions */}
          <div className="bg-purple-950/20 border border-purple-500/20 p-4 rounded-xl flex gap-3 text-purple-300/90 text-xs leading-relaxed">
            <Info className="w-4 h-4 shrink-0 mt-0.5 text-purple-400" />
            <div>
              {mode === "auto" ? (
                <ul className="list-disc pl-4 space-y-1">
                  <li>{t("pr_sube_archivo")} <b>.pdb</b> {t("pr_por_ejemplo_rcsb")}</li>
                  <li>{t("pr_pipeline_filtrara")}</li>
                  <li>{t("pr_se_autodescubrira")} <b>Sitio Activo</b> {t("pr_basado_cocristal")}</li>
                </ul>
              ) : (
                <ul className="list-disc pl-4 space-y-1">
                  <li>{t("pr_sube_archivo")} <b>.pdbqt</b> {t("pr_ya_preparado")}</li>
                  <li>{t("pr_no_modificaremos")}</li>
                  <li>Es <b>obligatorio</b> {t("pr_indicar_coordenadas")}</li>
                </ul>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* General Settings */}
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                  {t("pr_nombre_receptor")}
                </label>
                <input 
                  type="text" 
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Ej. Mi Quinasa Mutante"
                  className="w-full bg-black border border-zinc-800 rounded-xl px-3.5 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-purple-500/40 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                  Cadena a Evaluar
                </label>
                <div className="flex gap-1 bg-black p-1 rounded-xl border border-zinc-800">
                  {["A", "B", "C", "D"].map((chain) => (
                    <button
                      key={chain}
                      type="button"
                      onClick={() => setChainId(chain)}
                      className={`flex-1 py-1.5 font-mono text-xs font-bold rounded transition-colors cursor-pointer ${
                        chainId === chain
                          ? "bg-zinc-900 border border-purple-500/30 text-purple-300"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      {chain}
                    </button>
                  ))}
                </div>
              </div>

              {mode === "auto" && (
                <div>
                  <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                    Cofactores a mantener (Opcional)
                  </label>
                  <input 
                    type="text" 
                    value={cofactors}
                    onChange={e => setCofactors(e.target.value)}
                    placeholder="Ej. HEM, ZN, MG"
                    className="w-full bg-black border border-zinc-800 rounded-xl px-3.5 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-purple-500/40 transition-all"
                  />
                </div>
              )}
            </div>

            {/* Grid Box Settings */}
            <div className="space-y-4">
              <input 
                type="file" 
                ref={fileInputRef}
                accept={mode === "auto" ? ".pdb" : ".pdbqt"} 
                onChange={handleFileChange}
                className="hidden" 
              />
              
              {mode === "manual" ? (
                <>
                  <div>
                    <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                      Coordenadas Centro (Grid Box)
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      <input type="number" step="0.1" placeholder="X" value={gridX} onChange={e => setGridX(e.target.value)} className="bg-black border border-zinc-800 rounded-xl px-3 py-2 text-white text-xs text-center outline-none focus:border-purple-500/40" />
                      <input type="number" step="0.1" placeholder="Y" value={gridY} onChange={e => setGridY(e.target.value)} className="bg-black border border-zinc-800 rounded-xl px-3 py-2 text-white text-xs text-center outline-none focus:border-purple-500/40" />
                      <input type="number" step="0.1" placeholder="Z" value={gridZ} onChange={e => setGridZ(e.target.value)} className="bg-black border border-zinc-800 rounded-xl px-3 py-2 text-white text-xs text-center outline-none focus:border-purple-500/40" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                      {t("pr_tamano_caja")}
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      <input type="number" step="0.1" placeholder="SX" value={gridSizeX} onChange={e => setGridSizeX(e.target.value)} className="bg-black border border-zinc-800 rounded-xl px-3 py-2 text-white text-xs text-center outline-none focus:border-purple-500/40" />
                      <input type="number" step="0.1" placeholder="SY" value={gridSizeY} onChange={e => setGridSizeY(e.target.value)} className="bg-black border border-zinc-800 rounded-xl px-3 py-2 text-white text-xs text-center outline-none focus:border-purple-500/40" />
                      <input type="number" step="0.1" placeholder="SZ" value={gridSizeZ} onChange={e => setGridSizeZ(e.target.value)} className="bg-black border border-zinc-800 rounded-xl px-3 py-2 text-white text-xs text-center outline-none focus:border-purple-500/40" />
                    </div>
                  </div>
                </>
              ) : (
                <div className="bg-black border border-zinc-800 rounded-xl p-4 space-y-1">
                  <h4 className="text-xs font-bold uppercase text-purple-300">{t("pr_automatizacion")}</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    {t("pr_servidor_rastreara")}
                  </p>
                </div>
              )}
              
              {error && (
                <div className="bg-red-950/40 border border-red-500/30 text-red-300 p-3 rounded-xl text-xs flex items-center gap-2">
                  <Info className="w-4 h-4 shrink-0" />
                  {error}
                </div>
              )}
            </div>

          </div>

          {/* Unified Footer */}
          <div className="pt-4 border-t border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <input 
                type="checkbox" 
                id="share_community"
                checked={isCommunity}
                onChange={e => setIsCommunity(e.target.checked)}
                className="w-4 h-4 accent-purple-500 rounded cursor-pointer"
              />
              <label htmlFor="share_community" className="text-xs font-bold uppercase text-zinc-300 cursor-pointer">
                {t("pr_compartir_comunidad")}
              </label>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button 
                type="button"
                onClick={onClose}
                disabled={loading}
                className="px-5 py-2 rounded-xl text-xs font-bold uppercase border border-zinc-800 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                Cancelar
              </button>
              <button 
                type="submit"
                disabled={loading}
                className="px-6 py-2.5 rounded-xl font-bold uppercase text-xs bg-zinc-900 hover:bg-zinc-800 text-purple-300 hover:text-white border border-purple-500/30 transition-colors flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <span>Procesando...</span>
                ) : (
                  <>
                    {file ? <CheckCircle2 className="w-4 h-4 text-purple-400" /> : <Upload className="w-4 h-4 text-purple-400" />}
                    {file ? `Procesar: ${file.name.substring(0, 15)}...` : "Seleccionar Archivo"}
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

      </div>
    </div>
  );
}
