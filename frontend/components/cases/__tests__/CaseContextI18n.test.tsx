import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CaseContextPanel } from "../CaseContextPanel";
const language = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("../../../context/LanguageContext", async importOriginal => {
  const actual = await importOriginal<typeof import("../../../context/LanguageContext")>();
  return { ...actual, useLanguage: () => ({ locale: language.locale, t: (key: string, values?: Record<string, string | number>) => actual.interpolar(actual.TRANSLATIONS[language.locale][key] ?? key, values) }) };
});
afterEach(cleanup);
describe.each(["es", "en"] as const)("contexto en %s", locale => {
  it.each(["saving", "saved", "error"] as const)("localiza %s, severidad y recuento completo", state => {
    language.locale = locale;
    render(<CaseContextPanel context={{}} saveState={state} onChange={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent((locale === "es" ? { saving: "Guardando…", saved: "Guardado.", error: "Error al guardar." } : { saving: "Saving…", saved: "Saved.", error: "Error saving." })[state]);
    expect(screen.getByText(locale === "es" ? "5 advertencias, 2 opcionales" : "5 warnings, 2 optional items")).toBeInTheDocument();
    expect(screen.getAllByText(locale === "es" ? "Contexto opcional" : "Optional context")).toHaveLength(2);
    expect(screen.getByText(locale === "es" ? "Pendientes:" : "Pending:")).toBeInTheDocument();
  });
});
