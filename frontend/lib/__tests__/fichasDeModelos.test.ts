// Controles de respuesta conocida de la sección «Modelos»: cada prueba fija
// qué salida pertenece a qué modelo y cuándo una ausencia sigue siendo ausencia.
// El resultado de entrada se construye a mano, así que la respuesta correcta se
// conoce sin ejecutar ningún modelo.

import { describe, expect, it } from "vitest";
import type { EvaluationResult } from "../types";
import { fichasDeModelos } from "../fichasDeModelos";

const resultado = (parcial: Record<string, unknown> = {}) => parcial as unknown as EvaluationResult;

describe("fichasDeModelos · ausencia y presencia", () => {
  it("F01 sin resultado no hay fichas ni líneas de «sin salida»", () => {
    for (const vacio of [null, undefined]) {
      const f = fichasDeModelos(vacio);
      expect(f).toEqual({ regresor: null, clasificador: null, clgnn: null, sinSalida: [], conAlguna: false });
    }
  });

  it("F02 un resultado sin salidas nombra los tres modelos como «sin salida» y no inventa ningún valor", () => {
    const f = fichasDeModelos(resultado({
      ml_pki: null, xgb_score: null, clgnn_score: null, shap_values: null,
    }));
    expect(f.conAlguna).toBe(false);
    expect([f.regresor, f.clasificador, f.clgnn]).toEqual([null, null, null]);
    expect(f.sinSalida.map((m) => m.id)).toEqual(["regresor", "clasificador", "clgnn"]);
  });

  it("F03 un cero es una predicción: el clasificador y CL-GNN con 0 tienen ficha", () => {
    const f = fichasDeModelos(resultado({ xgb_score: 0, clgnn_score: 0 }));
    expect(f.clasificador?.probabilidad).toBe(0);
    expect(f.clgnn?.valor).toBe(0);
    expect(f.sinSalida.map((m) => m.id)).not.toContain("clasificador");
    expect(f.sinSalida.map((m) => m.id)).not.toContain("clgnn");
  });

  it("F04 un valor no finito se trata como ausencia, no como número", () => {
    const f = fichasDeModelos(resultado({ xgb_score: Number.NaN, clgnn_score: Number.POSITIVE_INFINITY, ml_pki: Number.NaN }));
    expect([f.clasificador, f.clgnn, f.regresor]).toEqual([null, null, null]);
  });
});

describe("fichasDeModelos · cada salida es de su modelo", () => {
  it("F05 xgb_score es del CLASIFICADOR y ml_pki de la REGRESIÓN, sin mezclarse", () => {
    const soloClasificador = fichasDeModelos(resultado({ xgb_score: 0.05, ml_pki: null }));
    expect(soloClasificador.clasificador?.probabilidad).toBe(0.05);
    expect(soloClasificador.regresor).toBeNull();

    const soloRegresion = fichasDeModelos(resultado({ xgb_score: null, ml_pki: 6.31 }));
    expect(soloRegresion.regresor?.pki).toBe(6.31);
    expect(soloRegresion.clasificador).toBeNull();
  });

  it("F06 la GNN legacy no tiene ficha ni línea: su productor no existe", () => {
    const f = fichasDeModelos(resultado({ gnn_score: 0.9, stacking_gnn_weight: 0.4 }));
    expect(Object.keys(f)).not.toContain("gnn");
    expect(f.sinSalida.map((m) => m.id as string)).not.toContain("gnn");
    expect(f.conAlguna).toBe(false);
  });

  it("F07 CL-GNN guarda su valor y su peso propios, no los de la GNN legacy", () => {
    const f = fichasDeModelos(resultado({
      clgnn_score: 0.7, stacking_clgnn_weight: 0.25, stacking_gnn_weight: 0.9,
    }));
    expect(f.clgnn).toEqual({ valor: 0.7, peso: 0.25, declaradoAusente: false });
  });
});

describe("fichasDeModelos · pesos", () => {
  it("F08 el peso 0 registrado se conserva como 0 (no como «sin peso»)", () => {
    const f = fichasDeModelos(resultado({
      xgb_score: 0.4, clgnn_score: 0.6, stacking_effective_weights: { vina: 1, xgb: 0, gnn: 0, clgnn: 0 },
    }));
    expect(f.clasificador?.peso).toBe(0);
    expect(f.clgnn?.peso).toBe(0);
  });

  it("F09 sin pesos registrados el peso es null, nunca 0 ni un valor de diseño", () => {
    const f = fichasDeModelos(resultado({ xgb_score: 0.4, clgnn_score: 0.6 }));
    expect(f.clasificador?.peso).toBeNull();
    expect(f.clgnn?.peso).toBeNull();
  });

  it("F10 cae a los pesos nominales de la corrida cuando faltan los efectivos", () => {
    const f = fichasDeModelos(resultado({ xgb_score: 0.4, stacking_xgb_weight: 0.3, stacking_clgnn_weight: 0.1, clgnn_score: 0.5 }));
    expect(f.clasificador?.peso).toBe(0.3);
    expect(f.clgnn?.peso).toBe(0.1);
  });

  it("F11 el stacking sólo declara ausente al componente que listó", () => {
    const f = fichasDeModelos(resultado({ xgb_score: null, clgnn_score: null, stacking_missing_components: ["clgnn"] }));
    expect(f.sinSalida.find((m) => m.id === "clgnn")?.declaradoAusente).toBe(true);
    expect(f.sinSalida.find((m) => m.id === "clasificador")?.declaradoAusente).toBe(false);
  });
});

describe("fichasDeModelos · regresión y SHAP", () => {
  it("F12 el dominio es tal como se registró: false sigue siendo false y null sigue siendo desconocido", () => {
    expect(fichasDeModelos(resultado({ ml_pki: 6, in_applicability_domain: false })).regresor?.enDominio).toBe(false);
    expect(fichasDeModelos(resultado({ ml_pki: 6, in_applicability_domain: true })).regresor?.enDominio).toBe(true);
    expect(fichasDeModelos(resultado({ ml_pki: 6, in_applicability_domain: null, ml_pki_aplicada: null })).regresor?.enDominio).toBeNull();
    // Si sólo consta el flag de la regresión, se usa ese.
    expect(fichasDeModelos(resultado({ ml_pki: 6, in_applicability_domain: null, ml_pki_aplicada: false })).regresor?.enDominio).toBe(false);
  });

  it("F13 un SHAP vacío es ausencia: sin pKi tampoco hay ficha de regresión", () => {
    const f = fichasDeModelos(resultado({ ml_pki: null, shap_values: {} }));
    expect(f.regresor).toBeNull();
    expect(f.sinSalida.map((m) => m.id)).toContain("regresor");
  });

  it("F14 una corrida con SHAP y sin pKi conserva la ficha y declara el pKi como no consta", () => {
    const f = fichasDeModelos(resultado({ ml_pki: null, shap_values: { mw: 0.1 }, shap_output: "delta_pKi" }));
    expect(f.regresor).not.toBeNull();
    expect(f.regresor?.pki).toBeNull();
    expect(f.regresor?.shap).toEqual({ mw: 0.1 });
    expect(f.regresor?.salidaDelShap).toBe("delta_pKi");
  });

  it("F15 el nombre del modelo y su huella son cosas distintas: model_used es el nombre, shap_model_id el SHA-256", () => {
    // Caso real de una corrida con el modelo universal: nombre corto y huella de 64 caracteres.
    const sha = "d2041777857586065aa29dcc8b876a9c1e89394dacbf517e9c071e5cba27f0b2";
    const f = fichasDeModelos(resultado({ ml_pki: 4.37, model_used: "universal", shap_model_id: sha }));
    expect(f.regresor?.modelo).toBe("universal");
    expect(f.regresor?.huellaDelModelo).toBe(sha);
    expect(fichasDeModelos(resultado({ ml_pki: 6, model_used: "universal" })).regresor?.huellaDelModelo).toBeNull();
  });

  it("F16 un texto vacío es ausencia (modelo y motivo de respaldo)", () => {
    const f = fichasDeModelos(resultado({ ml_pki: 6, model_used: "  ", fallback_reason: "" }));
    expect(f.regresor?.modelo).toBeNull();
    expect(f.regresor?.motivoDeRespaldo).toBeNull();
  });
});
