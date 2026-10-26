import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("../config", () => ({ getApiUrl: vi.fn(async () => "http://127.0.0.1:18012"), resetApiUrl: vi.fn() }));
const desktop = vi.hoisted(() => ({ login: vi.fn(), remembered: { user_id: "qa2", username: "desktop", email: "qa2@local" } }));
vi.mock("../desktopAuth", () => ({ desktopLogin: desktop.login }));
vi.mock("../traspaso", () => ({ invitadoRecordado: () => desktop.remembered, recordarInvitado: vi.fn() }));
import { crearMolcy, fuentesMolcy } from "../molcy";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const session = (owner = "qa2", token = "caducado") => localStorage.setItem("moldesign_auth", JSON.stringify({ token, refreshToken: "refresh", user: { user_id: owner } }));
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); session(); Object.assign(window, { __TAURI__: {} }); });
afterEach(() => { vi.unstubAllGlobals(); delete (window as unknown as Record<string, unknown>).__TAURI__; });

describe("QA2-008: recuperación de sesión Molcy", () => {
  it("renueva al mismo invitado después de reiniciar el backend y conserva sus fuentes", async () => {
    desktop.login.mockResolvedValue({ access_token: "nuevo", refresh_token: "nuevo-refresh", user_id: "qa2", username: "desktop", email: "qa2@local" });
    const fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) return json({ detail: "caducada" }, 401);
      if (new Headers(init?.headers).get("Authorization") === "Bearer nuevo")
        return json({ moldex: [{ id: "m1", nombre: "Mi corrida", disponible: true, motivo: null }], receptores: [] });
      return json({ detail: "Sesión invitada caducada" }, 401);
    });
    vi.stubGlobal("fetch", fetch);
    expect((await fuentesMolcy()).moldex[0].id).toBe("m1");
    expect(desktop.login).toHaveBeenCalledTimes(1);
    expect(JSON.parse(localStorage.getItem("moldesign_auth")!).user.user_id).toBe("qa2");
  });

  it("no reenvía un render pendiente si la cuenta cambia durante el 401", async () => {
    const fetch = vi.fn(async () => { session("otra-cuenta", "otro-token"); return json({ detail: "caducada" }, 401); });
    vi.stubGlobal("fetch", fetch);
    await expect(crearMolcy({ origen: "moldex", id: "m1", task_id: "run1", escena: "resultado", formato: "previsualizacion", dispositivo: "cpu" })).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(desktop.login).not.toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem("moldesign_auth")!).user.user_id).toBe("otra-cuenta");
  });

  it("conserva el motivo del servidor para una operación rechazada", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Espera a que termine el render" }, 409)));
    await expect(crearMolcy({ origen: "moldex", id: "m1", task_id: "run1", escena: "resultado", formato: "previsualizacion", dispositivo: "cpu" })).rejects.toThrow("Espera a que termine el render");
    expect(desktop.login).not.toHaveBeenCalled();
  });
});
