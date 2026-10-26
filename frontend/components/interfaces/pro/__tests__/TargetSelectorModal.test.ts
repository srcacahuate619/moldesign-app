import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const source = readFileSync(
  resolve(process.cwd(), "components/interfaces/pro/TargetSelectorModal.tsx"),
  "utf8",
);

describe("feedback al compartir receptores", () => {
  it("no bloquea la aplicación con alert y expone éxito/error de forma accesible", () => {
    expect(source).not.toMatch(/\b(?:window\.)?alert\s*\(/);
    expect(source).toContain('role={shareFeedback.kind === "error" ? "alert" : "status"}');
    expect(source).toContain('aria-live="polite"');
    expect(source).toContain("disabled={sharingTargetId !== null}");
    expect(source).toContain("aria-busy={sharingTargetId ===");
  });
});

describe("coste de abrir el selector de receptores", () => {
  // El catálogo son 387 receptores. Cada añadido de aquí se paga 387 veces, y en
  // un equipo modesto la diferencia entre abrir el selector y esperar a que
  // aparezca era visible. Estas guardas fijan lo que se retiró para que no
  // vuelva por costumbre.

  it("no anima tarjeta por tarjeta al abrir ni al filtrar", () => {
    expect(source).not.toContain("gsap");
    expect(source).not.toMatch(/animateCards/);
  });

  it("no espera 300 ms fingidos: el catálogo ya está en memoria", () => {
    expect(source).not.toMatch(/setIsLoading/);
    expect(source).not.toMatch(/setTimeout\(\s*\(\)\s*=>\s*\{?\s*setIsLoading/);
  });

  it("las tarjetas no nacen invisibles esperando a que algo las revele", () => {
    // `opacity-0` en la clase + una animación que la sube es un catálogo en
    // blanco si la animación no llega a correr, con los datos ya cargados.
    expect(source).not.toContain("target-card opacity-0");
    expect(source).not.toContain('family-section space-y-4 opacity-0');
  });

  it("no apila desenfoques de pantalla completa", () => {
    expect(source).not.toContain("backdrop-blur");
  });

  it("no anima todas las propiedades de cada tarjeta", () => {
    expect(source).not.toContain("transition-all");
  });

  it("deja que el navegador se salte lo que está fuera de pantalla", () => {
    expect(source).toContain('contentVisibility: "auto"');
  });
});

describe("dianas que hoy no se pueden preparar (DOCK-003/DOCK-002)", () => {
  // Siguen en el catálogo —ocultarlas lo vaciaría—, pero elegirlas haría fallar
  // la corrida al preparar el receptor.
  it("se muestran con su motivo y no se pueden elegir", () => {
    expect(source).toContain("const noDisponible = targetObj.disponible === false;");
    expect(source).toContain("if (noDisponible) return;");
    expect(source).toContain('t("pn_no_disponible")');
    expect(source).toContain("targetObj.motivo_no_disponible");
  });

  it("una diana disponible con cadenas truncadas en el sitio lo dice antes de elegirla", () => {
    expect(source).toContain("targetObj.cadenas_truncadas_en_sitio ?? []");
    expect(source).toContain('t("pn_truncadas_en_sitio", { n: truncadas.length })');
  });
});

// ── SOL-03: preparación estructural ≠ calibración predictiva ─────────
//
// La auditoría lo midió con 3F75: el badge verde decía «CALIBRACIÓN — Listo»
// mientras el objeto real del receptor decía `curado_estructural`,
// `spearman_rho: null`, `requiere_advertencia: true` — «Curado
// estructuralmente; sin calibrar». El campo `calibration_status` mide
// is_prepared + grid + hotspots: readiness ESTRUCTURAL. El lugar donde el
// investigador ELIGE el receptor comunicaba respaldo predictivo que no
// existía.
//
// La regla: el badge estructural se rotula como lo que mide («Preparación»)
// y la calibración predictiva se muestra con el componente SC-9 compartido
// (`RespaldoDelReceptor`) — el mismo que ya usa el resultado, para que el
// selector y la corrida no puedan decir cosas distintas del mismo receptor.

describe("SOL-03: preparación y calibración no se confunden", () => {
  it("el badge estructural se rotula como preparación, no como calibración", () => {
    expect(source).toContain('t("pn_preparacion")');
    // El rótulo «CALIBRACIÓN» sobre `calibration_status` es la mentira
    // medida por la auditoría: ese campo no mide calibración predictiva.
    expect(source).not.toContain('t("pn_calibracion")');
  });

  it("la calibración predictiva viaja con el componente compartido SC-9", () => {
    // El objeto `calibracion` ya lo sirve `/targets` (SC-9); el selector no
    // puede inventar una segunda regla ni quedarse sin leerlo.
    expect(source).toContain("<RespaldoDelReceptor");
    expect(source).toContain("calibracion={targetObj.calibracion}");
  });

  it("el estado de preparación usa claves de diccionario, no cadenas fijas", () => {
    // «Listo»/«Revisar»/«Sin datos» eran español crudo pasado por t(), que
    // en inglés se queda en castellano. Ahora son claves.
    expect(source).not.toContain('return "Listo"');
    expect(source).toContain('case "listo": return "pn_prep_listo"');
  });
});
