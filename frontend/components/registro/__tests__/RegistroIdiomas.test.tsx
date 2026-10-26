import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", async importOriginal => {
  const actual = await importOriginal<typeof import("@/context/LanguageContext")>();
  return { ...actual, useLanguage: () => ({ locale: state.locale, t: (key: string, args?: Record<string, string | number>) => {
    let text = actual.TRANSLATIONS[state.locale][key] ?? key;
    for (const [name, value] of Object.entries(args ?? {})) text = text.replaceAll(`{${name}}`, String(value));
    return text;
  } }) };
});
vi.mock("@/lib/registro", async importOriginal => {
  const actual = await importOriginal<typeof import("@/lib/registro")>();
  const indice = JSON.parse(readFileSync(resolve(process.cwd(), "public/registro/index.json"), "utf8"));
  const cal = indice.experimentos.find((record: { id: string }) => record.id === "CAL-8HFI-01");
  const paper = JSON.parse(readFileSync(resolve(process.cwd(), "public/registro/papers/CAL-8HFI-01.json"), "utf8"));
  return { ...actual, cargarIndice: vi.fn(async () => ({ ...indice, experimentos: [cal] })), cargarPaper: vi.fn(async () => paper) };
});
import { RegistroCientifico } from "../RegistroCientifico";

beforeEach(() => {
  window.history.replaceState(null, "", "/ciencia");
  vi.stubGlobal("scrollTo", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

describe.each(["es", "en"] as const)("etiquetas de Ciencia (%s)", locale => {
  it("traduce columnas, capas y ficha sin reescribir el paper original", async () => {
    state.locale = locale;
    render(<RegistroCientifico />);
    await screen.findByText("CAL-8HFI-01");
    expect(screen.getByRole("heading", { name: locale === "en" ? "Refutations" : "Refutaciones" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: locale === "en" ? /Measurement.*Measures without deciding/ : /Medición.*Mide, no decide/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /CAL-8HFI-01/ }));
    expect(await screen.findByText(locale === "en" ? "Refutation" : "Refutación")).toBeInTheDocument();
    expect(screen.getByText(locale === "en" ? "Reproducibility" : "Reproducibilidad")).toBeInTheDocument();
    expect(screen.getByText(locale === "en" ? "Scientific texts and papers are shown in their original language." : "Los textos científicos y los papers se muestran en su idioma original.")).toBeInTheDocument();
    // Los números y la prosa científica proceden del paper real y quedan intactos.
    expect(await screen.findByRole("heading", { name: "Qué se midió" })).toBeInTheDocument();
    expect(screen.getAllByText("NO_GO")).toHaveLength(2);
    expect(screen.getByText(locale === "en" ? "branch" : "rama")).toBeInTheDocument();
  });
});
