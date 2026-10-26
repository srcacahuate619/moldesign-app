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
function mostrar(seleccion?: Record<string, unknown>, cambio = true, ph: number | null = 7.4) {
  return render(<EstadoDelLigando result={{ ligand_state: {
    smiles_entrada: "CCN", smiles_acoplado: "CC[NH3+]", cambio_respecto_a_la_entrada: cambio,
    carga_formal_neta: 1, tautomeria: { aplicada: true, alternativas: 2 },
    protonacion: { aplicada: true, ph, motor: "dimorphite-dl", alternativas: 3, seleccion },
  } } as EvaluationResult} />);
}
describe("SCI-A-067: criterio registrado del microestado", () => {
  it.each(["es", "en"] as const)("explica los cinco criterios sin selección por posición (%s)", (locale) => {
    idioma.locale = locale;
    const casos = [
      ["cargas_esperadas_ph_5.5", "Se eligió por las cargas esperadas a pH 5.5.", "Selected by the expected charges at pH 5.5."],
      ["primer_smiles_alfabetico_sin_centros", "No se reconocieron centros ionizables; se eligió por orden alfabético del SMILES.", "No ionizable centers were recognized; selection used SMILES alphabetical order."],
      ["grupo_reconocido_sin_pka", "Se reconoció un grupo sin pKa en la tabla; la elección requiere revisión.", "A group without a pKa in the table was recognized; the selection requires review."],
      ["sin_microestados", "El enumerador no devolvió microestados alternativos.", "The enumerator returned no alternative microstates."],
      ["sin_microestados_validos", "Ninguna alternativa fue válida; se conservó la entrada.", "No alternative was valid; the input was retained."],
    ];
    for (const [criterio, es, en] of casos) for (const cambio of [true, false]) {
      const { container } = mostrar({ criterio }, cambio);
      expect(screen.getByText(locale === "es" ? es : en)).toBeInTheDocument();
      expect(container).not.toHaveTextContent(/primero|first/i);
      if (cambio) {
        expect(container).toHaveTextContent(locale === "es" ? "entre 2 enumerados" : "among 2 enumerated forms");
        expect(container).toHaveTextContent(locale === "es" ? "3 estados devueltos" : "3 states returned");
      }
      cleanup();
    }
  });
  it.each(["es", "en"] as const)("conserva incertidumbre, motivo y ausencia sin adivinar (%s)", (locale) => {
    idioma.locale = locale;
    const { container } = mostrar({ criterio: "grupo_reconocido_sin_pka", quimica_resuelta: false, motivo: "Motivo literal del productor" });
    expect(screen.getByText(locale === "es" ? "La elección no está resuelta químicamente." : "The selection is not chemically resolved.")).toBeInTheDocument();
    expect(screen.getByText("Motivo literal del productor")).toBeInTheDocument();
    expect(container).not.toHaveTextContent(/primero|first/i);
    cleanup();
    mostrar({ criterio: "cargas_esperadas_ph_" });
    expect(screen.getByText(locale === "es" ? "Se eligió por las cargas esperadas a pH 7.4." : "Selected by the expected charges at pH 7.4.")).toBeInTheDocument();
    cleanup();
    mostrar({ criterio: "cargas_esperadas_ph_" }, true, null);
    expect(screen.getByText(locale === "es" ? "Se eligió por las cargas esperadas; no consta el pH del criterio." : "Selected by the expected charges; the criterion pH is not recorded.")).toBeInTheDocument();
    cleanup();
    for (const seleccion of [{ criterio: "xyz" }, { criterio: "toString" }, { criterio: "__proto__" }, undefined]) {
      const { container } = mostrar(seleccion, false);
      expect(screen.getByText(locale === "es" ? "No consta cómo se eligió el estado." : "How the state was selected is not recorded.")).toBeInTheDocument();
      expect(container).not.toHaveTextContent(/primero|first/i);
      cleanup();
    }
  });
});
