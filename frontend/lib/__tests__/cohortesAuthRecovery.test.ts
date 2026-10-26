import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("../config", () => ({ getApiUrl: vi.fn(async () => "http://127.0.0.1:18013"), resetApiUrl: vi.fn() }));
const desktop = vi.hoisted(() => ({ login: vi.fn(), remembered: { user_id: "qa3", username: "desktop", email: "qa3@local" } }));
vi.mock("../desktopAuth", () => ({ desktopLogin: desktop.login }));
vi.mock("../traspaso", () => ({ invitadoRecordado: () => desktop.remembered, recordarInvitado: vi.fn() }));
import { CohortError, createCohort, getRun, listCohorts, openRun, type CohortStudy } from "../cohorts";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const session = (owner = "qa3", token = "caducado") => localStorage.setItem("moldesign_auth", JSON.stringify({ token, refreshToken: "refresh", user: { user_id: owner } }));
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); session(); Object.assign(window, { __TAURI__: {} });
  desktop.login.mockResolvedValue({ access_token: "nuevo", refresh_token: "nuevo-refresh", user_id: "qa3", username: "desktop", email: "qa3@local" });
});
afterEach(() => { vi.unstubAllGlobals(); delete (window as unknown as Record<string, unknown>).__TAURI__; });

describe("Cohortes al reiniciar el backend", () => {
  it("recupera la lista y la corrida exacta con la sesión renovada del mismo invitado", async () => {
    const fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) return json({ detail: "caducada" }, 401);
      if (new Headers(init?.headers).get("Authorization") !== "Bearer nuevo") return json({ detail: "caducada" }, 401);
      return String(url).endsWith("/evaluation/cohorts") ? json([{ id: "cohorte" }]) : json({ id: "corrida-exacta", cohort_id: "cohorte" });
    });
    vi.stubGlobal("fetch", fetch);
    expect((await listCohorts())[0].id).toBe("cohorte");
    expect((await getRun("corrida-exacta")).id).toBe("corrida-exacta");
    expect(desktop.login).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls.filter(([url]) => String(url).endsWith("/evaluation/cohort-runs/corrida-exacta"))).toHaveLength(1);
  });
  it("no reenvía una ejecución pendiente con las credenciales de otra cuenta", async () => {
    const fetch = vi.fn(async () => { session("otra-cuenta", "otro-token"); return json({ detail: "caducada" }, 401); });
    vi.stubGlobal("fetch", fetch);
    await expect(openRun("cohorte", 1)).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(desktop.login).not.toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem("moldesign_auth")!).user.user_id).toBe("otra-cuenta");
  });
  it("conserva código y detalle del servidor cuando la corrida no existe", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: { message: "La corrida no existe", code: "RUN_NOT_FOUND" } }, 404)));
    await expect(getRun("ausente")).rejects.toMatchObject({ status: 404, message: "La corrida no existe", detail: { code: "RUN_NOT_FOUND" } });
    expect(desktop.login).not.toHaveBeenCalled();
  });
  it("envía el archivo multipart sin imponer Content-Type y conserva el 409 de la huella", async () => {
    const fetch = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.body).toBeInstanceOf(FormData);
      expect(new Headers(init?.headers).has("Content-Type")).toBe(false);
      expect((init?.body as FormData).get("expected_fingerprint")).toBe("huella");
      return json({ detail: "Cambió el archivo" }, 409);
    });
    vi.stubGlobal("fetch", fetch);
    const failure = await createCohort(new File(["smiles\nCCCCCO"], "qa.csv"), {} as CohortStudy, "huella").catch(error => error);
    expect(failure).toBeInstanceOf(CohortError);
    expect(failure).toMatchObject({ status: 409, message: "Cambió el archivo" });
  });
});
