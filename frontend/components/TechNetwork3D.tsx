"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useRef, useState, useMemo, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Html, Line, Sphere } from "@react-three/drei";
import * as THREE from "three";
import { motion, AnimatePresence } from "framer-motion";

const TECHNOLOGIES = [
  { name: "RDKit", role: "Quimioinformática", desc: "Valida la estructura, la valencia, la quiralidad, los conformeros y propiedades fisicoquímicas. Estas señales ayudan a revisar una entrada; no determinan por sí solas viabilidad clínica ni si una molécula es un fármaco." },
  { name: "ADMET-AI + Chemprop", role: "Señales ADMET", desc: "Modelos de aprendizaje automático que producen señales sobre absorción, permeabilidad, unión a proteínas y otros endpoints. El índice de perfil sanguíneo es heurístico y sirve para comparar una serie; no es un pronóstico clínico ni una decisión de seguridad." },
  { name: "TabPFN", role: "Modelo tabular experimental", desc: "Modelo tabular opcional para experimentos concretos. Sólo debe mostrarse cuando el manifiesto declara sus pesos, cohorte y aplicabilidad; no detecta patentes ni diagnostica toxicidad por sí mismo." },
  { name: "AutoDock Vina", role: "Docking local", desc: "Motor de docking empírico que explora poses dentro de una caja y devuelve un score de Vina. Ese score sirve para ordenar poses bajo el protocolo declarado; no es una energía libre experimental ni una garantía de afinidad." },
  { name: "XGBoost", role: "Rescoring condicionado", desc: "Regresión o clasificación sobre features de una pose cuando existe un perfil y dominio de aplicabilidad válidos. Su salida es una interpretación derivada; no sustituye el score observado de Vina fuera de dominio." },
  { name: "RTMScore", role: "Rescoring experimental", desc: "Artefacto de investigación para representar contactos proteína–ligando. No se presenta como verificador físico ni como motor disponible si sus dependencias o pesos no están presentes en esta instalación." },
  { name: "CL-GNN", role: "GNN condicionada por perfil", desc: "Red neuronal de grafos para producir una señal de rescoring cuando el modelo, sus pesos y su cohorte están declarados. Las métricas y cualquier afirmación sobre sesgo dependen de la partición y el benchmark concretos; no se generalizan a todas las moléculas." },
  { name: "UMS", role: "Señal SMARTS para metales", desc: "Detecta grupos funcionales candidatos a coordinar zinc desde la estructura química, sin ejecutar docking. Es una señal de protocolo para perfiles M5-Zn concretos; no es un cálculo cuántico ni una conclusión general de actividad." },
  { name: "MolChamb (xTB)", role: "Descriptores semi-empíricos", desc: "GFN2-xTB, tight-binding semi-empírico — no DFT. Calcula HOMO/LUMO, momento dipolar, cargas parciales y polarizabilidad en ~0.1 s/mol. No es equivalente a GAFF2: son campos de fuerza distintos y aquí no se ha medido ninguna correspondencia. El índice agregado que produce es heurístico y desde 2026-09-04 no entra al score principal." },
  { name: "OpenMM", role: "Preparación opcional", desc: "Herramienta disponible para operaciones de preparación y minimización configuradas explícitamente. MolDesign no ejecuta dinámica molecular de producción ni FEP con este componente." },
  { name: "MolGraph", role: "Procedencia y contexto local", desc: "Grafo local en SQLite y FTS5 que organiza moléculas, targets, evaluaciones y evidencia para que MolChat consulte hechos persistidos. Mejora el contexto recuperado, pero no garantiza cero alucinaciones ni sustituye la validación científica." },
  { name: "MolChat IA", role: "Asistente local opcional", desc: "Qwen2.5-1.5B servido localmente cuando el modelo está instalado. Puede consultar evidencia persistida y explicar estados, pero no es la fuente primaria de resultados, no implica voz local y funciona sin red sólo después de descargar el modelo." },
  { name: "Solana Devnet", role: "Registro opcional de integridad", desc: "Memo opcional que registra hashes y metadatos técnicos de un dossier. Puede probar qué bytes se asociaron a una fecha y transacción; no valida la ciencia, no certifica autoría y no sustituye la procedencia local." }
];

const NETWORK_EDGES = [
  [0, 1], [0, 2], [0, 3],
  [1, 3], [2, 3],
  [3, 4], [3, 5],
  [4, 6], [5, 7],
  [4, 8], [5, 9],
  [6, 10], [7, 10], [8, 10],
  [9, 11], [10, 11],
  [10, 12], [11, 12],
  [1, 5], [2, 4],
  [0, 12],
  [6, 8],
];

// Distribución en 3D (balanceada, antes de la expansión masiva)
const NODE_POSITIONS = [
  new THREE.Vector3(-6, 3, 0),     // 0: RDKit
  new THREE.Vector3(-4, 5.5, 0),   // 1: ADMET-AI+Chemprop
  new THREE.Vector3(-4, -2, 0),    // 2: TabPFN
  new THREE.Vector3(-1, 1.5, 0),   // 3: Vina
  new THREE.Vector3(2, 5, 1),      // 4: XGBoost
  new THREE.Vector3(2, 1, -1),     // 5: RTMScore
  new THREE.Vector3(2, 7, 2),      // 6: CL-GNN
  new THREE.Vector3(2, -1.5, 0),   // 7: UMS
  new THREE.Vector3(4.5, 5, 0),    // 8: MolChamb
  new THREE.Vector3(4.5, -1, -1),  // 9: MolGraph
  new THREE.Vector3(7, 3, 0),      // 10: OpenMM
  new THREE.Vector3(9, 0, 1),      // 11: MolChat
  new THREE.Vector3(11, -1, 0),    // 12: Solana
];

// Constantes relativas a la cámara para el estado activo (Z = -16 simula la distancia original)
const ACTIVE_POSITIONS_LOCAL = [
  new THREE.Vector3(-13, 7.5, -16),
  new THREE.Vector3(-13, 6.0, -16),
  new THREE.Vector3(-13, 4.5, -16),
  new THREE.Vector3(-13, 3.0, -16),
  new THREE.Vector3(-13, 1.5, -16),
  new THREE.Vector3(-13, 0.0, -16),
  new THREE.Vector3(-13, -1.5, -16),
  new THREE.Vector3(13, 7.5, -16),
  new THREE.Vector3(13, 6.0, -16),
  new THREE.Vector3(13, 4.5, -16),
  new THREE.Vector3(13, 3.0, -16),
  new THREE.Vector3(13, 1.5, -16),
  new THREE.Vector3(13, 0.0, -16),
];

function Node({ targetPos, tech, onClick, isAnyActive }: any) {
  const groupRef = useRef<THREE.Group>(null);
  
  const randomOffset = useMemo(() => Math.random() * Math.PI * 2, []);
  const speed = useMemo(() => 1 + Math.random() * 1.5, []);

  useFrame(() => {
    if (groupRef.current) {
      // Tamaño constante SIEMPRE, tanto en la red como al abrir la ventana.
      const targetScale = 1.0;
        
      const currentScale = groupRef.current.scale.x;
      const nextScale = THREE.MathUtils.lerp(currentScale, targetScale, 0.1);

      groupRef.current.scale.set(nextScale, nextScale, nextScale);
      groupRef.current.position.copy(targetPos);
    }
  });

  return (
    <group ref={groupRef}>
      <Html distanceFactor={18} center style={{ pointerEvents: 'none' }}>
        <div 
          className="flex flex-col items-center select-none"
          style={{ WebkitUserSelect: 'none', userSelect: 'none' }}
          draggable={false}
        >
          <div 
            className={`text-center bg-[#0f0f0f] border border-[#8c7a99]/40 text-white dark:text-white font-mono uppercase tracking-widest whitespace-nowrap cursor-pointer pointer-events-auto hover:bg-white hover:text-black hover:shadow-[0_0_20px_rgba(255,255,255,0.8)] transition-all duration-300 shadow-[0_0_12px_rgba(255,255,255,0.15)] ${isAnyActive ? 'w-[250px] text-xs px-4 py-2.5' : 'w-[210px] text-[10px] px-3 py-1.5'}`}
            onClick={(e) => {
              e.stopPropagation();
              onClick(tech);
            }}
          >
            [ {tech.name} ]
          </div>
        </div>
      </Html>
    </group>
  );
}

function AnimatedEdge({ startNode, endNode }: { startNode: THREE.Vector3, endNode: THREE.Vector3 }) {
  const lineRef = useRef<any>(null);
  useFrame(() => {
    if (lineRef.current) {
      lineRef.current.geometry.setPositions([
        startNode.x, startNode.y, startNode.z,
        endNode.x, endNode.y, endNode.z
      ]);
    }
  });
  return (
    <Line 
      ref={lineRef} 
      points={[startNode, endNode]} 
      color="#8c7a99" 
      lineWidth={1.5} 
      transparent 
      opacity={0.3} 
    />
  );
}

function Scene({ setActiveTech, activeTech, controlsRef }: { setActiveTech: (t: any) => void, activeTech: any, controlsRef: any }) {
  const groupRef = useRef<THREE.Group>(null);
  const { camera } = useThree();
  
  // Accumulated time to allow pausing
  const timeRef = useRef(0);

  // Mantener vectores mutables para animación sin re-renders de React
  const nodesRef = useRef<THREE.Vector3[]>(
    NODE_POSITIONS.map(p => p.clone())
  );
  
  // Parámetros de caos únicos por nodo
  const randomParams = useMemo(() => NODE_POSITIONS.map(() => ({
    rx: Math.random() * 100, ry: Math.random() * 100, rz: Math.random() * 100,
    sx: 0.1 + Math.random() * 0.2, sy: 0.1 + Math.random() * 0.2, sz: 0.1 + Math.random() * 0.2
  })), []);

  useFrame((state, delta) => {
    // Solo avanzar el tiempo si NO hay una tecnología activa (pausa el movimiento)
    if (!activeTech) {
      timeRef.current += delta;
    }
    
    const t = timeRef.current;
    
    // Rotar toda la escena lentamente
    if (groupRef.current) {
      if (!activeTech) {
        groupRef.current.rotation.y += delta * 0.1;
        groupRef.current.rotation.z = Math.sin(t * 0.05) * 0.1;
      }
      // Cuando activeTech es true, la rotación del grupo se congela exactamente donde está.
      // Ya no forzamos la cámara ni el grupo a alinearse a 0.
    }

    // Actualizar coordenadas mutables (movimiento caótico lento vs slots ordenados)
    nodesRef.current.forEach((pos, i) => {
      const base = NODE_POSITIONS[i];
      const params = randomParams[i];
      
      let targetX, targetY, targetZ;

      if (activeTech) {
        // 1. Calculamos dónde deberían estar respecto a la lente de la cámara (HUD effect)
        const targetWorld = ACTIVE_POSITIONS_LOCAL[i].clone();
        camera.localToWorld(targetWorld);
        
        // 2. Convertimos esa posición global a las coordenadas locales del grupo que está rotado
        if (groupRef.current) {
          groupRef.current.worldToLocal(targetWorld);
        }
        
        targetX = targetWorld.x;
        targetY = targetWorld.y;
        targetZ = targetWorld.z;
      } else {
        // Target caótico en movimiento según 't'
        targetX = base.x + Math.sin(t * params.sx + params.rx) * 1.5;
        targetY = base.y + Math.cos(t * params.sy + params.ry) * 1.5;
        targetZ = base.z + Math.sin(t * params.sz + params.rz) * 1.5;
      }

      // Interpolar suavemente la posición actual hacia el target calculado
      pos.x = THREE.MathUtils.lerp(pos.x, targetX, 0.05);
      pos.y = THREE.MathUtils.lerp(pos.y, targetY, 0.05);
      pos.z = THREE.MathUtils.lerp(pos.z, targetZ, 0.05);
    });
  });

  return (
    <group ref={groupRef}>
      {/* Conexiones (ocultas en modo ventana emergente) */}
      {!activeTech && NETWORK_EDGES.map((edge, idx) => (
        <AnimatedEdge
          key={idx}
          startNode={nodesRef.current[edge[0]]}
          endNode={nodesRef.current[edge[1]]}
        />
      ))}

      {/* Nodos */}
      {NODE_POSITIONS.map((_, idx) => (
        <Node 
          key={idx} 
          targetPos={nodesRef.current[idx]} 
          tech={TECHNOLOGIES[idx]} 
          onClick={setActiveTech}
          isAnyActive={!!activeTech}
        />
      ))}
    </group>
  );
}

export function TechNetwork3D() {
  const { t } = useLanguage();
  const [activeTech, setActiveTech] = useState<any>(null);
  const controlsRef = useRef<any>(null);

  // Bloquear scroll al abrir ventana emergente
  useEffect(() => {
    if (activeTech) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [activeTech]);

  return (
    <>
      <div 
        className="w-full h-[500px] md:h-[600px] relative bg-transparent overflow-visible"
        style={{ zIndex: activeTech ? 60 : 0 }}
      >
        {/* Franjas invisibles para permitir el scroll natural de la página en los bordes.
            Bloquean los eventos del ratón hacia el Canvas sin usar estado de React (que tiene lag).
            DESACTIVADAS cuando hay modal activo: los nodos se reagrupan en los bordes y
            necesitan recibir clicks para intercambiar ventana emergente. */}
        <div className={`absolute top-0 left-0 w-full h-[25%] z-10 ${activeTech ? 'pointer-events-none' : ''}`} />
        <div className={`absolute bottom-0 left-0 w-full h-[25%] z-10 ${activeTech ? 'pointer-events-none' : ''}`} />
        <div className={`absolute top-0 left-0 h-full w-[15%] md:w-[25%] z-10 ${activeTech ? 'pointer-events-none' : ''}`} />
        <div className={`absolute top-0 right-0 h-full w-[15%] md:w-[25%] z-10 ${activeTech ? 'pointer-events-none' : ''}`} />
        {/* Usamos gl={{ alpha: true }} para que no tenga fondo (sin límites a la vista) */}
        <Canvas camera={{ position: [0, 0, 16], fov: 60 }} className="w-full h-full">
          <ambientLight intensity={0.5} />
          <Scene setActiveTech={setActiveTech} activeTech={activeTech} controlsRef={controlsRef} />
          <OrbitControls 
            ref={controlsRef}
            enableZoom={!activeTech} 
            enablePan={!activeTech}
            enableRotate={!activeTech}
            minDistance={5}
            maxDistance={30}
          />
        </Canvas>
        
        {/* Overlay de instrucciones */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[9px] font-mono uppercase tracking-widest text-[var(--text-dim)] pointer-events-none">
          {t("z_girar_3d")}
        </div>
      </div>

      {/* Detail Modal */}
      <AnimatePresence>
        {activeTech && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/40 pointer-events-none"
          >
            <motion.div
              initial={{ scale: 0.95, y: 15, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.95, y: 15, opacity: 0 }}
              className="bg-[#0a0a0a]/80 backdrop-blur-md border border-[#8c7a99]/40 p-8 max-w-lg w-full relative shadow-[0_0_60px_rgba(140,122,153,0.25),0_0_120px_rgba(140,122,153,0.1)] ring-1 ring-white/10 pointer-events-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Línea de acento visual */}
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-[#8c7a99] to-transparent" />
              
              <button 
                onClick={() => setActiveTech(null)}
                className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors"
              >
                ✕
              </button>
              
              <div className="flex flex-col gap-1 mb-6 pl-2">
                <span className="text-[10px] font-mono text-[#8c7a99] uppercase tracking-[0.2em]">{activeTech.role}</span>
                <span className="text-2xl font-black text-white uppercase tracking-tight drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]">{activeTech.name}</span>
              </div>
              
              <div className="pl-2">
                <p className="text-xs sm:text-sm text-zinc-300 font-mono leading-relaxed uppercase bg-[#8c7a99]/5 p-5 border border-[#8c7a99]/10 shadow-inner">
                  {t(activeTech.desc)}
                </p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
