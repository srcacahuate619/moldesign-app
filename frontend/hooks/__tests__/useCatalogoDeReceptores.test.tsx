import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getTargets = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ getTargets }));

import { useCatalogoDeReceptores } from "../useCatalogoDeReceptores";
import { invalidarCatalogo, VIDA_DEL_CATALOGO_MS } from "@/lib/catalogoDeReceptores";

const receptor = { id: "1UZJ", pdb_id: "1UZJ", name: "Fibrillin", avisos_catalogo: ["SITIO_FUERA_UNIDAD_BIOLOGICA"] };

beforeEach(() => {
  invalidarCatalogo();
  window.localStorage.clear();
  window.localStorage.setItem("moldesign_auth", JSON.stringify({ token: "qa" }));
  getTargets.mockReset().mockResolvedValue([receptor]);
});
afterEach(() => vi.restoreAllMocks());

describe("catálogo en una vista que permanece montada", () => {
  it("renueva al volver a renderizar tras caducar y recupera los avisos", async () => {
    const { result, rerender } = renderHook(() => useCatalogoDeReceptores());
    await waitFor(() => expect(result.current).toEqual([receptor]));
    const despues = Date.now() + VIDA_DEL_CATALOGO_MS + 1;
    vi.spyOn(Date, "now").mockReturnValue(despues);
    let resolver!: (data: typeof receptor[]) => void;
    getTargets.mockReturnValueOnce(new Promise<typeof receptor[]>(resolve => { resolver = resolve; }));
    rerender();
    expect(result.current).toBeNull();
    expect(getTargets).toHaveBeenCalledTimes(2);
    await act(async () => resolver([receptor]));
    await waitFor(() => expect(result.current?.[0].avisos_catalogo).toEqual(receptor.avisos_catalogo));
    rerender();
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("recupera la invalidación de una caché sin cambiar la cuenta", async () => {
    const { result, rerender } = renderHook(() => useCatalogoDeReceptores());
    await waitFor(() => expect(result.current).toEqual([receptor]));
    invalidarCatalogo();
    getTargets.mockResolvedValueOnce([]);
    rerender();
    await waitFor(() => expect(result.current).toEqual([]));
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("una cuenta nueva no recibe el catálogo de la anterior", async () => {
    const { result, rerender } = renderHook(() => useCatalogoDeReceptores());
    await waitFor(() => expect(result.current).toEqual([receptor]));
    window.localStorage.setItem("moldesign_auth", JSON.stringify({ token: "otra" }));
    getTargets.mockResolvedValueOnce([]);
    rerender();
    await waitFor(() => expect(result.current).toEqual([]));
    expect(getTargets).toHaveBeenCalledTimes(2);
  });

  it("deshabilitado no consulta ni enseña el catálogo", async () => {
    const { result } = renderHook(() => useCatalogoDeReceptores(false));
    await act(async () => {});
    expect(result.current).toBeNull();
    expect(getTargets).not.toHaveBeenCalled();
  });
});
