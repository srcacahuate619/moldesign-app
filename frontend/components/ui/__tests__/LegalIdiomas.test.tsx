import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LegalModal } from "../LegalModal";

const state = vi.hoisted(() => ({ locale: "en" as "es" | "en" }));
vi.mock("../../../lib/webAnimation", () => ({ animateElements: vi.fn(() => []), cancelAnimations: vi.fn() }));
vi.mock("../../../context/LanguageContext", async () => {
  const real = await vi.importActual<typeof import("../../../context/LanguageContext")>("../../../context/LanguageContext");
  const t = (key: string, values?: Readonly<Record<string, string | number>>) =>
    real.interpolar(real.TRANSLATIONS[state.locale][key] ?? key, values);
  return { ...real, useLanguage: () => ({ locale: state.locale, t }) };
});
afterEach(cleanup);
describe.each(["es", "en"] as const)("nombre del motor en licencias en %s", locale => {
  it("localiza el encabezado y conserva la versión", async () => {
    state.locale = locale;
    render(<LegalModal isOpen onClose={vi.fn()} initialTab="licenses" />);
    const name = locale === "en" ? "Molcy engine" : "Motor Molcy";
    expect(await screen.findByRole("heading", { name: new RegExp(name), level: 4 })).toHaveTextContent("a3d0d10");
    if (locale === "en") expect(screen.queryByRole("heading", { name: /Motor Molcy/, level: 4 })).toBeNull();
  });
});
