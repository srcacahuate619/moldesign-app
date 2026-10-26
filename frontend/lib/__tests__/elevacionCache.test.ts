import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchBackend } from "../backendFetch";
import { ErrorDeElevacion, elevacionDelEditor, modeloDelEditorEnCache, type ModeloElevacion } from "../elevacion";

vi.mock("../backendFetch", () => ({ fetchBackend: vi.fn() }));
vi.mock("../api", () => ({ getAuthHeaders: () => ({}) }));

const modelo: ModeloElevacion = {
  contrato: "elevacion/v1",
  fuente: "conformador_calculado",
  lienzo: 300,
  svg: "<svg/>",
  atomos: [],
  enlaces: [],
  desajuste_px: 2,
  enlace_px: 30,
  razon_enlaces: 0.07,
  fiel: true,
};

function respuesta(ok: boolean): Response {
  return {
    ok,
    status: ok ? 200 : 422,
    json: async () => (ok ? modelo : { detail: "SMILES inválido." }),
  } as unknown as Response;
}

describe("caché del conformador del editor", () => {
  beforeEach(() => {
    vi.mocked(fetchBackend).mockReset();
  });

  it("un SMILES ya calculado se sirve de la caché y no vuelve a pedirse", async () => {
    vi.mocked(fetchBackend).mockResolvedValue(respuesta(true));
    const smiles = "CCO-cache-1";

    expect(modeloDelEditorEnCache(smiles)).toBeUndefined();
    await elevacionDelEditor(smiles);
    await elevacionDelEditor(smiles);

    expect(fetchBackend).toHaveBeenCalledTimes(1);
    expect(modeloDelEditorEnCache(smiles)).toEqual(modelo);
  });

  it("una respuesta con error no se guarda: la siguiente vez se vuelve a pedir", async () => {
    vi.mocked(fetchBackend).mockResolvedValue(respuesta(false));
    const smiles = "XX-error-1";

    await expect(elevacionDelEditor(smiles)).rejects.toBeInstanceOf(ErrorDeElevacion);
    expect(modeloDelEditorEnCache(smiles)).toBeUndefined();
  });
});

describe("vista «Se acoplará» del editor", () => {
  beforeEach(() => {
    vi.mocked(fetchBackend).mockReset();
    vi.mocked(fetchBackend).mockResolvedValue(respuesta(true));
  });

  it("pide la especie con el pH y el tautómero de la corrida", async () => {
    await elevacionDelEditor("CCN-acoplada-1", undefined, { vista: "acoplada", preparacion: { ph: 6.5, tautomero: "canonico" } });

    const cuerpo = JSON.parse(String(vi.mocked(fetchBackend).mock.calls[0][1]?.body));
    expect(cuerpo).toEqual({ smiles: "CCN-acoplada-1", vista: "acoplada", ph: 6.5, tautomero: "canonico" });
  });

  it("cada vista y cada pH son otra entrada de la caché; la vista escrita no cambia", async () => {
    const smiles = "CCN-acoplada-2";
    const a74 = { vista: "acoplada" as const, preparacion: { ph: 7.4, tautomero: "entrada" as const } };
    const a50 = { vista: "acoplada" as const, preparacion: { ph: 5.0, tautomero: "entrada" as const } };

    await elevacionDelEditor(smiles);
    await elevacionDelEditor(smiles, undefined, a74);
    await elevacionDelEditor(smiles, undefined, a74);
    await elevacionDelEditor(smiles, undefined, a50);

    expect(fetchBackend).toHaveBeenCalledTimes(3);
    expect(JSON.parse(String(vi.mocked(fetchBackend).mock.calls[0][1]?.body))).toEqual({ smiles });
    expect(modeloDelEditorEnCache(smiles)).toBeDefined();
    expect(modeloDelEditorEnCache(smiles, a74)).toBeDefined();
    expect(modeloDelEditorEnCache(smiles, { vista: "acoplada", preparacion: { ph: 9, tautomero: "entrada" } })).toBeUndefined();
  });
});

describe("petición rápida y dibujo de Ketcher", () => {
  beforeEach(() => {
    vi.mocked(fetchBackend).mockReset();
    vi.mocked(fetchBackend).mockResolvedValue(respuesta(true));
  });

  it("la rápida pide una semilla y no se guarda: la completa se vuelve a pedir", async () => {
    const smiles = "CCO-rapida-1";

    await elevacionDelEditor(smiles, undefined, { rapida: true });
    expect(modeloDelEditorEnCache(smiles)).toBeUndefined();
    await elevacionDelEditor(smiles);

    const cuerpos = vi.mocked(fetchBackend).mock.calls.map((c) => JSON.parse(String(c[1]?.body)));
    expect(cuerpos).toEqual([{ smiles, rapida: true }, { smiles }]);
    expect(modeloDelEditorEnCache(smiles)).toBeDefined();
  });

  it("el dibujo viaja en la petición y otro dibujo es otra entrada de la caché", async () => {
    const smiles = "CCO-dibujo-1";

    await elevacionDelEditor(smiles, undefined, { molfile: "dibujo A" });
    await elevacionDelEditor(smiles, undefined, { molfile: "dibujo A" });
    await elevacionDelEditor(smiles, undefined, { molfile: "dibujo B" });

    expect(fetchBackend).toHaveBeenCalledTimes(2);
    expect(JSON.parse(String(vi.mocked(fetchBackend).mock.calls[0][1]?.body))).toEqual({ smiles, molfile: "dibujo A" });
    expect(modeloDelEditorEnCache(smiles)).toBeUndefined();
  });
});
