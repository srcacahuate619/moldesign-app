// =====================================================================
// MOLCHAT-NET-005 — el cliente no puede aplicar un cambio de destino en silencio
// =====================================================================
//
// El backend responde 409 cuando `base_url` movería el host sin confirmar. Si
// el cliente tratara ese 409 como un guardado normal, la interfaz diría
// «Guardado» mientras el destino sigue siendo el viejo —o peor, el usuario
// creería que lo cambió—. Aquí se vigila el contrato del lado del cliente.
//
// Es lectura de la fuente, como `AIContextAuth.test.tsx`: montar el contexto
// entero exige backend, sesión y `getApiUrl`, y lo que hay que fijar es el
// contrato, no el render.

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
const modal = readFileSync(
  resolve(aqui, "..", "..", "components", "ai", "AISettingsModal.tsx"),
  "utf8",
);

describe("el contexto trata el cambio de destino como tal", () => {
  it("distingue el 409 de un guardado correcto", () => {
    expect(fuente).toContain("res.status === 409");
    expect(fuente).toContain("cambio_de_destino");
  });

  it("no despacha la configuración cuando el destino cambió sin confirmar", () => {
    // El `return detalle` tiene que ir ANTES del dispatch: si no, el estado
    // local diría que se guardó algo que el backend rechazó.
    const posicionRetorno = fuente.indexOf("return detalle as CambioDeDestino");
    const posicionDispatch = fuente.indexOf('dispatch({ type: "SET_PROVIDER_CONFIG", config })');

    expect(posicionRetorno).toBeGreaterThan(-1);
    expect(posicionDispatch).toBeGreaterThan(posicionRetorno);
  });

  it("pide el estado de destinos y sabe otorgarlo y revocarlo", () => {
    expect(fuente).toContain("/ai/consent");
    expect(fuente).toContain("otorgarConsentimiento");
    expect(fuente).toContain("revocarConsentimiento");
  });

  it("otorga el destino que se mostró, no el que haya en ese momento", () => {
    // El backend rechaza con 409 si no coinciden; el cliente tiene que mandar
    // el host que el usuario vio para que esa comprobación sirva de algo.
    expect(fuente).toMatch(/provider_id: providerId,\s*host\s*\}/);
  });

  it("el destino sólo se consulta con sesión", () => {
    expect(fuente).toContain("if (user) loadDestinos();");
  });
});

describe("la interfaz declara el destino antes de que el usuario escriba", () => {
  it("el panel avisa cuando el destino activo es remoto y no está autorizado", () => {
    expect(panel).toContain("destinoActivo?.es_remoto && !destinoActivo.consentido");
    expect(panel).toContain("barra-consentimiento");
  });

  it("el aviso ofrece autorizar, no sólo informar", () => {
    expect(panel).toContain("otorgarConsentimiento(destinoActivo.provider_id");
  });

  it("el modal pregunta antes de mover el destino", () => {
    expect(modal).toContain("confirmar-destino");
    expect(modal).toContain("handleSave(true)");
  });
});
