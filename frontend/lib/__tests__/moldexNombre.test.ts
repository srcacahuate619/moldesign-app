import { describe, expect, it } from "vitest";
import { nombreDeLaFicha } from "../moldex";

// El backend nombra en castellano la molécula sin nombre («Ligando 47cfbceb»); en inglés se veía tal cual.
describe("nombreDeLaFicha", () => {
  const base = { smiles_hash: "47cfbceb00", target: { pdb_id: "8T69" } } as never;
  it("cambia el nombre por defecto del backend por el código de la ficha", () => {
    expect(nombreDeLaFicha({ ...(base as object), name: "Ligando 47cfbceb" } as never)).toBe("MDX-8T69-47CF");
    expect(nombreDeLaFicha({ ...(base as object), name: "" } as never)).toBe("MDX-8T69-47CF");
  });
  it("respeta el nombre que puso el usuario", () => {
    expect(nombreDeLaFicha({ ...(base as object), name: "α-HTBZ lead" } as never)).toBe("α-HTBZ lead");
  });
});
