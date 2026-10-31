import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import HistoryPage from "../page";
import { TRANSLATIONS } from "../../../context/LanguageContext";
import { FrontendError, frontendMessage } from "../../../lib/frontendError";

const state = vi.hoisted(() => ({
  locale: "en" as "es" | "en",
  user: { user_id: "history-qa", username: "QA", email: "qa@local.test" },
  history: vi.fn(),
}));
vi.mock("../../../lib/auth", () => ({ useAuth: () => ({ user: state.user, isLoading: false }) }));
vi.mock("../../../context/KeepAliveContext", () => ({ useKeepAliveActive: () => true }));
vi.mock("../../../lib/api", () => ({
  getEvaluationHistory: (...args: unknown[]) => state.history(...args),
  getUserStats: async () => null,
  downloadCertificate: vi.fn(),
  mensajeDelError: (error: Error) => error.message,
}));
vi.mock("../../../context/LanguageContext", async () => {
  const real = await vi.importActual<typeof import("../../../context/LanguageContext")>("../../../context/LanguageContext");
  const t = (key: string, values?: Readonly<Record<string, string | number>>) =>
    real.interpolar(real.TRANSLATIONS[state.locale][key] ?? key, values);
  return { ...real, useLanguage: () => ({ locale: state.locale, t }) };
});
afterEach(cleanup);
describe.each(["es", "en"] as const)("error estructurado del historial en %s", locale => {
  it("presenta el descriptor sin reconocer frases del diccionario", async () => {
    state.locale = locale;
    state.history.mockRejectedValue(new FrontendError(frontendMessage("pg_hist_error_conexion")));
    render(<HistoryPage />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(TRANSLATIONS[locale].pg_hist_error_conexion);
    if (locale === "en") expect(alert).not.toHaveTextContent(TRANSLATIONS.es.pg_hist_error_conexion);
  });
  it("conserva una causa externa desconocida", async () => {
    state.locale = locale;
    state.history.mockRejectedValue(new Error("EXTERNAL_OPAQUE_42"));
    render(<HistoryPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("EXTERNAL_OPAQUE_42");
  });
});
