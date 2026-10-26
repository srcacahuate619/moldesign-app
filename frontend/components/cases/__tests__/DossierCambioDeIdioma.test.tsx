import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CaseRecord } from "@/lib/cases/types";

const state = vi.hoisted(() => ({ locale: "es" as "es" | "en", preview: vi.fn(), certificado: vi.fn() }));
vi.mock("@/context/LanguageContext", async importOriginal => {
  const actual = await importOriginal<typeof import("@/context/LanguageContext")>();
  return { ...actual, useLanguage: () => ({ locale: state.locale, t: (key: string) => actual.TRANSLATIONS[state.locale][key] ?? key }) };
});
vi.mock("@/lib/dossier", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/dossier")>(), requestDossierPreview: state.preview }));
vi.mock("@/lib/api", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/api")>(), fetchCertificateBlobUrl: state.certificado }));
vi.mock("@/components/CertificationModal", () => ({ CertificationModal: () => null }));

import { CaseDossierViewer } from "../CaseDossierViewer";
import { PDFReportViewer } from "@/components/PDFReportViewer";

const record: CaseRecord = {
  schemaVersion: 3, id: "qa", name: "qa", createdAt: "2026-10-09T00:00:00Z",
  updatedAt: "2026-10-09T00:00:00Z", lastOpenedAt: "2026-10-09T00:00:00Z",
  status: "review", storage: { mode: "browser", label: "Guardado en este navegador" }, runs: [],
  activeView: "report", context: {}, archived: false,
};
const reportable = { taskId: "corrida-exacta", moleculeId: "mol", certified: false };

beforeEach(() => {
  state.locale = "es";
  state.preview.mockReset();
  state.certificado.mockReset();
  class TestURL extends URL {
    static createObjectURL = vi.fn(() => `blob:${state.locale}`);
    static revokeObjectURL = vi.fn();
  }
  vi.stubGlobal("URL", TestURL);
});
afterEach(() => vi.unstubAllGlobals());

describe("PDF abierto al cambiar de idioma", () => {
  it("regenera el dossier del mismo caso y descarta la respuesta del idioma anterior", async () => {
    let resolver!: (value: { blob: Blob; filename: string }) => void;
    state.preview.mockReturnValueOnce(new Promise(resolve => { resolver = resolve; }))
      .mockResolvedValueOnce({ blob: new Blob(["en"]), filename: "en.pdf" });
    const view = render(<CaseDossierViewer caseRecord={record} reportable={reportable} runRelation="corresponde" />);
    await waitFor(() => expect(state.preview).toHaveBeenCalledTimes(1));
    const firstSignal = state.preview.mock.calls[0][2] as AbortSignal;
    state.locale = "en";
    view.rerender(<CaseDossierViewer caseRecord={record} reportable={reportable} runRelation="corresponde" />);
    await waitFor(() => expect(screen.getByTitle("Case dossier")).toHaveAttribute("src", "blob:en#toolbar=0&view=FitH"));
    expect(firstSignal.aborted).toBe(true);
    expect(state.preview.mock.calls[1][0]).toBe("mol");
    await act(async () => resolver({ blob: new Blob(["es"]), filename: "es.pdf" }));
    expect(screen.getByText("en.pdf")).toBeInTheDocument();
    expect(screen.queryByText("es.pdf")).toBeNull();
    expect(state.preview).toHaveBeenCalledTimes(2);
  });

  it("el certificado de una corrida también vuelve a consultarse con el idioma nuevo", async () => {
    state.certificado.mockResolvedValueOnce("blob:es").mockResolvedValueOnce("blob:en");
    const view = render(<PDFReportViewer moleculeId="mol" taskId="corrida-exacta" isCertified={false} />);
    await waitFor(() => expect(state.certificado).toHaveBeenCalledTimes(1));
    state.locale = "en";
    view.rerender(<PDFReportViewer moleculeId="mol" taskId="corrida-exacta" isCertified={false} />);
    await waitFor(() => expect(state.certificado).toHaveBeenCalledTimes(2));
    expect(screen.getByTitle("PDF dossier preview")).toHaveAttribute("src", "blob:en#toolbar=0&view=FitH");
    expect(state.certificado.mock.calls[1][0]).toBe("mol");
    expect(state.certificado.mock.calls[1][2]).toBe("corrida-exacta");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:es");
  });
});
