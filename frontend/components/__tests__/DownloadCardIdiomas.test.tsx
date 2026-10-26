import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
const language = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
const startDownload = vi.hoisted(() => vi.fn());
vi.mock("@/context/LanguageContext", async importOriginal => {
  const actual = await importOriginal<typeof import("@/context/LanguageContext")>();
  return { ...actual, useLanguage: () => ({ t: (key: string) => actual.TRANSLATIONS[language.locale][key] ?? key }) };
});
vi.mock("@/hooks/useDownload", () => ({ useDownload: () => ({ models: {}, progress: {}, startDownload, cancelDownload: vi.fn() }) }));
import { DownloadCard } from "../DownloadCard";
import { FALLBACK_MANIFEST } from "@/context/DownloadProvider";
afterEach(() => { cleanup(); language.locale = "es"; startDownload.mockClear(); });
describe("modelos descargables en el idioma elegido", () => {
  it("cambia la presentación de ESMFold y conserva el ID de descarga y el manifiesto", () => {
    const entry = FALLBACK_MANIFEST.find(e => e.id === "esmfold-weights")!;
    const original = JSON.stringify(entry);
    const view = render(<DownloadCard entry={entry} />);
    expect(screen.getByRole("heading", { name: "ESMFold v1 — pesos del modelo" })).toBeInTheDocument();
    language.locale = "en";
    view.rerender(<DownloadCard entry={entry} />);
    expect(screen.getByRole("heading", { name: "ESMFold v1 — model weights" })).toBeInTheDocument();
    expect(screen.getByText(/Peptide folding.*AutoDock Vina/)).toBeInTheDocument();
    expect(screen.queryByText(/Plegamiento de péptidos/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Download and verify" }));
    expect(startDownload).toHaveBeenCalledWith("esmfold-weights");
    expect(JSON.stringify(entry)).toBe(original);
  });
  it("traduce Qwen y conserva la descripción de un módulo desconocido", () => {
    language.locale = "en";
    const view = render(<DownloadCard entry={FALLBACK_MANIFEST[0]} />);
    expect(screen.getByText("Local LLM for MolChat")).toBeInTheDocument();
    view.rerender(<DownloadCard entry={{ ...FALLBACK_MANIFEST[0], id: "external-model", name: "Other model", description: "Author description" }} />);
    expect(screen.getByText("Author description")).toBeInTheDocument();
  });
});
