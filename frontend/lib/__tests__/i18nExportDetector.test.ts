import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
const require = createRequire(import.meta.url);
const { inspectItems, OWNER_PENDING } = require("../../scripts/i18n-dom.cjs") as {
  OWNER_PENDING: Array<{ id: string }>;
  inspectItems(items: Array<{ channel: string; text: string; element?: string; dataField?: string }>, data?: Set<string>, contract?: { keys: Set<string>; strings: Set<string> }): {
    findings: Array<{ channel: string; text: string }>; exclusions: Array<{ reason: string }>;
  };
};
describe("el detector del export demuestra que ve", () => {
  it("detecta frases en los cuatro canales y rótulos sin tilde", () => {
    const items = [
      { channel: "innerText", text: "Guardar" },
      { channel: "innerText", text: "OPCIONES" },
      { channel: "innerText", text: "Cohortes" },
      { channel: "innerText", text: "26 octubre 2026" },
      { channel: "title", text: "Falta un receptor" },
      { channel: "aria-label", text: "Sin datos" },
      { channel: "placeholder", text: "Escribe el nombre del caso" },
    ];
    expect(inspectItems(items).findings).toEqual(items);
  });
  it("sólo acepta los valores técnicos completos y el contenido original declarado", () => {
    expect(inspectItems(["Español", "SMILES", "VALIDADOR_EXCEDIO_EL_PLAZO", "No results yet", "Open Babel", "Clear Canvas (Ctrl+Del)", "Erase (Del)", "Align principal component axes of the loaded structures to the screen axes (“lay flat”)", "scripts/build_registro_cientifico.py"]
      .map(text => ({ channel: "innerText", text }))).findings).toEqual([]);
    const csv = "smiles,name,active,control_role CC(=O)Nc1ccc(O)cc1,paracetamol,1,reference CC(C)Cc1ccc(cc1)C(C)C(=O)O,ibuprofeno,0,none";
    expect(inspectItems([{ channel: "innerText", text: csv }]).findings).toEqual([]);
    expect(inspectItems([{ channel: "innerText", text: csv + " Guarda el caso" }]).findings).toHaveLength(1);
    expect(inspectItems([{ channel: "title", text: "Guardar SMILES (Ctrl+Del)" }]).findings).toHaveLength(1);
    expect(inspectItems([{ channel: "innerText", text: "Hipótesis original" }], new Set(["Hipótesis original"])).findings).toEqual([]);
  });
  it("limita los valores del contrato al consultable y no oculta su prosa", () => {
    const contract = { keys: new Set(["estado"]), strings: new Set(["FALLA"]) };
    const samples = [
      { channel: "innerText", element: "DT", dataField: "structural_evidence", text: "estado" },
      { channel: "innerText", element: "SPAN", dataField: "structural_evidence", text: "FALLA" },
      { channel: "innerText", element: "BUTTON", text: "estado" },
      { channel: "innerText", element: "SPAN", dataField: "structural_evidence", text: "Guarda el caso" },
    ];
    expect(inspectItems(samples, new Set(), contract).findings).toEqual(samples.slice(2));
  });
  it("sólo conserva excepciones del propietario que siguen pendientes", () => {
    const inventory = require("../../../docs/auditorias/i18n-frontend-2026-10-25/inventario.json") as Array<{ id: string; estado: string; motivo?: string }>;
    for (const row of OWNER_PENDING) {
      const entry = inventory.find(item => item.id === row.id);
      expect(entry?.estado, row.id).toBe("pendiente");
      expect(entry?.motivo, row.id).toBeTruthy();
    }
  });
  it("limita las exclusiones del propietario al tooltip exacto", () => {
    const text = "Listo para docking: grid box calibrado y 8 residuos del sitio activo identificados.";
    expect(inspectItems([{ channel: "title", text }]).exclusions[0].reason).toContain("I18N-113");
    expect(inspectItems([{ channel: "innerText", text }]).findings).toHaveLength(1);
    expect(inspectItems([{ channel: "title", text: text + " Nueva frase castellana." }]).findings).toHaveLength(1);
  });
});
