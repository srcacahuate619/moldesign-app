import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../lib/auth", () => ({
  useAuth: () => ({ isLoading: false, user: { user_id: "language-test" } }),
}));

import { LanguageProvider, useLanguage } from "../LanguageContext";
import { resetApiUrl, setApiUrlFromPort } from "../../lib/config";
import { mockFetch, setTauriEnv } from "../../vitest.setup";

const wrapper = ({ children }: { children: ReactNode }) => <LanguageProvider>{children}</LanguageProvider>;
const lastFetchCall = () => mockFetch.mock.calls.at(-1)! as unknown as Parameters<typeof window.fetch>;

describe("el idioma sólo se envía a la API local", () => {
  beforeEach(() => {
    setTauriEnv(false);
    resetApiUrl();
    setApiUrlFromPort(8007);
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(new Response("{}"));
  });

  afterEach(() => resetApiUrl());

  it.each(["en", "es"] as const)("arranca en %s sin alterar el IPC, los assets ni terceros", async (locale) => {
    localStorage.setItem("moldesign_locale:user:language-test", locale);
    const { result, unmount } = renderHook(() => useLanguage(), { wrapper });
    await waitFor(() => expect(result.current.locale).toBe(locale));
    const fetchWithLanguage = window.fetch;

    for (const url of [
      "http://ipc.localhost/ensure_backend",
      "ipc://localhost/plugin%3Aevent%7Clisten",
      "/registro/index.json",
      "data:application/wasm;base64,AGFzbQ==",
      "https://api.devnet.solana.com",
      "http://127.0.0.1:8008/health",
    ]) {
      const init = { method: "POST", body: "{}", headers: { "Tauri-Callback": "123" } };
      await window.fetch(url, init);
      expect(mockFetch).toHaveBeenLastCalledWith(url, init);
      // La misma configuración llega al transporte; ni siquiera se clona.
      expect(lastFetchCall()[1]).toBe(init);
    }

    unmount();
    expect(window.fetch).not.toBe(fetchWithLanguage);
    expect(window.fetch).toBe(mockFetch);
  });

  it("conserva cuerpo, sesión y cancelación al traducir y cambiar de puerto", async () => {
    localStorage.setItem("moldesign_locale:user:language-test", "en");
    const { result } = renderHook(() => useLanguage(), { wrapper });
    await waitFor(() => expect(result.current.locale).toBe("en"));
    const controller = new AbortController();
    const request = new Request("http://127.0.0.1:8007/evaluation/preflight", {
      method: "POST", body: "{\"smiles\":\"CCO\"}",
      headers: { Authorization: "Bearer test", "Content-Type": "application/json" },
      signal: controller.signal,
    });
    const init = { headers: { "X-Test": "preserved" }, signal: controller.signal };
    await window.fetch(request, init);
    const [input, options] = lastFetchCall() as [Request, RequestInit];
    expect(input).toBe(request);
    expect(await input.clone().text()).toBe('{"smiles":"CCO"}');
    expect(options.signal).toBe(controller.signal);
    const headers = new Headers(options.headers);
    expect(headers.get("Accept-Language")).toBe("en");
    expect(headers.get("Authorization")).toBe("Bearer test");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-Test")).toBe("preserved");

    act(() => result.current.setLocale("es"));
    act(() => setApiUrlFromPort(8012));
    await window.fetch("http://127.0.0.1:8012/health");
    const optionsAfterChange = lastFetchCall()[1] as RequestInit;
    expect(new Headers(optionsAfterChange.headers).get("Accept-Language")).toBe("es");
    const oldPortInit = { headers: { "X-Test": "old-port" } };
    await window.fetch("http://127.0.0.1:8007/health", oldPortInit);
    expect(lastFetchCall()[1]).toBe(oldPortInit);
  });
});
