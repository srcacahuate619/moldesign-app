// =====================================================================
// MOLCHAT-AUD-01, eje FE/UX — el motivo de un turno que no salió
// =====================================================================
//
// EL FALLO QUE VIGILA. `sendMessage` hacía `if (!res.ok) { SET_STREAMING
// false; return; }`. El mensaje del investigador quedaba en la lista, no
// llegaba respuesta y NADA decía por qué. Los motivos que esta pestaña añadió
// al backend —403 sin consentimiento del destino (MOLCHAT-NET-005), 503 si el
// historial local no acepta escribir (MOLCHAT-BE-008)— morían en ese `return`.
//
// Un mensaje accionable dice qué hacer. «El servidor respondió 403» no lo es.

import { describe, expect, it } from "vitest";

import { motivoDeRespuesta } from "../motivoDeTurno";

function respuesta(status: number, cuerpo?: unknown) {
  return {
    status,
    json: async () => {
      if (cuerpo === undefined) throw new Error("sin cuerpo");
      return cuerpo;
    },
  };
}

describe("el motivo que ve el investigador", () => {
  it("usa el detalle del backend cuando lo hay", async () => {
    const motivo = await motivoDeRespuesta(
      respuesta(403, { detail: "El destino ollama@10.0.0.7 no está autorizado." }),
    );

    expect(motivo).toBe("El destino ollama@10.0.0.7 no está autorizado.");
  });

  it("entiende un detalle estructurado", async () => {
    const motivo = await motivoDeRespuesta(
      respuesta(409, { detail: { motivo: "cambio_de_destino", mensaje: "Mueve el host." } }),
    );

    expect(motivo).toBe("Mueve el host.");
  });

  it("sin detalle, un 403 dice qué hacer y no el número", async () => {
    const motivo = await motivoDeRespuesta(respuesta(403));

    expect(motivo).toMatch(/autorizar el destino/i);
    expect(motivo).not.toMatch(/^El servidor respondio/);
  });

  it("un 503 se explica como motor no disponible, no como error genérico", async () => {
    expect(await motivoDeRespuesta(respuesta(503))).toMatch(/no esta disponible/i);
  });

  it("una sesión caducada se dice, para que se pueda volver a entrar", async () => {
    expect(await motivoDeRespuesta(respuesta(401))).toMatch(/sesion caduco/i);
  });

  it("un estado no previsto no se inventa: se dice cuál fue", async () => {
    expect(await motivoDeRespuesta(respuesta(418))).toContain("418");
  });
});
