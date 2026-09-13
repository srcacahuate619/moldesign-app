"use client";

import { useEffect, useState, useMemo, useCallback, useRef } from "react";
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
  ALCANCE_DEL_SELLO,
  type MoldexMolecule,
} from "../../lib/moldex";
import { useApiUrl } from "../../hooks/useApiUrl";
import { useKeepAliveActive } from "../../context/KeepAliveContext";
import { MoleculeViewer3D } from "../../components/MoleculeViewer3D";
import MoldexCard from "../../components/MoldexCard";
import MolecularComparison from "../../components/MolecularComparison";
import { PDFReportViewer } from "../../components/PDFReportViewer";
import { CertificationModal, type CertificationSuccess } from "../../components/CertificationModal";
import { ThinkingOrb } from "../../components/ui/ThinkingOrb";
import { Virtuoso } from "react-virtuoso";

import { Search, ShieldCheck, Activity, Info, ChevronRight, Database, Box, FlaskConical, AlertCircle, Eye, Play } from "lucide-react";

import { ExternalLink } from "@/components/ui/ExternalLink";
// ─────────────────────────────────────────────────────────────────────
// MOLDEX — Bioteca del Laboratorio
// Layout: visor 3Dmol a pantalla completa + 2 paneles flotantes colapsables
//   (izquierda = biblioteca de moléculas, derecha = perfil farmacocinético)
//   + HUD inferior con affinity/score + modal comparador + modal PDF
// Adaptado del repo srcacahuate619/moldesign-app (frontend/app/moldex/page.tsx)
// Cambios desktop: sin interfaceMode (una sola UI), top-14 (nav h-14=56px),
// 3Dmol cargado local en app/layout.tsx, base de API resuelta por `useApiUrl`.
// ─────────────────────────────────────────────────────────────────────

const NAV_HEIGHT = 56; // h-14 del Navigation.tsx

export default function MoldexPage() {
  // Los enlaces de descarga se construyen EN RENDER, así que no pueden esperar
  // a una promesa: el hook devuelve null hasta que Rust confirma el puerto y
  // vuelve a pintar entonces. Mientras tanto los enlaces quedan inertes; usar
  // 8000 como conjetura podría enviarlos a otro producto instalado en el equipo.
  const apiUrl = useApiUrl();
  // FIX (keep-alive): /moldex vive en el DOM sin desmontarse (KeepAliveLayout).
  // useKeepAliveActive() es true solo cuando esta ruta es la activa. Con esto
  // recargamos la lista cada vez que el usuario VUELVE a Moldex, no solo al
  // primer montaje — así las moléculas recién guardadas en /evaluation aparecen.
  const isActive = useKeepAliveActive();
  const [molecules, setMolecules] = useState<MoldexMolecule[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [targetFilter, setTargetFilter] = useState("ALL");
  const [sortMode, setSortMode] = useState<"DATE_DESC" | "SCORE_DESC" | "SCORE_ASC">("DATE_DESC");

  // Panel States (colapsables)
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showRightPanel, setShowRightPanel] = useState(true);

  // Comparison state — "el comparador"
  const [compareMode, setCompareMode] = useState(false);
  const [selectionForCompare, setSelectionForCompare] = useState<string[]>([]);

  // 3D View state
  const [proteinData, setProteinData] = useState<string | null>(null);
  const [poseData, setPoseData] = useState<string | null>(null);
  const [loading3D, setLoading3D] = useState(false);
  const [activeView, setActiveView] = useState<'LIST' | '3D' | 'INFO'>('LIST');
  const [windowHeight, setWindowHeight] = useState(1000);
  const [showCertificationModal, setShowCertificationModal] = useState(false);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    if (!selectedId) return;
    setDescargando(que);
    setError(null);
    try {
      if (que === "pdf") await downloadCertificate(selectedId);
      else await downloadComplexFile(selectedId);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "No se pudo completar la descarga.",
      );
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
    setMolecules(prev => prev.map(m => m.id === selectedId
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
      setIsMobile(window.innerWidth < 768);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // ── Carga inicial de moléculas desde getMoldex() — limitado a 100 para memoria ──
  // `preferSelectId`: si llega (ej: desde el handler de `moldex:invalidated`,
  // cuando el usuario recién guardó una molécula en /evaluation), se respeta
  // como selectedId final SIEMPRE que esa molécula exista en la respuesta.
  // Sin esto, `setSelectedId(normalized[0].id)` pisaría la selección que el
  // handler ya decidió, rompiendo la UX "acabo de guardar, llévame a ella".
  const loadMoldex = useCallback((preferSelectId?: string) => {
    setLoading(true);
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
          hotspots_hit: normalizeArr(m.hotspots_hit),
          target: m.target
            ? { ...m.target, hotspots: normalizeArr(m.target.hotspots) }
            : m.target,
        }));
        setMolecules(normalized);
        if (normalized.length > 0) {
          // Si el caller pidió una molécula concreta (recién guardada), la
          // respetamos solo si está en la respuesta. Si no está (típicamente
          // porque el backend todavía no la commiteó — no debería pasar si el
          // CustomEvent se emite post-await), caemos al default: la primera.
          const wantsId = preferSelectId
            && normalized.some((m) => m.id === preferSelectId);
          setSelectedId(wantsId ? preferSelectId! : normalized[0].id);
        }
      })
      .catch((err) => {
        console.error("Error al cargar la bioteca:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  // Cargar al montar Y cada vez que la página se vuelve activa (keep-alive):
  // sin esto, guardar una molécula en /evaluation y volver a /moldex mostraba
  // la lista vieja del primer montaje.
  useEffect(() => {
    loadMoldex();
  }, [loadMoldex, isActive]);

  // Listener cross-route: cuando /evaluation (o cualquier otra ruta) hace
  // saveMolecule exitosamente, emite `moldex:invalidated` con detail.moleculeId.
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
      loadMoldex(detail?.moleculeId);
    };
    window.addEventListener("moldex:invalidated", handler);
    return () => window.removeEventListener("moldex:invalidated", handler);
  }, [loadMoldex]);

  const selectedMolecule = useMemo(() =>
    molecules.find(m => m.id === selectedId),
  [selectedId, molecules]);

  // FIX (rendimiento): memoizar props del visor 3D. `hotspots.map(...)` creaba
  // un array NUEVO en cada render del padre → MoleculeViewer3D (ahora memo)
  // re-renderizaba su árbol WebGL por CUALQUIER cambio de estado (buscar,
  // filtrar, colapsar panel) → jank en toda la página.
  const viewerHotspots = useMemo(
    () => (Array.isArray(selectedMolecule?.target?.hotspots) ? selectedMolecule.target.hotspots : []).map((h: any) => h.name),
    [selectedMolecule]
  );
  const viewerHotspotsHit = useMemo(
    () => selectedMolecule?.hotspots_hit || [],
    [selectedMolecule]
  );

  // Callbacks estables para el Virtuoso/MoldexCard memoizado.
  const handleSelectMolecule = useCallback((id: string) => {
    setSelectedId(id);
    if (typeof window !== "undefined" && window.innerWidth < 768) setActiveView('3D');
  }, []);
  const handleToggleCompare = useCallback((id: string) => {
    setSelectionForCompare(prev => {
      const next = prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id].slice(-2);
      if (next.length === 2) setTimeout(() => setCompareMode(true), 0);
      return next;
    });
  }, []);

  // ── Cargar proteinData + poseData 3D al cambiar selección ──
  // FIX (rendimiento): depende SOLO de selectedId (primitivo). Antes dependía
  // de selectedMolecule (objeto que cambia de referencia con cada re-fetch de
  // la lista), lo que re-descargaba protein/pose cada vez que la página se
  // reactivaba aunque la selección no hubiera cambiado.
  useEffect(() => {
    if (!selectedId) return;
    setLoading3D(true);
    setPoseData(null); // clear previous → spinner visible
    Promise.all([
      getProteinFile(selectedId),
      getPoseFile(selectedId)
    ]).then(([protein, pose]) => {
      setProteinData(protein);
      setPoseData(pose);
    }).catch(err => {
      console.error("Error loading 3D data:", err);
    }).finally(() => setLoading3D(false));
  }, [selectedId]);

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

  // Moléculas del comparador memoizadas (refs estables para el memo de
  // MolecularComparison; antes se recomputaban con .find() en cada render).
  const compareMols = useMemo(() => {
    if (selectionForCompare.length !== 2) return { molA: undefined, molB: undefined };
    return {
      molA: molecules.find(m => m.id === selectionForCompare[0]),
      molB: molecules.find(m => m.id === selectionForCompare[1]),
    };
  }, [molecules, selectionForCompare]);

  // ── Comparador: toggle, máx 2, autoabrir modal cuando hay 2 (ver handleToggleCompare arriba) ──

  // ────────── ESTADOS DE PANTALLA ──────────

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#05080f] text-slate-300 font-sans">
        <div className="flex flex-col items-center gap-8">
          {/* ThinkingOrb: 12 puntos orbitando en canvas 2D, color purple-400 en processing */}
          <ThinkingOrb state="processing" size="lg" label="SINCRONIZANDO BIOTECA" />

          {/* Sub-line decorativo, mono uppercase, visible sobre dark */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: [0.4, 0.75, 0.4] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
            className="text-[10px] font-mono tracking-[0.4em] uppercase text-white/45"
          >
            cargando moléculas · modo molecular · v 2.0
          </motion.p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#05080f] text-slate-300 font-sans p-6">
        <div className="max-w-md w-full rounded-2xl border border-red-500/20 bg-red-950/20 p-8 text-center backdrop-blur-xl shadow-2xl">
          <div className="mb-4 inline-block p-3 rounded-full bg-red-500/10 border border-red-500/30">
            <AlertCircle size={32} className="text-red-500" />
          </div>
          <h2 className="text-lg font-black text-white uppercase tracking-wider mb-2">Error de Conexión</h2>
          <p className="text-xs text-slate-400 leading-relaxed mb-6">{error}</p>
          <button
            onClick={() => { setError(null); loadMoldex(); }}
            className="w-full text-[10px] font-black text-white bg-red-600 hover:bg-red-500 py-3.5 rounded-xl transition-all uppercase tracking-widest"
          >
            Reintentar Conexión
          </button>
        </div>
      </div>
    );
  }

  if (molecules.length === 0) {
    return (
      <div className="relative min-h-screen bg-[#050508] text-slate-300 font-sans flex items-center justify-center overflow-hidden">

        {/* Glow ambiental purple radial (estático, llama desde el fondo) */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 50% 38%, rgba(147,51,234,0.08) 0%, transparent 55%)," +
              "radial-gradient(circle at 50% 100%, rgba(99,102,241,0.04) 0%, transparent 60%)",
          }}
        />

        {/* Particles decorativas "stars" sutiles arriba */}
        <div className="absolute inset-x-0 top-0 h-1/3 pointer-events-none">
          {[...Array(8)].map((_, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 0.5, 0] }}
              transition={{
                duration: 3 + (i % 3),
                repeat: Infinity,
                delay: i * 0.6,
                ease: "easeInOut",
              }}
              className="absolute h-px w-px bg-purple-300 rotate-45 shadow-[0_0_6px_rgba(216,180,254,0.7)]"
              style={{
                left: `${15 + (i * 9)}%`,
                top: `${8 + (i % 4) * 6}%`,
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
            <div className="flex items-center justify-center gap-3 text-white/30">
              <span className="text-[10px] font-mono tracking-[0.5em] uppercase">✦</span>
              <motion.h1
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15, duration: 0.5 }}
                className="text-3xl md:text-4xl font-black tracking-tight text-white uppercase"
              >
                Bioteca en Stand-By
              </motion.h1>
              <span className="text-[10px] font-mono tracking-[0.5em] uppercase">✦</span>
            </div>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="text-sm md:text-[15px] text-white/40 leading-relaxed max-w-md mx-auto"
            >
              Tu colección molecular te espera.
              Cada molécula guardada es una conquista —
              un docking realizado, hotspots impactados,
              un certificado en la blockchain.
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
              { n: "1", t: "Diseña", d: "con el Ketcher Editor" },
              { n: "2", t: "Acopla", d: "Vina + XGBoost + GNN" },
              { n: "3", t: "Guarda", d: "salva en tu bioteca" },
            ].map(s => (
              <div
                key={s.n}
                className="rounded-xl border border-white/5 bg-white/[0.015] p-4 backdrop-blur-sm hover:border-purple-500/30 transition-all group"
              >
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-[10px] font-mono font-bold text-purple-400">{s.n}</span>
                  <span className="text-sm font-black text-white tracking-tight uppercase">{s.t}</span>
                </div>
                <p className="text-[10px] font-mono text-white/30 uppercase tracking-wider">{s.d}</p>
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
            className="group relative inline-flex items-center gap-3 px-8 py-4 rounded-xl font-mono text-xs font-bold uppercase tracking-[0.2em] text-white bg-purple-600 hover:bg-purple-500 shadow-lg shadow-purple-950/50 border border-purple-400/30 transition-all"
          >
            <Play size={14} className="fill-white" />
            Lanzar Pipeline
            <ChevronRight size={14} className="group-hover:translate-x-1 transition-transform" />
          </motion.a>
        </div>

        {/* Footer status mono */}
        <div className="absolute bottom-6 left-0 right-0 z-10 flex justify-center">
          <p className="text-[10px] font-mono tracking-[0.3em] uppercase text-white/15">
            0 moléculas guardadas · bioteca local · v 2.0
          </p>
        </div>
      </div>
    );
  }

  // ────────── RENDER PRINCIPAL: overlay layout ──────────
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-50 bg-[#05080f] text-slate-300 font-sans selection:bg-indigo-500/30 overflow-hidden"
      style={{ top: NAV_HEIGHT }}
    >

      {/* 3D Viewport: El Protagonista (Full Background) */}
      <div className="absolute inset-0 z-0">
        <MoleculeViewer3D
          proteinData={proteinData ?? undefined}
          poseData={poseData ?? undefined}
          height={windowHeight - NAV_HEIGHT}
          hotspots={viewerHotspots}
          hotspotsHit={viewerHotspotsHit}
          mobileTopOffset={false} // noOverlap: nosotros ya topamos por contenedor, no por offset absoluto
        />
      </div>

      {/* Capa de Interfaz (Overlays Flotantes) */}
      <div className="absolute inset-0 z-10 pointer-events-none flex flex-col md:flex-row">

        {/* Mobile Navigation Header (LIST/3D/INFO tabs) */}
        <div className="h-[60px] flex md:hidden items-center justify-between px-6 bg-[#0a0f1d] border-b border-slate-800/50 z-50 pointer-events-auto w-full">
          <h1 className="text-sm font-black tracking-tighter text-white flex items-center gap-2">
            <FlaskConical size={16} className="text-indigo-500" />
            MOLDEX <span className="text-[8px] bg-indigo-500/15 text-indigo-400 px-1.5 py-0.5 rounded-full border border-indigo-500/35 tracking-widest uppercase font-black">Bioteca</span>
          </h1>
          <div className="flex gap-1">
            {([
              { id: 'LIST', icon: <Database size={14} /> },
              { id: '3D', icon: <Box size={14} /> },
              { id: 'INFO', icon: <Info size={14} /> }
            ] as const).map((btn) => (
              <button
                key={btn.id}
                onClick={() => setActiveView(btn.id)}
                className={`p-2 rounded-lg transition-all ${
                  activeView === btn.id
                    ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'
                    : 'bg-slate-900 text-slate-500'
                }`}
              >
                {btn.icon}
              </button>
            ))}
          </div>
        </div>

        {/* ── Sidebar Left: Biblioteca (Colapsable) ── */}
        <motion.aside
          initial={false}
          animate={isMobile ? {
            width: activeView === 'LIST' ? "100%" : 0,
            opacity: activeView === 'LIST' ? 1 : 0,
            x: activeView === 'LIST' ? 0 : -800
          } : {
            width: showLeftPanel ? 320 : 0,
            opacity: showLeftPanel ? 1 : 0,
            x: showLeftPanel ? 0 : -320
          }}
          transition={{ type: "spring", stiffness: 300, damping: 35 }}
          className={`border-r border-white/5 bg-[#0a0f1d]/95 md:bg-[#0a0f1d]/40 backdrop-blur-xl pointer-events-auto flex flex-col ${
            isMobile ? 'absolute inset-x-0 bottom-0 top-[60px] z-40 overflow-y-auto'
                     : 'h-full md:overflow-hidden'
          } ${isMobile && activeView !== 'LIST' ? 'pointer-events-none' : ''}`}
        >
          <div className="p-8 border-b border-white/5 min-w-[320px] shrink-0">
            <h1 className="text-xl font-black tracking-tighter text-white flex items-center gap-2 mb-8">
              <FlaskConical size={24} className="text-indigo-500" />
              MOLDEX <span className="text-[10px] bg-indigo-500/15 text-indigo-400 px-2 py-0.5 rounded-full border border-indigo-500/35 tracking-widest uppercase font-black">Bioteca</span>
            </h1>

            <div className="space-y-4">
              <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                <input
                  type="text"
                  placeholder="Buscar molécula..."
                  className="w-full rounded-2xl bg-black/40 border border-white/10 py-3 pl-10 pr-4 text-xs text-slate-200 outline-none focus:border-indigo-500/50 transition-all"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="flex items-center justify-between gap-2 overflow-x-auto pb-2 no-scrollbar w-full">
                <div className="flex items-center gap-2">
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
                        if (newFiltered.length > 0) setSelectedId(newFiltered[0].id);
                      }}
                      className={`flex-shrink-0 rounded-full px-4 py-2 text-[9px] font-black uppercase tracking-widest border transition-all ${
                        targetFilter === t ? 'bg-indigo-500 border-indigo-400 text-white'
                                           : 'bg-black/40 border-white/5 text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>

                <button
                  onClick={() => {
                    const nextSort = sortMode === "DATE_DESC" ? "SCORE_DESC"
                                   : sortMode === "SCORE_DESC" ? "SCORE_ASC" : "DATE_DESC";
                    setSortMode(nextSort);
                  }}
                  className="flex-shrink-0 flex items-center gap-1 rounded-full px-4 py-2 text-[9px] font-black uppercase tracking-widest border border-white/5 bg-black/40 text-slate-400 hover:text-slate-200 transition-all ml-auto"
                >
                  {sortMode === "DATE_DESC" ? "🕒 RECIENTES"
                   : sortMode === "SCORE_DESC" ? "⬇️ MAYOR SCORE"
                   : "⬆️ MENOR SCORE"}
                </button>
              </div>
            </div>
          </div>

          <div className={`p-6 min-w-[320px] ${isMobile ? '' : 'flex-1'}`} style={{ height: "100%" }}>
            {filteredMolecules.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center p-8 border border-white/5 rounded-2xl bg-slate-900/40"
              >
                <p className="text-xs text-slate-500 font-mono">No se encontraron moléculas con esos filtros.</p>
              </motion.div>
            ) : (
              <Virtuoso
                style={{ height: "100%" }}
                totalCount={filteredMolecules.length}
                data={filteredMolecules}
                increaseViewportBy={{ bottom: 300, top: 100 }}
                itemContent={(_, molecule) => (
                  <MoldexCard
                    key={molecule.id}
                    molecule={molecule}
                    isSelected={selectedId === molecule.id}
                    onClick={handleSelectMolecule}
                    onCompareToggle={handleToggleCompare}
                    isComparing={selectionForCompare.includes(molecule.id)}
                  />
                )}
              />
            )}
          </div>
        </motion.aside>

        {/* Toggle Left Button (chevron colapsa biblioteca) */}
        <div className="hidden md:flex items-center z-50 pointer-events-auto">
          <button
            onClick={() => setShowLeftPanel(!showLeftPanel)}
            className="h-16 w-6 bg-indigo-600/20 backdrop-blur-md border border-indigo-500/30 rounded-r-xl flex items-center justify-center text-indigo-400 hover:text-white transition-colors shadow-lg"
            aria-label={showLeftPanel ? "Ocultar biblioteca" : "Mostrar biblioteca"}
          >
            <ChevronRight size={14} className={`transition-transform ${showLeftPanel ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Espacio Central del Visor */}
        <div className="flex-1 relative pointer-events-none">
          {/* HUD Superior (title + brand) */}
          {!isMobile && (
            <div className="absolute top-8 left-8 right-8 flex items-start justify-between">
              <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4 pointer-events-auto">
                <div className="h-14 w-14 rounded-2xl bg-black/60 border border-white/10 flex items-center justify-center backdrop-blur-xl shadow-2xl">
                  <Box className="text-indigo-500" size={24} />
                </div>
                <div>
                  <p className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.3em] mb-1">PROTAGONISTA 3D</p>
                  <h2 className="text-2xl font-black text-white tracking-tighter">ESTÁNDAR CIENTÍFICO</h2>
                </div>
              </motion.div>
            </div>
          )}

          {/* HUD Inferior (Info de Molécula activa) */}
          <AnimatePresence mode="wait">
            {((!isMobile && selectedId) || (isMobile && activeView === '3D' && selectedId)) && (
              <motion.div
                key={selectedId}
                initial={{ y: 50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 50, opacity: 0 }}
                className={`absolute bottom-4 left-4 right-4 md:bottom-12 transition-all duration-300 ${
                  !isMobile
                    ? `${showLeftPanel ? 'left-[340px]' : 'left-12'} ${showRightPanel ? 'right-[420px]' : 'right-12'}`
                    : 'left-4 right-4'
                } pointer-events-auto`}
              >
                <div className="rounded-2xl md:rounded-[3rem] border border-white/10 bg-black/80 md:bg-black/60 px-6 py-4 md:px-10 md:py-6 backdrop-blur-2xl shadow-2xl max-w-sm md:max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-4 md:gap-16">
                  <div className="flex-1 min-w-0 w-full text-center md:text-left">
                    <div className="flex flex-col md:flex-row items-center gap-2 md:gap-4 mb-1 md:mb-2">
                      <span className="bg-indigo-500 text-white text-[8px] md:text-[10px] font-black px-2 py-0.5 md:px-3 md:py-1 rounded-full tracking-widest uppercase">Sitio del receptor</span>
                      <h3 className="text-xl md:text-3xl font-black text-white tracking-tighter truncate w-full md:w-auto">{selectedMolecule?.name || "Molécula"}</h3>
                    </div>
                    <p className="hidden md:block text-sm font-mono text-slate-500 truncate">{selectedMolecule?.smiles}</p>
                  </div>
                  <div className="flex items-center justify-between md:justify-end gap-8 md:gap-12 w-full md:w-auto border-t md:border-t-0 md:border-l border-white/10 pt-3 md:pt-0 md:pl-12">
                    <div className="text-left md:text-right">
                      <p className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest mb-0.5 md:mb-1">AFINIDAD</p>
                      <div className="text-2xl md:text-4xl font-black text-indigo-400 tabular-nums">
                        {selectedMolecule?.metrics?.affinity !== null && selectedMolecule?.metrics?.affinity !== undefined
                          ? selectedMolecule.metrics.affinity.toFixed(1)
                          : "—"} <span className="text-xs font-bold text-slate-600">kcal/mol</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest mb-0.5 md:mb-1">ÍNDICE COMPUESTO HISTÓRICO</p>
                      <div className="text-2xl md:text-4xl font-black tabular-nums text-indigo-300">
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
        <div className="hidden md:flex items-center z-50 pointer-events-auto">
          <button
            onClick={() => setShowRightPanel(!showRightPanel)}
            className="h-16 w-6 bg-indigo-600/20 backdrop-blur-md border border-indigo-500/30 rounded-l-xl flex items-center justify-center text-indigo-400 hover:text-white transition-colors shadow-lg"
            aria-label={showRightPanel ? "Ocultar perfil" : "Mostrar perfil"}
          >
            <ChevronRight size={14} className={`transition-transform ${showRightPanel ? '' : 'rotate-180'}`} />
          </button>
        </div>

        {/* ── Sidebar Right: Perfil Farmacocinético (Colapsable) ── */}
        <motion.aside
          initial={false}
          animate={isMobile ? {
            width: activeView === 'INFO' ? "100%" : 0,
            opacity: activeView === 'INFO' ? 1 : 0,
            x: activeView === 'INFO' ? 0 : 1000
          } : {
            width: showRightPanel ? 400 : 0,
            opacity: showRightPanel ? 1 : 0,
            x: showRightPanel ? 0 : 400
          }}
          transition={{ type: "spring", stiffness: 300, damping: 35 }}
          className={`border-l border-white/5 bg-[#0a0f1d]/95 md:bg-[#0a0f1d]/60 backdrop-blur-xl p-6 md:p-10 overflow-y-auto custom-scrollbar pointer-events-auto flex flex-col ${
            isMobile ? 'absolute inset-x-0 bottom-0 top-[60px] z-40'
                     : 'h-full'
          } ${isMobile && activeView !== 'INFO' ? 'pointer-events-none' : ''}`}
        >
          <AnimatePresence mode="wait">
            <motion.div key={selectedId} initial={{ x: 30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="space-y-10 min-w-[320px]">

              {/* MÓDULO 1: CONTEXTO DEL TARGET */}
              <section className="rounded-3xl bg-indigo-500/5 border border-indigo-500/20 p-6">
                <h4 className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-indigo-400 mb-4">
                  <Database size={14} /> CONTEXTO DEL TARGET
                </h4>
                <div className="space-y-3">
                  <div>
                    <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Proteína Receptora</p>
                    <p className="text-sm font-black text-white leading-tight">{selectedMolecule?.target?.name || "Sin Nombre"}</p>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-white/5">
                    <div>
                      <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Correlación del benchmark</p>
                      <p className="text-xs font-mono text-emerald-400">Spearman ρ = {selectedMolecule?.target?.spearman_rho?.toFixed(3) ?? "N/A"}</p>
                    </div>
                    <div className="h-10 w-10 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
                      <ShieldCheck size={18} className="text-emerald-500" />
                    </div>
                  </div>
                </div>
              </section>

              {/* MÓDULO 2: AUDITORÍA CIENTÍFICA */}
              <section>
                <h4 className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-slate-400 mb-6">
                  <AlertCircle size={16} className="text-amber-500" /> AUDITORÍA CIENTÍFICA
                </h4>
                <div className="space-y-3">
                  {(selectedMolecule?.scientific_warnings?.length ?? 0) > 0 ? (
                    (selectedMolecule?.scientific_warnings ?? []).map((warning: string, i: number) => (
                      <div key={i} className="flex gap-3 p-4 rounded-2xl bg-amber-500/5 border border-amber-500/10 text-[11px] leading-relaxed text-amber-200/70">
                        <div className="mt-1 flex-shrink-0 h-1.5 w-1.5 rounded-full bg-amber-500" />
                        {warning}
                      </div>
                    ))
                  ) : (
                    <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/10 text-[11px] text-emerald-400/70 italic text-center">
                      No hay advertencias registradas para esta corrida.
                    </div>
                  )}
                </div>
              </section>

              {/* MÓDULO 3: PERFIL FARMACOCINÉTICO */}
              <section>
                <div className="flex items-center justify-between mb-6">
                  <h4 className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-slate-400">
                    <Activity size={16} className="text-indigo-500" /> DESCRIPTORES Y REGLAS
                  </h4>
                  <div className="flex gap-1">
                    {selectedMolecule?.metrics?.lipinski_pass && (
                      <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">LIPINSKI</span>
                    )}
                    {selectedMolecule?.metrics?.veber_pass && (
                      <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">VEBER</span>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: "Lipofilia",  value: selectedMolecule?.metrics?.log_p?.toFixed(2) ?? "—",                         unit: "LogP" },
                    { label: "Masa",       value: selectedMolecule?.metrics?.mw?.toFixed(0) ?? "—",                             unit: "Da" },
                    { label: "Polaridad",  value: selectedMolecule?.metrics?.tpsa?.toFixed(1) ?? "—",                            unit: "Å²" },
                    { label: "Hotspots",   value: `${Array.isArray(selectedMolecule?.hotspots_hit) ? selectedMolecule.hotspots_hit.length : 0}/${Array.isArray(selectedMolecule?.target?.hotspots) ? selectedMolecule.target.hotspots.length : 0}`, unit: "HITS" },
                    { label: "Señal GNN (legacy)",     value: selectedMolecule?.metrics?.gnn_score !== null && selectedMolecule?.metrics?.gnn_score !== undefined ? selectedMolecule.metrics.gnn_score.toFixed(1) : "N/A", unit: "señal" },
                    { label: "Lipinski",   value: selectedMolecule?.metrics?.lipinski_pass === null ? "—" : selectedMolecule?.metrics?.lipinski_pass ? "Cumple" : "No cumple",        unit: "regla" },
                  ].map(stat => (
                    <div key={stat.label} className="rounded-2xl bg-black/40 p-4 border border-white/5 group hover:border-indigo-500/30 transition-all">
                      <p className="text-[8px] font-black text-slate-600 uppercase mb-1 tracking-widest">{stat.label}</p>
                      <p className="text-lg font-black text-slate-200">{stat.value} <span className="text-[10px] text-slate-600 ml-1">{stat.unit}</span></p>
                    </div>
                  ))}
                </div>
              </section>

              {/* MÓDULO 4: EVIDENCIA BLOCKCHAIN */}
              <section>
                <div className="rounded-[2.5rem] bg-gradient-to-br from-indigo-600/20 to-transparent border border-indigo-500/20 p-8 text-center">
                  <p className="text-[9px] font-black text-indigo-400 uppercase tracking-[0.4em] mb-2">Registro de integridad</p>
                  {/* MOLDEX-UX-008: el modal y el PDF ya decían esto; la ficha,
                      que es lo que se ve todo el tiempo, no lo decía. */}
                  <p className="mb-4 text-[10px] leading-relaxed text-slate-400">
                    {ALCANCE_DEL_SELLO}
                  </p>
                  {selectedMolecule?.blockchain?.tx_signature && (
                    <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-slate-500">
                      Red: {redDelSello ?? "comprobando…"}
                      {esRedDePruebas(redDelSello) && (
                        <span className="ml-2 rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-400">
                          red de pruebas
                        </span>
                      )}
                    </p>
                  )}

                  {selectedMolecule?.blockchain?.tx_signature ? (
                    <>
                      <div className="bg-black/60 rounded-xl p-3 mb-6 border border-white/5 font-mono text-[8px] text-slate-500 break-all leading-tight">
                        {selectedMolecule.blockchain.tx_signature}
                      </div>
                      {/* MOLDEX-SCI-001: si la corrida cambió después de sellar,
                          el lector tiene que ver ambas cifras y saber cuál
                          respalda la cadena. */}
                      {leerSello(selectedMolecule.blockchain) === "corrida-anterior" && (
                        <div
                          role="alert"
                          className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-left text-[11px] leading-relaxed text-amber-200/90"
                        >
                          <p className="font-black uppercase tracking-widest text-amber-400 mb-2">
                            Sello desfasado
                          </p>
                          <p>
                            La molécula se reevaluó después de certificarla. La cadena
                            atestigua un score de{" "}
                            <b>{selectedMolecule.blockchain.certified_total_score?.toFixed(1) ?? "—"}</b>{" "}
                            y esta ficha muestra{" "}
                            <b>{selectedMolecule.metrics?.score?.toFixed(1) ?? "—"}</b>.
                            El certificado sigue siendo válido para la corrida que selló,
                            no para la que se ve aquí.
                          </p>
                        </div>
                      )}
                      {leerSello(selectedMolecule.blockchain) === "indeterminado" && (
                        <div
                          role="alert"
                          className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-left text-[11px] leading-relaxed text-amber-200/90"
                        >
                          <p className="font-black uppercase tracking-widest text-amber-400 mb-2">
                            Sello sin corrida registrada
                          </p>
                          <p>
                            Este certificado es anterior al registro de procedencia: no
                            consta qué corrida atestiguó, así que no puede afirmarse que
                            corresponda a las cifras mostradas.
                          </p>
                        </div>
                      )}
                      <ExternalLink
                        href={urlDelExplorador(selectedMolecule.blockchain.tx_signature, redDelSello)}
                        className="w-full text-[10px] font-black text-white bg-indigo-600 py-4 rounded-2xl shadow-xl shadow-indigo-500/20 hover:bg-indigo-500 transition-all uppercase tracking-widest flex items-center justify-center gap-2 mb-3"
                      >
                        <FlaskConical size={14} /> VERIFICAR EN SOLANA
                      </ExternalLink>
                    </>
                  ) : (
                    <>
                      <div className="bg-black/60 rounded-xl p-3 mb-6 border border-white/5 font-mono text-[8px] text-slate-500 break-all leading-tight">
                        SYSTEM_AUTHENTICATED_LOCAL
                      </div>
                      <button
                        onClick={() => setShowCertificationModal(true)}
                        className="mb-3 flex w-full items-center justify-center gap-2 rounded-2xl border border-purple-500/40 bg-purple-600 py-4 text-[10px] font-black uppercase tracking-widest text-white transition-colors hover:bg-purple-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:bg-purple-700"
                      >
                        <Database size={14} /> REGISTRAR EN SOLANA
                      </button>
                    </>
                  )}

                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowPdfViewer(true)}
                      className="flex-1 text-[10px] font-black text-indigo-300 bg-indigo-500/20 border border-indigo-500/30 py-3 rounded-2xl hover:bg-indigo-500/30 transition-all uppercase tracking-widest flex items-center justify-center gap-2"
                    >
                      <Eye size={14} /> VER REPORTE
                    </button>
                    {/* MOLDEX-INT-006: era un `<a href>` crudo. El Bearer vive
                        en el envoltorio de fetch y una navegación no lo lleva,
                        así que para una cuenta real la descarga fallaba. */}
                    <button
                      type="button"
                      disabled={!selectedId || descargando !== null}
                      onClick={() => descargar("pdf")}
                      className="flex-1 text-[10px] font-black text-slate-400 bg-slate-800/50 py-3 rounded-2xl transition-all uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {descargando === "pdf" ? "DESCARGANDO…" : "DESCARGAR PDF"}
                    </button>
                  </div>

                  <button
                    type="button"
                    disabled={!selectedId || descargando !== null}
                    onClick={() => descargar("complejo")}
                    className="w-full mt-3 text-[10px] font-black text-slate-400 bg-slate-800/50 py-3 rounded-2xl transition-all uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Box size={14} />
                    {descargando === "complejo" ? "DESCARGANDO…" : "DESCARGAR COMPLEJO 3D (PDB)"}
                  </button>
                </div>
              </section>

            </motion.div>
          </AnimatePresence>
        </motion.aside>
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
      {showPdfViewer && selectedId && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in"
          onClick={() => setShowPdfViewer(false)}
        >
          <div
            className="bg-[#0f1015] border border-slate-800 rounded-2xl w-full max-w-5xl h-[85vh] shadow-2xl relative animate-in zoom-in-95 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-[#0a0a0a] rounded-t-2xl">
              <div className="flex items-center gap-3">
                <span className="text-xl">📄</span>
                <h3 className="text-lg font-bold text-white tracking-wide">Reporte Científico</h3>
              </div>
              <button
                onClick={() => setShowPdfViewer(false)}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-hidden p-4">
              <PDFReportViewer
                moleculeId={selectedId}
                isCertified={!!selectedMolecule?.blockchain?.tx_signature}
                onCertify={handleCertificationRecorded}
              />
            </div>
          </div>
        </div>
      )}

      {showCertificationModal && selectedId && (
        <CertificationModal
          moleculeId={selectedId}
          onClose={() => setShowCertificationModal(false)}
          onSuccess={handleCertificationRecorded}
        />
      )}
    </div>
  );
}
