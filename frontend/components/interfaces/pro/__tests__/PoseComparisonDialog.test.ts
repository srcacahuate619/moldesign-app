import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { extractPoseFromSdf } from "../PoseComparisonDialog";

const TWO_POSE_SDF = `Pose one
  MolDesign

  0  0  0  0  0  0  0  0  0  0  0  0
M  END
$$$$
Pose two
  MolDesign

  0  0  0  0  0  0  0  0  0  0  0  0
M  END
$$$$
`;

describe("extractPoseFromSdf", () => {
  it("extrae una sola pose por rango sin reordenar ni fabricar coordenadas", () => {
    expect(extractPoseFromSdf(TWO_POSE_SDF, 1)).toContain("Pose one");
    expect(extractPoseFromSdf(TWO_POSE_SDF, 1)).not.toContain("Pose two");
    expect(extractPoseFromSdf(TWO_POSE_SDF, 2)).toContain("Pose two");
    expect(extractPoseFromSdf(TWO_POSE_SDF, 2)).not.toContain("Pose one");
  });

  it("se abstiene si el rango no corresponde a una pose existente", () => {
    for (const rank of [0, -1, 3, 1.5, Number.NaN]) {
      expect(extractPoseFromSdf(TWO_POSE_SDF, rank)).toBeNull();
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Doc 71, defecto E4, segunda vuelta.
//
// El sintoma que la VM siguio viendo despues del primer arreglo era una barra
// de desplazamiento pegada al borde derecho de la pantalla, en el mismo sitio
// que la de la pagina. No venia de detras: el propio fondo del modal llevaba
// `overflow-y-auto` y, al ser `fixed inset-0`, su barra ocupa el alto entero
// del viewport y se lee como una segunda barra de la pagina.
//
// Los otros seis modales del producto no lo hacen: centran con flex y dejan el
// desplazamiento DENTRO de la tarjeta. Esta prueba fija esa forma, que es lo
// unico que impide que vuelva.
// ─────────────────────────────────────────────────────────────────────────

describe("el modal no dibuja una segunda barra de la pagina", () => {
  const fuente = readFileSync(
    resolve(process.cwd(), "components/interfaces/pro/PoseComparisonDialog.tsx"),
    "utf8",
  );

  const fondo = /className="fixed inset-0 z-\[135\][^"]*"/.exec(fuente)?.[0] ?? "";

  it("el fondo fijo no desplaza", () => {
    expect(fondo).not.toBe("");
    expect(fondo).not.toContain("overflow-y-auto");
    expect(fondo).toContain("overflow-hidden");
  });

  it("el fondo centra, como los otros seis modales", () => {
    expect(fondo).toContain("items-center");
    expect(fondo).toContain("justify-center");
  });

  it("el desplazamiento vive dentro de la tarjeta, con min-h-0", () => {
    // Sin `min-h-0` un hijo flex no baja de su altura de contenido y la tarjeta
    // se sale de la ventana en vez de dejar que este div se desplace.
    expect(fuente).toContain('className="min-h-0 flex-1 overflow-y-auto"');
    expect(fuente).toContain("flex max-h-full w-full max-w-6xl flex-col overflow-hidden");
  });

  it("sigue bloqueando la pagina de detras", () => {
    expect(fuente).toContain("useScrollLock(true)");
  });
});
