import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PRODUCT } from "../../../lib/softwareCatalog";
import { mockFetch } from "../../../vitest.setup";
import { LegalModal } from "../LegalModal";

vi.mock("../../../lib/webAnimation", () => ({
  animateElements: vi.fn(() => []),
  cancelAnimations: vi.fn(),
}));

describe("LegalModal · catálogo y documentos locales", () => {
  beforeEach(() => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => "# documento local",
    } as Response);
  });

  it("muestra RCSB/wwPDB, CC0, UniProt, CC BY y la procedencia de la traducción", async () => {
    render(<LegalModal isOpen onClose={vi.fn()} initialTab="licenses" />);

    const dialog = await screen.findByRole("dialog");
    const text = dialog.textContent ?? "";

    expect(text).toContain("RCSB Protein Data Bank / wwPDB");
    expect(text).toContain("CC0 1.0");
    expect(text).toContain("cita científica recomendada");
    expect(text).toContain("UniProtKB");
    expect(text).toContain("CC BY 4.0");
    expect(text).toContain("Fuente: UniProtKB; descripciones funcionales");
    expect(text).toContain("traducción/adaptación al español: MolDesign");
    expect(text).toContain("380 receptores curados");
    expect(text).not.toContain("387");
  });

  it.each([
    ["Inventario completo", PRODUCT.noticesUrl],
    ["Fuente y recompilación", PRODUCT.sourceOfferUrl],
    ["Uso comercial", PRODUCT.commercialLicenseUrl],
  ] as const)("abre %s desde el asset local, sin navegación externa", async (label, path) => {
    render(<LegalModal isOpen onClose={vi.fn()} initialTab="licenses" />);

    fireEvent.click(await screen.findByRole("button", { name: new RegExp(label) }));

    const title =
      label === "Inventario completo"
        ? "Inventario completo de terceros"
        : label === "Uso comercial"
          ? "Licencia de uso comercial"
          : label;
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledWith(path);

    fireEvent.click(screen.getByRole("button", { name: "Volver" }));
    await waitFor(() => expect(screen.queryByRole("heading", { name: /Licencia de uso comercial|Inventario completo|Fuente y recompilación/ })).not.toBeInTheDocument());
  });
});