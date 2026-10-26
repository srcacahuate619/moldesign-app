"use client";

import React, { useState, useRef, useEffect } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import { X, Upload, Info, FileText, CheckCircle2, Zap, Layers, Package } from "lucide-react";
import { uploadCustomTarget } from "../../../lib/api";
import { invalidarCatalogo } from "../../../lib/catalogoDeReceptores";

interface CustomReceptorModalProps {
  onClose: () => void;
  onSuccess: () => void;
  /** Reutiliza la misma subida; el backend ya admite esta marca. */
  antiDiana?: boolean;
}

/**
 * Los tres caminos de la subida de un receptor propio. Cada uno es una promesa distinta de MolDesign:
 *
 *  - A, estructura cruda: la prepara y audita lo que cambió (experimental o predicha).
 *  - B, ya preparada por el equipo: se respeta su protonación, aguas, metales y cofactores.
 *  - C, PDBQT listo para Vina: se evalúa tal cual; con su estructura de origen, además, se audita.
 *
 * Las extensiones se comparan sin distinguir mayúsculas y admiten `.gz`: lo mismo que acepta el backend
 * (`services/targets/entrada_receptor.py`). Los errores que salen de la subida son los del backend, ya en el idioma
 * de la interfaz: se muestran tal cual.
 */
export type Camino = "A" | "B" | "C";

export const EXTENSIONES_ESTRUCTURA = [".pdb", ".ent", ".cif", ".mmcif"] as const;

export const CAMINOS: Record<Camino, { extensiones: readonly string[]; modo: "automatico" | "respetar" | "pdbqt"; curado: boolean }> = {
  A: { extensiones: EXTENSIONES_ESTRUCTURA, modo: "automatico", curado: false },
  B: { extensiones: [...EXTENSIONES_ESTRUCTURA, ".pqr"], modo: "respetar", curado: false },
  C: { extensiones: [".pdbqt"], modo: "pdbqt", curado: true },
};

/** La estructura de la que salió un PDBQT: la misma lista que el camino B. */
export const EXTENSIONES_ORIGEN = CAMINOS.B.extensiones;

/** ¿El nombre termina en una de las extensiones, con o sin `.gz`, sin distinguir mayúsculas? */
export function extensionAdmitida(nombre: string, extensiones: readonly string[]): boolean {
  let n = nombre.toLowerCase();
  if (n.endsWith(".gz")) n = n.slice(0, -3);
  return extensiones.some((e) => n.endsWith(e));
}

const aceptar = (extensiones: readonly string[]) => [...extensiones, ".gz"].join(",");

export function CustomReceptorModal({ onClose, onSuccess, antiDiana = false }: CustomReceptorModalProps) {
  const { t } = useLanguage();
  const [camino, setCamino] = useState<Camino>("A");
  const [file, setFile] = useState<File | null>(null);
  const [origen, setOrigen] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [chainId, setChainId] = useState("A");

  // Caja de búsqueda: opcional en A y B (si el archivo trae el ligando del cristal se detecta sola), obligatoria en C.
  const [gridX, setGridX] = useState("");
  const [gridY, setGridY] = useState("");
  const [gridZ, setGridZ] = useState("");
  const [gridSizeX, setGridSizeX] = useState("20.0");
  const [gridSizeY, setGridSizeY] = useState("20.0");
  const [gridSizeZ, setGridSizeZ] = useState("20.0");

  const [cofactors, setCofactors] = useState("");
  const [isCommunity, setIsCommunity] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const origenInputRef = useRef<HTMLInputElement>(null);

  const config = CAMINOS[camino];

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

  const elegirCamino = (nuevo: Camino) => {
    setCamino(nuevo);
    setError(null);
    // El archivo que ya no corresponde a este camino se descarta; el que sí corresponde se conserva.
    if (file && !extensionAdmitida(file.name, CAMINOS[nuevo].extensiones)) setFile(null);
    if (nuevo !== "C") setOrigen(null);
  };

  const rechazar = (nombre: string, extensiones: readonly string[]) =>
    setError(t("pr_rp_extension_invalida", { name: nombre, ext: extensiones.join(" ") }));

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (!extensionAdmitida(selected.name, config.extensiones)) {
      rechazar(selected.name, config.extensiones);
      e.target.value = "";
      return;
    }
    setError(null);
    setFile(selected);
  };

  const handleOrigenChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (!extensionAdmitida(selected.name, EXTENSIONES_ORIGEN)) {
      rechazar(selected.name, EXTENSIONES_ORIGEN);
      e.target.value = "";
      return;
    }
    setError(null);
    setOrigen(selected);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError(t("pr_rp_falta_archivo"));
      return;
    }
    if (!name.trim()) {
      setError(t("auto_4a460dbb24e9"));
      return;
    }
    const centro = [gridX, gridY, gridZ];
    const conCentro = centro.filter((v) => v !== "").length;
    if (camino === "C" && conCentro < 3) {
      setError(t("pr_rp_caja_obligatoria_falta"));
      return;
    }
    if (conCentro > 0 && conCentro < 3) {
      setError(t("pr_rp_caja_incompleta"));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (camino === "C" && origen) formData.append("source_file", origen);
      formData.append("name", name);
      formData.append("is_curated", config.curado ? "true" : "false");
      formData.append("modo_preparacion", config.modo);
      formData.append("chain_id", chainId.trim() || "A");

      if (conCentro === 3) {
        formData.append("grid_center_x", gridX);
        formData.append("grid_center_y", gridY);
        formData.append("grid_center_z", gridZ);
        formData.append("grid_size_x", gridSizeX);
        formData.append("grid_size_y", gridSizeY);
        formData.append("grid_size_z", gridSizeZ);
      }

      if (camino === "A" && cofactors) {
        formData.append("cofactors_whitelist", cofactors);
      }
      formData.append("is_community", isCommunity ? "true" : "false");
      if (antiDiana) formData.append("is_anti_target", "true");

      await uploadCustomTarget(formData);
      invalidarCatalogo();
      onSuccess();
    } catch (err: any) {
      setError(err.message || t("auto_67bfa12d71a2"));
    } finally {
      setLoading(false);
    }
  };

  const tarjetas: { id: Camino; icono: React.ReactNode; titulo: string; desc: string }[] = [
    { id: "A", icono: <Zap className="w-4 h-4 text-purple-400/80" />, titulo: t("pr_rp_a_titulo"), desc: t("pr_rp_a_desc") },
    { id: "B", icono: <Layers className="w-4 h-4 text-purple-400/80" />, titulo: t("pr_rp_b_titulo"), desc: t("pr_rp_b_desc") },
    { id: "C", icono: <Package className="w-4 h-4 text-purple-400/80" />, titulo: t("pr_rp_c_titulo"), desc: t("pr_rp_c_desc") },
  ];
  const puntos: Record<Camino, string[]> = {
    A: [t("pr_rp_a_punto1"), t("pr_rp_a_punto2"), t("pr_rp_a_punto3")],
    B: [t("pr_rp_b_punto1"), t("pr_rp_b_punto2"), t("pr_rp_b_punto3")],
    C: [t("pr_rp_c_punto1"), t("pr_rp_c_punto2")],
  };
  const clasesCampoCaja = "bg-black border border-zinc-800 rounded-xl px-3 py-2 text-white text-xs text-center outline-none focus:border-purple-500/40";

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
                {t(antiDiana ? "cat_anti_subir" : "pr_custom_receptor_title")}
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

          {/* Camino */}
          <div>
            <p id="rp-camino-etiqueta" className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
              {t("pr_rp_camino_titulo")}
            </p>
            <div role="radiogroup" aria-labelledby="rp-camino-etiqueta" className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {tarjetas.map((tarjeta) => (
                <button
                  key={tarjeta.id}
                  type="button"
                  role="radio"
                  aria-checked={camino === tarjeta.id}
                  data-camino={tarjeta.id}
                  onClick={() => elegirCamino(tarjeta.id)}
                  className={`text-left p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1.5 ${
                    camino === tarjeta.id
                      ? "bg-zinc-900 border-purple-500/40 text-purple-200 shadow-sm"
                      : "bg-black border-zinc-800 text-zinc-400 hover:text-white"
                  }`}
                >
                  <span className="flex items-center gap-2 font-mono text-xs font-bold uppercase">
                    {tarjeta.icono}
                    {tarjeta.titulo}
                  </span>
                  <span className="text-[11px] leading-relaxed font-normal normal-case">{tarjeta.desc}</span>
                  <span className="text-[11px] text-zinc-500 normal-case">{CAMINOS[tarjeta.id].extensiones.join(" ")}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Qué hace este camino */}
          <div className="bg-purple-950/20 border border-purple-500/20 p-4 rounded-xl flex gap-3 text-purple-300/90 text-xs leading-relaxed">
            <Info className="w-4 h-4 shrink-0 mt-0.5 text-purple-400" />
            <ul className="list-disc pl-4 space-y-1" data-testid="rp-puntos">
              {puntos[camino].map((punto) => (
                <li key={punto}>{punto}</li>
              ))}
            </ul>
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
                  placeholder={t("pr_custom_name_placeholder")}
                  className="w-full bg-black border border-zinc-800 rounded-xl px-3.5 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-purple-500/40 transition-all"
                />
              </div>

              <div>
                <label htmlFor="rp-cadena" className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                  {t("pr_custom_chain_to_evaluate")}
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
                <input
                  id="rp-cadena"
                  type="text"
                  value={chainId}
                  maxLength={8}
                  onChange={e => setChainId(e.target.value)}
                  placeholder={t("pr_rp_cadena_otra")}
                  className="mt-2 w-full bg-black border border-zinc-800 rounded-xl px-3.5 py-2 text-white font-mono text-xs focus:outline-none focus:border-purple-500/40 transition-all"
                />
                <p className="mt-1 text-[11px] text-zinc-500 leading-relaxed">{t("pr_rp_cadena_nota")}</p>
              </div>

              {camino === "A" && (
                <div>
                  <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                    {t("pr_custom_cofactors_optional")}
                  </label>
                  <input
                    type="text"
                    value={cofactors}
                    onChange={e => setCofactors(e.target.value)}
                    placeholder={t("auto_4dfb289b81ba")}
                    className="w-full bg-black border border-zinc-800 rounded-xl px-3.5 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-purple-500/40 transition-all"
                  />
                </div>
              )}
            </div>

            {/* Archivos y caja */}
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">{t("pr_rp_archivo")}</label>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept={aceptar(config.extensiones)}
                  onChange={handleFileChange}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-zinc-800 bg-black text-xs text-zinc-300 hover:text-white hover:border-purple-500/30 transition-colors cursor-pointer text-left"
                >
                  <FileText className="w-4 h-4 shrink-0 text-purple-400" />
                  <span className="truncate">{file ? file.name : t("pr_rp_sin_archivo")}</span>
                  <span className="ml-auto shrink-0 text-purple-300">{t("pr_rp_elegir_archivo")}</span>
                </button>
                <p className="mt-1 text-[11px] text-zinc-500 leading-relaxed">
                  {t("pr_rp_extensiones", { ext: config.extensiones.join(" ") })} · {t("pr_rp_tambien_gz")}
                </p>
              </div>

              {camino === "C" && (
                <div>
                  <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">{t("pr_rp_origen")}</label>
                  <input
                    type="file"
                    ref={origenInputRef}
                    data-testid="rp-origen"
                    accept={aceptar(EXTENSIONES_ORIGEN)}
                    onChange={handleOrigenChange}
                    className="hidden"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => origenInputRef.current?.click()}
                      className="flex-1 flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-zinc-800 bg-black text-xs text-zinc-300 hover:text-white hover:border-purple-500/30 transition-colors cursor-pointer text-left"
                    >
                      <FileText className="w-4 h-4 shrink-0 text-purple-400" />
                      <span className="truncate">{origen ? origen.name : t("pr_rp_sin_archivo")}</span>
                    </button>
                    {origen && (
                      <button
                        type="button"
                        onClick={() => { setOrigen(null); if (origenInputRef.current) origenInputRef.current.value = ""; }}
                        className="px-3 rounded-xl border border-zinc-800 text-xs text-zinc-400 hover:text-white cursor-pointer"
                      >
                        {t("pr_rp_origen_quitar")}
                      </button>
                    )}
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-500 leading-relaxed">
                    {t("pr_rp_origen_nota")} {t("pr_rp_extensiones", { ext: EXTENSIONES_ORIGEN.join(" ") })}
                  </p>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold uppercase text-zinc-400 mb-1.5">
                  {camino === "C" ? t("pr_rp_caja_obligatoria") : t("pr_rp_caja_opcional")}
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <input type="number" step="0.1" placeholder="X" aria-label="X" value={gridX} onChange={e => setGridX(e.target.value)} className={clasesCampoCaja} />
                  <input type="number" step="0.1" placeholder="Y" aria-label="Y" value={gridY} onChange={e => setGridY(e.target.value)} className={clasesCampoCaja} />
                  <input type="number" step="0.1" placeholder="Z" aria-label="Z" value={gridZ} onChange={e => setGridZ(e.target.value)} className={clasesCampoCaja} />
                </div>
                <label className="block text-xs font-bold uppercase text-zinc-400 mt-3 mb-1.5">
                  {t("pr_tamano_caja")}
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <input type="number" step="0.1" placeholder={t("pr_custom_grid_size_x")} value={gridSizeX} onChange={e => setGridSizeX(e.target.value)} className={clasesCampoCaja} />
                  <input type="number" step="0.1" placeholder={t("pr_custom_grid_size_y")} value={gridSizeY} onChange={e => setGridSizeY(e.target.value)} className={clasesCampoCaja} />
                  <input type="number" step="0.1" placeholder={t("pr_custom_grid_size_z")} value={gridSizeZ} onChange={e => setGridSizeZ(e.target.value)} className={clasesCampoCaja} />
                </div>
              </div>

              {error && (
                <div role="alert" className="bg-red-950/40 border border-red-500/30 text-red-300 p-3 rounded-xl text-xs flex items-start gap-2">
                  <Info className="w-4 h-4 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{error}</span>
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
                {t("c_cancelar")}
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2.5 rounded-xl font-bold uppercase text-xs bg-zinc-900 hover:bg-zinc-800 text-purple-300 hover:text-white border border-purple-500/30 transition-colors flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <span>{t("pr_custom_processing")}</span>
                ) : (
                  <>
                    {file ? <CheckCircle2 className="w-4 h-4 text-purple-400" /> : <Upload className="w-4 h-4 text-purple-400" />}
                    {file ? t("pr_custom_process_file", { name: file.name.substring(0, 15) }) : t("pr_custom_select_file")}
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
