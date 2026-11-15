"use client";

import { aaInfoFromName, formatResidueLabel } from "../../../lib/aminoAcidPresentation";

import { appLocale } from "../../../lib/formatoNumerico";
import { useLanguage } from "@/context/LanguageContext";
/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V5 */

// Visor Web3D ligero (react-three-fiber) — alternativa a MolStar.
//
// Su trabajo es uno: ver DÓNDE busca Vina. Por eso lo que manda es la caja de búsqueda con su retícula, el sitio activo
// (esfera de alambre y superficie del bolsillo), la pose y lo que el receptor trae además de aminoácidos —metales,
// cofactores, aguas—, que Vina ve y Mol* sí enseña. El resto del receptor es contexto: gris, con luz y niebla para que se
// lea la profundidad sin competir con el sitio.
//
// - Átomos con InstancedMesh (una llamada de dibujo por nube)
// - Hasta MAX_ATOMS átomos del receptor: si hay más, los más cercanos a la caja, y se dice
// - Dibuja sólo cuando algo cambia (`frameloop="demand"`)

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, EyeOff, Atom, Zap, Settings, Maximize2, Minimize2 } from "lucide-react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { LineSegments2, LineSegmentsGeometry, LineMaterial, MarchingCubes } from "three-stdlib";
import type { InteractionDatum } from "../../../lib/types";
import { comprobarWebGL } from "../../../lib/webgl";
import {
  VIEWER_LABEL_BUTTON_CLASS,
  VIEWER_LABEL_PANEL_CLASS,
  VIEWER_SWITCH_BUTTON_CLASS,
} from "./viewerOverlayStyles";

type Atom = {
  x: number; y: number; z: number;
  element: string;
  isHotspot?: boolean;
  resId?: string; // residuo al que pertenece (ej. "ASP116"), para envolventes
  chain?: string; // cadena del PDB (físico: el mismo residuo en otra cadena NO es el hotspot)
};

type Props = {
  proteinData?: string;         // PDB - Receptor
  poseData?: string;            // SDF - Molécula (ligando acoplado)
  // Interacciones no-covalentes (PLIF del backend) para las líneas discontinuas
  interactions?: InteractionDatum[];
  // Hotspots del receptor: nombre + importancia (0-1). x/y/z son las
  // coordenadas REALES del CA (del catálogo calibrado, misma cadena del
  // receptor). El nombre puede venir con cadena ("A:LEU221") o sin ("LEU221").
  hotspots?: Array<{ name: string; importance?: number; x?: number; y?: number; z?: number }>;
  // Cadena del receptor (target.chain) — filtro físico: solo se parsean los
  // átomos de la cadena usada en el docking (evita cadenas homónimas en
  // complejos multicadena como GPCR + proteína G).
  chain?: string;
  gridInfo?: { centerX: number; centerY: number; centerZ: number;
               sizeX: number; sizeY: number; sizeZ: number } | null;
  onSwitchViewer?: () => void;
  viewerLabel?: string;
  // Sincronización de cámara con MolStar (vista completa position+target):
  onCameraChange?: (cam: ViewerCamera) => void;
  externalCamera?: ViewerCamera | null;
  // Solo reportar la cámara cuando el visor está visible (evita que el visor
  // oculto pise la vista del activo).
  active?: boolean;
  /** El equipo le quitó el contexto 3D y no lo devolvió: quien lo monta decide qué abrir. */
  onNoDisponible?: () => void;
  /**
   * De dónde sale `proteinData`. Con un resultado es el receptor que acopló Vina (lo que lleva, Vina lo vio); antes de
   * evaluar es el depósito del catálogo, y la preparación decide después qué metales, cofactores y aguas conserva.
   */
  origenDelReceptor?: "corrida" | "deposito";
};

const SIN_HOTSPOTS: NonNullable<Props["hotspots"]> = [];

/** Cuánto se espera a que el navegador devuelva un contexto perdido antes de darlo por perdido. */
const ESPERA_DE_CONTEXTO_MS = 4000;

// ── Radios físicos: radios covalentes (Å, CRC Handbook) escalados a la
//    escala visual del visor. Todos los átomos de un mismo elemento comparten
//    el MISMO radio (un carbono es un carbono) — los hotspots y la molécula
//    se distinguen por COLOR, no por tamaño. ──
const COVALENT_RADIUS_A: Record<string, number> = {
  H: 0.31, C: 0.77, N: 0.70, O: 0.66, F: 0.64,
  P: 1.11, S: 1.05, CL: 0.99, BR: 1.14, I: 1.33,
};
// Escala visual: 1 Å covalente → 0.55 unidades (C queda como antes)
const VISUAL_SCALE = 0.55 / 0.77;
const atomRadius = (element: string): number => (COVALENT_RADIUS_A[element] ?? 0.77) * VISUAL_SCALE;

// Colores CPK saturados — sitio activo (residuos hotspot)
const HOTSPOT_ELEMENT_COLOR: Record<string, string> = {
  C: "#7dd3fc", N: "#4f7dff", O: "#ff4d4d", S: "#e8c84f", P: "#ff9d5c", H: "#ffffff",
};
// Molécula (ligando acoplado)
const LIGAND_ELEMENT_COLOR: Record<string, string> = {
  C: "#e6e6f2", N: "#5b8cff", O: "#ff5a5a", S: "#e8c84f", P: "#ff9d5c",
  F: "#2fd99a", CL: "#2fd99a", BR: "#b5673a", I: "#9b5de5", H: "#ffffff",
};
const REST_ATOM_COLOR = "#5b6475"; // gris del resto del receptor: con luz se lee el volumen sin quitarle el sitio
/** Fracción del radio covalente con que se dibuja el receptor fuera del sitio. */
const RADIO_DEL_CONTEXTO = 0.5;
const LIGAND_BOND_COLOR = "#8fa3c0"; // enlaces de la molécula
// Paleta por residuo hotspot: cada residuo tiene SU color (convención
// "spectrum" de PyMOL) para distinguirlos sin etiquetas.
const RESIDUE_PALETTE = ["#22d3ee", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#60a5fa", "#fb923c", "#4ade80", "#f87171", "#2dd4bf", "#c084fc", "#facc15"];
// Colores por tipo de interacción no-covalente (convención PLIP/PyMOL):
const INTERACTION_COLORS: Record<string, string> = {
  hbond: "#facc15",        // amarillo — H-bond
  hydrophobic: "#cbd5e1",  // gris claro — contacto hidrofóbico
  pistacking: "#e879f9",   // magenta — π-stacking
  saltbridge: "#f87171",   // rojo — puente salino
  cationpi: "#fb923c",     // naranja — catión-π
  halogen: "#34d399",      // verde — enlace de halógeno
};
const INTERACTION_LABELS: Record<string, string> = {
  hbond: "H-bond", hydrophobic: "pr_aa_type_hydrophobic", pistacking: "π-stacking",
  saltbridge: "pr_interaction_salt", cationpi: "pr_interaction_cation_pi", halogen: "pr_interaction_halogen",
};
// La superficie del bolsillo se colorea por TIPO de residuo (convención
// AA_INFO: polar=azul, hidrofóbico=ámbar, aromático=púrpura, ácido=rojo,
// básico=verde, estructural=gris) — el color de la etiqueta que ya existe.
const MAX_ATOMS = 50000;

// ── Lo que el receptor trae además de aminoácidos ──────────────────────
//
// Se clasifica por el NOMBRE del residuo, no por el registro: Meeko escribe los iones como ATOM y los depósitos
// escriben la selenometionina como HETATM. Un residuo fuera de esta lista es un heteroátomo (metal, agua o grupo).
const RESIDUOS_DE_PROTEINA = new Set([
  "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER",
  "THR", "TRP", "TYR", "VAL",
  // protonaciones y variantes que escriben AMBER, CHARMM, PDB2PQR y Meeko
  "HID", "HIE", "HIP", "HSD", "HSE", "HSP", "CYX", "CYM", "ASH", "GLH", "LYN", "ARN", "TYM",
  // residuos modificados que forman parte de la cadena
  "MSE", "SEP", "TPO", "PTR", "CSO", "CSD", "CSX", "CME", "KCX", "LLP", "MLY", "HYP", "PCA",
  // extremos
  "ACE", "NME", "NH2",
  // ácidos nucleicos
  "DA", "DC", "DG", "DT", "DU", "A", "C", "G", "U",
]);
const AGUAS = new Set(["HOH", "WAT", "DOD", "H2O", "TIP", "TIP3", "SOL"]);
const METALES = new Set(["ZN", "MG", "CA", "FE", "MN", "CU", "CO", "NI", "NA", "K", "CD", "HG", "LI", "SR", "BA", "PT", "AU", "AG", "W", "MO", "V", "CR", "AL", "GA"]);
/** Colores de Jmol para los metales: el convenio que reconoce quien mira estructuras. */
const COLOR_DE_METAL: Record<string, string> = {
  ZN: "#7d80b0", MG: "#8aff00", CA: "#3dff00", FE: "#e06633", MN: "#9c7ac7", CU: "#c88033", CO: "#f090a0", NI: "#50d050",
  NA: "#ab5cf2", K: "#8f40d4", CD: "#ffd98f", HG: "#b8b8d0",
};
/** Los cofactores y grupos se tiñen en ámbar: no son el ligando (blanco) ni el receptor (gris). */
const HETERO_ELEMENT_COLOR: Record<string, string> = {
  C: "#f2b544", N: "#5b8cff", O: "#ff5a5a", S: "#e8c84f", P: "#ff9d5c", FE: "#e06633",
};
const AGUA_COLOR = "#ff8a8a";

export type GrupoHetero = { clave: string; residuo: string; cadena: string; numero: string; tipo: "metal" | "agua" | "grupo"; atomos: number };
export type AtomoHetero = { x: number; y: number; z: number; element: string; tipo: GrupoHetero["tipo"]; grupo: string };

/** Elemento de una línea ATOM/HETATM: la columna 77-78 y, si falta, el nombre del átomo. Sin la carga de la columna 79. */
function elementoDeLaLinea(line: string): string {
  const declarado = line.slice(76, 78).trim();
  if (declarado) return declarado.toUpperCase();
  const nombre = line.slice(12, 16).trim().replace(/[^A-Za-z]/g, "");
  return (nombre.slice(0, 1) || "C").toUpperCase();
}

/**
 * Metales, aguas y demás grupos del receptor, con su cadena. Las aguas del depósito se cuentan pero no se devuelven
 * como átomos: son cientos y la receta del catálogo las retira todas.
 */
export function parsePdbHetero(pdb: string, { conAguas }: { conAguas: boolean }): { atomos: AtomoHetero[]; grupos: GrupoHetero[] } {
  const atomos: AtomoHetero[] = [];
  const grupos = new Map<string, GrupoHetero>();
  for (const line of pdb.split("\n")) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    const residuo = line.slice(17, 20).trim().toUpperCase();
    if (RESIDUOS_DE_PROTEINA.has(residuo)) continue;
    const x = parseFloat(line.slice(30, 38)), y = parseFloat(line.slice(38, 46)), z = parseFloat(line.slice(46, 54));
    if (isNaN(x) || isNaN(y) || isNaN(z)) continue;
    const element = elementoDeLaLinea(line);
    const tipo: GrupoHetero["tipo"] = AGUAS.has(residuo) ? "agua" : METALES.has(element) && METALES.has(residuo) ? "metal" : "grupo";
    const cadena = (line[21] ?? "").trim().toUpperCase();
    const numero = line.slice(22, 27).trim();
    const clave = `${cadena}:${residuo}${numero}`;
    const g = grupos.get(clave) ?? { clave, residuo, cadena, numero, tipo, atomos: 0 };
    g.atomos++;
    grupos.set(clave, g);
    if (tipo !== "agua" || conAguas) atomos.push({ x, y, z, element, tipo, grupo: clave });
  }
  return { atomos, grupos: [...grupos.values()] };
}

/** La clave de un residuo es su cadena y su nombre con número: en un homodímero, A:ASP25 y B:ASP25 son dos. */
export const claveDeResiduo = (cadena: string | undefined, resId: string) => `${(cadena ?? "").toUpperCase()}:${resId.toUpperCase()}`;

/**
 * Si el receptor pasa de `max` átomos, se quedan los del sitio y los más cercanos a `centro`. Antes se cortaba en el
 * orden del archivo, sin avisar, y en un complejo grande el corte podía llevarse el sitio entero.
 */
export function recortarAlrededor<T extends { x: number; y: number; z: number; isHotspot?: boolean }>(atomos: T[], centro: [number, number, number], max: number): T[] {
  if (atomos.length <= max) return atomos;
  const [cx, cy, cz] = centro;
  const delSitio = atomos.filter((a) => a.isHotspot);
  const resto = atomos.filter((a) => !a.isHotspot)
    .map((a) => ({ a, d: (a.x - cx) ** 2 + (a.y - cy) ** 2 + (a.z - cz) ** 2 }))
    .sort((p, q) => p.d - q.d)
    .slice(0, Math.max(0, max - delSitio.length))
    .map((p) => p.a);
  return [...delSitio, ...resto];
}

// ── Estilo glassglow unificado: los 4 botones de esquina comparten el MISMO
//    tamaño (padding, tipografía, radio) y el mismo efecto vidrio + glow. ──

// Lookup de hotspots por CADENA: "B:LYS14" → cadena B; "MET97" → cadena del
// receptor (o "*" = cualquier cadena si no hay cadena definida). Respetar la
// cadena es FÍSICO: en dímeros (HIV-proteasa) el residuo homónimo de la otra
// cadena NO es el hotspot.
function buildHotspotLookup(hotspots: Array<{ name: string }>, fallbackChain?: string): Map<string, Set<string>> {
  const map = new Map<string, Set<string>>();
  hotspots.forEach((h) => {
    const upper = h.name.toUpperCase();
    const parts = upper.split(":");
    const hasChain = parts.length === 2 && !!parts[0].trim();
    const chain = hasChain ? parts[0].trim() : (fallbackChain ?? "").trim().toUpperCase() || "*";
    const rid = (hasChain ? parts[1] : upper).trim();
    if (!rid) return;
    const set = map.get(chain) ?? new Set<string>();
    set.add(rid);
    map.set(chain, set);
  });
  return map;
}

/** Los átomos de la proteína (o del ácido nucleico). Los heteroátomos van aparte: `parsePdbHetero`. Sin límite. */
export function parsePdbAtoms(pdb: string, lookup: Map<string, Set<string>>, chains?: Set<string>): Atom[] {
  const atoms: Atom[] = [];
  for (const line of pdb.split("\n")) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    const resName = line.slice(17, 20).trim().toUpperCase();
    if (!RESIDUOS_DE_PROTEINA.has(resName)) continue;
    const ch = (line[21] ?? "").trim().toUpperCase();
    if (chains && chains.size > 0 && !chains.has(ch)) continue;
    const x = parseFloat(line.slice(30, 38));
    const y = parseFloat(line.slice(38, 46));
    const z = parseFloat(line.slice(46, 54));
    if (isNaN(x) || isNaN(y) || isNaN(z)) continue;
    const element = elementoDeLaLinea(line);
    // ¿Este átomo pertenece a un residuo del sitio activo (hotspot)?
    const resSeq = line.slice(22, 27).trim();
    const rid = `${resName}${resSeq}`.toUpperCase();
    const isHotspot = lookup.get(ch)?.has(rid) || lookup.get("*")?.has(rid);
    atoms.push({ x, y, z, element, isHotspot: !!isHotspot, resId: rid, chain: ch });
  }
  return atoms;
}

type HotspotMarker = { x: number; y: number; z: number; name: string; importance: number };

export function parsePdbHotspots(pdb: string, hotspots: Array<{ name: string; importance?: number }>, chains?: Set<string>): HotspotMarker[] {
  // Extrae el CA de cada residuo hotspot respetando SU cadena (fallback:
  // "A:LEU221" con cadena explícita o "LEU221" en cualquier cadena).
  const impByRid = new Map<string, number>();
  const lookup = new Map<string, Set<string>>();
  hotspots.forEach((h) => {
    const upper = h.name.toUpperCase();
    const parts = upper.split(":");
    const hasChain = parts.length === 2 && !!parts[0].trim();
    const chain = hasChain ? parts[0].trim() : "*";
    const rid = (hasChain ? parts[1] : upper).trim();
    if (!rid) return;
    impByRid.set(`${chain}:${rid}`, h.importance ?? 0.5);
    const set = lookup.get(chain) ?? new Set<string>();
    set.add(rid);
    lookup.set(chain, set);
  });
  const result: HotspotMarker[] = [];
  const seen = new Set<string>();
  for (const line of pdb.split("\n")) {
    if (!line.startsWith("ATOM")) continue;
    const ch = line[21].trim().toUpperCase();
    if (chains && chains.size > 0 && !chains.has(ch)) continue;
    const resName = line.slice(17, 20).trim().toUpperCase();
    const resSeq = line.slice(22, 27).trim();
    const atomName = line.slice(12, 16).trim().toUpperCase();
    const rid = `${resName}${resSeq}`.toUpperCase();
    if (atomName !== "CA") continue;
    const hit = lookup.get(ch)?.has(rid) || lookup.get("*")?.has(rid);
    if (!hit) continue;
    const key = `${ch}:${rid}`;
    if (seen.has(key)) continue;
    seen.add(key);
    try {
      result.push({
        x: parseFloat(line.slice(30, 38)),
        y: parseFloat(line.slice(38, 46)),
        z: parseFloat(line.slice(46, 54)),
        name: `${ch}:${rid}`,
        importance: impByRid.get(key) ?? impByRid.get(`*:${rid}`) ?? 0.5,
      });
    } catch { /* skip */ }
  }
  return result;
}

// ── Nubes de átomos con InstancedMesh (una llamada de dibujo por nube) ──

type Esfera = { x: number; y: number; z: number; r: number; color: string };

/**
 * Esferas con luz. Antes eran `meshBasicMaterial`, que ignora las luces: cada átomo era un disco plano del mismo color
 * y la escena no tenía profundidad. Lambert calcula la luz por vértice, que es barato también sin tarjeta gráfica.
 */
function NubeDeEsferas({ esferas, segmentos = 10, brillo = false }: { esferas: Esfera[]; segmentos?: number; brillo?: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const invalidate = useThree((s) => s.invalidate);

  useEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    const m = new THREE.Matrix4();
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const e = new THREE.Vector3();
    const c = new THREE.Color();
    esferas.forEach((a, i) => {
      p.set(a.x, a.y, a.z);
      e.set(a.r, a.r, a.r);
      mesh.setMatrixAt(i, m.compose(p, q, e));
      mesh.setColorAt(i, c.set(a.color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
    // El lienzo sólo dibuja cuando se le pide (`frameloop="demand"`): un cambio
    // hecho a mano sobre la malla hay que anunciarlo.
    invalidate();
  }, [esferas, invalidate]);

  if (esferas.length === 0) return null;
  return (
    <instancedMesh key={esferas.length} ref={ref} args={[undefined, undefined, esferas.length]} frustumCulled={false}>
      <sphereGeometry args={[1, segmentos, Math.max(6, Math.round(segmentos * 0.75))]} />
      {brillo ? <meshPhongMaterial shininess={70} specular="#3a4458" /> : <meshLambertMaterial />}
    </instancedMesh>
  );
}

/**
 * El receptor. SITIO ACTIVO: cada residuo con SU color (convención spectrum), identificado por cadena y número; el resto,
 * gris. El radio es el covalente, igual para todos los átomos del mismo elemento.
 */
function AtomCloud({ atoms, hotspotColors }: { atoms: Atom[]; hotspotColors: Map<string, string> }) {
  // El resto del receptor va a la mitad del radio: es contexto. A tamaño completo, los átomos que quedan entre la cámara
  // y la caja tapaban el sitio entero (captura del 2026-11-10 con 8HFI).
  const esferas = useMemo(() => atoms.map((a): Esfera => ({
    x: a.x, y: a.y, z: a.z, r: atomRadius(a.element) * (a.isHotspot ? 1 : RADIO_DEL_CONTEXTO),
    color: a.isHotspot
      ? hotspotColors.get(claveDeResiduo(a.chain, a.resId ?? "")) ?? HOTSPOT_ELEMENT_COLOR[a.element] ?? HOTSPOT_ELEMENT_COLOR.C
      : REST_ATOM_COLOR,
  })), [atoms, hotspotColors]);
  return <NubeDeEsferas esferas={esferas} segmentos={8} />;
}

/** Metales (esfera grande, color de Jmol), cofactores y grupos (ámbar) y, si Vina las vio, aguas (punto rojo). */
function HeteroCloud({ atomos }: { atomos: AtomoHetero[] }) {
  const esferas = useMemo(() => atomos.map((a): Esfera => ({
    x: a.x, y: a.y, z: a.z,
    r: a.tipo === "metal" ? 0.95 : a.tipo === "agua" ? 0.32 : atomRadius(a.element),
    color: a.tipo === "metal" ? COLOR_DE_METAL[a.element] ?? "#b8b8d0" : a.tipo === "agua" ? AGUA_COLOR : HETERO_ELEMENT_COLOR[a.element] ?? HETERO_ELEMENT_COLOR.C,
  })), [atomos]);
  return <NubeDeEsferas esferas={esferas} segmentos={14} brillo />;
}

// ── Molécula (ligando acoplado) desde SDF ──────────────────────────────

type LigandAtom = { x: number; y: number; z: number; element: string };
type LigandBond = { a: number; b: number; type: number };

// Parsea un archivo SDF (Molfile V2000) → átomos + enlaces.
// Usa la PRIMERA pose (el SDF de poses trae varias separadas por $$$$).
function parseSdfLigand(sdf: string): { atoms: LigandAtom[]; bonds: LigandBond[] } {
  const block = sdf.split("$$$$")[0] ?? sdf;
  const lines = block.split(/\r?\n/);
  if (lines.length < 4) return { atoms: [], bonds: [] };

  const countsLine = lines[3] ?? "";
  const nAtoms = parseInt(countsLine.slice(0, 3).trim(), 10) || 0;
  const nBonds = parseInt(countsLine.slice(3, 6).trim(), 10) || 0;

  const atoms: LigandAtom[] = [];
  for (let i = 0; i < nAtoms; i++) {
    const line = lines[4 + i] ?? "";
    const x = parseFloat(line.slice(0, 10));
    const y = parseFloat(line.slice(10, 20));
    const z = parseFloat(line.slice(20, 30));
    const element = (line.slice(31, 34).trim() || "C").toUpperCase();
    if (isNaN(x) || isNaN(y) || isNaN(z)) continue;
    atoms.push({ x, y, z, element });
  }

  const bonds: LigandBond[] = [];
  for (let i = 0; i < nBonds; i++) {
    const line = lines[4 + nAtoms + i] ?? "";
    const a = parseInt(line.slice(0, 3).trim(), 10) - 1;
    const b = parseInt(line.slice(3, 6).trim(), 10) - 1;
    const type = parseInt(line.slice(6, 9).trim(), 10) || 1;
    if (isNaN(a) || isNaN(b) || a < 0 || b < 0 || a >= atoms.length || b >= atoms.length) continue;
    bonds.push({ a, b, type });
  }

  return { atoms, bonds };
}

// Enlaces con orden real (single/double/triple). Los enlaces dobles y triples
// se dibujan como líneas paralelas desplazadas (convención 3D estándar).
// Los aromáticos (tipo 4) se dibujan como línea simple (convención 3D).
function buildBondLines(atoms: LigandAtom[], bonds: LigandBond[]): number[] {
  const pts: number[] = [];
  const add = (a: [number, number, number], b: [number, number, number]) => pts.push(...a, ...b);
  const h = 0.22; // separación lateral entre líneas paralelas (Å)
  bonds.forEach((b) => {
    const a = atoms[b.a];
    const c = atoms[b.b];
    if (!a || !c) return;
    const ax = a.x, ay = a.y, az = a.z;
    const bx = c.x, by = c.y, bz = c.z;
    const dx = bx - ax, dy = by - ay, dz = bz - az;
    const len = Math.hypot(dx, dy, dz);
    if (len < 1e-6) return;
    const ux = dx / len, uy = dy / len, uz = dz / len;
    // Vector perpendicular al eje del enlace (dirección de desplazamiento).
    let px = 0, py = 0, pz = 0;
    if (Math.abs(uy) < 0.9) { px = -uz; pz = ux; } else { px = 1; }
    const pl = Math.hypot(px, py, pz);
    if (pl < 1e-6) return;
    px /= pl; py /= pl; pz /= pl;

    if (b.type === 3) {
      add([ax - px * h, ay - py * h, az - pz * h], [bx - px * h, by - py * h, bz - pz * h]);
      add([ax, ay, az], [bx, by, bz]);
      add([ax + px * h, ay + py * h, az + pz * h], [bx + px * h, by + py * h, bz + pz * h]);
    } else if (b.type === 2) {
      add([ax - px * h, ay - py * h, az - pz * h], [bx - px * h, by - py * h, bz - pz * h]);
      add([ax + px * h, ay + py * h, az + pz * h], [bx + px * h, by + py * h, bz + pz * h]);
    } else {
      // single (1) y aromático (4): línea simple, convención 3D estándar
      add([ax, ay, az], [bx, by, bz]);
    }
  });
  return pts;
}

/** Libera la geometría y el material de una línea gruesa cuando dejan de usarse (no lo hace nadie más: son `primitive`). */
function useLiberar(obj: { geometry: { dispose(): void }; material: unknown } | null) {
  useEffect(() => () => {
    if (!obj) return;
    obj.geometry.dispose();
    (obj.material as THREE.Material).dispose();
  }, [obj]);
}

/** El grosor de una línea gruesa se calcula en píxeles: necesita el tamaño del lienzo. */
function useResolucion(materiales: LineMaterial[]) {
  const { size, invalidate } = useThree();
  useEffect(() => {
    for (const m of materiales) m.resolution.set(size.width, size.height);
    invalidate();
  }, [size.width, size.height, materiales, invalidate]);
}

// Molécula en el canvas: átomos con brillo (se distinguen del receptor, que es mate) + enlaces (fat lines).
function LigandCloud({ atoms, bonds }: { atoms: LigandAtom[]; bonds: LigandBond[] }) {
  const esferas = useMemo(() => atoms.map((a): Esfera => ({
    x: a.x, y: a.y, z: a.z, r: atomRadius(a.element) * 0.85,
    color: LIGAND_ELEMENT_COLOR[a.element] ?? LIGAND_ELEMENT_COLOR.C,
  })), [atoms]);

  // Enlaces como fat lines (LineSegments2 — grosor real en px), con el orden
  // de enlace químico real (single/doble/triple).
  const bondObj = useMemo(() => {
    const geo = new LineSegmentsGeometry();
    geo.setPositions(buildBondLines(atoms, bonds));
    const mat = new LineMaterial({
      color: new THREE.Color(LIGAND_BOND_COLOR).getHex(),
      transparent: true,
      opacity: 0.9,
      linewidth: 3,
      depthWrite: false,
    });
    return new LineSegments2(geo, mat);
  }, [atoms, bonds]);
  useLiberar(bondObj);
  const materiales = useMemo(() => [bondObj.material as LineMaterial], [bondObj]);
  useResolucion(materiales);

  if (atoms.length === 0) return null;

  return (
    <group>
      <primitive object={bondObj} />
      <NubeDeEsferas esferas={esferas} segmentos={16} brillo />
    </group>
  );
}

// ── Grid box con cuadrículas (estilo grid de docking) ─────────────────
//
// Es lo que hace reconocible un visor de docking: la caja de Vina con su retícula. Se mantienen las cuatro piezas —
// aristas, retícula de 8 divisiones en las caras, caras translúcidas y centro—, pero con jerarquía: las aristas mandan
// (gruesas y brillantes), la retícula acompaña (fina y tenue) y el centro lleva los tres ejes, como la caja de
// AutoDockTools, para saber hacia dónde mira la escena.

const CAJA_COLOR = "#22d3ee";
const DIVISIONES_DE_LA_CAJA = 8;

function GridBox({ gridInfo }: { gridInfo: NonNullable<Props["gridInfo"]> }) {
  const { centerX, centerY, centerZ, sizeX, sizeY, sizeZ } = gridInfo;

  const { aristas, reticula, ejes } = useMemo(() => {
    const hx = sizeX / 2, hy = sizeY / 2, hz = sizeZ / 2;
    const cx = centerX, cy = centerY, cz = centerZ;
    const enAristas: number[] = [];
    const enReticula: number[] = [];
    const seg = (dest: number[], a: number[], b: number[]) => { dest.push(...a, ...b); };

    // ── Bordes del cubo (12 aristas) ──
    const v = [
      [cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz],
      [cx + hx, cy + hy, cz - hz], [cx - hx, cy + hy, cz - hz],
      [cx - hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz + hz],
      [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz],
    ];
    [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]].forEach(([i, j]) => seg(enAristas, v[i], v[j]));

    // ── Retícula sobre las seis caras: líneas paralelas a cada eje ──
    for (let i = 1; i < DIVISIONES_DE_LA_CAJA; i++) {
      const f = i / DIVISIONES_DE_LA_CAJA;
      const ox = -hx + sizeX * f, oy = -hy + sizeY * f, oz = -hz + sizeZ * f;
      // paralelas a X
      seg(enReticula, [cx - hx, cy + oy, cz - hz], [cx + hx, cy + oy, cz - hz]);
      seg(enReticula, [cx - hx, cy + oy, cz + hz], [cx + hx, cy + oy, cz + hz]);
      seg(enReticula, [cx - hx, cy - hy, cz + oz], [cx + hx, cy - hy, cz + oz]);
      seg(enReticula, [cx - hx, cy + hy, cz + oz], [cx + hx, cy + hy, cz + oz]);
      // paralelas a Y
      seg(enReticula, [cx + ox, cy - hy, cz - hz], [cx + ox, cy + hy, cz - hz]);
      seg(enReticula, [cx + ox, cy - hy, cz + hz], [cx + ox, cy + hy, cz + hz]);
      seg(enReticula, [cx - hx, cy - hy, cz + oz], [cx - hx, cy + hy, cz + oz]);
      seg(enReticula, [cx + hx, cy - hy, cz + oz], [cx + hx, cy + hy, cz + oz]);
      // paralelas a Z
      seg(enReticula, [cx + ox, cy - hy, cz - hz], [cx + ox, cy - hy, cz + hz]);
      seg(enReticula, [cx + ox, cy + hy, cz - hz], [cx + ox, cy + hy, cz + hz]);
      seg(enReticula, [cx - hx, cy + oy, cz - hz], [cx - hx, cy + oy, cz + hz]);
      seg(enReticula, [cx + hx, cy + oy, cz - hz], [cx + hx, cy + oy, cz + hz]);
    }

    const lineas = (puntos: number[], opciones: ConstructorParameters<typeof LineMaterial>[0]) => {
      const geo = new LineSegmentsGeometry();
      geo.setPositions(puntos);
      return new LineSegments2(geo, new LineMaterial({ transparent: true, depthWrite: false, ...opciones }));
    };
    // Los tres ejes desde el centro: X rojo, Y verde, Z azul (el convenio de los programas de modelado).
    const largo = Math.max(1.5, Math.min(sizeX, sizeY, sizeZ) / 6);
    const ejes = (["#f87171", "#4ade80", "#60a5fa"] as const).map((color, k) => {
      const fin = [cx, cy, cz];
      fin[k] += largo;
      return lineas([cx, cy, cz, ...fin], { color: new THREE.Color(color).getHex(), opacity: 0.95, linewidth: 2.5 });
    });
    return {
      aristas: lineas(enAristas, { color: new THREE.Color(CAJA_COLOR).getHex(), opacity: 0.95, linewidth: 2.5 }),
      reticula: lineas(enReticula, { color: new THREE.Color(CAJA_COLOR).getHex(), opacity: 0.32, linewidth: 1 }),
      ejes,
    };
  }, [centerX, centerY, centerZ, sizeX, sizeY, sizeZ]);

  const todas = useMemo(() => [aristas, reticula, ...ejes], [aristas, reticula, ejes]);
  useEffect(() => () => {
    for (const l of todas) { l.geometry.dispose(); (l.material as THREE.Material).dispose(); }
  }, [todas]);
  // CRÍTICO: LineMaterial necesita la resolución del canvas para calcular el
  // grosor en píxeles. Sin esto, linewidth se ve mal o las líneas no aparecen.
  const materiales = useMemo(() => todas.map((l) => l.material as LineMaterial), [todas]);
  useResolucion(materiales);

  const fmt = (n: number) => n.toFixed(1);
  return (
    <group>
      {/* Caras translúcidas: el volumen que explora Vina */}
      <mesh position={[centerX, centerY, centerZ]}>
        <boxGeometry args={[sizeX, sizeY, sizeZ]} />
        <meshBasicMaterial color={CAJA_COLOR} transparent opacity={0.035} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      <primitive object={reticula} />
      <primitive object={aristas} />
      {ejes.map((eje, i) => <primitive key={i} object={eje} />)}
      {/* Centro de la caja */}
      <mesh position={[centerX, centerY, centerZ]}>
        <sphereGeometry args={[0.45, 16, 16]} />
        <meshBasicMaterial color="#cffafe" />
      </mesh>
      <GridLabel
        position={[centerX, centerY + sizeY / 2 + Math.max(1.2, sizeY * 0.08), centerZ]}
        ancho={Math.max(sizeX, sizeZ) * 0.95}
        lineas={[`C  ${fmt(centerX)}, ${fmt(centerY)}, ${fmt(centerZ)} Å`, `${fmt(sizeX)} × ${fmt(sizeY)} × ${fmt(sizeZ)} Å`]}
      />
    </group>
  );
}

/**
 * Etiqueta de la caja. Antes era un sprite sin escala, de 1 Å de ancho: ilegible a cualquier distancia. Ahora mide lo
 * que la caja, se dibuja a doble resolución y siempre encima (no la tapa ningún átomo).
 */
function GridLabel({ position, ancho, lineas }: { position: [number, number, number]; ancho: number; lineas: string[] }) {
  const texto = lineas.join("|");
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 64 + 56 * lineas.length;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "rgba(6,16,26,0.82)";
      ctx.beginPath();
      ctx.roundRect?.(4, 4, canvas.width - 8, canvas.height - 8, 18);
      ctx.fill();
      ctx.strokeStyle = "rgba(34,211,238,0.55)";
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      lineas.forEach((linea, i) => {
        ctx.fillStyle = i === 0 ? "#cffafe" : "#67e8f9";
        ctx.font = `${i === 0 ? "bold " : ""}46px ui-monospace, Consolas, monospace`;
        ctx.fillText(linea, canvas.width / 2, 36 + 28 + i * 56);
      });
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.anisotropy = 4;
    tex.needsUpdate = true;
    return tex;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [texto]);
  useEffect(() => () => texture.dispose(), [texture]);
  const alto = ancho * (texture.image.height / texture.image.width);

  return (
    <sprite position={position} scale={[ancho, alto, 1]} renderOrder={10}>
      <spriteMaterial map={texture} transparent depthTest={false} depthWrite={false} />
    </sprite>
  );
}

// ── Sitio activo: hotspots como esferas destacadas ─────────────────────

// Esfera wireframe con líneas GRUESAS (LineSegments2 + LineMaterial de
// three-stdlib — las fat lines de WebGL2 soportan linewidth real, a
// diferencia de lineBasicMaterial que siempre dibuja grosor 1).
function FatWireSphere({ position, radius, color, opacity = 0.35, lineWidth = 2.5 }: {
  position: [number, number, number];
  radius: number;
  color: string;
  opacity?: number;
  lineWidth?: number;
}) {
  // Genera líneas de paralelos y meridianos de la esfera
  const geometry = useMemo(() => {
    const pts: number[] = [];
    const segments = 32; // resolución del círculo
    const rings = 8;     // nº de paralelos
    const meridians = 10;

    // Paralelos (círculos a lo largo de "latitud")
    for (let r = 1; r < rings; r++) {
      const phi = (r / rings) * Math.PI - Math.PI / 2; // latitud
      const cy = Math.sin(phi) * radius;
      const cr = Math.cos(phi) * radius;
      for (let i = 0; i < segments; i++) {
        const a1 = (i / segments) * Math.PI * 2;
        const a2 = ((i + 1) / segments) * Math.PI * 2;
        pts.push(
          Math.cos(a1) * cr, cy, Math.sin(a1) * cr,
          Math.cos(a2) * cr, cy, Math.sin(a2) * cr,
        );
      }
    }
    // Meridianos (círculos a lo largo de "longitud")
    for (let m = 0; m < meridians; m++) {
      const a = (m / meridians) * Math.PI;
      for (let i = 0; i < segments; i++) {
        const t1 = (i / segments) * Math.PI * 2;
        const t2 = ((i + 1) / segments) * Math.PI * 2;
        pts.push(
          Math.cos(t1) * Math.cos(a) * radius, Math.sin(t1) * radius, Math.cos(t1) * Math.sin(a) * radius,
          Math.cos(t2) * Math.cos(a) * radius, Math.sin(t2) * radius, Math.cos(t2) * Math.sin(a) * radius,
        );
      }
    }

    const geo = new LineSegmentsGeometry();
    geo.setPositions(pts);
    return geo;
  }, [radius]);

  const material = useMemo(() => {
    const m = new LineMaterial({
      color: new THREE.Color(color).getHex(),
      transparent: true,
      opacity,
      linewidth: lineWidth, // grosor real en px
      depthWrite: false,
    });
    return m;
  }, [color, opacity, lineWidth]);

  // Resolución del canvas para el grosor correcto en px
  const materiales = useMemo(() => [material], [material]);
  useResolucion(materiales);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useEffect(() => () => material.dispose(), [material]);

  const lineObj = useMemo(() => new LineSegments2(geometry, material), [geometry, material]);

  return (
    <primitive object={lineObj} position={position} />
  );
}

// Envolvente del bolsillo: centroide PONDERADO por importancia + radio
// derivado del spread real de los CAs (máx. distancia al centroide + margen
// de 4 Å para alcanzar cadenas laterales y el ligando acoplado). Reemplaza
// el radio fijo de 8 Å que no dependía del tamaño real del bolsillo.
type ResidueEnvelope = { cx: number; cy: number; cz: number; radius: number };

// Envolvente por residuo hotspot: centroide de sus átomos + radio = máxima
// distancia al centroide + radio atómico (contiene la cadena lateral).
// Se usa SOLO para centrar las esferas de click sobre cada residuo.
function buildResidueEnvelopes(atoms: Atom[], markers: HotspotMarker[]): Map<string, ResidueEnvelope> {
  const groups = new Map<string, { x: number; y: number; z: number; r: number }[]>();
  atoms.forEach((a) => {
    if (!a.isHotspot || !a.resId) return;
    const arr = groups.get(a.resId) ?? [];
    arr.push({ x: a.x, y: a.y, z: a.z, r: atomRadius(a.element) });
    groups.set(a.resId, arr);
  });
  const perResidue = new Map<string, ResidueEnvelope>();
  groups.forEach((arr, rid) => {
    const n = arr.length;
    const cx = arr.reduce((s, a) => s + a.x, 0) / n;
    const cy = arr.reduce((s, a) => s + a.y, 0) / n;
    const cz = arr.reduce((s, a) => s + a.z, 0) / n;
    const radius = Math.max(...arr.map((a) => Math.hypot(a.x - cx, a.y - cy, a.z - cz) + a.r));
    perResidue.set(rid, { cx, cy, cz, radius });
  });
  return perResidue;
}

// Superficie ADAPTATIVA del bolsillo (marching cubes): moldea el volumen que
// envuelve los átomos del sitio activo siguiendo su forma real — la convención
// de fpocket/DoGSite/PyMOL-sites — en vez de una esfera genérica. Coloreada
// por vértice según la importancia de cada residuo (heat map).
function PocketSurface({ atoms }: { atoms: { x: number; y: number; z: number; r: number; color: THREE.Color }[] }) {
  const mc = useMemo(() => {
    if (atoms.length === 0) return null;
    const pad = 4.0;
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    atoms.forEach((a) => {
      minX = Math.min(minX, a.x - a.r); maxX = Math.max(maxX, a.x + a.r);
      minY = Math.min(minY, a.y - a.r); maxY = Math.max(maxY, a.y + a.r);
      minZ = Math.min(minZ, a.z - a.r); maxZ = Math.max(maxZ, a.z + a.r);
    });
    const fieldSize = Math.max(maxX - minX, maxY - minY, maxZ - minZ) + pad * 2;
    const ox = minX - pad, oy = minY - pad, oz = minZ - pad;
    // ~1.6 células/Å → campo de 24³ a 48³
    const resolution = Math.min(48, Math.max(24, Math.round(fieldSize * 1.6)));

    // Con luz: la superficie se lee como un volumen y no como una mancha de color.
    const material = new THREE.MeshLambertMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.26,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const m = new MarchingCubes(resolution, material, false, true, 20000);
    // Campo normalizado [-1,1] → mundo: centro + escala·v
    m.position.set(ox + fieldSize / 2, oy + fieldSize / 2, oz + fieldSize / 2);
    m.scale.set(fieldSize / 2, fieldSize / 2, fieldSize / 2);
    atoms.forEach((a) => {
      const nx = (a.x - ox) / fieldSize;
      const ny = (a.y - oy) / fieldSize;
      const nz = (a.z - oz) / fieldSize;
      const rn = Math.max(a.r / fieldSize, 1e-4);
      // val = strength/d² - subtract = isolation(80) en r=rn → strength = 81·rn²
      m.addBall(nx, ny, nz, 81 * rn * rn, 1.0, a.color);
    });
    m.update();
    return m;
  }, [atoms]);

  useEffect(() => () => {
    if (mc) {
      mc.geometry.dispose();
      (mc.material as THREE.Material).dispose();
    }
  }, [mc]);

  if (!mc) return null;
  return <primitive object={mc} />;
}

// Líneas discontinuas de interacción no-covalente (convención PyMOL/PLIP):
// un segmento entre el átomo del ligando y el átomo de la proteína por
// contacto (H-bond, hidrofóbico, π-stacking, puente salino, catión-π...).
function InteractionLines({ interactions }: { interactions: InteractionDatum[] }) {
  const items = useMemo(() => {
    if (interactions.length === 0) return [];
    const byType = new Map<string, number[]>();
    interactions.forEach((it) => {
      const arr = byType.get(it.type) ?? [];
      arr.push(
        it.ligand_coords.x, it.ligand_coords.y, it.ligand_coords.z,
        it.protein_coords.x, it.protein_coords.y, it.protein_coords.z,
      );
      byType.set(it.type, arr);
    });
    return [...byType.entries()].map(([type, pts]) => {
      const geo = new LineSegmentsGeometry();
      geo.setPositions(pts);
      const mat = new LineMaterial({
        color: new THREE.Color(INTERACTION_COLORS[type] ?? "#94a3b8").getHex(),
        transparent: true,
        opacity: 0.95,
        linewidth: 2,
        depthWrite: false,
      });
      mat.dashed = true;
      mat.dashSize = 0.45;
      mat.gapSize = 0.35;
      return { type, obj: new LineSegments2(geo, mat) };
    });
  }, [interactions]);

  const materiales = useMemo(() => items.map((it) => it.obj.material as LineMaterial), [items]);
  useResolucion(materiales);

  useEffect(() => () => {
    items.forEach((it) => {
      it.obj.geometry.dispose();
      (it.obj.material as LineMaterial).dispose();
    });
  }, [items]);

  if (items.length === 0) return null;
  return <group>{items.map((it) => <primitive key={it.type} object={it.obj} />)}</group>;
}

function hotspotCentroid(hs: { x: number; y: number; z: number }[]): [number, number, number] {
  const n = hs.length;
  return [
    hs.reduce((a, h) => a + h.x, 0) / n,
    hs.reduce((a, h) => a + h.y, 0) / n,
    hs.reduce((a, h) => a + h.z, 0) / n,
  ];
}

// ── Cámara reactiva + sincronización de VISTA COMPLETA ─────────────────

export type ViewerCamera = {
  position: [number, number, number]; // posición 3D de la cámara
  target: [number, number, number];   // punto al que apunta (focus)
  distance: number;                   // |position - target|
};

// Cámara inicial (default): centrada en focus, desde una diagonal
function defaultCameraPos(center: [number, number, number], distance: number): [number, number, number] {
  return [center[0] + distance * 0.8, center[1] + distance * 0.6, center[2] + distance];
}

function CameraRig({ center, distance, externalCamera, onCameraChange, active }: {
  center: [number, number, number];
  distance: number;
  externalCamera?: ViewerCamera | null;
  onCameraChange?: (cam: ViewerCamera) => void;
  active?: boolean;
}) {
  const { camera, invalidate } = useThree();
  const controlsRef = useRef<any>(null);
  const lastKey = useRef("");
  const lastExternal = useRef("");

  // El lienzo dibuja a demanda. El encuadre de abajo vive en `useFrame`, que ya
  // no corre solo: cuando cambia el foco o llega una cámara de fuera hay que
  // pedir el fotograma en que se aplica.
  const claveDelFoco = `${center[0].toFixed(2)},${center[1].toFixed(2)},${center[2].toFixed(2)}`;
  const claveExterna = externalCamera
    ? externalCamera.position.map((v) => v.toFixed(2)).join(",") + "|" + externalCamera.target.map((v) => v.toFixed(2)).join(",")
    : "";
  useEffect(() => { invalidate(); }, [claveDelFoco, claveExterna, invalidate]);

  // Reportar la cámara cuando el usuario la deja quieta (rotación/zoom/pan).
  //
  // Antes esto vivía en `useFrame` y obligaba a dibujar 60 veces por segundo
  // aunque nadie tocara nada. Medido en el export (2026-11-09): con Web3D abierto
  // y en reposo, el navegador gastaba el 46 % de un núcleo con tarjeta gráfica y,
  // sin ella, entre 9 y 11 núcleos enteros —el rasterizador por software usa todos
  // los que hay—, que son los mismos que necesita Vina. Ahora se dibuja sólo
  // cuando algo cambia y la cámara se informa al terminar el gesto.
  const informe = useRef<ReturnType<typeof setTimeout> | null>(null);
  const informar = useRef<() => void>(() => {});
  informar.current = () => {
    if (!onCameraChange || !controlsRef.current || !active) return; // visor oculto → no pisa al activo
    const t = controlsRef.current.target;
    const pos = camera.position;
    onCameraChange({
      position: [pos.x, pos.y, pos.z],
      target: [t.x, t.y, t.z],
      distance: pos.distanceTo(t),
    });
  };
  const alMoverLaCamara = useRef(() => {
    if (informe.current) clearTimeout(informe.current);
    informe.current = setTimeout(() => { informe.current = null; informar.current(); }, 250);
  });
  useEffect(() => () => { if (informe.current) clearTimeout(informe.current); }, []);

  useFrame(() => {
    // ── Adoptar cámara externa (de MolStar) — UNA vez por cambio ──
    if (externalCamera) {
      const ek = externalCamera.position.map((v) => v.toFixed(2)).join(",") + "|" +
                 externalCamera.target.map((v) => v.toFixed(2)).join(",");
      if (ek !== lastExternal.current) {
        lastExternal.current = ek;
        const [px, py, pz] = externalCamera.position;
        const [tx, ty, tz] = externalCamera.target;
        camera.position.set(px, py, pz);
        camera.up.set(0, 1, 0);
        camera.lookAt(tx, ty, tz);
        camera.updateProjectionMatrix();
        if (controlsRef.current) {
          controlsRef.current.target.set(tx, ty, tz);
          controlsRef.current.update();
        }
        // Se informa DESPUÉS de encuadrar: antes de este fotograma los controles
        // apuntan al origen y el otro visor heredaría una vista que nadie ha visto.
        alMoverLaCamara.current();
      }
      return;
    }

    // ── Encuadre inicial (solo si cambió el focus) ──
    const key = `${center[0].toFixed(2)},${center[1].toFixed(2)},${center[2].toFixed(2)}`;
    if (key === lastKey.current) return;
    lastKey.current = key;
    const [cx, cy, cz] = center;
    camera.position.set(...defaultCameraPos(center, distance));
    camera.up.set(0, 1, 0);
    camera.lookAt(cx, cy, cz);
    camera.updateProjectionMatrix();
    if (controlsRef.current) {
      controlsRef.current.target.set(cx, cy, cz);
      controlsRef.current.update();
    }
    alMoverLaCamara.current();
  });

  return <OrbitControls ref={controlsRef} enableZoom enablePan makeDefault onChange={alMoverLaCamara.current} />;
}

/** Vigila el contexto del lienzo: si se pierde y el navegador no lo devuelve, avisa. */
function VigiaDelContexto({ onPerdido }: { onPerdido?: () => void }) {
  const gl = useThree((s) => s.gl);
  const avisar = useRef(onPerdido);
  avisar.current = onPerdido;
  useEffect(() => {
    const lienzo = gl.domElement;
    let espera: ReturnType<typeof setTimeout> | null = null;
    const alPerder = () => {
      if (espera) clearTimeout(espera);
      espera = setTimeout(() => { espera = null; avisar.current?.(); }, ESPERA_DE_CONTEXTO_MS);
    };
    const alRecuperar = () => { if (espera) clearTimeout(espera); espera = null; };
    lienzo.addEventListener("webglcontextlost", alPerder);
    lienzo.addEventListener("webglcontextrestored", alRecuperar);
    return () => {
      if (espera) clearTimeout(espera);
      lienzo.removeEventListener("webglcontextlost", alPerder);
      lienzo.removeEventListener("webglcontextrestored", alRecuperar);
    };
  }, [gl]);
  return null;
}

// ── Luz y profundidad ───────────────────────────────────────────────────

/** Una luz que sale de la cámara: la cara que se mira siempre está iluminada, se gire como se gire. */
function LuzDeCamara() {
  const camera = useThree((s) => s.camera);
  const luz = useRef<THREE.PointLight>(null);
  useFrame(() => { luz.current?.position.copy(camera.position); });
  return <pointLight ref={luz} intensity={2.6} decay={0} />;
}

/**
 * Pantalla completa. La del sistema si la ventana la concede; si no (o si falla), el visor ocupa la ventana entera.
 * En los dos casos se sale con Escape.
 */
function usePantallaCompleta(raiz: React.RefObject<HTMLDivElement | null>) {
  const [nativa, setNativa] = useState(false);
  const [enVentana, setEnVentana] = useState(false);
  useEffect(() => {
    const alCambiar = () => setNativa(!!raiz.current && document.fullscreenElement === raiz.current);
    document.addEventListener("fullscreenchange", alCambiar);
    return () => document.removeEventListener("fullscreenchange", alCambiar);
  }, [raiz]);
  useEffect(() => {
    if (!enVentana) return;
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") setEnVentana(false); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [enVentana]);
  // Si el visor se desmonta en pantalla completa (cambiar de caso, cambiar de visor), la ventana no se queda así.
  useEffect(() => {
    const nodo = raiz.current;
    return () => { if (nodo && document.fullscreenElement === nodo) void document.exitFullscreen().catch(() => {}); };
  }, [raiz]);
  const alternar = useCallback(() => {
    const nodo = raiz.current;
    if (!nodo) return;
    if (nativa) { void document.exitFullscreen().catch(() => {}); return; }
    if (enVentana) { setEnVentana(false); return; }
    if (typeof nodo.requestFullscreen === "function") nodo.requestFullscreen().catch(() => setEnVentana(true));
    else setEnVentana(true);
  }, [nativa, enVentana, raiz]);
  return { activa: nativa || enVentana, enVentana, alternar };
}

type ResiduoDelSitio = {
  clave: string;
  nombre: string;
  color: string;
  importancia: number;
  centro: [number, number, number];
  radio: number;
  atomos: Atom[];
};

const PALETA_DE_TIPO_POR_DEFECTO = "#c084fc";
/** En la leyenda, más grupos que éstos se resumen en «y N más»: la lista no puede tapar la escena. */
const GRUPOS_EN_LA_LEYENDA = 10;

// ── Componente principal ────────────────────────────────────────────────

export default function Web3DViewer({ proteinData, poseData, interactions, hotspots = SIN_HOTSPOTS, chain, gridInfo, onSwitchViewer, viewerLabel, onCameraChange, externalCamera, active = true, onNoDisponible, origenDelReceptor = "deposito" }: Props) {
  const { t, locale } = useLanguage();
  // Sin tarjeta gráfica cada píxel lo calcula el procesador: se dibuja a la
  // resolución de la pantalla, sin sobremuestreo ni suavizado de bordes.
  const porSoftware = comprobarWebGL().aceleracion === "software";
  const avisarNoDisponible = useRef(onNoDisponible);
  avisarNoDisponible.current = onNoDisponible;
  // Modo foco: ocultar los átomos grises del receptor (solo sitio activo + grid)
  const [showAtoms, setShowAtoms] = useState(true);
  // Visibilidad de la molécula (ligando acoplado, SDF)
  const [showMolecule, setShowMolecule] = useState(true);
  // Visibilidad de las líneas de interacción (H-bonds, hidrofóbicos...)
  const [showInteractions, setShowInteractions] = useState(true);
  // Metales, cofactores y aguas
  const [showHetero, setShowHetero] = useState(true);
  // Los dos paneles de la izquierda no se abren a la vez. Antes los dos abrían por defecto y la leyenda, con cada
  // residuo partido en dos líneas, tapaba el resumen y un cuarto de la escena.
  const [panel, setPanel] = useState<"resumen" | "leyenda" | null>(null);
  const alternarPanel = (cual: "resumen" | "leyenda") => setPanel((abierto) => (abierto === cual ? null : cual));
  // Panel OPCIONES (visibilidad receptor / molécula / interacciones)
  const [optionsOpen, setOptionsOpen] = useState(false);
  // Hotspot seleccionado (popup explicativo)
  const [selectedHotspot, setSelectedHotspot] = useState<{ name: string; importance: number } | null>(null);
  const raiz = useRef<HTMLDivElement>(null);
  const pantalla = usePantallaCompleta(raiz);
  // En pantalla completa hay sitio: la leyenda se abre sola.
  const pantallaActiva = useRef(false);
  useEffect(() => {
    if (pantallaActiva.current === pantalla.activa) return;
    pantallaActiva.current = pantalla.activa;
    setPanel(pantalla.activa ? "leyenda" : null);
  }, [pantalla.activa]);

  // Lookup de hotspots por CADENA (físico): "B:LYS14" → cadena B, "MET97" →
  // cadena del receptor. En dímeros (HIV-proteasa) el residuo homónimo de la
  // otra cadena NO es el hotspot.
  const hotspotLookup = useMemo(
    () => buildHotspotLookup(hotspots, chain),
    [hotspots, chain]
  );
  // Cadenas del receptor a mostrar: la cadena del docking + las cadenas
  // explícitas de los hotspots (el bolsillo de un dímero cruza ambas).
  const receptorChains = useMemo(() => {
    const set = new Set<string>();
    if (chain) set.add(chain.toUpperCase());
    hotspots.forEach((h) => {
      const parts = h.name.toUpperCase().split(":");
      if (parts.length === 2 && parts[0].trim()) set.add(parts[0].trim());
    });
    return set;
  }, [chain, hotspots]);
  const todosLosAtomos = useMemo(() => {
    if (!proteinData) return [];
    // Filtro por cadenas del receptor (docking + cadenas de hotspots): si no
    // producen átomos (PDB sin esas cadenas), degradar a todas las cadenas.
    const filtered = parsePdbAtoms(proteinData, hotspotLookup, receptorChains);
    return receptorChains.size > 0 && filtered.length === 0
      ? parsePdbAtoms(proteinData, hotspotLookup)
      : filtered;
  }, [proteinData, hotspotLookup, receptorChains]);
  const hotspotMarkers = useMemo(() => {
    // Prioridad 1: coordenadas REALES del catálogo (backend, mismo PDB y
    // cadena del receptor). Prioridad 2: derivar el CA del PDB (fallback).
    let parsed = proteinData ? parsePdbHotspots(proteinData, hotspots, receptorChains) : [];
    if (parsed.length === 0 && receptorChains.size > 0) parsed = proteinData ? parsePdbHotspots(proteinData, hotspots) : [];
    const byName = new Map(parsed.map((p) => [p.name.toUpperCase(), p]));
    const out: HotspotMarker[] = [];
    hotspots.forEach((h) => {
      const n = h.name.toUpperCase();
      if (h.x != null && h.y != null && h.z != null) {
        out.push({ x: h.x, y: h.y, z: h.z, name: h.name, importance: h.importance ?? 0.5 });
        return;
      }
      // Una cadena explícita forma parte de la identidad del residuo.
      // La anotación sin cadena sólo se acepta si hay una coincidencia única.
      const matches = n.includes(":") ? [] : parsed.filter((p) => p.name.split(":").pop()?.toUpperCase() === n);
      const f = n.includes(":") ? byName.get(n) : matches.length === 1 ? matches[0] : undefined;
      if (f) out.push({ x: f.x, y: f.y, z: f.z, name: h.name, importance: h.importance ?? f.importance ?? 0.5 });
    });
    return out;
  }, [proteinData, hotspots, receptorChains]);

  // Dónde mirar: la caja; sin ella, el sitio; sin sitio, el receptor entero.
  const centroDeInteres = useMemo((): [number, number, number] => {
    if (gridInfo) return [gridInfo.centerX, gridInfo.centerY, gridInfo.centerZ];
    const delSitio = todosLosAtomos.filter((a) => a.isHotspot);
    const base = delSitio.length > 0 ? delSitio : hotspotMarkers.length > 0 ? hotspotMarkers : todosLosAtomos;
    return base.length > 0 ? hotspotCentroid(base) : [0, 0, 0];
  }, [gridInfo, todosLosAtomos, hotspotMarkers]);
  const atoms = useMemo(() => recortarAlrededor(todosLosAtomos, centroDeInteres, MAX_ATOMS), [todosLosAtomos, centroDeInteres]);
  const recortado = atoms.length < todosLosAtomos.length;

  // Metales, cofactores y aguas. Las aguas sólo si son del receptor acoplado: las del depósito se retiran al preparar.
  const hetero = useMemo(
    () => (proteinData ? parsePdbHetero(proteinData, { conAguas: origenDelReceptor === "corrida" }) : { atomos: [] as AtomoHetero[], grupos: [] as GrupoHetero[] }),
    [proteinData, origenDelReceptor]
  );
  const metales = useMemo(() => hetero.grupos.filter((g) => g.tipo === "metal"), [hetero]);
  const otrosGrupos = useMemo(() => hetero.grupos.filter((g) => g.tipo === "grupo"), [hetero]);
  const aguas = useMemo(() => hetero.grupos.filter((g) => g.tipo === "agua"), [hetero]);

  // Residuos del sitio, por CADENA y número. Antes el color, la envolvente y la leyenda los identificaban sin cadena,
  // y en un homodímero los residuos homónimos de las dos cadenas compartían color y entrada.
  const residuosDelSitio = useMemo((): ResiduoDelSitio[] => {
    const importancia = new Map<string, number>();
    hotspots.forEach((h) => {
      const up = h.name.toUpperCase().trim();
      const partes = up.split(":");
      if (partes.length === 2 && partes[0].trim()) importancia.set(claveDeResiduo(partes[0].trim(), partes[1].trim()), h.importance ?? 0.5);
      else importancia.set(`*:${up}`, h.importance ?? 0.5);
    });
    const grupos = new Map<string, Atom[]>();
    for (const a of atoms) {
      if (!a.isHotspot || !a.resId) continue;
      const clave = claveDeResiduo(a.chain, a.resId);
      const lista = grupos.get(clave) ?? [];
      lista.push(a);
      grupos.set(clave, lista);
    }
    return [...grupos.entries()]
      .sort(([x], [y]) => x.localeCompare(y))
      .map(([clave, lista], i) => {
        const n = lista.length;
        const cx = lista.reduce((s2, a) => s2 + a.x, 0) / n;
        const cy = lista.reduce((s2, a) => s2 + a.y, 0) / n;
        const cz = lista.reduce((s2, a) => s2 + a.z, 0) / n;
        const radio = Math.max(...lista.map((a) => Math.hypot(a.x - cx, a.y - cy, a.z - cz) + atomRadius(a.element)));
        const [cadena, resId] = clave.split(":");
        return {
          clave,
          nombre: cadena ? `${cadena}:${resId}` : resId,
          color: RESIDUE_PALETTE[i % RESIDUE_PALETTE.length],
          importancia: importancia.get(clave) ?? importancia.get(`*:${resId}`) ?? 0.5,
          centro: [cx, cy, cz] as [number, number, number],
          radio,
          atomos: lista,
        };
      });
  }, [atoms, hotspots]);
  const hotspotColors = useMemo(() => new Map(residuosDelSitio.map((r) => [r.clave, r.color])), [residuosDelSitio]);
  // Átomos del sitio activo con color por TIPO de residuo (convención AA_INFO:
  // polar=azul, hidrofóbico=ámbar, aromático=púrpura, ácido=rojo, básico=verde)
  // — alimentan la superficie adaptativa del bolsillo.
  const pocketCloudAtoms = useMemo(() => residuosDelSitio.flatMap((r) => {
    const color = new THREE.Color(aaInfoFromName(r.nombre, t).typeColor ?? PALETA_DE_TIPO_POR_DEFECTO);
    return r.atomos.map((a) => ({ x: a.x, y: a.y, z: a.z, r: atomRadius(a.element), color }));
  }), [residuosDelSitio, t]);
  // Esfera-envolvente del bolsillo (ayuda de orientación): centroide ponderado
  // por importancia + radio que CONTIENE los átomos del sitio activo con un
  // pequeño margen visual. Envolvente, no superficie física.
  const pocketSphere = useMemo(() => {
    const pesos = residuosDelSitio.flatMap((r) => r.atomos.map((a) => ({ a, w: r.importancia > 0 ? r.importancia : 0.5 })));
    if (pesos.length < 2) return null;
    const wTotal = pesos.reduce((s2, p2) => s2 + p2.w, 0) || pesos.length;
    const cx = pesos.reduce((s2, p2) => s2 + p2.a.x * p2.w, 0) / wTotal;
    const cy = pesos.reduce((s2, p2) => s2 + p2.a.y * p2.w, 0) / wTotal;
    const cz = pesos.reduce((s2, p2) => s2 + p2.a.z * p2.w, 0) / wTotal;
    const radius = Math.max(...pesos.map(({ a }) => Math.hypot(a.x - cx, a.y - cy, a.z - cz) + atomRadius(a.element)));
    return { center: [cx, cy, cz] as [number, number, number], radius: radius + 1.0 };
  }, [residuosDelSitio]);
  const ligand = useMemo(
    () => (poseData ? parseSdfLigand(poseData) : { atoms: [] as LigandAtom[], bonds: [] as LigandBond[] }),
    [poseData]
  );

  const focusCenter = centroDeInteres;
  const focusDistance = gridInfo
    ? Math.max(60, Math.max(gridInfo.sizeX, gridInfo.sizeY, gridInfo.sizeZ) * 3)
    : 100;

  // "Ocultar receptor" oculta SOLO los átomos grises (no-hotspot).
  // Los átomos del sitio activo (hotspots) SIEMPRE quedan visibles.
  // NOTA: este useMemo va ANTES del return condicional (Rules of Hooks).
  const visibleAtoms = useMemo(
    () => (showAtoms ? atoms : atoms.filter((a) => a.isHotspot)),
    [atoms, showAtoms]
  );

  if (!proteinData || atoms.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-slate-600 text-xs font-mono uppercase tracking-widest bg-[#05080f]">
        {t("pn_sin_estructura")}
      </div>
    );
  }

  const selectedInfo = selectedHotspot ? aaInfoFromName(selectedHotspot.name, t) : null;
  const numero = (n: number) => n.toLocaleString(appLocale(locale));
  const hayHetero = hetero.atomos.length > 0 || aguas.length > 0;
  const tiposDelSitio = [...new Map(residuosDelSitio.map((r) => {
    const info = aaInfoFromName(r.nombre, t);
    return [info.typeCode, info] as const;
  })).values()];
  const entradasDeLeyenda = 1 + residuosDelSitio.length + metales.length + Math.min(otrosGrupos.length, GRUPOS_EN_LA_LEYENDA);
  const chip = "flex items-center gap-1.5 whitespace-nowrap";
  const origenDelHetero = t(origenDelReceptor === "corrida" ? "pn_w3d_hetero_corrida" : "pn_w3d_hetero_deposito");
  const opciones = [
    { activo: showAtoms, alternar: () => setShowAtoms((v) => !v), icono: <EyeOff size={12} className={showAtoms ? "text-amber-400" : "text-slate-500"} />,
      texto: showAtoms ? t("pr_viewer_hide_receptor") : t("pr_viewer_show_receptor"), titulo: showAtoms ? t("auto_7a2d6cf4994c") : t("auto_144067985189"), sinDatos: false },
    { activo: showMolecule, alternar: () => setShowMolecule((v) => !v), icono: <Atom size={12} className={showMolecule ? "text-sky-400" : "text-slate-500"} />,
      texto: showMolecule ? t("pr_viewer_hide_ligand") : t("pr_viewer_show_ligand"),
      titulo: ligand.atoms.length === 0 ? t("auto_abcb7f140cae") : showMolecule ? t("auto_b0487918dd42") : t("auto_e5d668feb775"), sinDatos: ligand.atoms.length === 0 },
    { activo: showInteractions, alternar: () => setShowInteractions((v) => !v), icono: <Zap size={12} className={showInteractions ? "text-yellow-400" : "text-slate-500"} />,
      texto: showInteractions ? t("pr_viewer_hide_interactions") : t("pr_viewer_show_interactions"),
      titulo: !interactions || interactions.length === 0 ? t("auto_fe9905aee429") : showInteractions ? t("auto_eef39378ea52") : t("auto_1054995e158b"), sinDatos: !interactions || interactions.length === 0 },
    { activo: showHetero, alternar: () => setShowHetero((v) => !v), icono: <Atom size={12} className={showHetero ? "text-amber-300" : "text-slate-500"} />,
      texto: t(showHetero ? "pn_w3d_ocultar_hetero" : "pn_w3d_ver_hetero"), titulo: origenDelHetero, sinDatos: !hayHetero },
  ];

  return (
    <div
      ref={raiz}
      data-pantalla-completa={pantalla.activa ? "" : undefined}
      className={pantalla.enVentana ? "fixed inset-0 z-[60] isolate overflow-hidden bg-[#05080f]" : "relative isolate h-full w-full overflow-hidden bg-[#05080f]"}
    >
      <Canvas
        camera={{ position: [focusCenter[0] + focusDistance * 0.8, focusCenter[1] + focusDistance * 0.6, focusCenter[2] + focusDistance], fov: 45 }}
        className="cursor-move"
        dpr={porSoftware ? 1 : [1, 1.5]}
        // El renderizador se crea AQUÍ, no dentro de la librería, para poder ver si
        // falla. R3F lo construye en una promesa: cuando three no consigue contexto
        // («Error creating WebGL context»), esa excepción no pasa por React, no la
        // recoge ninguna frontera y el visor se quedaba en un lienzo vacío sin
        // mensaje. Reproducido en el export (2026-11-09).
        gl={(porDefecto) => {
          try {
            return new THREE.WebGLRenderer({ ...porDefecto, antialias: !porSoftware } as THREE.WebGLRendererParameters);
          } catch (fallo) {
            // Fuera de esta pila: quien lo monta cambia de visor, y eso desmonta este lienzo.
            setTimeout(() => avisarNoDisponible.current?.(), 0);
            throw fallo;
          }
        }}
        // Sólo se dibuja cuando algo cambia. Con el bucle por defecto el visor
        // repintaba 60 veces por segundo una escena quieta.
        frameloop="demand"
      >
        <VigiaDelContexto onPerdido={onNoDisponible} />
        {/* Fondo y niebla del mismo color: lo lejano se apaga y la profundidad se lee sin girar la escena. */}
        <color attach="background" args={["#05080f"]} />
        <fog attach="fog" args={["#05080f", focusDistance * 0.6, focusDistance * 2.6]} />
        <hemisphereLight args={["#e0ecff", "#0b1020", 1.1]} />
        <ambientLight intensity={0.35} />
        <LuzDeCamara />
        {/* AtomCloud SIEMPRE montado; recibe solo hotspots cuando showAtoms=false
            (el receptor se oculta pero el sitio activo permanece). */}
        <AtomCloud atoms={visibleAtoms} hotspotColors={hotspotColors} />
        {showHetero && <HeteroCloud atomos={hetero.atomos} />}
        {/* Molécula acoplada (SDF): átomos + enlaces; toggle "Ver molécula" */}
        <LigandCloud atoms={showMolecule ? ligand.atoms : []} bonds={showMolecule ? ligand.bonds : []} />
        {/* Líneas discontinuas de interacción ligando-proteína (PLIF) */}
        {showInteractions && interactions && interactions.length > 0 && (
          <InteractionLines interactions={interactions} />
        )}
        {/* Superficie adaptativa del bolsillo: moldea el sitio activo */}
        <PocketSurface atoms={pocketCloudAtoms} />
        {/* Esfera-envolvente del bolsillo: ayuda de orientación que contiene
            el sitio activo (envolvente, no superficie física) */}
        {pocketSphere && (
          <FatWireSphere
            position={pocketSphere.center}
            radius={pocketSphere.radius}
            color="#a855f7"
            opacity={0.34}
            lineWidth={1.6}
          />
        )}
        {/* Esferas de CLICK sobre los residuos del sitio (casi invisibles, centradas en
            la envolvente del residuo para capturar toda su cadena lateral) */}
        {residuosDelSitio.map((r) => (
          <mesh
            key={r.clave}
            position={r.centro}
            onClick={(ev) => {
              ev.stopPropagation();
              setSelectedHotspot({ name: r.nombre, importance: r.importancia });
            }}
          >
            <sphereGeometry args={[r.radio + 0.6, 8, 8]} />
            {/* opacity 0.01 (no 0) para que el raycast de R3F lo capture */}
            <meshBasicMaterial transparent opacity={0.01} depthWrite={false} />
          </mesh>
        ))}
        {gridInfo && <GridBox gridInfo={gridInfo} />}
        <CameraRig center={focusCenter} distance={focusDistance} externalCamera={externalCamera} onCameraChange={onCameraChange} active={active} />
      </Canvas>

      {/* ── Esquina superior izquierda: cambio de visor y resumen ──
          El cambio de visor vivía abajo a la derecha, justo debajo de la burbuja de MolChat, que lo tapaba. */}
      <div className="absolute left-3 top-3 z-10 flex max-w-[calc(100%-1.5rem)] flex-col items-start gap-2">
        <div className="flex items-center gap-2">
          {onSwitchViewer && (
            <button onClick={onSwitchViewer} className={VIEWER_SWITCH_BUTTON_CLASS}>
              <Box size={12} className="text-emerald-400" />
              {t("pr_viewer_view")} {viewerLabel ?? "MolStar"}
            </button>
          )}
          <button
            onClick={() => alternarPanel("resumen")}
            aria-expanded={panel === "resumen"}
            className={`${VIEWER_LABEL_BUTTON_CLASS} justify-between`}
          >
            <span className="text-emerald-300">Web3D</span>
            <span className="font-mono normal-case tracking-normal text-slate-400">{numero(visibleAtoms.length)} {t("pn_atomos")}</span>
            <span className="text-slate-500">{panel === "resumen" ? "▾" : "▸"}</span>
          </button>
        </div>
        {panel === "resumen" && (
          <div className={`${VIEWER_LABEL_PANEL_CLASS} flex max-w-[360px] flex-col gap-1.5 px-3 py-2.5`}>
            <span className="text-[12px] font-mono text-slate-300">
              <span className="text-emerald-400 font-black">{numero(visibleAtoms.length)}</span> {t("pn_atomos")}
              <span className="text-slate-500"> {showAtoms ? t("auto_1e853721429d") : t("auto_2cdce3bc9ced")}</span>
            </span>
            {recortado && (
              <span role="status" className="text-[11px] leading-snug text-amber-300">
                {t("pn_w3d_recorte", { dibujados: numero(atoms.length), total: numero(todosLosAtomos.length) })}
              </span>
            )}
            <span className="text-[12px] font-mono text-cyan-300">
              <span className="font-black">{residuosDelSitio.length}</span> {t("pn_residuos_sitio")}
            </span>
            {hayHetero && (
              <span className="text-[11px] leading-snug text-slate-400">
                {t("pn_w3d_hetero_cuenta", { metales: metales.length, grupos: otrosGrupos.length, aguas: aguas.length })} {origenDelHetero}
              </span>
            )}
            <span className="text-[11px] font-mono text-slate-400">{t("pn_selecciona_residuo")}</span>
          </div>
        )}
      </div>

      {/* ── Esquina inferior izquierda: Leyenda (cerrada; panel hacia arriba) ── */}
      <div className="absolute bottom-3 left-3 z-10">
        <button
          onClick={() => alternarPanel("leyenda")}
          aria-expanded={panel === "leyenda"}
          className={`${VIEWER_LABEL_BUTTON_CLASS} min-w-[112px] justify-between`}
        >
          <span className="text-emerald-300">{t("pr_viewer_legend")}</span>
          <span className="font-mono text-slate-500">{entradasDeLeyenda}</span>
          <span className="text-slate-500">{panel === "leyenda" ? "▾" : "▸"}</span>
        </button>
        {/* La barra de desplazamiento existía, pero no se podía usar.
            EL FALLO: el panel combinaba `overflow-y-auto` con
            `pointer-events-none`. Con el puntero desactivado el gesto no lo
            recibe el panel sino lo que hay DEBAJO, que es el canvas: la rueda
            sobre la leyenda le hacía zoom a la cámara y arrastrar la barra
            rotaba la molécula, mientras la lista de residuos —que en un sitio
            activo grande no cabe en 55vh— se quedaba fija a media altura sin
            forma de leer el resto.

            `overscroll-contain`: al llegar al final, el gesto no se encadena al
            contenedor del visor.

            `stopPropagation` SIN `preventDefault`: corta la rueda para
            cualquier oyente de arriba (el zoom del visor), pero deja intacto el
            desplazamiento nativo del propio panel. Cancelarlo con
            `preventDefault` es el error clásico al arreglar esto — y además
            React registra `wheel` como pasivo, así que no haría nada salvo
            avisar por consola. */}
        {panel === "leyenda" && (
          <div
            onWheel={(e) => e.stopPropagation()}
            className={`${VIEWER_LABEL_PANEL_CLASS} pointer-events-auto absolute bottom-full left-0 mb-2 flex ${pantalla.activa ? "max-h-[70vh] w-[420px]" : "max-h-[42vh] w-[min(380px,calc(100vw-3rem))]"} flex-col gap-2 overflow-y-auto overscroll-contain px-3 py-2.5 text-[11px] font-semibold tracking-normal text-slate-300`}
          >
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              <span className={chip}><span className="h-2.5 w-2.5 rounded-sm bg-[#22d3ee] inline-block" /> {t("pn_caja_acoplamiento")}</span>
              {showMolecule && ligand.atoms.length > 0 && (
                <span className={chip}><span className="h-2.5 w-2.5 rounded-full bg-[#e6e6f2] inline-block" /> {t("pr_viewer_ligand_docked")}</span>
              )}
              {showAtoms && (
                <span className={chip}><span className="h-2.5 w-2.5 rounded-full inline-block" style={{ backgroundColor: REST_ATOM_COLOR }} /> {t(recortado ? "pn_w3d_receptor_recortado" : "pr_viewer_receptor_full")}</span>
              )}
            </div>
            {residuosDelSitio.length > 0 && (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(88px,1fr))] gap-x-2 gap-y-1">
                {residuosDelSitio.map((r) => (
                  <span key={r.clave} className={chip} title={formatResidueLabel(r.nombre, t)}>
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full inline-block" style={{ backgroundColor: r.color }} />
                    <span className="truncate font-mono">{r.nombre}</span>
                  </span>
                ))}
              </div>
            )}
            {/* Tipos de residuo presentes (color de la superficie del bolsillo) */}
            {tiposDelSitio.length > 0 && (
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                {tiposDelSitio.map((info) => (
                  <span key={info.typeCode} className={chip}>
                    <span className="h-2.5 w-2.5 rounded-sm inline-block" style={{ backgroundColor: info.typeColor ?? PALETA_DE_TIPO_POR_DEFECTO }} /> {info.type}
                  </span>
                ))}
              </div>
            )}
            {showHetero && hayHetero && (
              <div className="flex flex-col gap-1">
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {metales.map((g) => (
                    <span key={g.clave} className={chip}>
                      <span className="h-2.5 w-2.5 rounded-full inline-block" style={{ backgroundColor: COLOR_DE_METAL[g.residuo] ?? "#b8b8d0" }} />
                      <span className="font-mono">{g.cadena ? `${g.cadena}:` : ""}{g.residuo}{g.numero}</span>
                    </span>
                  ))}
                  {otrosGrupos.slice(0, GRUPOS_EN_LA_LEYENDA).map((g) => (
                    <span key={g.clave} className={chip}>
                      <span className="h-2.5 w-2.5 rounded-sm inline-block" style={{ backgroundColor: HETERO_ELEMENT_COLOR.C }} />
                      <span className="font-mono">{g.cadena ? `${g.cadena}:` : ""}{g.residuo}{g.numero}</span>
                    </span>
                  ))}
                  {otrosGrupos.length > GRUPOS_EN_LA_LEYENDA && (
                    <span className="text-slate-500">{t("pn_w3d_y_mas", { n: otrosGrupos.length - GRUPOS_EN_LA_LEYENDA })}</span>
                  )}
                  {aguas.length > 0 && origenDelReceptor === "corrida" && (
                    <span className={chip}><span className="h-2 w-2 rounded-full inline-block" style={{ backgroundColor: AGUA_COLOR }} /> {t("pn_w3d_aguas", { n: aguas.length })}</span>
                  )}
                </div>
                <span className="text-[10px] font-normal leading-snug text-slate-500">{origenDelHetero}</span>
              </div>
            )}
            {showInteractions && interactions && interactions.length > 0 && (
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                {[...new Set(interactions.map((i) => i.type))].map((interactionType) => (
                  <span key={interactionType} className={chip}>
                    <span className="h-2.5 w-2.5 rounded-sm inline-block" style={{ backgroundColor: INTERACTION_COLORS[interactionType] ?? "#94a3b8" }} />
                    {INTERACTION_LABELS[interactionType] ? t(INTERACTION_LABELS[interactionType]) : interactionType}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Esquina superior derecha: pantalla completa y visibilidad del receptor, ligando, interacciones y heteroátomos. */}
      <div className="absolute right-3 top-3 z-10 flex items-start gap-2">
        <button
          onClick={pantalla.alternar}
          aria-pressed={pantalla.activa}
          title={t(pantalla.activa ? "pn_w3d_salir_pantalla_completa" : "pn_w3d_pantalla_completa")}
          aria-label={t(pantalla.activa ? "pn_w3d_salir_pantalla_completa" : "pn_w3d_pantalla_completa")}
          className={`${VIEWER_LABEL_BUTTON_CLASS} px-2.5`}
        >
          {pantalla.activa ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
        </button>
        <div className="relative">
          <button
            onClick={() => setOptionsOpen((v) => !v)}
            className={`${VIEWER_LABEL_BUTTON_CLASS} min-w-[112px] justify-between`}
          >
            <span className="flex items-center gap-2 text-purple-300">
              <Settings size={12} />
              {t("ev_opciones")}
            </span>
            <span className="text-slate-500">{optionsOpen ? "▾" : "▸"}</span>
          </button>
          {optionsOpen && (
            <>
              {/* Backdrop: cerrar al hacer click fuera del panel */}
              <div className="fixed inset-0 z-10" onClick={() => setOptionsOpen(false)} />
              {/* z-20: el panel DEBE quedar sobre el backdrop, si no los clicks
                  de los switches golpean el backdrop y cierran sin togglear */}
              <div className={`${VIEWER_LABEL_PANEL_CLASS} absolute right-0 top-full z-20 mt-2 w-[232px] overflow-hidden`}>
                {opciones.map((op, i) => (
                  <button
                    key={i}
                    onClick={op.alternar}
                    disabled={op.sinDatos}
                    className="w-full flex items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-white/5 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                    title={op.titulo}
                  >
                    <span className="flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-slate-300">
                      {op.icono}
                      {op.texto}
                    </span>
                    <span className={`relative h-4 w-7 rounded-full transition-colors ${op.activo ? "bg-purple-500/60" : "bg-white/10"}`}>
                      <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white transition-transform ${op.activo ? "translate-x-3" : ""}`} />
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Popup de hotspot (ventana emergente explicativa) */}
      {selectedInfo && selectedHotspot && (
        <div className="absolute right-3 top-14 z-20 w-[280px] max-w-[calc(100%-1.5rem)] overflow-hidden rounded-xl border border-purple-500/30 bg-[#0d1220]/95 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-purple-500/10">
            <span className="text-[11px] font-black text-purple-200 uppercase tracking-wider font-mono">
              {formatResidueLabel(selectedHotspot.name, t)}
            </span>
            <button
              onClick={() => setSelectedHotspot(null)}
              className="text-slate-500 hover:text-white transition-colors cursor-pointer"
              title={t("c_cerrar")}
            >
              ✕
            </button>
          </div>
          <div className="p-3 space-y-2">
            <div className="flex items-center gap-2">
              <span
                className="text-[10px] font-black px-2 py-0.5 rounded-md uppercase tracking-wider"
                style={{ backgroundColor: `${selectedInfo.typeColor}22`, color: selectedInfo.typeColor, border: `1px solid ${selectedInfo.typeColor}44` }}
              >
                {selectedInfo.type}
              </span>
              <span className="text-[10px] font-mono text-slate-400">{selectedInfo.name}</span>
            </div>
            <p className="text-[10px] font-mono text-slate-300 leading-relaxed">
              {t(selectedInfo.desc)}
            </p>
            <div className="pt-1 border-t border-white/5 flex items-center justify-between text-[10px] font-mono">
              <span className="text-slate-500 uppercase tracking-wider">{t("pr_viewer_relative_importance")}</span>
              <span className={`font-black ${selectedHotspot.importance >= 0.8 ? "text-emerald-400" : selectedHotspot.importance >= 0.5 ? "text-amber-400" : "text-slate-400"}`}>
                {selectedHotspot.importance.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
