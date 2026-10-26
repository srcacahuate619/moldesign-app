import { describe, expect, it } from "vitest";
import { comparacionConElSello, type CampoDelSello, type ParametrosDeCorrida } from "../seccionCatalogo";
import { verificacionDePrueba as sello } from "./fixtures/verificacionReceptor";

const completa: ParametrosDeCorrida = {
  receptor_sha256: sello.receptor_sha256,
  docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 },
};
const conCampo = (campo: CampoDelSello, valor: unknown): ParametrosDeCorrida => campo === "receptor"
  ? { ...completa, receptor_sha256: valor }
  : { ...completa, docking_protocol: { ...completa.docking_protocol, [campo]: valor } };

describe("comparación con el sello: mismos campos y orden que el dossier", () => {
  it.each([
    ["receptor", sello.receptor_sha256, "otro"], ["exhaustiveness", 8, 32], ["num_poses", 9, 10], ["seed", 42, 43],
  ] as Array<[CampoDelSello, unknown, unknown]>)("%s distingue igual, distinto y sin declarar", (campo, igual, distinto) => {
    expect(comparacionConElSello(conCampo(campo, igual), sello)).toEqual({ difiere: [], sinDeclarar: [] });
    expect(comparacionConElSello(conCampo(campo, distinto), sello)).toEqual({ difiere: [campo], sinDeclarar: [] });
    for (const ausencia of [undefined, null]) {
      expect(comparacionConElSello(conCampo(campo, ausencia), sello)).toEqual({ difiere: [], sinDeclarar: [campo] });
    }
  });
  it.each([undefined, null])("sin corrida (%j) no compara", corrida => {
    expect(comparacionConElSello(corrida, sello)).toEqual({ difiere: [], sinDeclarar: [] });
  });
  it("una corrida vacía declara la ausencia de los cuatro campos en orden", () => {
    expect(comparacionConElSello({}, sello)).toEqual({ difiere: [], sinDeclarar: ["receptor", "exhaustiveness", "num_poses", "seed"] });
  });
  it.each([
    [sello.receptor_sha256, "otro"], ["otro", sello.receptor_sha256],
  ])("cualquiera de los hashes contradictorios invalida la comparación", (raiz, procedencia) => {
    expect(comparacionConElSello({ ...completa, receptor_sha256: raiz, docking_protocol: { ...completa.docking_protocol, execution_provenance: { receptor_sha256: procedencia } } }, sello)).toEqual({ difiere: ["receptor"], sinDeclarar: [] });
  });
  it("lee el hash de procedencia y la semilla alternativa sin inventar campos", () => {
    expect(comparacionConElSello({ receptor_sha256: null, vina_random_seed: 42, docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: null, execution_provenance: { receptor_sha256: sello.receptor_sha256 } } }, sello)).toEqual({ difiere: [], sinDeclarar: [] });
    expect(comparacionConElSello({ ...completa, vina_random_seed: 43 }, sello)).toEqual({ difiere: ["seed"], sinDeclarar: [] });
  });
  it("conserva a la vez diferencias y ausencias, con orden estable", () => {
    expect(comparacionConElSello({ receptor_sha256: "otro", docking_protocol: { num_poses: 10 } }, sello)).toEqual({ difiere: ["receptor", "num_poses"], sinDeclarar: ["exhaustiveness", "seed"] });
  });
});
