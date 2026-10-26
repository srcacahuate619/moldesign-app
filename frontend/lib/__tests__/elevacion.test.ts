import { describe, expect, it } from "vitest";
import {
  IDENTIDAD,
  avisosDePose,
  multiplicar,
  pintar,
  prepararEscena,
  proyectar,
  rotX,
  rotY,
  type EspecieDePose,
  type EstereoDePose,
  type ModeloElevacion,
} from "../elevacion";

/** Etanol con un oxígeno cargado: tres átomos, dos enlaces, una etiqueta. */
const modelo: ModeloElevacion = {
  contrato: "elevacion/v1",
  fuente: "pose_vina_top1",
  lienzo: 300,
  svg: "<svg/>",
  atomos: [
    { elemento: "C", carga: 0, hidrogenos: 3, plano: [100, 160], xyz: [102, 158, -20] },
    { elemento: "C", carga: 0, hidrogenos: 2, plano: [150, 130], xyz: [149, 131, 15] },
    { elemento: "O", carga: -1, hidrogenos: 0, plano: [200, 160], xyz: [199, 162, -5] },
  ],
  enlaces: [{ a: 0, b: 1, orden: 1 }, { a: 1, b: 2, orden: 1 }],
  desajuste_px: 2,
  enlace_px: 30,
  razon_enlaces: 0.07,
  fiel: true,
};

const det = (m: ReturnType<typeof rotX>) =>
  m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
  m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
  m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

describe("elevación 2D → 3D", () => {
  const escena = prepararEscena(modelo);

  it("sin elevar, cada átomo está exactamente donde lo dibujó la miniatura", () => {
    const puntos = proyectar(modelo, escena, rotY(1.2), 0);
    puntos.forEach((p, i) => {
      expect(p.x).toBeCloseTo(modelo.atomos[i].plano[0], 6);
      expect(p.y).toBeCloseTo(modelo.atomos[i].plano[1], 6);
      expect(p.z).toBeCloseTo(0, 9);
    });
  });

  it("elevado y sin girar, conserva la forma del modelo alineado, sólo recentrado", () => {
    const puntos = proyectar(modelo, escena, IDENTIDAD, 1);
    const d = (i: number, j: number) => Math.hypot(puntos[i].x - puntos[j].x, puntos[i].y - puntos[j].y);
    const dm = (i: number, j: number) =>
      Math.hypot(modelo.atomos[i].xyz[0] - modelo.atomos[j].xyz[0], modelo.atomos[i].xyz[1] - modelo.atomos[j].xyz[1]);
    expect(d(0, 2)).toBeCloseTo(dm(0, 2) * escena.encoge, 6);
    // La profundidad mantiene el sentido: el átomo 1 sigue delante.
    expect(puntos[1].z).toBeGreaterThan(puntos[0].z);
  });

  it("los giros que componen el visor son rotaciones propias: nunca un espejo", () => {
    let R = IDENTIDAD;
    for (let k = 0; k < 50; k++) R = multiplicar(multiplicar(rotY(0.37 * k), rotX(-0.21 * k)), R);
    expect(det(R)).toBeCloseTo(1, 9);
  });

  it("pinta la etiqueta del heteroátomo con su carga y deja implícitos los carbonos", () => {
    const svg = pintar(modelo, escena, proyectar(modelo, escena, IDENTIDAD, 1));
    expect(svg).toContain(">O−</text>");
    expect(svg.match(/<text/g)).toHaveLength(1);
    expect(svg.match(/<line/g)?.length).toBeGreaterThanOrEqual(2);
  });

  it("los rótulos van encima de todos los enlaces, aunque el átomo quede detrás", () => {
    // El O (átomo 2) queda al fondo al girar media vuelta; su letra no puede
    // quedar tapada por el halo de un enlace que pase por delante.
    const svg = pintar(modelo, escena, proyectar(modelo, escena, rotY(Math.PI), 1));
    expect(svg.lastIndexOf("<line")).toBeLessThan(svg.indexOf("<text"));
  });

  it("escapa lo que no sea un símbolo químico", () => {
    const raro = { ...modelo, atomos: modelo.atomos.map((a, i) => (i === 2 ? { ...a, elemento: "<b>" } : a)) };
    const svg = pintar(raro, prepararEscena(raro), proyectar(raro, prepararEscena(raro), IDENTIDAD, 0));
    expect(svg).not.toContain("<b>");
  });
});

describe("avisos de la pose", () => {
  const conPose = (estereo: Partial<EstereoDePose>, especie: EspecieDePose): ModeloElevacion => ({
    ...modelo,
    pose: {
      registro: 1,
      afinidad_kcal_mol: -6.1,
      sdf_sha256: "0".repeat(64),
      task_id: null,
      estereo: { declarados: 1, conservados: 1, invertidos: [], no_asignables: [], sin_declarar: [], ...estereo },
      especie,
    },
  });
  const sinCarga = { carga_smiles: 0, carga_acoplada: 0 };

  it("una pose que conserva su configuración y su carga no levanta avisos", () => {
    expect(avisosDePose(conPose({}, sinCarga))).toEqual([]);
  });

  it("un centro invertido se señala con su átomo", () => {
    const avisos = avisosDePose(conPose({ conservados: 0, invertidos: [{ atomo: 1, smiles: "S", pose: "R" }] }, sinCarga));
    expect(avisos).toEqual([{ tipo: "estereo_invertido", atomos: [1] }]);
  });

  it("un centro sin declarar y una carga distinta se señalan por separado", () => {
    const avisos = avisosDePose(
      conPose({ declarados: 0, conservados: 0, sin_declarar: [1] }, { carga_smiles: 0, carga_acoplada: 1 }),
    );
    expect(avisos.map((aviso) => aviso.tipo)).toEqual(["estereo_sin_declarar", "especie_cargada"]);
  });

  it("un conformador no tiene avisos de pose", () => {
    expect(avisosDePose(modelo)).toEqual([]);
  });
});

describe("vista «Se acoplará»: lo que cambió la preparación", () => {
  const especie = (cambios: NonNullable<ModeloElevacion["especie_acoplada"]>["cambios"]): ModeloElevacion => ({
    ...modelo,
    fuente: "especie_acoplada",
    especie_acoplada: {
      smiles: "CC[O-]",
      ph: 7.4,
      aviso_de_ph: null,
      protonacion: { aplicada: true, motor: "dimorphite-dl", alternativas: 2, motivo: null },
      tautomero: { modo: "entrada", aplicada: false, alternativas: 1, motivo: null },
      conformador: { semilla: 42, campo_de_fuerza: "MMFF94", convergio: true },
      sdf_sha256: null,
      cambios,
      estereo: { declarados: 0, conservados: 0, invertidos: [], no_asignables: [], sin_declarar: [] },
      contraiones: [],
    },
  });
  const marcas = (svg: string, tipo: string) => (svg.match(new RegExp(`data-cambio="${tipo}"`, "g")) ?? []).length;

  it("marca cada átomo y cada enlace que cambió, y nada más", () => {
    const m = especie({
      atomos: [{ atomo: 2, carga: [0, -1], hidrogenos: [1, 0] }],
      enlaces: [{ a: 2, b: 1, orden: [1, 2] }],
    });
    const escena = prepararEscena(m);
    const svg = pintar(m, escena, proyectar(m, escena, IDENTIDAD, 1));

    expect(marcas(svg, "atomo")).toBe(1);
    expect(marcas(svg, "enlace")).toBe(1);
  });

  it("sin cambios, o en la vista escrita, no hay marcas", () => {
    const sin = especie({ atomos: [], enlaces: [] });
    const escena = prepararEscena(sin);
    expect(pintar(sin, escena, proyectar(sin, escena, IDENTIDAD, 1))).not.toContain("data-cambio");
    expect(pintar(modelo, escena, proyectar(modelo, escena, IDENTIDAD, 1))).not.toContain("data-cambio");
  });
});

describe("detectores, E/Z y validez física", () => {
  it("cada átomo que señala un detector lleva su marca", () => {
    const m: ModeloElevacion = {
      ...modelo,
      detectores: [
        { tipo: "ojiva", codigo: "x", nombre: "x", atomos: [0, 1] },
        { tipo: "pains", codigo: "y", nombre: "y", atomos: [1] },
      ],
    };
    const escena = prepararEscena(m);
    const svg = pintar(m, escena, proyectar(m, escena, IDENTIDAD, 1));

    expect((svg.match(/data-detector="atomo"/g) ?? []).length).toBe(2);
  });

  const conPose = (pose: Partial<NonNullable<ModeloElevacion["pose"]>>): ModeloElevacion => ({
    ...modelo,
    pose: { registro: 1, afinidad_kcal_mol: -6, sdf_sha256: "0".repeat(64), task_id: null, ...pose },
  });
  const estereo = { declarados: 0, conservados: 0, invertidos: [], no_asignables: [], sin_declarar: [] };

  it("un doble enlace al revés es un aviso", () => {
    const avisos = avisosDePose(conPose({
      estereo: { ...estereo, dobles_declarados: 1, dobles_invertidos: [{ enlace: [1, 2], smiles: "E", pose: "Z" }] },
    }));
    expect(avisos).toEqual([{ tipo: "doble_invertido", enlaces: [[1, 2]] }]);
  });

  it("una pose que no pasa la validación física es aviso; una que pasa, no", () => {
    const fisica = (status: string) => ({ status, label: status, motor: "posebusters", comprobaciones_que_fallan: ["clash"] });
    expect(avisosDePose(conPose({ validez_fisica: fisica("failed") })).map((a) => a.tipo)).toEqual(["validez_fisica"]);
    expect(avisosDePose(conPose({ validez_fisica: fisica("passed") }))).toEqual([]);
    expect(avisosDePose(conPose({ validez_fisica: null }))).toEqual([]);
  });
});
