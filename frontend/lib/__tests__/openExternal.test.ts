import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExternalNavigationError, esExterno, openExternal } from "../openExternal";
import { mockOpenUrl, setTauriEnv } from "../../vitest.setup";

describe("frontera de navegación externa", () => {
  beforeEach(() => setTauriEnv(false));

  it("en Tauri delega un HTTPS una sola vez al openUrl oficial", async () => {
    setTauriEnv(true);

    await openExternal("https://example.com/repository");

    expect(mockOpenUrl).toHaveBeenCalledTimes(1);
    expect(mockOpenUrl).toHaveBeenCalledWith("https://example.com/repository");
  });

  it("en navegador normal conserva el fallback web", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue({} as Window);

    await openExternal("https://example.com/repository");

    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith(
      "https://example.com/repository",
      "_blank",
      "noopener,noreferrer",
    );
    open.mockRestore();
  });

  it.each(["javascript:alert(1)", "file:///C:/secret.txt", "data:text/html,boom", "ftp://example.com"])(
    "rechaza el esquema no permitido: %s",
    async (url) => {
      await expect(openExternal(url)).rejects.toBeInstanceOf(ExternalNavigationError);
      expect(mockOpenUrl).not.toHaveBeenCalled();
    },
  );

  it("no intercepta rutas internas, anchors ni blobs", () => {
    expect(esExterno("/legal/THIRD_PARTY_NOTICES.md")).toBe(false);
    expect(esExterno("#licencias")).toBe(false);
    expect(esExterno("blob:http://tauri.localhost/id")).toBe(false);
  });

  it("abre mailto en el fallback del navegador", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue({} as Window);

    await openExternal("mailto:moldesign-ai@proton.me");

    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith(
      "mailto:moldesign-ai@proton.me",
      "_blank",
      "noopener,noreferrer",
    );
    open.mockRestore();
  });
});