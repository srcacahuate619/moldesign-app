import { readFileSync } from "node:fs";
import { resolve } from "node:path";

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

  it("el API declara `por_defecto: true` para las del usuario y la interfaz lo respeta; `false` las deja fuera", () => {
    const propia = { pdb_id: "USR1", name: "propia", category: "Custom", risk: "", threshold_kcal: -7, source: "user" };
    expect(antiDianasPorDefecto([{ ...propia, por_defecto: true }])).toEqual(["USR1"]);
    expect(antiDianasPorDefecto([{ ...propia, por_defecto: false }])).toEqual([]);
  });

  it("una respuesta antigua sin los campos nuevos se comporta como antes", () => {
    expect(antiDianasPorDefecto([{ pdb_id: "5VA1", name: "hERG", category: "", risk: "", threshold_kcal: -7 }]))
      .toEqual(["5VA1"]);
  });
});

describe("controles de selección compartidos del panel de Bowes 2012", () => {
  const fuente = readFileSync(resolve(process.cwd(), "components/interfaces/pro/AntiDianasSelector.tsx"), "utf8");
  it("ofrece marcar todas, el panel por defecto o ninguna", () => {
    for (const clave of ["pn_anti_todas", "pn_panel_por_defecto", "pn_ninguna"]) expect(fuente).toContain(clave);
  });
  it("todas usa sólo las filas disponibles", () => {
    expect(fuente).toContain("const available = targets.filter(disponible)");
    expect(fuente).toContain("available.map((a) => a.pdb_id!)");
  });
  it("enseña el número efectivo seleccionado y el total disponible", () => {
    expect(fuente).toContain("n: effective.length, total: available.length");
  });
  it("la lista conserva altura máxima y scroll", () => {
    expect(fuente).toContain('max-h-64 space-y-3 overflow-y-auto pr-1');
  });
});
