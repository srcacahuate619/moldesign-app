import { describe, expect, it } from "vitest";
import { bloqueoDeEvaluacionDesdeChat } from "../evaluacionDesdeChat";

describe("entrada de evaluación desde MolChat", () => {
  const ready = { expired: false, reviewing: false, exampleLigand: false, canRun: true,
    runBlocked: false, antiNeedsReview: false, hasButton: true, busy: false };
  it("acepta solo cuando el botón y los datos del usuario están listos", () => {
    expect(bloqueoDeEvaluacionDesdeChat(ready)).toBeNull();
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, exampleLigand: true })).toBe("blocked");
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, canRun: false })).toBe("blocked");
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, runBlocked: true })).toBe("blocked");
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, antiNeedsReview: true })).toBe("blocked");
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, hasButton: false })).toBe("blocked");
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, busy: true })).toBe("busy");
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, reviewing: true })).toBe("needs_review");
    expect(bloqueoDeEvaluacionDesdeChat({ ...ready, expired: true })).toBe("unknown");
  });
});

import { motivoDeBloqueoDesdeChat } from "../evaluacionDesdeChat";
import { evaluacion } from "../../context/traducciones/evaluacion";

const claves = (clave: string) => clave;

describe("motivoDeBloqueoDesdeChat", () => {
  it("distingue una evaluación en marcha de un botón deshabilitado y de la pantalla ocupada", () => {
    expect(motivoDeBloqueoDesdeChat({ busy: true, buttonDisabled: false, running: true }, claves)).toBe("ev_chat_motivo_en_marcha");
    expect(motivoDeBloqueoDesdeChat({ busy: true, buttonDisabled: true, running: false }, claves)).toBe("ev_chat_motivo_deshabilitado");
    expect(motivoDeBloqueoDesdeChat({ busy: true, buttonDisabled: false, running: false }, claves)).toBe("ev_chat_motivo_ocupada");
  });
  it("cada mensaje del chat existe en los dos idiomas y el inglés no es el castellano", () => {
    const propias = Object.keys(evaluacion.es).filter(clave => clave.startsWith("ev_chat_"));
    expect(propias.length).toBeGreaterThanOrEqual(18);
    for (const clave of propias) {
      expect(evaluacion.en[clave], clave).toBeTruthy();
      expect(evaluacion.en[clave], clave).not.toBe(evaluacion.es[clave]);
    }
  });
});

import { debeEsperarLaPantalla } from "../evaluacionDesdeChat";

describe("debeEsperarLaPantalla", () => {
  it("espera mientras el caso carga y se rinde pasado el límite", () => {
    expect(debeEsperarLaPantalla("blocked", 200, 30000)).toBe(true);
    expect(debeEsperarLaPantalla("busy", 29999, 30000)).toBe(true);
    expect(debeEsperarLaPantalla("busy", 30000, 30000)).toBe(false);
  });
  it("no espera cuando el resultado no depende de que cargue la pantalla", () => {
    for (const estado of ["needs_review", "unknown", null]) expect(debeEsperarLaPantalla(estado, 0, 30000)).toBe(false);
  });
});

import { etapaDeEvaluacionChat, marcarEtapaDeEvaluacionChat } from "../evaluacionDesdeChat";

describe("etapas de una evaluación pedida desde el chat", () => {
  it("recuerda la última etapa y dice cuando no hubo ninguna", () => {
    expect(etapaDeEvaluacionChat("nunca-vista", claves)).toBe("ev_chat_sin_etapa");
    marcarEtapaDeEvaluacionChat("r1", "recibida");
    marcarEtapaDeEvaluacionChat("r1", "botón pulsado");
    expect(etapaDeEvaluacionChat("r1", claves)).toBe("botón pulsado");
  });
  it("no crece sin límite", () => {
    for (let i = 0; i < 40; i++) marcarEtapaDeEvaluacionChat(`id-${i}`, "x");
    expect(etapaDeEvaluacionChat("id-0", claves)).toBe("ev_chat_sin_etapa");
    expect(etapaDeEvaluacionChat("id-39", claves)).toBe("x");
  });
});
