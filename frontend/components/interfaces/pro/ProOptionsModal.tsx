"use client";
import { useScrollLock } from "@/hooks/useScrollLock";
import { useLanguage } from "../../../context/LanguageContext";

import React, { useState, useRef, useEffect } from "react";
import {
  X, Dna, Cpu, Zap, Brain, Sparkles,
  Box, Crosshair, Sliders, Gauge,
  Layers, ShieldCheck, Atom, Info, Target,
  ChevronDown, ChevronUp,
} from "lucide-react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Edges, Sphere } from "@react-three/drei";

// ── Tipos ─────────────────────────────────────────────────────
import { encenderMotor, inventarioDeMotores, type InventarioDeMotores } from "../../../lib/api";
import { BADGE_PROXIMAMENTE, esProximamente, textoProximamente } from "../../../lib/motores";

export interface DockingEngineConfig {
  engine: "vina" | "qvina2" | "diffdock";
  peptideEngine: "esmfold" | "esmfold-pro" | "esmfold-experimental" | "colabfold" | null;
  gnnPrecision: "fp32" | "fp16";
}

export interface GridBoxConfig {
  centerX: number;
  centerY: number;
  centerZ: number;
  sizeX: number;
  sizeY: number;
  sizeZ: number;
  exhaustiveness: number;
  numModes: number;
}

export interface AdvancedConfig {
  /**
   * pH al que se protona el LIGANDO antes de acoplarlo.
   *
   * No es un ajuste del motor: cambia la {t("op_ph_especie")} que entra a Vina. Un
   * ácido carboxílico a pH 1 se acopla neutro y a pH 7.4 como anión, y ésa es
   * una molécula distinta con otra huella y otro resultado. Medido sobre el
   * runtime empaquetado: ibuprofeno neutro a pH 1-4 y `[O-]` de 7.4 en
   * adelante; lisina da tres especies distintas entre pH 1 y 12.
   */
  protonationPh: number;
  numWorkers: number;
  parallelDocks: number;
  enableSelectivity: boolean;
  selectedAntiTargets: string[];
  enableMMGBSA: boolean;
  mmgbsaSteps: number;
  enableADMET: boolean;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onApply: (
    engine: DockingEngineConfig,
    gridBox: GridBoxConfig,
    advanced: AdvancedConfig,
    hotspots?: string[]
  ) => void;
  initialEngine?: DockingEngineConfig;
  initialGridBox?: GridBoxConfig;
  initialAdvanced?: AdvancedConfig;
  initialHotspots?: readonly string[];
  targetHotspots?: Array<{ name: string; importance: number }>;
  gpuAvailable?: boolean;
  gpuCuda?: boolean;
  isPeptide?: boolean;
  /**
   * El caso ya tiene una corrida TERMINADA en su sistema estructural.
   *
   * Congela la caja y los residuos —lo que define el sistema— y deja libre el
   * protocolo. La versión anterior no abría siquiera este modal: cambiar la
   * exhaustiveness para comprobar convergencia obligaba a crear otro caso, y
   * eso no protegía ninguna comparación. Lo que hay que impedir es comparar en
   * silencio dos corridas incomparables, y de eso se encarga el libro de
   * corridas, que enseña el protocolo de cada una.
   */
  systemSealed?: boolean;
}

// ── Valores por defecto ─────────────────────────────────────────
const DEFAULT_ENGINE: DockingEngineConfig = {
  engine: "vina",
  peptideEngine: null,
  gnnPrecision: "fp32",
};

const DEFAULT_GRID: GridBoxConfig = {
  centerX: 0.0,
  centerY: 0.0,
  centerZ: 0.0,
  sizeX: 22.5,
  sizeY: 22.5,
  sizeZ: 22.5,
  exhaustiveness: 8,
  numModes: 9,
};

const DEFAULT_ADVANCED: AdvancedConfig = {
  numWorkers: 4,
  parallelDocks: 2,
  enableSelectivity: false,
  selectedAntiTargets: ["5VA1", "4NY4", "4NC3", "1SO2", "6MVW"],
  // 7.4 es el de siempre: una corrida que no lo toque produce exactamente el
  // mismo SMILES protonado, el mismo hash y la misma entrada de caché que
  // antes de que este campo existiera. Verificado sobre cuatro moléculas.
  protonationPh: 7.4,
  enableMMGBSA: true,
  mmgbsaSteps: 1000,
  // OPT-IN, no opt-out. ADMET-AI es un modelo aparte que se carga en local y
  // cuya primera ejecución domina el reloj de la corrida; el backend ya lo
  // trata como apagado por defecto (`run_admet_ai=False` cuando la clave no
  // viene). Este valor es el mismo defecto, dicho en la UI.
  enableADMET: false,
};

// ── Sub-componentes ─────────────────────────────────────────────

function SectionHeader({ icon: Icon, label, subtitle }: { icon: any; label: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-3 mb-4 pb-3 border-b border-zinc-800/60">
      <div className="h-8 w-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
        <Icon size={16} />
      </div>
      <div className="min-w-0">
        <h3 className="text-sm font-mono font-black text-white uppercase tracking-wider">{label}</h3>
        {subtitle && <p className="text-sm font-mono text-zinc-500 mt-0.5 truncate">{subtitle}</p>}
      </div>
    </div>
  );
}

function RadioCard({
  selected,
  onClick,
  label,
  badge,
  badgeStyle,
  desc,
  meta,
  disabled,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
  badge?: string;
  badgeStyle?: { bg: string; text: string };
  desc: string;
  meta?: { icon: any; text: string };
  disabled?: boolean;
}) {
  return (
    <label
      className={`flex items-start gap-3 p-3.5 rounded-xl border transition-all duration-200 ${
        disabled
          ? "opacity-30 cursor-not-allowed border-zinc-800/30 bg-transparent"
          : selected
          ? "border-purple-500/40 bg-purple-500/[0.06] cursor-pointer"
          : "border-zinc-800/60 bg-zinc-900/40 hover:border-zinc-700 cursor-pointer"
      }`}
    >
      <input
        type="radio"
        checked={selected}
        onChange={onClick}
        disabled={disabled}
        className="mt-0.5 w-3.5 h-3.5 accent-purple-500"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-sm font-bold font-mono uppercase tracking-wider ${disabled ? "text-zinc-600" : selected ? "text-white" : "text-zinc-300"}`}>
            {label}
          </span>
          {badge && badgeStyle && (
            <span
              className="text-sm px-1.5 py-0.5 rounded font-mono font-bold uppercase"
              style={{ backgroundColor: badgeStyle.bg, color: badgeStyle.text }}
            >
              {badge}
            </span>
          )}
        </div>
        <p className={`text-sm mt-1 leading-relaxed ${disabled ? "text-zinc-700" : "text-zinc-500"}`}>{desc}</p>
        {meta && !disabled && (
          <div className="flex items-center gap-1.5 mt-1.5">
            <meta.icon size={11} className="text-zinc-500" />
            <span className="text-sm font-mono text-zinc-500">{meta.text}</span>
          </div>
        )}
      </div>
    </label>
  );
}

// El estado del interruptor se pintaba SÓLO con clases de color. Para quien
// usa lector de pantalla —y para cualquier prueba que quiera saber si un
// módulo del pipeline está encendido— eso es un botón sin nombre y sin
// estado. `role="switch"` + `aria-checked` dicen lo mismo que el color.
function ToggleSwitch({ enabled, onChange, disabled, label }: { enabled: boolean; onChange: () => void; disabled?: boolean; label?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      onClick={onChange}
      disabled={disabled}
      className={`relative h-5 w-9 shrink-0 overflow-hidden rounded-full transition-colors duration-200 cursor-pointer ${
        disabled ? "opacity-30 cursor-not-allowed" : ""
      } ${enabled ? "bg-purple-600" : "bg-zinc-700"}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-200 ${
          enabled ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
  label,
  disabled = false,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className={`text-sm font-mono uppercase tracking-wider ${disabled ? "text-zinc-600" : "text-zinc-500"}`}>{label}</label>
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => onChange(Math.max(min, value - step))}
          disabled={disabled}
          className="w-7 h-7 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-600 flex items-center justify-center text-sm font-mono transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:text-zinc-400 disabled:hover:border-zinc-700"
        >
          −
        </button>
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            if (!isNaN(v)) onChange(Math.min(max, Math.max(min, v)));
          }}
          className="w-16 text-center bg-black border border-zinc-700 rounded-lg py-1.5 font-mono text-sm text-white outline-none focus:border-purple-500/40 transition-colors disabled:cursor-not-allowed disabled:text-zinc-500"
        />
        <button
          onClick={() => onChange(Math.min(max, value + step))}
          disabled={disabled}
          className="w-7 h-7 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-600 flex items-center justify-center text-sm font-mono transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:text-zinc-400 disabled:hover:border-zinc-700"
        >
          +
        </button>
      </div>
    </div>
  );
}

// ── Mini Visualizador del Grid Box (Reactivo 3D) ───────────────────────
// La cámara se reposiciona SOLO cuando el centro del grid cambia (nuevo
// receptor o ajuste manual). Cuando el usuario rota/zoomea con OrbitControls,
// NO se le pelea la interacción (solo re-centramos si cambió el target).
// EFICIENCIA (2026-09-01). Esto era un `useFrame`, es decir un bucle de render a
// 60 fps mientras el modal estuviera abierto, para una caja que no se mueve. El
// cuerpo del bucle no hacía nada el 99.9% de los fotogramas: comparaba el centro
// con el anterior y salía. En un equipo modesto eso es la GPU y un núcleo
// ocupados por una previsualización estática.
//
// Ahora la cámara se recoloca en un efecto —cuando el centro cambia de verdad— y
// el `Canvas` renderiza bajo demanda (`frameloop="demand"`): un fotograma cuando
// algo cambia, y ninguno mientras nadie toca nada. `invalidate()` es lo que pide
// ese fotograma; `OrbitControls` lo llama solo al arrastrar.
function CameraRig({ center, distance }: { center: [number, number, number]; distance: number }) {
  const { camera, invalidate } = useThree();
  const controlsRef = useRef<any>(null);
  const [cx, cy, cz] = center;

  useEffect(() => {
    camera.position.set(cx + distance * 0.8, cy + distance * 0.6, cz + distance);
    camera.lookAt(cx, cy, cz);
    camera.updateProjectionMatrix();
    if (controlsRef.current) {
      controlsRef.current.target.set(cx, cy, cz);
      controlsRef.current.update();
    }
    invalidate();
  }, [camera, invalidate, cx, cy, cz, distance]);

  return <OrbitControls ref={controlsRef} enableZoom enablePan makeDefault />;
}

function GridBoxPreview({ config }: { config: GridBoxConfig }) {
  // Ajuste dinámico de cámara basado en el tamaño más grande
  const maxDim = Math.max(config.sizeX, config.sizeY, config.sizeZ);
  const cameraDistance = Math.max(50, maxDim * 2.5);

  return (
    <div className="relative w-full aspect-[4/3] bg-black/60 rounded-xl border border-zinc-800/60 overflow-hidden">
      
      {/* HUD 2D superpuesto al 3D */}
      <div className="absolute top-3 left-3 z-10 pointer-events-none flex flex-col gap-1">
        <span className="text-sm font-mono font-bold text-zinc-400">CENTRO</span>
        <span className="text-sm font-mono text-zinc-500">
          X: {config.centerX.toFixed(1)} / Y: {config.centerY.toFixed(1)} / Z: {config.centerZ.toFixed(1)}
        </span>
      </div>
      
      <div className="absolute bottom-3 left-3 right-3 flex justify-between z-10 pointer-events-none">
        <span className="text-sm font-mono text-zinc-500">X: {config.sizeX.toFixed(1)} Å</span>
        <span className="text-sm font-mono text-zinc-500">Y: {config.sizeY.toFixed(1)} Å</span>
        <span className="text-sm font-mono text-zinc-500">Z: {config.sizeZ.toFixed(1)} Å</span>
      </div>

      {/* CameraRig re-centra la cámara cuando cambian las coordenadas, sin
          re-montar el Canvas y sin un bucle de render permanente. */}
      <Canvas
        frameloop="demand"
        camera={{ position: [config.centerX + cameraDistance * 0.8, config.centerY + cameraDistance * 0.6, config.centerZ + cameraDistance], fov: 45 }}
        className="cursor-move"
      >
        <ambientLight intensity={0.5} />
        <pointLight position={[config.centerX + 100, config.centerY + 100, config.centerZ + 100]} intensity={1} />
        
        {/* Helper de ejes: X (rojo), Y (verde), Z (azul) — centrado en el grid */}
        <group position={[config.centerX, config.centerY, config.centerZ]}>
          <axesHelper args={[maxDim * 1.5]} />
        </group>

        <CameraRig center={[config.centerX, config.centerY, config.centerZ]} distance={cameraDistance} />

        {/* Caja envolvente */}
        <mesh position={[config.centerX, config.centerY, config.centerZ]}>
          <boxGeometry args={[config.sizeX, config.sizeY, config.sizeZ]} />
          <meshBasicMaterial color="#a855f7" transparent opacity={0.06} depthWrite={false} />
          {/* Bordes brillantes para el grid */}
          <Edges scale={1} threshold={15} color="#c084fc" opacity={0.6} transparent />
        </mesh>

        {/* Esfera central del bolsillo */}
        <Sphere args={[maxDim * 0.02 + 0.5, 16, 16]} position={[config.centerX, config.centerY, config.centerZ]}>
          <meshBasicMaterial color="#e9d5ff" />
        </Sphere>
      </Canvas>
    </div>
  );
}

// ── Componente Principal ─────────────────────────────────────────
export default function ProOptionsModal({
  isOpen,
  onClose,
  onApply,
  initialEngine,
  initialGridBox,
  initialAdvanced,
  initialHotspots,
  targetHotspots = [],
  gpuAvailable = false,
  gpuCuda = false,
  isPeptide = false,
  systemSealed = false,
}: Props) {
  const { t } = useLanguage();
  useScrollLock(isOpen);
  const [engine, setEngine] = useState<DockingEngineConfig>(initialEngine || DEFAULT_ENGINE);

  // ENG-001. Este menú ofrecía siete motores sin comprobar ninguno. En una
  // instalación limpia sólo AutoDock Vina existe: QuickVina 2 no se empaqueta, y
  // DiffDock, ESMFold, ESMFold Pro/RFdiffusion y ColabFold son clientes de
  // servicios externos que esta versión no instala ni levanta. Elegir uno llevaba
  // a un preflight bloqueado —o, por la ruta peptídica, a una pose de Vina— tras
  // haber configurado todo lo demás.
  //
  // `GET /evaluation/engines` dice qué puede ejecutar ESTA instalación. Mientras
  // la respuesta no llega no se apaga nada: un motor real no puede quedar
  // deshabilitado por una consulta lenta.
  const [motores, setMotores] = useState<InventarioDeMotores | null>(null);
  useEffect(() => {
    if (!isOpen) return;
    let vivo = true;
    inventarioDeMotores()
      .then((inv) => vivo && setMotores(inv))
      .catch(() => vivo && setMotores(null));
    return () => {
      vivo = false;
    };
  }, [isOpen]);

  const estadoMotor = (id: string): {
    disponible: boolean;
    motivo: string | null;
    accion: string | null;
    estado: string | null;
    requiere: string;
  } => {
    // Mientras el inventario no responde no se puede afirmar que un motor
    // exista en esta instalación. El backend es la autoridad; deshabilitar
    // provisionalmente evita seleccionar un motor fantasma durante la carrera.
    const ausente = { disponible: false, motivo: "Comprobando motores disponibles…", accion: null, estado: "UNKNOWN", requiere: "" };
    if (!motores) return ausente;
    const encontrado = [...motores.docking, ...motores.peptido].find((m) => m.id === id);
    if (!encontrado) return ausente;
    return {
      disponible: encontrado.disponible,
      motivo: encontrado.motivo,
      accion: encontrado.accion,
      estado: encontrado.estado,
      requiere: encontrado.requiere,
    };
  };

  // ENG-004. Un motor que esta version no ejecuta se anuncia como
  // «Proximamente», no como averia. La distincion la hace `requiere`, que viene
  // del backend: ESMFold no esta disponible hasta descargarlo, pero la
  // aplicacion sabe resolverlo y por eso conserva su etiqueta real.
  const badgeDe = (id: string, badgeReal: string): string => {
    const st = estadoMotor(id);
    if (st.disponible) return badgeReal;
    return esProximamente(st) ? BADGE_PROXIMAMENTE : badgeReal;
  };
  const descDe = (id: string, etiqueta: string, descReal: string): string => {
    const st = estadoMotor(id);
    if (st.disponible) return descReal;
    if (esProximamente(st)) return textoProximamente(etiqueta);
    return st.motivo ?? descReal;
  };

  // Encender es un gesto del investigador, no un efecto de abrir el modal:
  // cargar un checkpoint de 8.4 GB ocupa memoria y tarda. Al terminar se relee
  // el inventario en vez de suponer el resultado.
  const [encendiendo, setEncendiendo] = useState<string | null>(null);
  const encender = async (id: string) => {
    setEncendiendo(id);
    try {
      await encenderMotor(id);
    } catch {
      // El estado real llega del inventario; un fallo aquí no inventa nada.
    } finally {
      try {
        setMotores(await inventarioDeMotores());
      } catch {
        /* se conserva lo que hubiera */
      }
      setEncendiendo(null);
    }
  };
  const [gridBox, setGridBox] = useState<GridBoxConfig>(initialGridBox || DEFAULT_GRID);
  const [advanced, setAdvanced] = useState<AdvancedConfig>(initialAdvanced || DEFAULT_ADVANCED);
  // Hotspots del receptor seleccionado: se inicializan con TODOS marcados.
  const [selectedHotspots, setSelectedHotspots] = useState<string[]>(
    () => targetHotspots.map((h) => h.name)
  );

  // Re-sincronizar el borrador interno con el caso SOLO al abrir. El modal
  // permanece montado, por lo que `useState(initial...)` no basta al cambiar
  // de caso/configuración. Los hotspots personalizados se restauran; si no
  // existen, el significado es «usar todos los del catálogo».
  const prevOpen = useRef(isOpen);
  useEffect(() => {
    if (isOpen && !prevOpen.current) {
      if (initialEngine) setEngine(initialEngine);
      if (initialGridBox) setGridBox(initialGridBox);
      if (initialAdvanced) setAdvanced(initialAdvanced);
      setSelectedHotspots(
        initialHotspots ? [...initialHotspots] : targetHotspots.map((h) => h.name),
      );
    }
    prevOpen.current = isOpen;
  }, [initialAdvanced, initialEngine, initialGridBox, initialHotspots, isOpen, targetHotspots]);

  const windowRef = useRef<HTMLDivElement>(null);

  // Animar entrada con la API nativa del navegador.
  useEffect(() => {
    if (!isOpen || !windowRef.current) return;
    windowRef.current.animate(
      [
        { transform: "translateY(16px) scale(0.96)", opacity: 0 },
        { transform: "translateY(0) scale(1)", opacity: 1 },
      ],
      { duration: 300, easing: "cubic-bezier(0.16, 1, 0.3, 1)" },
    );
  }, [isOpen]);

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

  if (!isOpen) return null;

  const handleApply = () => {
    onApply(engine, gridBox, advanced, selectedHotspots);
    onClose();
  };

  // Los residuos son parte del SISTEMA, no del protocolo: cambiarlos mueve la
  // región que guía la búsqueda. El guard va aquí y no sólo en el botón para
  // que una ruta nueva no se lo salte.
  const toggleHotspot = (name: string) => {
    if (systemSealed) return;
    setSelectedHotspots((prev) =>
      prev.includes(name) ? prev.filter((h) => h !== name) : [...prev, name]
    );
  };

  const toggleAllHotspots = () => {
    if (systemSealed) return;
    setSelectedHotspots(
      selectedHotspots.length === targetHotspots.length
        ? []
        : targetHotspots.map((h) => h.name)
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200" role="presentation">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-xl" onClick={onClose} />

      {/* Ventana */}
      <div
        ref={windowRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pro-options-title"
        className="relative w-full max-w-6xl max-h-[90vh] bg-zinc-950/95 border border-purple-500/20 rounded-2xl shadow-[0_0_40px_-15px_rgba(168,85,247,0.18)] backdrop-blur-2xl flex flex-col overflow-hidden"
      >
        {/* ── Header ── */}
        <div className="flex-none px-6 py-4 border-b border-zinc-800/80 bg-black/60 backdrop-blur-md flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-300">
              <Sliders size={18} />
            </div>
            <div>
              <h2 id="pro-options-title" className="text-sm font-bold font-mono text-white uppercase tracking-wider">
                {t("op_titulo")}
              </h2>
              <p className="text-sm text-zinc-500 font-mono mt-0.5">
                {t("op_subtitulo")}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("op_cerrar")}
            className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white hover:border-purple-500/30 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* ── Body: 3 Columnas ── */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* ═══ COLUMNA 1: {t("op_motor_docking")} ═══ */}
            <div>
              <SectionHeader icon={Dna} label={t("op_motor_docking")} subtitle={t("op_sub_herramienta")} />

              {/* Moléculas pequeñas */}
              <div className="space-y-2 mb-4">
                <p className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Atom size={12} /> {t("op_moleculas_pequenas")}
                </p>

                <RadioCard
                  selected={engine.engine === "vina"}
                  onClick={() => setEngine({ ...engine, engine: "vina" })}
                  disabled={!estadoMotor("vina").disponible}
                  label="AutoDock Vina 1.2.7"
                  badge={t("pr_mot_clasico")}
                  badgeStyle={{ bg: "rgba(168,85,247,0.15)", text: "#a78bfa" }}
                  desc={estadoMotor("vina").motivo ?? t("auto_2e24a6f6267b")}
                  meta={{ icon: Cpu, text: "~20s" }}
                />

                <RadioCard
                  selected={engine.engine === "qvina2"}
                  onClick={() => setEngine({ ...engine, engine: "qvina2" })}
                  disabled={!estadoMotor("qvina2").disponible}
                  label="QuickVina 2"
                  badge={badgeDe("qvina2", t("pr_mot_rapido"))}
                  badgeStyle={{ bg: "rgba(251,191,36,0.15)", text: "#fbbf24" }}
                  desc={descDe("qvina2", "QuickVina 2", t("auto_09e250071934"))}
                  meta={{ icon: Zap, text: "~8s" }}
                />

                <RadioCard
                  selected={engine.engine === "diffdock"}
                  onClick={() => setEngine({ ...engine, engine: "diffdock" })}
                  disabled={!estadoMotor("diffdock").disponible}
                  label="DiffDock"
                  badge={badgeDe("diffdock", t("pr_mot_difusion"))}
                  badgeStyle={{ bg: "rgba(139,92,246,0.15)", text: "#8b5cf6" }}
                  desc={descDe("diffdock", "DiffDock", t("pr_mot_difusion_d"))}
                  meta={{ icon: Sparkles, text: "~1-5 min" }}
                />
              </div>

              {/* Péptidos */}
              <div className="space-y-2 pt-3 border-t border-zinc-800/60">
                <p className="text-sm font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Brain size={12} /> {t("auto_7987f4801c2c")}
                  {!isPeptide && <span className="text-sm text-zinc-500 ml-1 font-mono normal-case font-normal">{t("auto_a7ff1c2aeb72")}</span>}
                </p>

                {(["esmfold", "esmfold-pro", "colabfold", "esmfold-experimental"] as const).map((pe) => {
                  const labels: Record<string, { label: string; badge: string; desc: string }> = {
                    esmfold: { label: "ESMFold", badge: "PLEGADO", desc: t("auto_14578be07d4d") },
                    "esmfold-pro": { label: "ESMFold Pro", badge: "PRECISO", desc: "Plegamiento + refinamiento OpenMM." },
                    colabfold: { label: "ColabFold", badge: "PREDICTIVO", desc: t("auto_0ec637ca2747") },
                    "esmfold-experimental": { label: "RFdiffusion", badge: "EXPERIMENTAL", desc: t("auto_9331807fc431") },
                  };
                  const info = labels[pe];
                  const gpuNeeded = pe === "esmfold-experimental";
                  return (
                    <RadioCard
                      key={pe}
                      selected={engine.peptideEngine === pe}
                      onClick={() => setEngine({ ...engine, peptideEngine: engine.peptideEngine === pe ? null : pe })}
                      disabled={!isPeptide || (gpuNeeded && !gpuAvailable) || !estadoMotor(pe).disponible}
                      label={info.label}
                      badge={badgeDe(pe, info.badge)}
                      badgeStyle={{
                        bg: pe === "esmfold-experimental"
                          ? "rgba(251,191,36,0.15)"
                          : pe === "esmfold-pro"
                          ? "rgba(168,85,247,0.15)"
                          : pe === "colabfold"
                          ? "rgba(52,211,153,0.15)"
                          : "rgba(56,189,248,0.15)",
                        text: pe === "esmfold-experimental"
                          ? "#fbbf24"
                          : pe === "esmfold-pro"
                          ? "#a78bfa"
                          : pe === "colabfold"
                          ? "#34d399"
                          : "#38bdf8",
                      }}
                      desc={descDe(pe, info.label, info.desc)}
                    />
                  );
                })}

                {/* ENG-002. Un motor descargable no es un motor ausente: se
                    puede resolver desde aquí. La acción sale del backend —él
                    sabe si faltan los pesos, una librería o sólo encenderlo— y
                    esta interfaz no la deduce por su cuenta. */}
                {(["esmfold", "esmfold-pro", "colabfold", "esmfold-experimental"] as const)
                  .map((pe) => ({ pe, st: estadoMotor(pe) }))
                  .filter(({ st }) => st.accion === "descargar" || st.accion === "encender")
                  .map(({ pe, st }) => (
                    <div key={`accion-${pe}`} className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2">
                      <span className="text-sm text-zinc-400">
                        {st.accion === "descargar"
                          ? `${pe} necesita descargarse una vez`
                          : `${pe} está instalado y apagado`}
                      </span>
                      {st.accion === "encender" ? (
                        <button
                          type="button"
                          onClick={() => encender(pe)}
                          disabled={encendiendo === pe}
                          className="rounded border border-purple-500/40 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-purple-300 transition-colors hover:bg-purple-950/40 disabled:opacity-50"
                        >
                          {encendiendo === pe ? t("auto_43584ce3b53d") : "Encender"}
                        </button>
                      ) : (
                        <a
                          href="/launcher"
                          className="rounded border border-cyan-500/40 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-cyan-300 transition-colors hover:bg-cyan-950/30"
                        >
                          Abrir gestor
                        </a>
                      )}
                    </div>
                  ))}
              </div>

              {/* {t("op_precision_gnn")} */}
              {!isPeptide && (
                <div className="space-y-2 pt-3 border-t border-zinc-800/60">
                  <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
                    <Gauge size={11} /> {t("op_precision_gnn")}
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {(["fp32", "fp16"] as const).map((p) => (
                      <button
                        key={p}
                        disabled={p === "fp16" && (!gpuAvailable || !gpuCuda)}
                        onClick={() => setEngine({ ...engine, gnnPrecision: p })}
                        className={`p-2.5 rounded-lg border text-sm font-mono font-bold uppercase transition-all ${
                          p === "fp16" && (!gpuAvailable || !gpuCuda)
                            ? "opacity-30 cursor-not-allowed border-zinc-800/30 text-zinc-600"
                            : engine.gnnPrecision === p
                            ? "border-purple-500/40 bg-purple-500/10 text-purple-300"
                            : "border-zinc-800/60 text-zinc-400 hover:border-zinc-700"
                        } cursor-pointer`}
                      >
                        <span>{p.toUpperCase()}</span>
                        {p === "fp16" && <Zap size={10} className="inline ml-1 text-amber-400" />}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ═══ COLUMNA 2: {t("op_parametros_bolsillo")} ═══ */}
            <div>
              <SectionHeader icon={Box} label={t("op_parametros_bolsillo")} subtitle={t("op_sub_donde")} />

              {/* Lógica de aplicabilidad del Grid Box */}
              {(() => {
                const isVina = !isPeptide && (engine.engine === "vina" || engine.engine === "qvina2");
                const isEsmVina = isPeptide && (engine.peptideEngine === "esmfold" || engine.peptideEngine === "esmfold-pro");
                const usesGridBox = isVina || isEsmVina;
                
                if (!usesGridBox) {
                  let reason = "";
                  if (isPeptide && engine.peptideEngine === "colabfold") reason = "ColabFold pliega el complejo entero (proteína-péptido). No requiere definir un bolsillo de unión específico.";
                  else if (isPeptide && engine.peptideEngine === "esmfold-experimental") reason = "RFdiffusion diseña/acopla mediante difusión global sobre la estructura. No utiliza un grid box clásico.";
                  else if (!isPeptide && engine.engine === "diffdock") reason = "DiffDock es un modelo generativo de difusión que busca (blind-docking) a lo largo de toda la proteína. El grid box no aplica.";
                  
                  return (
                    <div className="flex flex-col items-center justify-center h-48 border border-zinc-800/40 border-dashed rounded-xl bg-zinc-900/20 p-4 text-center">
                      <Box className="w-8 h-8 text-zinc-600 mb-3" />
                      <p className="text-sm font-semibold text-zinc-400">{t("op_no_aplica")}</p>
                      <p className="text-sm text-zinc-500 mt-2 leading-relaxed max-w-[200px]">
                        {reason}
                      </p>
                    </div>
                  );
                }

                return (
                  <div className="animate-in fade-in duration-300">
                    {/* Grid Box Preview */}
                    <GridBoxPreview config={gridBox} />

                    {systemSealed && (
                      <div className="mt-4 rounded-xl border border-purple-500/20 bg-purple-500/[0.04] p-3">
                        <p className="font-mono text-xs font-bold uppercase tracking-[0.12em] text-purple-200">
                          {t("op_sistema_sellado_titulo")}
                        </p>
                        <p className="mt-1 text-sm font-mono leading-relaxed text-zinc-300">
                          {t("op_sistema_sellado")}
                        </p>
                      </div>
                    )}

                    {/* Coordenadas del Centro */}
                    <div className="mt-4 space-y-3">
                      <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500">
                        {t("op_centro_grid")}
                      </p>
                      <div className="grid grid-cols-3 gap-2">
                        <NumberInput label="X" value={gridBox.centerX} onChange={(v) => setGridBox({ ...gridBox, centerX: v })} min={-100} max={100} step={0.5} disabled={systemSealed} />
                        <NumberInput label="Y" value={gridBox.centerY} onChange={(v) => setGridBox({ ...gridBox, centerY: v })} min={-100} max={100} step={0.5} disabled={systemSealed} />
                        <NumberInput label="Z" value={gridBox.centerZ} onChange={(v) => setGridBox({ ...gridBox, centerZ: v })} min={-100} max={100} step={0.5} disabled={systemSealed} />
                      </div>
                    </div>

                    {/* Tamaño del Grid Box */}
                    <div className="mt-4 space-y-3">
                      <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500">
                        {t("op_dimensiones_grid")}
                      </p>
                      <div className="grid grid-cols-3 gap-2">
                        <NumberInput label={t("op_tamano_x")} value={gridBox.sizeX} onChange={(v) => setGridBox({ ...gridBox, sizeX: v })} min={5} max={50} step={0.5} disabled={systemSealed} />
                        <NumberInput label={t("op_tamano_y")} value={gridBox.sizeY} onChange={(v) => setGridBox({ ...gridBox, sizeY: v })} min={5} max={50} step={0.5} disabled={systemSealed} />
                        <NumberInput label={t("op_tamano_z")} value={gridBox.sizeZ} onChange={(v) => setGridBox({ ...gridBox, sizeZ: v })} min={5} max={50} step={0.5} disabled={systemSealed} />
                      </div>
                    </div>

                    {/* Exhaustiveness & Num Modes */}
                    <div className="mt-4 space-y-3">
                      <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500">
                        {t("op_parametros_busqueda")}
                      </p>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="flex flex-col gap-1">
                          <label className="text-sm font-mono uppercase tracking-wider text-zinc-500">
                            {t("c_exhaustividad")}
                          </label>
                          <select
                            value={gridBox.exhaustiveness}
                            onChange={(e) => setGridBox({ ...gridBox, exhaustiveness: parseInt(e.target.value) })}
                            className="bg-black border border-zinc-700 rounded-lg py-1.5 px-2 font-mono text-sm text-white outline-none focus:border-purple-500/40 transition-colors cursor-pointer"
                          >
                            {[1, 2, 4, 8, 16, 24, 32].map((n) => (
                              <option key={n} value={n}>{n} {n <= 8 ? t("auto_78940da1bb6a") : n >= 24 ? t("auto_9af5776f1fea") : ""}</option>
                            ))}
                          </select>
                        </div>
                        <div className="flex flex-col gap-1">
                          <label className="text-sm font-mono uppercase tracking-wider text-zinc-500">
                            Num Modes
                          </label>
                          <select
                            value={gridBox.numModes}
                            onChange={(e) => setGridBox({ ...gridBox, numModes: parseInt(e.target.value) })}
                            className="bg-black border border-zinc-700 rounded-lg py-1.5 px-2 font-mono text-sm text-white outline-none focus:border-purple-500/40 transition-colors cursor-pointer"
                          >
                            {[1, 3, 5, 9, 15, 20].map((n) => (
                              <option key={n} value={n}>{n} poses</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Info contextual */}
                    <div className="mt-4 p-3 rounded-xl bg-purple-500/[0.04] border border-purple-500/10 flex items-start gap-2">
                      <Info size={13} className="text-purple-400 mt-0.5 shrink-0" />
                      <p className="text-sm font-mono text-zinc-400 leading-relaxed">
                        {t("op_grid_explicacion")}
                      </p>
                    </div>
                  </div>
                );
              })()}

              {/* ── Hotspots del receptor ── */}
              {targetHotspots.length > 0 && (
                <div className="mt-6 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
                      <Target size={11} /> {t("op_hotspots")}
                    </p>
                    <button
                      type="button"
                      onClick={toggleAllHotspots}
                      disabled={systemSealed}
                      className="text-[10px] font-mono font-bold uppercase tracking-wider px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white border border-zinc-700 transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-zinc-800 disabled:hover:text-zinc-300"
                    >
                      {selectedHotspots.length === targetHotspots.length
                        ? t("op_desmarcar_todos")
                        : t("op_marcar_todos")}
                    </button>
                  </div>
                  <p className="text-sm font-mono text-zinc-500 leading-relaxed">
                    {systemSealed
                      ? t("op_hotspots_fijados")
                      : t("op_hotspots_explicacion")}
                    {" "}({selectedHotspots.length}/{targetHotspots.length} activos)
                  </p>
                  <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                    {targetHotspots.map((h) => {
                      const active = selectedHotspots.includes(h.name);
                      return (
                        <button
                          key={h.name}
                          type="button"
                          onClick={() => toggleHotspot(h.name)}
                          disabled={systemSealed}
                          title={`${h.name} · importancia ${h.importance?.toFixed?.(2) ?? h.importance}`}
                          className={`px-2 py-1 rounded-lg text-[10px] font-mono font-bold transition-all border disabled:cursor-not-allowed ${
                            systemSealed ? "cursor-not-allowed" : "cursor-pointer"
                          } ${
                            active
                              ? "bg-purple-500/15 border-purple-500/40 text-purple-300"
                              : "bg-zinc-900/60 border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
                          }`}
                        >
                          {active ? "●" : "○"} {h.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* ═══ COLUMNA 3: Opciones Avanzadas ═══ */}
            <div>
              <SectionHeader icon={Sliders} label={t("op_opciones_avanzadas")} subtitle={t("op_sub_recursos")} />

              {/* Workers & Parallel Docks */}
              <div className="space-y-3">
                <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
                  <Cpu size={11} /> {t("op_recursos")}
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Procesos"
                    value={advanced.numWorkers}
                    onChange={(v) => setAdvanced({ ...advanced, numWorkers: v })}
                    min={1} max={16} step={1}
                  />
                  <NumberInput
                    label="Docks Paralelos"
                    value={advanced.parallelDocks}
                    onChange={(v) => setAdvanced({ ...advanced, parallelDocks: v })}
                    min={1} max={8} step={1}
                  />
                </div>
              </div>

              {/* ── {t("op_preparacion_ligando")} ────────────────────────────────
                  Va ANTES de los módulos del pipeline porque no es un módulo:
                  no se enciende ni se apaga, siempre ocurre. Lo que se elige
                  aquí es QUÉ MOLÉCULA entra al motor. */}
              <div className="mt-4 pt-3 border-t border-zinc-800/60">
                <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
                  <Atom size={11} /> {t("op_preparacion_ligando")}
                </p>

                <div className="mt-3 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <NumberInput
                      label={t("op_ph_protonacion")}
                      value={advanced.protonationPh}
                      onChange={(v) =>
                        // `NumberInput` suma y resta en coma flotante: sin
                        // redondear, 7.4 − 0.1 se convierte en 7.300000000000001
                        // y eso acabaría escrito en el expediente.
                        setAdvanced({ ...advanced, protonationPh: Math.round(v * 10) / 10 })
                      }
                      min={1} max={12} step={0.1}
                    />
                    {advanced.protonationPh !== DEFAULT_ADVANCED.protonationPh && (
                      <button
                        type="button"
                        onClick={() =>
                          setAdvanced({ ...advanced, protonationPh: DEFAULT_ADVANCED.protonationPh })
                        }
                        className="rounded-lg border border-zinc-700 px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider text-zinc-400 transition-colors hover:border-zinc-600 hover:text-white cursor-pointer"
                      >
                        Volver a 7.4
                      </button>
                    )}
                  </div>
                  <p className="text-sm font-mono text-zinc-600 mt-2 leading-relaxed">
                    {t("op_ph_cambia_a")} <span className="text-zinc-400">{t("op_ph_especie")}</span> {t("op_ph_cambia_b")}
                  </p>
                  {advanced.protonationPh !== DEFAULT_ADVANCED.protonationPh && (
                    <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-sm leading-relaxed text-amber-300">
                      {t("op_ph_fuera_fisiologico")} {t("auto_f0d9b3df714d")}
                    </p>
                  )}
                </div>
              </div>

              {/* Toggles */}
              <div className="mt-4 space-y-3 pt-3 border-t border-zinc-800/60">
                <p className="text-sm font-mono font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-1.5">
                  <Layers size={11} /> {t("op_modulos_pipeline")}
                </p>

                {[
                  {
                    key: "enableSelectivity" as const,
                    label: "Selectividad Anti-Target",
                    desc: t("auto_bf0382f209fa"),
                    icon: ShieldCheck,
                    badge: undefined as string | undefined,
                    note: undefined as string | undefined,
                  },
                  {
                    key: "enableMMGBSA" as const,
                    label: "Refinamiento MM-GBSA",
                    desc: t("auto_dc39d5d9367f"),
                    icon: Atom,
                    badge: undefined as string | undefined,
                    note: undefined as string | undefined,
                  },
                  {
                    key: "enableADMET" as const,
                    label: "Perfil ADMET",
                    desc: t("auto_38997db9a692"),
                    icon: Gauge,
                    // Lo que el usuario necesita saber ANTES de encenderlo, no
                    // después de esperar. Cada frase corresponde a un hecho
                    // comprobado del runtime, no a una advertencia genérica.
                    badge: t("auto_e422c24500d4"),
                    note: t("z_admet_note"),
                  },
                ].map((mod) => (
                  <div
                    key={mod.key}
                    className="flex items-start justify-between gap-3 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/60"
                  >
                    <div className="flex min-w-0 flex-1 items-start gap-2.5">
                      <mod.icon size={14} className="text-purple-400 mt-0.5 shrink-0" />
                      <div className="min-w-0">
                        <span className="text-sm font-mono font-bold text-white uppercase tracking-wider block">
                          {mod.label}
                          {mod.badge && (
                            <span className="ml-2 align-middle rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-bold normal-case tracking-normal text-amber-300">
                              {mod.badge}
                            </span>
                          )}
                        </span>
                        <p className="text-sm text-zinc-500 mt-0.5 leading-relaxed">{mod.desc}</p>
                        {mod.note && (
                          <p className="mt-1.5 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-2.5 py-2 text-[11px] leading-relaxed text-amber-100/80">
                            {mod.note}
                          </p>
                        )}
                      </div>
                    </div>
                    <ToggleSwitch
                      label={mod.label}
                      enabled={advanced[mod.key] as boolean}
                      onChange={() => setAdvanced({ ...advanced, [mod.key]: !advanced[mod.key] })}
                    />
                  </div>
                ))}
              </div>

              {/* MMGBSA Steps (solo visible si enableMMGBSA) */}
              {advanced.enableMMGBSA && (
                <div className="mt-3 pt-3 border-t border-zinc-800/60">
                  <NumberInput
                    label="Pasos MM-GBSA"
                    value={advanced.mmgbsaSteps}
                    onChange={(v) => setAdvanced({ ...advanced, mmgbsaSteps: v })}
                    min={100} max={5000} step={100}
                  />
                  <p className="text-sm font-mono text-zinc-600 mt-1">
                    {t("op_pasos_no_garantizan")}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="flex-none px-6 py-4 border-t border-zinc-800/80 bg-black/60 backdrop-blur-md flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl font-mono text-sm font-bold uppercase tracking-wider bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            {t("c_cancelar")}
          </button>
          <button
            onClick={handleApply}
            className="px-6 py-2.5 rounded-xl font-mono text-sm font-bold uppercase tracking-wider bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-950/50 border border-purple-400/30 transition-all flex items-center gap-2 cursor-pointer"
          >
            <CheckCircle size={14} />
            {t("op_aplicar")}
          </button>
        </div>
      </div>
    </div>
  );
}

// Helper component necesario
function CheckCircle({ size, className }: { size: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
