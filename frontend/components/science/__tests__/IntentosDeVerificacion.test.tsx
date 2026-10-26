import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import type { Target } from "@/lib/api";
import { intentoPublicado } from "@/lib/__tests__/fixtures/intentoPublicado";
import { seccionDelReceptor, type IntentoVerificacion } from "@/lib/seccionCatalogo";
import { InsigniaDelCatalogo } from "../InsigniaDelCatalogo";
import { IntentoEnTarjeta, IntentosPublicados } from "../IntentosDeVerificacion";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string, params: Record<string, string | number> = {}) =>
  Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), catalogo[mocks.locale][key] ?? key) }) }));
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => [target] }));
const target = { pdb_id: "8HFI", name: "Transportador de noradrenalina", seccion_catalogo: "demostracion", intentos_verificacion: [intentoPublicado] } as Target;
beforeEach(() => { mocks.locale = "es"; });

describe("intentos publicados del catálogo", () => {
  for (const locale of ["es", "en"] as const) {
    it.each([
      { ic: [-0.2, 0.4], frase: "cat_intento_azar" },
      { ic: [0, 0.4], frase: "cat_intento_azar" },
      { ic: [-0.4, 0], frase: "cat_intento_azar" },
      { ic: [-0.6, -0.1], frase: "cat_intento_inverso" },
      { ic: [0.1, 0.6], frase: null },
      { ic: undefined, frase: null }, { ic: null, frase: null },
      { ic: ["-0.2", "0.4"], frase: null }, { ic: [NaN, 0.4], frase: null },
      { ic: [-Infinity, 0.4], frase: null }, { ic: [0.4, -0.2], frase: null },
    ])(`interpreta sólo un IC numérico ordenado en ${locale}: $ic`, ({ ic, frase }) => {
      mocks.locale = locale;
      const receptor = { ...target, intentos_verificacion: [{ ...intentoPublicado, calibracion: { ...intentoPublicado.calibracion, ic95: ic } } as IntentoVerificacion] };
      const view = render(<IntentosPublicados targets={[receptor]} />);
      for (const clave of ["cat_intento_azar", "cat_intento_inverso"]) expect(view.container.textContent?.includes(catalogo[locale][clave])).toBe(clave === frase);
      expect(screen.getByText(/n = 57/)).toBeVisible();
      view.rerender(<IntentoEnTarjeta target={receptor} />);
      const note = screen.getByRole("note");
      for (const clave of ["cat_intento_azar", "cat_intento_inverso"]) expect(note.title.includes(catalogo[locale][clave])).toBe(clave === frase);
      expect(note.getAttribute("aria-label")).toBe(note.title);
    });
  }
  it.each([undefined, null, []])("sin intentos (%j) no añade ningún bloque ni línea", (intentos) => {
    const receptor = { ...target, intentos_verificacion: intentos };
    const { container } = render(<><IntentosPublicados targets={[receptor]} /><IntentoEnTarjeta target={receptor} /></>);
    expect(container).toBeEmptyDOMElement();
  });
  it.each(["es", "en"] as const)("el NO_GO real conserva todas sus cifras y condiciones en %s", (locale) => {
    mocks.locale = locale;
    render(<IntentosPublicados targets={[target]} />);
    expect(screen.getByRole("heading", { name: "8HFI · Transportador de noradrenalina" })).toBeVisible();
    expect(screen.getByText(/ρ = 0.13.*−?\-0.16–0.41.*n = 57.*Ki, CHEMBL853189/)).toBeVisible();
    expect(screen.getByText(/ρ = 0.13/).textContent).toContain(catalogo[locale].cat_intento_azar);
    expect(screen.queryByText(new RegExp(catalogo[locale].cat_intento_inverso))).toBeNull();
    expect(screen.getByText(locale === "es" ? "Pose del cristal reproducida en 3 de 5 semillas (RMSD ≤ 2 Å)" : "Crystal pose reproduced in 3 of 5 seeds (RMSD ≤ 2 Å)")).toBeVisible();
    expect(screen.getByText(/(?:exhaustividad|exhaustiveness) 8, 9 poses.*42/)).toBeVisible();
    for (const clave of ["cat_cond_sin_iones", "cat_cond_serie", "cat_cond_ensayo"]) expect(screen.getByText(catalogo[locale][clave])).toBeVisible();
    expect(screen.getByText(/0.6, 0.5, 4.1, 0.6, 3.7 Å/)).toBeVisible();
    expect(screen.getByText(/CAL-8HFI-01 \(2026-10-09\)/)).toBeVisible();
    expect(screen.queryByText(locale === "es" ? "Verificado" : "Verified", { exact: true })).toBeNull();
    expect(seccionDelReceptor(target)).toBe("demostracion");
  });
  it.each(["es", "en"] as const)("la tarjeta compacta contiene el texto completo en sus atributos en %s", (locale) => {
    mocks.locale = locale;
    render(<IntentoEnTarjeta target={target} />);
    const note = screen.getByRole("note");
    expect(note.textContent).toBe(catalogo[locale].cat_intento_compacto);
    expect(note.getAttribute("aria-label")).toBe(note.title);
    for (const value of ["ρ = 0.13", "-0.16–0.41", "n = 57", "CHEMBL853189", "CAL-8HFI-01", catalogo[locale].cat_cond_sin_iones]) expect(note.title).toContain(value);
    expect(screen.queryByText(/n = 57/)).toBeNull();
  });
  it("un GO hipotético no dice que no superó la calibración ni concede el sello", () => {
    const go = { ...target, intentos_verificacion: [{ ...intentoPublicado, decision: "GO" as const }] };
    render(<><IntentosPublicados targets={[go]} /><IntentoEnTarjeta target={go} /><InsigniaDelCatalogo target={go} /></>);
    expect(screen.queryByText(/no superó|No superó|no lo superaron/)).toBeNull();
    expect(screen.getAllByText("Intento de verificación: GO (CALIBRACION_NO_SUPERADA).").length).toBeGreaterThan(0);
    expect(seccionDelReceptor(go)).toBe("demostracion");
    expect(screen.queryByText("Verificado", { exact: true })).toBeNull();
  });
  it("las conclusiones y condiciones desconocidas conservan sus códigos", () => {
    render(<IntentosPublicados targets={[{ ...target, intentos_verificacion: [{ ...intentoPublicado, conclusion: "OTRO_RESULTADO", condiciones: ["OTRA_CONDICION", "constructor"] }] }]} />);
    expect(screen.getByText("Intento de verificación: NO_GO (OTRO_RESULTADO).")).toBeVisible();
    expect(screen.getByText(/ρ = 0.13.*n = 57/)).toBeVisible();
    expect(screen.getByText("Condición declarada: OTRA_CONDICION")).toBeVisible();
    expect(screen.getByText("Condición declarada: constructor")).toBeVisible();
  });
  it.each(["es", "en"] as const)("el resultado completo añade el intento y el compacto conserva sólo su etiqueta en %s", (locale) => {
    mocks.locale = locale;
    const view = render(<InsigniaDelCatalogo pdbId="8hfi" />);
    expect(screen.getByText(catalogo[locale].cat_intento_resumen)).toBeVisible();
    // SCI-A-016: el resumen conserva el panel, n, la magnitud, las condiciones y el experimento.
    expect(screen.getByText(/ρ = 0.13.*-0.16–0.41.*n = 57.*Ki, CHEMBL853189/)).toBeVisible();
    for (const clave of ["cat_cond_sin_iones", "cat_cond_serie", "cat_cond_ensayo"]) expect(screen.getByText(catalogo[locale][clave])).toBeVisible();
    expect(screen.getByText(/CAL-8HFI-01 \(2026-10-09\)/)).toBeVisible();
    expect(screen.queryByText(catalogo[locale].cat_insignia_ayuda)).toBeNull();
    view.rerender(<InsigniaDelCatalogo pdbId="8hfi" compacta />);
    expect(screen.getByRole("note").textContent).toBe(locale === "es" ? "Demostración" : "Demo");
    expect(screen.queryByText(/ρ =/)).toBeNull();
  });
  it.each([{ is_private: true }, { is_community: true }, { pdb_id: "1AAA" }])("no atribuye intentos ajenos al receptor (%j)", (extra) => {
    const { container } = render(<IntentosPublicados targets={[{ ...target, ...extra }]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
