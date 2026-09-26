import { describe, expect, it } from "vitest";

import { antiDianasPorDefecto } from "../ProConfigPanel";

describe("anti-dianas marcadas al abrir el panel", () => {
  const lista = [
    { pdb_id: "5VA1", name: "hERG", category: "Cardiac", risk: "", threshold_kcal: -7, source: "default", por_defecto: true, disponible: true },
    { pdb_id: "4NC3", name: "5-HT2B", category: "CNS", risk: "", threshold_kcal: -7.5, source: "default", por_defecto: true, disponible: false },
    { pdb_id: "7E2Y", name: "5-HT1A", category: "Bowes 2012 · GPCR", risk: "", threshold_kcal: -7, source: "bowes2012", por_defecto: false, disponible: true },
    { pdb_id: "USR1", name: "propia", category: "Custom", risk: "", threshold_kcal: -7, source: "user" },
  ];

  it("marca el panel por defecto disponible y las del usuario, no las sugeridas ni las no disponibles", () => {
    expect(antiDianasPorDefecto(lista)).toEqual(["5VA1", "USR1"]);
  });

  it("una respuesta antigua sin los campos nuevos se comporta como antes", () => {
    expect(antiDianasPorDefecto([{ pdb_id: "5VA1", name: "hERG", category: "", risk: "", threshold_kcal: -7 }]))
      .toEqual(["5VA1"]);
  });
});
