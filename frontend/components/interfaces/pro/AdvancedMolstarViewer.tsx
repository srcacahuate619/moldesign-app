"use client";

import { useEffect, useRef, useState } from "react";
import { Box, Crosshair } from "lucide-react";
import {
  VIEWER_LABEL_BUTTON_CLASS,
  VIEWER_LABEL_PANEL_CLASS,
  VIEWER_SWITCH_BUTTON_CLASS,
} from "./viewerOverlayStyles";

type Props = {
  poseData?: string;     // SDF - Ligando
  proteinData?: string;  // PDB - Receptor
  moleculeId?: string;
  height?: number;
  hotspots?: string[];
  hotspotsHit?: string[];
  gnnAttention?: number[];
  onOpenTargetSelector?: () => void;
  // Botón nativo para cambiar de visor (MolStar ↔ Web3D) — renderizado DENTRO
  // del canvas, sobre el WebGL.
  onSwitchViewer?: () => void;
  viewerLabel?: string;
  // Info del grid box del receptor para mostrarla en el visor (coords reales).
  gridInfo?: { centerX: number; centerY: number; centerZ: number; sizeX: number; sizeY: number; sizeZ: number } | null;
  // Sincronización de cámara con Web3D (vista completa position+target):
  // externalCamera → posición de Web3D para adoptar (position + target)
  // onCameraChange → reporta la posición actual para transferir a Web3D
  externalCamera?: { position: [number, number, number]; target: [number, number, number]; distance: number } | null;
  onCameraChange?: (cam: { position: [number, number, number]; target: [number, number, number]; distance: number }) => void;
  // NIVEL 2: cuando el wrapper del KeepAlive pasa a display:none, el canvas
  // WebGL queda congelado (0x0). Al volver a display:block hay que forzar un
  // resize explícito para que Molstar recupere el aspect ratio correcto.
  // Sin esto, el visor aparece negro/colgado hasta que el usuario mueve algo.
  isActive?: boolean;
};

const loadScript = (src: string, id: string): Promise<void> => {
  if (typeof document === "undefined") return Promise.resolve();
  return new Promise((resolve, reject) => {
    if (document.getElementById(id)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.id = id;
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => {
      script.remove();
      reject(new Error(`Failed to load script ${src}`));
    };
    document.head.appendChild(script);
  });
};

const loadStyle = (href: string, id: string): Promise<void> => {
  if (typeof document === "undefined") return Promise.resolve();
  return new Promise((resolve, reject) => {
    if (document.getElementById(id)) {
      resolve();
      return;
    }
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    link.onload = () => resolve();
    link.onerror = () => {
      link.remove();
      reject(new Error(`Failed to load style ${href}`));
    };
    document.head.appendChild(link);
  });
};

// --- HELPER PARSERS ---

const cleanPdb = (pdbStr: string): string => {
  const standardResidues = new Set(["MSE", "SEP", "TPO", "PTR", "CSX", "CSD", "CSO", "CME"]);
  return pdbStr
    .split("\n")
    .filter((line) => {
      const record = line.slice(0, 6).trim();
      if (record === "HETATM") {
        const resName = line.slice(17, 20).trim();
        return standardResidues.has(resName);
      }
      return true;
    })
    .join("\n");
};

const crystallizationHelpers = new Set([
  // Common Crystallization Helpers & Ions
  "SO4", "PO4", "CL", "NA", "K", "MG", "CA", "ZN", "FE", "NI", "CU", "CO", "MN", "NH4", "LI", "BR", "I",
  "GOL", "EDO", "DMS", "ACT", "PEG", "PG4", "PGE", "IPA", "EOH", "MOH", "TRS", "FMT", "BU3", "MPD", "AZI", 
  "UNX", "DTT", "BME", "CIT", "DIO", "MLI", "PE8", "P33", "P4C"
]);

const extractReferenceLigand = (pdbStr: string): string | null => {
  const standardResidues = new Set(["MSE", "SEP", "TPO", "PTR", "CSX", "CSD", "CSO", "CME"]);
  const lines = pdbStr.split("\n").filter((line) => {
    const record = line.slice(0, 6).trim();
    if (record === "HETATM") {
      const resName = line.slice(17, 20).trim();
      const isWater = ["HOH", "WAT", "DOD", "SOL", "TIP"].includes(resName);
      return !standardResidues.has(resName) && !isWater && !crystallizationHelpers.has(resName);
    }
    return false;
  });
  if (lines.length === 0) return null;
  return lines.join("\n") + "\nEND\n";
};

const patchSdfTitle = (sdfStr: string): string => {
  const lines = sdfStr.split("\n");
  if (lines.length > 0) {
    // Forcefully overwrite the SDF title to ensure Molstar reads it
    lines[0] = "Candidato_Ligando_MolDesign";
  }
  return lines.join("\n");
};

const getResidueCoordinates = (pdbStr: string, residueName: string, residueSeq: number, chainId: string = "A") => {
  const lines = pdbStr.split("\n");
  for (const line of lines) {
    const record = line.slice(0, 6).trim();
    if (record === "ATOM" || record === "HETATM") {
      const atomName = line.slice(12, 16).trim();
      const resName = line.slice(17, 20).trim();
      const chain = line.slice(21, 22).trim() || "A";
      const seq = parseInt(line.slice(22, 26).trim());
      if (atomName === "CA" && resName === residueName && seq === residueSeq && chain === chainId) {
        const x = parseFloat(line.slice(30, 38).trim());
        const y = parseFloat(line.slice(38, 46).trim());
        const z = parseFloat(line.slice(46, 54).trim());
        return { x, y, z };
      }
    }
  }
  return null;
};

const createHotspotsPdb = (pdbStr: string, hotspots: string[], hotspotsHit: string[]) => {
  let pdbContent = "";
  let atomIndex = 1;
  for (const hs of hotspots) {
    const match = hs.match(/(?:([A-Z]):)?([A-Z]{3})\s*(\d+)/i);
    if (!match) continue;
    const chain = match[1] || "A";
    const resn = match[2].toUpperCase();
    const resi = parseInt(match[3]);

    const coords = getResidueCoordinates(pdbStr, resn, resi, chain);
    if (coords) {
      const x = coords.x.toFixed(3).padStart(8);
      const y = coords.y.toFixed(3).padStart(8);
      const z = coords.z.toFixed(3).padStart(8);

      const isHit = hotspotsHit.includes(hs);
      const element = isHit ? "MG" : "O";
      const atomName = isHit ? "MG " : "O  ";
      const resName = isHit ? "MG " : "HOH";
      pdbContent += `HETATM${atomIndex.toString().padStart(5)}  ${atomName} ${resName} ${chain}${resi.toString().padStart(4)}    ${x}${y}${z}  1.00 20.00          ${element.padStart(2)}\n`;
      atomIndex++;
    }
  }
  if (pdbContent === "") return null;
  return pdbContent + "END\n";
};

const createGnnAttentionPdb = (sdfStr: string, attention: number[]) => {
  const lines = sdfStr.split("\n");
  let pdbContent = "";
  let atomIndex = 1;
  let inAtoms = false;
  
  for (const line of lines) {
    if (line.includes("V2000") || line.includes("V3000")) {
       inAtoms = true;
       continue;
    }
    if (inAtoms && line.includes("M  END")) break;
    
    if (inAtoms && line.length >= 30) {
       const match = line.match(/^\s*([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)\s+([A-Za-z]+)/);
       if (match) {
         const x = parseFloat(match[1]).toFixed(3).padStart(8);
         const y = parseFloat(match[2]).toFixed(3).padStart(8);
         const z = parseFloat(match[3]).toFixed(3).padStart(8);
         
         const att = attention[atomIndex - 1] || 0.0;
         
         // Mapeo de color: O (Rojo/Magenta) para < 0.3, CL (Verde oscuro) para 0.3-0.7, MG (Verde claro/limón) para > 0.7
         let element = "O";
         let atomName = "O  ";
         if (att >= 0.7) {
           element = "MG";
           atomName = "MG ";
         } else if (att >= 0.3) {
           element = "CL";
           atomName = "CL ";
         }
         
         pdbContent += `HETATM${atomIndex.toString().padStart(5)}  ${atomName} XAI A   1    ${x}${y}${z}  1.00 20.00          ${element.padStart(2)}\n`;
         atomIndex++;
       }
    }
  }
  if (pdbContent === "") return null;
  return pdbContent + "END\n";
};

const NO_HOTSPOTS: string[] = [];
const NO_ATTENTION: number[] = [];

export default function AdvancedMolstarViewer({ poseData, proteinData, height = 500, hotspots = NO_HOTSPOTS, hotspotsHit = NO_HOTSPOTS, gnnAttention = NO_ATTENTION, onOpenTargetSelector, onSwitchViewer, viewerLabel, gridInfo, externalCamera, onCameraChange, isActive = true }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewerReady, setViewerReady] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleFocusCandidate = () => {
    const viewer = viewerRef.current;
    if (viewer && viewerReady) {
      try {
        const structures = viewer.plugin.managers.structure.hierarchy.current.structures;
        
        let candidate = structures.find((s: any) => {
          const label1 = (s.cell?.obj?.label || "").toLowerCase();
          const label2 = (s.cell?.obj?.data?.label || "").toLowerCase();
          return label1.includes("candidato") || label1.includes("diseño") || label1.includes("ligando") || label1.includes("sdf") || label1.includes("unknown") ||
                 label2.includes("candidato") || label2.includes("diseño") || label2.includes("ligando") || label2.includes("sdf") || label2.includes("unknown");
        });

        if (!candidate && poseData && structures.length > 1) {
          console.warn("Candidate not found by label. Falling back to the last loaded structure.");
          candidate = structures[structures.length - 1];
        }

        if (candidate && candidate.cell?.obj?.data) {
          const data = candidate.cell.obj.data;
          
          if (data.boundary && data.boundary.sphere) {
            // Focus on the sphere with a slight zoom out for context
            viewer.plugin.managers.camera.focusSphere(data.boundary.sphere);
            
            // Try to highlight it if possible
            if (data.representativeLoci) {
              try {
                viewer.plugin.managers.interactivity.lociHighlights.highlightOnly({ loci: data.representativeLoci });
              } catch (e) { /* ignore highlight error */ }
            }
          } else if (data.representativeLoci) {
            viewer.plugin.managers.camera.focusLoci(data.representativeLoci);
          } else {
            console.warn("No boundary or loci found on candidate data.");
            viewer.plugin.managers.camera.reset();
          }
        } else {
          console.warn("No candidate data object found.");
          viewer.plugin.managers.camera.reset();
        }
      } catch (e) {
        console.error("Error focusing on candidate molecule:", e);
      }
    }
  };

  // 1. Initial Load of Scripts and Molstar Instance (Only once on unmount)
  useEffect(() => {
    let viewer: any = null;
    let cancelled = false;
    let sub: any = null;

    const initMolstar = async () => {
      if (!containerRef.current) return;
      setLoading(true);
      setError(null);

      try {
        // NIVEL 1 (Doc 30 CSP Audit): todo local, cero CDN.
        // Antes: probe CDN jsdelivr primero + fallback local → fetch network 4.8MB
        // por cada montaje. Eliminado: /public/molstar.css (71KB) y /public/molstar.js
        // (4.8MB) ya sirven localmente. Ahorra ~200-1000ms de latency + parse por montaje.
        await loadStyle("/molstar.css", "molstar-css");
        await loadScript("/molstar.js", "molstar-js");

        const molstarGlobal = window.molstar;
        if (!molstarGlobal) {
          throw new Error("Global 'molstar' not found.");
        }
        const Viewer = molstarGlobal.Viewer;
        if (!Viewer) {
          throw new Error("Viewer object not found in global 'molstar'.");
        }
        if (typeof Viewer.create !== "function") {
          throw new Error("Viewer.create is not a function.");
        }

        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = "";

        // Create the viewer instance with default controls enabled (settings, selection, expand)
        viewer = await Viewer.create(containerRef.current, {
          layoutIsExpanded: false,
          layoutShowControls: false,
          layoutShowRemoteState: false,
          layoutShowSequence: false,
          layoutShowLog: false,
          viewportShowExpand: true,         // Enable default expand button
          viewportShowSelectionMode: true,  // Enable default selection controls
          viewportShowSettings: true,       // Enable default settings button
        });

        // Subscribe to layout changes to reactively update the outer container's size
        sub = viewer.plugin.layout.events.updated.subscribe(() => {
          if (viewer.plugin && viewer.plugin.layout) {
            setIsExpanded(!!viewer.plugin.layout.state.isExpanded);
          }
        });

        viewerRef.current = viewer;
        setViewerReady(true);
      } catch (err) {
        if (!cancelled) {
          console.error("Error al inicializar Molstar:", err);
          setError("No se pudo cargar el visor 3D científico (Mol*).");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    initMolstar();

    return () => {
      cancelled = true;
      setViewerReady(false);
      if (sub) {
        try { sub.unsubscribe(); } catch (e) { /* ignore */ }
      }
      if (viewer) {
        try { viewer.dispose(); } catch (e) { /* ignore */ }
      }
    };
  }, []);

  // 2. Dynamic Reload of Models when Data changes (Fast reload without WebGL flashing)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !viewerReady) return;

    let cancelled = false;

    const loadStructures = async () => {
      try {
        setLoading(true);

        // Clear previous structures
        await viewer.plugin.clear();

        const hasProtein = !!proteinData && proteinData.trim().length > 10;
        const hasLigand = !!poseData && poseData.trim().length > 10;

        if (cancelled) return;

        if (hasProtein) {
          // Load cleaned protein receptor structure (no overlapping HETATMs)
          const cleanProt = cleanPdb(proteinData!);
          await viewer.loadStructureFromData(cleanProt, "pdb", { dataLabel: "Receptor" });

          if (cancelled) return;

          // Always load crystallographic reference ligand as a separate named structure
          const refLig = extractReferenceLigand(proteinData!);
          if (refLig) {
            await viewer.loadStructureFromData(refLig, "pdb", { dataLabel: "Referencia (Cristalografía)" });
          }

          if (cancelled) return;

          // Always load pocket hotspots as a separate named structure
          if (hotspots.length > 0) {
            const hotspotsPdb = createHotspotsPdb(proteinData!, hotspots, hotspotsHit);
            if (hotspotsPdb) {
              await viewer.loadStructureFromData(hotspotsPdb, "pdb", { dataLabel: "Hotspots (Puntos Clave)" });
            }
          }
        }

        if (cancelled) return;

        if (hasLigand) {
          // Load candidate ligand (patched to avoid "unknown" label in tooltip)
          const singlePoseData = poseData!.split("$$$$")[0] + "\n$$$$\n";
          const patchedSdf = patchSdfTitle(singlePoseData);
          await viewer.loadStructureFromData(patchedSdf, "sdf", { dataLabel: "Mi Diseño MolDesign (Candidato)" });

          if (cancelled) return;

          // Load GNN Attention overlay if available
          if (gnnAttention && gnnAttention.length > 0) {
            const attPdb = createGnnAttentionPdb(singlePoseData, gnnAttention);
            if (attPdb) {
              await viewer.loadStructureFromData(attPdb, "pdb", { dataLabel: "Atención GNN 3D (RTMScore)" });
            }
          }
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Error al cargar estructuras en Molstar:", err);
          setError("Error al cargar coordenadas en el visualizador.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadStructures();

    return () => {
      cancelled = true;
    };
  }, [viewerReady, proteinData, poseData, hotspots, hotspotsHit]);

  const prevExpandedRef = useRef<boolean>(isExpanded);

  // 3. Reactively Resize Molstar WebGL canvas when layout expanded state changes
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer && viewerReady) {
      // Only execute resize logic if expanded state has actually changed (prevents 0x0 canvas collapse on mount)
      if (prevExpandedRef.current !== isExpanded) {
        prevExpandedRef.current = isExpanded;

        const resize = () => {
          try {
            const container = containerRef.current;
            if (container && container.clientWidth > 0 && container.clientHeight > 0) {
              // Trigger layout event
              if (typeof viewer.handleResize === "function") {
                viewer.handleResize();
              }
              // Force WebGL canvas resize and aspect ratio correction
              if (viewer.plugin && viewer.plugin.canvas3d && typeof viewer.plugin.canvas3d.handleResize === "function") {
                viewer.plugin.canvas3d.handleResize();
              }
              // Dispatch window resize event to trigger internal observers in Molstar
              window.dispatchEvent(new Event("resize"));
            }
          } catch (e) {
            console.warn("Resize error on expand state change:", e);
          }
        };

        // NIVEL 3: un único rAF en lugar de 3 setTimeout en cascada.
        // El rAF espera al próximo frame del browser → reflow ya completado.
        // Un setTimeout(300) extra cubre transiciones CSS largas (ej. expand).
        let raf1 = 0;
        let raf2 = 0;
        const scheduleResize = (delay: number) =>
          new Promise<void>(resolve => requestAnimationFrame(() => {
            resize();
            resolve();
          }));

        // Primera resincronización inmediata (próximo frame)
        raf1 = requestAnimationFrame(resize);
        // Segunda resincronización post-transition (300ms cubre CSS transitions típicas)
        const t3 = setTimeout(() => { raf2 = requestAnimationFrame(resize); }, 300);

        return () => {
          cancelAnimationFrame(raf1);
          cancelAnimationFrame(raf2);
          clearTimeout(t3);
        };
      }
    }
  }, [isExpanded, viewerReady]);

  // 4. Sincronización de cámara con Web3D.
  // externalCamera → adoptar posición (target + distancia) cuando llega desde
  // Web3D. onCameraChange → reportar la cámara actual para transferir a Web3D.
  const externalCameraKey = externalCamera
    ? `${externalCamera.position[0].toFixed(2)},${externalCamera.position[1].toFixed(2)},${externalCamera.position[2].toFixed(2)}|${externalCamera.target[0].toFixed(2)},${externalCamera.target[1].toFixed(2)},${externalCamera.target[2].toFixed(2)}`
    : "";
  const lastExternalKey = useRef("");

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !viewerReady) return;
    if (!externalCamera || externalCameraKey === lastExternalKey.current) return;
    lastExternalKey.current = externalCameraKey;

    try {
      const [px, py, pz] = externalCamera.position;
      const [tx, ty, tz] = externalCamera.target;
      const camMgr = viewer.plugin.managers.camera;
      // MolStar: setSnapshot con position + target EXACTOS — reconstruye la
      // vista completa (orientación + zoom) del Web3D, no solo el foco.
      if (camMgr && typeof camMgr.setSnapshot === "function") {
        camMgr.setSnapshot({
          position: [px, py, pz],
          target: [tx, ty, tz],
          radius: externalCamera.distance,
        });
      } else if (camMgr && typeof camMgr.focus === "function") {
        // Fallback: solo focus + radio (orientación por defecto de MolStar)
        camMgr.focus({ target: [tx, ty, tz], radius: externalCamera.distance });
      }
    } catch (e) {
      console.warn("Sync camera MolStar ← Web3D:", e);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalCameraKey, viewerReady]);

  // Reportar cámara de MolStar para transferir a Web3D.
  // Usa POLLING (intervalo) en lugar de depender de eventos de interacción:
  // la rotación es con DRAG que NO genera interaction.click, por eso antes
  // Web3D nunca recibía la cámara de MolStar. Con el intervalo capturamos
  // drag/zoom/pan y también el estado inicial.
  // IMPORTANTE: solo reporta cuando MolStar está ACTIVO (visible) — si está
  // oculto (opacity:0), su cámara no es la que el usuario ve y reportarla
  // pisaría la vista de Web3D.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !viewerReady || !onCameraChange || !isActive) return;

    const camMgr = viewer.plugin.managers.camera;
    if (!camMgr) return;

    let lastSent = "";
    const report = () => {
      try {
        const st = camMgr.getSnapshot?.();
        if (!st) return;
        const p = st.position as [number, number, number] | undefined;
        const t = st.target as [number, number, number] | undefined;
        const r = st.radius as number | undefined;
        if (!p || !t || !r) return;
        const key = `${p[0].toFixed(1)},${p[1].toFixed(1)},${p[2].toFixed(1)}|${t[0].toFixed(1)},${t[1].toFixed(1)},${t[2].toFixed(1)}`;
        if (key === lastSent) return; // no cambió → no spamear
        lastSent = key;
        onCameraChange({
          position: [p[0], p[1], p[2]],
          target: [t[0], t[1], t[2]],
          distance: r,
        });
      } catch (e) {
        // silencioso
      }
    };

    // Report inicial (para que Web3D pueda adoptar la vista actual de MolStar)
    const initT = setTimeout(report, 500);
    const interval = setInterval(report, 400);
    return () => {
      clearTimeout(initT);
      clearInterval(interval);
    };
  }, [viewerReady, onCameraChange, isActive]);

  // NIVEL 2: Recovery del render loop cuando el wrapper vuelve a ser visible.
  // Cuando el KeepAlive deja el wrapper en display:none, el canvas WebGL pasa
  // a 0x0. Al volver a display:block, Molstar NO se entera solo — hay que forzar
  // un handleResize() para que recupere el aspect ratio. Sin esto, el visor queda
  // "colgado" visualmente hasta que el usuario mueve algo.
  // Estrategia: escuchar el paso false→true en `isActive` y disparar resize.
  const prevActiveRef = useRef<boolean>(isActive);
  useEffect(() => {
    const wasActive = prevActiveRef.current;
    prevActiveRef.current = isActive;
    if (!wasActive && isActive) {
      // Pasó de oculto a visible: re-sync canvas
      const viewer = viewerRef.current;
      if (!viewer || !viewerReady) return;
      const syncResize = () => {
        try {
          const container = containerRef.current;
          if (container && container.clientWidth > 0 && container.clientHeight > 0) {
            if (typeof viewer.handleResize === "function") viewer.handleResize();
            if (viewer.plugin?.canvas3d && typeof viewer.plugin.canvas3d.handleResize === "function") {
              viewer.plugin.canvas3d.handleResize();
            }
          }
        } catch (e) {
          console.warn("Recovery resize error:", e);
        }
      };
      // Doble rAF: el primero espera al commit del DOM (display:block aplicado),
      // el segundo espera al paint para que clientWidth/Height ya sean reales.
      // EL SEGUNDO rAF NO SE CANCELABA. Estaba escrito así:
      //
      //     (syncResize as any)._raf2 = raf2;
      //     return () => cancelAnimationFrame(raf1);
      //
      // El identificador se colgaba del propio callback y no lo leía nadie: el
      // comentario decía «cleanup del segundo rAF» y el cleanup sólo cancelaba
      // el primero. Al desmontar entre los dos frames, `syncResize` corría sobre
      // un visor ya destruido. El `as any` era lo que dejaba escribir una
      // propiedad inventada en una función sin que nada lo señalara.
      let raf2: number | null = null;
      const raf1 = requestAnimationFrame(() => {
        raf2 = requestAnimationFrame(syncResize);
      });
      return () => {
        cancelAnimationFrame(raf1);
        if (raf2 !== null) cancelAnimationFrame(raf2);
      };
    }
  }, [isActive, viewerReady]);

  const hasData = !!(poseData || proteinData);

  // Stacking context breakout styles when viewport is expanded
  const wrapperStyle = isExpanded
    ? { position: "fixed" as const, inset: 0, width: "100vw", height: "100vh", zIndex: 9999 }
    : { height, width: "100%", position: "relative" as const };

  const canvasStyle = isExpanded
    ? { position: "relative" as const, width: "100vw", height: "100vh" }
    : { position: "relative" as const, width: "100%", height: "100%", minHeight: `${height}px` };

  return (
    <div 
      className={
        isExpanded
          ? "bg-[#060a13] w-screen h-screen flex items-center justify-center z-[9999]"
          : "relative isolate overflow-hidden rounded-3xl border border-indigo-500/10 bg-[#060a13] shadow-2xl"
      }
      style={wrapperStyle}
    >
      <style>{`
        .msp-plugin,
        .msp-plugin-container,
        .msp-viewport {
          width: 100% !important;
          height: 100% !important;
        }
        .msp-viewport canvas {
          width: 100% !important;
          height: 100% !important;
        }
      `}</style>

      {/* Floating Controls Bar */}
      {hasData && !loading && !error && !isExpanded && (
        <div className="pointer-events-auto absolute left-3 top-3 z-10 flex items-center gap-2">
          {/* Identify Candidate Ligand Button */}
          {poseData && (
            <button
              onClick={handleFocusCandidate}
              className={VIEWER_LABEL_BUTTON_CLASS}
            >
              <Crosshair size={12} className="text-indigo-400" />
              <span>Identificar Mi Diseño</span>
            </button>
          )}
        </div>
      )}

      {/* Canvas container - forces the WebGL canvas to span full boundaries */}
      <div 
        ref={containerRef} 
        className="w-full h-full [&_canvas]:!w-full [&_canvas]:!h-full [&_.msp-plugin]:!w-full [&_.msp-plugin]:!h-full [&_.msp-plugin-container]:!w-full [&_.msp-plugin-container]:!h-full [&_.msp-viewport]:!w-full [&_.msp-viewport]:!h-full" 
        style={canvasStyle} 
      />

      {/* Esquina inferior derecha exclusiva para cambiar de visor. */}
      {hasData && !loading && !error && (
        <div className="pointer-events-auto absolute bottom-3 right-3 z-10">
          {/* Botón cambiar visor */}
          {onSwitchViewer && (
            <button
              onClick={onSwitchViewer}
              className={VIEWER_SWITCH_BUTTON_CLASS}
              title={viewerLabel ? `Cambiar a visor ${viewerLabel}` : "Cambiar visor"}
            >
              <Crosshair size={12} className="text-indigo-400" />
              Ver {viewerLabel ?? "Web3D"}
            </button>
          )}

        </div>
      )}

      {/* Loading HUD */}
      {loading && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#05080f]/70 backdrop-blur-sm gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-indigo-400 animate-pulse">Cargando Mol* (WebGL2)...</span>
        </div>
      )}

      {/* Error HUD */}
      {error && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#05080f]/90 gap-2 p-4 text-center">
          <span className="text-2xl text-rose-500">⚠️</span>
          <p className="text-xs text-rose-400 font-bold">{error}</p>
        </div>
      )}

      {/* No Data HUD */}
      {!hasData && !loading && !error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-slate-600 bg-[#05080f]/80">
          <Box size={40} className="opacity-30 text-indigo-400" />
          <p className="text-xs font-black uppercase tracking-widest text-slate-500">Esperando coordenadas estructurales...</p>
        </div>
      )}

      {/* Información secundaria: nunca se monta un panel vacío. */}
      {hasData && !loading && !error && !isExpanded && (gridInfo || hotspots.length > 0) && (
        <div className={`${VIEWER_LABEL_PANEL_CLASS} absolute bottom-3 left-3 z-10 flex max-w-[280px] flex-col gap-1.5 p-2.5`}>
          {gridInfo && (
            <div className="pointer-events-none flex flex-col gap-0.5">
              <span className="text-[8px] font-black uppercase tracking-widest text-cyan-300">Grid Box</span>
              <span className="text-[9px] font-mono text-slate-300">
                C: {gridInfo.centerX.toFixed(1)}, {gridInfo.centerY.toFixed(1)}, {gridInfo.centerZ.toFixed(1)} &Aring;
              </span>
              <span className="text-[8px] font-mono text-slate-500">
                {gridInfo.sizeX.toFixed(1)}&times;{gridInfo.sizeY.toFixed(1)}&times;{gridInfo.sizeZ.toFixed(1)} &Aring;
              </span>
            </div>
          )}
          {hotspots.length > 0 && (
            <div className="flex items-center gap-3 text-[8px] font-bold text-slate-400 uppercase tracking-wider">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#10b981] inline-block shadow-[0_0_6px_#10b981]" /> Contacto</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#ef4444] inline-block shadow-[0_0_6px_#ef4444]" /> Omitido</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
