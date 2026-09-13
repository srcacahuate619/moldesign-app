import { beforeEach, describe, expect, it } from "vitest";

import { getTargets, uploadCustomTarget } from "../api";
import { resetApiUrl, setApiUrlFromPort } from "../config";
import { mockFetch } from "../../vitest.setup";


describe("contrato de propiedad de receptores", () => {
  beforeEach(() => {
    resetApiUrl();
    setApiUrlFromPort(8042);
    window.localStorage.clear();
    window.localStorage.setItem(
      "moldesign_auth",
      JSON.stringify({ token: "alice-token", user: { user_id: "alice" } }),
    );
  });

  it("lista por sesión autenticada sin enviar IDs privados del navegador", async () => {
    window.localStorage.setItem(
      "moldesign_custom_targets:user:alice",
      JSON.stringify(["private-from-browser"]),
    );
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await getTargets();

    const [url, init] = mockFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8042/targets/");
    expect(url).not.toContain("private_ids");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer alice-token");
  });

  it("subir un receptor no crea una credencial de propiedad en localStorage", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          success: true,
          message: "ok",
          target: { id: "target-1", pdb_id: "USR_ABC123", name: "Privado" },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    await uploadCustomTarget(new FormData());

    expect(window.localStorage.getItem("moldesign_custom_targets:user:alice")).toBeNull();
  });
});
