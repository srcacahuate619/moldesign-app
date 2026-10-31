"use client";
import { useScrollLock } from "@/hooks/useScrollLock";
import { useLanguage } from "../../../context/LanguageContext";

import React, { useId, useState, useRef, useEffect } from "react";
import {
  X, Dna, Cpu, Brain,
  Box, Crosshair, Sliders, Gauge,
  Layers, ShieldCheck, Atom, Target,
  ChevronDown, ChevronUp,
} from "lucide-react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Edges, Sphere } from "@react-three/drei";

import { AntiDianasSelector } from "./AntiDianasSelector";
import { BotonAyuda, DialogoDeAyuda, type TemaDeAyuda } from "./AyudaDelParametro";
import { antiDianasParaEnviar, antiDianasPorDefecto, useAntiDianas } from "@/lib/antiDianas";

// ── Tipos ─────────────────────────────────────────────────────
import { encenderMotor, inventarioDeMotores, type InventarioDeMotores } from "../../../lib/api";
import { puedeElegirse } from "../../../lib/motores";
import { clavePluralDePoses } from "../../../lib/formatoNumerico";
import { CAJA_CENTRO_MAX_A, CAJA_LADO_MAX_A, CAJA_LADO_MIN_A } from "../../../lib/limitesCaja";

export interface DockingEngineConfig {
  /** Vina es el único motor de docking que esta versión ejecuta. */
  engine: "vina";
  /** ESMFold pliega el péptido antes del acoplamiento. `null` acopla con Vina directamente. */
  peptideEngine: "esmfold" | null;
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
  tautomerMode?: "canonico" | "entrada";
  numWorkers: number;
  parallelDocks: number;
  enableSelectivity: boolean;
  selectedAntiTargets: string[];
  antiTargetsPending?: boolean;
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
    hotspots?: string[],
    conformers?: number,
  ) => void;
  initialEngine?: DockingEngineConfig;
  initialGridBox?: GridBoxConfig;
  initialAdvanced?: AdvancedConfig;
  initialHotspots?: readonly string[];
  /** K vigente del caso; el borrador sólo se guarda al aplicar. */
  initialConformers?: number;
  targetHotspots?: Array<{ name: string; importance: number }>;
  gpuAvailable?: boolean;
  gpuCuda?: boolean;
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

// Nombre propio: no se traduce. Titula la ayuda de la ruta peptídica.
const NOMBRE_ESMFOLD = "ESMFold";

function normalizarConformeros(value: number): number {
  return Number.isFinite(value) ? Math.min(64, Math.max(1, Math.trunc(value))) : 1;
}

// ── Valores por defecto ─────────────────────────────────────────
const DEFAULT_ENGINE: DockingEngineConfig = {
  engine: "vina",
  peptideEngine: null,
  gnnPrecision: "fp32",
};

/**
 * Una configuración guardada puede traer motores que esta versión ya no ejecuta
 * (QuickVina, DiffDock, ColabFold, RFdiffusion…). Se reducen a Vina sin plegado
 * previo, en vez de dejar un radio sin marcar que nadie puede volver a elegir.
 */
function normalizarMotor(c: Partial<DockingEngineConfig> | null | undefined): DockingEngineConfig {
  return {
    engine: "vina",
    peptideEngine: c?.peptideEngine === "esmfold" ? "esmfold" : null,
    gnnPrecision: c?.gnnPrecision === "fp16" ? "fp16" : "fp32",
  };
}

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
  selectedAntiTargets: [],
  antiTargetsPending: true,
  // 7.4 es el de siempre: una corrida que no lo toque produce exactamente el
  // mismo SMILES protonado, el mismo hash y la misma entrada de caché que
  // antes de que este campo existiera. Verificado sobre cuatro moléculas.
  protonationPh: 7.4,
  // Decisión del propietario, 2026-10-10: por defecto se acopla el tautómero escrito.
  tautomerMode: "entrada",
  enableMMGBSA: false,
  mmgbsaSteps: 1000,
  // OPT-IN, no opt-out. ADMET-AI es un modelo aparte que se carga en local y
  // cuya primera ejecución domina el reloj de la corrida; el backend ya lo
  // trata como apagado por defecto (`run_admet_ai=False` cuando la clave no
  // viene). Este valor es el mismo defecto, dicho en la UI.
  enableADMET: false,
};

// ── Sub-componentes ─────────────────────────────────────────────

function SectionHeader({ icon: Icon, label, subtitle, ayuda }: { icon: any; label: string; subtitle?: string; ayuda?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-4 pb-3 border-b border-zinc-800/60">
      <div className="h-8 w-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
        <Icon size={16} />
      </div>
      <div className="min-w-0">
        <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">{label}</h3>
        {subtitle && <p className="text-xs font-mono text-zinc-500 mt-0.5 truncate">{subtitle}</p>}
      </div>
      {ayuda && <div className="ml-auto shrink-0">{ayuda}</div>}
    </div>
  );
}

function RadioCard({
  selected,
  onClick,
  label,
  badge,
  badgeStyle,
  badgeMayusculas = true,
  desc,
  meta,
  disabled,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
  badge?: string;
  badgeStyle?: { bg: string; text: string };
  /** Por defecto la insignia va en mayúsculas; la de ESMFold y la de ADMET se leen en tipo normal. */
  badgeMayusculas?: boolean;
  desc?: string;
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
          : "border-zinc-800/60 bg-[var(--bg-secondary)] hover:border-zinc-700 cursor-pointer"
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
              className={`text-xs px-1.5 py-0.5 rounded font-mono font-bold ${badgeMayusculas ? "uppercase" : "normal-case"}`}
              style={{ backgroundColor: badgeStyle.bg, color: "var(--text)" }}
            >
              {badge}
            </span>
          )}
        </div>
        {desc && (
          <p className={`text-xs mt-1 leading-relaxed ${disabled ? "text-zinc-700" : "text-zinc-500"}`}>{desc}</p>
        )}
        {meta && !disabled && (
          <div className="flex items-center gap-1.5 mt-1.5">
            <meta.icon size={11} className="text-zinc-500" />
            <span className="text-xs font-mono text-zinc-500">{meta.text}</span>
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
  grupo,
  disabled = false,
  integerOnly = false,
  alignWithPeers = false,
  ayuda,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
  /** Lo que la etiqueta visible («X») no dice sola: «Centro del grid box (Å)». */
  grupo?: string;
  disabled?: boolean;
  integerOnly?: boolean;
  /** Comparte las filas de etiqueta, control y aviso con los campos vecinos. */
  alignWithPeers?: boolean;
  /** Botón «?» junto a la etiqueta. */
  ayuda?: React.ReactNode;
}) {
  const { t } = useLanguage();
  const id = useId();
  // SOL-14: el nombre accesible nombra eje y dimensión, no sólo «X».
  const nombre = grupo ? `${grupo} · ${label}` : label;
  // SOL-13. Lo tecleado vive en un borrador: sólo llega a `onChange` si es un
  // número dentro de [min, max]. Antes cada pulsación se recortaba al rango
  // («150» se volvía «100») sin decirlo, y el valor pedido se perdía. Ahora el
  // valor vigente NO cambia con una entrada inválida y el rechazo se declara,
  // con el número que se tecleó, el rango y el valor que se conserva.
  const [borrador, setBorrador] = useState<string | null>(null);
  const [rechazo, setRechazo] = useState<string | null>(null);

  // Los pasos suman en coma flotante: sin redondear, 0.1 + 0.2 acaba escrito.
  const paso = (delta: number) => {
    setBorrador(null);
    setRechazo(null);
    onChange(Math.min(max, Math.max(min, Number((value + delta).toFixed(6)))));
  };

  const alEscribir = (crudo: string) => {
    setBorrador(crudo);
    // Vacío o «-» son una edición a medias, no un rechazo.
    if (crudo.trim() === "" || crudo === "-") {
      setRechazo(null);
      return;
    }
    const v = Number(crudo);
    if (!Number.isFinite(v)) {
      setRechazo(t("op_numero_no_valido", { valor: crudo, vigente: value }));
      return;
    }
    if (v < min || v > max) {
      setRechazo(t("op_numero_fuera_de_rango", { valor: crudo, min, max, vigente: value }));
      return;
    }
    if (integerOnly && !Number.isInteger(v)) {
      setRechazo(t("op_numero_no_entero", { valor: crudo, vigente: value }));
      return;
    }
    setRechazo(null);
    onChange(v);
  };

  const botonPaso =
    "w-7 h-7 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-600 flex items-center justify-center text-sm font-mono transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:text-zinc-400 disabled:hover:border-zinc-700";

  return (
    <div className={alignWithPeers ? "row-span-3 grid grid-rows-subgrid gap-1" : "flex flex-col gap-1"}>
      <div className="flex items-center gap-1.5">
        <label htmlFor={id} className={`text-xs font-mono uppercase tracking-wider ${disabled ? "text-zinc-600" : "text-zinc-500"}`}>{label}</label>
        {ayuda}
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => paso(-step)}
          disabled={disabled || value <= min}
          aria-label={t("op_numero_disminuir", { campo: nombre })}
          className={botonPaso}
        >
          <span aria-hidden="true">−</span>
        </button>
        <input
          id={id}
          type="number"
          value={borrador ?? String(value)}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          aria-label={nombre}
          aria-invalid={rechazo ? true : undefined}
          aria-describedby={rechazo ? `${id}-rechazo` : undefined}
          onChange={(e) => alEscribir(e.target.value)}
          onBlur={() => setBorrador(null)}
          className="w-20 text-center bg-[var(--bg)] border border-zinc-700 rounded-lg py-1.5 font-mono text-sm text-white outline-none focus:border-purple-500/40 transition-colors disabled:cursor-not-allowed disabled:text-zinc-500 aria-[invalid=true]:border-amber-500/60 [appearance:textfield] [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
        />
        <button
          type="button"
          onClick={() => paso(step)}
          disabled={disabled || value >= max}
          aria-label={t("op_numero_aumentar", { campo: nombre })}
          className={botonPaso}
        >
          <span aria-hidden="true">+</span>
        </button>
      </div>
      {rechazo && (
        <p id={`${id}-rechazo`} role="alert" className="max-w-[12rem] text-xs leading-snug text-amber-800 dark:text-amber-300">
          {rechazo}
        </p>
      )}
    </div>
  );
}

/**
 * Selector con su etiqueta ASOCIADA (SOL-14). Antes la etiqueta era un <label>
 * suelto junto al <select>: sin `htmlFor`, el control no tenía nombre y un
 * lector de pantalla anunciaba «cuadro combinado» sin decir de qué.
 */
function SelectorEtiquetado({
  etiqueta,
  value,
  onChange,
  children,
}: {
  etiqueta: string;
  value: number;
  onChange: React.ChangeEventHandler<HTMLSelectElement>;
  children: React.ReactNode;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-mono uppercase tracking-wider text-zinc-500">
        {etiqueta}
      </label>
      <select
        id={id}
        value={value}
        onChange={onChange}
        className="bg-[var(--bg)] border border-zinc-700 rounded-lg py-1.5 px-2 font-mono text-sm text-white outline-none focus:border-purple-500/40 transition-colors cursor-pointer"
      >
        {children}
      </select>
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
  const { t } = useLanguage();
  // Ajuste dinámico de cámara basado en el tamaño más grande
  const maxDim = Math.max(config.sizeX, config.sizeY, config.sizeZ);
  const cameraDistance = Math.max(50, maxDim * 2.5);

  return (
    <div className="relative w-full aspect-[4/3] bg-[var(--bg-secondary)] rounded-xl border border-zinc-800/60 overflow-hidden">

      {/* HUD 2D superpuesto al 3D */}
      <div className="absolute top-3 left-3 z-10 pointer-events-none flex flex-col gap-1">
        <span className="text-xs font-mono font-bold text-zinc-400">{t("pr_cfg_centro")}</span>
        <span className="text-xs font-mono text-zinc-500">
          X: {config.centerX.toFixed(1)} / Y: {config.centerY.toFixed(1)} / Z: {config.centerZ.toFixed(1)}
        </span>
      </div>

      <div className="absolute bottom-3 left-3 right-3 flex justify-between z-10 pointer-events-none">
        <span className="text-xs font-mono text-zinc-500">X: {config.sizeX.toFixed(1)} Å</span>
        <span className="text-xs font-mono text-zinc-500">Y: {config.sizeY.toFixed(1)} Å</span>
        <span className="text-xs font-mono text-zinc-500">Z: {config.sizeZ.toFixed(1)} Å</span>
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
  initialConformers = 1,
  targetHotspots = [],
  systemSealed = false,
}: Props) {
  const { t } = useLanguage();
  useScrollLock(isOpen);
  const [engine, setEngine] = useState<DockingEngineConfig>(() => normalizarMotor(initialEngine));
  const [conformers, setConformers] = useState(() => normalizarConformeros(initialConformers));
  const conformersTitleId = useId();

  // Ayuda de un parámetro («?»): un solo diálogo para todo el modal. Mientras está abierto,
  // Escape lo cierra a él y no a este diálogo (`ayudaAbierta` lo dice sin esperar al render).
  const [ayuda, setAyuda] = useState<{ tema: TemaDeAyuda; origen: HTMLElement } | null>(null);
  const ayudaAbierta = useRef(false);
  ayudaAbierta.current = ayuda !== null;
  const abrirAyuda = (tema: TemaDeAyuda, origen: HTMLElement) => setAyuda({ tema, origen });
  const botonAyuda = (tema: TemaDeAyuda) => <BotonAyuda tema={tema} onAbrir={abrirAyuda} />;
  useEffect(() => {
    if (!isOpen) setAyuda(null);
  }, [isOpen]);

  // ENG-001. Este menú ofrecía siete motores sin comprobar ninguno. En una
  // instalación limpia sólo AutoDock Vina existe, así que el menú sólo muestra
  // lo que la build ejecuta (decisión del 2026-10-07: los demás no se listan).
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
    const ausente = { disponible: false, motivo: t("op_comprobando_motores"), accion: null, estado: "UNKNOWN", requiere: "" };
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

  // ESMFold se elige igual que Vina, sin mirar la molécula. Sólo lo que de verdad
  // no puede ejecutarse todavía —falta descargarlo, falta una librería o falló al
  // arrancar— lo deshabilita. Instalado y apagado se enciende solo cuando la
  // corrida lo necesita: `run_peptide_docking_helper` lo arranca al empezar.
  const esm = estadoMotor("esmfold");
  const esmfoldElegible = puedeElegirse(esm);

  // Sólo el reintento tras un arranque fallido pide algo al investigador. Encender
  // es un gesto explícito —un modelo de 8 GB no arranca por abrir una pantalla—, y
  // al terminar se relee el inventario en vez de suponer el resultado.
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
  const anti = useAntiDianas(isOpen);
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
      setConformers(normalizarConformeros(initialConformers));
      if (initialEngine) setEngine(normalizarMotor(initialEngine));
      if (initialGridBox) setGridBox(initialGridBox);
      if (initialAdvanced) setAdvanced(initialAdvanced);
      setSelectedHotspots(
        initialHotspots ? [...initialHotspots] : targetHotspots.map((h) => h.name),
      );
    }
    prevOpen.current = isOpen;
  }, [initialAdvanced, initialConformers, initialEngine, initialGridBox, initialHotspots, isOpen, targetHotspots]);

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
      if (event.key === "Escape" && !ayudaAbierta.current) {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // La ausencia de una lista guardada significa «panel por defecto». Se deriva
  // del catálogo al pintar: abrir el modal antes de que el fetch termine no
  // produce una lista vacía que parezca la elección explícita «Ninguna».
  const antiTargetSelection = advanced.antiTargetsPending && anti.targets
    ? antiDianasPorDefecto(anti.targets)
    : advanced.selectedAntiTargets;

  const handleApply = () => {
    if (advanced.enableSelectivity && (anti.targets === null || anti.error)) return;
    const advancedToApply = {
      ...advanced,
      antiTargetsPending: false,
      selectedAntiTargets: advanced.enableSelectivity
        ? antiDianasParaEnviar(anti.targets, antiTargetSelection)
        : antiTargetSelection,
    };
    onApply(engine, gridBox, advancedToApply, selectedHotspots, conformers);
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

  // Lo que explica un parámetro se lee con su «?»: son las mismas claves de traducción de
  // siempre, no copias. A la vista queda sólo lo que cambia con el estado (un pH fuera de
  // 7.4, un motor sin descargar, un número rechazado).
  const estadoLargoEsmfold = esm.disponible
    ? t("op_esm_encendido")
    : esm.accion === "encender"
    ? t("op_esm_se_enciende")
    : esm.motivo ?? t("op_esm_sin_estado");
  const chipEsmfold = esm.disponible
    ? t("op_esm_chip_listo")
    : esm.accion === "encender"
    ? t("op_esm_chip_instalado")
    : esm.accion === "descargar"
    ? t("op_esm_chip_sin_descargar")
    : esm.accion === "reintentar"
    ? t("op_esm_chip_no_arranco")
    : esm.estado === "UNKNOWN"
    ? t("op_esm_sin_estado")
    : t("op_esm_chip_no_disponible");
  const temas = {
    caja: { titulo: t("op_parametros_bolsillo"), parrafos: [t("op_grid_explicacion")] },
    sellado: { titulo: t("op_sistema_sellado_titulo"), parrafos: [t("op_sistema_sellado")] },
    hotspots: {
      titulo: t("op_hotspots"),
      parrafos: [...(systemSealed ? [t("op_hotspots_fijados")] : []), t("op_hotspots_explicacion")],
    },
    ph: {
      titulo: t("op_ph_protonacion"),
      parrafos: [`${t("op_ph_cambia_a")} ${t("op_ph_especie")} ${t("op_ph_cambia_b")}`],
    },
    tautomero: { titulo: t("op_tautomero"), parrafos: [t("op_tautomero_ayuda")] },
    conformeros: { titulo: t("ayuda_ensemble_titulo"), parrafos: [t("ayuda_ensemble")] },
    peptidos: {
      titulo: NOMBRE_ESMFOLD,
      parrafos: [t("pr_pep_experimental_aviso"), t("op_esm_desc"), estadoLargoEsmfold, t("op_esm_alcance")],
    },
  } satisfies Record<string, TemaDeAyuda>;

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
        className="relative w-full max-w-6xl max-h-[90vh] bg-[var(--bg-card)] border border-purple-500/20 rounded-2xl shadow-[0_0_40px_-15px_rgba(168,85,247,0.18)] backdrop-blur-2xl flex flex-col overflow-hidden"
      >
        {/* ── Header ── */}
        <div className="flex-none px-6 py-4 border-b border-zinc-800/80 bg-[var(--bg-secondary)] backdrop-blur-md flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-300">
              <Sliders size={18} />
            </div>
            <div>
              <h2 id="pro-options-title" className="text-base font-bold font-mono text-white uppercase tracking-wider">
                {t("op_titulo")}
              </h2>
              <p className="text-xs text-zinc-500 font-mono mt-0.5">
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
                <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Atom size={12} /> {t("op_moleculas_pequenas")}
                </p>

                <RadioCard
                  selected={engine.peptideEngine === null}
                  onClick={() => setEngine({ ...engine, peptideEngine: null })}
                  disabled={!estadoMotor("vina").disponible}
                  label="AutoDock Vina 1.2.7"
                  badge={t("pr_mot_clasico")}
                  badgeStyle={{ bg: "rgba(168,85,247,0.15)", text: "#a78bfa" }}
                  desc={estadoMotor("vina").motivo ?? t("auto_2e24a6f6267b")}
                  meta={{ icon: Cpu, text: "~20s" }}
                />
              </div>

              {/* Péptidos. ESMFold se elige sin depender de la molécula: el aviso
                  dice cuándo conviene y la decisión queda en el investigador. */}
              <div className="space-y-2 pt-3 border-t border-zinc-800/60">
                <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Brain size={12} /> {t("auto_7987f4801c2c")} {botonAyuda(temas.peptidos)}
                </p>

                <RadioCard
                  selected={engine.peptideEngine === "esmfold"}
                  onClick={() => setEngine({ ...engine, peptideEngine: "esmfold" })}
                  disabled={!esmfoldElegible}
                  label="ESMFold"
                  badge={t("pr_cfg_experimental")}
                  badgeMayusculas={false}
                  badgeStyle={{ bg: "rgba(251,191,36,0.15)", text: "#fbbf24" }}
                />

                {/* Estado de ESMFold: informa siempre; la acción sólo aparece cuando algo impide usarlo. */}
                <div className="flex flex-wrap items-center gap-2 pl-7 text-xs font-mono text-zinc-500">
                  <span>{chipEsmfold}</span>
                  {esm.accion === "descargar" && (
                    <a
                      href="/launcher"
                      className="rounded border border-cyan-500/40 px-2.5 py-1 font-mono text-xs font-bold uppercase tracking-wider text-cyan-300 transition-colors hover:bg-cyan-950/30"
                    >
                      {t("pr_cfg_abrir_gestor")}
                    </a>
                  )}
                  {esm.accion === "reintentar" && (
                    <button
                      type="button"
                      onClick={() => encender("esmfold")}
                      disabled={encendiendo === "esmfold"}
                      className="rounded border border-purple-500/40 px-2.5 py-1 font-mono text-xs font-bold uppercase tracking-wider text-purple-300 transition-colors hover:bg-purple-950/40 disabled:opacity-50"
                    >
                      {encendiendo === "esmfold" ? t("auto_43584ce3b53d") : t("op_esm_reintentar")}
                    </button>
                  )}
                </div>
              </div>

              {/* Motor externo (Vía API). Sin conexión en esta versión: la plaza deja visible
                  dónde irá un motor de terceros, en su propio grupo y no dentro de péptidos,
                  porque un motor externo declara qué moléculas acepta. No es elegible hasta
                  que exista una conexión verificada. Ver docs/96_DISENO_MOTOR_EXTERNO_VIA_API.md. */}
              <div className="space-y-2 pt-3 border-t border-zinc-800/60">
                <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Layers size={12} /> {t("op_api_grupo")}
                </p>
                <div
                  data-testid="plaza-motor-api"
                  aria-disabled="true"
                  className="flex items-start gap-3 p-3.5 rounded-xl border border-dashed border-zinc-800/60 opacity-60"
                >
                  <span aria-hidden="true" className="mt-0.5 w-3.5 h-3.5 shrink-0 rounded-full border border-zinc-700" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold font-mono uppercase tracking-wider text-zinc-500">{t("op_api_titulo")}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded font-mono font-bold uppercase bg-zinc-800 text-zinc-400">{t("op_api_badge")}</span>
                    </div>
                    <p className="text-xs mt-1 leading-relaxed text-zinc-500">{t("op_api_desc")}</p>
                  </div>
                </div>
              </div>

              {/* Muestreo del ligando: se aplica junto con el resto del protocolo.
                  gnnPrecision se conserva para leer configuraciones anteriores. */}
              <section aria-labelledby={conformersTitleId} className="space-y-2 pt-3 border-t border-zinc-800/60">
                  <h4 id={conformersTitleId} className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                    <Atom size={12} aria-hidden="true" /> {t("ayuda_ensemble_titulo")} {botonAyuda(temas.conformeros)}
                  </h4>
                  <p className="text-xs font-mono text-zinc-500">{t("op_conformeros_descripcion")}</p>
                  <div role="group" aria-labelledby={conformersTitleId} className="grid grid-cols-2 gap-2">
                    {([false, true] as const).map((multiple) => (
                      <button
                        key={String(multiple)}
                        type="button"
                        aria-pressed={(conformers > 1) === multiple}
                        onClick={() => setConformers(multiple ? (conformers > 1 ? conformers : 30) : 1)}
                        className={`p-2.5 rounded-lg border text-sm font-mono font-bold uppercase transition-colors focus-visible:outline-2 focus-visible:outline-purple-400 active:bg-purple-500/20 ${
                          (conformers > 1) === multiple
                            ? "border-purple-500/40 bg-purple-500/10 text-purple-300"
                            : "border-zinc-800/60 text-zinc-400 hover:border-zinc-700 hover:text-white"
                        } cursor-pointer`}
                      >
                        {t(multiple ? "op_conformeros_varios" : "pr_conformero_unico")}
                      </button>
                    ))}
                  </div>
                  {conformers > 1 && (
                    <>
                      <NumberInput
                        value={conformers}
                        onChange={setConformers}
                        min={2}
                        max={64}
                        step={1}
                        integerOnly
                        label={t("op_conformeros_numero")}
                      />
                      <p className="text-xs font-mono leading-relaxed text-amber-800 dark:text-amber-300">{t("op_conformeros_aviso")}</p>
                    </>
                  )}
              </section>
            </div>

            {/* ═══ COLUMNA 2: {t("op_parametros_bolsillo")} ═══ */}
            <div>
              <SectionHeader icon={Box} label={t("op_parametros_bolsillo")} subtitle={t("op_sub_donde")} ayuda={botonAyuda(temas.caja)} />

              {/* La caja de búsqueda la usan Vina y ESMFold (el acoplamiento va después
                  del plegado): no depende de la molécula ni del motor elegido. */}
              {(() => {
                return (
                  <div className="animate-in fade-in duration-300">
                    {/* Grid Box Preview */}
                    <GridBoxPreview config={gridBox} />

                    {systemSealed && (
                      <div className="mt-4 flex items-center justify-between gap-2 rounded-xl border border-purple-500/20 bg-purple-500/[0.04] px-3 py-2">
                        <p className="text-xs font-mono font-bold uppercase tracking-wider text-purple-200">
                          {t("op_sistema_sellado_titulo")}
                        </p>
                        {botonAyuda(temas.sellado)}
                      </div>
                    )}

                    {/* Coordenadas del Centro */}
                    <div className="mt-4 space-y-3">
                      <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400">
                        {t("op_centro_grid")}
                      </p>
                      <div className="grid grid-cols-3 gap-2">
                        <NumberInput label="X" grupo={t("op_centro_grid")} value={gridBox.centerX} onChange={(v) => setGridBox({ ...gridBox, centerX: v })} min={-CAJA_CENTRO_MAX_A} max={CAJA_CENTRO_MAX_A} step={0.5} disabled={systemSealed} />
                        <NumberInput label="Y" grupo={t("op_centro_grid")} value={gridBox.centerY} onChange={(v) => setGridBox({ ...gridBox, centerY: v })} min={-CAJA_CENTRO_MAX_A} max={CAJA_CENTRO_MAX_A} step={0.5} disabled={systemSealed} />
                        <NumberInput label="Z" grupo={t("op_centro_grid")} value={gridBox.centerZ} onChange={(v) => setGridBox({ ...gridBox, centerZ: v })} min={-CAJA_CENTRO_MAX_A} max={CAJA_CENTRO_MAX_A} step={0.5} disabled={systemSealed} />
                      </div>
                    </div>

                    {/* Tamaño del Grid Box */}
                    <div className="mt-4 space-y-3">
                      <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400">
                        {t("op_dimensiones_grid")}
                      </p>
                      <div className="grid grid-cols-3 gap-2">
                        <NumberInput label={t("op_tamano_x")} grupo={t("op_dimensiones_grid")} value={gridBox.sizeX} onChange={(v) => setGridBox({ ...gridBox, sizeX: v })} min={CAJA_LADO_MIN_A} max={CAJA_LADO_MAX_A} step={0.5} disabled={systemSealed} />
                        <NumberInput label={t("op_tamano_y")} grupo={t("op_dimensiones_grid")} value={gridBox.sizeY} onChange={(v) => setGridBox({ ...gridBox, sizeY: v })} min={CAJA_LADO_MIN_A} max={CAJA_LADO_MAX_A} step={0.5} disabled={systemSealed} />
                        <NumberInput label={t("op_tamano_z")} grupo={t("op_dimensiones_grid")} value={gridBox.sizeZ} onChange={(v) => setGridBox({ ...gridBox, sizeZ: v })} min={CAJA_LADO_MIN_A} max={CAJA_LADO_MAX_A} step={0.5} disabled={systemSealed} />
                      </div>
                    </div>

                    {/* Exhaustiveness & Num Modes */}
                    <div className="mt-4 space-y-3">
                      <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400">
                        {t("op_parametros_busqueda")}
                      </p>
                      <div className="grid grid-cols-2 gap-3">
                        <SelectorEtiquetado
                          etiqueta={t("c_exhaustividad")}
                          value={gridBox.exhaustiveness}
                          onChange={(e) => setGridBox({ ...gridBox, exhaustiveness: parseInt(e.target.value) })}
                        >
                          {[1, 2, 4, 8, 16, 24, 32].map((n) => (
                            <option key={n} value={n}>{n} {n <= 8 ? t("auto_78940da1bb6a") : n >= 24 ? t("auto_9af5776f1fea") : ""}</option>
                          ))}
                        </SelectorEtiquetado>
                        <SelectorEtiquetado
                          etiqueta={t("pr_cfg_num_modes")}
                          value={gridBox.numModes}
                          onChange={(e) => setGridBox({ ...gridBox, numModes: parseInt(e.target.value) })}
                        >
                          {[1, 3, 5, 9, 15, 20].map((n) => (
                            <option key={n} value={n}>{n} {t(clavePluralDePoses(n))}</option>
                          ))}
                        </SelectorEtiquetado>
                      </div>
                    </div>

                                      </div>
                );
              })()}

              {/* ── Hotspots del receptor ── */}
              {targetHotspots.length > 0 && (
                <div className="mt-6 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                      <Target size={11} /> {t("op_hotspots")} {botonAyuda(temas.hotspots)}
                    </p>
                    <button
                      type="button"
                      onClick={toggleAllHotspots}
                      disabled={systemSealed}
                      className="text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white border border-zinc-700 transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-zinc-800 disabled:hover:text-zinc-300"
                    >
                      {selectedHotspots.length === targetHotspots.length
                        ? t("op_desmarcar_todos")
                        : t("op_marcar_todos")}
                    </button>
                  </div>
                  <p className="text-xs font-mono text-zinc-500 leading-relaxed">
                    ({selectedHotspots.length}/{targetHotspots.length} {t("pr_cfg_activos")})
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
                          title={t("pr_hotspot_importance", { name: h.name, importance: h.importance?.toFixed?.(2) ?? h.importance ?? "—" })}
                          className={`px-2 py-1 rounded-lg text-xs font-mono font-bold transition-all border disabled:cursor-not-allowed ${
                            systemSealed ? "cursor-not-allowed" : "cursor-pointer"
                          } ${
                            active
                              ? "bg-purple-500/15 border-purple-500/40 text-purple-300"
                              : "bg-[var(--bg-secondary)] border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
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
                <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Cpu size={11} /> {t("op_recursos")}
                </p>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                  <NumberInput
                    alignWithPeers
                    label={t("pr_cfg_procesos")}
                    value={advanced.numWorkers}
                    onChange={(v) => setAdvanced({ ...advanced, numWorkers: v })}
                    min={1} max={16} step={1}
                  />
                  <NumberInput
                    alignWithPeers
                    label={t("pr_cfg_docks_paralelos")}
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
                <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Atom size={11} /> {t("op_preparacion_ligando")}
                </p>

                <div className="mt-3 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/60">
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <NumberInput
                      label={t("op_ph_protonacion")}
                      ayuda={botonAyuda(temas.ph)}
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
                        className="rounded-lg border border-zinc-700 px-2.5 py-1 font-mono text-xs uppercase tracking-wider text-zinc-400 transition-colors hover:border-zinc-600 hover:text-white cursor-pointer"
                      >
                        {t("pr_cfg_volver_ph")}
                      </button>
                    )}
                  </div>
                                    {advanced.protonationPh !== DEFAULT_ADVANCED.protonationPh && (
                    <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-xs leading-relaxed text-amber-800 dark:text-amber-300">
                      {t("op_ph_fuera_fisiologico")} {t("auto_f0d9b3df714d")}
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-zinc-700 p-3">
                <div className="flex items-center gap-2">
                  <label htmlFor="tautomer-mode" className="block text-xs font-mono uppercase tracking-wider text-zinc-500">{t("op_tautomero")}</label>
                  {botonAyuda(temas.tautomero)}
                </div>
                <select id="tautomer-mode"
                  className="mt-2 min-h-11 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 text-sm text-zinc-100 focus-visible:outline-2 focus-visible:outline-cyan-400"
                  value={advanced.tautomerMode ?? "entrada"}
                  onChange={(event) => setAdvanced({ ...advanced, tautomerMode: event.target.value as "canonico" | "entrada" })}>
                  <option value="entrada">{t("op_tautomero_entrada")}</option>
                  <option value="canonico">{t("op_tautomero_defecto")}</option>
                </select>
              </div>

              {/* Toggles */}
              <div className="mt-4 space-y-3 pt-3 border-t border-zinc-800/60">
                <p className="text-sm font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Layers size={11} /> {t("op_modulos_pipeline")}
                </p>

                {[
                  {
                    key: "enableSelectivity" as const,
                    label: t("pr_cfg_selectividad_antitarget"),
                    ayuda: [t("auto_bf0382f209fa")],
                    icon: ShieldCheck,
                    badge: undefined as string | undefined,
                  },
                  {
                    key: "enableADMET" as const,
                    label: t("pr_cfg_perfil_admet"),
                    ayuda: [t("auto_38997db9a692"), t("z_admet_note")],
                    icon: Gauge,
                    // Lo que el usuario necesita saber ANTES de encenderlo, no
                    // después de esperar. Cada frase corresponde a un hecho
                    // comprobado del runtime, no a una advertencia genérica.
                    badge: t("auto_e422c24500d4"),
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
                            <span className="ml-2 align-middle rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-xs font-bold normal-case tracking-normal text-amber-800 dark:text-amber-300">
                              {mod.badge}
                            </span>
                          )}
                          <span className="ml-2 inline-block align-middle">
                            {botonAyuda({ titulo: mod.label, parrafos: mod.ayuda })}
                          </span>
                        </span>
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

              {advanced.enableSelectivity && <div className="mt-3"><AntiDianasSelector targets={anti.targets} selected={antiTargetSelection} error={anti.error} onRetry={anti.retry} onChange={(ids) => setAdvanced({ ...advanced, antiTargetsPending: false, selectedAntiTargets: ids })} /></div>}

              {/* MMGBSA Steps (solo visible si enableMMGBSA) */}
              {advanced.enableMMGBSA && (
                <div className="mt-3 pt-3 border-t border-zinc-800/60">
                  <NumberInput
                    label={t("pr_cfg_pasos_mmgbsa")}
                    value={advanced.mmgbsaSteps}
                    onChange={(v) => setAdvanced({ ...advanced, mmgbsaSteps: v })}
                    min={100} max={5000} step={100}
                  />
                  <p className="text-xs font-mono text-zinc-600 mt-1">
                    {t("op_pasos_no_garantizan")}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="flex-none px-6 py-4 border-t border-zinc-800/80 bg-[var(--bg-secondary)] backdrop-blur-md flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl font-mono text-sm font-bold uppercase tracking-wider bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            {t("c_cancelar")}
          </button>
          <button
            onClick={handleApply}
            disabled={advanced.enableSelectivity && (anti.targets === null || anti.error)}
            className="px-6 py-2.5 rounded-xl font-mono text-sm font-bold uppercase tracking-wider bg-purple-600 hover:bg-purple-500 text-[#fff] shadow-lg shadow-purple-950/50 border border-purple-400/30 transition-all flex items-center gap-2 cursor-pointer"
          >
            <CheckCircle size={14} />
            {t("op_aplicar")}
          </button>
        </div>
      </div>

      {ayuda && (
        <DialogoDeAyuda tema={ayuda.tema} origen={ayuda.origen} onCerrar={() => setAyuda(null)} />
      )}
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
