"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

// --------------------------------------------------------
// MOLECULAR BACKGROUNDS
// --------------------------------------------------------
const CaffeineSVG = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 400 400" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <g transform="translate(100, 100) scale(0.8)">
      <polygon points="100,50 150,80 150,140 100,170 50,140 50,80" />
      <polygon points="150,80 200,50 250,80 250,140 200,170 150,140" />
      <polygon points="250,80 300,50 350,80 350,140 300,170 250,140" />
      <circle cx="100" cy="50" r="15" fill="currentColor" opacity="0.2" />
      <circle cx="200" cy="170" r="15" fill="currentColor" opacity="0.2" />
      <circle cx="350" cy="80" r="15" fill="currentColor" opacity="0.2" />
      <line x1="100" y1="50" x2="100" y2="10" strokeWidth="4" />
      <line x1="250" y1="140" x2="280" y2="190" strokeWidth="4" />
      <line x1="150" y1="140" x2="150" y2="190" strokeWidth="4" strokeDasharray="4 4" />
    </g>
  </svg>
);

const SerotoninSVG = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 400 400" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <g transform="translate(80, 120) scale(0.7)">
      <polygon points="100,80 160,80 190,130 160,180 100,180 70,130" />
      <polygon points="190,130 250,130 280,80 250,30 190,30 160,80" />
      <line x1="280" y1="80" x2="330" y2="80" strokeWidth="3" />
      <line x1="330" y1="80" x2="360" y2="120" strokeWidth="3" />
      <circle cx="70" cy="130" r="18" fill="currentColor" opacity="0.1" />
      <circle cx="190" cy="30" r="18" fill="currentColor" opacity="0.1" />
      <circle cx="360" cy="120" r="18" fill="currentColor" opacity="0.1" />
    </g>
  </svg>
);

// --------------------------------------------------------
// DATA & MATH
// --------------------------------------------------------
const CX = 1500;
const CY = 1500;

const RINGS = [350, 650, 950, 1250]; 
const MEGA_RING_R = 1300;

const polarToCartesian = (radius: number, angleInDegrees: number) => {
  const angleInRadians = (angleInDegrees - 90) * Math.PI / 180.0;
  return {
    x: radius * Math.cos(angleInRadians),
    y: radius * Math.sin(angleInRadians)
  };
};

type NodeType = 'primary' | 'process' | 'error' | 'decision';

interface NodeDef {
  id: string;
  label: string;
  ring: number; 
  type: NodeType;
  tag: string;
  desc: string;
  parentId?: string; 
}

const NODES: NodeDef[] = [
  // L1
  { id: 'start', label: 'Ingesta SMILES', ring: 0, type: 'primary', tag: 'INPUT', desc: 'Punto de entrada al acelerador. Soporta ingesta masiva en lotes (CSV/SDF) o cadenas individuales. Tokenización inmediata para el pipeline de validación.' },
  { id: 'rdkit', label: 'RDKit', ring: 0, type: 'process', tag: 'VAL-01', desc: 'Valida sanitización, valencias, aromaticidad y representaciones moleculares. Las señales se conservan para revisión; no decide por sí solo la viabilidad del compuesto.' },
  { id: 'err1', label: 'Revisión requerida', ring: 0, type: 'error', tag: 'REVIEW', desc: 'La entrada no supera una comprobación estructural. Se conserva el motivo y se bloquea la etapa que no puede ejecutarse; no se elimina silenciosamente el caso.', parentId: 'rdkit' },
  { id: 'physchem', label: 'Propiedades fisicoquímicas', ring: 0, type: 'process', tag: 'ADME', desc: 'Calcula descriptores y reglas de drug-likeness para contextualizar la estructura. No garantiza absorción, seguridad ni viabilidad oral.' },
  { id: 'sa', label: 'SA Score', ring: 0, type: 'process', tag: 'HEUR', desc: 'Heurística de accesibilidad sintética (1–10). Es una señal orientativa sobre complejidad molecular, no un precio ni una garantía de que la síntesis sea posible.' },
  { id: 'err2', label: 'Revisión de alertas', ring: 0, type: 'error', tag: 'REVIEW', desc: 'Una alerta PAINS, una heurística SA u otra regla requiere revisión. Se conserva como evidencia y no se convierte automáticamente en toxicidad o descarte.', parentId: 'sa' },

  // L2
  { id: 'etkdg', label: 'Motor ETKDG', ring: 1, type: 'process', tag: '3D-GEN', desc: 'Genera conformaciones 3D plausibles mediante restricciones geométricas y muestreo estocástico. No demuestra que una conformación sea la dominante en solución.' },
  { id: 'vina', label: 'AutoDock Vina', ring: 1, type: 'process', tag: 'DOCK', desc: 'Docking local dentro de la caja declarada. Explora poses y devuelve un score empírico de Vina; no afirma una pose termodinámicamente óptima ni una energía libre experimental.' },
  { id: 'pose', label: 'Controles físicos de pose', ring: 1, type: 'process', tag: 'FIL-3', desc: 'Comprueba geometría, choques, conectividad e interacciones bajo los controles disponibles. RMSD sólo es interpretable cuando existe una referencia compatible.' },
  
  // L3 — RESCORING MULTI-MODELO
  { id: 'xgboost', label: 'XGBoost', ring: 2, type: 'process', tag: 'ML-01', desc: 'Rescoring derivado de features de la pose cuando el perfil y su dominio están disponibles. La salida puede expresarse en pKi y kcal equivalentes según el protocolo; fuera de dominio prevalece la observación de Vina.' },
  { id: 'cl_gnn', label: 'CL-GNN', ring: 2, type: 'process', tag: 'GNN-02', desc: 'Señal neuronal de grafos disponible sólo para perfiles que declaran modelo, pesos y cohorte. Las métricas son condicionales al benchmark; no se presenta como detector universal de sesgo o termodinámica.' },
  { id: 'rtmscore', label: 'RTMScore', ring: 2, type: 'process', tag: 'DEEP', desc: 'Artefacto de rescoring experimental que representa contactos de una pose. No emite automáticamente Kd/Ki en esta instalación ni valida por sí solo la geometría.' },
  { id: 'ums', label: 'UMS Metal', ring: 2, type: 'decision', tag: 'GATE', desc: 'Detector SMARTS de grupos funcionales candidatos a coordinar metales. Sólo se integra mediante perfiles M5-Zn exactos; su estado, componentes y aplicabilidad se muestran sin fabricar una fórmula fuera de perfil.' },
  { id: 'molchamb', label: 'MolChamb', ring: 2, type: 'process', tag: 'Q-01', desc: 'Descriptores de GFN2-xTB (cargas tight-binding, gap HOMO-LUMO, energía) y de MMFF94, ~0.1 s/mol. El índice agregado que produce es una combinación lineal con pesos elegidos a mano: informa y se guarda, pero desde 2026-09-04 no entra al score principal. No es equivalente a GAFF2 ni a un cálculo DFT.' },
  { id: 'final', label: 'Interpretación del perfil', ring: 2, type: 'process', tag: 'SYNC', desc: 'Cruza sólo las señales que el perfil declara y que la corrida produjo. Conserva observación, score derivado, aplicabilidad y abstención; no equivale a un consenso universal ni a una conclusión experimental.' },

  // L4 — POST-PROCESAMIENTO Y CERTIFICACIÓN
  { id: 'selectivity', label: 'Selectividad', ring: 3, type: 'process', tag: 'REG', desc: 'Acoplamiento contra los 5 anti-targets del panel (ANTI_TARGET_PANEL): hERG/KCNH2 5VA1 (cardiotoxicidad), CYP3A4 4NY4 (interacciones), 5-HT2B 4NC3 (valvulopatía), PDE3A 1SO2, NaV1.5/SCN5A 6MVW (conducción cardíaca). Da el margen on/off-target; no emite un veredicto de seguridad.' },
  { id: 'admet', label: 'ADMET Final', ring: 3, type: 'process', tag: 'TOX', desc: 'Absorción intestinal, permeabilidad BBB, PPB, solubilidad LogS y alertas de reactividad, con ADMET-AI (Chemprop D-MPNN). El consenso de BBB acierta 39 de 41 fármacos de difusión pasiva en una cohorte de regresión de 46, sin holdout independiente: es la cifra con la que se ajustó, no una validación externa. El índice de perfil sanguíneo es heurístico.' },
  { id: 'molchat', label: 'MolChat IA', ring: 3, type: 'primary', tag: 'AI', desc: 'Asistente opcional con Qwen2.5-1.5B local que consulta evidencia persistida y ayuda a explicarla. No es fuente primaria de resultados; requiere el modelo instalado y no incluye voz local en este runtime.' },
  { id: 'solana', label: 'Registro Solana', ring: 3, type: 'primary', tag: 'HASH', desc: 'Integración opcional que registra un hash y metadatos técnicos en un memo público. Puede verificar integridad y fecha de emisión; no valida la ciencia ni publica automáticamente la estructura.' },
  { id: 'certificado', label: 'Certificado PDF', ring: 3, type: 'primary', tag: 'PDF', desc: 'Genera un PDF con la evidencia y sus identificadores verificables. Puede incluir un enlace de integridad a Solana cuando el usuario lo solicita; no transfiere la propiedad de la molécula, el caso ni sus resultados.' },
];

const getLevelName = (ringIndex: number) => {
  if (ringIndex === 0) return "NIVEL 1";
  if (ringIndex === 1) return "NIVEL 2";
  if (ringIndex === 2) return "NIVEL 3";
  return "NIVEL 4";
};

const drawHexagon = (r: number) => {
  let points = "";
  for (let i = 0; i < 6; i++) {
    const angle_deg = 60 * i - 30;
    const angle_rad = Math.PI / 180 * angle_deg;
    points += `${r * Math.cos(angle_rad)},${r * Math.sin(angle_rad)} `;
  }
  return points;
};

// --------------------------------------------------------
// COMPONENT
// --------------------------------------------------------
export function PipelineFlowchart() {
  const { t } = useLanguage();
  const [isPlaying, setIsPlaying] = useState(true);
  const [playSessionKey, setPlaySessionKey] = useState(0); 
  const [selectedNode, setSelectedNode] = useState<NodeDef | null>(null);
  const [waveRing, setWaveRing] = useState(-1);

  const isFocused = selectedNode !== null;

  useEffect(() => {
    if (!isPlaying) {
      setWaveRing(-1);
      return;
    }
    
    let frameId: number;
    const startTime = Date.now();
    const CYCLE_DURATION = 6000;
    
    const animate = () => {
      const elapsed = (Date.now() - startTime) % CYCLE_DURATION;
      
      if (elapsed >= 500 && elapsed < 1200) setWaveRing(0);
      else if (elapsed >= 1300 && elapsed < 2200) setWaveRing(1);
      else if (elapsed >= 2300 && elapsed < 3400) setWaveRing(2);
      else if (elapsed >= 3400 && elapsed < 4600) setWaveRing(3);
      else setWaveRing(-1);

      frameId = requestAnimationFrame(animate);
    };
    
    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [isPlaying, playSessionKey]);

  const togglePlay = () => {
    if (isFocused) {
      setSelectedNode(null);
    } else {
      setIsPlaying(!isPlaying);
      setPlaySessionKey(prev => prev + 1);
    }
  };

  const mainNodes = NODES.filter(n => !n.parentId);
  const getSatellites = (parentId: string) => NODES.filter(n => n.parentId === parentId);

  const nodesByRing = {
    0: mainNodes.filter(n => n.ring === 0),
    1: mainNodes.filter(n => n.ring === 1),
    2: mainNodes.filter(n => n.ring === 2),
    3: mainNodes.filter(n => n.ring === 3),
  };

  const megaRingAngleOffset = 360 / mainNodes.length;
  const ARROW_OFFSET_DEG = 8.5; // Offset to clear the hexagons

  return (
    <>
      <section className="w-full relative py-24 bg-[#0a0a0a] overflow-hidden border-y border-zinc-800/80 min-h-screen flex flex-col justify-center">
        
        {/* Styles */}
        <style dangerouslySetInnerHTML={{__html: `
          :root {
            --play-state: ${isPlaying ? 'running' : 'paused'};
          }
          @keyframes rotateSlow {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          @keyframes rotateFast {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(-360deg); }
          }
          @keyframes pulseGlow {
            0%, 100% { opacity: 0.6; filter: brightness(1); }
            50% { opacity: 1; filter: brightness(1.5); }
          }
          @keyframes orbitCW {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes orbitCCW {
            from { transform: rotate(0deg); }
            to { transform: rotate(-360deg); }
          }
          @keyframes radarWave {
            0% { r: 0; opacity: 0.8; stroke-width: 40px; }
            12% { r: 350; opacity: 0.6; stroke-width: 22px; }
            25% { r: 650; opacity: 0.45; stroke-width: 14px; }
            40% { r: 950; opacity: 0.3; stroke-width: 8px; }
            55% { r: 1250; opacity: 0.18; stroke-width: 4px; }
            78% { r: 1400; opacity: 0; stroke-width: 1px; }
            100% { r: 1400; opacity: 0; stroke-width: 0px; }
          }
          .radar-pulse {
            animation: radarWave 6s linear infinite var(--play-state);
          }
          .anim-rotate-slow {
            transform-origin: center center;
            animation: rotateSlow 150s linear infinite var(--play-state);
          }
          .anim-rotate-fast {
            transform-origin: center center;
            animation: rotateFast 90s linear infinite var(--play-state);
          }
          .anim-pulse {
            animation: pulseGlow 6s ease-in-out infinite var(--play-state);
          }
          .sat-orbit { transform-origin: 0px 0px; animation: orbitCW 15s linear infinite var(--play-state); }
          .sat-counter { transform-origin: 0px 0px; animation: orbitCCW 15s linear infinite var(--play-state); }

          @media (prefers-reduced-motion: reduce) {
            .anim-rotate-slow, .anim-rotate-fast, .anim-pulse, 
            .sat-orbit, .sat-counter, .radar-pulse {
              animation: none !important;
              transform: none !important;
              opacity: 1 !important;
            }
          }
        `}} />

        {/* Background Molecules */}
        <div className="absolute inset-0 w-full h-full opacity-20 pointer-events-none flex items-center justify-center mix-blend-screen">
          <CaffeineSVG className="absolute w-[80vw] h-[80vw] max-w-[1000px] max-h-[1000px] text-[#4a3e5c] anim-rotate-slow" />
          <SerotoninSVG className="absolute w-[60vw] h-[60vw] max-w-[800px] max-h-[800px] text-[#364259] anim-rotate-fast" />
        </div>

        <AnimatePresence>
          {isFocused && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 z-40 bg-transparent"
              onClick={() => setSelectedNode(null)}
            />
          )}
        </AnimatePresence>

        {/* max-w-[1300px] para restaurar el tamaño físico original post-viewBox expand */}
        <div className={`relative px-4 md:px-8 w-full max-w-[1300px] mx-auto flex flex-col items-center ${isFocused ? 'z-50' : 'z-10'}`}>
          
          {/* Header */}
          <div className="w-full flex flex-col md:flex-row items-center justify-between gap-6 mb-8">
            <div className="text-center md:text-left">
              <h2 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                {t("z_acelerador")} <span className="text-zinc-500 font-light">| {isFocused ? 'Enfoque Profundo' : t("auto_a187157bca8f")}</span>
              </h2>
              <p className="text-zinc-400 text-sm mt-2 max-w-2xl font-mono">
                {isFocused 
                  ? t("auto_fa699172d465")
                  : t("auto_98c1ad5d0471")}
              </p>
            </div>
            <div className="flex items-center gap-4 bg-zinc-900/50 p-2 border border-zinc-800 rounded-full backdrop-blur-md">
              <span className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 font-bold px-2">{t("z_simulacion_visual")}</span>
              <button 
                onClick={togglePlay}
                aria-label={
                  isFocused
                    ? t("auto_73ce5e0c984a")
                    : isPlaying
                      ? t("auto_c025cd216bcf")
                      : t("auto_7b77d6194b7b")
                }
                className={`w-10 h-10 flex items-center justify-center rounded-full transition-colors ${isFocused ? 'bg-red-900 hover:bg-red-800 text-white' : 'bg-zinc-800 hover:bg-zinc-700 text-white'}`}
              >
                {isFocused ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                ) : isPlaying ? (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6zm8 0h4v16h-4z"/></svg>
                ) : (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                )}
              </button>
            </div>
          </div>

          {/* SVG PIPELINE */}
          <div className="w-full flex justify-center items-center py-4 relative">
            <svg 
              viewBox="0 0 3000 3000" 
              className="w-full h-auto drop-shadow-2xl"
            >
              <defs>
                <filter id="neon-primary" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="8" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
                <filter id="neon-error" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="6" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
                <filter id="neon-active" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="5" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>

                <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#8c7a99" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#0a0a0a" stopOpacity="0" />
                </radialGradient>

                {/* Arrowhead Marker */}
                <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="5" refY="4" orient="auto">
                  <path d="M 0 0 L 8 4 L 0 8 Z" fill="#8c7a99" />
                </marker>
                
                {/* Arrowhead Active Marker */}
                <marker id="arrowhead-active" markerWidth="8" markerHeight="8" refX="5" refY="4" orient="auto">
                  <path d="M 0 0 L 8 4 L 0 8 Z" fill="#fff" />
                </marker>
              </defs>

              {/* Core Glow */}
              <circle cx={CX} cy={CY} r="250" fill="url(#centerGlow)" className="anim-pulse" 
                style={{ opacity: isFocused ? 0 : 1, transition: 'opacity 1s ease' }} 
              />

              {/* EXPANDING RADAR WAVE */}
              <g transform={`translate(${CX}, ${CY})`} style={{ opacity: isFocused ? 0 : 1, transition: 'opacity 1s ease' }}>
                <circle key={`wave-${playSessionKey}`} cx={0} cy={0} fill="none" className="stroke-[#8c7a99] radar-pulse" />
              </g>

              {/* Orbital Rings with Text Labels */}
              {RINGS.map((r, i) => {
                const isRingActive = waveRing === i;
                const ringTransition = isRingActive 
                  ? { transition: "stroke 0.1s ease-out, opacity 1s ease" } 
                  : { transition: "stroke 1.2s ease-in, opacity 1s ease" };
                  
                const textTransition = isRingActive
                  ? { transition: "fill 0.1s ease-out, filter 0.1s ease-out, opacity 1s ease" }
                  : { transition: "fill 1.2s ease-in, filter 1.2s ease-in, opacity 1s ease" };

                return (
                  <g key={`ring-${i}`} transform={`translate(${CX}, ${CY})`} style={{ opacity: isFocused ? 0 : 1 }}>
                    <circle cx={0} cy={0} r={r} fill="none" className="stroke-zinc-800" strokeWidth="2" strokeDasharray="10 15" style={ringTransition} />
                    <circle 
                      cx={0} cy={0} r={r} fill="none" 
                      className={isRingActive ? "stroke-[#8c7a99]/40" : "stroke-[#8c7a99]/10"} 
                      strokeWidth="12" 
                      style={ringTransition}
                    />
                    <text 
                      x={0} y={-r - 45} textAnchor="middle" 
                      className={`${isRingActive ? "fill-zinc-300 drop-shadow-[0_0_10px_rgba(255,255,255,0.5)]" : "fill-zinc-600"} font-mono text-[28px] font-bold tracking-[0.3em] uppercase pointer-events-none select-none`}
                      style={textTransition}
                    >
                      {t(getLevelName(i))}
                    </text>
                  </g>
                )
              })}

              {/* Pipeline Arrows (Visible only in Focused mode) */}
              <g transform={`translate(${CX}, ${CY})`} style={{ opacity: isFocused ? 1 : 0, transition: 'opacity 1s ease 0.5s' }}>
                {mainNodes.map((_, i) => {
                  const startAngle = (megaRingAngleOffset * i) - 90 + ARROW_OFFSET_DEG;
                  const endAngle = (megaRingAngleOffset * (i + 1)) - 90 - ARROW_OFFSET_DEG;
                  
                  const startPt = polarToCartesian(MEGA_RING_R, startAngle);
                  const endPt = polarToCartesian(MEGA_RING_R, endAngle);
                  
                  // Arrow path drawing an arc along the Mega-Ring
                  const pathD = `M ${startPt.x} ${startPt.y} A ${MEGA_RING_R} ${MEGA_RING_R} 0 0 1 ${endPt.x} ${endPt.y}`;
                  
                  return (
                    <path 
                      key={`arrow-${i}`}
                      d={pathD}
                      fill="none"
                      stroke="#8c7a99"
                      strokeWidth="4"
                      strokeDasharray="10 10"
                      markerEnd="url(#arrowhead)"
                      className="opacity-40"
                    />
                  );
                })}
              </g>

              {/* Nodos Principales y Satélites */}
              <g transform={`translate(${CX}, ${CY})`}>
                {mainNodes.map((node, mainIdx) => {
                  // Posición Normal en Anillos
                  const ringNodes = nodesByRing[node.ring as keyof typeof nodesByRing] || [];
                  const nodeIndex = ringNodes.findIndex(n => n.id === node.id);
                  const normalAngle = (360 / ringNodes.length) * nodeIndex - 30;
                  const normalPos = polarToCartesian(RINGS[node.ring], normalAngle);
                  
                  // Posición Focused en Mega-Anillo Secuencial
                  const focusedAngle = (megaRingAngleOffset * mainIdx) - 90;
                  const focusedPos = polarToCartesian(MEGA_RING_R, focusedAngle);

                  // Posición Efectiva actual (se anima fluidamente por CSS)
                  const pos = isFocused ? focusedPos : normalPos;
                  
                  const isPrimary = node.type === 'primary';
                  const isSelected = selectedNode?.id === node.id;
                  
                  // Si estamos en foco, todos los nodos tienen color normal EXCEPTO el seleccionado que brilla.
                  // Si no estamos en foco, el brillo depende de la onda.
                  const isWaveHit = !isFocused && waveRing === node.ring;
                  const isActive = isSelected || isWaveHit;
                  
                  const nodeTransition = isWaveHit 
                    ? { transition: "fill 0.1s ease-out, stroke 0.1s ease-out" } 
                    : { transition: "fill 1.2s ease-in, stroke 1.2s ease-in" };

                  let hexColor = isPrimary ? "stroke-white fill-zinc-900" : "stroke-[#8c7a99] fill-black";
                  let filter = "url(#neon-primary)";

                  if (isActive) {
                    hexColor = "stroke-white fill-[#8c7a99]/40"; 
                    filter = "url(#neon-active)";
                  } else if (isSelected) {
                    // Ya no se usa porque isSelected => isActive
                  } else if (isFocused) {
                    // En estado de foco, los nodos no seleccionados se apagan levemente
                    hexColor = "stroke-[#8c7a99]/50 fill-black";
                    filter = "none";
                  }

                  const tagColor = isActive ? "fill-white" : isFocused ? "fill-zinc-600" : "fill-zinc-500";
                  const labelColor = isActive ? "fill-white" : isFocused ? "fill-zinc-500" : "fill-zinc-400";
                  
                  const hexRadius = 120; 
                  const textOffset = 140; 
                  
                  const satellites = getSatellites(node.id);

                  return (
                    <g key={node.id}>
                      {/* Transición Suave de Layout (Transform) */}
                      <g 
                        style={{ 
                          transform: `translate(${pos.x}px, ${pos.y}px)`, 
                          transition: "transform 1.2s cubic-bezier(0.22, 1, 0.36, 1)" 
                        }}
                      >
                        <g 
                          className={`cursor-pointer transition-transform duration-300 ease-in-out hover:scale-105 ${isSelected ? 'scale-110' : ''}`}
                          onClick={() => setSelectedNode(node)}
                        >
                          <circle cx={0} cy={0} r={hexRadius} fill="transparent" />

                          <polygon 
                            points={drawHexagon(hexRadius)}
                            className={`${hexColor} ${isActive ? 'stroke-[6px]' : 'stroke-[4px]'}`}
                            filter={filter}
                            style={nodeTransition}
                          />

                          <circle cx={0} cy={0} r="10" className={isActive ? "fill-white" : "fill-[#8c7a99]"} style={nodeTransition} />

                          <text 
                            x={0} y={35} 
                            textAnchor="middle" 
                            className={`${labelColor} font-mono font-bold text-[22px] pointer-events-none select-none`}
                            style={nodeTransition}
                          >
                            {t(node.label)}
                          </text>
                          
                          <text 
                            x={0} y={-textOffset} 
                            textAnchor="middle" 
                            className={`font-mono font-bold text-[32px] pointer-events-none select-none ${tagColor}`}
                            style={nodeTransition}
                          >
                            {node.tag}
                          </text>
                          
                          {satellites.length > 0 && satellites.map((sat, sIdx) => {
                            const satRadius = 55;
                            const satDist = 180 + (sIdx * 30); 
                            const isSatSelected = selectedNode?.id === sat.id;
                            const isSatActive = isSatSelected || isWaveHit;
                            
                            return (
                              <g key={sat.id} className="sat-orbit">
                                <g transform={`translate(${satDist}, 0)`}>
                                  <g 
                                    className="sat-counter cursor-pointer transition-transform duration-300 ease-in-out hover:scale-110"
                                    onClick={(e) => { 
                                      e.stopPropagation(); 
                                      setSelectedNode(sat); 
                                    }}
                                  >
                                    <circle cx={0} cy={0} r={satRadius} fill="transparent" />
                                    <polygon 
                                      points={drawHexagon(satRadius)}
                                      className={`stroke-red-500 ${isSatActive ? 'fill-red-500/40 stroke-[4px]' : 'fill-red-950/80'} ${isSatSelected ? 'stroke-[4px]' : 'stroke-[2px]'}`}
                                      filter="url(#neon-error)"
                                      style={nodeTransition}
                                    />
                                    <circle cx={0} cy={0} r="4" className={isSatActive ? "fill-white" : "fill-red-400"} style={nodeTransition} />
                                    
                                    <text 
                                      x={0} y={15} 
                                      textAnchor="middle" 
                                      className={`${isSatActive ? "fill-white" : "fill-zinc-300"} font-mono font-bold text-[14px] pointer-events-none select-none`}
                                      style={nodeTransition}
                                    >
                                      {sat.label}
                                    </text>
                                    
                                    <text 
                                      x={0} y={-65} 
                                      textAnchor="middle" 
                                      className={`font-mono font-bold text-[16px] pointer-events-none select-none ${isSatSelected || isSatActive ? 'fill-white' : 'fill-red-400'}`}
                                      style={nodeTransition}
                                    >
                                      {sat.tag}
                                    </text>
                                  </g>
                                </g>
                              </g>
                            )
                          })}

                        </g>
                      </g>
                    </g>
                  );
                })}
              </g>

            </svg>

            {/* Centered Modal inside SVG container */}
            <AnimatePresence>
              {selectedNode && (
                <motion.div
                  initial={{ scale: 0.95, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.95, opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center pointer-events-none z-50"
                >
                  <div 
                    className={`pointer-events-auto bg-[#050505]/95 border ${selectedNode.type === 'error' ? 'border-red-900/40' : 'border-[#8c7a99]/40'} p-8 max-w-lg w-full relative shadow-[0_0_50px_rgba(140,122,153,0.15)] ring-1 ring-white/5 mx-4`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className={`absolute left-0 top-0 bottom-0 w-1 ${selectedNode.type === 'error' ? 'bg-gradient-to-b from-red-600 to-transparent' : 'bg-gradient-to-b from-[#8c7a99] to-transparent'}`} />
                    
                    <button 
                      onClick={() => setSelectedNode(null)}
                      className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors"
                    >
                      ✕
                    </button>
                    
                    <div className="flex flex-col gap-1 mb-6 pl-2">
                      <span className={`text-[10px] font-mono ${selectedNode.type === 'error' ? 'text-red-500' : 'text-[#8c7a99]'} uppercase tracking-[0.2em]`}>
                        {t(getLevelName(selectedNode.ring))} · {selectedNode.type}
                      </span>
                      <span className="text-2xl font-black text-white uppercase tracking-tight drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]">
                        {t(selectedNode.label)} <span className="text-zinc-500 font-light text-xl">[{selectedNode.tag}]</span>
                      </span>
                    </div>
                    
                    <div className="pl-2">
                      <p className={`text-xs sm:text-sm text-zinc-300 font-mono leading-relaxed uppercase p-5 border shadow-inner ${selectedNode.type === 'error' ? 'bg-red-950/20 border-red-900/30' : 'bg-[#8c7a99]/5 border-[#8c7a99]/10'}`}>
                        {t(selectedNode.desc)}
                      </p>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </section>
    </>
  );
}
