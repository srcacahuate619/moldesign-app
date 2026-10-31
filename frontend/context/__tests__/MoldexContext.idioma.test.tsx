import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock("../../lib/api", () => ({ getMoldex: api.list, getProteinFile: vi.fn(), getPoseFile: vi.fn() }));
vi.mock("../LanguageContext", async (cargar) => {
  const real = await cargar<typeof import("../LanguageContext")>();
  const t = (clave: string) => real.TRANSLATIONS.en[clave] ?? clave;
  return { ...real, useLanguage: () => ({ locale: "en", t }) };
});
import { MoldexProvider, useMoldex } from "../MoldexContext";

const wrapper = ({ children }: { children: ReactNode }) => <MoldexProvider>{children}</MoldexProvider>;
beforeEach(() => { api.list.mockReset(); vi.spyOn(console, "error").mockImplementation(() => {}); });

describe("fallo al cargar Moldex", () => {
  it("presenta en inglés la alternativa cuando el error no trae detalle", async () => {
    api.list.mockRejectedValue(new Error(""));
    const { result } = renderHook(() => useMoldex(), { wrapper });
    await waitFor(() => expect(result.current.error).toBe("Could not load the library."));
  });

  it("conserva sin traducir el detalle que viene de una fuente externa", async () => {
    api.list.mockRejectedValue(new Error("external error / ejemplo"));
    const { result } = renderHook(() => useMoldex(), { wrapper });
    await waitFor(() => expect(result.current.error).toBe("external error / ejemplo"));
  });
});
