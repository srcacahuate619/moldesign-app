import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BatchRowResult } from "@/components/evaluation/BatchRowResult";
import { catalogo } from "@/context/traducciones/catalogo";
import type { EvidenceMolecule } from "@/lib/cohorts";
import { verificacionDePrueba as sello } from "@/lib/__tests__/fixtures/verificacionReceptor";

const mocks = vi.hoisted(() => ({ get: vi.fn(), locale: "es" as "es" | "en", verified: true }));
vi.mock("@/lib/api", () => ({ getEvaluationResult: mocks.get }));
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => [{ pdb_id: "8HFI", seccion_catalogo: mocks.verified ? "verificado" : "demostracion", verificacion: sello }] }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t }) }));
const t = (key: string, params: Record<string, string | number> = {}) => (catalogo[mocks.locale][key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`));
const row = (task_id: string | null = "run-a") => ({ molecule_id: "mol-a", task_id } as EvidenceMolecule);
const igual = { receptor_sha256: sello.receptor_sha256, docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 } };
beforeEach(() => { mocks.get.mockReset(); mocks.locale = "es"; mocks.verified = true; localStorage.clear(); });

describe("fila compacta: primero comprobar la corrida exacta", () => {
  it.each(["es", "en"] as const)("espera sin declarar una ausencia y después confirma en %s", async locale => {
    mocks.locale = locale;
    let resolver!: (value: object) => void;
    mocks.get.mockImplementation(() => new Promise(resolve => { resolver = resolve; }));
    render(<BatchRowResult row={row()} pdbId="8HFI" />);
    expect(screen.getByRole("note")).toHaveTextContent(catalogo[locale].cat_verificado_compacta_comprobando);
    expect(screen.getByRole("note")).not.toHaveAttribute("title", expect.stringContaining(catalogo[locale].cat_receptor_sin_declarar));
    expect(mocks.get).toHaveBeenCalledExactlyOnceWith("mol-a", "run-a");
    await act(async () => { resolver(igual); });
    expect(screen.getByRole("note")).toHaveTextContent(t("cat_verificado_compacta", {rho:"0.41"}));
    fireEvent.click(screen.getByRole("button"));
    expect(mocks.get).toHaveBeenCalledTimes(1);
  });
  it.each(["es", "en"] as const)("declara diferencias o ausencias sólo tras recibir el snapshot en %s", async locale => {
    mocks.locale = locale;
    mocks.get.mockResolvedValue({ receptor_sha256: "otro", docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 } });
    const view = render(<BatchRowResult row={row()} pdbId="8HFI" />);
    await waitFor(() => expect(screen.getByRole("note")).toHaveTextContent(catalogo[locale].cat_verificado_compacta_no_describe));
    expect(screen.getByRole("note")).toHaveAttribute("title", expect.stringContaining(catalogo[locale].cat_receptor_distinto));
    mocks.get.mockResolvedValue({});
    view.rerender(<BatchRowResult row={row("run-b")} pdbId="8HFI" />);
    expect(screen.getByRole("note")).toHaveTextContent(catalogo[locale].cat_verificado_compacta_comprobando);
    await waitFor(() => expect(screen.getByRole("note")).toHaveAttribute("aria-label", expect.stringContaining(catalogo[locale].cat_receptor_sin_declarar)));
  });
  it.each(["es", "en"] as const)("un fallo conserva comprobando y explica el motivo en ambos atributos en %s", async locale => {
    mocks.locale = locale;
    mocks.get.mockRejectedValue(new Error("HTTP 404 snapshot"));
    render(<BatchRowResult row={row()} pdbId="8HFI" />);
    await waitFor(() => expect(screen.getByRole("note")).toHaveAttribute("title", `${catalogo[locale].cat_verificado_compacta_comprobando}. HTTP 404 snapshot`));
    expect(screen.getByRole("note")).toHaveAttribute("aria-label", `${catalogo[locale].cat_verificado_compacta_comprobando}. HTTP 404 snapshot`);
    expect(screen.getByRole("note")).not.toHaveTextContent(catalogo[locale].cat_verificado_compacta_no_describe);
  });
  it("descarta una respuesta tardía al cambiar de fila", async () => {
    let resolver!: (value: object) => void;
    mocks.get.mockImplementationOnce(() => new Promise(resolve => { resolver = resolve; })).mockResolvedValueOnce({});
    const view = render(<BatchRowResult row={row()} pdbId="8HFI" />);
    view.rerender(<BatchRowResult row={{ ...row("run-b"), molecule_id: "mol-b" }} pdbId="8HFI" />);
    await act(async () => { resolver(igual); });
    expect(screen.getByRole("note")).toHaveTextContent(catalogo.es.cat_verificado_compacta_no_describe);
    expect(mocks.get.mock.calls).toEqual([["mol-a", "run-a"], ["mol-b", "run-b"]]);
  });
  it("al cambiar de cuenta no reutiliza el resultado anterior", async () => {
    mocks.get.mockResolvedValueOnce(igual).mockImplementationOnce(() => new Promise(() => {}));
    const view = render(<BatchRowResult row={row()} pdbId="8HFI" />);
    await waitFor(() => expect(screen.getByRole("note")).not.toHaveTextContent(catalogo.es.cat_verificado_compacta_comprobando));
    localStorage.setItem("moldesign_auth", "bob");
    view.rerender(<BatchRowResult row={row()} pdbId="8HFI" />);
    expect(screen.getByRole("note")).toHaveTextContent(catalogo.es.cat_verificado_compacta_comprobando);
    expect(mocks.get).toHaveBeenCalledTimes(2);
  });
  it("sin IDs conserva la incertidumbre sin pedir la proyección actual", () => {
    render(<BatchRowResult row={row(null)} pdbId="8HFI" />);
    expect(screen.getByRole("note")).toHaveTextContent(catalogo.es.cat_verificado_compacta_comprobando);
    expect(mocks.get).not.toHaveBeenCalled();
  });
  it("un receptor de demostración no añade consultas mientras la fila está compacta", () => {
    mocks.verified = false;
    render(<BatchRowResult row={row()} pdbId="8HFI" />);
    expect(screen.getByRole("note")).toHaveTextContent("Demostración");
    expect(mocks.get).not.toHaveBeenCalled();
  });
});
