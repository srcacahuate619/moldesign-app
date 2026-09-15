// =====================================================================
// MOLCHAT-AUD-01, eje FE/UX — el turno que falla, y el reintento idempotente
// =====================================================================
//
// EL FALLO QUE VIGILA. `sendMessage` hacía `if (!res.ok) { SET_STREAMING
// false; return; }`. El mensaje del investigador quedaba en la lista, no
// llegaba respuesta y NADA decía por qué. Los motivos que esta pestaña añadió
// al backend —403 sin consentimiento del destino (MOLCHAT-NET-005), 503 si el
// historial local no acepta escribir (MOLCHAT-BE-008)— morían en ese `return`.
//
// El §8 pide además reintento idempotente. La forma de conseguirlo no es
// volver a llamar a `sendMessage` —eso añadiría el mensaje del investigador una
// segunda vez— sino repetir el MISMO snapshot del turno que falló. Eso es una
// propiedad estructural, y aquí se fija como tal.
//
// Es lectura de la fuente, como `AIContextAuth.test.tsx` y
// `AIContextConsentimiento.test.tsx`: montar el contexto entero exige backend,
// sesión y `getApiUrl`. El mensaje accionable sí se prueba de verdad, en
// `motivoDeTurno.test.ts`, que vive en su propio módulo justamente para eso.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const aqui = dirname(fileURLToPath(import.meta.url));
const fuente = readFileSync(resolve(aqui, "..", "AIContext.tsx"), "utf8");
const panel = readFileSync(
  resolve(aqui, "..", "..", "components", "ai", "ChatPanel.tsx"),
  "utf8",
);
const entrada = readFileSync(
  resolve(aqui, "..", "..", "components", "ai", "ChatInput.tsx"),
  "utf8",
);

describe("un turno que no sale deja motivo", () => {
  it("el `!res.ok` ya no es un `return` mudo", () => {
    expect(fuente).toContain("motivoDeRespuesta(res)");
    expect(fuente).toContain('type: "SET_TURNO_FALLIDO"');
  });

  it("el turno devuelve su desenlace a quien lo escribió", () => {
    expect(fuente).toContain("Promise<ResultadoDeEnvio>");
  });

  it("la pantalla enseña el motivo y ofrece repetirlo", () => {
    expect(panel).toContain("turnoFallido");
    expect(panel).toContain("retryLastTurn");
    expect(panel).toContain('t("c_reintentar")');
  });

  it("un error de red también deja motivo, no sólo un estado HTTP", () => {
    expect(fuente).toContain("No se pudo conectar con el motor");
  });
});

describe("el reintento es idempotente por construcción", () => {
  it("reejecuta el snapshot guardado, no vuelve a componer el turno", () => {
    expect(fuente).toContain("return ejecutarTurno(fallido.snapshot)");
  });

  it("sólo `sendMessage` añade el mensaje del investigador", () => {
    // Si `retryLastTurn` o `ejecutarTurno` despacharan ADD_MESSAGE, reintentar
    // dejaría la misma pregunta dos veces en la conversación.
    const inicioReintento = fuente.indexOf("const retryLastTurn");
    const inicioEjecutar = fuente.indexOf("const ejecutarTurno");
    const finEjecutar = fuente.indexOf("const sendMessage");

    expect(inicioEjecutar).toBeGreaterThan(-1);
    expect(finEjecutar).toBeGreaterThan(inicioEjecutar);

    const cuerpoEjecutar = fuente.slice(inicioEjecutar, finEjecutar);
    expect(cuerpoEjecutar).not.toContain('role: "user"');

    const cuerpoReintento = fuente.slice(inicioReintento);
    expect(cuerpoReintento).not.toContain("ADD_MESSAGE");
  });

  it("no se reintenta encima de un turno en curso", () => {
    expect(fuente).toContain("if (!fallido || state.isStreaming)");
  });
});

describe("el borrador no se pierde", () => {
  it("la caja sólo se limpia si el turno salió", () => {
    expect(entrada).toContain("if (resultado && resultado.ok === false)");
    expect(entrada).toContain("setInput(trimmed)");
  });
});
