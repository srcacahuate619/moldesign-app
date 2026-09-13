/**
 * Procedencia y respaldo de las descargas de módulos.
 *
 * Dos defectos pequeños que sólo se ven el día que muerden:
 *
 * 1. **`revision: "main"`** — el manifiesto fijaba el SHA-256 del archivo pero
 *    descargaba de una rama. `main` se mueve cuando su dueño quiere: el día que
 *    upstream reemplace el peso, el hash deja de coincidir y la descarga falla
 *    para todos los usuarios, sin que nadie lo haya decidido. Fijar el commit da
 *    la inmutabilidad de un espejo sin tener que alojar nada.
 *
 * 2. **`urls` era un array del que sólo se leía `[0]`.** La estructura para
 *    tener una fuente oficial y un espejo de respaldo ya estaba escrita; lo que
 *    faltaba era usarla. Si la primera dirección fallaba, la descarga moría con
 *    un error genérico aunque hubiera otra al lado.
 *
 * Lo que el respaldo NO puede relajar: el `sha256` se verifica igual en todas
 * las fuentes —que un espejo responda no lo autoriza a entregar otro archivo— y
 * una cancelación del investigador no se reintenta contra la siguiente.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const RAIZ = resolve(process.cwd(), "..");
const manifiesto = JSON.parse(
  readFileSync(resolve(RAIZ, "launcher-manifest.json"), "utf8"),
) as { modules: Array<Record<string, unknown>> };
const proveedor = readFileSync(
  resolve(process.cwd(), "context/DownloadProvider.tsx"),
  "utf8",
);

const COMMIT = /^[0-9a-f]{40}$/;

describe("procedencia de los módulos descargables", () => {
  it("cada URL apunta a un commit inmutable y no a una rama", () => {
    for (const modulo of manifiesto.modules) {
      for (const url of (modulo.urls as string[]) ?? []) {
        const marca = url.split("/resolve/")[1]?.split("/")[0];
        expect(marca, `${modulo.id} descarga de una referencia móvil`).toMatch(COMMIT);
      }
    }
  });

  it("la revisión declarada es ese mismo commit", () => {
    for (const modulo of manifiesto.modules) {
      expect(String(modulo.revision), `${modulo.id}`).toMatch(COMMIT);
      const url = ((modulo.urls as string[]) ?? [])[0] ?? "";
      const marca = url.split("/resolve/")[1]?.split("/")[0];
      expect(marca, `${modulo.id}: la URL y la revisión declarada discrepan`).toBe(
        String(modulo.revision),
      );
    }
  });

  it("todo módulo conserva su hash: el commit no lo sustituye", () => {
    for (const modulo of manifiesto.modules) {
      expect(String(modulo.sha256), `${modulo.id}`).toMatch(/^[0-9a-f]{64}$/);
    }
  });
});

describe("respaldo de fuentes", () => {
  it("el descargador recorre las URL en vez de quedarse con la primera", () => {
    expect(proveedor).not.toMatch(/const url = entry\.urls\?\.\[0\]/);
    expect(proveedor).toContain("for (let i = 0; i < urls.length; i += 1)");
  });

  it("verifica el sha256 en cualquier fuente que responda", () => {
    // El hash viaja en la misma llamada que la URL: no hay camino que descargue
    // sin verificar, ni siquiera desde un espejo.
    const llamada = proveedor.slice(
      proveedor.indexOf("const descargarCon"),
      proveedor.indexOf("if (entry.type === \"archive\")"),
    );
    expect(llamada).toContain("sha256: entry.sha256");
  });

  it("una cancelación no se reintenta contra la siguiente fuente", () => {
    expect(proveedor).toMatch(/cancelada[\s\S]{0,120}throw err/);
  });

  it("un módulo sin URL falla diciéndolo, no en silencio", () => {
    expect(proveedor).toContain("no declara ninguna URL de descarga");
  });
});
