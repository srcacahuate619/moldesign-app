import { describe, expect, it } from "vitest";

import { avisosPorTransicion } from "../avisosDeModulos";

const ID = "model:esmfold-weights";

describe("avisos de las descargas de modelos", () => {
  it("al arrancar no avisa de nada: instalado o no, no es actividad", () => {
    const acciones = avisosPorTransicion({}, { "esmfold-weights": "missing", "llm-qwen15": "error" });
    expect(acciones).toEqual([]);
  });

  it("empezar, terminar y fallar son la misma entrada", () => {
    const empieza = avisosPorTransicion({ "esmfold-weights": "missing" }, { "esmfold-weights": "downloading" });
    expect(empieza).toMatchObject([{ tipo: "emitir", aviso: { id: ID, status: "in_progress", moduleId: "esmfold-weights", href: "/launcher" } }]);

    const termina = avisosPorTransicion({ "esmfold-weights": "downloading" }, { "esmfold-weights": "ready" });
    expect(termina).toMatchObject([{ tipo: "emitir", aviso: { id: ID, status: "success", titleKey: "nt_modelo_instalado" } }]);

    const falla = avisosPorTransicion({ "esmfold-weights": "extracting" }, { "esmfold-weights": "error" });
    expect(falla).toMatchObject([{ tipo: "emitir", aviso: { id: ID, status: "error", titleKey: "nt_modelo_fallo" } }]);
  });

  it("descargar → extraer no repite el aviso de inicio", () => {
    expect(avisosPorTransicion({ a: "downloading" }, { a: "extracting" })).toEqual([]);
  });

  it("una cancelación retira la descarga en curso y nada más", () => {
    expect(avisosPorTransicion({ "esmfold-weights": "downloading" }, { "esmfold-weights": "missing" }))
      .toEqual([{ tipo: "retirar", id: ID, soloSi: "in_progress" }]);
  });

  it("un modelo que ya está en disco retira la sugerencia de descargarlo, no su «instalado»", () => {
    expect(avisosPorTransicion({}, { "esmfold-weights": "ready" }))
      .toEqual([{ tipo: "retirar", id: ID, soloSi: "info" }]);
  });
});
