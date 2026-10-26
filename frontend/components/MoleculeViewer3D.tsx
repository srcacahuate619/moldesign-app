"use client";


import { Translated, useLanguage } from "@/context/LanguageContext";
import { memo, useEffect, useRef, useState } from "react";
import { liberarVisor3D } from "../lib/visor3d";
import { comprobarWebGL, type EstadoWebGL } from "../lib/webgl";

type Props = {
  poseData?: string;
  proteinData?: string;
  height?: number | string;
  hotspots?: string[];
  hotspotsHit?: string[];
  hideLegend?: boolean;
  mobileTopOffset?: boolean;
  pocketFocus?: boolean;
};

type ViewMode = "standard" | "surface" | "charges";

type ContactGeometry = {
  proteinData?: string;
  poseData?: string;
  protAtoms: any[];
  pocketResis: Set<string>;
  pocketSelArray: Array<{ chain: string; resi: number }>;
  polarProximities: Array<{ p: any; l: any; dist2: number }>;
  nearestAtomByResidue: Map<string, { atom: any; dist2: number }>;
};

/** Índice espacial de 5 Å: sólo se inspeccionan átomos del ligando cercanos. */
function calculateContactGeometry(protAtoms: any[], ligAtoms: any[], proteinData?: string, poseData?: string): ContactGeometry {
  const pocketResis = new Set<string>();
  const pocketSelArray: Array<{ chain: string; resi: number }> = [];
  const polarProximities: Array<{ p: any; l: any; dist2: number }> = [];
  const nearestAtomByResidue = new Map<string, { atom: any; dist2: number }>();
  const cell = (n: number) => Math.floor(n / 5);
  const key = (x: number, y: number, z: number) => `${x}:${y}:${z}`;
  const cells = new Map<string, any[]>();
  for (const atom of ligAtoms) {
    const k = key(cell(atom.x), cell(atom.y), cell(atom.z));
    const bucket = cells.get(k) ?? [];
    bucket.push(atom);
    cells.set(k, bucket);
  }
  for (const p of protAtoms) {
    if (p.hetflag) continue;
    const px = cell(p.x), py = cell(p.y), pz = cell(p.z);
    for (let x = px - 1; x <= px + 1; x++) {
      for (let y = py - 1; y <= py + 1; y++) {
        for (let z = pz - 1; z <= pz + 1; z++) {
          for (const l of cells.get(key(x, y, z)) ?? []) {
            const dx = p.x - l.x, dy = p.y - l.y, dz = p.z - l.z;
            const dist2 = dx * dx + dy * dy + dz * dz;
            if (dist2 > 25) continue;
            const residue = `${p.chain}:${p.resi}`;
            const nearest = nearestAtomByResidue.get(residue);
            if (!nearest || dist2 < nearest.dist2) nearestAtomByResidue.set(residue, { atom: p, dist2 });
            if (!pocketResis.has(residue)) {
              pocketResis.add(residue);
              pocketSelArray.push({ chain: p.chain, resi: p.resi });
            }
            if (dist2 <= 12.25 &&
                ["O", "N", "F", "S"].includes(l.elem?.trim().toUpperCase()) &&
                ["O", "N", "F", "S"].includes(p.elem?.trim().toUpperCase())) {
              polarProximities.push({ p, l, dist2 });
            }
          }
        }
      }
    }
  }
  polarProximities.sort((a, b) => a.dist2 - b.dist2);
  return { proteinData, poseData, protAtoms, pocketResis, pocketSelArray, polarProximities, nearestAtomByResidue };
}

export const MoleculeViewer3D = memo(function MoleculeViewer3D({ poseData, proteinData, height = 450, hotspots = [], hotspotsHit = [], hideLegend = false, mobileTopOffset = false, pocketFocus = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { t } = useLanguage();
  const viewerRef    = useRef<any>(null);
  const geometryRef = useRef<ContactGeometry | null>(null);
  const fitCameraRef = useRef(false);

  const [viewMode, setViewMode] = useState<ViewMode>("standard");
  const [showInteractions, setShowInteractions] = useState(false);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [showHotspots, setShowHotspots] = useState(true);
  const [selectedHotspot, setSelectedHotspot] = useState<string | null>(null);
  const [selectedEduLegend, setSelectedEduLegend] = useState<{title: string, desc: React.ReactNode, icon?: string} | null>(null);

  const [isMobile, setIsMobile] = useState(false);
  const [isInteractive, setIsInteractive] = useState(false);

  // ── Sin aceleración 3D no se crea el visor ─────────────────────────────
  //
  // EL FALLO. Este visor llamaba a `$3Dmol.createViewer` sin preguntar si el
  // equipo puede crear un contexto. En la máquina virtual sin GPU virtualizada,
  // 3Dmol falla al construir su renderizador, `modelsLoaded` nunca pasa a true
  // y lo que le queda al investigador es el spinner girando para siempre sobre
  // un recuadro vacío, con los controles «Surface», «Charges» e «Interactions»
  // encima invitando a pulsar botones que no van a hacer nada.
  //
  // La comprobación es la misma que usa Evaluación (`lib/webgl.ts`), no una
  // copia: preguntar por el navegador o por el driver da falsos positivos, y
  // duplicar la detección garantiza que las dos versiones se separen.
  //
  // `null` mientras no se sabe: en render de servidor no hay canvas que probar,
  // y decidir durante el primer render pintaría en el cliente algo distinto de
  // lo que el servidor envió. El efecto lo resuelve en el mismo montaje, así
  // que ese estado dura un render — no es un tercer camino que el usuario vea.
  const [estadoWebGL, setEstadoWebGL] = useState<EstadoWebGL | null>(null);
  useEffect(() => {
    setEstadoWebGL(comprobarWebGL());
  }, []);
  const sinWebGL = estadoWebGL?.disponible === false;

  // ── Liberar la GPU al desmontar ────────────────────────────────────────
  //
  // EL FALLO. El efecto que crea el visor (`$3Dmol.createViewer`) reutiliza a
  // propósito la instancia entre cambios de datos, así que no puede destruirla
  // en su propia limpieza. El resultado era que NADIE la destruía: cada vez que
  // se navegaba entre Evaluación, Estructura e Informe quedaba un contexto
  // WebGL huérfano con sus búferes vivos.
  //
  // Duele especialmente en la máquina virtual sin GPU, que es donde se probó:
  // WebView2 cae al renderizador por software y el proceso pasaba de ~180 MB a
  // más de 600 MB tras varias evaluaciones seguidas. Y hay un límite duro que
  // el tamaño no deja ver: Chromium sólo mantiene ~16 contextos WebGL vivos; al
  // pasarse, pierde el más antiguo y ese visor se queda en negro.
  //
  // `[]` de dependencias: esta limpieza corre SÓLO al desmontar. Con las
  // dependencias del efecto de carga destruiría el visor en cada cambio de
  // pose, que es justo lo que aquel evita.
  useEffect(() => {
    const contenedor = containerRef.current;
    return () => {
      const visor = viewerRef.current;
      viewerRef.current = null;
      liberarVisor3D(contenedor, visor);
    };
  }, []);

  useEffect(() => {
    const checkMobile = () => {
      const touchScreen = window.matchMedia("(pointer: coarse)").matches;
      const smallScreen = window.innerWidth < 768;
      setIsMobile(touchScreen || smallScreen);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  useEffect(() => {
    if (!modelsLoaded || !viewerRef.current || !containerRef.current) return;
    const container = containerRef.current;
    let previousWidth = 0;
    let previousHeight = 0;
    const handleResize = () => {
      const v = viewerRef.current;
      if (!v) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height || (width === previousWidth && height === previousHeight)) return;
      previousWidth = width;
      previousHeight = height;
      v.resize();
      v.render();
    };
    // Los paneles de Moldex cambian el ancho disponible sin redimensionar la
    // ventana. ResizeObserver mantiene el canvas nítido en ambos casos.
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleResize) : null;
    observer?.observe(container);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", handleResize);
    };
  }, [modelsLoaded]);

  useEffect(() => {
    // Antes que nada: sin contexto no se monta el motor. Va aquí y no dentro de
    // `loadModels` porque la rama del `setTimeout` volvería a entrar a los 600 ms.
    if (!estadoWebGL?.disponible) return;

    const hasProtein = !!proteinData && proteinData.trim().length > 10;
    const hasLigand  = !!poseData    && poseData.trim().length    > 10;

    if (!hasProtein && !hasLigand) {
      setModelsLoaded(false);
      return;
    }

    const $3d = window.$3Dmol;
    if (!$3d) {
      const t = setTimeout(() => {
        const v2 = window.$3Dmol;
        if (v2 && containerRef.current) loadModels(v2);
      }, 600);
      return () => clearTimeout(t);
    }
    
    loadModels($3d);

    function loadModels($3dmol: any) {
      if (!containerRef.current) return;

      if (!viewerRef.current) {
        // Use a neutral gray/black bg instead of blue-tinted
        const bgColor = document.documentElement.classList.contains('dark') ? "#0a0a0a" : "#ffffff";
        viewerRef.current = $3dmol.createViewer(containerRef.current, {
          backgroundColor: bgColor,
          antialias: true,
        });
      }
      const v = viewerRef.current;
      v.clear();
      geometryRef.current = null;
      fitCameraRef.current = true;

      if (hasProtein) {
        v.addModel(proteinData, "pdb");
      }

      if (hasLigand) {
        const singlePoseData = poseData!.split('$$$$')[0] + '\n$$$$\n';
        v.addModel(singlePoseData, "sdf");
      }
      
      setModelsLoaded(true);
    }
  }, [poseData, proteinData, estadoWebGL]);

  useEffect(() => {
    if (!modelsLoaded || !viewerRef.current) return;
    const v = viewerRef.current;
    const $3d = window.$3Dmol;
    
    const hasProtein = !!proteinData && proteinData.trim().length > 10;
    const hasLigand  = !!poseData    && poseData.trim().length    > 10;
    const ligIdx = hasProtein ? 1 : 0;

    v.removeAllSurfaces();
    v.removeAllShapes();

    if (hasProtein) {
      v.setStyle({ model: 0 }, { cartoon: { color: "spectrum", opacity: 0.50, thickness: 0.30 } });
    }
    if (hasLigand) {
      v.setStyle({ model: ligIdx }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
    }

    if (hasProtein && hasLigand) {
      const m0 = v.getModel(0);
      const m1 = v.getModel(ligIdx);
      if (m0 && m1) {
        const resisWithLines = new Set<string>();
        let geometry = geometryRef.current;
        if (!geometry || geometry.proteinData !== proteinData || geometry.poseData !== poseData) {
          geometry = calculateContactGeometry(m0.selectedAtoms({}), m1.selectedAtoms({}), proteinData, poseData);
          geometryRef.current = geometry;
        }
        
        // Distancia entre heteroátomos; no se infiere puente H ni energía.
        geometry.polarProximities.slice(0, 5).forEach(({ p, l }) => {
            resisWithLines.add(`${p.chain}:${p.resn}${p.resi}`);
            if (showInteractions) v.addCylinder({ start: l, end: p, radius: 0.05, color: "white", dashed: true });
          });

        geometry.pocketSelArray.forEach(sel => {
          v.addStyle({ model: 0, ...sel }, { stick: { colorscheme: "lightgreyCarbon", radius: 0.14, opacity: 0.99 } });
        });

        if (showHotspots) {
          hotspots.forEach(hs => {
            if (typeof hs !== "string") return;
            const match = hs.match(/(?:([A-Z]):)?([A-Z]{1,3})\s*(\d+)/i);
            if (match) {
              const chain = match[1];
              const resn = match[2].toUpperCase();
              const resi = parseInt(match[3]);
              const isHit = hotspotsHit.includes(hs);
              // Un hotspot es un residuo, no una esfera por cada átomo del
              // residuo. Marcar el átomo más próximo a la pose evita la nube
              // de esferas y sitúa el marcador dentro del bolsillo real.
              const candidates = geometry.protAtoms.filter((p: any) => p.resn === resn && p.resi === resi && (!chain || p.chain === chain));
              const preferred = candidates.find((p: any) => geometry.nearestAtomByResidue.get(`${p.chain}:${p.resi}`)?.atom === p)
                ?? candidates.find((p: any) => p.atom === "CA")
                ?? candidates[0];
              if (!preferred?.atom) return;
              // SCI-A-015: atribuir proximidad y marcador a la cadena dibujada.
              const hasLine = resisWithLines.has(`${preferred.chain}:${resn}${resi}`);
              const color = isHit ? (hasLine ? "#10b981" : "#52525b") : "#71717a";
              const radius = hasLine ? 0.65 : 0.5;
              const selector: any = { model: 0, chain: preferred.chain, resn, resi, atom: preferred.atom };
              v.addStyle(selector, { sphere: { color, radius } });
              v.setClickable(selector, true, () => setSelectedHotspot(`${chain ? chain + ':' : ''}${resn}${resi}`));
            }
          });
        }

        const surfaceSelector = (pocketFocus || isMobile) && geometry.pocketResis.size > 0
          ? { model: 0, predicate: (atom: any) => geometry!.pocketResis.has(`${atom.chain}:${atom.resi}`) }
          : { model: 0 };

        if (viewMode === "surface") {
          v.addSurface($3d.SurfaceType.VDW, { opacity: isMobile ? 0.35 : 0.5, color: "white" }, surfaceSelector);
        } else if (viewMode === "charges") {
          geometry.protAtoms.forEach((p: any) => {
            if (["ASP", "GLU"].includes(p.resn)) p.color = "red";
            else if (["ARG", "LYS", "HIS"].includes(p.resn)) p.color = "blue";
            else p.color = "white";
          });
          v.addSurface($3d.SurfaceType.VDW, { opacity: isMobile ? 0.45 : 0.65 }, surfaceSelector);
        }
      }
    }

    if (fitCameraRef.current) {
      const pocket = geometryRef.current?.pocketResis;
      if (pocketFocus && hasProtein && hasLigand && pocket?.size) {
        // Encuadrar el bolsillo derivado de la pose, no sólo el ligando. El
        // selector usa los mismos residuos ≤5 Å ya calculados para la vista.
        v.zoomTo({ model: 0, predicate: (atom: any) => pocket.has(`${atom.chain}:${atom.resi}`) });
        v.zoom(0.82);
      } else if (hasLigand) {
        v.zoomTo({ model: ligIdx });
        v.zoom(0.85);
      } else {
        v.zoomTo();
      }
      fitCameraRef.current = false;
    }
    v.render();
  }, [modelsLoaded, viewMode, showInteractions, showHotspots, poseData, proteinData, hotspots, hotspotsHit, isMobile, pocketFocus]);

  const hasData = !!(poseData || proteinData);

  return (
    <>
      <div className="relative overflow-hidden border border-[var(--border)] bg-[var(--bg-card)]" style={{ height, width: "100%", position: "relative" }}>
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} className="[&_canvas]:!w-full [&_canvas]:!h-full" />

        {/* Estado propio, no el fallo de la librería. Lo que hay que responder
            no es «qué pasó con el renderizador» sino «qué de lo mío sigue
            sirviendo»: el visor no calcula nada, sólo dibuja lo ya calculado. */}
        {sinWebGL && (
          <div
            role="status"
            className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-white px-6 text-center dark:bg-[#0a0a0a]"
          >
            <span className="text-2xl opacity-50 grayscale">🧊</span>
            <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
              <Translated id="z_3d_no_dibuja" />
            </p>
            <p className="max-w-sm text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400">
              <Translated id="auto_6982bfeae501" /> {estadoWebGL?.motivo}
            </p>
            <p className="max-w-sm text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400">
              <Translated id="z_3d_datos" />
            </p>
          </div>
        )}

        {!sinWebGL && isMobile && !isInteractive && hasData && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-white/80 dark:bg-[#0a0a0a]/80 backdrop-blur-sm gap-2 p-4 transition-all duration-300">
            <span className="text-2xl animate-bounce">🖐️</span>
            <p className="text-[11px] text-zinc-600 dark:text-zinc-400 text-center font-medium px-4">
              {t("z_camera_locked")}
            </p>
            <button
              onClick={() => setIsInteractive(true)}
              className="mt-2 px-4 py-2 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 rounded-lg text-xs font-semibold hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
            >
              {t("z_unlock_3d")}
            </button>
          </div>
        )}

        {!sinWebGL && !modelsLoaded && hasData && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/50 dark:bg-[#0a0a0a]/50 backdrop-blur-sm">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-900 dark:border-white border-t-transparent" />
          </div>
        )}

        {!sinWebGL && !hasData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-zinc-400 dark:text-zinc-600 bg-white dark:bg-[#0a0a0a]">
            <span className="text-2xl grayscale opacity-50">🔬</span>
            <p className="text-xs font-medium"><Translated id="z_3d_al_terminar" /></p>
          </div>
        )}

        {!sinWebGL && hasData && (
          <>
            <div className="absolute z-10 flex max-w-[88%] flex-wrap justify-end gap-2 transition-[right] duration-200 ease-out" style={{ top: (isMobile && mobileTopOffset) ? "72px" : "16px", right: "calc(16px + var(--viewer-inset-r, 0px))" }}>
              <div className="flex border border-[var(--border-light)] bg-[var(--bg-card)] p-1">
                {(["standard", "surface", "charges"] as ViewMode[]).map((m) => (
                  <button key={m} type="button" aria-pressed={viewMode === m} title={m === "charges" ? t("z_residue_types_desc") : undefined} onClick={() => setViewMode(m)} className={`min-h-8 cursor-pointer px-2.5 py-1.5 text-[11px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] ${viewMode === m ? 'bg-[var(--bg-secondary)] text-[var(--text)]' : 'text-[var(--text-dim)] hover:text-[var(--text)]'}`}>
                    {m === "standard" ? t("z_view_pocket") : m === "surface" ? t("z_view_surface") : t("z_view_residues")}
                  </button>
                ))}
              </div>
              <button type="button" aria-pressed={showInteractions} title={t("z_polar_proximity_desc")} onClick={() => setShowInteractions(!showInteractions)} className={`min-h-9 cursor-pointer border border-[var(--border-light)] px-3 py-1.5 text-[11px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] ${showInteractions ? 'bg-[var(--bg-secondary)] text-[var(--accent-strong)]' : 'bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text)]'}`}>
                {t("z_polar_proximity")}
              </button>
              <button type="button" aria-pressed={showHotspots} onClick={() => setShowHotspots(!showHotspots)} className={`min-h-9 cursor-pointer border border-[var(--border-light)] px-3 py-1.5 text-[11px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] ${showHotspots ? 'bg-[var(--bg-secondary)] text-[var(--accent-strong)]' : 'bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text)]'}`}>
                {t("z_view_hotspots")}
              </button>
            </div>

            {selectedHotspot && (
              <div style={{ left: "calc(16px + var(--viewer-inset-l, 0px))" }} className="absolute bottom-4 z-20 transition-[left] duration-200 ease-out bg-white/80 dark:bg-zinc-900/80 border border-zinc-200 dark:border-zinc-800 px-3 py-2 rounded-lg backdrop-blur-md text-[11px] font-mono text-zinc-900 dark:text-zinc-200 flex items-center gap-3 shadow-sm">
                <span>🎯 {selectedHotspot}</span>
                <button onClick={() => setSelectedHotspot(null)} className="text-zinc-400 hover:text-zinc-900 dark:hover:text-white">✕</button>
              </div>
            )}

            {isMobile && isInteractive && (
              <button
                onClick={() => setIsInteractive(false)}
                className="absolute bottom-4 right-4 z-30 px-3 py-2 bg-white/90 dark:bg-zinc-900/90 text-zinc-600 dark:text-zinc-400 rounded-lg text-[10px] font-bold uppercase tracking-widest border border-zinc-200 dark:border-zinc-800 hover:text-zinc-900 dark:hover:text-white transition-colors backdrop-blur-md shadow-sm"
              >
                {t("z_lock_3d")}
              </button>
            )}
          </>
        )}
      </div>

      {!sinWebGL && !hideLegend && (
        <div style={{ marginLeft: "var(--viewer-inset-l, 0px)", marginRight: "var(--viewer-inset-r, 0px)" }} className="mt-3 flex flex-wrap items-center justify-center gap-4 border border-[var(--border)] bg-[var(--bg-card)] px-4 py-3">
          <button 
            onClick={() => setSelectedEduLegend({
              title: t("z_critical_hit"),
              desc: t("z_critical_hit_desc")
            })}
            className="flex items-center gap-2 group"
          >
            <div className="h-2.5 w-2.5 rounded-full bg-[var(--categoria-hallazgo)]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-secondary)] transition-colors group-hover:text-[var(--text)]">{t("z_hit")}</span>
          </button>
          
          <button 
            onClick={() => setSelectedEduLegend({
              title: t("z_proximity_contact"),
              desc: t("z_proximity_contact_desc")
            })}
            className="flex items-center gap-2 group"
          >
            <div className="h-2.5 w-2.5 rounded-full bg-[var(--border-light)]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-secondary)] transition-colors group-hover:text-[var(--text)]">{t("z_proximity")}</span>
          </button>
          
          <button 
            onClick={() => setSelectedEduLegend({
              title: t("z_miss"),
              desc: t("z_miss_desc")
            })}
            className="flex items-center gap-2 group"
          >
            <div className="h-2.5 w-2.5 rounded-full bg-[var(--text-dim)]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-secondary)] transition-colors group-hover:text-[var(--text)]">{t("z_miss")}</span>
          </button>
        </div>
      )}

      {selectedEduLegend && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-white/80 dark:bg-[#0a0a0a]/80 backdrop-blur-md"
          onClick={() => setSelectedEduLegend(null)}
        >
          <div 
            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 max-w-md w-full shadow-2xl relative text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedEduLegend(null)}
              className="absolute top-6 right-6 text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="mb-4">
              <h3 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-white">{selectedEduLegend.title}</h3>
            </div>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
              {selectedEduLegend.desc}
            </p>
          </div>
        </div>
      )}
    </>
  );
});
