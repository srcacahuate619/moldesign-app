"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useEffect, useRef, useState } from "react";
import { liberarVisor3D } from "../lib/visor3d";
import { useTheme } from "../context/ThemeContext";
import { motion, AnimatePresence } from "framer-motion";

const TECH = [
  { name: "RDKit", role: "Quimioinformática", color: "#4ade80", desc: "Valida valencias, quiralidad, conformeros y descriptores fisicoquímicos. Sus señales sirven para revisar una estructura; no determinan por sí solas si es un fármaco." },
  { name: "ADMET-AI", role: "Señales ADMET", color: "#60a5fa", desc: "Modelos D-MPNN que producen señales sobre absorción, permeabilidad y otros endpoints. Se interpretan como predicciones computacionales, no como seguridad clínica." },
  { name: "TabPFN", role: "Modelo tabular experimental", color: "#f87171", desc: "Modelo tabular opcional para cohortes y pesos declarados por un perfil. No diagnostica toxicidad ni identifica patentes por sí mismo." },
  { name: "Vina", role: "Docking molecular", color: "#fb923c", desc: "AutoDock Vina 1.2.7 explora poses dentro de la caja declarada y devuelve un score empírico para ordenar poses. No es energía libre experimental." },
  { name: "XGBoost", role: "Rescoring condicionado", color: "#c084fc", desc: "Regresión sobre features de pose cuando existe un perfil y dominio válidos. La salida es una interpretación derivada, no una corrección universal de Vina." },
  { name: "RTMScore", role: "Topología GNN", color: "#a78bfa", desc: "Artefacto experimental que representa contactos proteína–ligando. No valida por sí solo la geometría ni emite Kd/Ki en esta instalación." },
  { name: "OpenMM", role: "Preparación opcional", color: "#22d3ee", desc: "Herramienta disponible para operaciones explícitamente configuradas de preparación o minimización. MolDesign no ejecuta MD de producción ni FEP con ella." },
  { name: "Solana", role: "Registro opcional", color: "#facc15", desc: "Memo opcional con hashes y metadatos técnicos de un dossier. Prueba integridad y fecha de emisión, no autoría, validez científica ni propiedad intelectual." },
];

// Benzaldehyde PDB (C₇H₆O) — 8 heavy atoms
const PDB = [
  "HETATM    1  C1  LIG A   1       1.210   0.700   0.200  1.00  0.00           C",
  "HETATM    2  C2  LIG A   1       0.000   1.400  -0.100  1.00  0.00           C",
  "HETATM    3  C3  LIG A   1      -1.210   0.700   0.150  1.00  0.00           C",
  "HETATM    4  C4  LIG A   1      -1.210  -0.700  -0.150  1.00  0.00           C",
  "HETATM    5  C5  LIG A   1       0.000  -1.400   0.100  1.00  0.00           C",
  "HETATM    6  C6  LIG A   1       1.210  -0.700  -0.200  1.00  0.00           C",
  "HETATM    7  C7  LIG A   1       2.600   1.500   0.400  1.00  0.00           C",
  "HETATM    8  O1  LIG A   1       3.780   0.850   0.300  1.00  0.00           O",
  "END",
].join("\n");

export function MoleculeTechViewer() {
  const { t } = useLanguage();
  const { theme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState<number | null>(null);
  const modalRef = useRef<number | null>(null);

  useEffect(() => {
    const load = () => {
      const $3d = window.$3Dmol;
      if (!$3d || !containerRef.current) return;
      if (viewerRef.current) return;

      const isDark = theme === "dark";
      const v = $3d.createViewer(containerRef.current, {
        backgroundColor: isDark ? "#0a0a0a" : "#ffffff",
        antialias: true,
        specular: true,
      });

      v.addModel(PDB, "pdb");
      v.zoomTo();
      v.render();

      // Style each atom by technology color
      TECH.forEach((t, i) => {
        const serial = i + 1;
        v.setStyle({ serial }, { stick: { color: t.color, radius: 0.18 } });
        v.setStyle({ serial }, { sphere: { color: t.color, radius: 0.5, specular: "#ffffff", shininess: 0.4 } });
        v.setClickable({ serial }, true, () => {
          setActive(i);
        });
      });

      // Highlight on hover
      v.setHoverable({}, true, (atom: any) => {
        if (!atom || !atom.serial) return;
        const idx = atom.serial - 1;
        if (idx >= 0 && idx < TECH.length) {
          const c = TECH[idx].color;
          v.setStyle({ serial: atom.serial }, { stick: { color: c, radius: 0.22 } });
          v.setStyle({ serial: atom.serial }, { sphere: { color: c, radius: 0.65, specular: "#ffffff", shininess: 0.6 } });
          containerRef.current!.style.cursor = "pointer";
          v.render();
        }
      }, (atom: any) => {
        if (!atom || !atom.serial) return;
        const idx = atom.serial - 1;
        if (idx >= 0 && idx < TECH.length) {
          const c = TECH[idx].color;
          v.setStyle({ serial: atom.serial }, { stick: { color: c, radius: 0.18 } });
          v.setStyle({ serial: atom.serial }, { sphere: { color: c, radius: 0.5, specular: "#ffffff", shininess: 0.4 } });
          containerRef.current!.style.cursor = "default";
          v.render();
        }
      });

      // Auto-rotation for 3D depth
      v.spin("y", 0.015);
      v.setBackgroundColor(isDark ? "#0a0a0a" : "#ffffff", 0);

      viewerRef.current = v;
      setReady(true);
    };

    // 3Dmol may already be loaded via layout.tsx <Script>
    let check: ReturnType<typeof setInterval> | null = null;
    if (window.$3Dmol) {
      load();
    } else {
      check = setInterval(() => {
        if (window.$3Dmol) {
          if (check) clearInterval(check);
          load();
        }
      }, 100);
    }

    // La limpieza estaba SÓLO en la rama del `else`, así que en el camino
    // normal —3Dmol ya cargado por `layout.tsx`— este efecto no devolvía nada
    // y el visor no se destruía nunca. Peor: `v.spin("y", 0.015)` seguía
    // pidiendo fotogramas después de desmontar, sobre un contexto que ya nadie
    // mira. Ver `lib/visor3d.ts`.
    const contenedor = containerRef.current;
    return () => {
      if (check) clearInterval(check);
      const visor = viewerRef.current;
      viewerRef.current = null;
      liberarVisor3D(contenedor, visor);
    };
  }, []);

  return (
    <>
      <div className="relative w-full h-[600px] overflow-hidden border border-zinc-800">
        <div ref={containerRef} className="w-full h-full [&_canvas]:!w-full [&_canvas]:!h-full" />

        {/* Legend overlay */}
        <div className="absolute top-4 left-4 z-10 flex flex-wrap gap-2 max-w-[70%]">
          {TECH.map((t, i) => (
            <button
              key={t.name}
              onClick={() => setActive(active === i ? null : i)}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-mono uppercase tracking-wider border transition-all ${
                active === i
                  ? "bg-white text-black border-white"
                  : "bg-black/60 text-zinc-300 border-zinc-700 hover:border-zinc-500"
              }`}
              style={{ borderLeftColor: t.color, borderLeftWidth: 3 }}
            >
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: t.color }} />
              {t.name}
            </button>
          ))}
        </div>

        {/* Molecule label */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[10px] font-mono uppercase tracking-widest text-zinc-600 pointer-events-none">
          {t("z_benzaldehido")}
        </div>

        {!ready && (
          <div className={`absolute inset-0 flex items-center justify-center ${theme === "dark" ? "bg-[#0a0a0a]" : "bg-white"}`}>
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-600 border-t-white" />
          </div>
        )}
      </div>

      <AnimatePresence>
        {active !== null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
            onClick={() => setActive(null)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 15, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.95, y: 15, opacity: 0 }}
              className="bg-[#050505]/95 border border-zinc-800 p-8 max-w-lg w-full relative shadow-[0_0_50px_rgba(140,122,153,0.15)] ring-1 ring-white/5"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="absolute left-0 top-0 bottom-0 w-1" style={{ background: `linear-gradient(to bottom, ${TECH[active].color}, transparent)` }} />
              <button onClick={() => setActive(null)} className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors">✕</button>
              <div className="flex items-center gap-4 mb-6 pl-2">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center font-mono text-sm font-bold"
                  style={{ backgroundColor: TECH[active].color + "20", color: TECH[active].color, border: `1px solid ${TECH[active].color}40` }}
                >
                  {["C","C","C","C","C","C","C","O"][active]}
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-[0.2em]">{TECH[active].role}</span>
                  <span className="text-2xl font-black text-white uppercase tracking-tight">{TECH[active].name}</span>
                </div>
              </div>
              <div className="pl-2">
                <p className="text-xs text-zinc-300 font-mono leading-relaxed uppercase bg-zinc-900/50 p-5 border border-zinc-800">{t(TECH[active].desc)}</p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
