// =====================================================================
// La escena del visor que no necesita WebGL
// =====================================================================
//
// POR QUÉ EXISTE. Mol* y Web3D dibujan con WebGL. Medido en el motor de
// WebView2 157 (2026-11-09): sin GPU, WebGL sigue existiendo mientras quede el
// rasterizador por software; con `--disable-gpu --disable-software-rasterizer`
// —el estado en que queda Chromium cuando el proceso de GPU muere varias veces,
// o cuando una política lo veta— `getContext("webgl")` devuelve `null` y la
// bandera `--enable-unsafe-swiftshader` no lo cambia. En ese estado la pestaña
// Evaluación enseñaba un recuadro negro con un aviso. El lienzo 2D sí existe
// siempre: es lo único con lo que se puede contar.
//
// QUÉ ES. Geometría pura: lee el receptor (PDB) y la pose (SDF), elige qué
// merece dibujarse y lo proyecta. No toca el DOM, así que se prueba sin
// navegador. El componente (`VisorSinWebGL.tsx`) sólo pinta lo que sale de aquí.
//
// QUÉ NO ES. No es un tercer motor 3D: no hay superficies, ni cartoon, ni
// selección de átomos. Es la vista mínima que responde «¿dónde quedó la pose
// respecto del sitio?» cuando no hay con qué dibujar otra cosa.

export type Vec3 = readonly [number, number, number];

export interface AtomoDelReceptor {
  readonly x: number; readonly y: number; readonly z: number;
  readonly elemento: string;
  readonly nombre: string;
  readonly residuo: string;
  readonly cadena: string;
  readonly numero: number;
  readonly hetero: boolean;
}

export interface AtomoDelLigando {
  readonly x: number; readonly y: number; readonly z: number;
  readonly elemento: string;
}

export interface Ligando {
  readonly atomos: readonly AtomoDelLigando[];
  /** Pares de índices de `atomos` (sólo entre átomos pesados). */
  readonly enlaces: readonly (readonly [number, number])[];
}

export interface CajaDeBusqueda {
  readonly centerX: number; readonly centerY: number; readonly centerZ: number;
  readonly sizeX: number; readonly sizeY: number; readonly sizeZ: number;
}

export interface EtiquetaDeResiduo {
  readonly x: number; readonly y: number; readonly z: number;
  /** «ASP75», o «B:ASP75» si el sitio toca más de una cadena. */
  readonly texto: string;
}

export interface Escena {
  readonly centro: Vec3;
  /** Radio, en Å, de lo que la vista encuadra al abrir. */
  readonly radio: number;
  /** Radio, en Å, que contiene el receptor entero desde `centro`. */
  readonly radioTotal: number;
  /** Segmentos Cα–Cα consecutivos: [x1,y1,z1,x2,y2,z2, …]. */
  readonly traza: Float32Array;
  readonly sitio: {
    readonly atomos: readonly AtomoDelReceptor[];
    readonly enlaces: readonly (readonly [number, number])[];
    readonly etiquetas: readonly EtiquetaDeResiduo[];
  };
  readonly ligando: Ligando;
  /** Las 12 aristas de la caja, como segmentos, o `null` si no hay caja. */
  readonly caja: Float32Array | null;
  /** Hacia dónde mirar al abrir: del interior del receptor hacia el ligando. */
  readonly haciaElObservador: Vec3 | null;
  readonly cuenta: {
    readonly atomosDelReceptor: number;
    readonly residuosDelSitio: number;
    readonly atomosDelLigando: number;
  };
  /** De dónde salió el sitio dibujado; la interfaz lo dice tal cual. */
  readonly criterioDelSitio: "ligando" | "caja" | "ninguno";
}

/** Distancia, en Å, a la que un residuo cuenta como «del sitio» respecto de la pose. */
export const RADIO_DE_CONTACTO = 4.5;
/** Sin pose: distancia, en Å, al centro de la caja de búsqueda dentro de la que se dibujan los residuos. */
export const RADIO_SIN_POSE = 8;
/** Tope de átomos del sitio que se dibujan: el lienzo 2D no es para el receptor entero. */
export const MAXIMO_DE_ATOMOS_DEL_SITIO = 2500;

const AGUAS = new Set(["HOH", "WAT", "DOD", "SOL", "TIP", "TIP3"]);
const DOS_LETRAS = new Set(["CL", "BR", "ZN", "MG", "FE", "CA", "NA", "MN", "CU", "CO", "NI", "SE", "LI", "CD", "HG"]);

/** Elemento de una línea de coordenadas: la columna 77–78 y, si falta, el nombre del átomo. */
function elementoDe(linea: string, hetero: boolean): string {
  // Sólo letras: los PDB de varios programas escriben la carga pegada («ZN2+», «O1-»).
  const columna = linea.slice(76, 78).replace(/[^A-Za-z]/g, "").toUpperCase();
  if (columna) return columna;
  const nombre = linea.slice(12, 16).replace(/[^A-Za-z]/g, "").toUpperCase();
  if (!nombre) return "C";
  // En una proteína «CA» es el carbono alfa, no calcio: sin columna de elemento
  // sólo un HETATM puede ser de dos letras.
  if (hetero && DOS_LETRAS.has(nombre.slice(0, 2))) return nombre.slice(0, 2);
  return nombre[0];
}

/** Átomos pesados del receptor (sin aguas ni hidrógenos). Tolera CRLF y líneas cortas. */
export function leerAtomosDelReceptor(pdb: string): AtomoDelReceptor[] {
  const atomos: AtomoDelReceptor[] = [];
  for (const cruda of pdb.split("\n")) {
    const hetero = cruda.startsWith("HETATM");
    if (!hetero && !cruda.startsWith("ATOM")) continue;
    const linea = cruda.replace(/\r$/, "");
    if (linea.length < 54) continue;
    const x = Number.parseFloat(linea.slice(30, 38));
    const y = Number.parseFloat(linea.slice(38, 46));
    const z = Number.parseFloat(linea.slice(46, 54));
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    const residuo = linea.slice(17, 20).trim().toUpperCase();
    if (AGUAS.has(residuo)) continue;
    const elemento = elementoDe(linea, hetero);
    if (elemento === "H" || elemento === "D") continue;
    // Conformación alternativa: sólo la primera, como hace la preparación.
    const alterna = linea[16];
    if (alterna && alterna !== " " && alterna !== "A") continue;
    atomos.push({
      x, y, z, elemento,
      nombre: linea.slice(12, 16).trim().toUpperCase(),
      residuo,
      cadena: (linea[21] ?? " ").trim().toUpperCase(),
      numero: Number.parseInt(linea.slice(22, 26), 10) || 0,
      hetero,
    });
  }
  return atomos;
}

/** Primera pose de un SDF (V2000 o V3000), sin hidrógenos. */
export function leerLigando(sdf: string): Ligando {
  const bloque = (sdf.split("$$$$")[0] ?? sdf).split(/\r?\n/);
  const crudos: AtomoDelLigando[] = [];
  const paresCrudos: [number, number][] = [];

  if (bloque.some((linea) => linea.includes("V3000"))) {
    let seccion: "atomos" | "enlaces" | null = null;
    const indice = new Map<number, number>();
    for (const linea of bloque) {
      if (!linea.startsWith("M  V30 ")) continue;
      const resto = linea.slice(7).trim();
      if (resto.startsWith("BEGIN ATOM")) { seccion = "atomos"; continue; }
      if (resto.startsWith("BEGIN BOND")) { seccion = "enlaces"; continue; }
      if (resto.startsWith("END ")) { seccion = null; continue; }
      const campos = resto.split(/\s+/);
      if (seccion === "atomos" && campos.length >= 5) {
        const [x, y, z] = [campos[2], campos[3], campos[4]].map(Number.parseFloat);
        if (![x, y, z].every(Number.isFinite)) continue;
        indice.set(Number.parseInt(campos[0], 10), crudos.length);
        crudos.push({ x, y, z, elemento: campos[1].toUpperCase() });
      } else if (seccion === "enlaces" && campos.length >= 4) {
        const a = indice.get(Number.parseInt(campos[2], 10));
        const b = indice.get(Number.parseInt(campos[3], 10));
        if (a !== undefined && b !== undefined) paresCrudos.push([a, b]);
      }
    }
  } else if (bloque.length >= 4) {
    const cuentas = bloque[3] ?? "";
    const nAtomos = Number.parseInt(cuentas.slice(0, 3), 10) || 0;
    const nEnlaces = Number.parseInt(cuentas.slice(3, 6), 10) || 0;
    // El índice del SDF cuenta líneas, no átomos válidos: una coordenada ilegible
    // no puede desplazar a las siguientes, o los enlaces unirían otros átomos.
    const indice = new Map<number, number>();
    for (let i = 0; i < nAtomos; i++) {
      const linea = bloque[4 + i] ?? "";
      const x = Number.parseFloat(linea.slice(0, 10));
      const y = Number.parseFloat(linea.slice(10, 20));
      const z = Number.parseFloat(linea.slice(20, 30));
      if (![x, y, z].every(Number.isFinite)) continue;
      indice.set(i, crudos.length);
      crudos.push({ x, y, z, elemento: (linea.slice(31, 34).trim() || "C").toUpperCase() });
    }
    for (let i = 0; i < nEnlaces; i++) {
      const linea = bloque[4 + nAtomos + i] ?? "";
      const a = indice.get(Number.parseInt(linea.slice(0, 3), 10) - 1);
      const b = indice.get(Number.parseInt(linea.slice(3, 6), 10) - 1);
      if (a !== undefined && b !== undefined) paresCrudos.push([a, b]);
    }
  }

  // Sin hidrógenos: en una proyección plana sólo estorban.
  const pesado = new Map<number, number>();
  const atomos: AtomoDelLigando[] = [];
  crudos.forEach((atomo, i) => {
    if (atomo.elemento === "H" || atomo.elemento === "D") return;
    pesado.set(i, atomos.length);
    atomos.push(atomo);
  });
  const enlaces: [number, number][] = [];
  for (const [a, b] of paresCrudos) {
    const pa = pesado.get(a), pb = pesado.get(b);
    if (pa !== undefined && pb !== undefined) enlaces.push([pa, pb]);
  }
  return { atomos, enlaces };
}

const claveDeResiduo = (a: AtomoDelReceptor) => `${a.cadena}|${a.numero}|${a.residuo}`;

function centroide(puntos: readonly { x: number; y: number; z: number }[]): Vec3 {
  let x = 0, y = 0, z = 0;
  for (const p of puntos) { x += p.x; y += p.y; z += p.z; }
  const n = puntos.length || 1;
  return [x / n, y / n, z / n];
}

function radioDesde(centro: Vec3, puntos: readonly { x: number; y: number; z: number }[]): number {
  let maximo = 0;
  for (const p of puntos) {
    const d = Math.hypot(p.x - centro[0], p.y - centro[1], p.z - centro[2]);
    if (d > maximo) maximo = d;
  }
  return maximo;
}

function aristasDeLaCaja(caja: CajaDeBusqueda): Float32Array {
  const { centerX: cx, centerY: cy, centerZ: cz } = caja;
  const hx = caja.sizeX / 2, hy = caja.sizeY / 2, hz = caja.sizeZ / 2;
  const v: Vec3[] = [
    [cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz], [cx + hx, cy + hy, cz - hz], [cx - hx, cy + hy, cz - hz],
    [cx - hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz + hz], [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz],
  ];
  const pares = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
  const salida = new Float32Array(pares.length * 6);
  pares.forEach(([a, b], i) => salida.set([...v[a], ...v[b]], i * 6));
  return salida;
}

/** Enlaces entre átomos pesados por distancia. Suficiente para dibujar cadenas laterales, no para química. */
function enlacesPorDistancia(atomos: readonly AtomoDelReceptor[]): [number, number][] {
  const enlaces: [number, number][] = [];
  for (let i = 0; i < atomos.length; i++) {
    const a = atomos[i];
    for (let j = i + 1; j < atomos.length; j++) {
      const b = atomos[j];
      const dx = a.x - b.x;
      if (dx > 2.3 || dx < -2.3) continue;
      const dy = a.y - b.y;
      if (dy > 2.3 || dy < -2.3) continue;
      const dz = a.z - b.z;
      const limite = a.elemento === "S" || b.elemento === "S" || a.elemento === "P" || b.elemento === "P" ? 2.2 : 1.9;
      if (dx * dx + dy * dy + dz * dz <= limite * limite) enlaces.push([i, j]);
    }
  }
  return enlaces;
}

export interface EntradaDeEscena {
  readonly pdb?: string | null;
  readonly sdf?: string | null;
  readonly caja?: CajaDeBusqueda | null;
}

/**
 * Decide qué se dibuja. Devuelve `null` si no hay ni receptor ni ligando.
 *
 * El sitio son los residuos con algún átomo a `RADIO_DE_CONTACTO` o menos de la
 * pose; sin pose, los que tienen algún átomo a `RADIO_SIN_POSE` o menos del
 * centro de la caja; sin ninguna de las dos, sólo el esqueleto. El criterio viaja
 * en `criterioDelSitio` para que la interfaz no presente una caja como si fueran
 * contactos.
 */
export function construirEscena({ pdb, sdf, caja }: EntradaDeEscena): Escena | null {
  const receptor = pdb && pdb.trim().length > 10 ? leerAtomosDelReceptor(pdb) : [];
  const ligando = sdf && sdf.trim().length > 10 ? leerLigando(sdf) : { atomos: [], enlaces: [] };
  if (receptor.length === 0 && ligando.atomos.length === 0) return null;

  // ── Esqueleto: Cα consecutivos de la misma cadena, sin saltar huecos ──────
  const alfas = receptor.filter((a) => !a.hetero && a.nombre === "CA" && a.elemento === "C");
  const tramos: number[] = [];
  for (let i = 1; i < alfas.length; i++) {
    const a = alfas[i - 1], b = alfas[i];
    if (a.cadena !== b.cadena) continue;
    // 3,8 Å entre Cα vecinos; por encima de 4,3 falta al menos un residuo.
    if (Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) > 4.3) continue;
    tramos.push(a.x, a.y, a.z, b.x, b.y, b.z);
  }

  // ── Sitio ────────────────────────────────────────────────────────────────
  let criterio: Escena["criterioDelSitio"] = "ninguno";
  const delSitio = new Set<string>();
  if (ligando.atomos.length > 0 && receptor.length > 0) {
    criterio = "ligando";
    const limite2 = RADIO_DE_CONTACTO * RADIO_DE_CONTACTO;
    const c = centroide(ligando.atomos);
    const alcance = radioDesde(c, ligando.atomos) + RADIO_DE_CONTACTO;
    for (const a of receptor) {
      // Descarte barato antes de comparar con cada átomo del ligando.
      if (Math.hypot(a.x - c[0], a.y - c[1], a.z - c[2]) > alcance) continue;
      for (const l of ligando.atomos) {
        const dx = a.x - l.x, dy = a.y - l.y, dz = a.z - l.z;
        if (dx * dx + dy * dy + dz * dz <= limite2) { delSitio.add(claveDeResiduo(a)); break; }
      }
    }
  } else if (caja && receptor.length > 0) {
    // Sin pose todavía, la caja entera no sirve de sitio: una de 22,5 Å de lado
    // contiene unos doscientos residuos (207 en 8HFI) y el dibujo es una maraña.
    // Se enseña el corazón de la caja, que es donde va a buscar el acoplamiento.
    criterio = "caja";
    const limite2 = RADIO_SIN_POSE * RADIO_SIN_POSE;
    for (const a of receptor) {
      const dx = a.x - caja.centerX, dy = a.y - caja.centerY, dz = a.z - caja.centerZ;
      if (dx * dx + dy * dy + dz * dz <= limite2) delSitio.add(claveDeResiduo(a));
    }
  }
  let atomosDelSitio = receptor.filter((a) => delSitio.has(claveDeResiduo(a)));
  if (atomosDelSitio.length > MAXIMO_DE_ATOMOS_DEL_SITIO) atomosDelSitio = atomosDelSitio.slice(0, MAXIMO_DE_ATOMOS_DEL_SITIO);

  // ── Etiquetas: una por residuo, en el centroide de su cadena lateral ──────
  const porResiduo = new Map<string, AtomoDelReceptor[]>();
  for (const a of atomosDelSitio) {
    const lista = porResiduo.get(claveDeResiduo(a));
    if (lista) lista.push(a); else porResiduo.set(claveDeResiduo(a), [a]);
  }
  const variasCadenas = new Set(atomosDelSitio.map((a) => a.cadena)).size > 1;
  const etiquetas: EtiquetaDeResiduo[] = [];
  for (const lista of porResiduo.values()) {
    const lateral = lista.filter((a) => !["N", "C", "O", "CA"].includes(a.nombre));
    const [x, y, z] = centroide(lateral.length > 0 ? lateral : lista);
    const a = lista[0];
    etiquetas.push({ x, y, z, texto: `${variasCadenas && a.cadena ? `${a.cadena}:` : ""}${a.residuo}${a.numero}` });
  }

  // ── Encuadre ─────────────────────────────────────────────────────────────
  const centroDelReceptor = receptor.length > 0 ? centroide(receptor) : null;
  let centro: Vec3;
  let radio: number;
  if (ligando.atomos.length > 0) {
    centro = centroide(ligando.atomos);
    radio = Math.max(radioDesde(centro, ligando.atomos) + 7, 11);
  } else if (caja) {
    centro = [caja.centerX, caja.centerY, caja.centerZ];
    radio = Math.max(Math.hypot(caja.sizeX, caja.sizeY, caja.sizeZ) / 2, 8);
  } else {
    centro = centroDelReceptor ?? [0, 0, 0];
    radio = Math.max(radioDesde(centro, receptor), 8);
  }
  const radioTotal = Math.max(radio, radioDesde(centro, receptor), caja ? Math.hypot(caja.sizeX, caja.sizeY, caja.sizeZ) / 2 : 0);

  let haciaElObservador: Vec3 | null = null;
  if (centroDelReceptor && (ligando.atomos.length > 0 || caja)) {
    const d: Vec3 = [centro[0] - centroDelReceptor[0], centro[1] - centroDelReceptor[1], centro[2] - centroDelReceptor[2]];
    const n = Math.hypot(d[0], d[1], d[2]);
    if (n > 1.5) haciaElObservador = [d[0] / n, d[1] / n, d[2] / n];
  }

  return {
    centro, radio, radioTotal,
    traza: Float32Array.from(tramos),
    sitio: { atomos: atomosDelSitio, enlaces: enlacesPorDistancia(atomosDelSitio), etiquetas },
    ligando,
    caja: caja ? aristasDeLaCaja(caja) : null,
    haciaElObservador,
    cuenta: { atomosDelReceptor: receptor.length, residuosDelSitio: porResiduo.size, atomosDelLigando: ligando.atomos.length },
    criterioDelSitio: criterio,
  };
}

// ── Vista: una rotación y un zoom ───────────────────────────────────────────

/** Matriz de rotación 3×3 por filas. La fila 2 es la dirección que apunta al observador. */
export type Rotacion = readonly [number, number, number, number, number, number, number, number, number];

export const SIN_ROTAR: Rotacion = [1, 0, 0, 0, 1, 0, 0, 0, 1];

function normalizar(v: Vec3): Vec3 {
  const n = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / n, v[1] / n, v[2] / n];
}
function cruz(a: Vec3, b: Vec3): Vec3 {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

/** Rotación que deja `direccion` apuntando al observador. */
export function mirarDesde(direccion: Vec3 | null): Rotacion {
  if (!direccion) return SIN_ROTAR;
  const z = normalizar(direccion);
  const apoyo: Vec3 = Math.abs(z[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
  const x = normalizar(cruz(apoyo, z));
  const y = cruz(z, x);
  return [x[0], x[1], x[2], y[0], y[1], y[2], z[0], z[1], z[2]];
}

/** Gira la vista: `dx` alrededor del eje vertical de la pantalla, `dy` alrededor del horizontal (radianes). */
export function girar(r: Rotacion, dx: number, dy: number): Rotacion {
  const cx = Math.cos(dx), sx = Math.sin(dx), cy = Math.cos(dy), sy = Math.sin(dy);
  // Primero alrededor de Y de pantalla, luego alrededor de X de pantalla.
  const a: number[] = [
    cx * r[0] + sx * r[6], cx * r[1] + sx * r[7], cx * r[2] + sx * r[8],
    r[3], r[4], r[5],
    -sx * r[0] + cx * r[6], -sx * r[1] + cx * r[7], -sx * r[2] + cx * r[8],
  ];
  const b: number[] = [
    a[0], a[1], a[2],
    cy * a[3] - sy * a[6], cy * a[4] - sy * a[7], cy * a[5] - sy * a[8],
    sy * a[3] + cy * a[6], sy * a[4] + cy * a[7], sy * a[5] + cy * a[8],
  ];
  // Tras cientos de arrastres el error de coma flotante deforma la matriz: se
  // vuelve a ortonormalizar para que la molécula no se achate.
  const x = normalizar([b[0], b[1], b[2]]);
  const zProvisional: Vec3 = [b[6], b[7], b[8]];
  const y = normalizar(cruz(zProvisional, x));
  const z = cruz(x, y);
  return [x[0], x[1], x[2], y[0], y[1], y[2], z[0], z[1], z[2]];
}

export interface Vista {
  readonly rotacion: Rotacion;
  /** 1 = el encuadre inicial. */
  readonly zoom: number;
}

export const ZOOM_MINIMO = 0.15;
export const ZOOM_MAXIMO = 8;

export type Primitiva =
  | { readonly tipo: "linea"; readonly capa: "traza" | "caja" | "sitio" | "ligando"; readonly x1: number; readonly y1: number; readonly x2: number; readonly y2: number; readonly z: number; readonly elemento?: string }
  | { readonly tipo: "disco"; readonly capa: "sitio" | "ligando"; readonly x: number; readonly y: number; readonly z: number; readonly elemento: string }
  | { readonly tipo: "texto"; readonly capa: "etiqueta"; readonly x: number; readonly y: number; readonly z: number; readonly texto: string };

export interface Proyeccion {
  /** De la más lejana a la más cercana: pintar en este orden resuelve qué tapa a qué. */
  readonly primitivas: readonly Primitiva[];
  /** Píxeles por ångström. */
  readonly escala: number;
  /** Profundidad, en Å, que la niebla da por «fondo» y por «frente». */
  readonly fondo: number;
}

export interface OpcionesDeProyeccion {
  readonly etiquetas?: boolean;
  readonly traza?: boolean;
}

/**
 * Proyecta la escena (ortográfica) a un lienzo de `ancho`×`alto` píxeles CSS.
 *
 * La coordenada `z` de cada primitiva va en Å respecto del centro: positiva es
 * hacia el observador. El pintor la usa para ordenar y para la niebla.
 */
export function proyectar(escena: Escena, vista: Vista, ancho: number, alto: number, opciones: OpcionesDeProyeccion = {}): Proyeccion {
  const r = vista.rotacion;
  const [cx, cy, cz] = escena.centro;
  const escala = (0.46 * Math.min(ancho, alto) / escena.radio) * vista.zoom;
  const mx = ancho / 2, my = alto / 2;
  const px = (x: number, y: number, z: number) => mx + (r[0] * (x - cx) + r[1] * (y - cy) + r[2] * (z - cz)) * escala;
  // La pantalla crece hacia abajo: se invierte Y para que «arriba» siga arriba.
  const py = (x: number, y: number, z: number) => my - (r[3] * (x - cx) + r[4] * (y - cy) + r[5] * (z - cz)) * escala;
  const pz = (x: number, y: number, z: number) => r[6] * (x - cx) + r[7] * (y - cy) + r[8] * (z - cz);
  const margen = 40;
  const fuera = (x: number, y: number) => x < -margen || y < -margen || x > ancho + margen || y > alto + margen;

  const primitivas: Primitiva[] = [];
  const segmentos = (datos: Float32Array, capa: "traza" | "caja") => {
    for (let i = 0; i < datos.length; i += 6) {
      const x1 = px(datos[i], datos[i + 1], datos[i + 2]), y1 = py(datos[i], datos[i + 1], datos[i + 2]);
      const x2 = px(datos[i + 3], datos[i + 4], datos[i + 5]), y2 = py(datos[i + 3], datos[i + 4], datos[i + 5]);
      if (fuera(x1, y1) && fuera(x2, y2)) continue;
      const z = (pz(datos[i], datos[i + 1], datos[i + 2]) + pz(datos[i + 3], datos[i + 4], datos[i + 5])) / 2;
      primitivas.push({ tipo: "linea", capa, x1, y1, x2, y2, z });
    }
  };
  if (opciones.traza !== false) segmentos(escena.traza, "traza");
  if (escena.caja) segmentos(escena.caja, "caja");

  // Cada enlace se parte por la mitad y cada mitad toma el color de su átomo.
  const moleculas = (atomos: readonly { x: number; y: number; z: number; elemento: string }[], enlaces: readonly (readonly [number, number])[], capa: "sitio" | "ligando") => {
    const sx = atomos.map((a) => px(a.x, a.y, a.z));
    const sy = atomos.map((a) => py(a.x, a.y, a.z));
    const sz = atomos.map((a) => pz(a.x, a.y, a.z));
    for (const [a, b] of enlaces) {
      if (fuera(sx[a], sy[a]) && fuera(sx[b], sy[b])) continue;
      const xm = (sx[a] + sx[b]) / 2, ym = (sy[a] + sy[b]) / 2, zm = (sz[a] + sz[b]) / 2;
      primitivas.push({ tipo: "linea", capa, x1: sx[a], y1: sy[a], x2: xm, y2: ym, z: (sz[a] + zm) / 2, elemento: atomos[a].elemento });
      primitivas.push({ tipo: "linea", capa, x1: xm, y1: ym, x2: sx[b], y2: sy[b], z: (sz[b] + zm) / 2, elemento: atomos[b].elemento });
    }
    atomos.forEach((atomo, i) => {
      if (fuera(sx[i], sy[i])) return;
      // Del sitio sólo se marcan los heteroátomos: son los que dicen qué puede donar o aceptar.
      if (capa === "sitio" && atomo.elemento === "C") return;
      primitivas.push({ tipo: "disco", capa, x: sx[i], y: sy[i], z: sz[i] + 0.05, elemento: atomo.elemento });
    });
  };
  moleculas(escena.sitio.atomos, escena.sitio.enlaces, "sitio");
  moleculas(escena.ligando.atomos, escena.ligando.enlaces, "ligando");

  primitivas.sort((a, b) => a.z - b.z);

  if (opciones.etiquetas) {
    // Las etiquetas van al final: un nombre tapado por un enlace no se lee.
    const textos: Primitiva[] = [];
    for (const e of escena.sitio.etiquetas) {
      const x = px(e.x, e.y, e.z), y = py(e.x, e.y, e.z);
      if (fuera(x, y)) continue;
      textos.push({ tipo: "texto", capa: "etiqueta", x, y, z: pz(e.x, e.y, e.z), texto: e.texto });
    }
    textos.sort((a, b) => a.z - b.z);
    primitivas.push(...textos);
  }

  return { primitivas, escala, fondo: Math.max(escena.radio, 6) };
}

/** Opacidad por profundidad: lo del fondo se apaga, lo del frente no. */
export function niebla(z: number, fondo: number): number {
  const t = Math.min(1, Math.max(0, (z + fondo) / (2 * fondo)));
  return 0.28 + 0.72 * t;
}
