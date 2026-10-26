/**
 * Elevación 2D → 3D: el dibujo plano de una molécula «se levanta» y gira.
 *
 * El backend (`backend/chem/elevacion.py`) entrega, para cada átomo pesado, su
 * posición en la miniatura 2D (`plano`) y su posición 3D ya alineada con ese
 * dibujo por una rotación propia (`xyz`). Aquí sólo se interpola entre las dos
 * y se pinta en SVG. No hay WebGL: una rejilla de Moldex con un contexto WebGL
 * por ficha agotaría los del navegador, y un SVG no ocupa ninguno.
 *
 * La idea de la interpolación átomo por átomo viene del visor de MolTalk
 * (Dominic Fico, MIT; ver `third_party/moltalk/`). El código es propio.
 *
 * TRES FUENTES QUE NO SE CONFUNDEN. `pose_vina_top1` es la geometría de la
 * corrida (Moldex); `conformador_calculado` es un ETKDG del editor;
 * `especie_acoplada` es lo que la corrida prepararía antes de acoplar (editor,
 * vista «Se acoplará»). El visor dice cuál enseña.
 */

import { getAuthHeaders } from "./api";
import { fetchBackend } from "./backendFetch";

export type FuenteElevacion = "pose_vina_top1" | "conformador_calculado" | "especie_acoplada";

/** Qué enseña el visor del editor: la molécula escrita o la que prepararía la corrida. */
export type VistaDelEditor = "escrita" | "acoplada";

/** Los parámetros de preparación de la corrida que se va a lanzar. */
export interface PreparacionDeLaCorrida {
  ph: number;
  tautomero: "canonico" | "entrada";
}

export interface AtomoElevacion {
  elemento: string;
  carga: number;
  hidrogenos: number;
  /** Posición en la miniatura, px del lienzo (y hacia abajo). */
  plano: [number, number];
  /** Posición 3D alineada con el dibujo, px del lienzo (y hacia abajo, z hacia quien mira). */
  xyz: [number, number, number];
}

export interface EnlaceElevacion {
  a: number;
  b: number;
  orden: 1 | 2 | 3;
}

/** Lo que la pose declara frente al SMILES guardado. */
export interface EstereoDePose {
  /** Centros tetraédricos que el SMILES declara con configuración. */
  declarados: number;
  conservados: number;
  invertidos: { atomo: number; smiles: string; pose: string }[];
  /** Centros declarados que la geometría de la pose no permite asignar. */
  no_asignables: number[];
  /** Centros que el SMILES no declara: la pose les fija una configuración. */
  sin_declarar: number[];
  /** Dobles enlaces con E/Z declarado en el SMILES. */
  dobles_declarados?: number;
  dobles_invertidos?: { enlace: [number, number]; smiles: "E" | "Z"; pose: "E" | "Z" }[];
}

/** Veredicto físico (PoseBusters) que la corrida guardó para su pose top-1. Se lee, no se recalcula. */
export interface ValidezFisica {
  status: "passed" | "failed" | "review" | "not_evaluated" | string | null;
  label: string | null;
  motor: string | null;
  comprobaciones_que_fallan: string[];
}

/** Un hallazgo de los detectores del producto, con los átomos del modelo. */
export interface Detector {
  tipo: "ojiva" | "pains" | "especie_en_revision";
  codigo: string;
  nombre: string;
  atomos: number[];
}

/** Lo que la geometría implica para Vina. */
export interface GeometriaDelModelo {
  espesor_A: number | null;
  plana: boolean;
  /** Anillos de 7 a 33 átomos: Meeko los abre para que Vina explore su forma. */
  macrociclos: number[];
  anillos_rigidos_grandes: number[];
}

export interface EspecieDePose {
  carga_smiles: number;
  /** Carga neta de lo que Vina acopló (puede estar protonado). */
  carga_acoplada: number;
}

export interface PoseDeLaCorrida {
  registro: number;
  afinidad_kcal_mol: number | null;
  sdf_sha256: string;
  task_id: string | null;
  estereo?: EstereoDePose;
  especie?: EspecieDePose;
  /** Fragmentos del SMILES guardado (SMILES canónico) que no se acoplaron, como el contraión de una sal: no se levantan. */
  contraiones?: string[];
  validez_fisica?: ValidezFisica | null;
}

/** Lo que la preparación de la corrida cambia de la molécula escrita. */
export interface EspecieAcoplada {
  /** SMILES de la especie que entraría en Vina. */
  smiles: string;
  ph: number | null;
  aviso_de_ph: string | null;
  protonacion: { aplicada: boolean | null; motor: string | null; alternativas: number | null; motivo: string | null };
  tautomero: { modo: "canonico" | "entrada" | null; aplicada: boolean | null; alternativas: number | null; motivo: string | null };
  conformador: { semilla: number | null; campo_de_fuerza: string | null; convergio: boolean | null };
  sdf_sha256: string | null;
  cambios: {
    atomos: { atomo: number; carga: [number, number]; hidrogenos: [number, number] }[];
    /** Órdenes con el aromático como 1,5. */
    enlaces: { a: number; b: number; orden: [number, number] }[];
  };
  estereo: EstereoDePose;
  contraiones: string[];
}

export interface ModeloElevacion {
  contrato: "elevacion/v1";
  fuente: FuenteElevacion;
  lienzo: number;
  svg: string;
  atomos: AtomoElevacion[];
  enlaces: EnlaceElevacion[];
  desajuste_px: number;
  /** Longitud media de enlace del dibujo, px del lienzo. Null si no hay enlaces. */
  enlace_px: number | null;
  /** Desajuste mediano frente a un enlace: se abstiene si pasa de 1. Null sin enlaces. */
  razon_enlaces: number | null;
  /** Falso si el dibujo no se puede levantar: el visor no lo presenta como levantamiento. */
  fiel: boolean;
  /** Verdadero con una sola semilla (petición rápida): la decisión de `fiel` puede cambiar. */
  abstencion_provisional?: boolean;
  /** De qué dibujo parte: el de Ketcher o el de RDKit (con el motivo si se descartó el de Ketcher). */
  dibujo?: { fuente: "ketcher" | "rdkit"; motivo: string | null };
  geometria?: GeometriaDelModelo;
  detectores?: Detector[];
  pose?: PoseDeLaCorrida;
  conformador?: {
    metodo: string;
    campo_de_fuerza: string;
    semillas: number[];
    candidatos_por_semilla: number;
    /** Energía del elegido sobre el más bajo encontrado (campo de fuerza, fase gas). */
    delta_e_kcal_mol?: number | null;
  };
  especie_acoplada?: EspecieAcoplada;
}

// ── Álgebra mínima ────────────────────────────────────────────────────────────

export type Matriz = readonly [readonly [number, number, number], readonly [number, number, number], readonly [number, number, number]];

export const IDENTIDAD: Matriz = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

export function multiplicar(a: Matriz, b: Matriz): Matriz {
  const fila = (i: number) =>
    [0, 1, 2].map((j) => a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]) as unknown as readonly [number, number, number];
  return [fila(0), fila(1), fila(2)];
}

/** Giro alrededor del eje vertical de la pantalla: arrastrar a la derecha lleva el frente a la derecha. */
export function rotY(angulo: number): Matriz {
  const c = Math.cos(angulo), s = Math.sin(angulo);
  return [[c, 0, s], [0, 1, 0], [-s, 0, c]];
}

/** Giro alrededor del eje horizontal: arrastrar hacia abajo lleva el frente hacia abajo. */
export function rotX(angulo: number): Matriz {
  const c = Math.cos(angulo), s = Math.sin(angulo);
  return [[1, 0, 0], [0, c, -s], [0, s, c]];
}

export function suavizar(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return x * x * (3 - 2 * x);
}

// ── Proyección ────────────────────────────────────────────────────────────────

export interface Escena {
  /** Centro de giro, en el marco con y hacia arriba. */
  centro: [number, number, number];
  /** Encogimiento que mantiene la molécula dentro del lienzo en cualquier orientación. */
  encoge: number;
  /** Vecinos de cada átomo (para el lado del doble enlace y la etiqueta). */
  vecinos: number[][];
}

export function prepararEscena(modelo: ModeloElevacion): Escena {
  const puntos = modelo.atomos.map((a) => [a.xyz[0], -a.xyz[1], a.xyz[2]]);
  const n = Math.max(1, puntos.length);
  const centro = [0, 1, 2].map((k) => puntos.reduce((s, p) => s + p[k], 0) / n) as [number, number, number];
  const radio = puntos.reduce((r, p) => Math.max(r, Math.hypot(p[0] - centro[0], p[1] - centro[1], p[2] - centro[2])), 0);
  // Margen para la etiqueta de un heteroátomo en el borde.
  const libre = modelo.lienzo / 2 - 14;
  const encoge = radio > libre ? libre / radio : 1;
  const vecinos = modelo.atomos.map(() => [] as number[]);
  for (const e of modelo.enlaces) {
    vecinos[e.a].push(e.b);
    vecinos[e.b].push(e.a);
  }
  return { centro, encoge, vecinos };
}

export interface Punto {
  x: number;
  y: number;
  /** Profundidad hacia quien mira, ya multiplicada por la elevación. */
  z: number;
}

/**
 * Posición en pantalla de cada átomo para una rotación `R` y una elevación
 * `s` ∈ [0, 1]. Con `s = 0` es exactamente la miniatura 2D; con `s = 1`, la
 * proyección del modelo 3D girado, centrada y encogida si hace falta. El
 * encogimiento se aplica con `s`, para que se lea como parte del movimiento.
 */
export function proyectar(modelo: ModeloElevacion, escena: Escena, R: Matriz, s: number): Punto[] {
  const mitad = modelo.lienzo / 2;
  const k = 1 + (escena.encoge - 1) * s;
  const [cx, cy, cz] = escena.centro;
  return modelo.atomos.map((a) => {
    const x = a.xyz[0] - cx, y = -a.xyz[1] - cy, z = a.xyz[2] - cz;
    const rx = R[0][0] * x + R[0][1] * y + R[0][2] * z;
    const ry = R[1][0] * x + R[1][1] * y + R[1][2] * z;
    const rz = R[2][0] * x + R[2][1] * y + R[2][2] * z;
    const sx = mitad + k * rx, sy = mitad - k * ry;
    const [fx, fy] = a.plano;
    return { x: fx + (sx - fx) * s, y: fy + (sy - fy) * s, z: rz * s };
  });
}

// ── Pintado ───────────────────────────────────────────────────────────────────

const SUBINDICE = "₀₁₂₃₄₅₆₇₈₉";

function escapar(texto: string): string {
  return texto.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function textoDeCarga(carga: number): string {
  if (!carga) return "";
  const signo = carga > 0 ? "+" : "−";
  return Math.abs(carga) === 1 ? signo : `${Math.abs(carga)}${signo}`;
}

/** Como en la miniatura de RDKit: los carbonos son implícitos salvo cargados o aislados. */
function rotulo(atomo: AtomoElevacion, vecinos: number): string | null {
  if (atomo.elemento === "C" && !atomo.carga && vecinos > 0) return null;
  const h = atomo.hidrogenos > 0 ? `H${atomo.hidrogenos > 1 ? SUBINDICE[atomo.hidrogenos] ?? atomo.hidrogenos : ""}` : "";
  return `${atomo.elemento}${h}${textoDeCarga(atomo.carga)}`;
}

/**
 * El SVG interior (sin la etiqueta `<svg>`) para unas posiciones dadas.
 *
 * Profundidad: lo lejano se pinta antes, más fino y más tenue, y cada enlace
 * lleva un halo del color del fondo en su tramo central, de modo que el que
 * pasa por delante corta visualmente al de detrás sin abrir huecos en los
 * vértices.
 */
/** Marca de lo que la preparación cambió. No es el color de ningún elemento. */
const MARCA = "#d97706";
/** Marca de lo que señalan los detectores: discontinua, para no confundirse con la anterior. */
const MARCA_DETECTOR = "#7c3aed";

export function pintar(modelo: ModeloElevacion, escena: Escena, puntos: Punto[], tinta = "#000000", fondo = "#ffffff"): string {
  const zs = puntos.map((p) => p.z);
  const zMin = Math.min(...zs), zMax = Math.max(...zs);
  const rango = zMax - zMin;
  const cercania = (z: number) => (rango > 1 ? (z - zMin) / rango : 1);
  const rotulos = modelo.atomos.map((a, i) => rotulo(a, escena.vecinos[i].length));

  type Pieza = { z: number; svg: string };
  const piezas: Pieza[] = [];
  // Vista «Se acoplará»: los átomos y enlaces que la preparación cambió llevan una marca.
  const cambios = modelo.especie_acoplada?.cambios;
  const atomoCambiado = new Set(cambios?.atomos.map((c) => c.atomo) ?? []);
  const enlaceCambiado = new Set(cambios?.enlaces.map((c) => `${Math.min(c.a, c.b)}-${Math.max(c.a, c.b)}`) ?? []);
  // Átomos que señala algún detector (ojiva, PAINS, especie en revisión).
  const atomoDetectado = new Set((modelo.detectores ?? []).flatMap((d) => d.atomos));

  for (const e of modelo.enlaces) {
    const p = puntos[e.a], q = puntos[e.b];
    const dx = q.x - p.x, dy = q.y - p.y;
    const largo = Math.hypot(dx, dy);
    if (largo < 0.5) continue;
    const z = (p.z + q.z) / 2;
    const c = cercania(z);
    const ancho = 1.3 + 1.1 * c;
    const opacidad = 0.45 + 0.55 * c;
    // Recorta el extremo que lleva rótulo, para no tachar la letra.
    const recorte = (i: number) => (rotulos[i] ? Math.min(0.42, 9 / largo) : 0);
    const ta = recorte(e.a), tb = recorte(e.b);
    const ax = p.x + dx * ta, ay = p.y + dy * ta, bx = q.x - dx * tb, by = q.y - dy * tb;
    const ux = dx / largo, uy = dy / largo, nx = -uy, ny = ux;
    let lineas = "";
    const linea = (x1: number, y1: number, x2: number, y2: number) =>
      `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`;
    if (e.orden === 1) {
      lineas = linea(ax, ay, bx, by);
    } else {
      // El segundo trazo va hacia el lado de un sustituyente (dentro del anillo
      // casi siempre), acortado como lo dibuja RDKit.
      const otro = escena.vecinos[e.a].find((j) => j !== e.b) ?? escena.vecinos[e.b].find((j) => j !== e.a);
      let lado = 0;
      if (otro !== undefined) {
        const o = puntos[otro];
        lado = Math.sign((o.x - p.x) * nx + (o.y - p.y) * ny);
      }
      const sep = 4.5;
      if (e.orden === 3 || lado === 0) {
        const m = e.orden === 3 ? sep : sep / 2;
        if (e.orden === 3) lineas += linea(ax, ay, bx, by);
        lineas += linea(ax + nx * m, ay + ny * m, bx + nx * m, by + ny * m);
        lineas += linea(ax - nx * m, ay - ny * m, bx - nx * m, by - ny * m);
      } else {
        const acorta = 0.14;
        lineas += linea(ax, ay, bx, by);
        lineas += linea(
          ax + dx * acorta + nx * sep * lado, ay + dy * acorta + ny * sep * lado,
          bx - dx * acorta + nx * sep * lado, by - dy * acorta + ny * sep * lado,
        );
      }
    }
    const h0 = 0.2, h1 = 0.8;
    const halo = rango > 1
      ? `<line x1="${(p.x + dx * h0).toFixed(1)}" y1="${(p.y + dy * h0).toFixed(1)}" x2="${(p.x + dx * h1).toFixed(1)}" y2="${(p.y + dy * h1).toFixed(1)}" stroke="${fondo}" stroke-width="${(ancho + 4 + (e.orden > 1 ? 9 : 0)).toFixed(1)}"/>`
      : "";
    const marca = enlaceCambiado.has(`${Math.min(e.a, e.b)}-${Math.max(e.a, e.b)}`)
      ? `<line data-cambio="enlace" x1="${p.x.toFixed(1)}" y1="${p.y.toFixed(1)}" x2="${q.x.toFixed(1)}" y2="${q.y.toFixed(1)}" stroke="${MARCA}" stroke-opacity="0.35" stroke-width="12"/>`
      : "";
    piezas.push({
      z,
      svg: `<g stroke-linecap="round">${halo}${marca}<g stroke="${tinta}" stroke-opacity="${opacidad.toFixed(2)}" stroke-width="${ancho.toFixed(2)}">${lineas}</g></g>`,
    });
  }

  atomoDetectado.forEach((i) => {
    const p = puntos[i];
    if (!p) return;
    piezas.push({
      z: p.z + 2e6,
      svg: `<circle data-detector="atomo" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="14" fill="none" stroke="${MARCA_DETECTOR}" stroke-width="1.5" stroke-dasharray="3 2.5"/>`,
    });
  });

  atomoCambiado.forEach((i) => {
    const p = puntos[i];
    if (!p) return;
    piezas.push({
      z: p.z + 2e6,
      svg: `<circle data-cambio="atomo" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="11.5" fill="none" stroke="${MARCA}" stroke-width="2"/>`,
    });
  });

  modelo.atomos.forEach((_, i) => {
    const texto = rotulos[i];
    if (!texto) return;
    const p = puntos[i];
    const c = cercania(p.z);
    // Encima de TODOS los enlaces, ordenados entre sí por profundidad: si
    // compitieran con ellos, el halo de un enlace cercano cortaba la letra de un
    // átomo lejano («Ͻ» en lugar de «O»).
    piezas.push({
      z: p.z + 1e6,
      svg:
        `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="8.5" fill="${fondo}"/>` +
        `<text x="${p.x.toFixed(1)}" y="${p.y.toFixed(1)}" fill="${tinta}" fill-opacity="${(0.5 + 0.5 * c).toFixed(2)}" ` +
        `font-family="sans-serif" font-size="14" text-anchor="middle" dominant-baseline="central">${escapar(texto)}</text>`,
    });
  });

  piezas.sort((a, b) => a.z - b.z);
  return `<rect width="${modelo.lienzo}" height="${modelo.lienzo}" fill="${fondo}"/>` + piezas.map((p) => p.svg).join("");
}

// ── Avisos de la pose ─────────────────────────────────────────────────────────

export type AvisoDePose =
  | { tipo: "estereo_invertido"; atomos: number[] }
  | { tipo: "estereo_sin_declarar"; atomos: number[] }
  | { tipo: "estereo_no_verificable"; atomos: number[] }
  | { tipo: "doble_invertido"; enlaces: [number, number][] }
  | { tipo: "especie_cargada"; carga_smiles: number; carga_acoplada: number }
  | { tipo: "validez_fisica"; status: string; label: string | null; comprobaciones: string[] };

/**
 * Lo que la pose de la corrida no coincide con el SMILES guardado. El visor lo
 * declara en vez de enseñar la pose como si fuera la molécula guardada. Un
 * conformador no lleva `pose`, así que no tiene avisos de este tipo.
 */
export function avisosDePose(modelo: ModeloElevacion): AvisoDePose[] {
  const pose = modelo.pose;
  if (!pose) return [];
  const avisos: AvisoDePose[] = [];
  const estereo = pose.estereo;
  if (estereo?.invertidos.length) {
    avisos.push({ tipo: "estereo_invertido", atomos: estereo.invertidos.map((i) => i.atomo) });
  }
  if (estereo?.sin_declarar.length) avisos.push({ tipo: "estereo_sin_declarar", atomos: estereo.sin_declarar });
  if (estereo?.no_asignables.length) avisos.push({ tipo: "estereo_no_verificable", atomos: estereo.no_asignables });
  if (estereo?.dobles_invertidos?.length) {
    avisos.push({ tipo: "doble_invertido", enlaces: estereo.dobles_invertidos.map((d) => d.enlace) });
  }
  const especie = pose.especie;
  if (especie && especie.carga_smiles !== especie.carga_acoplada) {
    avisos.push({ tipo: "especie_cargada", carga_smiles: especie.carga_smiles, carga_acoplada: especie.carga_acoplada });
  }
  // Sólo un veredicto que pide atención es aviso; «pasa» y «no evaluada» se leen en el detalle.
  const fisica = pose.validez_fisica;
  if (fisica && (fisica.status === "failed" || fisica.status === "review")) {
    avisos.push({ tipo: "validez_fisica", status: fisica.status, label: fisica.label, comprobaciones: fisica.comprobaciones_que_fallan });
  }
  return avisos;
}

/** Un número para leer en pantalla, con la coma o el punto del idioma del navegador. */
export function formatoDeNumero(valor: number): string {
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(valor);
}

// ── Datos ─────────────────────────────────────────────────────────────────────

/**
 * Modelos ya pedidos por ficha. `null` = esa corrida no conserva pose: no se
 * vuelve a preguntar en la sesión. Acotado: una bioteca grande no se queda
 * entera en memoria.
 */
const CACHE_MAX = 200;
const cache = new Map<string, Promise<ModeloElevacion | null>>();

function recordar(clave: string, valor: Promise<ModeloElevacion | null>) {
  cache.set(clave, valor);
  while (cache.size > CACHE_MAX) {
    const primera = cache.keys().next().value;
    if (primera === undefined) break;
    cache.delete(primera);
  }
}

/** La pose top-1 de la corrida de una ficha de Moldex, o `null` si no la conserva. */
export function elevacionDeLaCorrida(moleculeId: string, taskId: string | null | undefined): Promise<ModeloElevacion | null> {
  const clave = `${moleculeId}|${taskId ?? ""}`;
  const previa = cache.get(clave);
  if (previa) return previa;
  const consulta = taskId ? `?task_id=${encodeURIComponent(taskId)}` : "";
  const promesa = fetchBackend(`/chem/elevacion/${moleculeId}${consulta}`, {
    headers: { "ngrok-skip-browser-warning": "true", ...getAuthHeaders() },
    cache: "no-store",
  })
    .then(async (res) => {
      if (!res.ok) return null;
      const modelo = (await res.json()) as ModeloElevacion;
      return modelo.contrato === "elevacion/v1" && modelo.fuente === "pose_vina_top1" ? modelo : null;
    })
    .catch(() => {
      // Un fallo de red no dice que la corrida carezca de pose: se olvida y se
      // vuelve a intentar la próxima vez.
      cache.delete(clave);
      return null;
    });
  recordar(clave, promesa);
  return promesa;
}

export class ErrorDeElevacion extends Error {}

/**
 * Conformadores ya calculados por SMILES. Un SMILES que vuelve (salir del visor,
 * volver a Ketcher, editar y deshacer) no pide otro cálculo al backend. Acotado
 * como las demás cachés del módulo; un error no se guarda.
 */
const cacheDelEditor = new Map<string, ModeloElevacion>();

/** Cómo se pide el modelo del editor. Sin opciones, la vista «Escrita». */
export interface OpcionesDelEditor {
  vista?: VistaDelEditor;
  /** Sólo cuenta en la vista «Se acoplará». Sin ella, el pH y el tautómero por defecto de la corrida. */
  preparacion?: PreparacionDeLaCorrida;
  /** El dibujo de Ketcher (molfile): el levantamiento parte de él si es la molécula del SMILES. */
  molfile?: string | null;
  /** Una semilla en vez de tres (vista «Escrita»): para enseñar algo enseguida. No se guarda en la caché. */
  rapida?: boolean;
}

/** Un resumen corto y estable del dibujo, para la clave de la caché. */
function huella(texto: string): string {
  let h = 5381;
  for (let i = 0; i < texto.length; i++) h = ((h << 5) + h + texto.charCodeAt(i)) | 0;
  return `${texto.length}:${(h >>> 0).toString(36)}`;
}

/** La especie depende del pH y del tautómero, y el plano del dibujo: cada combinación es otra entrada. */
function claveDelEditor(smiles: string, opciones?: OpcionesDelEditor): string {
  const dibujo = opciones?.molfile ? `|${huella(opciones.molfile)}` : "";
  if (opciones?.vista !== "acoplada") return `${smiles}${dibujo}`;
  const p = opciones.preparacion;
  return `acoplada|${p?.ph ?? ""}|${p?.tautomero ?? ""}|${smiles}${dibujo}`;
}

/** El modelo ya calculado para este SMILES y esta vista, o `undefined` si hay que pedirlo. */
export function modeloDelEditorEnCache(smiles: string, opciones?: OpcionesDelEditor): ModeloElevacion | undefined {
  return cacheDelEditor.get(claveDelEditor(smiles, opciones));
}

function recordarDelEditor(smiles: string, modelo: ModeloElevacion) {
  cacheDelEditor.set(smiles, modelo);
  while (cacheDelEditor.size > CACHE_MAX) {
    const primera = cacheDelEditor.keys().next().value;
    if (primera === undefined) break;
    cacheDelEditor.delete(primera);
  }
}

/**
 * El modelo del SMILES del editor: los conformadores de lo escrito o, con
 * `vista: "acoplada"`, la especie que prepararía la corrida con su pH y su modo
 * de tautómero.
 */
export async function elevacionDelEditor(
  smiles: string,
  signal?: AbortSignal,
  opciones?: OpcionesDelEditor,
): Promise<ModeloElevacion> {
  const clave = claveDelEditor(smiles, opciones);
  const previo = cacheDelEditor.get(clave);
  if (previo) return previo;
  const dibujo = opciones?.molfile ? { molfile: opciones.molfile } : {};
  const cuerpo = opciones?.vista === "acoplada"
    ? { smiles, vista: "acoplada", ph: opciones.preparacion?.ph ?? null, tautomero: opciones.preparacion?.tautomero ?? null, ...dibujo }
    : { smiles, ...dibujo, ...(opciones?.rapida ? { rapida: true } : {}) };
  const res = await fetchBackend("/chem/elevacion", {
    method: "POST",
    headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true", ...getAuthHeaders() },
    body: JSON.stringify(cuerpo),
    signal,
  });
  if (!res.ok) {
    let detalle = `HTTP ${res.status}`;
    try {
      const cuerpo = await res.json();
      if (typeof cuerpo?.detail === "string") detalle = cuerpo.detail;
    } catch { /* el detalle por defecto basta */ }
    throw new ErrorDeElevacion(detalle);
  }
  const modelo = (await res.json()) as ModeloElevacion;
  // Una respuesta rápida es provisional: la completa la sustituye y es la que se guarda.
  if (!(opciones?.rapida && opciones.vista !== "acoplada")) recordarDelEditor(clave, modelo);
  return modelo;
}

/** `prefers-reduced-motion`: sin animaciones que el investigador no pidió. */
export function prefiereMenosMovimiento(): boolean {
  try {
    return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}
