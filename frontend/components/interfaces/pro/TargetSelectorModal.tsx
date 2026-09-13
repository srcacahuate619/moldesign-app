"use client";
import { useScrollLock } from "@/hooks/useScrollLock";

import React, { useState, useMemo, useEffect, useRef } from "react";
import { X, Search, Database, Fingerprint, Activity, Crosshair, Upload, Globe, User, ShieldCheck, Sparkles, FlaskConical, AlertTriangle, Loader2 } from "lucide-react";
import type { Target } from "../../../lib/api";
import { shareCustomTarget } from "../../../lib/api";
import { groupTargets, readClassificationMode, writeClassificationMode } from "../../../lib/targetGrouping";
import { ChipsDelSitio } from "../../science/ChipsDelSitio";
import type { ClassificationMode } from "../../../lib/targetGrouping";
import { CustomReceptorModal } from "./CustomReceptorModal";
import { ReceptorVariantModal } from "./ReceptorVariantModal";

interface TargetSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  targets: Target[];
  onSelect: (pdbId: string) => void;
  selectedTargetId: string | null;
  onTargetUploadSuccess?: () => void;
}

function calibrationLabel(status?: string): string {
  switch (status) {
    case "listo": return "Listo";
    case "revisar": return "Revisar";
    default: return "Sin datos";
  }
}

function calibrationTooltip(status?: string, nHotspots: number = 0): string {
  switch (status) {
    case "listo":
      return `Listo para docking: grid box calibrado y ${nHotspots} residuos del sitio activo identificados.`;
    case "revisar":
      return `Requiere revisión: grid box presente pero pocos residuos del sitio activo (${nHotspots}). El ligando de referencia puede no ser un fármaco.`;
    default:
      return "Sin datos de calibración: el receptor no está preparado o no tiene sitio activo identificado.";
  }
}

export default function TargetSelectorModal({
  isOpen,
  onClose,
  targets,
  onSelect,
  selectedTargetId,
  onTargetUploadSuccess
}: TargetSelectorModalProps) {
  useScrollLock(isOpen);
  const [searchTerm, setSearchTerm] = useState("");
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [variantBase, setVariantBase] = useState<Target | null>(null);
  const [activeTab, setActiveTab] = useState<"oficiales" | "propios" | "comunidad">("oficiales");
  const [sharingTargetId, setSharingTargetId] = useState<string | null>(null);
  const [shareFeedback, setShareFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  // Eje de clasificación: química (structural_family) ↔ terapéutica (therapeutic_family).
  // Preferencia persistida en localStorage (D5/D6 del plan de clasificación dual).
  const [classificationMode, setClassificationMode] = useState<ClassificationMode>(readClassificationMode);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  const handleClassificationModeChange = (mode: ClassificationMode) => {
    setClassificationMode(mode);
    writeClassificationMode(mode);
  };

  const contentRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const cardsContainerRef = useRef<HTMLDivElement>(null);
  const uploadRef = useRef<HTMLButtonElement>(null);

  const handleOpenUpload = () => {
    setShowCustomModal(true);
  };

  // EFICIENCIA (2026-09-01). Aqui vivia una coreografia GSAP que animaba CADA
  // tarjeta del catalogo —387 receptores— con opacidad, desplazamiento, escala y
  // `filter: blur(3px)` escalonados, mas una espera fingida de 300 ms al abrir y
  // cuatro puntos pulsando en bucle infinito. El catalogo ya esta en memoria
  // cuando el modal se abre: esa espera no cargaba nada, solo se sentia lenta.
  //
  // El coste era real y peor en equipos modestos: `filter: blur` fuerza repintado
  // de capa, y animar cientos de nodos a la vez satura el hilo de composicion.
  // Ademas las tarjetas nacian con `opacity-0` y solo GSAP las hacia visibles: si
  // la animacion no llegaba a correr —un re-render rapido, StrictMode, el modal
  // reabierto—, el catalogo se quedaba en blanco con los datos ya cargados.
  //
  // Ahora la lista aparece cuando esta lista. `content-visibility: auto` deja que
  // el navegador se salte el trazado de las familias fuera de pantalla, que es lo
  // que de verdad cuesta con este numero de tarjetas.

  const handleShareTarget = async (id: string) => {
    setSharingTargetId(id);
    setShareFeedback(null);
    try {
      const res = await shareCustomTarget(id);
      if (!res.success) {
        setShareFeedback({
          kind: "error",
          message: res.message || "No fue posible compartir el receptor.",
        });
        return;
      }
      onTargetUploadSuccess?.();
      setShareFeedback({
        kind: "success",
        message: res.message || "El receptor ya está disponible en la comunidad.",
      });
    } catch (err: unknown) {
      setShareFeedback({
        kind: "error",
        message: err instanceof Error ? err.message : "No fue posible compartir el receptor.",
      });
    } finally {
      setSharingTargetId(null);
    }
  };

  const groupedTargets = useMemo(() => {
    const term = searchTerm.toLowerCase();

    // 1) Filtro por tab (oficiales / propios / comunidad) ANTES de agrupar.
    let tabTargets = targets;
    if (activeTab === "oficiales") {
      tabTargets = targets.filter(t => !t.is_private && !t.is_community);
    } else if (activeTab === "propios") {
      // El backend ya devuelve únicamente los privados de la cuenta actual.
      tabTargets = targets.filter(t => t.is_private && !t.is_community);
    } else if (activeTab === "comunidad") {
      tabTargets = targets.filter(t => t.is_community);
    }

    // 2) Búsqueda: nombre, PDB ID, organismo + familia del eje de clasificación activo
    //    (el placeholder "o familia" ahora dice la verdad).
    const filtered = tabTargets.filter(t => {
      const family = classificationMode === "quimica" ? t.structural_family : t.therapeutic_family;
      return (
        (t.name || "").toLowerCase().includes(term) || 
        (t.pdb_id || "").toLowerCase().includes(term) || 
        (t.organism && t.organism.toLowerCase().includes(term)) ||
        (family && family.toLowerCase().includes(term))
      );
    });

    // 3) Agrupar por eje activo: display names, "Otra / No Clasificada" al final,
    //    COUNT DESC. groupTargets es puro: NUNCA filtra ni muta.
    return groupTargets(filtered, classificationMode);
  }, [targets, searchTerm, activeTab, classificationMode]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8" role="presentation">
      
      {/* Backdrop con Blur Soft Glassmorphism */}
      <div 
        className="absolute inset-0 bg-black/85"
        onClick={onClose}
      />

      {/* Modal Window con Retroiluminación Morada Sutil (Soft Glassglow) */}
      <div className="relative w-full max-w-5xl h-[85vh] bg-zinc-950/95 border border-purple-500/20 rounded-2xl flex flex-col overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="target-selector-title">
        
        {/* Header Quirúrgico Hallmark */}
        <div ref={headerRef} className="flex-none px-6 py-5 border-b border-zinc-800/80 bg-black/60 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-300">
                <Database size={18} />
              </div>
              <div>
              <h2 id="target-selector-title" className="text-base font-bold font-mono text-white uppercase tracking-wider flex items-center gap-2">
                  Catálogo de Receptores
                </h2>
                <p className="text-xs text-zinc-400 font-mono mt-0.5">
                  Selecciona una estructura biológica para la simulación de acoplamiento molecular
                </p>
              </div>
            </div>

            <button 
              type="button"
              onClick={onClose}
              aria-label="Cerrar catálogo de receptores"
              className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:border-purple-500/30 transition-colors cursor-pointer"
            >
              <X size={18} />
            </button>
          </div>

          {/* Search Bar & Subir Receptor Action */}
          <div className="flex flex-col sm:flex-row gap-3 w-full">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" size={15} />
              <input
                type="text"
                placeholder="Buscar por PDB ID, nombre de la proteína, o familia..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-black border border-zinc-800 rounded-xl py-2.5 pl-10 pr-4 font-mono text-xs text-white placeholder-zinc-600 outline-none focus:border-purple-500/40 transition-colors duration-150"
              />
            </div>
            
            <button 
              ref={uploadRef}
              onClick={handleOpenUpload}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl font-mono text-xs font-bold uppercase tracking-wider bg-zinc-900 hover:bg-zinc-800 text-purple-300 hover:text-white border border-purple-500/30 transition-colors flex items-center justify-center gap-2 cursor-pointer"
            >
              <Upload size={14} />
              Subir Receptor
            </button>
          </div>

          {/* Toggle Clasificación: Familia Química ↔ Familia Terapéutica */}
          <div className="flex items-center gap-1 w-fit rounded-lg bg-black/60 border border-zinc-800/80 p-1">
            <button
              onClick={() => handleClassificationModeChange("quimica")}
              className={`px-4 py-2.5 text-xs font-mono font-bold uppercase tracking-wider border-b-2 rounded-md transition-colors cursor-pointer ${
                classificationMode === "quimica"
                  ? "border-purple-400/80 text-purple-300 bg-purple-500/5"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              Familia Química
            </button>
            <button
              onClick={() => handleClassificationModeChange("terapeutica")}
              className={`px-4 py-2.5 text-xs font-mono font-bold uppercase tracking-wider border-b-2 rounded-md transition-colors cursor-pointer ${
                classificationMode === "terapeutica"
                  ? "border-purple-400/80 text-purple-300 bg-purple-500/5"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              Familia Terapéutica
            </button>
          </div>

          {/* Tabs Navigation */}
          <div className="flex border-b border-zinc-800/80 pt-1 gap-2">
            <button
              onClick={() => setActiveTab("oficiales")}
              className={`pb-2.5 px-4 text-xs font-mono font-bold uppercase tracking-wider border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
                activeTab === "oficiales"
                  ? "border-purple-400/80 text-purple-300 bg-purple-500/5"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              <Globe size={13} />
              Receptores Oficiales
            </button>
            
            <button
              onClick={() => setActiveTab("propios")}
              className={`pb-2.5 px-4 text-xs font-mono font-bold uppercase tracking-wider border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
                activeTab === "propios"
                  ? "border-purple-400/80 text-purple-300 bg-purple-500/5"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              <User size={13} />
              Mis Receptores
            </button>

            <button
              onClick={() => setActiveTab("comunidad")}
              className={`pb-2.5 px-4 text-xs font-mono font-bold uppercase tracking-wider border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
                activeTab === "comunidad"
                  ? "border-purple-400/80 text-purple-300 bg-purple-500/5"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              <Sparkles size={13} />
              Comunidad Científica
            </button>
          </div>

          {shareFeedback && (
            <div
              role={shareFeedback.kind === "error" ? "alert" : "status"}
              aria-live="polite"
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium ${
                shareFeedback.kind === "success"
                  ? "border-emerald-500/25 bg-emerald-950/20 text-emerald-200"
                  : "border-rose-500/25 bg-rose-950/20 text-rose-200"
              }`}
            >
              {shareFeedback.kind === "success" ? (
                <ShieldCheck size={14} aria-hidden="true" />
              ) : (
                <AlertTriangle size={14} aria-hidden="true" />
              )}
              <span>{shareFeedback.message}</span>
            </div>
          )}
        </div>

        {/* Catálogo. Sin estado de carga: `targets` ya viene resuelto del padre. */}
          <div ref={cardsContainerRef} className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-purple-500/10 scrollbar-track-transparent">
          {groupedTargets.length === 0 ? (
            <div className="w-full h-full flex flex-col items-center justify-center text-zinc-500 space-y-3 py-16">
              <Crosshair size={40} className="opacity-20 text-purple-400" />
              <p className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400">
                No se encontraron receptores en esta sección
              </p>
            </div>
          ) : (
            groupedTargets.map(([family, familyTargets]) => (
              <div
                key={family}
                className="family-section space-y-4"
                style={{ contentVisibility: "auto", containIntrinsicSize: "auto 420px" }}
              >
                
                {/* Categoría Header */}
                <div className="flex items-center gap-3">
                  <h3 className="text-xs font-mono font-bold text-white uppercase tracking-widest flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400/60" />
                    {family}
                  </h3>
                  <div className="flex-1 h-px bg-zinc-800" />
                  <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                    {familyTargets.length} OBJETIVOS
                  </span>
                </div>

                {/* Target Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {familyTargets.map(targetObj => {
                    const isSelected = 
                      (targetObj.pdb_id && selectedTargetId && targetObj.pdb_id.toLowerCase() === selectedTargetId.toLowerCase()) ||
                      (targetObj.id && selectedTargetId && targetObj.id.toLowerCase() === selectedTargetId.toLowerCase());

                    return (
                      <div 
                        key={targetObj.pdb_id || targetObj.id}
                        onClick={() => {
                          onSelect(targetObj.pdb_id || targetObj.id || "");
                          onClose();
                        }}
                        className={`target-card group relative flex flex-col p-4 rounded-xl border transition-colors duration-150 cursor-pointer ${
                          isSelected 
                            ? "bg-zinc-900 border-purple-500/50 text-white"
                            : "bg-zinc-900/50 border-zinc-800/80 hover:border-purple-500/30 hover:bg-zinc-900"
                        }`}
                      >
                        {isSelected && (
                          <div className="absolute top-3 right-3">
                            <span className="bg-purple-950/60 border border-purple-500/30 text-purple-300 text-[9px] font-mono font-bold uppercase px-2 py-0.5 rounded shadow-sm flex items-center gap-1">
                              <ShieldCheck size={10} /> Activo
                            </span>
                          </div>
                        )}

                        <div className="flex justify-between items-start mb-2 gap-2 pr-12">
                          <h4 className="text-xs font-mono font-bold text-white tracking-wide line-clamp-2 h-9 leading-snug">
                            {targetObj.name}
                          </h4>
                        </div>
                        
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[10px] font-mono text-purple-300 font-bold bg-zinc-950 border border-purple-500/20 px-2 py-0.5 rounded">
                            {targetObj.pdb_id}
                          </span>
                          <span className="text-[10px] font-mono text-zinc-400 truncate">
                            {targetObj.organism || "Humano"}
                          </span>
                        </div>

                        {/* Doc 71: qué cadenas forman el sitio, y con qué evidencia se
                            sabe. Va aquí, con la identidad del receptor, porque eso
                            es: no una métrica de calidad sino parte de qué es esta
                            estructura. Los mismos chips que la pestaña de Evaluación
                            —componente compartido para que no puedan divergir—. */}
                        <div className="mb-4">
                          <ChipsDelSitio target={targetObj} />
                        </div>

                        {targetObj.preparation_parent_id && (
                          <div className="mb-3 rounded-lg border border-cyan-500/20 bg-cyan-950/15 px-2.5 py-2 font-mono text-[9px] text-cyan-200/80">
                            Variante reproducible
                            {targetObj.prepared_receptor_sha256
                              ? ` · sha256:${targetObj.prepared_receptor_sha256.slice(0, 10)}…`
                              : ""}
                          </div>
                        )}

                        {/* Stats Grid */}
                        <div className="mt-auto grid grid-cols-2 gap-2">
                          {/* Estado de calibración: lo que el usuario final entiende */}
                          <div className="flex items-center gap-1.5 p-2 rounded-lg bg-black border border-zinc-800"
                               title={calibrationTooltip(targetObj.calibration_status, targetObj.hotspot_count ?? 0)}>
                            <span className={`h-2 w-2 rounded-full shrink-0 ${
                              (targetObj.calibration_status ?? "sin_datos") === "listo" ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" :
                              (targetObj.calibration_status ?? "sin_datos") === "revisar" ? "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.8)]" :
                              "bg-zinc-600"
                            }`} />
                            <div className="flex flex-col">
                              <span className="text-[8px] font-mono text-zinc-500 uppercase font-bold">Calibración</span>
                              <span className={`text-[10px] font-mono font-bold ${
                                (targetObj.calibration_status ?? "sin_datos") === "listo" ? "text-emerald-400" :
                                (targetObj.calibration_status ?? "sin_datos") === "revisar" ? "text-amber-400" :
                                "text-zinc-500"
                              }`}>
                                {calibrationLabel(targetObj.calibration_status)}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 p-2 rounded-lg bg-black border border-zinc-800">
                            <Fingerprint size={12} className="text-purple-400/80" />
                            <div className="flex flex-col">
                              <span className="text-[8px] font-mono text-zinc-500 uppercase font-bold">Resolución</span>
                              <span className="text-[10px] font-mono font-bold text-white">
                                {targetObj.resolution ? `${targetObj.resolution.toFixed(2)} Å` : "N/A"}
                              </span>
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setVariantBase(targetObj);
                          }}
                          className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-lg border border-cyan-500/25 bg-cyan-950/15 px-2.5 py-1.5 font-mono text-[9px] font-bold uppercase tracking-wider text-cyan-200 transition-colors hover:border-cyan-400/50 hover:bg-cyan-950/30"
                        >
                          <FlaskConical size={11} /> Crear variante
                        </button>

                        {/* Credits for author / Share button */}
                        {activeTab === "propios" && !targetObj.is_community ? (
                          <div className="mt-3 pt-2 border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono">
                            <span className="text-zinc-500">Privado</span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleShareTarget(targetObj.id || targetObj.pdb_id || "");
                              }}
                              disabled={sharingTargetId !== null}
                              aria-busy={sharingTargetId === (targetObj.id || targetObj.pdb_id)}
                              className="inline-flex min-w-[6rem] items-center justify-center gap-1.5 rounded border border-purple-500/30 bg-zinc-800 px-2.5 py-1 font-bold text-[9px] uppercase tracking-wider text-purple-300 transition-colors hover:bg-purple-950/40 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {sharingTargetId === (targetObj.id || targetObj.pdb_id) ? (
                                <><Loader2 size={10} className="animate-spin" aria-hidden="true" /> Compartiendo</>
                              ) : "Compartir"}
                            </button>
                          </div>
                        ) : targetObj.creator_username ? (
                          <div className="mt-3 pt-2 border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-500">
                            <span>Colaborador:</span>
                            <span className="text-purple-300">@{targetObj.creator_username}</span>
                          </div>
                        ) : null}

                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {showCustomModal && (
        <CustomReceptorModal 
          onClose={() => setShowCustomModal(false)} 
          onSuccess={() => {
            setShowCustomModal(false);
            if (onTargetUploadSuccess) onTargetUploadSuccess();
          }} 
        />
      )}

      {variantBase && (
        <ReceptorVariantModal
          parent={variantBase}
          onClose={() => setVariantBase(null)}
          onSuccess={(target) => {
            setVariantBase(null);
            if (onTargetUploadSuccess) onTargetUploadSuccess();
            onSelect(target.pdb_id);
            onClose();
          }}
        />
      )}
    </div>
  );
}
