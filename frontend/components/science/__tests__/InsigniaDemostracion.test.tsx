import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import type { Target } from "@/lib/api";
import { invalidarCatalogo } from "@/lib/catalogoDeReceptores";
import { InsigniaDemostracion } from "../InsigniaDemostracion";

const getTargets = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ getTargets }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string) => catalogo.es[key] ?? key }) }));
beforeEach(() => { invalidarCatalogo(); localStorage.clear(); getTargets.mockReset(); });

describe("resultados de demostración", () => {
  it("sin dato avisa con texto explicativo aunque el catálogo no responda", async () => {
    getTargets.mockRejectedValue(new Error("sin backend"));
    render(<InsigniaDemostracion pdbId="1AAA" />);
    expect(screen.getByText("Demostración")).toBeTruthy();
    expect(screen.getByText(catalogo.es.cat_insignia_ayuda)).toBeTruthy();
    await waitFor(() => expect(getTargets).toHaveBeenCalledTimes(1));
  });
  it("dos corridas comparten una consulta y los receptores propios no llevan insignia", async () => {
    getTargets.mockResolvedValue([{ pdb_id: "LOCAL", is_private: true }]);
    render(<><InsigniaDemostracion pdbId="LOCAL" /><InsigniaDemostracion pdbId="LOCAL" /></>);
    await waitFor(() => expect(screen.queryAllByRole("note")).toHaveLength(0));
    expect(getTargets).toHaveBeenCalledTimes(1);
  });
  it("los receptores privados y de comunidad no se rotulan como demostración", () => {
    for (const target of [
      { pdb_id: "LOCAL", is_community: true },
      { pdb_id: "LOCAL", is_private: true },
    ]) {
      const view = render(<InsigniaDemostracion target={target as Target} />);
      expect(view.queryByRole("note")).toBeNull();
      view.unmount();
    }
    expect(getTargets).not.toHaveBeenCalled();
  });
});
