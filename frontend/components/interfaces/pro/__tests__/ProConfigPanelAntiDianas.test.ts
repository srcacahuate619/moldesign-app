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

  it("una respuesta antigua sin los campos nuevos se comporta como antes", () => {
    expect(antiDianasPorDefecto([{ pdb_id: "5VA1", name: "hERG", category: "", risk: "", threshold_kcal: -7 }]))
      .toEqual(["5VA1"]);
  });
});

describe("controles de selección del panel de Bowes 2012", () => {
  const fuente = readFileSync(
    resolve(process.cwd(), "components/interfaces/pro/ProConfigPanel.tsx"),
    "utf8",
  );

  it("ofrece marcar todas, el panel por defecto o ninguna", () => {
    expect(fuente).toContain('seleccionar = (cuales: "todas" | "ninguna" | "por_defecto")');
    // Los tres botones salen de una tabla clave→traducción, no de tres `t(...)`.
    for (const clave of ["pn_todas", "pn_panel_por_defecto", "pn_ninguna"]) {
      expect(fuente).toContain(clave);
    }
  });

  it("«todas» no marca las que no se pueden preparar", () => {
    expect(fuente).toContain('antiTargets.filter((a) => a.disponible !== false && a.pdb_id)');
  });

  it("enseña cuántas hay seleccionadas de cuántas disponibles", () => {
    expect(fuente).toContain("{config.selectedAntiTargets.length}/{disponibles}");
  });

  it("la lista tiene altura máxima: 46 filas no pueden empujar el resto del panel", () => {
    expect(fuente).toContain('className="max-h-64 space-y-1.5 overflow-y-auto pr-1"');
  });
});
