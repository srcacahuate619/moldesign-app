import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import type { Target } from "@/lib/api";
import { intentosDelReceptor, seccionDelReceptor, type IntentoVerificacion } from "@/lib/seccionCatalogo";
import { IntentosPublicados } from "../IntentosDeVerificacion";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string, params: Record<string, string | number> = {}) =>
  Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), catalogo[mocks.locale][key] ?? key) }) }));

/** Los intentos reales de 8T69: la lectura es del archivo publicado, no una copia. */
const publicados = JSON.parse(readFileSync(resolve(process.cwd(), "../backend/data/intentos_de_verificacion.json"), "utf8")) as { intentos: IntentoVerificacion[] };
const intentos = publicados.intentos.filter(i => i.pdb_id === "8T69");
const verificados = JSON.parse(readFileSync(resolve(process.cwd(), "../backend/data/receptores_verificados.json"), "utf8")) as { verificados: Record<string, Target["verificacion"]> };
const target = { pdb_id: "8T69", name: "VMAT2", seccion_catalogo: "verificado", verificacion: verificados.verificados["8T69"],
  intentos_verificacion: intentos } as Target;
beforeEach(() => { mocks.locale = "es"; });

describe("intentos de VMAT2 (8T69)", () => {
  it("un NO_GO por fallo técnico, un reanálisis INCONCLUSIVE y la repetición GO, que es la que promociona", () => {
    expect(intentos.map(i => [i.experimento, i.decision])).toEqual([
      ["CAL-D-01-R4-VMAT2-8T69", "NO_GO"], ["CAL-D-01-R4B-VMAT2-8T69", "INCONCLUSIVE"], ["CAL-D-01-R4-2-VMAT2-8T69", "GO"]]);
    expect(intentosDelReceptor(target)).toHaveLength(3);
    expect(seccionDelReceptor(target)).toBe("verificado");
  });
  it.each(["es", "en"] as const)("muestra ρ y ρ de peor caso, y qué intento concede el sello, en %s", (locale) => {
    mocks.locale = locale;
    render(<IntentosPublicados targets={[target]} />);
    const t = catalogo[locale];
    expect(screen.getByText(new RegExp(t.cat_intento_fallo_tecnico.slice(0, 40)))).toBeVisible();
    expect(screen.getByText(new RegExp(t.cat_intento_post_hoc.slice(0, 40)))).toBeVisible();
    expect(screen.getByText(new RegExp(t.cat_intento_superado.slice(0, 22)))).toBeVisible();
    expect(screen.getByText(/con los 89 compuestos|with all 89 panel/)).toBeVisible();
    expect(screen.getAllByText(/ρ = 0[.,]39/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/ρ = 0[.,]32/).length).toBeGreaterThanOrEqual(2);
    for (const clave of ["cat_cond_serie", "cat_cond_ensayo_vmat2", "cat_cond_lote"]) expect(screen.getAllByText(t[clave]).length).toBeGreaterThan(0);
    expect(screen.queryByText(t.cat_cond_ensayo)).toBeNull();   // el de [3H]nisoxetina es de 8HFI
  });
});
