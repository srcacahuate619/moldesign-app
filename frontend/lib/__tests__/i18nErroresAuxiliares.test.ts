import { beforeEach, describe, expect, it, vi } from "vitest";
import { TRANSLATIONS } from "../../context/LanguageContext";
import { setTauriEnv } from "../../vitest.setup";

const red = vi.hoisted(() => ({ fetchBackend: vi.fn() }));
vi.mock("../backendFetch", () => red);

import { traspasarDelInvitado } from "../api";
import { presentError, type Translate } from "../frontendError";
import { fotogramaMolcy } from "../molcy";

const ingles: Translate = (clave, valores) => (TRANSLATIONS.en[clave] ?? clave)
  .replace(/\{(\w+)\}/g, (texto, nombre: string) => String(valores?.[nombre] ?? texto));
const castellano: Translate = (clave, valores) => (TRANSLATIONS.es[clave] ?? clave)
  .replace(/\{(\w+)\}/g, (texto, nombre: string) => String(valores?.[nombre] ?? texto));

beforeEach(() => { red.fetchBackend.mockReset(); setTauriEnv(false); });

describe("diagnósticos propios conservan el idioma al presentarse", () => {
  it("explica el traspaso fuera del escritorio en ambos idiomas", async () => {
    const error = await traspasarDelInvitado([]).catch((e: unknown) => e);
    expect(presentError(error, ingles)).toBe("Guest transfer requires the desktop app.");
    expect(presentError(error, castellano)).toBe("El traspaso del invitado requiere el escritorio.");
  });

  it("traduce el error HTTP del fotograma sin perder el código", async () => {
    red.fetchBackend.mockResolvedValue(new Response(null, { status: 503 }));
    const error = await fotogramaMolcy("trabajo").catch((e: unknown) => e);
    expect(presentError(error, ingles)).toBe("Molcy: could not read the frame (503).");
    expect(presentError(error, castellano)).toBe("Molcy: no se pudo leer el fotograma (503).");
  });

  it("traduce la respuesta inválida del fotograma", async () => {
    red.fetchBackend.mockResolvedValue(new Response(new Blob(["texto"], { type: "text/plain" }), {
      status: 200, headers: { "X-Molcy-Fotograma": "1" },
    }));
    const error = await fotogramaMolcy("trabajo").catch((e: unknown) => e);
    expect(presentError(error, ingles)).toBe("Molcy: incompatible response; the frame is not a valid image.");
    expect(presentError(error, castellano)).toBe("Molcy: respuesta incompatible; el fotograma no es una imagen válida.");
  });
});
