
import { useLanguage } from "@/context/LanguageContext";
/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V5 */
"use client";

// Visor Web3D ligero (react-three-fiber) — alternativa a MolStar.
// - Átomos con InstancedMesh (1 draw call → sin lag, soporta 50k+ átomos)
// - Grid box con cuadrículas (estilo grid de docking)
// - Sitio activo: hotspots como esferas púrpura + esfera del bolsillo

import { useEffect, useMemo, useRef, useState } from "react";
import { Box, EyeOff, Atom, Zap, Settings } from "lucide-react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { LineSegments2, LineSegmentsGeometry, LineMaterial, MarchingCubes } from "three-stdlib";
import type { InteractionDatum } from "../../../lib/types";
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
};

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
const REST_ATOM_COLOR = "#4a4a5a"; // gris apagado (resto del receptor)
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
  hbond: "H-bond", hydrophobic: "Hidrofóbico", pistacking: "π-stacking",
  saltbridge: "Puente salino", cationpi: "Catión-π", halogen: "Halógeno",
};
// La superficie del bolsillo se colorea por TIPO de residuo (convención
// AA_INFO: polar=azul, hidrofóbico=ámbar, aromático=púrpura, ácido=rojo,
// básico=verde, estructural=gris) — el color de la etiqueta que ya existe.
const MAX_ATOMS = 50000;

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

function parsePdbAtoms(pdb: string, lookup: Map<string, Set<string>>, chains?: Set<string>): Atom[] {
  const atoms: Atom[] = [];
  for (const line of pdb.split("\n")) {
    if (!line.startsWith("ATOM")) continue;
    const ch = line[21].trim().toUpperCase();
    if (chains && chains.size > 0 && !chains.has(ch)) continue;
    try {
      const x = parseFloat(line.slice(30, 38));
      const y = parseFloat(line.slice(38, 46));
      const z = parseFloat(line.slice(46, 54));
      if (isNaN(x) || isNaN(y) || isNaN(z)) continue;
      const element = (line.slice(76, 78).trim() || line.slice(12, 16).trim() || "C").toUpperCase();
      // ¿Este átomo pertenece a un residuo del sitio activo (hotspot)?
      const resName = line.slice(17, 20).trim().toUpperCase();
      const resSeq = line.slice(22, 26).trim();
      const rid = `${resName}${resSeq}`.toUpperCase();
      const isHotspot = lookup.get(ch)?.has(rid) || lookup.get("*")?.has(rid);
      atoms.push({ x, y, z, element, isHotspot: !!isHotspot, resId: rid, chain: ch });
      if (atoms.length >= MAX_ATOMS) break;
    } catch { /* skip */ }
  }
  return atoms;
}

type HotspotMarker = { x: number; y: number; z: number; name: string; importance: number };

function parsePdbHotspots(pdb: string, hotspots: Array<{ name: string; importance?: number }>, chains?: Set<string>): HotspotMarker[] {
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
    impByRid.set(rid, h.importance ?? 0.5);
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
    const resSeq = line.slice(22, 26).trim();
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
        importance: impByRid.get(rid) ?? 0.5,
      });
    } catch { /* skip */ }
  }
  return result;
}

// ── Información de aminoácidos para el popup de hotspots ───────────────

const AA_INFO: Record<string, { name: string; type: string; typeColor: string; desc: string }> = {
  ALA: { name: "Alanina", type: "Hidrofóbico", typeColor: "#fbbf24", desc: "Residuo pequeño, contribuye al empaquetamiento hidrofóbico del bolsillo." },
  VAL: { name: "Valina", type: "Hidrofóbico", typeColor: "#fbbf24", desc: "Cadena lateral ramificada; contactos de van der Waals con ligandos lipofílicos." },
  LEU: { name: "Leucina", type: "Hidrofóbico", typeColor: "#fbbf24", desc: "Contacto hidrofóbico frecuente en bolsillos de unión." },
  ILE: { name: "Isoleucina", type: "Hidrofóbico", typeColor: "#fbbf24", desc: "Hidrofóbico; define la forma del bolsillo." },
  MET: { name: "Metionina", type: "Hidrofóbico", typeColor: "#fbbf24", desc: "Azufre en la cadena lateral; puede hacer contactos S-π o S-H." },
  PHE: { name: "Fenilalanina", type: "Aromático", typeColor: "#a78bfa", desc: "Anillo aromático; interacciones π-stacking con ligandos aromáticos." },
  TRP: { name: "Triptófano", type: "Aromático", typeColor: "#a78bfa", desc: "Indol; π-stacking, cation-π y contactos hidrofóbicos fuertes." },
  TYR: { name: "Tirosina", type: "Aromático", typeColor: "#a78bfa", desc: "Fenol; π-stacking + H-bond donor/acceptor por el OH." },
  HIS: { name: "Histidina", type: "Aromático y polar", typeColor: "#a78bfa", desc: "Imidazol; coordina metales, pH-dependiente, H-bonds." },
  SER: { name: "Serina", type: "Polar", typeColor: "#60a5fa", desc: "OH reactivo; H-bonds, a veces nucleófilo catalítico." },
  THR: { name: "Treonina", type: "Polar", typeColor: "#60a5fa", desc: "OH; H-bonds, geometría restringida por el metilo." },
  ASN: { name: "Asparagina", type: "Polar", typeColor: "#60a5fa", desc: "Amida; donor y acceptor de H-bonds." },
  GLN: { name: "Glutamina", type: "Polar", typeColor: "#60a5fa", desc: "Amida más larga; donor y acceptor de H-bonds." },
  ASP: { name: "Aspartato", type: "Ácido", typeColor: "#f87171", desc: "Carboxilato (−); iónico/sal bridge, acceptor fuerte de H-bond." },
  GLU: { name: "Glutamato", type: "Ácido", typeColor: "#f87171", desc: "Carboxilato (−); sal bridge, reconocimiento de cationes." },
  LYS: { name: "Lisina", type: "Básico", typeColor: "#4ade80", desc: "Amino (+); sal bridge con ligandos ácidos, cation-π." },
  ARG: { name: "Arginina", type: "Básico", typeColor: "#4ade80", desc: "Guanidinio (+); sal bridge fuerte, reconocimiento de fosfatos." },
  CYS: { name: "Cisteína", type: "Polar y reactivo", typeColor: "#60a5fa", desc: "Tiol; puede formar enlaces covalentes con warheads electrofílicos." },
  PRO: { name: "Prolina", type: "Estructural", typeColor: "#94a3b8", desc: "Rígida; define giros, contribuye a la forma del sitio." },
  GLY: { name: "Glicina", type: "Estructural", typeColor: "#94a3b8", desc: "Sin cadena lateral; permite espacios estrechos en el bolsillo." },
};

function formatResidueLabel(name: string): string {
  const [first, second] = name.trim().toUpperCase().split(":");
  return second ? `${second} · cadena ${first}` : first;
}
function aaInfoFromName(name: string): { code: string; name: string; type: string; typeColor: string; desc: string } {
  // name viene como "LEU221" o "A:LEU221" → extraer el código de 3 letras
  const clean = name.toUpperCase().split(":").pop() ?? "";
  const code = clean.replace(/\d+/g, "").slice(0, 3);
  const info = AA_INFO[code] ?? { name: code, type: "Residuo", typeColor: "#94a3b8", desc: "Residuo del sitio activo." };
  return { code, ...info };
}

// ── Nube de átomos con InstancedMesh (sin lag) ─────────────────────────

function AtomCloud({ atoms, hotspotColors }: { atoms: Atom[]; hotspotColors: Map<string, string> }) {
  const ref = useRef<THREE.InstancedMesh>(null);

  // Matrices por átomo: posición + escala (radio covalente) + color.
  // SITIO ACTIVO: cada residuo hotspot con SU color (convención spectrum);
  // el resto del receptor gris uniforme apagado. El radio es FÍSICO
  // (covalente), idéntico para átomos del mismo elemento.
  const { matrices, colors } = useMemo(() => {
    const count = atoms.length;
    const matrices = new Float32Array(count * 16);
    const colors = new Float32Array(count * 3);
    const m = new THREE.Matrix4();
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const c = new THREE.Color();

    atoms.forEach((a, i) => {
      const color = a.isHotspot
        ? hotspotColors.get(a.resId ?? "") ?? HOTSPOT_ELEMENT_COLOR[a.element] ?? HOTSPOT_ELEMENT_COLOR.C
        : REST_ATOM_COLOR;
      const r = atomRadius(a.element);
      p.set(a.x, a.y, a.z);
      q.identity();
      s.set(r, r, r);
      m.compose(p, q, s);
      m.toArray(matrices, i * 16);
      c.set(color);
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    });
    return { matrices, colors };
  }, [atoms]);

  useEffect(() => {
    if (!ref.current) return;
    const mesh = ref.current;
    for (let i = 0; i < atoms.length; i++) {
      mesh.setMatrixAt(i, new THREE.Matrix4().fromArray(matrices, i * 16));
      mesh.setColorAt(i, new THREE.Color().setRGB(colors[i * 3], colors[i * 3 + 1], colors[i * 3 + 2]));
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [atoms, matrices, colors]);

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, atoms.length]} frustumCulled={false}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial />
    </instancedMesh>
  );
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

// Molécula en el canvas: átomos (InstancedMesh) + enlaces (fat lines).
function LigandCloud({ atoms, bonds }: { atoms: LigandAtom[]; bonds: LigandBond[] }) {
  const ref = useRef<THREE.InstancedMesh>(null);

  const { matrices, colors } = useMemo(() => {
    const count = atoms.length;
    const matrices = new Float32Array(count * 16);
    const colors = new Float32Array(count * 3);
    const m = new THREE.Matrix4();
    const p = new THREE.Vector3();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const c = new THREE.Color();

    atoms.forEach((a, i) => {
      const color = LIGAND_ELEMENT_COLOR[a.element] ?? LIGAND_ELEMENT_COLOR.C;
      const r = atomRadius(a.element);
      p.set(a.x, a.y, a.z);
      q.identity();
      s.set(r, r, r);
      m.compose(p, q, s);
      m.toArray(matrices, i * 16);
      c.set(color);
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    });
    return { matrices, colors };
  }, [atoms]);

  useEffect(() => {
    if (!ref.current) return;
    const mesh = ref.current;
    for (let i = 0; i < atoms.length; i++) {
      mesh.setMatrixAt(i, new THREE.Matrix4().fromArray(matrices, i * 16));
      mesh.setColorAt(i, new THREE.Color().setRGB(colors[i * 3], colors[i * 3 + 1], colors[i * 3 + 2]));
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [atoms, matrices, colors]);

  // Enlaces como fat lines (LineSegments2 — grosor real en px), con el orden
  // de enlace químico real (single/doble/triple).
  const bondGeo = useMemo(() => {
    const geo = new LineSegmentsGeometry();
    geo.setPositions(buildBondLines(atoms, bonds));
    return geo;
  }, [atoms, bonds]);

  const bondMat = useMemo(() => {
    return new LineMaterial({
      color: new THREE.Color(LIGAND_BOND_COLOR).getHex(),
      transparent: true,
      opacity: 0.65,
      linewidth: 2,
      depthWrite: false,
    });
  }, []);

  const { size } = useThree();
  useEffect(() => {
    bondMat.resolution.set(size.width, size.height);
  }, [size.width, size.height, bondMat]);

  const bondObj = useMemo(() => new LineSegments2(bondGeo, bondMat), [bondGeo, bondMat]);

  if (atoms.length === 0) return null;

  return (
    <group>
      <primitive object={bondObj} />
      <instancedMesh ref={ref} args={[undefined, undefined, atoms.length]} frustumCulled={false}>
        <sphereGeometry args={[1, 12, 12]} />
        <meshBasicMaterial />
      </instancedMesh>
    </group>
  );
}

// ── Grid box con cuadrículas (estilo grid de docking) ─────────────────

function GridBox({ gridInfo }: { gridInfo: NonNullable<Props["gridInfo"]> }) {
  const { centerX, centerY, centerZ, sizeX, sizeY, sizeZ } = gridInfo;

  // Líneas del cubo: bordes + cuadrícula 3D (estilo grid de docking)
  // Genera líneas paralelas a X, Y y Z a través del volumen del cubo.
  const lines = useMemo(() => {
    const pts: number[] = [];
    const hx = sizeX / 2, hy = sizeY / 2, hz = sizeZ / 2;
    const cx = centerX, cy = centerY, cz = centerZ;
    const divisions = 8; // 8 divisiones por eje → 9 planos

    // Helper: push de un segmento
    const seg = (a: number[], b: number[]) => { pts.push(...a, ...b); };

    // ── Bordes del cubo (12 aristas) ──
    const v = [
      [cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz],
      [cx + hx, cy + hy, cz - hz], [cx - hx, cy + hy, cz - hz],
      [cx - hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz + hz],
      [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz],
    ];
    const edges = [
      [0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7],
    ];
    edges.forEach(([a, b]) => seg(v[a], v[b]));

    // ── Cuadrícula: líneas paralelas a X ──
    // Planos YZ fijos, barrer en Y y Z
    for (let i = 1; i < divisions; i++) {
      const offY = -hy + sizeY * (i / divisions);
      const offZ = -hz + sizeZ * (i / divisions);
      // Líneas paralelas a X en un plano Y fijo (barriendo Z)
      seg([cx - hx, cy + offY, cz - hz], [cx + hx, cy + offY, cz - hz]);
      seg([cx - hx, cy + offY, cz + hz], [cx + hx, cy + offY, cz + hz]);
      // Líneas paralelas a X en un plano Z fijo (barriendo Y)
      seg([cx - hx, cy - hy, cz + offZ], [cx + hx, cy - hy, cz + offZ]);
      seg([cx - hx, cy + hy, cz + offZ], [cx + hx, cy + hy, cz + offZ]);
    }
    // ── Cuadrícula: líneas paralelas a Y ──
    for (let i = 1; i < divisions; i++) {
      const offX = -hx + sizeX * (i / divisions);
      const offZ = -hz + sizeZ * (i / divisions);
      seg([cx + offX, cy - hy, cz - hz], [cx + offX, cy + hy, cz - hz]);
      seg([cx + offX, cy - hy, cz + hz], [cx + offX, cy + hy, cz + hz]);
      seg([cx - hx, cy - hy, cz + offZ], [cx - hx, cy + hy, cz + offZ]);
      seg([cx + hx, cy - hy, cz + offZ], [cx + hx, cy + hy, cz + offZ]);
    }
    // ── Cuadrícula: líneas paralelas a Z ──
    for (let i = 1; i < divisions; i++) {
      const offX = -hx + sizeX * (i / divisions);
      const offY = -hy + sizeY * (i / divisions);
      seg([cx + offX, cy - hy, cz - hz], [cx + offX, cy - hy, cz + hz]);
      seg([cx + offX, cy + hy, cz - hz], [cx + offX, cy + hy, cz + hz]);
      seg([cx - hx, cy + offY, cz - hz], [cx - hx, cy + offY, cz + hz]);
      seg([cx + hx, cy + offY, cz - hz], [cx + hx, cy + offY, cz + hz]);
    }

    return new Float32Array(pts);
  }, [centerX, centerY, centerZ, sizeX, sizeY, sizeZ]);

  const lineGeo = useMemo(() => {
    const geo = new LineSegmentsGeometry();
    geo.setPositions(Array.from(lines));
    return geo;
  }, [lines]);

  const lineMat = useMemo(() => {
    return new LineMaterial({
      color: new THREE.Color("#22d3ee").getHex(),
      transparent: true,
      opacity: 0.85,
      linewidth: 2, // grosor real en px (fat lines)
      depthWrite: false,
    });
  }, []);

  // CRÍTICO: LineMaterial necesita la resolución del canvas para calcular el
  // grosor en píxeles. Sin esto, linewidth se ve mal o las líneas no aparecen.
  const { size } = useThree();
  useEffect(() => {
    lineMat.resolution.set(size.width, size.height);
  }, [size.width, size.height, lineMat]);

  // Instancia única memoizada (no recrear en cada render)
  const linesObj = useMemo(() => new LineSegments2(lineGeo, lineMat), [lineGeo, lineMat]);

  return (
    <group>
      {/* Caras semitransparentes — cian (contrasta con púrpura de hotspots) */}
      <mesh position={[centerX, centerY, centerZ]}>
        <boxGeometry args={[sizeX, sizeY, sizeZ]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.04} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      {/* Cuadrícula completa — cian brillante, líneas GRUESAS */}
      <primitive object={linesObj} />
      {/* Centro del bolsillo */}
      <mesh position={[centerX, centerY, centerZ]}>
        <sphereGeometry args={[0.8, 16, 16]} />
        <meshBasicMaterial color="#a5f3fc" />
      </mesh>
      {/* Punto central + etiqueta de coordenadas flotante */}
      <GridLabel position={[centerX, centerY + sizeY / 2 + 2, centerZ]} text={`C: ${centerX.toFixed(1)}, ${centerY.toFixed(1)}, ${centerZ.toFixed(1)}`} />
    </group>
  );
}

// Etiqueta de coordenadas flotante (textura memoizada por texto)
function GridLabel({ position, text }: { position: [number, number, number]; text: string }) {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 64;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "rgba(8,20,30,0.9)";  // fondo más oscuro para que el cian resalte
    ctx.fillRect(0, 0, 512, 64);
    ctx.strokeStyle = "rgba(34,211,238,0.5)";
    ctx.strokeRect(1, 1, 510, 62);
    ctx.fillStyle = "#a5f3fc";  // cian claro
    ctx.font = "bold 28px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 256, 32);
    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    return tex;
  }, [text]);

  return (
    <sprite position={position}>
      <spriteMaterial map={texture} transparent depthTest={false} />
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
    const segments = 24; // resolución del círculo
    const rings = 10;    // nº de paralelos
    const meridians = 12;

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
  const { size } = useThree();
  useEffect(() => {
    material.resolution.set(size.width, size.height);
  }, [size.width, size.height, material]);

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

    const material = new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.3,
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
  const { size } = useThree();
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

  useEffect(() => {
    items.forEach((it) => {
      (it.obj.material as LineMaterial).resolution.set(size.width, size.height);
    });
  }, [size.width, size.height, items]);

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
  const { camera } = useThree();
  const controlsRef = useRef<any>(null);
  const lastKey = useRef("");
  const lastExternal = useRef("");

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
  });

  // Reportar cambios de cámara del usuario (rotación/zoom/pan) con debounce
  const lastReport = useRef(0);
  useFrame(() => {
    const now = performance.now();
    if (now - lastReport.current < 300) return; // reportar cada 300ms máx
    if (!onCameraChange || !controlsRef.current) return;
    if (!active) return; // visor oculto → no reportar (no pisa al activo)
    lastReport.current = now;
    const t = controlsRef.current.target;
    const pos = camera.position;
    onCameraChange({
      position: [pos.x, pos.y, pos.z],
      target: [t.x, t.y, t.z],
      distance: pos.distanceTo(t),
    });
  });

  return <OrbitControls ref={controlsRef} enableZoom enablePan makeDefault />;
}

// ── Componente principal ────────────────────────────────────────────────

export default function Web3DViewer({ proteinData, poseData, interactions, hotspots = [], chain, gridInfo, onSwitchViewer, viewerLabel, onCameraChange, externalCamera, active = true }: Props) {
  const { t } = useLanguage();
  // Modo foco: ocultar los átomos grises del receptor (solo sitio activo + grid)
  const [showAtoms, setShowAtoms] = useState(true);
  // Visibilidad de la molécula (ligando acoplado, SDF)
  const [showMolecule, setShowMolecule] = useState(true);
  // Visibilidad de las líneas de interacción (H-bonds, hidrofóbicos...)
  const [showInteractions, setShowInteractions] = useState(true);
  // HUD colapsable (header siempre visible, detalle colapsado)
  const [hudOpen, setHudOpen] = useState(true);
  // Leyenda colapsable (como el HUD)
  const [legendOpen, setLegendOpen] = useState(true);
  // Panel OPCIONES (visibilidad receptor / molécula / interacciones)
  const [optionsOpen, setOptionsOpen] = useState(false);
  // Hotspot seleccionado (popup explicativo)
  const [selectedHotspot, setSelectedHotspot] = useState<{ name: string; importance: number } | null>(null);

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
  const atoms = useMemo(() => {
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
    const byName = new Map(parsed.map((p) => [p.name.toUpperCase().split(":").pop() ?? "", p]));
    const out: HotspotMarker[] = [];
    hotspots.forEach((h) => {
      const n = h.name.toUpperCase();
      if (h.x != null && h.y != null && h.z != null) {
        out.push({ x: h.x, y: h.y, z: h.z, name: h.name, importance: h.importance ?? 0.5 });
        return;
      }
      const f = byName.get(n.split(":").pop() ?? "");
      if (f) out.push({ x: f.x, y: f.y, z: f.z, name: h.name, importance: h.importance ?? f.importance ?? 0.5 });
    });
    return out;
  }, [proteinData, hotspots, chain]);
  // Envolventes por residuo (para centrar las esferas de click).
  const residueEnvelopes = useMemo(
    () => buildResidueEnvelopes(atoms, hotspotMarkers),
    [atoms, hotspotMarkers]
  );
  // Color por residuo hotspot: paleta estable (orden alfabético) para
  // distinguir cada residuo sin etiquetas (convención spectrum de PyMOL).
  const hotspotColors = useMemo(() => {
    const map = new Map<string, string>();
    [...hotspotMarkers]
      .sort((a, b) => a.name.localeCompare(b.name))
      .forEach((h, i) => {
        const clean = h.name.toUpperCase().split(":").pop() ?? "";
        map.set(clean, RESIDUE_PALETTE[i % RESIDUE_PALETTE.length]);
      });
    return map;
  }, [hotspotMarkers]);
  // Átomos del sitio activo con color por TIPO de residuo (convención AA_INFO:
  // polar=azul, hidrofóbico=ámbar, aromático=púrpura, ácido=rojo, básico=verde)
  // — alimentan la superficie adaptativa del bolsillo.
  const pocketCloudAtoms = useMemo(() => {
    const colorByKey = new Map<string, string>();
    hotspotMarkers.forEach((h) => {
      const upper = h.name.toUpperCase();
      const parts = upper.split(":");
      const rid = (parts.length === 2 ? parts[1] : upper);
      const ch = parts.length === 2 ? parts[0] : "";
      const color = aaInfoFromName(h.name).typeColor;
      colorByKey.set(`${ch}:${rid}`, color);
      colorByKey.set(rid, color);
    });
    return atoms
      .filter((a) => a.isHotspot && a.resId)
      .map((a) => ({
        x: a.x, y: a.y, z: a.z, r: atomRadius(a.element),
        color: new THREE.Color(
          colorByKey.get(`${a.chain ?? ""}:${a.resId!}`) ?? colorByKey.get(a.resId!) ?? "#c084fc"
        ),
      }));
  }, [atoms, hotspotMarkers]);
  // Esfera-envolvente del bolsillo (ayuda de orientación, de vuelta): centroide
  // ponderado por importancia + radio que CONTIENE los átomos del sitio activo
  // con un pequeño margen visual. Envolvente, no superficie física.
  const pocketSphere = useMemo(() => {
    const hs = atoms.filter((a) => a.isHotspot && a.resId);
    if (hs.length < 2) return null;
    const impByRes = new Map(
      hotspotMarkers.map((h) => {
        const clean = h.name.toUpperCase().split(":").pop() ?? "";
        return [clean, h.importance > 0 ? h.importance : 0.5] as const;
      })
    );
    const wTotal = hs.reduce((s, a) => s + (impByRes.get(a.resId!) ?? 0.5), 0) || hs.length;
    const cx = hs.reduce((s, a) => s + a.x * (impByRes.get(a.resId!) ?? 0.5), 0) / wTotal;
    const cy = hs.reduce((s, a) => s + a.y * (impByRes.get(a.resId!) ?? 0.5), 0) / wTotal;
    const cz = hs.reduce((s, a) => s + a.z * (impByRes.get(a.resId!) ?? 0.5), 0) / wTotal;
    const radius = Math.max(...hs.map((a) => Math.hypot(a.x - cx, a.y - cy, a.z - cz) + atomRadius(a.element)));
    return { center: [cx, cy, cz] as [number, number, number], radius: radius + 1.0 };
  }, [atoms, hotspotMarkers]);
  const ligand = useMemo(
    () => (poseData ? parseSdfLigand(poseData) : { atoms: [] as LigandAtom[], bonds: [] as LigandBond[] }),
    [poseData]
  );

  const focusCenter: [number, number, number] = gridInfo
    ? [gridInfo.centerX, gridInfo.centerY, gridInfo.centerZ]
    : hotspotMarkers.length > 0
      ? hotspotCentroid(hotspotMarkers)
      : [0, 0, 0];
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

  const selectedInfo = selectedHotspot ? aaInfoFromName(selectedHotspot.name) : null;

  return (
    <div className="relative isolate h-full w-full overflow-hidden bg-[#05080f]">
      <Canvas
        camera={{ position: [focusCenter[0] + focusDistance * 0.8, focusCenter[1] + focusDistance * 0.6, focusCenter[2] + focusDistance], fov: 45 }}
        className="cursor-move"
        dpr={[1, 1.5]}
      >
        <ambientLight intensity={0.6} />
        <pointLight position={[focusCenter[0] + 100, focusCenter[1] + 100, focusCenter[2] + 100]} intensity={0.8} />
        {/* AtomCloud SIEMPRE montado; recibe solo hotspots cuando showAtoms=false
            (el receptor se oculta pero el sitio activo permanece). */}
        <AtomCloud atoms={visibleAtoms} hotspotColors={hotspotColors} />
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
            opacity={0.5}
            lineWidth={2.5}
          />
        )}
        {/* Esferas de CLICK sobre los hotspots (casi invisibles, centradas en
            la envolvente del residuo para capturar toda su cadena lateral) */}
        {hotspotMarkers.map((h, i) => {
          const clean = h.name.toUpperCase().split(":").pop() ?? "";
          const e = residueEnvelopes.get(clean);
          const pos: [number, number, number] = e ? [e.cx, e.cy, e.cz] : [h.x, h.y, h.z];
          const clickR = e ? e.radius + 0.6 : 2.2;
          return (
            <mesh
              key={i}
              position={pos}
              onClick={(ev) => {
                ev.stopPropagation();
                setSelectedHotspot({ name: h.name, importance: h.importance });
              }}
            >
              <sphereGeometry args={[clickR, 8, 8]} />
              {/* opacity 0.01 (no 0) para que el raycast de R3F lo capture */}
              <meshBasicMaterial transparent opacity={0.01} depthWrite={false} />
            </mesh>
          );
        })}
        {gridInfo && <GridBox gridInfo={gridInfo} />}
        <CameraRig center={focusCenter} distance={focusDistance} externalCamera={externalCamera} onCameraChange={onCameraChange} active={active} />
      </Canvas>

      {/* ── Esquina TL: HUD Web3D (colapsable) ── */}
      <div className="absolute left-3 top-3 z-10">
        <button
          onClick={() => setHudOpen((v) => !v)}
          className={`${VIEWER_LABEL_BUTTON_CLASS} min-w-[112px] justify-between`}
        >
          <span className="text-emerald-300">Web3D</span>
          <span className="text-slate-500">{hudOpen ? "▾" : "▸"}</span>
        </button>
        {hudOpen && (
          <div className={`${VIEWER_LABEL_PANEL_CLASS} mt-2 flex max-w-[340px] flex-col gap-1.5 px-3 py-2.5`}>
            <span className="text-[12px] font-mono text-slate-300">
              <span className="text-emerald-400 font-black">{visibleAtoms.length.toLocaleString()}</span> {t("pn_atomos")}
              <span className="text-slate-500"> {showAtoms ? t("auto_1e853721429d") : t("auto_2cdce3bc9ced")}</span>
            </span>
            <span className="text-[12px] font-mono text-cyan-300">
              <span className="font-black">{hotspotMarkers.length}</span> {t("pn_residuos_sitio")}
            </span>
            <span className="text-[11px] font-mono text-slate-400">{t("pn_selecciona_residuo")}</span>
          </div>
        )}
      </div>

      {/* ── Esquina BL: Leyenda (colapsable, panel hacia arriba) ── */}
      <div className="absolute bottom-3 left-3 z-10">
        <button
          onClick={() => setLegendOpen((v) => !v)}
          className={`${VIEWER_LABEL_BUTTON_CLASS} min-w-[112px] justify-between`}
        >
          <span className="text-emerald-300">Leyenda</span>
          <span className="text-slate-500">{legendOpen ? "▾" : "▸"}</span>
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
        {legendOpen && (
          <div
            onWheel={(e) => e.stopPropagation()}
            className={`${VIEWER_LABEL_PANEL_CLASS} pointer-events-auto absolute bottom-full left-0 mb-2 flex max-h-[55vh] max-w-[380px] flex-wrap items-center gap-x-3 gap-y-1.5 overflow-y-auto overscroll-contain px-3 py-2.5 text-[11px] font-semibold tracking-normal text-slate-300`}
          >
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-[#22d3ee] inline-block" /> {t("pn_caja_acoplamiento")}</span>
            {hotspotMarkers.map((h) => {
              const clean = h.name.toUpperCase().split(":").pop() ?? "";
              const c = hotspotColors.get(clean) ?? "#7dd3fc";
              return (
                <span key={clean} className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full inline-block" style={{ backgroundColor: c }} /> {formatResidueLabel(h.name)}
                </span>
              );
            })}
            {/* Tipos de residuo presentes (color de la superficie del bolsillo) */}
            {hotspotMarkers.length > 0 && (
              [...new Set(hotspotMarkers.map((h) => aaInfoFromName(h.name).type))].map((t) => {
                const info = hotspotMarkers.map((h) => aaInfoFromName(h.name)).find((i) => i.type === t);
                return (
                  <span key={t} className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-sm inline-block" style={{ backgroundColor: info?.typeColor ?? "#c084fc" }} /> {t}
                  </span>
                );
              })
            )}
            {showAtoms && <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[#4a4a5a] inline-block" /> Receptor completo</span>}
            {showMolecule && ligand.atoms.length > 0 && (
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-[#e6e6f2] inline-block" /> Ligando acoplado</span>
            )}
            {showInteractions && interactions && interactions.length > 0 && (
              [...new Set(interactions.map((i) => i.type))].map((interactionType) => (
                <span key={interactionType} className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm inline-block" style={{ backgroundColor: INTERACTION_COLORS[interactionType] ?? "#94a3b8" }} />
                  {INTERACTION_LABELS[interactionType] ? t(INTERACTION_LABELS[interactionType]) : interactionType}
                </span>
              ))
            )}
          </div>
        )}
      </div>

      {/* Esquina inferior derecha: cambio de visor, idéntico en ambos motores. */}
      {onSwitchViewer && (
        <div className="absolute bottom-3 right-3 z-10">
          <button onClick={onSwitchViewer} className={VIEWER_SWITCH_BUTTON_CLASS}>
            <Box size={12} className="text-emerald-400" />
            Ver {viewerLabel ?? "MolStar"}
          </button>
        </div>
      )}

      {/* Esquina superior derecha: visibilidad del receptor, ligando e interacciones. */}
      <div className="absolute right-3 top-3 z-10">
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
              <button
                onClick={() => setShowAtoms((v) => !v)}
                className="w-full flex items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-white/5 transition-colors cursor-pointer"
                title={showAtoms ? t("auto_7a2d6cf4994c") : t("auto_144067985189")}
              >
                <span className="flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-slate-300">
                  <EyeOff size={12} className={showAtoms ? "text-amber-400" : "text-slate-500"} />
                  {showAtoms ? "Ocultar receptor" : "Mostrar receptor"}
                </span>
                <span className={`relative h-4 w-7 rounded-full transition-colors ${showAtoms ? "bg-purple-500/60" : "bg-white/10"}`}>
                  <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white transition-transform ${showAtoms ? "translate-x-3" : ""}`} />
                </span>
              </button>
              <button
                onClick={() => setShowMolecule((v) => !v)}
                disabled={ligand.atoms.length === 0}
                className="w-full flex items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-white/5 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                title={
                  ligand.atoms.length === 0
                    ? t("auto_abcb7f140cae")
                    : showMolecule
                    ? t("auto_b0487918dd42")
                    : t("auto_e5d668feb775")
                }
              >
                <span className="flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-slate-300">
                  <Atom size={12} className={showMolecule ? "text-sky-400" : "text-slate-500"} />
                  {showMolecule ? "Ocultar ligando" : "Mostrar ligando"}
                </span>
                <span className={`relative h-4 w-7 rounded-full transition-colors ${showMolecule ? "bg-purple-500/60" : "bg-white/10"}`}>
                  <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white transition-transform ${showMolecule ? "translate-x-3" : ""}`} />
                </span>
              </button>
              <button
                onClick={() => setShowInteractions((v) => !v)}
                disabled={!interactions || interactions.length === 0}
                className="w-full flex items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-white/5 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                title={
                  !interactions || interactions.length === 0
                    ? t("auto_fe9905aee429")
                    : showInteractions
                    ? t("auto_eef39378ea52")
                    : t("auto_1054995e158b")
                }
              >
                <span className="flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-slate-300">
                  <Zap size={12} className={showInteractions ? "text-yellow-400" : "text-slate-500"} />
                  {showInteractions ? "Ocultar interacciones" : "Ver interacciones"}
                </span>
                <span className={`relative h-4 w-7 rounded-full transition-colors ${showInteractions ? "bg-purple-500/60" : "bg-white/10"}`}>
                  <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white transition-transform ${showInteractions ? "translate-x-3" : ""}`} />
                </span>
              </button>
            </div>
          </>
        )}
      </div>

      {/* Popup de hotspot (ventana emergente explicativa) */}
      {selectedInfo && selectedHotspot && (
        <div className="absolute right-3 top-14 z-20 w-[280px] max-w-[calc(100%-1.5rem)] overflow-hidden rounded-xl border border-purple-500/30 bg-[#0d1220]/95 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-purple-500/10">
            <span className="text-[11px] font-black text-purple-200 uppercase tracking-wider font-mono">
              {formatResidueLabel(selectedHotspot.name)}
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
              <span className="text-slate-500 uppercase tracking-wider">Importancia relativa</span>
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
