// «Modelos»: cada tarjeta enseña la salida de SU modelo, con la ausencia dicha
// como ausencia y sin adjetivos de calidad.

import { beforeAll, describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { EvaluationResult } from "@/lib/types";
import { modelos } from "@/context/traducciones/modelos";
import { ProModelsTab } from "../ProModelsTab";
import { ResultReadingPresentation } from "../ResultReadingPresentation";

beforeAll(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); } });
});

const vista = (parcial: Record<string, unknown>) => render(
  <ResultReadingPresentation><ProModelsTab result={parcial as unknown as EvaluationResult} /></ResultReadingPresentation>,
);
// Los «?» pintan su texto en un portal: se abre con un clic y se lee en todo el documento.
const abrirAyuda = (nombre: string) => fireEvent.click(screen.getByRole("button", { name: nombre }));
const SHA = "d2041777857586065aa29dcc8b876a9c1e89394dacbf517e9c071e5cba27f0b2";
const tarjeta = (container: HTMLElement, id: string) => container.querySelector<HTMLElement>(`[data-model-card="${id}"]`);

const COMPLETO = {
  ml_pki: 6.31, model_used: "model_a_gpcr", in_applicability_domain: true,
  shap_values: { ecif_N_don_C: 0.12, vina_best_score: -0.2 }, shap_output: "delta_pKi",
  xgb_score: 0.05, clgnn_score: 0.7,
  stacking_effective_weights: { vina: 1, xgb: 0, gnn: 0, clgnn: 0 },
};

describe("Modelos · tarjetas", () => {
  it("M01 sin ninguna salida se dice y no se dibuja ninguna tarjeta", () => {
    const { container } = vista({ ml_pki: null, xgb_score: null, clgnn_score: null, shap_values: null });
    expect(container.querySelector("[data-models-empty]")).toHaveTextContent("no guardó la salida de ningún modelo");
    expect(container.querySelectorAll("[data-model-card]")).toHaveLength(0);
    expect(container.querySelector("[data-models-absent]")).toBeNull();
  });

  it("M02 con todo guardado salen tres tarjetas, en orden, y ninguna línea de «sin salida»", () => {
    const { container } = vista(COMPLETO);
    expect([...container.querySelectorAll("[data-model-card]")].map((n) => n.getAttribute("data-model-card")))
      .toEqual(["regresor", "clasificador", "clgnn"]);
    expect(container.querySelector("[data-models-absent]")).toBeNull();
  });

  it("M03 cada número está en la tarjeta de su modelo: pKi en la regresión, probabilidad en el clasificador", () => {
    const { container } = vista(COMPLETO);
    const regresion = tarjeta(container, "regresor")!;
    const clasificador = tarjeta(container, "clasificador")!;
    expect(regresion).toHaveTextContent("pKi 6.31");
    expect(regresion).not.toHaveTextContent(/\b0\.05\b/);
    expect(clasificador).toHaveTextContent("0.05");
    // La probabilidad no es un pKi: sólo la regresión rotula su salida así.
    for (const id of ["clasificador", "clgnn"]) expect(tarjeta(container, id)).not.toHaveTextContent(/pKi \d/);
    expect(tarjeta(container, "clgnn")).toHaveTextContent("0.70");
  });

  it("M04 el SHAP vive dentro de la tarjeta de la regresión y no en otra", () => {
    const { container } = vista(COMPLETO);
    expect(tarjeta(container, "regresor")!.querySelector("[data-shap-chart]")).not.toBeNull();
    for (const otra of ["clasificador", "clgnn"]) expect(tarjeta(container, otra)!.querySelector("[data-shap-chart]")).toBeNull();
  });

  it("M05 el clasificador y CL-GNN no inventan un identificador que la corrida no registró", () => {
    const { container } = vista(COMPLETO);
    for (const id of ["clasificador", "clgnn"]) expect(tarjeta(container, id)).toHaveTextContent("Sin identificador registrado en la corrida");
    expect(tarjeta(container, "regresor")).toHaveTextContent("model_a_gpcr");
  });
});

describe("Modelos · disposición", () => {
  it("L01 la regresión va en la columna izquierda y el clasificador y CL-GNN en la derecha", () => {
    const { container } = vista(COMPLETO);
    const columnas = [...container.querySelectorAll("[data-models-grid] > div")];
    expect(columnas).toHaveLength(2);
    expect([...columnas[0].querySelectorAll("[data-model-card]")].map((n) => n.getAttribute("data-model-card"))).toEqual(["regresor"]);
    expect([...columnas[1].querySelectorAll("[data-model-card]")].map((n) => n.getAttribute("data-model-card"))).toEqual(["clasificador", "clgnn"]);
    expect(container.querySelector("[data-models-grid]")!.className).not.toMatch(/unaColumna/);
  });

  it("L02 sin regresión, o sin nadie a su lado, las fichas se apilan en una sola columna", () => {
    const sinRegresion = vista({ xgb_score: 0.4 });
    expect(sinRegresion.container.querySelector("[data-models-grid]")!.className).toMatch(/unaColumna/);
    sinRegresion.unmount();
    const soloRegresion = vista({ ml_pki: 6 });
    expect(soloRegresion.container.querySelector("[data-models-grid]")!.className).toMatch(/unaColumna/);
  });

  it("L03 el SHA-256 de 64 caracteres se abrevia y se conserva íntegro en el atributo y el título", () => {
    const { container } = vista({ ml_pki: 4.37, model_used: "universal", shap_model_id: SHA });
    const huella = container.querySelector<HTMLElement>("[data-model-sha]")!;
    expect(huella.dataset.modelSha).toBe(SHA);
    expect(huella.textContent).toBe(`${SHA.slice(0, 12)}…${SHA.slice(-8)}`);
    expect(huella.closest("dd")).toHaveAttribute("title", SHA);
    expect(tarjeta(container, "regresor")).toHaveTextContent("universal");
  });

  it("L04 sin huella registrada no hay fila de SHA-256", () => {
    const { container } = vista({ ml_pki: 4.37, model_used: "universal" });
    expect(container.querySelector("[data-model-sha]")).toBeNull();
  });
});

describe("Modelos · pesos y dominio", () => {
  it("M06 peso 0: se enseña 0.00 y se dice que no entra en la composición", () => {
    const { container } = vista(COMPLETO);
    const clasificador = tarjeta(container, "clasificador")!;
    expect(within(clasificador).getByText("Peso en la composición del resultado").closest("dt")!.nextElementSibling).toHaveTextContent("0.00");
    expect(clasificador.querySelector('[data-model-weight="zero"]')).not.toBeNull();
  });

  it("M07 sin pesos registrados el peso es «No consta», no 0.00, y no hay nota de peso cero", () => {
    const { container } = vista({ xgb_score: 0.4 });
    const clasificador = tarjeta(container, "clasificador")!;
    expect(within(clasificador).getByText("Peso en la composición del resultado").closest("dt")!.nextElementSibling).toHaveTextContent("No consta");
    expect(clasificador.querySelector('[data-model-weight="zero"]')).toBeNull();
  });

  it("M08 el dominio se enseña tal como se registró: fuera advierte a la vista; desconocido y dentro, sin advertencia", () => {
    const fuera = vista({ ml_pki: 6, in_applicability_domain: false });
    expect(fuera.container.querySelector('[data-model-domain="out"]')).toHaveTextContent("como referencia, no como predicción");
    expect(tarjeta(fuera.container, "regresor")).toHaveTextContent("Fuera");
    fuera.unmount();
    const desconocido = vista({ ml_pki: 6 });
    expect(desconocido.container.querySelector('[data-model-domain="out"]')).toBeNull();
    expect(tarjeta(desconocido.container, "regresor")).toHaveTextContent("No consta");
    abrirAyuda("Qué significa el dominio de aplicabilidad");
    expect(document.body.querySelector('[data-model-domain="unknown"]')).toHaveTextContent("no se puede afirmar");
    desconocido.unmount();
    const dentro = vista({ ml_pki: 6, in_applicability_domain: true });
    expect(dentro.container.querySelector("[data-model-domain]")).toBeNull();
    expect(tarjeta(dentro.container, "regresor")).toHaveTextContent("Dentro");
    abrirAyuda("Qué significa el dominio de aplicabilidad");
    expect(document.body.querySelector('[data-model-domain="unknown"]')).toBeNull();
  });

  it("M08b el motivo del respaldo vive en un «?» junto al modelo, tal como lo escribió el backend, y sólo si existe", () => {
    const con = vista({ ml_pki: 6, fallback_reason: "Familia 'transporter' sin modelo entrenado disponible — modelo universal usado." });
    expect(con.container.querySelector("[data-model-fallback]")).toBeNull(); // no está a la vista
    abrirAyuda("Ver el motivo del respaldo");
    expect(document.body.querySelector("[data-model-fallback]")).toHaveTextContent("Familia 'transporter' sin modelo entrenado disponible — modelo universal usado.");
    con.unmount();
    const sin = vista({ ml_pki: 6 });
    expect(screen.queryByRole("button", { name: "Ver el motivo del respaldo" })).toBeNull();
    expect(sin.container.querySelector("[data-model-fallback]")).toBeNull();
  });

  it("M08c las explicaciones del SHAP no están a la vista: sólo el «?» y la gráfica", () => {
    const { container } = vista(COMPLETO);
    expect(container.querySelector("[data-shap-output]")).toBeNull();
    expect(container.querySelector("[data-shap-truncation]")).toBeNull();
    expect(screen.getByRole("button", { name: "Cómo leer las contribuciones SHAP" })).toBeInTheDocument();
  });

  it("M09 una corrida con SHAP y sin pKi dice que el pKi no consta", () => {
    const { container } = vista({ ml_pki: null, shap_values: { mw: 0.1 }, shap_output: "delta_pKi" });
    expect(tarjeta(container, "regresor")).toHaveTextContent("anterior al registro de la regresión");
    expect(tarjeta(container, "regresor")).not.toHaveTextContent(/pKi \d/);
  });
});

describe("Modelos · ausencias", () => {
  it("M10 los modelos sin salida se nombran aparte cuando otro sí la dejó", () => {
    const { container } = vista({ ml_pki: 6, in_applicability_domain: true });
    const ausentes = container.querySelector("[data-models-absent]")!;
    expect([...ausentes.querySelectorAll("[data-model-absent]")].map((n) => n.getAttribute("data-model-absent")))
      .toEqual(["clasificador", "clgnn"]);
    expect(ausentes.querySelector('[data-model-absent="clgnn"]')).toHaveTextContent("no consta su salida");
  });

  it("M11 un componente que el stacking declaró ausente lo dice con sus palabras", () => {
    const { container } = vista({ ml_pki: 6, stacking_missing_components: ["clgnn"] });
    expect(container.querySelector('[data-model-absent="clgnn"]')).toHaveTextContent("la composición del resultado lo declaró ausente");
    expect(container.querySelector('[data-model-absent="clasificador"]')).toHaveTextContent("no consta su salida");
  });

  it("M12 la GNN legacy no aparece aunque traiga un número", () => {
    const { container } = vista({ ml_pki: 6, gnn_score: 0.9, stacking_gnn_weight: 0.4 });
    expect(container.textContent ?? "").not.toMatch(/GNN legacy|RTMScore/i);
    expect(container.querySelectorAll('[data-model-absent]')).toHaveLength(2);
  });
});

describe("Modelos · selector de poses", () => {
  it("M13 el selector no tiene tarjeta aquí: su lugar es «Evidencia estructural»", () => {
    const { container } = vista({ ...COMPLETO, pose_selection: { status: "selected", vina_top1_rank: 1, selected_pose_rank: 3 } });
    expect(tarjeta(container, "selector")).toBeNull();
    expect(container.querySelector("[data-model-absent=\"selector\"]")).toBeNull();
    expect(container.textContent ?? "").not.toMatch(/Selector de poses/);
  });
});

describe("Modelos · sin adjetivos de calidad", () => {
  it("M14 ningún texto de la sección llama a un modelo universal, definitivo, calibrado ni el mejor", () => {
    const prohibidas = /universal|definitiv|calibrad|\bmejor(es)?\b|\bbest\b|reliable|state[- ]of[- ]the[- ]art|validad[oa]s?\b/i;
    for (const idioma of ["es", "en"] as const) {
      for (const [clave, texto] of Object.entries(modelos[idioma])) {
        expect(texto, `${idioma}.${clave}`).not.toMatch(prohibidas);
      }
    }
  });

  it("M15 es y en declaran las mismas claves", () => {
    expect(Object.keys(modelos.en).sort()).toEqual(Object.keys(modelos.es).sort());
  });
});
