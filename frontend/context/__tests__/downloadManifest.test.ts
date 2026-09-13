import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { FALLBACK_MANIFEST } from "../DownloadProvider";

describe("contrato del manifiesto de descargas", () => {
  it("exige integridad, procedencia, licencia y rutas relativas no duplicadas", () => {
    expect(new Set(FALLBACK_MANIFEST.map((entry) => entry.id)).size).toBe(FALLBACK_MANIFEST.length);
    for (const entry of FALLBACK_MANIFEST) {
      expect(entry.size_bytes).toBeGreaterThan(0);
      expect(entry.sha256).toMatch(/^[a-f0-9]{64}$/);
      expect(entry.urls?.[0]).toMatch(/^https:\/\//);
      expect(entry.license).toBeTruthy();
      expect(entry.source_url).toMatch(/^https:\/\//);
      expect(entry.filename).not.toMatch(/[\\/]/);
      expect(entry.destination).not.toMatch(/(^[A-Za-z]:|\.\.)/);
    }
  });

  it("no vuelve a ofrecer el runtime embebido como m?dulo descargable", () => {
    expect(FALLBACK_MANIFEST.some((entry) => entry.id === "base")).toBe(false);
    expect(FALLBACK_MANIFEST.every((entry) => entry.required !== true)).toBe(true);
  });

  it("mantiene sincronizado el fallback tipado con launcher-manifest.json", () => {
    const disk = JSON.parse(readFileSync(resolve(process.cwd(), "..", "launcher-manifest.json"), "utf8"));
    expect(disk.modules).toEqual(FALLBACK_MANIFEST);
  });
});