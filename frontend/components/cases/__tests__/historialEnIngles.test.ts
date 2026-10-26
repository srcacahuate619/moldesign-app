import { describe, expect, it } from "vitest";
import { formatRunMoment } from "../CaseRunHistoryModal";
import { casos } from "../../../context/traducciones/casos";

// Con la interfaz en inglés, el historial de corridas decía «TERMINADA · 25 oct 2026, 05:15 p.m.» (vídeo, 2026-10-25).
describe("historial de corridas en el idioma de la interfaz", () => {
  it("la fecha sigue el idioma de la interfaz, no el del sistema", () => {
    const en = formatRunMoment("2026-10-25T17:15:00Z", "en");
    expect(en).toMatch(/Oct/);
    expect(en).not.toMatch(/oct |p\. ?m\./);
    expect(formatRunMoment("2026-10-25T17:15:00Z", "es")).toMatch(/oct/);
    expect(formatRunMoment("no-es-fecha", "en")).toBe("Unreadable date");
  });

  it("cada estado de corrida tiene etiqueta en los dos idiomas", () => {
    for (const estado of ["idle", "submitted", "running", "interrupted", "completed", "failed", "cancelled"]) {
      const clave = `ca_estado_corrida_${estado}`;
      expect(casos.es[clave], clave).toBeTruthy();
      expect(casos.en[clave], clave).toBeTruthy();
      expect(casos.en[clave]).not.toBe(casos.es[clave]);
    }
    expect(casos.en.ca_estado_corrida_completed).toBe("Completed");
  });
});
