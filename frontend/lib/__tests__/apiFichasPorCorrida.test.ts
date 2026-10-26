import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:9999" }));

import {
  fetchCertificateBlobUrl,
  getComplexFile,
  getPoseFile,
  linkCertification,
  prepareCertification,
  saveMolecule,
} from "../api";

// Una molécula se evalúa varias veces y Moldex guarda cada evaluación por
// separado: toda petición que describe «esta evaluación» debe llevar su corrida,
// o el backend responde con la última.

function urlDe(llamada: unknown[]): string {
  return String(llamada[0]);
}

describe("las peticiones de una ficha de Moldex llevan su corrida", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("moldesign_auth", JSON.stringify({ token: "t" }));
    fetchSpy = vi.fn(async () =>
      new Response(JSON.stringify({ success: true, signature: "s", already_certified: false }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = fetchSpy as typeof fetch;
  });

  it("guarda la corrida pedida con su nombre", async () => {
    await saveMolecule("mol-1", "mi ficha", "run A/1");

    const url = new URL(urlDe(fetchSpy.mock.calls[0]));
    expect(url.pathname).toBe("/history/save/mol-1");
    expect(url.searchParams.get("task_id")).toBe("run A/1");
    expect(url.searchParams.get("name")).toBe("mi ficha");
    expect((fetchSpy.mock.calls[0][1] as RequestInit).method).toBe("POST");
  });

  it("sin corrida ni nombre no añade parámetros (cliente anterior)", async () => {
    await saveMolecule("mol-1");

    expect(urlDe(fetchSpy.mock.calls[0])).toBe("http://127.0.0.1:9999/history/save/mol-1");
  });

  it("pide las poses y el complejo de la corrida de la ficha", async () => {
    fetchSpy.mockImplementation(async () => new Response("SDF", { status: 200 }));

    await getPoseFile("mol-1", "run-A");
    await getComplexFile("mol-1", "run-A");
    await getPoseFile("mol-1");

    expect(urlDe(fetchSpy.mock.calls[0])).toBe(
      "http://127.0.0.1:9999/evaluation/files/poses/mol-1?task_id=run-A",
    );
    expect(urlDe(fetchSpy.mock.calls[1])).toBe(
      "http://127.0.0.1:9999/evaluation/files/complex/mol-1?task_id=run-A",
    );
    expect(urlDe(fetchSpy.mock.calls[2])).toBe(
      "http://127.0.0.1:9999/evaluation/files/poses/mol-1",
    );
  });

  it("pide el dossier de la corrida de la ficha", async () => {
    fetchSpy.mockImplementation(async () => new Response(new Blob(["%PDF"]), { status: 200 }));
    URL.createObjectURL = vi.fn(() => "blob:x");

    await fetchCertificateBlobUrl("mol-1", undefined, "run-A");

    expect(urlDe(fetchSpy.mock.calls[0])).toBe(
      "http://127.0.0.1:9999/blockchain/certificate/mol-1/preview?task_id=run-A",
    );
  });

  it("certifica la corrida de la ficha: el memo y el enlace llevan su task_id", async () => {
    await prepareCertification("mol-1", "Wallet1", "run-A");
    await linkCertification("mol-1", "firma", "run-A");
    await linkCertification("mol-1", "firma");

    expect(urlDe(fetchSpy.mock.calls[0])).toBe(
      "http://127.0.0.1:9999/blockchain/certify/mol-1/prepare?user_wallet=Wallet1&task_id=run-A",
    );
    expect(JSON.parse((fetchSpy.mock.calls[1][1] as RequestInit).body as string)).toEqual({
      molecule_id: "mol-1", signature: "firma", task_id: "run-A",
    });
    expect(JSON.parse((fetchSpy.mock.calls[2][1] as RequestInit).body as string)).toEqual({
      molecule_id: "mol-1", signature: "firma",
    });
  });
});
