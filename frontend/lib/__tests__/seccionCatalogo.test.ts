import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Target } from "../api";
import { agruparSecciones, RECETA_RECEPTOR_DEL_SELLO, seccionDelReceptor, seccionPorPdbId } from "../seccionCatalogo";
import { invalidarCatalogo, obtenerCatalogo } from "../catalogoDeReceptores";

const getTargets = vi.hoisted(() => vi.fn());
vi.mock("../api", () => ({ getTargets }));
import { verificacionDePrueba as completo } from "./fixtures/verificacionReceptor";
const receptor = (extra: object = {}) => ({ pdb_id: "8HFI", ...extra }) as Target;
beforeEach(() => { invalidarCatalogo(); localStorage.clear(); getTargets.mockReset(); });

describe("secciones del catálogo", () => {
  it("la receta del sello coincide con la autoridad del backend", () => {
    const fuente = readFileSync(resolve(process.cwd(), "../backend/services/docking/preparer.py"), "utf8");
    expect(Number(fuente.match(/^RECEPTOR_RECIPE_VERSION = (\d+)/m)?.[1])).toBe(RECETA_RECEPTOR_DEL_SELLO);
  });
  it.each([
    { protocolo: undefined }, { condiciones: undefined }, { protocolo: {} },
    { protocolo: { ...completo.protocolo, semilla: true } }, { condiciones: [""] }, { condiciones: [42] },
    { receptor_sha256: "" }, { receta_receptor: 8 },
    { pose: { ...completo.pose, semillas_rmsd_ok: 2 } },
    { pose: { ...completo.pose, posebusters_valida: false } },
    { calibracion: { ...completo.calibracion, ic95: [0, 0.61] } },
    // SCI-D-002: resúmenes completos que no describen el protocolo o ninguna ρ posible.
    { pose: { ...completo.pose, semillas: 100, semillas_rmsd_ok: 3 } },
    { calibracion: { ...completo.calibracion, rho: -0.8, ic95: [0.1, 0.5] } },
    { calibracion: { ...completo.calibracion, rho: 0, ic95: [0.1, 0.5] } },
    { calibracion: { ...completo.calibracion, ic95: [1.1, 1.3] } },
    { calibracion: { ...completo.calibracion, rho: 1.4, ic95: [0.2, 0.6] } },
  ])("rechaza la evidencia que el backend no aceptaría: %j", (cambio) => {
    expect(seccionDelReceptor(receptor({ seccion_catalogo: "verificado", verificacion: { ...completo, ...cambio } }))).toBe("demostracion");
  });
  it("una lista vacía de condiciones declara la ausencia de restricciones adicionales", () => {
    expect(seccionDelReceptor(receptor({ seccion_catalogo: "verificado", verificacion: { ...completo, condiciones: [] } }))).toBe("verificado");
  });
  it("los campos ausentes y una verificación incompleta son demostración", () => {
    expect(seccionDelReceptor(receptor())).toBe("demostracion");
    expect(seccionDelReceptor(receptor({ seccion_catalogo: "verificado" }))).toBe("demostracion");
    expect(seccionDelReceptor(receptor({ seccion_catalogo: "verificado", verificacion: { pose: {} } }))).toBe("demostracion");
    expect(seccionPorPdbId(undefined, [receptor({ is_private: true })])).toBe("demostracion");
    expect(seccionPorPdbId("", [receptor({ is_private: true })])).toBe("demostracion");
  });
  it("reconoce la evidencia completa y prioriza propios/comunidad", () => {
    expect(seccionDelReceptor(receptor({ seccion_catalogo: "verificado", verificacion: completo }))).toBe("verificado");
    for (const flag of ["is_private", "is_community"]) expect(seccionDelReceptor(receptor({ [flag]: true, seccion_catalogo: "verificado", verificacion: completo }))).toBe("propios");
  });
  it("mantiene las tres secciones en orden aunque estén vacías", () => {
    expect(agruparSecciones([receptor()]).map((s) => [s.seccion, s.targets.length])).toEqual([["verificado", 0], ["propios", 0], ["demostracion", 1]]);
  });
  it("consulta la caché por PDB sin distinguir mayúsculas", async () => {
    getTargets.mockResolvedValue([receptor({ seccion_catalogo: "verificado", verificacion: completo })]);
    await obtenerCatalogo();
    expect(seccionPorPdbId("8hfi")).toBe("verificado");
    expect(seccionPorPdbId("1AAA")).toBe("demostracion");
    expect(getTargets).toHaveBeenCalledTimes(1);
  });
  it("no reutiliza la sección privada de otra sesión", async () => {
    localStorage.setItem("moldesign_auth", JSON.stringify({ token: "uno" }));
    getTargets.mockResolvedValue([receptor({ is_private: true, id: "local" })]);
    await obtenerCatalogo();
    expect(seccionPorPdbId("local")).toBe("propios");
    localStorage.setItem("moldesign_auth", JSON.stringify({ token: "dos" }));
    expect(seccionPorPdbId("local")).toBe("demostracion");
  });
});
