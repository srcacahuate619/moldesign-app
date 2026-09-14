/**
 * El catálogo se pide UNA vez, y nunca se sirve el de otra cuenta.
 *
 * El defecto que esto cierra: `CaseEvaluationRunner` pide el catálogo al
 * montarse y `CaseWorkspace` lo monta con `key={activeCase.id}`, así que cada
 * cambio de caso volvía a bajar 1 225 608 bytes. Medido sobre el runtime
 * empaquetado: 2 486 ms la primera vez, 339 ms de mediana las siguientes en
 * una máquina de desarrollo.
 *
 * Lo que estas pruebas vigilan no es la velocidad —eso se mide fuera— sino las
 * dos cosas que una caché puede romper: servir datos de más (los de otra
 * sesión) y servir datos de menos (no enterarse de un cambio).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getTargets = vi.fn();

vi.mock("../api", () => ({
  getTargets: (...args: unknown[]) => getTargets(...args),
}));

import {
  VIDA_DEL_CATALOGO_MS,
  catalogoEnMemoria,
  invalidarCatalogo,
  obtenerCatalogo,
} from "../catalogoDeReceptores";

const RECEPTOR = { id: "1", pdb_id: "3F75", name: "prueba" };

function sesion(token: string | null): void {
  if (token === null) window.localStorage.removeItem("moldesign_auth");
  else window.localStorage.setItem("moldesign_auth", JSON.stringify({ token }));
}

beforeEach(() => {
  invalidarCatalogo();
  window.localStorage.clear();
  getTargets.mockReset();
  getTargets.mockResolvedValue([RECEPTOR]);
  vi.useRealTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("catálogo de receptores", () => {
  it("dos montajes seguidos hacen UNA sola petición", async () => {
    sesion("t1");
    await obtenerCatalogo();
    await obtenerCatalogo();
    await obtenerCatalogo();
    expect(getTargets).toHaveBeenCalledTimes(1);
  });

  it("dos peticiones a la vez comparten la que está en vuelo", async () => {
    sesion("t1");
    let resolver: (valor: unknown) => void = () => {};
    getTargets.mockReturnValue(new Promise((r) => { resolver = r; }));

    const a = obtenerCatalogo();
    const b = obtenerCatalogo();
    resolver([RECEPTOR]);

    await expect(a).resolves.toHaveLength(1);
    await expect(b).resolves.toHaveLength(1);
    // Sin compartir la promesa esto serían dos descargas de 1,2 MB por cada
    // cambio de caso, porque el runner nuevo monta antes de que el viejo se
    // termine de desmontar.
    expect(getTargets).toHaveBeenCalledTimes(1);
  });

  it("NO sirve el catálogo de otra sesión", async () => {
    sesion("t1");
    await obtenerCatalogo();
    expect(getTargets).toHaveBeenCalledTimes(1);

    // El endpoint declara que deriva los receptores privados de la cuenta
    // autenticada. Reutilizar la respuesta anterior sería enseñar receptores
    // privados de otra cuenta: peor que la lentitud que esto arregla.
    sesion("t2");
    await obtenerCatalogo();
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("cerrar sesión tampoco hereda el catálogo anterior", async () => {
    sesion("t1");
    await obtenerCatalogo();
    sesion(null);
    await obtenerCatalogo();
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("`forzar` vuelve a preguntar aunque haya caché válida", async () => {
    sesion("t1");
    await obtenerCatalogo();
    await obtenerCatalogo({ forzar: true });
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("invalidar obliga a pedirlo de nuevo", async () => {
    sesion("t1");
    await obtenerCatalogo();
    invalidarCatalogo();
    await obtenerCatalogo();
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("caduca, para que una edición externa no quede escondida", async () => {
    sesion("t1");
    await obtenerCatalogo();

    const original = Date.now;
    try {
      const despues = original() + VIDA_DEL_CATALOGO_MS + 1;
      Date.now = () => despues;
      await obtenerCatalogo();
    } finally {
      Date.now = original;
    }
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("un fallo NO se memoriza: el siguiente intento vuelve a pedirlo", async () => {
    sesion("t1");
    getTargets.mockRejectedValueOnce(new Error("motor caído"));
    await expect(obtenerCatalogo()).rejects.toThrow("motor caído");

    getTargets.mockResolvedValue([RECEPTOR]);
    await expect(obtenerCatalogo()).resolves.toHaveLength(1);
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("`catalogoEnMemoria` no pide nada y respeta la identidad", async () => {
    sesion("t1");
    expect(catalogoEnMemoria()).toBeNull();

    await obtenerCatalogo();
    expect(catalogoEnMemoria()).toHaveLength(1);

    sesion("t2");
    expect(catalogoEnMemoria()).toBeNull();
    // Consultar la memoria nunca dispara una petición.
    expect(getTargets).toHaveBeenCalledTimes(1);
  });
});
