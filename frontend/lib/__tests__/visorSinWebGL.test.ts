/**
 * La escena del visor de respaldo (el que no necesita WebGL).
 *
 * Lo que se prueba es lo que decide qué ve el investigador cuando no hay 3D:
 * qué residuos cuentan como «del sitio», qué se une con qué, y que lo de delante
 * se pinte después que lo de detrás. Todo sin navegador: es geometría.
 */
import { describe, expect, it } from "vitest";

import {
  RADIO_DE_CONTACTO, RADIO_SIN_POSE, SIN_ROTAR,
  construirEscena, girar, leerAtomosDelReceptor, leerLigando, mirarDesde, niebla, proyectar,
  type Rotacion,
} from "../visorSinWebGL";

/** Una línea ATOM/HETATM con las columnas del formato PDB. */
function atomo(registro: "ATOM" | "HETATM", serie: number, nombre: string, residuo: string, cadena: string, numero: number,
  x: number, y: number, z: number, elemento = ""): string {
  const nombre4 = nombre.length < 4 ? ` ${nombre}`.padEnd(4) : nombre;
  return `${registro.padEnd(6)}${String(serie).padStart(5)} ${nombre4} ${residuo.padStart(3)} ${cadena}${String(numero).padStart(4)}    `
    + `${x.toFixed(3).padStart(8)}${y.toFixed(3).padStart(8)}${z.toFixed(3).padStart(8)}  1.00 20.00          ${elemento.padStart(2)}`;
}

/** Tres residuos en fila a lo largo de X, separados 3,8 Å, y un cuarto lejos (un hueco). */
const RECEPTOR = [
  atomo("ATOM", 1, "N", "ALA", "A", 1, -0.5, 1.2, 0, "N"),
  atomo("ATOM", 2, "CA", "ALA", "A", 1, 0, 0, 0, "C"),
  atomo("ATOM", 3, "CB", "ALA", "A", 1, 0, -1.5, 0, "C"),
  atomo("ATOM", 4, "CA", "ASP", "A", 2, 3.8, 0, 0, "C"),
  atomo("ATOM", 5, "CG", "ASP", "A", 2, 3.8, -1.5, 0, "C"),
  atomo("ATOM", 6, "OD1", "ASP", "A", 2, 3.8, -2.7, 0, "O"),
  atomo("ATOM", 7, "HD2", "ASP", "A", 2, 3.8, -3.6, 0, "H"),
  atomo("ATOM", 8, "CA", "GLY", "A", 3, 7.6, 0, 0, "C"),
  atomo("ATOM", 9, "CA", "LEU", "A", 9, 30, 0, 0, "C"),
  atomo("HETATM", 10, "O", "HOH", "A", 101, 3.8, -4, 0, "O"),
  atomo("HETATM", 11, "ZN", "ZN", "A", 201, 50, 50, 50, "ZN"),
  "END",
].join("\n");

/** Un ligando de tres átomos pesados y un hidrógeno, cerca del ASP 2. */
const LIGANDO = [
  "ligando", "  prueba", "",
  "  4  3  0  0  0  0  0  0  0  0999 V2000",
  "    3.8000   -5.5000    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0",
  "    3.8000   -7.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0",
  "    5.1000   -7.7000    0.0000 Cl  0  0  0  0  0  0  0  0  0  0  0  0",
  "    3.8000   -4.6000    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0",
  "  1  2  1  0", "  2  3  1  0", "  1  4  1  0",
  "M  END", "$$$$", "",
].join("\n");

describe("leer el receptor", () => {
  it("deja fuera aguas e hidrógenos y conserva los metales", () => {
    const atomos = leerAtomosDelReceptor(RECEPTOR);
    expect(atomos.some((a) => a.residuo === "HOH")).toBe(false);
    expect(atomos.some((a) => a.elemento === "H")).toBe(false);
    expect(atomos.find((a) => a.residuo === "ZN")?.elemento).toBe("ZN");
    expect(atomos).toHaveLength(9);
  });

  it("sin columna de elemento, el «CA» de una proteína es carbono y no calcio", () => {
    const sinElemento = atomo("ATOM", 1, "CA", "ALA", "A", 1, 0, 0, 0).trimEnd();
    expect(leerAtomosDelReceptor(sinElemento)[0].elemento).toBe("C");
    const calcio = atomo("HETATM", 2, "CA", "CA", "A", 300, 0, 0, 0).trimEnd();
    expect(leerAtomosDelReceptor(calcio)[0].elemento).toBe("CA");
  });

  it("la carga pegada al elemento no forma parte del elemento", () => {
    // «ZN2+» en la columna 77-80: 45 de 446 depósitos lo escriben así.
    const linea = atomo("HETATM", 1, "ZN", "ZN", "A", 1, 0, 0, 0, "ZN") + "2+";
    expect(leerAtomosDelReceptor(linea)[0].elemento).toBe("ZN");
  });

  it("tolera finales de línea de Windows", () => {
    expect(leerAtomosDelReceptor(RECEPTOR.replace(/\n/g, "\r\n"))).toHaveLength(9);
  });
});

describe("leer la pose", () => {
  it("quita los hidrógenos sin descolocar los enlaces de los demás", () => {
    const ligando = leerLigando(LIGANDO);
    expect(ligando.atomos.map((a) => a.elemento)).toEqual(["N", "C", "CL"]);
    expect(ligando.enlaces).toEqual([[0, 1], [1, 2]]);
  });

  it("sólo lee la primera pose de un archivo con varias", () => {
    expect(leerLigando(LIGANDO + LIGANDO).atomos).toHaveLength(3);
  });

  it("lee también el formato V3000", () => {
    const v3000 = [
      "ligando", "  prueba", "", "  0  0  0  0  0  0  0  0  0  0999 V3000",
      "M  V30 BEGIN CTAB", "M  V30 COUNTS 3 2 0 0 0", "M  V30 BEGIN ATOM",
      "M  V30 1 N 3.8 -5.5 0 0", "M  V30 2 C 3.8 -7 0 0", "M  V30 3 H 3.8 -4.6 0 0",
      "M  V30 END ATOM", "M  V30 BEGIN BOND", "M  V30 1 1 1 2", "M  V30 2 1 1 3", "M  V30 END BOND",
      "M  V30 END CTAB", "M  END", "$$$$",
    ].join("\n");
    const ligando = leerLigando(v3000);
    expect(ligando.atomos.map((a) => a.elemento)).toEqual(["N", "C"]);
    expect(ligando.enlaces).toEqual([[0, 1]]);
  });

  it("un texto que no es un SDF da un ligando vacío, no una excepción", () => {
    expect(leerLigando("esto no es un SDF").atomos).toEqual([]);
  });
});

describe("construir la escena", () => {
  it("sin receptor ni pose no hay escena", () => {
    expect(construirEscena({})).toBeNull();
    expect(construirEscena({ pdb: "", sdf: "   " })).toBeNull();
  });

  it("con pose, el sitio son los residuos a la distancia de contacto, y se dice que el criterio es la pose", () => {
    const escena = construirEscena({ pdb: RECEPTOR, sdf: LIGANDO });
    expect(escena).not.toBeNull();
    expect(escena!.criterioDelSitio).toBe("ligando");
    // El N del ligando está a 2,8 Å del OD1 del ASP 2; ALA 1 y GLY 3 quedan a más de 4,5 Å.
    expect(escena!.sitio.etiquetas.map((e) => e.texto)).toEqual(["ASP2"]);
    expect(escena!.cuenta.residuosDelSitio).toBe(1);
    // El residuo entra ENTERO, no sólo el átomo que toca.
    expect(escena!.sitio.atomos.map((a) => a.nombre)).toEqual(["CA", "CG", "OD1"]);
    expect(RADIO_DE_CONTACTO).toBe(4.5);
  });

  it("une por distancia los átomos de un mismo residuo y nada más", () => {
    const escena = construirEscena({ pdb: RECEPTOR, sdf: LIGANDO })!;
    // CA–CG (1,5 Å) y CG–OD1 (1,2 Å); CA–OD1 (2,7 Å) no es un enlace.
    expect(escena.sitio.enlaces).toEqual([[0, 1], [1, 2]]);
  });

  it("el esqueleto une Cα vecinos y no salta los huecos", () => {
    const escena = construirEscena({ pdb: RECEPTOR })!;
    // ALA1–ASP2 y ASP2–GLY3; de GLY3 a LEU9 hay 22 Å: falta cadena y no se inventa.
    expect(escena.traza.length / 6).toBe(2);
    expect(escena.criterioDelSitio).toBe("ninguno");
    expect(escena.sitio.atomos).toHaveLength(0);
  });

  it("sin pose pero con caja, el sitio es el corazón de la caja, y se dice", () => {
    // La caja mide 60 Å y contiene los cuatro residuos, pero sólo se dibujan los
    // que están a 8 Å o menos de su centro: la caja entera es una maraña (207
    // residuos en 8HFI con la caja por defecto).
    const escena = construirEscena({ pdb: RECEPTOR, caja: { centerX: 0, centerY: 0, centerZ: 0, sizeX: 60, sizeY: 60, sizeZ: 60 } })!;
    expect(escena.criterioDelSitio).toBe("caja");
    expect(RADIO_SIN_POSE).toBe(8);
    // ALA1 (en el centro), ASP2 (a 3,8 Å) y GLY3 (a 7,6 Å); LEU9 está a 30 Å.
    expect(escena.sitio.etiquetas.map((e) => e.texto)).toEqual(["ALA1", "ASP2", "GLY3"]);
    expect(escena.caja!.length / 6).toBe(12);
    expect(escena.centro).toEqual([0, 0, 0]);
  });

  it("encuadra la pose, no el receptor entero, y mira desde fuera hacia el sitio", () => {
    const escena = construirEscena({ pdb: RECEPTOR, sdf: LIGANDO })!;
    expect(escena.centro[1]).toBeCloseTo(-6.73, 1);
    expect(escena.radio).toBeLessThan(escena.radioTotal);
    // El ligando está por debajo (−Y) del receptor: se mira desde ahí.
    expect(escena.haciaElObservador![1]).toBeLessThan(-0.3);
  });

  it("con el sitio en dos cadenas, la etiqueta lleva la cadena", () => {
    const dosCadenas = [
      atomo("ATOM", 1, "CA", "ASP", "A", 2, 3.8, -3, 0, "C"),
      atomo("ATOM", 2, "CA", "ASP", "B", 2, 3.8, -8, 2, "C"),
    ].join("\n");
    const escena = construirEscena({ pdb: dosCadenas, sdf: LIGANDO })!;
    expect(escena.sitio.etiquetas.map((e) => e.texto).sort()).toEqual(["A:ASP2", "B:ASP2"]);
  });

  it("un ligando sin receptor también se puede mirar", () => {
    const escena = construirEscena({ sdf: LIGANDO })!;
    expect(escena.ligando.atomos).toHaveLength(3);
    expect(escena.traza).toHaveLength(0);
  });
});

describe("la vista", () => {
  const esOrtonormal = (r: Rotacion) => {
    const filas = [[r[0], r[1], r[2]], [r[3], r[4], r[5]], [r[6], r[7], r[8]]];
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
      const punto = filas[i][0] * filas[j][0] + filas[i][1] * filas[j][1] + filas[i][2] * filas[j][2];
      expect(punto).toBeCloseTo(i === j ? 1 : 0, 6);
    }
  };

  it("mirar desde una dirección la deja apuntando al observador", () => {
    const r = mirarDesde([0, -1, 0]);
    expect([r[6], r[7], r[8]]).toEqual([0, -1, 0]);
    esOrtonormal(r);
    expect(mirarDesde(null)).toEqual(SIN_ROTAR);
  });

  it("mil arrastres seguidos no deforman la molécula", () => {
    let r: Rotacion = SIN_ROTAR;
    for (let i = 0; i < 1000; i++) r = girar(r, 0.013 * ((i % 7) - 3), 0.021 * ((i % 5) - 2));
    esOrtonormal(r);
  });

  it("girar un cuarto de vuelta lleva lo de la derecha al frente", () => {
    const r = girar(SIN_ROTAR, -Math.PI / 2, 0);
    // El eje X del mundo queda ahora en la fila que mira al observador.
    expect(r[6]).toBeCloseTo(1, 6);
  });
});

describe("proyectar", () => {
  const escena = construirEscena({ pdb: RECEPTOR, sdf: LIGANDO, caja: { centerX: 3.8, centerY: -6, centerZ: 0, sizeX: 10, sizeY: 10, sizeZ: 10 } })!;

  it("ordena de atrás hacia delante: pintar en ese orden resuelve qué tapa a qué", () => {
    const { primitivas } = proyectar(escena, { rotacion: girar(SIN_ROTAR, 0.6, 0.4), zoom: 1 }, 640, 480);
    const profundidades = primitivas.map((p) => p.z);
    expect(profundidades).toEqual([...profundidades].sort((a, b) => a - b));
    expect(primitivas.some((p) => p.capa === "ligando" && p.tipo === "disco")).toBe(true);
  });

  it("las etiquetas van al final, por encima de todo, y sólo si se piden", () => {
    const vista = { rotacion: SIN_ROTAR, zoom: 1 };
    const sin = proyectar(escena, vista, 640, 480);
    expect(sin.primitivas.some((p) => p.tipo === "texto")).toBe(false);
    const con = proyectar(escena, vista, 640, 480, { etiquetas: true });
    expect(con.primitivas[con.primitivas.length - 1]).toMatchObject({ tipo: "texto", texto: "ASP2" });
  });

  it("el centro de la escena cae en el centro del lienzo y acercar agranda", () => {
    const vista = { rotacion: SIN_ROTAR, zoom: 1 };
    const base = proyectar(escena, vista, 640, 480);
    const cerca = proyectar(escena, { ...vista, zoom: 2 }, 640, 480);
    expect(cerca.escala).toBeCloseTo(base.escala * 2, 6);
    const centroide = base.primitivas.filter((p) => p.tipo === "disco" && p.capa === "ligando") as { x: number; y: number }[];
    const mx = centroide.reduce((s, p) => s + p.x, 0) / centroide.length;
    const my = centroide.reduce((s, p) => s + p.y, 0) / centroide.length;
    expect(mx).toBeCloseTo(320, 0);
    expect(my).toBeCloseTo(240, 0);
  });

  it("del sitio sólo se marcan los heteroátomos; del ligando, todos", () => {
    const { primitivas } = proyectar(escena, { rotacion: SIN_ROTAR, zoom: 1 }, 640, 480);
    const discos = primitivas.filter((p) => p.tipo === "disco") as { capa: string; elemento: string }[];
    expect(discos.filter((d) => d.capa === "sitio").map((d) => d.elemento)).toEqual(["O"]);
    expect(discos.filter((d) => d.capa === "ligando")).toHaveLength(3);
  });

  it("lo que queda fuera del lienzo no se manda a pintar", () => {
    const lejos = proyectar(escena, { rotacion: SIN_ROTAR, zoom: 8 }, 200, 200);
    const todo = proyectar(escena, { rotacion: SIN_ROTAR, zoom: 0.15 }, 200, 200);
    expect(lejos.primitivas.length).toBeLessThan(todo.primitivas.length);
  });

  it("la niebla apaga el fondo sin borrar nada", () => {
    expect(niebla(-100, 10)).toBeCloseTo(0.28, 6);
    expect(niebla(100, 10)).toBeCloseTo(1, 6);
    expect(niebla(0, 10)).toBeGreaterThan(niebla(-5, 10));
  });
});
