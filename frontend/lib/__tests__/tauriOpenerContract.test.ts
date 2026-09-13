import { describe, expect, it } from "vitest";

import capability from "../../src-tauri/capabilities/default.json";
import { esExterno } from "../openExternal";

/**
 * Por qué este test mira el SCOPE y no sólo el permiso.
 *
 * `opener:allow-open-url` habilita el comando «without any pre-configured
 * scope»: el plugin comprueba después `is_url_allowed`, que devuelve
 * `allowed.iter().any(...)` — es decir, `false` para TODA url cuando la lista de
 * permitidos está vacía. Conceder el permiso a secas deja la aplicación
 * exactamente como estaba antes de tener plugin: ningún enlace externo abre, y
 * el rechazo llega como `ForbiddenUrl`, que es fácil de confundir con «no pasa
 * nada al hacer clic».
 *
 * La versión anterior de este test comprobaba que el permiso estuviera
 * concedido y daba el contrato por bueno. Pasaba en verde con la aplicación
 * rota. Ahora se comprueba que el scope existe y que cubre exactamente los
 * esquemas que la frontera de `openExternal` acepta, ni uno más.
 */

type PermisoConScope = { identifier: string; allow?: { url?: string }[] };

function permisoDeOpenUrl(): PermisoConScope {
  const encontrado = (capability.permissions as unknown[]).find(
    (p) => typeof p === "object" && p !== null
      && (p as PermisoConScope).identifier === "opener:allow-open-url",
  );
  expect(encontrado, "la capability no concede opener:allow-open-url con scope").toBeDefined();
  return encontrado as PermisoConScope;
}

describe("capability del opener", () => {
  it("sólo concede open-url a la ventana main", () => {
    expect(capability.windows).toEqual(["main"]);
    const identificadores = (capability.permissions as unknown[]).map((p) =>
      typeof p === "string" ? p : (p as PermisoConScope).identifier,
    );
    expect(identificadores).toContain("opener:allow-open-url");
    expect(identificadores).not.toEqual(
      expect.arrayContaining([
        "opener:default",
        "opener:allow-open-path",
        "opener:allow-reveal-item-in-dir",
        "shell:default",
        "shell:allow-execute",
      ]),
    );
  });

  it("el scope no está vacío: sin él el plugin rechaza todas las urls", () => {
    const permiso = permisoDeOpenUrl();
    expect(permiso.allow, "scope ausente: is_url_allowed devolvería false siempre").toBeDefined();
    expect(permiso.allow!.length).toBeGreaterThan(0);
  });

  it("el scope y la frontera de openExternal permiten los mismos esquemas", () => {
    const patrones = permisoDeOpenUrl().allow!.map((e) => e.url);
    expect(new Set(patrones)).toEqual(new Set(["https://*", "http://*", "mailto:*"]));

    // El scope de Rust no puede ser más ancho que la validación de TypeScript:
    // `tel:` está en el `allow-default-urls` oficial y aquí se deja fuera a
    // propósito, porque `openExternal` lo rechazaría de todos modos.
    expect(patrones).not.toContain("tel:*");
    expect(esExterno("tel:+34600000000")).toBe(false);

    // Y al revés: todo lo que la frontera acepta debe tener patrón que lo cubra.
    expect(esExterno("https://github.com/srcacahuate619/moldesign-app")).toBe(true);
    expect(esExterno("http://127.0.0.1:8001/health")).toBe(true);
    expect(esExterno("mailto:moldesign@amezcua-dev.com")).toBe(true);
  });
});
