"use client";

import { presentError } from "../../lib/frontendError";

/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4
 * Bioteca y expediente en paneles sólidos; el visor ocupa sólo su área útil. */

import type { CSSProperties } from "react";
import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { motion, AnimatePresence } from "framer-motion";
import {
  getMoldex,
  getProteinFile,
  getPoseFile,
  downloadCertificate,
  downloadComplexFile,
  checkBlockchainHealth,
} from "../../lib/api";
import {
  porEvaluacionReciente,
  porScore,
  leerSello,
  urlDelExplorador,
  esRedDePruebas,
  presentarClgnn,
  calibracionDeLaFicha,
  hotspotsTocados,
  nombreDeLaFicha,
  type MoldexMolecule,
} from "../../lib/moldex";
import { useApiUrl } from "../../hooks/useApiUrl";
import { useDownload } from "../../hooks/useDownload";
import { useKeepAliveActive } from "../../context/KeepAliveContext";
import { isDesktopRuntime } from "../../lib/tauri";
import { MoleculeViewer3D } from "../../components/MoleculeViewer3D";
import Link from "next/link";
import { InsigniaDelCatalogo } from "@/components/science/InsigniaDelCatalogo";
import { pedirPreparacion } from "@/lib/peticionDePreparacion";
import MoldexCard from "../../components/MoldexCard";
import { MoldexUbicacion } from "../../components/MoldexUbicacion";
import MolecularComparison from "../../components/MolecularComparison";
import { PDFReportViewer } from "../../components/PDFReportViewer";
import { CertificationModal, type CertificationSuccess } from "../../components/CertificationModal";
import { ThinkingOrb } from "../../components/ui/ThinkingOrb";
import { Virtuoso } from "react-virtuoso";

import { Search, Activity, Info, ChevronRight, ClipboardCheck, Database, Box, FlaskConical, AlertCircle, Eye, Play } from "lucide-react";

import { ExternalLink } from "@/components/ui/ExternalLink";
// ─────────────────────────────────────────────────────────────────────
// MOLDEX — Bioteca del Laboratorio
// Layout: biblioteca, visor de bolsillo y expediente en tres columnas.
// Los dos paneles se pliegan; el canvas ocupa sólo el área central disponible.
// Se conservan comparador, PDF, certificación y descargas existentes.
// Adaptado del repo srcacahuate619/moldesign-app (frontend/app/moldex/page.tsx)
// Cambios desktop: sin interfaceMode (una sola UI), top-14 (nav h-14=56px),
// 3Dmol se carga localmente en app/layout.tsx; la API conserva su resolución dinámica.
// ─────────────────────────────────────────────────────────────────────

const NAV_HEIGHT = 56; // h-14 del Navigation.tsx
// Los paneles sólo se desplazan (transform, en el compositor); nunca animan width ni tocan el canvas.
const PANEL_TRANSITION = { type: "tween", duration: 0.2, ease: "easeOut" } as const;

type MoldexErrorKind = "engine" | "request" | "download";

type MoldexError = {
  kind: MoldexErrorKind;
  message: string;
};

type MoldexActiveView = "list" | "3d" | "info";

const MOBILE_TABS = [
  { id: "list" as const, clave: "mx_tab_bioteca", icon: Database },
  { id: "3d" as const, clave: "mx_tab_estructura_3d", icon: Box },
  { id: "info" as const, clave: "auto_26f227a3a058", icon: Info },
] as const;

function isTransportError(message: string): boolean {
  return /no se pudo establecer contacto|failed to fetch|networkerror|econnrefused|econnreset|timeout/i.test(message);
}

export default function MoldexPage() {
  const { t } = useLanguage();
  const allTargetsLabel = t("mx_filter_all");
  // Los enlaces de descarga se construyen EN RENDER, así que no pueden esperar
  // a una promesa: el hook devuelve null hasta que Rust confirma el puerto y
  // vuelve a pintar entonces. Mientras tanto los enlaces quedan inertes; usar
  // 8000 como conjetura podría enviarlos a otro producto instalado en el equipo.
  const apiUrl = useApiUrl();
  const { engine, initialized, retryEngine } = useDownload();
  const desktopRuntime = isDesktopRuntime();
  // FIX (keep-alive): /moldex vive en el DOM sin desmontarse (KeepAliveLayout).
  // useKeepAliveActive() es true solo cuando esta ruta es la activa. Con esto
  // recargamos la lista cada vez que el usuario VUELVE a Moldex, no solo al
  // primer montaje — así las moléculas recién guardadas en /evaluation aparecen.
  const isActive = useKeepAliveActive();
  const [molecules, setMolecules] = useState<MoldexMolecule[]>([]);
  const [catalogTotal, setCatalogTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [targetFilter, setTargetFilter] = useState("ALL");
  const [sortMode, setSortMode] = useState<"DATE_DESC" | "SCORE_DESC" | "SCORE_ASC">("DATE_DESC");

  const sortModeLabel = useMemo(() => {
    if (sortMode === "DATE_DESC") return t("mx_orden_recientes");
    if (sortMode === "SCORE_DESC") return t("mx_orden_indice_mayor");
    return t("mx_orden_indice_menor");
  }, [sortMode, t]);

  // Panel States (colapsables)
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showRightPanel, setShowRightPanel] = useState(true);

  // Comparison state — t("mx_comparador")
  const [compareMode, setCompareMode] = useState(false);
  const [selectionForCompare, setSelectionForCompare] = useState<string[]>([]);

  // 3D View state
  const [proteinData, setProteinData] = useState<string | null>(null);
  const [poseData, setPoseData] = useState<string | null>(null);
  const [loading3D, setLoading3D] = useState(false);
  const [viewerError, setViewerError] = useState(false);
  const [viewerRetry, setViewerRetry] = useState(0);
  const [activeView, setActiveView] = useState<MoldexActiveView>("list");
  const [windowHeight, setWindowHeight] = useState(1000);
  const [windowWidth, setWindowWidth] = useState(1440);
  const [showCertificationModal, setShowCertificationModal] = useState(false);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [error, setError] = useState<MoldexError | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  // ── Red del sello (MOLDEX-UX-008) ──
  // El enlace al explorador llevaba `cluster=devnet` escrito a mano. La red la
  // sabe el backend; codificarla aquí significa que un cambio de red dejaría el
  // enlace apuntando a otra cadena sin que nadie se entere.
  const [redDelSello, setRedDelSello] = useState<string | null>(null);

  useEffect(() => {
    let activo = true;
    checkBlockchainHealth()
      .then((h) => {
        if (activo) setRedDelSello(h.network || null);
      })
      .catch(() => {
        if (activo) setRedDelSello(null);
      });
    return () => {
      activo = false;
    };
  }, []);

  // ── Descargas autenticadas (MOLDEX-INT-006) ──
  const [descargando, setDescargando] = useState<"pdf" | "complejo" | null>(null);

  const descargar = async (que: "pdf" | "complejo") => {
    if (!selectedMolecule) return;
    setDescargando(que);
    setError(null);
    // El archivo es el de la corrida de la ficha, no el de la última evaluación
    // de la molécula: una molécula guardada varias veces tiene varias fichas.
    const corrida = selectedMolecule.provenance?.task_id ?? null;
    try {
      if (que === "pdf") await downloadCertificate(selectedMolecule.id, "general", corrida);
      else await downloadComplexFile(selectedMolecule.id, "general", corrida);
    } catch (e) {
      setError({
        kind: "download",
        message: e instanceof Error ? presentError(e, t) : t("mx_descarga_fallida"),
      });
    } finally {
      setDescargando(null);
    }
  };

  // ── Certificar en Solana / blockchain local ──
  const handleCertificationRecorded = ({ signature }: CertificationSuccess) => {
    if (!selectedId) return;
    // El sello acaba de emitirse contra la corrida que la ficha muestra, así
    // que se registra esa correspondencia (MOLDEX-SCI-001). Sin esto la
    // insignia diría «sello sin corrida» justo después de certificar con éxito.
    setMolecules(prev => prev.map(m => m.entry_id === selectedId
      ? {
          ...m,
          blockchain: {
            ...m.blockchain,
            certified: true,
            tx_signature: signature,
            certified_task_id: m.provenance?.task_id ?? null,
            certified_total_score: m.metrics?.score ?? null,
            matches_current_run: true,
          },
        }
      : m
    ));
  };

  useEffect(() => {
    setWindowHeight(window.innerHeight);
    const handleResize = () => {
      setWindowHeight(window.innerHeight);
      setWindowWidth(window.innerWidth);
      setIsMobile(window.innerWidth < 768);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // ── Carga inicial de moléculas desde getMoldex() — limitado a 100 para memoria ──
  // `preferir`: si llega (ej: desde el handler de `moldex:invalidated`, cuando
  // el usuario recién guardó una evaluación en /evaluation), se respeta como
  // selección final SIEMPRE que esa ficha exista en la respuesta. Se identifica
  // por molécula + corrida: una molécula guardada varias veces tiene varias
  // fichas y «la de esta molécula» no dice cuál.
  // Sin esto, `setSelectedId(normalized[0].entry_id)` pisaría la selección que el
  // handler ya decidió, rompiendo la UX t("mx_llevame_a_ella").
  // `silencioso`: al volver a la pestaña (keep-alive) la lista que había se queda en pantalla hasta que llega la nueva,
  // sin «cargando», y la ficha elegida sigue elegida si sigue en la lista. Un fallo silencioso no tapa la lista.
  const cargada = useRef(false);
  const loadMoldex = useCallback((preferir?: { moleculeId?: string; taskId?: string }, opciones?: { silencioso?: boolean }) => {
    const silencioso = Boolean(opciones?.silencioso);
    if (!silencioso) {
      setError(null);
      setLoading(true);
    }
    getMoldex(undefined, 100, 0)
      .then((data) => {
        // FIX: el backend serializa `target.hotspots` (y a veces `hotspots_hit`)
        // como string JSON, no como array. Si llega string, parsear; si no, [].
        // Sin esto, `(hotspots || []).map` revienta porque `"[...]" || []` cae
        // al truthy string y `.map` no existe en String.
        const normalizeArr = (v: any): any[] => {
          if (Array.isArray(v)) return v;
          if (typeof v === "string" && v.trim()) {
            try { return JSON.parse(v); } catch { return []; }
          }
          return [];
        };
        const normalized: MoldexMolecule[] = (data.results || []).map((m) => ({
          ...m,
          hotspots_hit: hotspotsTocados(m.hotspots_hit),
          target: m.target
            ? { ...m.target, hotspots: normalizeArr(m.target.hotspots) }
            : m.target,
        }));
        setMolecules(normalized);
        setCatalogTotal(typeof data.total === "number" ? data.total : normalized.length);
        cargada.current = true;
        if (normalized.length > 0) {
          // Si el caller pidió una molécula concreta (recién guardada), la
          // respetamos solo si está en la respuesta. Si no está (típicamente
          // porque el backend todavía no la commiteó — no debería pasar si el
          // CustomEvent se emite post-await), caemos al default: la primera.
          const preferida = preferir?.moleculeId
            ? normalized.find((m) =>
                m.id === preferir.moleculeId
                && (!preferir.taskId || m.provenance?.task_id === preferir.taskId))
            : undefined;
          setSelectedId((anterior) => preferida ? preferida.entry_id
            : silencioso && anterior && normalized.some((m) => m.entry_id === anterior) ? anterior
              : normalized[0].entry_id);
        }
      })
      .catch((err) => {
        console.error("Error loading Moldex library:", err);
        if (silencioso) return;
        setError({
          kind: "request",
          message: err instanceof Error ? presentError(err, t) : String(err),
        });
      })
      .finally(() => setLoading(false));
  }, [t]);

  // Cargar al montar Y cada vez que la página se vuelve activa (keep-alive):
  // sin esto, guardar una molécula en /evaluation y volver a /moldex mostraba
  // la lista vieja del primer montaje.
  useEffect(() => {
    if (!isActive) return;

    // Moldex shares the same startup state as the rest of the desktop app.
    // Do not issue a request while Rust is still publishing the real port.
    if (desktopRuntime) {
      if (!initialized || engine.state === "starting" || engine.state === "idle") {
        setError(null);
        setLoading(true);
        return;
      }
      if (engine.state !== "ready") {
        setLoading(false);
        setError({
          kind: "engine",
          message: engine.detail || "",
        });
        return;
      }
    }

    loadMoldex(undefined, { silencioso: cargada.current });
  }, [loadMoldex, isActive, desktopRuntime, initialized, engine.state, engine.detail]);

  // Listener cross-route: cuando /evaluation (o cualquier otra ruta) hace
  // saveMolecule exitosamente, emite `moldex:invalidated` con detail.moleculeId
  // y detail.taskId (la evaluación guardada).
  // Aquí recargamos la biblioteca y pre-seleccionamos la molécula nueva para
  // que el usuario la vea sin tener que hacer scroll/buscar. Esto cubre el
  // race condition "POST→navegación→loadMoldex antes de commit del backend":
  // el evento solo se emite DESPUÉS del await saveMolecule exitoso, así que
  // cuando loadMoldex corre aquí con el moleculeId, la molécula YA está
  // persistida y el fallback "primera de la lista" casi nunca se acciona.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      loadMoldex({ moleculeId: detail?.moleculeId, taskId: detail?.taskId });
    };
    window.addEventListener("moldex:invalidated", handler);
    return () => window.removeEventListener("moldex:invalidated", handler);
  }, [loadMoldex]);

  const selectedMolecule = useMemo(() =>
    molecules.find(m => m.entry_id === selectedId),
  [selectedId, molecules]);
  // Primitivos: el efecto del visor 3D depende de ellos y no de `selectedMolecule`
  // (que cambia de referencia en cada recarga de la lista).
  const selectedMoleculeId = selectedMolecule?.id ?? null;
  const selectedTaskId = selectedMolecule?.provenance?.task_id ?? null;

  // FIX (rendimiento): memoizar props del visor 3D. `hotspots.map(...)` creaba
  // un array NUEVO en cada render del padre → MoleculeViewer3D (ahora memo)
  // re-renderizaba su árbol WebGL por CUALQUIER cambio de estado (buscar,
  // filtrar, colapsar panel) → jank en toda la página.
  const viewerHotspots = useMemo(
    () => (Array.isArray(selectedMolecule?.target?.hotspots) ? selectedMolecule.target.hotspots : [])
      .map((h: any) => h.name)
      .filter((name: unknown): name is string => typeof name === "string"),
    [selectedMolecule]
  );
  const viewerHotspotsHit = useMemo(
    () => selectedMolecule?.hotspots_hit || [],
    [selectedMolecule]
  );

  // Callbacks estables para el Virtuoso/MoldexCard memoizado.
  const handleSelectMolecule = useCallback((id: string) => {
    setSelectedId(id);
    if (typeof window !== "undefined" && window.innerWidth < 768) setActiveView("3d");
  }, []);
  const handleToggleCompare = useCallback((id: string) => {
    setSelectionForCompare(prev => {
      const next = prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id].slice(-2);
      if (next.length === 2) setTimeout(() => setCompareMode(true), 0);
      return next;
    });
  }, []);

  // ── Cargar proteinData + poseData 3D al cambiar selección ──
  // FIX (rendimiento): depende SOLO de primitivos (molécula y corrida de la
  // ficha). Antes dependía de selectedMolecule (objeto que cambia de referencia
  // con cada re-fetch de la lista), lo que re-descargaba protein/pose cada vez
  // que la página se reactivaba aunque la selección no hubiera cambiado.
  // La pose es la de la corrida de la ficha, no la de la última evaluación.
  useEffect(() => {
    if (!selectedMoleculeId) {
      setProteinData(null);
      setPoseData(null);
      return;
    }
    if (!selectedTaskId) {
      setProteinData(null); setPoseData(null); setLoading3D(false); setViewerError(true);
      return;
    }
    let cancelled = false;
    setLoading3D(true);
    setViewerError(false);
    setProteinData(null);
    setPoseData(null);
    Promise.all([
      getProteinFile(selectedMoleculeId, selectedTaskId),
      getPoseFile(selectedMoleculeId, selectedTaskId)
    ]).then(([protein, pose]) => {
      if (cancelled) return;
      setProteinData(protein);
      setPoseData(pose);
      setViewerError(!protein || !pose);
    }).catch(err => {
      if (cancelled) return;
      console.error("Error loading 3D data:", err);
      setViewerError(true);
    }).finally(() => { if (!cancelled) setLoading3D(false); });
    return () => { cancelled = true; };
  }, [selectedMoleculeId, selectedTaskId, viewerRetry]);

  const filteredMolecules = useMemo(() => {
    const q = search.toLowerCase();
    return molecules.filter(m => {
      const name = m.name?.toLowerCase() || "";
      const smiles = m.smiles || "";
      const matchesSearch = name.includes(q) || smiles.includes(search);
      const matchesTarget = targetFilter === "ALL" || m.target?.pdb_id === targetFilter;
      return matchesSearch && matchesTarget;
    }).sort((a, b) => {
      if (sortMode === "DATE_DESC") {
        // MOLDEX-INT-007: `evaluated_at` ya llega del backend, así que
        // «RECIENTES» ordena por la fecha de la evaluación y no por el día en
        // que se dibujó la molécula. El comparador vive en `lib/moldex.ts`
        // para poder probarlo; antes se cacheaba un `_ts` mutando la propia
        // molécula con `as any`.
        return porEvaluacionReciente(a, b);
      }
      // MOLDEX-SCI-014: `score || 0` metía en el ranking a las moléculas sin
      // score. Ahora quedan siempre al final, en los dos sentidos.
      return porScore(sortMode === "SCORE_DESC" ? "desc" : "asc")(a, b);
    });
  }, [molecules, search, targetFilter, sortMode]);

  const targets = useMemo(() => {
    const t = new Set(molecules.map(m => m.target?.pdb_id).filter(Boolean));
    return ["ALL", ...Array.from(t)];
  }, [molecules]);
  const compactDesktop = windowWidth < 1280;
  const leftWidth = compactDesktop ? 280 : 320;
  const rightWidth = compactDesktop ? 320 : 400;

  // Moléculas del comparador memoizadas (refs estables para el memo de
  // MolecularComparison; antes se recomputaban con .find() en cada render).
  const compareMols = useMemo(() => {
    if (selectionForCompare.length !== 2) return { molA: undefined, molB: undefined };
    return {
      molA: molecules.find(m => m.entry_id === selectionForCompare[0]),
      molB: molecules.find(m => m.entry_id === selectionForCompare[1]),
    };
  }, [molecules, selectionForCompare]);

  // ── Comparador: toggle, máx 2, autoabrir modal cuando hay 2 (ver handleToggleCompare arriba) ──

  // ────────── ESTADOS DE PANTALLA ──────────

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--bg)] font-sans text-muted dark:bg-[#05080f] dark:text-slate-300">
        <div className="flex flex-col items-center gap-8">
          {/* ThinkingOrb: 12 puntos orbitando en canvas 2D, color purple-400 en processing */}
          <ThinkingOrb state="processing" size="lg" label={t("mx_sincronizando_bioteca")} />

          {/* Sub-line decorativo, mono uppercase, visible sobre dark */}
          <p className="font-mono text-xs uppercase tracking-[0.4em] text-dim opacity-60 dark:text-white/60 motion-safe:animate-latido">
            {t("pg_mx_cargando")}
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    const motorListo = !desktopRuntime || engine.state === "ready";
    const transporteConMotorListo =
      motorListo && error.kind === "request" && isTransportError(presentError(error, t));
    const titulo = error.kind === "engine"
      ? t("mx_error_conexion")
      : t("mx_error_carga");
    const detalle = error.kind === "engine" && !presentError(error, t)
      ? t("mx_motor_no_disponible")
      : transporteConMotorListo
        ? t("mx_error_motor_listo")
        : presentError(error, t);

    return (
      <div className="flex h-screen items-center justify-center bg-[var(--bg)] p-6 font-sans text-muted dark:bg-[#05080f] dark:text-slate-300">
        <div role="alert" className="w-full max-w-md rounded-2xl border border-red-300 bg-red-50 p-8 text-center shadow-2xl backdrop-blur-xl dark:border-red-500/20 dark:bg-red-950/20">
          <div className="mb-4 inline-block p-3 rounded-full bg-red-500/10 border border-red-500/30">
            <AlertCircle size={32} className="text-red-500" />
          </div>
          <h1 className="mb-2 text-lg font-black uppercase tracking-wider text-theme">{titulo}</h1>
          <p className="mb-6 text-xs leading-relaxed text-muted">{detalle}</p>
          <button
            onClick={async () => {
              setError(null);
              if (error.kind === "engine" || transporteConMotorListo) {
                await retryEngine();
              } else {
                loadMoldex();
              }
            }}
            className="w-full rounded-xl bg-red-600 py-3.5 text-xs font-black uppercase tracking-widest text-white dark:text-white transition-all hover:bg-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]"
          >
            {t("pg_mx_reintentar")}
          </button>
        </div>
      </div>
    );
  }

  if (molecules.length === 0) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--bg)] font-sans text-muted dark:bg-[#050508] dark:text-slate-300">

        {/* Glow ambiental purple radial (estático, llama desde el fondo) */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 50% 38%, rgba(147,51,234,0.08) 0%, transparent 55%)," +
              "radial-gradient(circle at 50% 100%, rgba(99,102,241,0.04) 0%, transparent 60%)",
          }}
        />

        {/* Estrellas decorativas: animación CSS (se detiene sola con la pestaña oculta y con «reducir movimiento») */}
        <div className="absolute inset-x-0 top-0 h-1/3 pointer-events-none">
          {[...Array(8)].map((_, i) => (
            <span
              key={i}
              data-testid="estrella-decorativa"
              className="absolute h-px w-px bg-purple-300 rotate-45 opacity-0 shadow-[0_0_6px_rgba(216,180,254,0.7)] motion-safe:animate-destello"
              style={{
                left: `${15 + (i * 9)}%`,
                top: `${8 + (i % 4) * 6}%`,
                animationDuration: `${3 + (i % 3)}s`,
                animationDelay: `${i * 0.6}s`,
              }}
            />
          ))}
        </div>

        {/* ─── Centro: ThinkingOrb idle + headline + ritual + CTA ─── */}
        <div className="relative z-10 flex flex-col items-center gap-8 max-w-2xl px-6 text-center">

          {/* ThinkingOrb idle — 12 dots sutiles, vibrando en grayscale */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          >
            <ThinkingOrb state="idle" size="lg" />
          </motion.div>

          {/* Headline */}
          <div className="space-y-3">
            <div className="flex items-center justify-center gap-3 text-dim dark:text-white/45">
              <span className="font-mono text-xs uppercase tracking-[0.5em]">✦</span>
              <motion.h1
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15, duration: 0.5 }}
                className="text-3xl font-black uppercase tracking-tight text-theme md:text-4xl"
              >
                {t("mx_bioteca_en_espera")}
              </motion.h1>
              <span className="font-mono text-xs uppercase tracking-[0.5em]">✦</span>
            </div>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="mx-auto max-w-md text-sm leading-relaxed text-muted md:text-[15px]"
            >
              {t("pg_mx_vacio")}
            </motion.p>
          </div>

          {/* Ritual: 3 pasos */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45, duration: 0.5 }}
            className="grid grid-cols-1 sm:grid-cols-3 gap-2 w-full max-w-xl py-2"
          >
            {[
              { n: "1", t: t("mx_paso_disena"), d: t("mx_paso_disena_d") },
              { n: "2", t: t("mx_paso_acopla"), d: t("mx_paso_acopla_vina_d") },
              { n: "3", t: t("mx_paso_guarda"), d: t("mx_paso_guarda_d") },
            ].map(s => (
              <div
                key={s.n}
                className="group rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4 backdrop-blur-sm transition-all hover:border-purple-500/30 dark:border-white/5 dark:bg-white/[0.015]"
              >
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{s.n}</span>
                  <span className="text-sm font-black uppercase tracking-tight text-theme">{s.t}</span>
                </div>
                <p className="font-mono text-xs uppercase tracking-wider text-dim">{s.d}</p>
              </div>
            ))}
          </motion.div>

          {/* CTA épico — estilo del botón Play de ProEvaluation */}
          <motion.a
            href="/evaluation"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.6, duration: 0.5, type: "spring", stiffness: 200, damping: 18 }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="group relative inline-flex items-center gap-3 rounded-xl border border-purple-400/30 bg-purple-600 px-8 py-4 font-mono text-xs font-bold uppercase tracking-[0.2em] text-white shadow-lg shadow-purple-950/50 transition-all hover:bg-purple-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]"
          >
            <Play size={14} className="fill-white" />
            {t("c_lanzar_pipeline")}
            <ChevronRight size={14} className="group-hover:translate-x-1 transition-transform" />
          </motion.a>
        </div>

        {/* Footer status mono */}
        <div className="absolute bottom-6 left-0 right-0 z-10 flex justify-center">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-dim">
            {t("pg_mx_cero_guardadas")}
          </p>
        </div>
      </div>
    );
  }

  // ────────── RENDER PRINCIPAL: estación de trabajo de escritorio ──────────
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-50 flex flex-col overflow-hidden bg-[var(--bg)] font-sans text-[var(--text)]"
      style={{ top: NAV_HEIGHT }}
    >
      <header className="hidden h-[72px] shrink-0 items-center justify-between gap-6 border-b border-[var(--border)] bg-[var(--bg-card)] px-8 md:flex">
        <div className="flex min-w-0 items-center gap-5">
          <div className="flex size-9 shrink-0 items-center justify-center border border-[var(--accent)] text-[var(--accent-strong)]"><FlaskConical size={18} /></div>
          <div className="min-w-0">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">{t("mx_subtitulo_bioteca")}</p>
            <h1 className="font-display text-xl font-bold leading-tight">Moldex</h1>
          </div>
          <div className="ml-5 min-w-0 border-l border-[var(--border)] pl-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-dim)]">{t("mx_molecula")}</p>
            <p className="truncate text-sm font-semibold text-[var(--text-secondary)]">{selectedMolecule ? nombreDeLaFicha(selectedMolecule) : "—"}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-dim)]">
          <span className="size-1.5 rounded-full bg-[var(--accent-strong)]" />
          {molecules.length}/{catalogTotal} {t(molecules.length === 1 ? "mx_molecula_cargada" : "mx_moleculas_cargadas")}
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1 flex-col md:flex-row">
      {/* El canvas tiene siempre el tamaño completo: los paneles se dibujan encima. Redimensionarlo al
          abrir/cerrar paneles reconstruía el framebuffer WebGL en cada fotograma de la animación. */}
      <div
        className="absolute inset-0 z-0 overflow-hidden"
        style={isMobile ? undefined : ({ "--viewer-inset-l": `${showLeftPanel ? leftWidth : 0}px`, "--viewer-inset-r": `${showRightPanel ? rightWidth : 0}px` } as CSSProperties)}
      >
        <MoleculeViewer3D
          proteinData={proteinData ?? undefined}
          poseData={poseData ?? undefined}
          height={Math.max(260, windowHeight - NAV_HEIGHT - (isMobile ? 0 : 72) - 76)}
          hotspots={viewerHotspots}
          hotspotsHit={viewerHotspotsHit}
          pocketFocus
          mobileTopOffset={false} // noOverlap: nosotros ya topamos por contenedor, no por offset absoluto
        />
        {loading3D && (
          <div role="status" className="pointer-events-none absolute inset-x-0 top-24 flex justify-center">
            <span className="border border-[var(--border-light)] bg-[var(--bg-card)] px-3 py-2 font-mono text-[11px] text-[var(--text-secondary)]">{t("pg_mx_cargando")}</span>
          </div>
        )}
        {viewerError && !loading3D && (
          <div role="alert" className="pointer-events-auto absolute inset-x-6 top-24 mx-auto max-w-md border border-[var(--border-light)] bg-[var(--bg-card)] p-5 text-center shadow-lg">
            <p className="text-xs leading-5 text-[var(--text-secondary)]">{t(selectedTaskId ? "mx_visor_archivos_error" : "rx_sin_identidad_corrida")}</p>
            <button type="button" onClick={() => setViewerRetry((n) => n + 1)} className="mt-4 cursor-pointer border border-[var(--accent)] px-3 py-2 text-xs font-bold text-[var(--accent-strong)] hover:bg-[var(--bg-secondary)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]">{t("mx_visor_reintentar")}</button>
          </div>
        )}
      </div>

      {/* Paneles y métricas sobre su propia superficie, sin tapar el canvas. */}
      <div className="relative z-10 flex min-h-0 flex-1 flex-col pointer-events-none md:flex-row">

        {/* Mobile Navigation Header (LIST/3D/INFO tabs) */}
        <div className="pointer-events-auto z-50 flex h-[60px] w-full items-center justify-between border-b border-[var(--border)] bg-[var(--bg-card)] px-6 md:hidden dark:border-slate-800/50 dark:bg-[#0a0f1d]">
          <h1 className="flex items-center gap-2 text-sm font-black tracking-tighter text-theme">
            <FlaskConical size={16} className="text-indigo-500" />
            <span className="uppercase">Moldex</span> <span className="rounded-full border border-indigo-500/35 bg-indigo-500/15 px-1.5 py-0.5 text-xs font-black uppercase tracking-widest text-indigo-600 dark:text-indigo-400">{t("mx_subtitulo_bioteca")}</span>
          </h1>
          <div className="flex gap-1">
            {MOBILE_TABS.map((btn) => {
              const Icon = btn.icon;
              return (
                <button
                  key={btn.id}
                  onClick={() => setActiveView(btn.id)}
                  aria-label={t(btn.clave)}
                  aria-pressed={activeView === btn.id}
                  className={`p-2 rounded-lg transition-all ${
                    activeView === btn.id
                      ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                      : "bg-[var(--bg-secondary)] text-muted dark:bg-slate-900 dark:text-slate-500"
                  } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/70`}
                >
                  <Icon size={14} />
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Sidebar Left: Biblioteca (Colapsable) ── */}
        <motion.aside
          initial={false}
          animate={isMobile ? {
            width: activeView === "list" ? "100%" : 0,
            opacity: activeView === "list" ? 1 : 0,
            x: activeView === "list" ? 0 : -800
          } : {
            width: leftWidth,
            opacity: 1,
            x: showLeftPanel ? 0 : -leftWidth
          }}
          transition={isMobile ? { type: "spring", stiffness: 300, damping: 35 } : PANEL_TRANSITION}
          inert={!isMobile && !showLeftPanel}
          className={`pointer-events-auto flex flex-col border-r border-[var(--border)] bg-[var(--bg-card)] ${
            isMobile ? 'absolute inset-x-0 bottom-0 top-[60px] z-40 overflow-y-auto'
                     : 'absolute inset-y-0 left-0 z-30 will-change-transform md:overflow-hidden'
          } ${isMobile && activeView !== "list" ? 'pointer-events-none' : ''}`}
        >
          <div className="min-w-0 shrink-0 border-b border-[var(--border)] p-5">
            <div className="mb-5 flex items-end justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">01 / Moldex</p>
                <h2 className="mt-1 font-display text-lg font-bold text-[var(--text)]">{t("mx_subtitulo_bioteca")}</h2>
              </div>
              <span className="font-mono text-xs tabular-nums text-[var(--text-dim)]">{filteredMolecules.length}/{molecules.length}</span>
            </div>

            <div className="space-y-3">
              <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)]" size={14} />
                <input
                  type="text"
                  placeholder={t("mx_buscar")}
                  aria-label={t("mx_buscar")}
                  className="w-full border border-[var(--border-light)] bg-[var(--bg)] py-2.5 pl-10 pr-3 text-xs text-[var(--text)] outline-none transition-colors placeholder:text-[var(--text-dim)] hover:border-[var(--accent)] focus-visible:border-[var(--accent-strong)] focus-visible:ring-1 focus-visible:ring-[var(--accent-strong)]"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="w-full overflow-x-auto pb-1 no-scrollbar">
                <div className="flex w-max items-center gap-1.5">
                  {targets.map(t => (
                    <button
                      key={t}
                      onClick={() => {
                        setTargetFilter(t);
                        // Re-selecciona la primera molécula filtrada
                        const newFiltered = molecules.filter(m => {
                          const name = m.name?.toLowerCase() || "";
                          const smiles = m.smiles || "";
                          const matchesSearch = name.includes(search.toLowerCase()) || smiles.includes(search);
                          const matchesTarget = t === "ALL" || m.target?.pdb_id === t;
                          return matchesSearch && matchesTarget;
                        });
                        if (newFiltered.length > 0) setSelectedId(newFiltered[0].entry_id);
                      }}
                      aria-pressed={targetFilter === t}
                      className={`min-h-8 flex-shrink-0 cursor-pointer border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] ${
                        targetFilter === t ? 'border-[var(--accent-strong)] bg-[var(--bg-secondary)] text-[var(--text)]'
                                           : 'border-[var(--border)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:border-[var(--border-light)]'
                      }`}
                    >
                      {t === "ALL" ? allTargetsLabel : t}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between border-t border-[var(--border)] pt-2">
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-dim)]">{t("mx_ordenar")}</span>
                <button
                  onClick={() => {
                    const nextSort = sortMode === "DATE_DESC" ? "SCORE_DESC"
                                   : sortMode === "SCORE_DESC" ? "SCORE_ASC" : "DATE_DESC";
                    setSortMode(nextSort);
                  }}
                  className="min-h-8 cursor-pointer border border-[var(--border)] bg-[var(--bg-card)] px-2.5 py-1 font-mono text-[10px] font-bold text-[var(--text-secondary)] transition-colors hover:border-[var(--border-light)] hover:text-[var(--text)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]"
                >
                  {sortModeLabel}
                </button>
              </div>
            </div>
          </div>

          <div className={`min-w-0 min-h-0 p-3 ${isMobile ? 'h-full' : 'flex-1'}`}>
            {filteredMolecules.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-8 text-center dark:border-white/5 dark:bg-slate-900/40"
              >
                <p className="font-mono text-xs text-muted">{t("mx_sin_resultados")}</p>
              </motion.div>
            ) : (
              <Virtuoso
                className="focus-visible:!outline-solid focus-visible:!outline-2 focus-visible:!outline-[var(--accent-strong)] focus-visible:!outline-offset-[-2px]"
                style={{ height: "100%" }}
                totalCount={filteredMolecules.length}
                data={filteredMolecules}
                increaseViewportBy={{ bottom: 300, top: 100 }}
                itemContent={(_, molecule) => (
                  <MoldexCard
                    key={molecule.entry_id}
                    molecule={molecule}
                    isSelected={selectedId === molecule.entry_id}
                    onClick={handleSelectMolecule}
                    onCompareToggle={handleToggleCompare}
                    isComparing={selectionForCompare.includes(molecule.entry_id)}
                  />
                )}
              />
            )}
          </div>
          {!isMobile && <MoldexUbicacion />}
        </motion.aside>

        {/* Toggle Left Button (chevron colapsa biblioteca) */}
        <div
          className="pointer-events-auto absolute top-1/2 z-40 hidden -translate-y-1/2 transition-transform duration-200 ease-out md:flex"
          style={{ left: leftWidth, transform: `translate(${showLeftPanel ? 0 : -leftWidth}px, -50%)` }}
        >
          <button
            onClick={() => setShowLeftPanel(!showLeftPanel)}
            className="flex h-16 w-6 cursor-pointer items-center justify-center border border-[var(--border-light)] bg-[var(--bg-card)] text-[var(--accent-strong)] transition-colors hover:bg-[var(--bg-secondary)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]"
            aria-label={showLeftPanel ? t("mx_ocultar_biblioteca") : t("mx_mostrar_biblioteca")}
          >
            <ChevronRight size={14} className={`transition-transform ${showLeftPanel ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Espacio Central del Visor */}
        <div
          className="pointer-events-none absolute inset-y-0 md:left-[var(--hud-l)] md:right-[var(--hud-r)]"
          style={isMobile ? undefined : ({ "--hud-l": `${showLeftPanel ? leftWidth : 0}px`, "--hud-r": `${showRightPanel ? rightWidth : 0}px` } as CSSProperties)}
        >
          {/* HUD Inferior (Info de Molécula activa) */}
          <AnimatePresence mode="wait">
            {((!isMobile && selectedId) || (isMobile && activeView === "3d" && selectedId)) && (
              <motion.div
                key={selectedId}
                initial={{ y: 12, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 12, opacity: 0 }}
                className="pointer-events-auto absolute bottom-4 left-4 right-4 md:bottom-[84px]"
              >
                <div className="mx-auto flex max-w-3xl flex-col gap-3 border border-[var(--border-light)] bg-[var(--bg-card)] px-4 py-3 shadow-lg md:flex-row md:items-center md:gap-5">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="border border-[var(--accent)] px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide text-[var(--accent-strong)]">{t("mx_sitio_receptor")}</span>
                      <h3 className="truncate font-display text-sm font-bold text-[var(--text)]">{selectedMolecule ? nombreDeLaFicha(selectedMolecule) : t("mx_molecula")}</h3>
                    </div>
                    <p className="hidden truncate font-mono text-[10px] text-[var(--text-dim)] md:block">{selectedMolecule?.smiles}</p>
                  </div>
                  <div className="flex items-center justify-between gap-5 border-t border-[var(--border)] pt-2 md:border-l md:border-t-0 md:pl-5 md:pt-0">
                    <div>
                      <p className="mb-1 font-mono text-[9px] font-bold uppercase tracking-wide text-[var(--text-dim)]">{t(selectedMolecule?.metrics?.affinity_origin === "vina" ? "mx_afinidad_observada" : "mx_afinidad_heredada")}</p>
                      <div className="font-display text-xl font-bold tabular-nums text-[var(--text)]">
                        {selectedMolecule?.metrics?.affinity !== null && selectedMolecule?.metrics?.affinity !== undefined
                          ? selectedMolecule.metrics.affinity.toFixed(1)
                          : "—"} <span className="font-mono text-[10px] font-normal text-[var(--text-secondary)]">kcal/mol</span>
                      </div>
                    </div>
                    <div>
                      <p className="mb-1 font-mono text-[9px] font-bold uppercase tracking-wide text-[var(--text-dim)]" title={t("mx_indice_compuesto_nota")}>{t("mx_indice_compuesto")}</p>
                      <div className="font-display text-xl font-bold tabular-nums text-[var(--accent-strong)]">
                        {selectedMolecule?.metrics?.score?.toFixed(1) ?? "—"}
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Toggle Right Button (chevron colapsa panel derecho) */}
        <div
          className="pointer-events-auto absolute top-1/2 z-40 hidden transition-transform duration-200 ease-out md:flex"
          style={{ right: rightWidth, transform: `translate(${showRightPanel ? 0 : rightWidth}px, -50%)` }}
        >
          <button
            onClick={() => setShowRightPanel(!showRightPanel)}
            className="flex h-16 w-6 cursor-pointer items-center justify-center border border-[var(--border-light)] bg-[var(--bg-card)] text-[var(--accent-strong)] transition-colors hover:bg-[var(--bg-secondary)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]"
            aria-label={showRightPanel ? t("mx_ocultar_perfil") : t("mx_mostrar_perfil")}
          >
            <ChevronRight size={14} className={`transition-transform ${showRightPanel ? '' : 'rotate-180'}`} />
          </button>
        </div>

        {/* ── Sidebar Right: Perfil Farmacocinético (Colapsable) ── */}
        <motion.aside
          initial={false}
          animate={isMobile ? {
            width: activeView === "info" ? "100%" : 0,
            opacity: activeView === "info" ? 1 : 0,
            x: activeView === "info" ? 0 : 1000
          } : {
            width: rightWidth,
            opacity: 1,
            x: showRightPanel ? 0 : rightWidth
          }}
          transition={isMobile ? { type: "spring", stiffness: 300, damping: 35 } : PANEL_TRANSITION}
          inert={!isMobile && !showRightPanel}
          className={`custom-scrollbar pointer-events-auto flex flex-col overflow-y-auto border-l border-[var(--border)] bg-[var(--bg-card)] p-5 ${
            isMobile ? 'absolute inset-x-0 bottom-0 top-[60px] z-40'
                     : 'absolute inset-y-0 right-0 z-30 will-change-transform'
          } ${isMobile && activeView !== "info" ? 'pointer-events-none' : ''}`}
        >
          <AnimatePresence mode="wait">
            <motion.div key={selectedId} initial={{ x: 12, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="min-w-0 space-y-7">

              <div className="border-b border-[var(--border)] pb-4">
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">02 / {t("mx_molecula")}</p>
                <h2 className="mt-1 truncate font-display text-lg font-bold text-[var(--text)]" title={selectedMolecule ? nombreDeLaFicha(selectedMolecule) : undefined}>{selectedMolecule ? nombreDeLaFicha(selectedMolecule) : t("mx_sin_nombre")}</h2>
                <p className="mt-1 font-mono text-[10px] text-[var(--text-dim)]">{selectedMolecule?.target?.pdb_id || "—"}</p>
                {selectedMolecule && <InsigniaDelCatalogo pdbId={selectedMolecule.target?.pdb_id} corrida={{ receptor_sha256: selectedMolecule.provenance?.receptor_sha256, docking_protocol: selectedMolecule.provenance?.docking_protocol, vina_random_seed: selectedMolecule.provenance?.random_seed }} />}
              </div>

              {/* MÓDULO 1: {t("pg_mx_contexto_target")} */}
              <section className="border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
                <h2 className="mb-4 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--accent-strong)]">
                  <Database size={14} /> {t("pg_mx_contexto_target")}
                </h2>
                <div className="space-y-3">
                  <div>
                    <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[var(--text-dim)]">{t("mx_proteina_receptora")}</p>
                    <p className="mt-1 text-sm font-semibold leading-tight text-[var(--text)]">{selectedMolecule?.target?.name || t("mx_sin_nombre")}</p>
                  </div>
                  <div className="flex items-center justify-between border-t border-[var(--border)] pt-3">
                    <div>
                      <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[var(--text-dim)]">{t("mx_correlacion_benchmark")}</p>
                      <p className="mt-1 font-mono text-xs text-[var(--text)]">{(() => {
                        const cal = calibracionDeLaFicha(selectedMolecule?.target);
                        return cal.medida ? t("mx_calibracion_medida", { rho: cal.rho, a: cal.a, b: cal.b, n: cal.n }) : t("mx_calibracion_sin_medida");
                      })()}</p>
                    </div>
                  </div>
                </div>
              </section>

              {/* MÓDULO 2: {t("pg_mx_auditoria")} */}
              <section>
                <h2 className="mb-3 flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-dim)]">
                  <AlertCircle size={14} className="text-[var(--categoria-corrigendum)]" /> {t("pg_mx_auditoria")}
                </h2>
                <div className="space-y-3">
                  {(selectedMolecule?.scientific_warnings?.length ?? 0) > 0 ? (
                    (selectedMolecule?.scientific_warnings ?? []).map((warning: string, i: number) => (
                      <div key={i} className="flex gap-3 border border-[var(--border)] bg-[var(--bg-secondary)] p-3 text-xs leading-relaxed text-[var(--text-secondary)]">
                        <div className="mt-1 flex-shrink-0 h-1.5 w-1.5 rounded-full bg-[var(--categoria-corrigendum)]" />
                        {warning}
                      </div>
                    ))
                  ) : (
                    <div className="border border-[var(--border)] bg-[var(--bg-secondary)] p-3 text-xs text-[var(--text-secondary)]">
                      {t("pg_mx_sin_advertencias")}
                    </div>
                  )}
                  {/* La auditoría de preparación vive en su pestaña: necesita el CASO que produjo
                      la corrida (sus inputs, su comprobación previa y sus decisiones), y Moldex
                      guarda corridas. Se pide por `task_id` y Preparación busca su caso. */}
                  <div className="border border-[var(--border)] bg-[var(--bg-secondary)] p-3">
                    {selectedTaskId ? (
                      <Link
                        href="/preparacion"
                        onClick={() => pedirPreparacion({ taskId: selectedTaskId, etiqueta: selectedMolecule ? nombreDeLaFicha(selectedMolecule) : undefined })}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--accent-strong)] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"
                      >
                        <ClipboardCheck size={13} aria-hidden="true" />
                        {t("pg_mx_ver_preparacion")}
                      </Link>
                    ) : (
                      <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{t("pg_mx_preparacion_sin_corrida")}</p>
                    )}
                    <p className="mt-1 text-[11px] leading-5 text-[var(--text-dim)]">{t("pg_mx_preparacion_alcance")}</p>
                  </div>
                </div>
              </section>

              {/* MÓDULO 3: PERFIL FARMACOCINÉTICO */}
              <section>
                <div className="mb-3 flex items-center justify-between gap-2">
                  <h2 className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-dim)]">
                    <Activity size={14} className="text-[var(--accent-strong)]" /> <span>{t("mx_descriptores_reglas")}</span>
                  </h2>
                  <div className="flex gap-1">
                    {selectedMolecule?.metrics?.lipinski_pass && (
                      <span className="border border-[var(--border)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--categoria-hallazgo)]">Lipinski</span>
                    )}
                    {selectedMolecule?.metrics?.veber_pass && (
                      <span className="border border-[var(--border)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--categoria-medicion)]">Veber</span>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: t("mx_lipofilia"),  value: selectedMolecule?.metrics?.log_p?.toFixed(2) ?? "—",                         unit: "LogP" },
                    { label: t("mx_masa"),       value: selectedMolecule?.metrics?.mw?.toFixed(0) ?? "—",                             unit: "Da" },
                    { label: t("mx_polaridad"),  value: selectedMolecule?.metrics?.tpsa?.toFixed(1) ?? "—",                            unit: "Å²" },
                    // SCI-A-010: sin análisis no hay cero que enseñar.
                    { label: t("mx_hotspots"),   value: Array.isArray(selectedMolecule?.hotspots_hit) ? `${selectedMolecule.hotspots_hit.length}/${Array.isArray(selectedMolecule?.target?.hotspots) ? selectedMolecule.target.hotspots.length : 0}` : "—", unit: Array.isArray(selectedMolecule?.hotspots_hit) ? t("mx_hits_unidad") : t("mx_hits_no_evaluado") },
                    // CL-GNN, no `gnn_score` (RTMScore, que la app instalada nunca produce).
                    // Cómo se enseña y por qué: `presentarClgnn` en lib/moldex.ts.
                    { label: t("mx_senal_clgnn"), value: presentarClgnn(selectedMolecule?.metrics?.clgnn_score).valor, unit: t(presentarClgnn(selectedMolecule?.metrics?.clgnn_score).condicion) },
                    { label: "Lipinski",   value: selectedMolecule?.metrics?.lipinski_pass === null ? "—" : selectedMolecule?.metrics?.lipinski_pass ? t("mx_cumple") : t("mx_no_cumple"),        unit: t("mx_unidad_regla") },
                  ].map(stat => (
                    <div key={stat.label} className="min-h-20 border border-[var(--border)] bg-[var(--bg-secondary)] p-3">
                      <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-wide text-[var(--text-dim)]">{stat.label}</p>
                      <p className="font-display text-base font-bold text-[var(--text)]">{stat.value} <span className="ml-1 font-mono text-[10px] font-normal text-[var(--text-secondary)]">{stat.unit}</span></p>
                    </div>
                  ))}
                </div>
              </section>

              {/* MÓDULO 4: EVIDENCIA BLOCKCHAIN */}
              <section>
                <div className="border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
                  <h2 className="mb-3 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--accent-strong)]">{t("mx_registro_integridad")}</h2>
                  {/* MOLDEX-UX-008: el modal y el PDF ya decían esto; la ficha,
                      que es lo que se ve todo el tiempo, no lo decía. */}
                  <p className="mb-4 text-xs leading-relaxed text-[var(--text-secondary)]">
                    {t("mx_alcance_registro")}
                  </p>
                  {selectedMolecule?.blockchain?.tx_signature && (
                    <p className="mb-4 text-xs font-bold uppercase tracking-widest text-muted">
                      {t("auto_342a5736290d")} {redDelSello ?? t("auto_ee1fa5bbd7ed")}
                      {esRedDePruebas(redDelSello) && (
                        <span className="ml-2 rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-400">
                          {t("pg_mx_red_pruebas")}
                        </span>
                      )}
                    </p>
                  )}

                  {selectedMolecule?.blockchain?.tx_signature ? (
                    <>
                      <div className="mb-4 break-all border border-[var(--border)] bg-[var(--bg-card)] p-3 font-mono text-[10px] leading-relaxed text-[var(--text-secondary)]">
                        {selectedMolecule.blockchain.tx_signature}
                      </div>
                      {/* MOLDEX-SCI-001: si la corrida cambió después de sellar,
                          el lector tiene que ver ambas cifras y saber cuál
                          respalda la cadena. */}
                      {leerSello(selectedMolecule.blockchain) === "corrida-anterior" && (
                        <div
                          role="alert"
                          className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-50 p-4 text-left text-xs leading-relaxed text-amber-900 dark:bg-amber-500/10 dark:text-amber-200/90"
                        >
                          <p className="mb-2 font-black uppercase tracking-widest text-amber-800 dark:text-amber-400">
                            {t("mx_sello_desfasado")}
                          </p>
                          <p>
                            {t("auto_d789b996261e")}{" "}
                            <b>{selectedMolecule.blockchain.certified_total_score?.toFixed(1) ?? "—"}</b>{" "}
                            {t("auto_faf5a356627c")}{" "}
                            <b>{selectedMolecule.metrics?.score?.toFixed(1) ?? "—"}</b>{t("pg_mx_recibo_otra_corrida")}
                          </p>
                        </div>
                      )}
                      {leerSello(selectedMolecule.blockchain) === "indeterminado" && (
                        <div
                          role="alert"
                          className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-50 p-4 text-left text-xs leading-relaxed text-amber-900 dark:bg-amber-500/10 dark:text-amber-200/90"
                        >
                          <p className="mb-2 font-black uppercase tracking-widest text-amber-800 dark:text-amber-400">
                            {t("pg_mx_sello_sin_corrida")}
                          </p>
                          <p>
                            {t("pg_mx_recibo_sin_procedencia")}
                          </p>
                        </div>
                      )}
                      <ExternalLink
                        href={urlDelExplorador(selectedMolecule.blockchain.tx_signature, redDelSello)}
                        className="mb-3 flex min-h-10 w-full items-center justify-center gap-2 bg-[var(--accent-strong)] px-3 py-2 text-xs font-bold text-[var(--bg)] transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"
                      >
                        <FlaskConical size={14} /> <span className="uppercase">{t("mx_verificar_solana")}</span>
                      </ExternalLink>
                    </>
                  ) : (
                    <>
                      <div className="mb-4 break-all border border-[var(--border)] bg-[var(--bg-card)] p-3 font-mono text-[10px] leading-relaxed text-[var(--text-secondary)]">
                        {t("mx_token_local")}
                      </div>
                      <button
                        onClick={() => setShowCertificationModal(true)}
                        className="mb-3 flex min-h-10 w-full cursor-pointer items-center justify-center gap-2 bg-[var(--accent-strong)] px-3 py-2 text-xs font-bold text-[var(--bg)] transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"
                      >
                        <Database size={14} /> <span className="uppercase">{t("mx_registrar_solana")}</span>
                      </button>
                    </>
                  )}

                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowPdfViewer(true)}
                      className="flex min-h-9 flex-1 cursor-pointer items-center justify-center gap-2 border border-[var(--border-light)] bg-[var(--bg-card)] px-2 py-2 text-[10px] font-bold text-[var(--text)] transition-colors hover:border-[var(--accent)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]"
                    >
                      <Eye size={14} /> <span className="uppercase">{t("mx_ver_reporte")}</span>
                    </button>
                    {/* MOLDEX-INT-006: era un `<a href>` crudo. El Bearer vive
                        en el envoltorio de fetch y una navegación no lo lleva,
                        así que para una cuenta real la descarga fallaba. */}
                    <button
                      type="button"
                      disabled={!selectedId || descargando !== null}
                      onClick={() => descargar("pdf")}
                      className="flex min-h-9 flex-1 cursor-pointer items-center justify-center gap-2 border border-[var(--border-light)] bg-[var(--bg-card)] px-2 py-2 text-[10px] font-bold text-[var(--text)] transition-colors hover:border-[var(--accent)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {descargando === "pdf" ? t("auto_bdd6a9ac7cec") : t("mx_descargar_recibo_pdf")}
                    </button>
                  </div>

                  <button
                    type="button"
                    disabled={!selectedId || descargando !== null}
                    onClick={() => descargar("complejo")}
                    className="mt-2 flex min-h-9 w-full cursor-pointer items-center justify-center gap-2 border border-[var(--border-light)] bg-[var(--bg-card)] px-3 py-2 text-[10px] font-bold text-[var(--text)] transition-colors hover:border-[var(--accent)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Box size={14} />
                    {descargando === "complejo" ? t("auto_bdd6a9ac7cec") : t("mx_descargar_complejo_pdb")}
                  </button>
                </div>
              </section>

            </motion.div>
          </AnimatePresence>
        </motion.aside>
      </div>
      </div>

      {/* ── Comparador Modal (cuando 2 moléculas seleccionadas) ── */}
      {compareMode && compareMols.molA && compareMols.molB && (
        <MolecularComparison
          molA={compareMols.molA}
          molB={compareMols.molB}
          onClose={() => { setCompareMode(false); setSelectionForCompare([]); }}
        />
      )}

      {/* Modal Visor PDF */}
      {showPdfViewer && selectedMolecule && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in"
          onClick={() => setShowPdfViewer(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="moldex-report-title"
            className="relative flex h-[85vh] w-full max-w-5xl animate-in flex-col rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] shadow-2xl zoom-in-95 dark:border-slate-800 dark:bg-[#0f1015]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between rounded-t-2xl border-b border-[var(--border)] bg-[var(--bg-secondary)] p-4 dark:border-slate-800 dark:bg-[#0a0a0a]">
              <div className="flex items-center gap-3">
                <span className="text-xl">📄</span>
                <h2 id="moldex-report-title" className="text-lg font-bold tracking-wide text-theme">{t("mx_reporte_cientifico")}</h2>
              </div>
              <button
                onClick={() => setShowPdfViewer(false)}
                aria-label={t("mx_cerrar_reporte")}
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--bg)] text-muted transition-colors hover:text-theme focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/70 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-hidden p-4">
              <PDFReportViewer
                moleculeId={selectedMolecule.id}
                taskId={selectedMolecule.provenance?.task_id ?? null}
                isCertified={!!selectedMolecule?.blockchain?.tx_signature}
                onCertify={handleCertificationRecorded}
              />
            </div>
          </div>
        </div>
      )}

      {showCertificationModal && selectedMolecule && (
        <CertificationModal
          moleculeId={selectedMolecule.id}
          taskId={selectedMolecule.provenance?.task_id ?? null}
          onClose={() => setShowCertificationModal(false)}
          onSuccess={handleCertificationRecorded}
        />
      )}
    </div>
  );
}
