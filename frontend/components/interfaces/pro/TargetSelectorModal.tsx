"use client";

import { presentError } from "../../../lib/frontendError";

import { useLanguage } from "@/context/LanguageContext";
import { useScrollLock } from "@/hooks/useScrollLock";

import React, { useState, useMemo, useEffect, useRef } from "react";
import { X, Search, Database, Fingerprint, Upload, ShieldCheck, FlaskConical, AlertTriangle, Loader2 } from "lucide-react";
import type { Target } from "../../../lib/api";
import { shareCustomTarget } from "../../../lib/api";
import { groupTargets, readClassificationMode, writeClassificationMode } from "../../../lib/targetGrouping";
import { esExcepcionCruda } from "../../../lib/receptorNoDisponible";
import { puntuarReceptor } from "../../../lib/busquedaDeReceptores";
import { ChipsDelSitio } from "../../science/ChipsDelSitio";
import { DetalleDelSitio } from "../../science/DetalleDelSitio";
import { RespaldoDelReceptor } from "../../science/RespaldoDelReceptor";
import type { ClassificationMode } from "../../../lib/targetGrouping";
import { agruparSecciones } from "../../../lib/seccionCatalogo";
import type { SeccionCatalogo } from "../../../lib/seccionCatalogo";
import { SeccionDelCatalogo, EvidenciaDelCatalogo, CLAVE_DE_SECCION } from "../../science/SeccionDelCatalogo";
import { IntentosPublicados } from "../../science/IntentosDeVerificacion";
import { CustomReceptorModal } from "./CustomReceptorModal";
import { ReceptorVariantModal } from "./ReceptorVariantModal";

// Las tres secciones del catálogo van como pestañas. La Demostración abre primero:
// es donde está el catálogo entero (381 receptores) y lo que casi todo el mundo viene a
// explorar. «Verificados» va al final porque hoy está vacía y sólo trae intentos
// publicados; antes, ser la primera sección empujaba la Demostración fuera de pantalla.
const ORDEN_DE_PESTANAS: readonly SeccionCatalogo[] = ["demostracion", "propios", "verificado"];
const SECCION_INICIAL: SeccionCatalogo = "demostracion";

interface TargetSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  targets: Target[];
  onSelect: (pdbId: string) => void;
  selectedTargetId: string | null;
  onTargetUploadSuccess?: () => void;
}

// SOL-03: el badge del selector mide readiness ESTRUCTURAL (preparado +
// grid + hotspots) y se rotula como lo que mide. La calibración PREDICTIVA
// del receptor la muestra el componente SC-9 compartido
// (`RespaldoDelReceptor`), con su nivel y su ρ — el mismo que la corrida,
// para que las dos pantallas no puedan decir cosas distintas.
function calibrationLabel(status?: string): string {
  switch (status) {
    case "listo": return "pn_prep_listo";
    case "revisar": return "pn_prep_revisar";
    default: return "pn_prep_sin_datos";
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
  const { t } = useLanguage();
  useScrollLock(isOpen);
  const [searchTerm, setSearchTerm] = useState("");
  const [seccionActiva, setSeccionActiva] = useState<SeccionCatalogo>(SECCION_INICIAL);
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [variantBase, setVariantBase] = useState<Target | null>(null);
  const [sharingTargetId, setSharingTargetId] = useState<string | null>(null);
  const [shareFeedback, setShareFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  // Eje de clasificación: química (structural_family) ↔ terapéutica (therapeutic_family).
  // Preferencia persistida en localStorage (D5/D6 del plan de clasificación dual).
  const [classificationMode, setClassificationMode] = useState<ClassificationMode>(readClassificationMode);
  // QA1-006. `therapeutic_family` viene vacío en los 380 receptores del catálogo: la
  // pestaña «Familia terapéutica» listaba todo en «Otra / No clasificada», y con la
  // preferencia guardada el catálogo podía abrirse así. No se ofrece —ni se aplica—
  // un eje sin datos hasta que algún receptor lo traiga.
  const hayFamiliaTerapeutica = useMemo(
    () => targets.some((target) => (target.therapeutic_family ?? "").trim() !== ""),
    [targets],
  );
  const ejeDeClasificacion: ClassificationMode = hayFamiliaTerapeutica ? classificationMode : "quimica";

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
  const pestanasRef = useRef<Partial<Record<SeccionCatalogo, HTMLButtonElement | null>>>({});

  // El padre de Batch deja el modal montado y sólo cambia `isOpen`: sin esto, la pestaña
  // en la que se cerró sería la de la siguiente vez, y el catálogo no abriría en Demostración.
  useEffect(() => {
    if (isOpen) setSeccionActiva(SECCION_INICIAL);
  }, [isOpen]);

  const handleSeccionChange = (seccion: SeccionCatalogo) => {
    setSeccionActiva(seccion);
    // Cada pestaña es otra lista: se empieza arriba, no a media altura de la anterior.
    cardsContainerRef.current?.scrollTo?.({ top: 0 });
  };

  // Patrón de pestañas del WAI-ARIA: las flechas mueven la selección, Inicio y Fin saltan a los extremos.
  const handlePestanaKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, indice: number) => {
    const ultimo = ORDEN_DE_PESTANAS.length - 1;
    const destino =
      event.key === "ArrowRight" ? (indice + 1) % (ultimo + 1)
      : event.key === "ArrowLeft" ? (indice + ultimo) % (ultimo + 1)
      : event.key === "Home" ? 0
      : event.key === "End" ? ultimo
      : null;
    if (destino === null) return;
    event.preventDefault();
    const seccion = ORDEN_DE_PESTANAS[destino];
    handleSeccionChange(seccion);
    pestanasRef.current[seccion]?.focus();
  };

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
          message: res.message || t("ca_frontend_110"),
        });
        return;
      }
      onTargetUploadSuccess?.();
      setShareFeedback({
        kind: "success",
        message: res.message || t("ca_frontend_111"),
      });
    } catch (err: unknown) {
      setShareFeedback({
        kind: "error",
        message: err instanceof Error ? presentError(err, t) : t("ca_frontend_110"),
      });
    } finally {
      setSharingTargetId(null);
    }
  };

  const seccionesConGrupos = useMemo(() => agruparSecciones(targets).map(({ seccion, targets: tabTargets }) => {
    // 2) Búsqueda por PALABRAS (QA1-004): nombre, PDB ID, organismo y familia del eje activo.
    //    «ace» ya no casa por la mitad de «alcaligenaceae»; los nombres van antes que el organismo.
    const buscando = searchTerm.trim().length > 0;
    const puntuados = tabTargets
      .map((target, orden) => ({
        target,
        orden,
        puntos: puntuarReceptor(
          target,
          searchTerm,
          ejeDeClasificacion === "quimica" ? target.structural_family : target.therapeutic_family,
        ),
      }))
      .filter((p) => p.puntos > 0);
    if (buscando) puntuados.sort((a, b) => b.puntos - a.puntos || a.orden - b.orden);
    const puntos = new Map(puntuados.map((p) => [p.target, p.puntos]));

    // 3) Agrupar por eje activo: display names, "Otra / No Clasificada" al final,
    //    COUNT DESC. groupTargets es puro: NUNCA filtra ni muta.
    const grupos = groupTargets(puntuados.map((p) => p.target), ejeDeClasificacion);
    // Con una búsqueda activa manda la mejor coincidencia de cada grupo, no su tamaño: la ACE
    // no puede quedar detrás de un grupo grande que sólo la contiene por el organismo.
    if (buscando) {
      const mejor = (g: [string, Target[]]) => Math.max(...g[1].map((x) => puntos.get(x) ?? 0));
      grupos.sort((a, b) => mejor(b) - mejor(a));
    }
    // `total` rotula la pestaña: con una búsqueda activa cuenta las coincidencias, y así se ve
    // en qué sección están aunque no sea la que se está mirando.
    return { seccion, grupos, total: puntuados.length, vacia: seccion === "propios" ? !tabTargets.some((target) => target.is_private && !target.is_community) : tabTargets.length === 0 };
  }), [targets, searchTerm, ejeDeClasificacion]);

  const buscando = searchTerm.trim().length > 0;
  const totalDe = (seccion: SeccionCatalogo) => seccionesConGrupos.find((s) => s.seccion === seccion)?.total ?? 0;
  const otrasConCoincidencias = ORDEN_DE_PESTANAS.filter((s) => s !== seccionActiva && totalDe(s) > 0);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8" role="presentation">
      
      {/* Backdrop con Blur Soft Glassmorphism */}
      <div 
        className="absolute inset-0 bg-black/85"
        onClick={onClose}
      />

      {/* Modal Window con Retroiluminación Morada Sutil (Soft Glassglow) */}
      <div className="relative w-full max-w-5xl h-[85vh] bg-[var(--bg-card)] border border-purple-500/20 rounded-2xl flex flex-col overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="target-selector-title">
        
        {/* Header Quirúrgico Hallmark */}
        <div ref={headerRef} className="flex-none px-6 py-5 border-b border-zinc-800/80 bg-[var(--bg-secondary)] flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-[var(--accent-strong)]">
                <Database size={18} />
              </div>
              <div>
              <h2 id="target-selector-title" className="text-base font-bold font-mono text-white uppercase tracking-wider flex items-center gap-2">
                  {t("z_catalogo_receptores")}
                </h2>
                <p className="text-xs text-zinc-400 font-mono mt-0.5">
                  {t("pn_catalogo_sub")}
                </p>
              </div>
            </div>

            <button 
              type="button"
              onClick={onClose}
              aria-label={t("pn_cerrar_catalogo")}
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
                placeholder={t("z_buscar_receptor")}
                aria-label={t("z_buscar_receptor")}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-[var(--bg)] border border-zinc-800 rounded-xl py-2.5 pl-10 pr-4 font-mono text-xs text-white placeholder-zinc-600 outline-none focus:border-purple-500/40 transition-colors duration-150"
              />
            </div>
            
            <button 
              ref={uploadRef}
              onClick={handleOpenUpload}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl font-mono text-xs font-bold uppercase tracking-wider bg-zinc-900 hover:bg-zinc-800 text-[var(--accent-strong)] hover:text-white border border-purple-500/30 transition-colors flex items-center justify-center gap-2 cursor-pointer"
            >
              <Upload size={14} />
              {t("pn_receptor_subir")}
            </button>
          </div>

          {/* Secciones del catálogo. Justo bajo la búsqueda, que filtra las tres a la vez:
              el número de cada pestaña cuenta lo que queda de esa sección. */}
          <div
            role="tablist"
            aria-label={t("cat_secciones_aria")}
            className="grid grid-cols-3 sm:flex w-full sm:w-fit items-stretch sm:items-center gap-1 rounded-lg bg-[var(--bg-secondary)] border border-zinc-800/80 p-1"
          >
            {ORDEN_DE_PESTANAS.map((seccion, indice) => {
              const activa = seccion === seccionActiva;
              return (
                <button
                  key={seccion}
                  ref={(el) => { pestanasRef.current[seccion] = el; }}
                  type="button"
                  role="tab"
                  id={`target-selector-tab-${seccion}`}
                  aria-selected={activa}
                  aria-controls="target-selector-panel"
                  tabIndex={activa ? 0 : -1}
                  onClick={() => handleSeccionChange(seccion)}
                  onKeyDown={(event) => handlePestanaKeyDown(event, indice)}
                  className={`flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 px-1 sm:px-4 py-2 sm:py-2.5 text-center text-[10px] sm:text-xs leading-tight font-mono font-bold uppercase tracking-wide sm:tracking-wider border-b-2 rounded-md transition-colors cursor-pointer ${
                    activa
                      ? "border-purple-400/80 text-[var(--accent-strong)] bg-purple-500/5"
                      : "border-transparent text-zinc-400 hover:text-white"
                  }`}
                >
                  {t(CLAVE_DE_SECCION[seccion])}
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${
                      activa ? "bg-purple-500/15 text-[var(--accent-strong)]" : "bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {totalDe(seccion)}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Toggle Clasificación: Familia Química ↔ Familia Terapéutica. Sólo si hay
              datos terapéuticos (QA1-006): con un único eje no hay nada que alternar. */}
          {hayFamiliaTerapeutica && (
          <div className="flex items-center gap-1 w-fit rounded-lg bg-[var(--bg-secondary)] border border-zinc-800/80 p-1">
            <button
              onClick={() => handleClassificationModeChange("quimica")}
              className={`px-4 py-2.5 text-xs font-mono font-bold uppercase tracking-wider border-b-2 rounded-md transition-colors cursor-pointer ${
                classificationMode === "quimica"
                  ? "border-purple-400/80 text-[var(--accent-strong)] bg-purple-500/5"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              {t("z_familia_quimica")}
            </button>
            <button
              onClick={() => handleClassificationModeChange("terapeutica")}
              className={`px-4 py-2.5 text-xs font-mono font-bold uppercase tracking-wider border-b-2 rounded-md transition-colors cursor-pointer ${
                classificationMode === "terapeutica"
                  ? "border-purple-400/80 text-[var(--accent-strong)] bg-purple-500/5"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              {t("z_familia_terapeutica")}
            </button>
          </div>
          )}

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
          <div
            ref={cardsContainerRef}
            role="tabpanel"
            id="target-selector-panel"
            aria-labelledby={`target-selector-tab-${seccionActiva}`}
            className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-purple-500/10 scrollbar-track-transparent"
          >
          {seccionesConGrupos.filter(({ seccion }) => seccion === seccionActiva).map(({ seccion, grupos, vacia }) => (
            <SeccionDelCatalogo key={seccion} seccion={seccion} vacia={vacia} onUpload={handleOpenUpload} intentos={seccion === "verificado" && <IntentosPublicados targets={seccionesConGrupos.flatMap(section => section.grupos.flatMap(([, members]) => members))} />}>
            {buscando && grupos.length === 0 && !vacia && (
              <p role="status" className="text-sm leading-6 text-[var(--text-secondary)]">
                {t("cat_busqueda_sin_resultados")}
                {otrasConCoincidencias.length > 0 && ` ${t("cat_busqueda_en_otras", {
                  secciones: otrasConCoincidencias.map((s) => `${t(CLAVE_DE_SECCION[s])} (${totalDe(s)})`).join(", "),
                })}`}
              </p>
            )}
            {grupos.map(([family, familyTargets]) => (
              <div
                key={family}
                className="family-section space-y-4"
                style={{ contentVisibility: "auto", containIntrinsicSize: "auto 420px" }}
              >
                
                {/* Categoría Header */}
                <div className="flex items-center gap-3">
                  <h4 className="text-xs font-mono font-bold text-white uppercase tracking-widest flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400/60" />
                    {t(family)}
                  </h4>
                  <div className="flex-1 h-px bg-zinc-800" />
                  <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                    {t("pn_targets_count", { n: familyTargets.length })}
                  </span>
                </div>

                {/* Target Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {familyTargets.map(targetObj => {
                    const isSelected =
                      (targetObj.pdb_id && selectedTargetId && targetObj.pdb_id.toLowerCase() === selectedTargetId.toLowerCase()) ||
                      (targetObj.id && selectedTargetId && targetObj.id.toLowerCase() === selectedTargetId.toLowerCase());
                    // DOCK-003: se muestra con su motivo, pero no se puede elegir.
                    const noDisponible = targetObj.disponible === false;
                    // Receta v7: disponible no es intacta. Se dice antes de elegirla.
                    const truncadas = noDisponible ? [] : targetObj.cadenas_truncadas_en_sitio ?? [];

                    return (
                      <div
                        key={targetObj.pdb_id || targetObj.id}
                        aria-disabled={noDisponible || undefined}
                        onClick={() => {
                          if (noDisponible) return;
                          onSelect(targetObj.pdb_id || targetObj.id || "");
                          onClose();
                        }}
                        className={`target-card group relative flex flex-col p-4 rounded-xl border transition-colors duration-150 ${
                          noDisponible
                            ? "cursor-not-allowed bg-[var(--bg-secondary)] border-zinc-800/60"
                            : isSelected
                            ? "cursor-pointer bg-zinc-900 border-purple-500/50 text-white"
                            : "cursor-pointer bg-zinc-900/50 border-zinc-800/80 hover:border-purple-500/30 hover:bg-zinc-900"
                        }`}
                      >
                        {noDisponible && (
                          <div className="mb-2 rounded-lg border border-amber-500/30 bg-amber-950/20 px-2.5 py-2 font-mono text-[9px] text-amber-800 dark:text-amber-200/90">
                            <span className="font-bold uppercase">{t("pn_no_disponible")}</span>
                            {/* QA1-003: una excepción de Python no es un motivo. Va una frase
                                al frente y el texto técnico, detrás de «Detalle técnico». */}
                            {esExcepcionCruda(targetObj.motivo_no_disponible)
                              ? ` · ${t("pn_no_disponible_meeko")}`
                              : targetObj.motivo_no_disponible
                                ? ` · ${targetObj.motivo_no_disponible}`
                                : ""}
                            {esExcepcionCruda(targetObj.motivo_no_disponible) && (
                              <details className="mt-1" onClick={(event) => event.stopPropagation()}>
                                <summary className="cursor-pointer text-amber-800 dark:text-amber-200/70">{t("pn_detalle_tecnico")}</summary>
                                <span className="mt-1 block break-words text-amber-800 dark:text-amber-100/70">{targetObj.motivo_no_disponible}</span>
                              </details>
                            )}
                          </div>
                        )}
                        {truncadas.length > 0 && (
                          <div
                            className="mb-2 rounded-lg border border-amber-500/30 bg-amber-950/20 px-2.5 py-2 font-mono text-[9px] text-amber-800 dark:text-amber-200/90"
                            title={truncadas.join("\n")}
                          >
                            {t("pn_truncadas_en_sitio", { n: truncadas.length })}
                          </div>
                        )}
                        {isSelected && (
                          <div className="absolute top-3 right-3">
                            <span className="bg-purple-500/10 border border-purple-500/30 text-[var(--accent-strong)] text-[9px] font-mono font-bold uppercase px-2 py-0.5 rounded shadow-sm flex items-center gap-1">
                              <ShieldCheck size={10} /> {t("pn_receptor_activo")}
                            </span>
                          </div>
                        )}

                        <div className="flex justify-between items-start mb-2 gap-2 pr-12">
                          <h4 className="text-xs font-mono font-bold text-white tracking-wide line-clamp-2 h-9 leading-snug">
                            {targetObj.name}
                          </h4>
                        </div>
                        
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[10px] font-mono text-[var(--accent-strong)] font-bold bg-zinc-950 border border-purple-500/20 px-2 py-0.5 rounded">
                            {targetObj.pdb_id}
                          </span>
                          <span className="text-[10px] font-mono text-zinc-400 truncate">
                            {targetObj.organism || t("pn_organismo_humano")}
                          </span>
                        </div>

                        {/* Doc 71: qué cadenas forman el sitio, y con qué evidencia se
                            sabe. Va aquí, con la identidad del receptor, porque eso
                            es: no una métrica de calidad sino parte de qué es esta
                            estructura. Los mismos chips que la pestaña de Evaluación
                            —componente compartido para que no puedan divergir—. */}
                        <div className="mb-4 space-y-2">
                          <ChipsDelSitio target={targetObj} />
                          {/* La versión larga, cerrada de entrada. El chip de
                              arriba basta para quien ya lee «Interfaz A·B»; esto
                              existe para quien no, y para los 110 receptores en
                              los que el aviso ámbar cambia cómo hay que leer la
                              afinidad. Antes eso vivía en un `title`, que en
                              táctil y con teclado no se alcanza. */}
                          <DetalleDelSitio target={targetObj} />
                          {/* SOL-03: el respaldo PREDICTIVO del receptor, con el
                              componente SC-9 que ya usa el resultado. Antes el
                              badge verde decía «CALIBRACIÓN — Listo» para un
                              receptor `curado_estructural` con `spearman_rho:
                              null`: la preparación estructural se leía como
                              respaldo predictivo que no existía. */}
                          <EvidenciaDelCatalogo target={targetObj} />
                          {targetObj.is_community && <p className="text-sm text-zinc-300">{t("z_comunidad_cientifica")}</p>}
                          <RespaldoDelReceptor calibracion={targetObj.calibracion} compacto />
                        </div>

                        {targetObj.preparation_parent_id && (
                          <div className="mb-3 rounded-lg border border-cyan-500/20 bg-cyan-950/15 px-2.5 py-2 font-mono text-[9px] text-cyan-800 dark:text-cyan-200/80">
                            {t("pn_variante_reproducible")}
                            {targetObj.prepared_receptor_sha256
                              ? ` · sha256:${targetObj.prepared_receptor_sha256.slice(0, 10)}…`
                              : ""}
                          </div>
                        )}

                        {/* Stats Grid */}
                        <div className="mt-auto grid grid-cols-2 gap-2">
                          {/* SOL-03: readiness ESTRUCTURAL del receptor —
                              preparado, con grid y residuos del sitio. No es
                              calibración predictiva: esa viaja arriba, con el
                              componente SC-9. */}
                          {/* QA1-003: `calibration_status` mide preparado + grid + hotspots, y los 15
                              receptores no disponibles llegan con `is_prepared` verdadero: la
                              tarjeta decía «Preparación · Listo» sobre un receptor que Meeko no
                              puede construir. Un receptor no disponible no está listo, y lo dice. */}
                          <div className="flex items-center gap-1.5 p-2 rounded-lg bg-[var(--bg)] border border-zinc-800"
                               title={noDisponible ? t("pn_no_disponible") : t(calibrationTooltip(targetObj.calibration_status, targetObj.hotspot_count ?? 0))}>
                            <span className={`h-2 w-2 rounded-full shrink-0 ${
                              noDisponible ? "bg-amber-500/70" :
                              (targetObj.calibration_status ?? "sin_datos") === "listo" ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" :
                              (targetObj.calibration_status ?? "sin_datos") === "revisar" ? "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.8)]" :
                              "bg-zinc-600"
                            }`} />
                            <div className="flex flex-col">
                              <span className="text-[8px] font-mono text-zinc-500 uppercase font-bold">{t("pn_preparacion")}</span>
                              <span className={`text-[10px] font-mono font-bold ${
                                noDisponible ? "text-amber-700 dark:text-amber-400" :
                                (targetObj.calibration_status ?? "sin_datos") === "listo" ? "text-emerald-700 dark:text-emerald-400" :
                                (targetObj.calibration_status ?? "sin_datos") === "revisar" ? "text-amber-700 dark:text-amber-400" :
                                "text-zinc-500"
                              }`}>
                                {noDisponible ? t("pn_no_disponible") : t(calibrationLabel(targetObj.calibration_status))}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 p-2 rounded-lg bg-[var(--bg)] border border-zinc-800">
                            <Fingerprint size={12} className="text-purple-400/80" />
                            <div className="flex flex-col">
                              <span className="text-[8px] font-mono text-zinc-500 uppercase font-bold">{t("pn_resolucion")}</span>
                              <span className="text-[10px] font-mono font-bold text-white">
                                {targetObj.resolution ? `${targetObj.resolution.toFixed(2)} Å` : "N/A"}
                              </span>
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          disabled={noDisponible}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (noDisponible) return;
                            onSelect(targetObj.pdb_id || targetObj.id || "");
                            onClose();
                          }}
                          className="mt-3 min-h-11 rounded-lg border border-zinc-700 px-3 text-sm font-semibold text-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-40"
                        >
                          {t("ev_elige_receptor")} · {targetObj.pdb_id}
                        </button>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            // QA1-003: una variante sólo cambia qué metales y cofactores se conservan;
                            // no repara lo que Meeko no puede construir. Decisión del propietario
                            // (2026-10-04): no se ofrece sobre un receptor no disponible.
                            if (noDisponible) return;
                            setVariantBase(targetObj);
                          }}
                          disabled={noDisponible}
                          title={noDisponible ? t("pn_variante_no_disponible") : undefined}
                          className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-lg border border-cyan-500/25 bg-cyan-950/15 px-2.5 py-1.5 font-mono text-[9px] font-bold uppercase tracking-wider text-cyan-200 transition-colors hover:border-cyan-400/50 hover:bg-cyan-950/30 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-cyan-500/25 disabled:hover:bg-cyan-950/15"
                        >
                          <FlaskConical size={11} /> {t("pn_variante_crear")}
                        </button>

                        {/* Credits for author / Share button */}
                        {targetObj.is_private && !targetObj.is_community ? (
                          <div className="mt-3 pt-2 border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono">
                            <span className="text-zinc-500">{t("pn_receptor_privado")}</span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleShareTarget(targetObj.id || targetObj.pdb_id || "");
                              }}
                              disabled={sharingTargetId !== null}
                              aria-busy={sharingTargetId === (targetObj.id || targetObj.pdb_id)}
                              className="inline-flex min-w-[6rem] items-center justify-center gap-1.5 rounded border border-purple-500/30 bg-zinc-800 px-2.5 py-1 font-bold text-[9px] uppercase tracking-wider text-[var(--accent-strong)] transition-colors hover:bg-purple-950/40 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {sharingTargetId === (targetObj.id || targetObj.pdb_id) ? (
                                <><Loader2 size={10} className="animate-spin" aria-hidden="true" /> {t("pn_compartiendo")}</>
                              ) : t("pn_compartir")}
                            </button>
                          </div>
                        ) : targetObj.creator_username ? (
                          <div className="mt-3 pt-2 border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-500">
                            <span>{t("auto_1623b4a2c03e")}</span>
                            <span className="text-[var(--accent-strong)]">@{targetObj.creator_username}</span>
                          </div>
                        ) : null}

                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
            </SeccionDelCatalogo>
          ))}
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
