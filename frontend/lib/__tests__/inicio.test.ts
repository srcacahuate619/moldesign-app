import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { SITE, VERSION_DE_LAS_NOTAS, versionAlcanza } from "../inicio";

describe("versionAlcanza", () => {
  it("compara por números, no por texto", () => {
    expect(versionAlcanza("1.0.10", "1.0.2")).toBe(true); // por texto «1.0.10» < «1.0.2»
    expect(versionAlcanza("1.0.2", "1.0.10")).toBe(false);
  });

  it("la misma versión alcanza; una anterior no; una posterior sí", () => {
    expect(versionAlcanza("1.0.2", "1.0.2")).toBe(true);
    expect(versionAlcanza("1.0.1", "1.0.2")).toBe(false);
    expect(versionAlcanza("1.1.0", "1.0.2")).toBe(true);
    expect(versionAlcanza("2.0.0", "1.9.9")).toBe(true);
  });

  it("una versión con menos o más campos no rompe", () => {
    expect(versionAlcanza("1.0", "1.0.0")).toBe(true);
    expect(versionAlcanza("1.0", "1.0.1")).toBe(false);
    expect(versionAlcanza("1.0.2.1", "1.0.2")).toBe(true);
  });

  it("un texto que no es versión se lee como cero y no lanza", () => {
    expect(versionAlcanza("dev", "1.0.2")).toBe(false);
  });
});

describe("la web del inicio", () => {
  it("es la web vigente, con barra final, y las notas describen 1.0.2", () => {
    expect(SITE).toBe("https://moldesign.amezcua-dev.com/");
    expect(VERSION_DE_LAS_NOTAS).toBe("1.0.2");
  });

  it("es el mismo dominio que la web declara como canónico", () => {
    // La app y la web llegaron a decir dominios distintos el mismo día: que no vuelva a pasar en silencio.
    const generador = readFileSync(resolve(process.cwd(), "../scripts/build_sitio_publico.py"), "utf8");
    const dominio = generador.match(/^DOMINIO = "([^"]+)"$/m)?.[1];
    expect(dominio).toBe(SITE);
  });

  it("es el dominio que escribe el cierre de los vídeos de Molcy", () => {
    // El cierre va grabado en cada vídeo: si la app cambia de dominio y el motor no, los vídeos anuncian otra web.
    const cierre = readFileSync(resolve(process.cwd(), "../tools/molcy/scripts/marca/cierre.py"), "utf8");
    const web = cierre.match(/^WEB = "([^"]+)"$/m)?.[1];
    expect(web).toBeDefined();
    expect(`https://${web}/`).toBe(SITE);
  });

  it("el inicio no escribe el dominio a mano ni enlaza rutas que no existen en `site/`", () => {
    const pagina = readFileSync(resolve(process.cwd(), "app/page.tsx"), "utf8");
    expect(pagina).not.toMatch(/amezcua-dev\.com/);
    expect(pagina).not.toMatch(/\/novedades|\/ciencia/);
  });

  it("una página de Next sólo exporta la página (otro nombre rompe la comprobación de tipos del build)", () => {
    const pagina = readFileSync(resolve(process.cwd(), "app/page.tsx"), "utf8");
    const exportaciones = [...pagina.matchAll(/^export\s+(?!default\b)/gm)];
    expect(exportaciones).toHaveLength(0);
  });
});
