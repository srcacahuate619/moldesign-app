import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:9999", resetApiUrl: () => {} }));
vi.mock("../desktopAuth", () => ({ desktopLogin: vi.fn() }));
import { getJobStatus } from "../api";
import { AuthProvider, useAuth } from "../auth";
import { desktopLogin } from "../desktopAuth";
import { recordarInvitado } from "../traspaso";
import { setTauriEnv } from "../../vitest.setup";

const guest = { user_id: "guest-1", username: "Desktop User", email: "local@test" };
const personal = { user_id: "personal-1", username: "Desktop User", email: "person@test" };
const payload = { ...guest, access_token: "new-access", refresh_token: "new-refresh" };
const response = (status: number, value = {}) => new Response(JSON.stringify(value), { status });
function Probe() {
  const { token, user } = useAuth();
  return <output data-testid="session">{user?.user_id}:{token}</output>;
}
function session(user = guest) {
  localStorage.setItem("moldesign_auth", JSON.stringify({ token: "old-access", refreshToken: "old-refresh", user }));
  render(<AuthProvider><Probe /></AuthProvider>);
}

describe("sesión de escritorio después de invalidar tokens", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(desktopLogin).mockReset();
    setTauriEnv(true);
    window.history.replaceState({}, "", "/evaluation");
  });
  afterEach(() => { cleanup(); setTauriEnv(false); vi.unstubAllGlobals(); });

  it("recupera una sola vez el invitado por IPC, reintenta las peticiones y actualiza React", async () => {
    recordarInvitado(guest);
    session();
    vi.mocked(desktopLogin).mockResolvedValue(payload);
    const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) return response(401);
      return (init?.headers as Record<string, string>).Authorization === "Bearer new-access"
        ? response(200, { status: "COMPLETED" }) : response(401);
    });
    vi.stubGlobal("fetch", fetcher);
    await act(async () => {
      const results = await Promise.all([getJobStatus("a"), getJobStatus("b")]);
      expect(results.every(r => r.status === "COMPLETED")).toBe(true);
    });
    expect(desktopLogin).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith("/auth/refresh"))).toHaveLength(1);
    expect(screen.getByTestId("session")).toHaveTextContent("guest-1:new-access");
  });

  it("una cuenta personal no se convierte en invitado aunque use el mismo nombre", async () => {
    recordarInvitado(guest);
    session(personal);
    vi.stubGlobal("fetch", vi.fn(async () => response(401)));
    await act(async () => { await expect(getJobStatus("a")).rejects.toMatchObject({ status: 401 }); });
    expect(desktopLogin).not.toHaveBeenCalled();
    expect(localStorage.getItem("moldesign_auth")).toBeNull();
    expect(screen.getByTestId("session")).toHaveTextContent(":");
  });

  it("un fallo temporal de refresh conserva la cuenta y no hace login de invitado", async () => {
    recordarInvitado(guest);
    session(personal);
    const stored = localStorage.getItem("moldesign_auth");
    vi.stubGlobal("fetch", vi.fn(async (url) => response(String(url).endsWith("/auth/refresh") ? 503 : 401)));
    await expect(getJobStatus("a")).rejects.toMatchObject({ status: 503 });
    expect(localStorage.getItem("moldesign_auth")).toBe(stored);
    expect(desktopLogin).not.toHaveBeenCalled();
  });

  it("también comunica a React una renovación normal de tokens personales", async () => {
    session(personal);
    vi.stubGlobal("fetch", vi.fn(async (url, init) => {
      if (String(url).endsWith("/auth/refresh")) return response(200, { ...payload, ...personal });
      return (init.headers as Record<string, string>).Authorization === "Bearer new-access" ? response(200) : response(401);
    }));
    await act(async () => { await getJobStatus("a"); });
    expect(screen.getByTestId("session")).toHaveTextContent("personal-1:new-access");
    expect(desktopLogin).not.toHaveBeenCalled();
  });

  it("un logout mientras se renueva no resucita la sesión", async () => {
    session(personal);
    let complete!: (res: Response) => void;
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/auth/refresh")) return new Promise<Response>(resolve => { complete = resolve; });
      return response(401);
    }));
    await act(async () => {
      const pending = getJobStatus("a");
      await vi.waitFor(() => expect(complete).toBeDefined());
      localStorage.removeItem("moldesign_auth");
      complete(response(200, { ...payload, ...personal }));
      await expect(pending).rejects.toMatchObject({ status: 401 });
    });
    expect(localStorage.getItem("moldesign_auth")).toBeNull();
  });
  it("no reenvía una petición antigua bajo otra cuenta que acaba de iniciar sesión", async () => {
    session();
    let complete!: (res: Response) => void;
    const fetcher = vi.fn()
      .mockImplementationOnce(() => new Promise<Response>(resolve => { complete = resolve; }))
      .mockResolvedValue(response(200));
    vi.stubGlobal("fetch", fetcher);
    const pending = getJobStatus("guest-task");
    await vi.waitFor(() => expect(complete).toBeDefined());
    const replacement = JSON.stringify({ token: "personal-access", refreshToken: "personal-refresh", user: personal });
    localStorage.setItem("moldesign_auth", replacement);
    complete(response(401));
    await expect(pending).rejects.toMatchObject({ status: 401 });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem("moldesign_auth")).toBe(replacement);
  });

});
