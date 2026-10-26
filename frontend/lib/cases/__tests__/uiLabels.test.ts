import { describe, expect, it } from "vitest";

import { casos } from "../../../context/traducciones/casos";
import { caseViewLabel, localizeCaseStorageLabel } from "../uiLabels";

function translate(locale: "es" | "en") {
  return (key: string) => casos[locale][key] ?? key;
}

describe("etiquetas localizadas del espacio de casos", () => {
  it("traduce los nombres de almacenamiento conocidos y conserva los externos", () => {
    expect(localizeCaseStorageLabel("Carpeta en este equipo", translate("en")))
      .toBe("Folder on this device");
    expect(localizeCaseStorageLabel("Guardado en este navegador", translate("en")))
      .toBe("Saved in this browser");
    expect(localizeCaseStorageLabel("Custom storage", translate("en")))
      .toBe("Custom storage");
    expect(localizeCaseStorageLabel("Carpeta en este equipo", translate("es")))
      .toBe("Carpeta en este equipo");
  });

  it("traduce los nombres visibles de las dos vistas sin cambiar el idioma base", () => {
    expect(caseViewLabel("evaluation", translate("en"))).toBe("Evaluation");
    expect(caseViewLabel("report", translate("en"))).toBe("Dossier");
    expect(caseViewLabel("evaluation", translate("es"))).toBe("Evaluación");
    expect(caseViewLabel("report", translate("es"))).toBe("Dossier");
  });
});
