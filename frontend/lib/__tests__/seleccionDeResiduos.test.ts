import { describe, expect, it } from "vitest";

import { seleccionAplicada, seleccionInicial, seleccionParaGuardar } from "../seleccionDeResiduos";

describe("seleccionDeResiduos: tres estados, sin cruzar [] con null (QA1-007)", () => {
  it("lo no decidido sigue sin decidir en los tres pasos", () => {
    expect(seleccionInicial(undefined)).toBeNull();
    expect(seleccionInicial(null)).toBeNull();
    expect(seleccionAplicada(undefined)).toBeNull();
    expect(seleccionParaGuardar(null)).toBeUndefined();
  });

  it("«ninguno» (`[]`) es una decisión y se conserva en los tres pasos", () => {
    // Antes `ProEvaluation` lo convertía en `null`: «Opciones» volvía a enseñar los 15
    // activos aunque el caso guardara «ninguno».
    expect(seleccionInicial([])).toEqual([]);
    expect(seleccionAplicada([])).toEqual([]);
    expect(seleccionParaGuardar([])).toEqual([]);
  });

  it("una lista es una decisión y se copia", () => {
    const original = ["A:ASP32", "A:ASP228"];
    const inicial = seleccionInicial(original);
    expect(inicial).toEqual(original);
    expect(inicial).not.toBe(original);
    expect(seleccionAplicada(original)).toEqual(original);
    expect(seleccionParaGuardar(inicial)).toEqual(original);
  });

  it("el ciclo guardar → reabrir devuelve exactamente lo que había", () => {
    for (const estado of [null, [], ["A:ASP32"]] as const) {
      const guardado = seleccionParaGuardar(estado as string[] | null);
      expect(seleccionInicial(guardado)).toEqual(estado);
    }
  });
});
