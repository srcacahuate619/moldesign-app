import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("../config", () => ({ getApiUrl: vi.fn(async () => "http://127.0.0.1:18013"), resetApiUrl: vi.fn() }));
vi.mock("../desktopAuth", () => ({ desktopLogin: vi.fn() }));
vi.mock("../traspaso", () => ({ invitadoRecordado: () => null, recordarInvitado: vi.fn() }));
import { renderizadorMolcy } from "../molcy";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("moldesign_auth", JSON.stringify({ token: "t", refreshToken: "r", user: { user_id: "u", username: "u", email: "u@local" } }));
});
afterEach(() => vi.unstubAllGlobals());

/**
 * El sondeo del renderizador son dos arranques de Blender. Sin pedirlo, el backend reutiliza el último que salió bien;
 * «Comprobar» y el fin de una instalación sí lo piden (`?recomprobar=true`).
 */
describe("Molcy: sondeo del renderizador con o sin recomprobación", () => {
  it("por defecto no pide recomprobar; con `true`, sí", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => { urls.push(String(url)); return json({ disponible: true, motivo: null }); }));
    await renderizadorMolcy();
    await renderizadorMolcy(true);
    expect(urls[0]).toMatch(/\/molcy\/renderizador$/);
    expect(urls[1]).toMatch(/\/molcy\/renderizador\?recomprobar=true$/);
  });

  it("una respuesta ilegible se rechaza también cuando se pide recomprobar (la consulta no desactiva la validación)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ disponible: "true", motivo: null })));
    await expect(renderizadorMolcy(true)).rejects.toThrow();
    await expect(renderizadorMolcy()).rejects.toThrow();
  });
});
