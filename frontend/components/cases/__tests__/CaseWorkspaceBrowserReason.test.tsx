import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createBrowserCaseRepository } from "../../../lib/cases/browserCaseRepository";
import { CaseProvider } from "../../../context/CaseContext";
import { CaseWorkspace } from "../CaseWorkspace";

vi.mock("../../../context/LanguageContext", async (cargar) => {
  const real = await cargar<typeof import("../../../context/LanguageContext")>();
  const t = (key: string, values?: Readonly<Record<string, string | number>>) =>
    real.interpolar(real.TRANSLATIONS.en[key] ?? key, values);
  return { ...real, useLanguage: () => ({ locale: "en", t }) };
});
vi.mock("../../evaluation/CaseEvaluationRunner", () => ({ default: () => null }));
vi.mock("../CaseDossierViewer", () => ({ CaseDossierViewer: () => null }));

describe("el motivo para no abrir carpeta en el navegador", () => {
  it("se presenta en inglés en la pantalla real de Evaluación", async () => {
    const repo = createBrowserCaseRepository("reason-i18n");
    render(<CaseProvider repository={repo}><CaseWorkspace /></CaseProvider>);
    expect(await screen.findByText("Opening a folder on disk requires the desktop application. In the browser, cases are stored locally on this computer.")).toBeInTheDocument();
  });

  it("conserva el motivo externo de un repositorio sin descriptor", async () => {
    const browser = createBrowserCaseRepository("external-reason");
    const repo = { ...browser, capabilities: { ...browser.capabilities, openFolderUnavailableMessage: undefined,
      openFolderUnavailableReason: "Motivo externo: ruta restringida" } };
    render(<CaseProvider repository={repo}><CaseWorkspace /></CaseProvider>);
    expect(await screen.findByText("Motivo externo: ruta restringida")).toBeInTheDocument();
  });
});
