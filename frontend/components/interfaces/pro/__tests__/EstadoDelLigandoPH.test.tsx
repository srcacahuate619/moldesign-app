import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import type { EvaluationResult } from "../../../../lib/types";
const idioma = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../../context/LanguageContext")>();
  return { ...actual, useLanguage: () => ({ t: (key: string, params?: Record<string, string | number>) =>
    (actual.TRANSLATIONS[idioma.locale][key] ?? key).replace(/\{(\w+)\}/g, (_, k) => String(params?.[k] ?? `{${k}}`)) }) };
});
import { EstadoDelLigando } from "../EstadoDelLigando";
type Prot = NonNullable<NonNullable<EvaluationResult["ligand_state"]>["protonacion"]>;
function mostrar(protonacion: Prot, cambio = false) {
  return render(<EstadoDelLigando result={{ ligand_state: {
    smiles_entrada: "CCN", smiles_acoplado: "CCN", cambio_respecto_a_la_entrada: cambio,
    protonacion,
  } } as EvaluationResult} />);
}
describe("SCI-A-066: pH registrado de la corrida", () => {
  it.each(["es", "en"] as const)("muestra pH 5.5, 7.4, 9 y decimales sin redondeo (%s)", (locale) => {
    idioma.locale = locale;
    for (const ph of [5.5, 7.4, 9, 5.555]) for (const cambio of [true, false]) {
      const { container } = mostrar({ aplicada: true, ph }, cambio);
      expect(screen.getByRole("heading", { level: 4 })).toHaveTextContent(locale === "es"
        ? `Especie acoplada a pH ${ph}` : `Species docked at pH ${ph}`);
      if (!cambio) expect(container).toHaveTextContent(locale === "es"
        ? `A pH ${ph} la especie no cambia` : `At pH ${ph} the species does not change`);
      if (ph !== 7.4) expect(container).not.toHaveTextContent("pH 7.4");
      cleanup();
    }
  });
  it.each(["es", "en"] as const)("distingue no aplicada y pH no registrado (%s)", (locale) => {
    idioma.locale = locale;
    for (const prot of [{ aplicada: false, ph: 7.4 }, { aplicada: true, ph: null }, { aplicada: true }, {}]) for (const cambio of [false, true]) {
      const { container } = mostrar(prot, cambio);
      const title = screen.getByRole("heading", { level: 4 });
      expect(title).not.toHaveTextContent(/pH/i);
      expect(title).toHaveTextContent(prot.aplicada === false
        ? (locale === "es" ? "protonación no aplicada" : "protonation not applied")
        : (locale === "es" ? "protonación no consta completa" : "protonation record incomplete"));
      expect(container).not.toHaveTextContent(/pH 7\.4/);
      if (!cambio) expect(container).toHaveTextContent(prot.aplicada === false
        ? (locale === "es" ? "La protonación no se aplicó." : "Protonation was not applied.")
        : (locale === "es" ? "No consta completa la protonación." : "The protonation record is incomplete."));
      if (cambio && prot.aplicada === true) expect(container).toHaveTextContent(locale === "es"
        ? "Se aplicó la protonación, pero no consta su pH." : "Protonation was applied, but its pH is not recorded.");
      cleanup();
    }
  });
  it.each(["es", "en"] as const)("separa solicitado 14 y ejecutado 12 y conserva el aviso (%s)", (locale) => {
    idioma.locale = locale;
    const aviso = "pH solicitado 14 fuera del intervalo; acotado a 12 por el backend";
    mostrar({ aplicada: true, ph: 12, ph_solicitado: 14, aviso_de_ph: aviso });
    expect(screen.getByRole("heading", { level: 4 })).toHaveTextContent("pH 12");
    expect(screen.getByText(locale === "es" ? "pH solicitado: 14; pH ejecutado: 12." : "Requested pH: 14; executed pH: 12.")).toBeInTheDocument();
    expect(screen.getByText(aviso)).toBeInTheDocument();
  });
});
