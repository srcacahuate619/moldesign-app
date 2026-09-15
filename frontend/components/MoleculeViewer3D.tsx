"use client";


import { Translated, useLanguage } from "@/context/LanguageContext";
import { memo, useEffect, useRef, useState } from "react";
import { liberarVisor3D } from "../lib/visor3d";
import { comprobarWebGL, type EstadoWebGL } from "../lib/webgl";

type Props = {
  poseData?: string;
  proteinData?: string;
  height?: number;
  hotspots?: string[];
  hotspotsHit?: string[];
  hideLegend?: boolean;
  mobileTopOffset?: boolean;
};

type ViewMode = "standard" | "surface" | "charges";

export const MoleculeViewer3D = memo(function MoleculeViewer3D({ poseData, proteinData, height = 450, hotspots = [], hotspotsHit = [], hideLegend = false, mobileTopOffset = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { t } = useLanguage();
  const viewerRef    = useRef<any>(null);

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

    const handleResize = () => {
      if (!viewerRef.current || !containerRef.current) return;
      const v = viewerRef.current;
      const container = containerRef.current;
      const w = container.clientWidth;
      const h = container.clientHeight;

      if (isMobile) {
        v.resize(w * 1.2, h * 1.2);
      } else {
        v.resize();
      }
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [modelsLoaded, isMobile]);

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
        const protAtoms = m0.selectedAtoms({});
        const ligAtoms = m1.selectedAtoms({});
        const resisWithLines = new Set<string>();
        const pocketResis = new Set<string>();
        const pocketSelArray: any[] = [];

        const potentialInteractions: { p: any, l: any, dist2: number }[] = [];

        for (const p of protAtoms) {
          if (p.hetflag) continue;
          for (const l of ligAtoms) {
            const dx = p.x - l.x, dy = p.y - l.y, dz = p.z - l.z;
            const dist2 = dx*dx + dy*dy + dz*dz;
            if (dist2 <= 25) {
              const key = `${p.chain}:${p.resi}`;
              if (!pocketResis.has(key)) {
                pocketResis.add(key);
                pocketSelArray.push({ chain: p.chain, resi: p.resi });
              }
              if (showInteractions && dist2 <= 12.25) {
                const lElem = l.elem?.trim().toUpperCase();
                const pElem = p.elem?.trim().toUpperCase();
                if (["O","N","F","S"].includes(lElem) && ["O","N","F","S"].includes(pElem)) {
                  potentialInteractions.push({ p, l, dist2 });
                }
              }
            }
          }
        }
        
        // Draw only top 5 closest interactions
        potentialInteractions
          .sort((a, b) => a.dist2 - b.dist2)
          .slice(0, 5)
          .forEach(({ p, l }) => {
            resisWithLines.add(`${p.resn}${p.resi}`);
            v.addCylinder({ start: l, end: p, radius: 0.05, color: "white", dashed: true });
          });

        pocketSelArray.forEach(sel => {
          v.addStyle({ model: 0, ...sel }, { stick: { colorscheme: "lightgreyCarbon", radius: 0.14, opacity: 0.99 } });
        });

        if (showHotspots) {
          hotspots.forEach(hs => {
            const match = hs.match(/(?:([A-Z]):)?([A-Z]{1,3})\s*(\d+)/i);
            if (match) {
              const chain = match[1];
              const resn = match[2].toUpperCase();
              const resi = parseInt(match[3]);
              const isHit = hotspotsHit.includes(hs);
              const hasLine = resisWithLines.has(`${resn}${resi}`);
              const color = isHit ? (hasLine ? "#10b981" : "#52525b") : "#71717a";
              const opacity = (isHit && !hasLine) ? 0.45 : 1.0;
              const radius = hasLine ? 0.75 : 0.6;
              const selector: any = { model: 0, resn, resi };
              if (chain) selector.chain = chain;
              v.addStyle(selector, { sphere: { color, radius, opacity } });
              v.setClickable(selector, true, () => setSelectedHotspot(`${chain ? chain + ':' : ''}${resn}${resi}`));
            }
          });
        }

        const surfaceSelector = (isMobile && pocketResis.size > 0)
          ? { model: 0, predicate: (atom: any) => pocketResis.has(`${atom.chain}:${atom.resi}`) }
          : { model: 0 };

        if (viewMode === "surface") {
          v.addSurface($3d.SurfaceType.VDW, { opacity: isMobile ? 0.35 : 0.5, color: "white" }, surfaceSelector);
        } else if (viewMode === "charges") {
          protAtoms.forEach((p: any) => {
            if (["ASP", "GLU"].includes(p.resn)) p.color = "red";
            else if (["ARG", "LYS", "HIS"].includes(p.resn)) p.color = "blue";
            else p.color = "white";
          });
          v.addSurface($3d.SurfaceType.VDW, { opacity: isMobile ? 0.45 : 0.65 }, surfaceSelector);
        }
      }
    }

    if (hasLigand) { v.zoomTo({ model: ligIdx }); v.zoom(0.85); } else v.zoomTo();
    v.render();
  }, [modelsLoaded, viewMode, showInteractions, showHotspots, poseData, proteinData, hotspots, hotspotsHit]);

  const hasData = !!(poseData || proteinData);

  return (
    <>
      <div className="relative overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-[#0a0a0a]" style={{ height, width: "100%", position: "relative" }}>
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
            <div className="absolute z-10 flex flex-wrap justify-end gap-2 max-w-[90%]" style={{ top: (isMobile && mobileTopOffset) ? "72px" : "16px", right: "16px" }}>
              <div className="flex bg-white/80 dark:bg-zinc-900/80 rounded-lg p-1 border border-zinc-200 dark:border-zinc-800 backdrop-blur-md">
                {["standard", "surface", "charges"].map((m: any) => (
                  <button key={m} onClick={() => setViewMode(m)} className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${viewMode === m ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-white' : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-300'}`}>
                    {m === "standard" ? "Pocket" : m === "surface" ? "Surface" : "Charges"}
                  </button>
                ))}
              </div>
              <button onClick={() => setShowInteractions(!showInteractions)} className={`px-3 py-1.5 text-xs font-semibold rounded-lg border backdrop-blur-md transition-all ${showInteractions ? 'bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-600 text-zinc-900 dark:text-white' : 'bg-white/80 dark:bg-zinc-900/80 border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:text-zinc-900 dark:hover:text-white'}`}>
                Interactions
              </button>
              <button onClick={() => setShowHotspots(!showHotspots)} className={`px-3 py-1.5 text-xs font-semibold rounded-lg border backdrop-blur-md transition-all ${showHotspots ? 'bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-600 text-zinc-900 dark:text-white' : 'bg-white/80 dark:bg-zinc-900/80 border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:text-zinc-900 dark:hover:text-white'}`}>
                Hotspots
              </button>
            </div>

            {selectedHotspot && (
              <div className="absolute bottom-4 left-4 z-20 bg-white/80 dark:bg-zinc-900/80 border border-zinc-200 dark:border-zinc-800 px-3 py-2 rounded-lg backdrop-blur-md text-[11px] font-mono text-zinc-900 dark:text-zinc-200 flex items-center gap-3 shadow-sm">
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
        <div className="mt-4 flex flex-wrap items-center justify-center gap-4 sm:gap-6 px-4 py-3 bg-zinc-50 dark:bg-zinc-900/50 rounded-xl border border-zinc-200 dark:border-zinc-800">
          <button 
            onClick={() => setSelectedEduLegend({
              title: t("z_critical_hit"),
              desc: t("z_critical_hit_desc")
            })}
            className="flex items-center gap-2 group"
          >
            <div className="h-2.5 w-2.5 rounded-full bg-zinc-900 dark:bg-white" />
            <span className="text-[10px] font-bold text-zinc-700 dark:text-zinc-300 uppercase tracking-widest group-hover:text-zinc-900 dark:group-hover:text-white transition-colors">{t("z_hit")}</span>
          </button>
          
          <button 
            onClick={() => setSelectedEduLegend({
              title: t("z_proximity_contact"),
              desc: t("z_proximity_contact_desc")
            })}
            className="flex items-center gap-2 group"
          >
            <div className="h-2.5 w-2.5 rounded-full bg-zinc-400 dark:bg-zinc-600" />
            <span className="text-[10px] font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-widest group-hover:text-zinc-700 dark:group-hover:text-zinc-300 transition-colors">{t("z_proximity")}</span>
          </button>
          
          <button 
            onClick={() => setSelectedEduLegend({
              title: t("z_miss"),
              desc: t("z_miss_desc")
            })}
            className="flex items-center gap-2 group"
          >
            <div className="h-2.5 w-2.5 rounded-full border-2 border-zinc-300 dark:border-zinc-700 bg-transparent" />
            <span className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest group-hover:text-zinc-600 dark:group-hover:text-zinc-400 transition-colors">{t("z_miss")}</span>
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
