import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import type { Target } from "@/lib/api";
import { invalidarCatalogo } from "@/lib/catalogoDeReceptores";
import { verificacionDePrueba as verificacion } from "@/lib/__tests__/fixtures/verificacionReceptor";
import type { ParametrosDeCorrida } from "@/lib/seccionCatalogo";
import { InsigniaDelCatalogo } from "../InsigniaDelCatalogo";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en", getTargets: vi.fn() }));
vi.mock("@/lib/api", () => ({ getTargets: mocks.getTargets }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string, params: Record<string, string | number> = {}) => (catalogo[mocks.locale][key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`)) }) }));
const target = { pdb_id: "8HFI", seccion_catalogo: "verificado", verificacion } as Target;
beforeEach(() => { mocks.locale = "es"; mocks.getTargets.mockReset(); invalidarCatalogo(); localStorage.clear(); });

describe("sello del catálogo", () => {
  it.each(["es", "en"] as const)("distingue ausencias y diferencias en el texto completo y compacto en %s", locale => {
    mocks.locale = locale;
    const corrida = { receptor_sha256: "otro", docking_protocol: { exhaustiveness: 8, num_poses: 9 } };
    const view = render(<InsigniaDelCatalogo target={target} corrida={corrida} />);
    expect(screen.getByText(catalogo[locale].cat_receptor_distinto)).toBeVisible();
    expect(screen.getByText(catalogo[locale].cat_parametros_sin_declarar)).toBeVisible();
    expect(screen.queryByText(catalogo[locale].cat_receptor_sin_declarar)).toBeNull();
    expect(screen.queryByText(catalogo[locale].cat_parametros_distintos)).toBeNull();
    view.rerender(<InsigniaDelCatalogo target={target} corrida={{}} compacta />);
    const note = screen.getByRole("note");
    expect(note.textContent).toBe(catalogo[locale].cat_verificado_compacta_no_describe);
    expect(note.title).toContain(catalogo[locale].cat_receptor_sin_declarar);
    expect(note.title).toContain(catalogo[locale].cat_parametros_sin_declarar);
    expect(note.getAttribute("aria-label")).toBe(note.title);
  });
  it.each(["es", "en"] as const)("sin corrida o con todos los campos iguales conserva rho sin advertencias en %s", locale => {
    mocks.locale = locale;
    const view = render(<InsigniaDelCatalogo target={target} compacta />);
    for (const corrida of [undefined, null, { receptor_sha256: verificacion.receptor_sha256, docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 } }]) {
      view.rerender(<InsigniaDelCatalogo target={target} compacta corrida={corrida} />);
      const note = screen.getByRole("note");
      expect(note.textContent).toBe(locale === "es" ? "Verificado · ρ = 0.41" : "Verified · ρ = 0.41");
      for (const clave of ["cat_receptor_distinto", "cat_parametros_distintos", "cat_receptor_sin_declarar", "cat_parametros_sin_declarar"]) expect(note.title).not.toContain(catalogo[locale][clave]);
    }
  });
  it.each([
    [undefined, false], [{ receptor_sha256: null }, false], [{ receptor_sha256: verificacion.receptor_sha256 }, false], [{ receptor_sha256: "otro" }, true],
    [{ docking_protocol: { execution_provenance: { receptor_sha256: verificacion.receptor_sha256 } } }, false],
    [{ docking_protocol: { execution_provenance: { receptor_sha256: "otro" } } }, true],
    [{ receptor_sha256: verificacion.receptor_sha256, docking_protocol: { execution_provenance: { receptor_sha256: "otro" } } }, true],
    [{ receptor_sha256: "otro", docking_protocol: { execution_provenance: { receptor_sha256: verificacion.receptor_sha256 } } }, true],
  ] as Array<[ParametrosDeCorrida | undefined, boolean]>)("el sello compara el receptor declarado: %j", (corrida, difiere) => {
    const view = render(<InsigniaDelCatalogo target={target} corrida={corrida} />);
    expect(screen.queryByText(catalogo.es.cat_receptor_distinto) !== null).toBe(difiere);
    expect(screen.queryByText(catalogo.es.cat_parametros_distintos)).toBeNull();
    view.rerender(<InsigniaDelCatalogo target={target} corrida={corrida} compacta />);
    expect(screen.getByRole("note").title.includes(catalogo.es.cat_receptor_distinto)).toBe(difiere);
  });
  it("la advertencia del receptor también se muestra en inglés", () => {
    mocks.locale = "en";
    render(<InsigniaDelCatalogo target={target} corrida={{ receptor_sha256: "otro" }} />);
    expect(screen.getByText(catalogo.en.cat_receptor_distinto)).toBeVisible();
  });
  it.each(["es", "en"] as const)("la etiqueta compacta conserva el texto completo en %s", (locale) => {
    mocks.locale = locale;
    const view = render(<InsigniaDelCatalogo target={target} compacta corrida={{ vina_random_seed: 43 }} />);
    const sello = screen.getByRole("note");
    expect(sello.textContent).toBe(catalogo[locale].cat_verificado_compacta_no_describe);
    expect(sello.title).toContain("n = 57");
    for (const clave of ["cat_cond_sin_iones", "cat_cond_serie", "cat_cond_ensayo", "cat_parametros_distintos"]) expect(sello.title).toContain(catalogo[locale][clave]);
    expect(sello.getAttribute("aria-label")).toBe(sello.title);
    expect(sello.title).toContain(locale === "es" ? "exhaustividad 8, 9 poses y semilla 42" : "exhaustiveness 8, 9 poses and seed 42");
    view.rerender(<InsigniaDelCatalogo target={{ ...target, seccion_catalogo: undefined, verificacion: undefined }} compacta />);
    const demo = screen.getByRole("note");
    expect(demo.textContent).toBe(locale === "es" ? "Demostración" : "Demo");
    expect(demo.title).toContain(catalogo[locale].cat_insignia_ayuda);
    expect(demo.getAttribute("aria-label")).toBe(demo.title);
  });
  it.each(["es", "en"] as const)("muestra cifras, pose, parámetros y condiciones en %s", (locale) => {
    mocks.locale = locale;
    render(<InsigniaDelCatalogo target={target} />);
    expect(screen.getByText(locale === "es" ? "Verificado" : "Verified")).toBeVisible();
    expect(screen.getByText(locale === "es" ? "ρ = 0.41 (IC 95 %: 0.17–0.61; n = 57; Ki, CHEMBL853189)" : "ρ = 0.41 (95% CI: 0.17–0.61; n = 57; Ki, CHEMBL853189)")).toBeVisible();
    expect(screen.getByText(locale === "es" ? "Pose del cristal reproducida en 4 de 5 semillas (RMSD ≤ 2 Å)" : "Crystal pose reproduced in 4 of 5 seeds (RMSD ≤ 2 Å)")).toBeVisible();
    expect(screen.getByText(catalogo[locale].cat_parametros.replace("{e}", "8").replace("{p}", "9").replace("{s}", "42"))).toBeVisible();
    for (const clave of ["cat_cond_sin_iones", "cat_cond_serie", "cat_cond_ensayo"]) expect(screen.getByText(catalogo[locale][clave])).toBeVisible();
  });
  it("no oculta códigos desconocidos, incluidos nombres de propiedades heredadas", () => {
    render(<InsigniaDelCatalogo target={{ ...target, verificacion: { ...verificacion, condiciones: ["NUEVA_CONDICION", "constructor"] } }} />);
    expect(screen.getByText("Condición declarada: NUEVA_CONDICION")).toBeVisible();
    expect(screen.getByText("Condición declarada: constructor")).toBeVisible();
  });
  it("formatea rho e intervalo a dos decimales y los RMSD a uno", () => {
    render(<InsigniaDelCatalogo target={{ ...target, verificacion: { ...verificacion, calibracion: { ...verificacion.calibracion, rho: 0.4, ic95: [0.1, 0.6] }, pose: { ...verificacion.pose, rmsd_top1_A: [1, 1.26] } } }} />);
    expect(screen.getByText("ρ = 0.40 (IC 95 %: 0.10–0.60; n = 57; Ki, CHEMBL853189)")).toBeVisible();
    expect(screen.getByText("RMSD del top-1 por semilla: 1.0, 1.3 Å.")).toBeVisible();
  });
  it.each([
    [undefined, false], [{}, false], [{ docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 } }, false],
    [{ docking_protocol: { exhaustiveness: 32 } }, true], [{ docking_protocol: { num_poses: 10 } }, true],
    [{ docking_protocol: { seed: 43 } }, true], [{ vina_random_seed: 43 }, true], [{ vina_random_seed: 42 }, false],
    [{ docking_protocol: { seed: 42 }, vina_random_seed: 43 }, true], [{ docking_protocol: { seed: null } }, false],
  ] as Array<[ParametrosDeCorrida | undefined, boolean]>)("compara sólo los parámetros declarados: %j", (corrida, difiere) => {
    render(<InsigniaDelCatalogo target={target} corrida={corrida} />);
    expect(screen.queryByText(catalogo.es.cat_parametros_distintos) !== null).toBe(difiere);
  });
  it("recupera también las cifras del receptor desde el catálogo compartido", async () => {
    mocks.getTargets.mockResolvedValue([target]);
    render(<InsigniaDelCatalogo pdbId="8hfi" />);
    await waitFor(() => expect(screen.getByText("Verificado")).toBeVisible());
    expect(screen.getByText(/n = 57/)).toBeVisible();
    expect(mocks.getTargets).toHaveBeenCalledTimes(1);
  });
});
