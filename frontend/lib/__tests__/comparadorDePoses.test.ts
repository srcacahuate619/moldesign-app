// =====================================================================
// Comparador 3D entre corridas: qué se compara y qué distancia se pide
// =====================================================================
//
// 1. Las fuentes son las corridas terminadas del caso, sin la actual.
// 2. El SDF manda en cuántas poses hay; el resultado sólo pone la energía y los controles (y sin él no se inventan).
// 3. La distancia se pide al endpoint que corresponde: misma corrida, misma molécula o ligandos distintos.
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ same: vi.fn(), run: vi.fn(), analog: vi.fn(), matches: vi.fn(), interactions: vi.fn() }));
vi.mock("../proApi", () => ({
  getSameRunPoseComparison: api.same,
  getRunPoseComparison: api.run,
  getAnalogPoseComparison: api.analog,
  getPoseMatches: api.matches,
}));
vi.mock("../api", () => ({ getInteractions: api.interactions }));

import {
  coincidenciasDePoses,
  compararContactos,
  etiquetaDeCorrida,
  fuentesDelCaso,
  lineasDeContactos,
  medirDistancia,
  posesDeLaCorrida,
  resumenDeLaComparacion,
  textoSinDistancia,
} from "../comparadorDePoses";
import type { CaseRun } from "../cases/types";

const corrida = (taskId: string, moleculeId: string | undefined, extra: Partial<CaseRun> = {}): CaseRun => ({
  taskId, moleculeId, executionState: "completed", startedAt: "2026-11-01T10:00:00.000Z", ...extra,
});
const sdf = (n: number) => Array.from({ length: n }, (_, i) => `p${i}\n\nM  END\n$$$$\n`).join("");
const fuente = (taskId: string, moleculeId: string) => ({ taskId, moleculeId, etiqueta: taskId });

beforeEach(() => { api.same.mockReset(); api.run.mockReset(); api.analog.mockReset(); api.matches.mockReset(); api.interactions.mockReset(); });

describe("fuentesDelCaso", () => {
  it("deja las corridas terminadas con molécula, sin la actual y con la más reciente primero", () => {
    const libro = [
      corrida("a", "m1"), corrida("b", "m1"), corrida("c", "m2"),
      corrida("falla", "m1", { executionState: "failed" }), corrida("sin-mol", undefined), corrida("actual", "m1"),
    ];
    const fuentes = fuentesDelCaso(libro, "actual", (run) => `etq-${run.taskId}`);
    expect(fuentes.map((f) => f.taskId)).toEqual(["c", "b", "a"]);
    expect(fuentes[0]).toEqual({ taskId: "c", moleculeId: "m2", etiqueta: "etq-c" });
  });

  it("sin libro no hay nada que comparar", () => {
    expect(fuentesDelCaso(undefined, "x", () => "")).toEqual([]);
  });

  it("con una molécula pedida sólo quedan las corridas de esa molécula (Poses y controles no sale de ella)", () => {
    const libro = [
      corrida("a", "m1"), corrida("b", "m2"), corrida("c", "m1"), corrida("sin-mol", undefined),
      corrida("falla", "m1", { executionState: "failed" }), corrida("actual", "m1"),
    ];
    expect(fuentesDelCaso(libro, "actual", (run) => run.taskId, "m1").map((f) => f.taskId)).toEqual(["c", "a"]);
    expect(fuentesDelCaso(libro, "actual", (run) => run.taskId, "m3")).toEqual([]);
    // Sin molécula pedida (o vacía) no filtra: es el comportamiento del SAR, que compara entre análogos.
    expect(fuentesDelCaso(libro, "actual", (run) => run.taskId, null).map((f) => f.taskId)).toEqual(["c", "b", "a"]);
  });
});

describe("etiquetaDeCorrida", () => {
  it("lleva ligando y exhaustividad, y no revienta sin protocolo ni fecha válida", () => {
    const t = (key: string, p: Record<string, string | number> = {}) => `${key}|${p.ligando}|${p.e}`;
    expect(etiquetaDeCorrida(corrida("a", "m", { ligandSmiles: "CCO", protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1 } }), t, "es"))
      .toBe("pn_cmp3d_opcion|CCO|8");
    expect(etiquetaDeCorrida(corrida("a", "m", { startedAt: "no-es-fecha" }), t, "es")).toBe("pn_cmp3d_opcion|—|—");
    expect(etiquetaDeCorrida(corrida("a", "m", { ligandSmiles: "C".repeat(40) }), t, "es")).toContain("…");
  });
});

describe("posesDeLaCorrida", () => {
  it("el SDF fija cuántas poses hay; sin resultado salen sin energía y sin validez", () => {
    const poses = posesDeLaCorrida(sdf(3), null);
    expect(poses.map((p) => p.rank)).toEqual([1, 2, 3]);
    expect(poses.every((p) => p.affinity === null && p.physicallyValid === false)).toBe(true);
  });

  it("con resultado pone la energía por rango, y sólo `passed` es válida", () => {
    const resultado = {
      docking_poses: [{ rank: 1, affinity: -7.1 }, { rank: 2, affinity: -6.5 }],
      structural_evidence: { poses: [{ rank: 1, estado: "PASA", checks: [] }] },
    };
    const poses = posesDeLaCorrida(sdf(3), resultado);
    expect(poses[0].affinity).toBe(-7.1);
    expect(poses[1].affinity).toBe(-6.5);
    expect(poses[2].affinity).toBeNull();
    expect(poses.filter((p) => p.physicallyValid)).toHaveLength(poses.filter((p) => p.physicalStatus === "passed").length);
  });
});

describe("medirDistancia", () => {
  it("misma corrida: pide las dos poses de esa corrida", async () => {
    api.same.mockResolvedValue({
      task_id: "t1", left: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, right: { rank: 2, found: true, vina_affinity_kcal_mol: -6.5 },
      difference: { right_minus_left_vina_kcal_mol: 0.5, pose_rmsd_between_poses: { available: true, reason_code: null, rmsd_angstrom: 2.3 } },
    });
    const m = await medirDistancia({ fuente: fuente("t1", "m"), rank: 1 }, { fuente: fuente("t1", "m"), rank: 2 });
    expect(api.same).toHaveBeenCalledWith("t1", 1, 2);
    expect(m).toMatchObject({ tipo: "misma_corrida", disponible: true, rmsd: 2.3, diferenciaVina: 0.5, diferenciaComparable: true });
  });

  it("misma molécula, otra corrida: pide el endpoint de corridas con sus rangos y conserva lo que difiere", async () => {
    api.run.mockResolvedValue({
      frame: "same", a: { rank: 3, found: true, vina_affinity_kcal_mol: -6 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -7 },
      difference: { b_minus_a_vina_kcal_mol: -1, pose_rmsd_between_runs: { available: true, reason_code: null, rmsd_angstrom: 0.4, heavy_atoms: 10 } },
      protocol_differences: [{ field: "seed", a: 1, b: 2 }],
    });
    const m = await medirDistancia({ fuente: fuente("t1", "m"), rank: 3 }, { fuente: fuente("t0", "m"), rank: 1 });
    expect(api.run).toHaveBeenCalledWith("t1", "t0", 3, 1);
    expect(m).toMatchObject({ tipo: "misma_molecula", rmsd: 0.4, marco: "same", diferenciaComparable: false });
    expect(m.diferencias).toEqual([{ field: "seed", a: 1, b: 2 }]);
  });

  it("misma molécula con otro receptor: no hay distancia y llega el motivo", async () => {
    api.run.mockResolvedValue({
      frame: "different", a: { rank: 1, found: true, vina_affinity_kcal_mol: -6 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -7 },
      difference: { b_minus_a_vina_kcal_mol: -1, pose_rmsd_between_runs: { available: false, reason_code: "DIFFERENT_RECEPTOR", rmsd_angstrom: null, heavy_atoms: null } },
      protocol_differences: [],
    });
    const m = await medirDistancia({ fuente: fuente("t1", "m"), rank: 1 }, { fuente: fuente("t0", "m"), rank: 1 });
    expect(m).toMatchObject({ disponible: false, rmsd: null, motivo: "DIFFERENT_RECEPTOR", marco: "different" });
  });

  it("ligandos distintos: pide el núcleo común y enseña su tamaño; el delta de Vina sigue la comparabilidad", async () => {
    api.analog.mockResolvedValue({
      frame: "same", a: { rank: 1, found: true, vina_affinity_kcal_mol: -6.9 }, b: { rank: 2, found: true, vina_affinity_kcal_mol: -7.4 },
      difference: { b_minus_a_vina_kcal_mol: -0.5, affinity_delta_comparable: false, core_rmsd: { available: true, reason_code: null, rmsd_angstrom: 0.8, core_heavy_atoms: 9, core_fraction_of_smaller: 0.9 } },
      protocol_differences: [{ field: "exhaustiveness", a: 8, b: 32 }],
    });
    const m = await medirDistancia({ fuente: fuente("t1", "base"), rank: 1 }, { fuente: fuente("t9", "analogo"), rank: 2 });
    expect(api.analog).toHaveBeenCalledWith("t1", "t9", 1, 2);
    expect(m).toMatchObject({ tipo: "nucleo_comun", rmsd: 0.8, nucleo: { atomos: 9, fraccion: 0.9 }, diferenciaComparable: false });
  });
});


// ── Átomos del núcleo ─────────────────────────────────────────────────────────────────────────────────────────────

describe("átomos del núcleo común", () => {
  const analogo = (nucleo: Record<string, unknown>) => ({
    frame: "same", a: { rank: 1, found: true, vina_affinity_kcal_mol: -6.9 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -7.4 },
    difference: { b_minus_a_vina_kcal_mol: -0.5, affinity_delta_comparable: true, core_rmsd: nucleo },
    protocol_differences: [],
  });

  it("los pasa de izquierda a derecha cuando se midió el núcleo", async () => {
    api.analog.mockResolvedValue(analogo({
      available: true, reason_code: null, rmsd_angstrom: 0.8, core_heavy_atoms: 9, core_fraction_of_smaller: 0.9,
      core_atoms: { a: [0, 1, 2], b: [0, 1, 5], index_basis: "sdf_atom_index_zero_based" },
    }));
    const m = await medirDistancia({ fuente: fuente("t1", "base"), rank: 1 }, { fuente: fuente("t9", "analogo"), rank: 1 });
    expect(m.atomosDelNucleo).toEqual({ izquierda: [0, 1, 2], derecha: [0, 1, 5] });
  });

  it("sin distancia (núcleo pequeño, otro receptor) no hay átomos que resaltar", async () => {
    api.analog.mockResolvedValue(analogo({ available: false, reason_code: "CORE_TOO_SMALL", rmsd_angstrom: null, core_heavy_atoms: 3 }));
    const m = await medirDistancia({ fuente: fuente("t1", "base"), rank: 1 }, { fuente: fuente("t9", "analogo"), rank: 1 });
    expect(m.atomosDelNucleo).toBeNull();
  });

  it("la misma molécula no tiene núcleo distinto de ella misma: no se resalta nada", async () => {
    api.run.mockResolvedValue({
      frame: "same", a: { rank: 1, found: true }, b: { rank: 1, found: true },
      difference: { b_minus_a_vina_kcal_mol: 0, pose_rmsd_between_runs: { available: true, reason_code: null, rmsd_angstrom: 0.4, heavy_atoms: 10 } },
      protocol_differences: [],
    });
    const m = await medirDistancia({ fuente: fuente("t1", "m"), rank: 1 }, { fuente: fuente("t0", "m"), rank: 1 });
    expect(m.atomosDelNucleo).toBeNull();
  });
});

// ── Qué pose de la otra evaluación se parece más ─────────────────────────────────────────────────────────────────

describe("coincidenciasDePoses", () => {
  const respuesta = (extra: Record<string, unknown> = {}) => ({
    task_a: "t1", task_b: "t0", rank_a: 2, kind: "molecule", frame: "same", available: true, reason_code: null,
    matches: [
      { rank: 1, available: true, reason_code: null, rmsd_angstrom: 3.2 },
      { rank: 2, available: false, reason_code: "POSE_UNREADABLE", rmsd_angstrom: null },
      { rank: 3, available: true, reason_code: null, rmsd_angstrom: 0.4 },
    ],
    closest_rank: 3, closest_rmsd_angstrom: 0.4, ...extra,
  });

  it("pide la pose elegida contra la otra evaluación y devuelve la distancia de cada pose y la más cercana", async () => {
    api.matches.mockResolvedValue(respuesta());
    const r = await coincidenciasDePoses({ fuente: fuente("t1", "m"), rank: 2 }, fuente("t0", "m"));
    expect(api.matches).toHaveBeenCalledWith("t1", "t0", 2);
    expect(r).toEqual({
      tipo: "molecule",
      poses: [{ rank: 1, rmsd: 3.2 }, { rank: 2, rmsd: null }, { rank: 3, rmsd: 0.4 }],
      masCercana: 3,
    });
  });

  it("dentro de una misma evaluación no hay nada que preguntar", async () => {
    expect(await coincidenciasDePoses({ fuente: fuente("t1", "m"), rank: 1 }, fuente("t1", "m"))).toBeNull();
    expect(api.matches).not.toHaveBeenCalled();
  });

  it("si el backend se abstiene no se enseña nada", async () => {
    api.matches.mockResolvedValue(respuesta({ available: false, reason_code: "DIFFERENT_RECEPTOR", matches: [], closest_rank: null }));
    expect(await coincidenciasDePoses({ fuente: fuente("t1", "m"), rank: 1 }, fuente("t0", "m"))).toBeNull();
  });
});

// ── Contactos que una pose gana o pierde ─────────────────────────────────────────────────────────────────────────

describe("compararContactos", () => {
  const dato = (type: string, name: string, number: number, distance: number, chain = "A") => ({
    type, residue: `${name}${number}${chain}`, residue_name: name, residue_number: number, residue_chain: chain,
    distance, angle: null, strength: null, ligand_atom: "O1", protein_atom: "OG",
    ligand_coords: { x: 0, y: 0, z: number }, protein_coords: { x: 2, y: 0, z: number },
  });
  const informe = (interactions: unknown[], extra: Record<string, unknown> = {}) => ({
    engine: "prolif:2.0.3", protein_source_sha256: "rec", contact_coverage: "first_match_per_type_and_residue",
    hydrogen_model: "rdkit_add_hs_coordinates", interactions, ...extra,
  });
  const izq = { fuente: fuente("t1", "m1"), rank: 1 };
  const der = { fuente: fuente("t2", "m2"), rank: 3 };

  it("los pone frente a frente por tipo y residuo: sólo izquierda, sólo derecha y los de las dos", async () => {
    api.interactions
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9), dato("hydrophobic", "LEU", 20, 3.8)]))
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 3.1), dato("salt_bridge", "ASP", 30, 3.4)]));
    const r = await compararContactos(izq, der);
    expect(api.interactions).toHaveBeenNthCalledWith(1, "m1", 1, "t1");
    expect(api.interactions).toHaveBeenNthCalledWith(2, "m2", 3, "t2");
    if (!r.disponible) throw new Error("debía haber contactos");
    expect(r.contactos.map((c) => [c.residuo, c.tipo, c.estado])).toEqual([
      ["SER10A", "hbond", "ambas"],
      ["LEU20A", "hydrophobic", "solo_izquierda"],
      ["ASP30A", "salt_bridge", "solo_derecha"],
    ]);
    expect(r.contactos[0].izquierda?.distancia).toBe(2.9);
    expect(r.contactos[0].derecha?.distancia).toBe(3.1);
    expect(r.motor).toBe("prolif:2.0.3");
    expect(r.cobertura).toBe("first_match_per_type_and_residue");
  });

  it("el mismo residuo con otro tipo de contacto no es el mismo contacto", async () => {
    api.interactions
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9)]))
      .mockResolvedValueOnce(informe([dato("hydrophobic", "SER", 10, 3.9)]));
    const r = await compararContactos(izq, der);
    if (!r.disponible) throw new Error("debía haber contactos");
    expect(r.contactos.map((c) => c.estado).sort()).toEqual(["solo_derecha", "solo_izquierda"]);
  });

  it("la cadena cuenta: el mismo número en otra cadena es otro residuo", async () => {
    api.interactions
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9, "A")]))
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9, "B")]));
    const r = await compararContactos(izq, der);
    if (!r.disponible) throw new Error("debía haber contactos");
    expect(r.contactos).toHaveLength(2);
  });

  it("con dos contactos del mismo tipo y residuo en un lado se queda el más cercano", async () => {
    api.interactions
      .mockResolvedValueOnce(informe([dato("hydrophobic", "LEU", 20, 4.2), dato("hydrophobic", "LEU", 20, 3.6)]))
      .mockResolvedValueOnce(informe([]));
    const r = await compararContactos(izq, der);
    if (!r.disponible) throw new Error("debía haber contactos");
    expect(r.contactos).toHaveLength(1);
    expect(r.contactos[0].izquierda?.distancia).toBe(3.6);
  });

  it("con otro receptor preparado no se compara, aunque los dos análisis hayan salido", async () => {
    api.interactions
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9)]))
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9)], { protein_source_sha256: "otro" }));
    expect(await compararContactos(izq, der)).toEqual({ disponible: false, motivo: "RECEPTORES_DISTINTOS" });
  });

  it("con otro motor (uno cayó al respaldo por distancias) no se compara", async () => {
    api.interactions
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9)]))
      .mockResolvedValueOnce(informe([dato("polar_contact", "SER", 10, 3.0)], { engine: "distance_fallback" }));
    expect(await compararContactos(izq, der)).toEqual({ disponible: false, motivo: "MOTORES_DISTINTOS" });
  });

  it("si uno de los dos análisis no se pudo leer, se dice", async () => {
    api.interactions.mockResolvedValueOnce(informe([])).mockResolvedValueOnce(null);
    expect(await compararContactos(izq, der)).toEqual({ disponible: false, motivo: "LECTURA_FALLIDA" });
  });
});

describe("lineasDeContactos", () => {
  const colores = { izquierda: "#L", derecha: "#R", compartido: "#C" };
  const punto = (z: number) => ({ x: 0, y: 0, z });
  const lado = (z: number) => ({ distancia: 3, angulo: null, atomoLigando: null, atomoReceptor: null, ligando: punto(z), receptor: punto(z + 3) });
  const contactos = [
    { clave: "a", tipo: "hbond", residuo: "SER1A", numero: 1, estado: "solo_izquierda" as const, izquierda: lado(1), derecha: null },
    { clave: "b", tipo: "hbond", residuo: "ASP2A", numero: 2, estado: "ambas" as const, izquierda: lado(2), derecha: lado(20) },
    { clave: "c", tipo: "hbond", residuo: "LEU3A", numero: 3, estado: "solo_derecha" as const, izquierda: null, derecha: lado(3) },
  ];

  it("cada visor dibuja los contactos de SU pose: los suyos de color y los compartidos en gris", () => {
    expect(lineasDeContactos(contactos, "izquierda", colores).map((l) => [l.color, l.start.z])).toEqual([["#L", 1], ["#C", 2]]);
    expect(lineasDeContactos(contactos, "derecha", colores).map((l) => [l.color, l.start.z])).toEqual([["#C", 20], ["#R", 3]]);
  });

  it("en una sola escena entran los tres, y un contacto compartido se dibuja una vez", () => {
    const todas = lineasDeContactos(contactos, "ambos", colores);
    expect(todas.map((l) => l.color)).toEqual(["#L", "#C", "#R"]);
  });
});

// ── El resumen para pegar en un informe ───────────────────────────────────────────────────────────────────────────

describe("resumenDeLaComparacion", () => {
  const t = (key: string, p: Record<string, string | number> = {}) =>
    `${key}${Object.keys(p).length ? `[${Object.entries(p).map(([k, v]) => `${k}=${v}`).join(",")}]` : ""}`;
  const medida = (extra: Record<string, unknown> = {}) => ({
    tipo: "misma_molecula" as const, disponible: true, rmsd: 0.42, motivo: null, nucleo: null, vinaIzquierda: -7, vinaDerecha: -6.5,
    diferenciaVina: 0.5, diferenciaComparable: true, marco: "same" as const, diferencias: [{ field: "seed", a: 42, b: 7 }],
    atomosDelNucleo: null, ...extra,
  });
  const lados = {
    izquierda: { etiqueta: "Corrida A", taskId: "tA", rank: 1, vina: -7 },
    derecha: { etiqueta: "Corrida B", taskId: "tB", rank: 3, vina: -6.5 },
  };

  it("dice qué se compara, la distancia, lo que difiere y los límites", () => {
    const texto = resumenDeLaComparacion({ t, ...lados, medida: medida(), contactos: null });
    expect(texto).toContain("Corrida A");
    expect(texto).toContain("(tA)");
    expect(texto).toContain("pn_cmp3d_rmsd: 0.42 Å");
    expect(texto).toContain("pn_cmp3d_res_receptor_mismo");
    expect(texto).toContain("pn_cmp_f_seed: 42 → 7");
    expect(texto.trim().endsWith("pn_cmp3d_res_aviso")).toBe(true);
  });

  it("sin distancia dice por qué, y con ligandos distintos avisa de que es el núcleo", () => {
    const sin = medida({ tipo: "nucleo_comun", disponible: false, rmsd: null, motivo: "DIFFERENT", marco: "different", diferenciaComparable: false });
    const texto = resumenDeLaComparacion({ t, ...lados, medida: sin, contactos: null });
    expect(texto).toContain("pn_cmp_sin_rmsd_distinto");
    expect(texto).toContain("pn_cmp3d_otro_ligando");
    expect(texto).toContain("pn_ana_delta_no_comparable");
    expect(texto).not.toContain("pn_cmp3d_res_receptor_mismo");
  });

  it("los contactos, si se calcularon, van agrupados con su motor", () => {
    const lado = { distancia: 3, angulo: null, atomoLigando: null, atomoReceptor: null, ligando: { x: 0, y: 0, z: 0 }, receptor: { x: 1, y: 0, z: 0 } };
    const contactos = {
      disponible: true as const, motor: "prolif:2.0", cobertura: null, hidrogenos: null,
      contactos: [
        { clave: "a", tipo: "hbond", residuo: "SER1A", numero: 1, estado: "solo_izquierda" as const, izquierda: lado, derecha: null },
        { clave: "b", tipo: "hydrophobic", residuo: "LEU2A", numero: 2, estado: "ambas" as const, izquierda: lado, derecha: lado },
      ],
    };
    const texto = resumenDeLaComparacion({ t, ...lados, medida: medida(), contactos });
    expect(texto).toContain("pn_cmp3d_contactos_solo_izq[n=1]\n  SER1A (cm_type_hbond)");
    expect(texto).toContain("pn_cmp3d_contactos_solo_der[n=0]\n  pn_cmp3d_contactos_ninguno");
    expect(texto).toContain("pn_cmp3d_contactos_ambas[n=1]\n  LEU2A (cm_type_hydrophobic)");
    expect(texto).toContain("pn_cmp3d_contactos_nota[motor=prolif:2.0]");
  });

  it("textoSinDistancia calla cuando hay distancia", () => {
    expect(textoSinDistancia(medida(), t)).toBeNull();
  });
});
