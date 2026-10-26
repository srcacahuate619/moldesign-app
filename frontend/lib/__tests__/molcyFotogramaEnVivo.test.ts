import { beforeEach, describe, expect, it, vi } from "vitest";

const red = vi.hoisted(() => ({ fetchBackend: vi.fn() }));
vi.mock("../backendFetch", () => red);
vi.mock("../api", async load => ({ ...await load<object>(), getAuthHeaders: () => ({}) }));

import { fotogramaMolcy, pieDelFotograma } from "../molcy";

const PNG = new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" });

function respuesta(cabeceras: Record<string, string>) {
  return new Response(PNG, { status: 200, headers: { "Content-Type": "image/png", ...cabeceras } });
}

beforeEach(() => {
  red.fetchBackend.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:fotograma");
});

describe("el fotograma en vivo de Molcy", () => {
  it("lee el número del guion, su orden entre los rendidos y el total", async () => {
    red.fetchBackend.mockResolvedValue(respuesta({ "X-Molcy-Fotograma": "681", "X-Molcy-Orden": "545", "X-Molcy-Total": "667" }));
    expect(await fotogramaMolcy("job")).toEqual({ url: "blob:fotograma", indice: 681, orden: 545, total: 667 });
  });

  it("sin orden legible lo deja en 0 en vez de inventarlo", async () => {
    red.fetchBackend.mockResolvedValue(respuesta({ "X-Molcy-Fotograma": "7", "X-Molcy-Orden": "x", "X-Molcy-Total": "667" }));
    expect(await fotogramaMolcy("job")).toMatchObject({ indice: 7, orden: 0, total: 667 });
  });
});

describe("el pie del fotograma en vivo", () => {
  it("con pausas pone sobre el total el orden entre los rendidos, no el número del guion («681 de 667»)", () => {
    expect(pieDelFotograma({ indice: 681, orden: 545, total: 667 }))
      .toEqual({ clave: "cy_live_frame", valores: { done: 545, total: 667 } });
  });

  it("sin pausas los dos números coinciden", () => {
    expect(pieDelFotograma({ indice: 12, orden: 12, total: 360 }).valores).toEqual({ done: 12, total: 360 });
  });

  it("sin total enseña sólo el número; sin orden, el del guion, que no va sobre ningún total", () => {
    expect(pieDelFotograma({ indice: 3, orden: 3, total: 0 })).toEqual({ clave: "cy_live_frame_sin_total", valores: { done: 3 } });
    expect(pieDelFotograma({ indice: 681, orden: 0, total: 667 }))
      .toEqual({ clave: "cy_live_frame_sin_total", valores: { done: 681 } });
  });
});
