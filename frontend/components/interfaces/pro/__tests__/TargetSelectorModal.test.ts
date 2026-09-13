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
