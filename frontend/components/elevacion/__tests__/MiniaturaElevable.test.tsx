import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { fetchBackend } from "../../../lib/backendFetch";
import MiniaturaElevable from "../MiniaturaElevable";

vi.mock("../../../lib/backendFetch", () => ({ fetchBackend: vi.fn() }));
vi.mock("../../../lib/api", () => ({ getAuthHeaders: () => ({}) }));
vi.mock("../../../context/LanguageContext", () => ({ useLanguage: () => ({ t: (clave: string) => clave }) }));

const pose = (fiel: boolean) => ({
  contrato: "elevacion/v1",
  fuente: "pose_vina_top1",
  lienzo: 300,
  svg: "<svg/>",
  atomos: [
    { elemento: "C", carga: 0, hidrogenos: 3, plano: [100, 160], xyz: [102, 158, -20] },
    { elemento: "O", carga: 0, hidrogenos: 1, plano: [150, 130], xyz: [149, 131, 15] },
  ],
  enlaces: [{ a: 0, b: 1, orden: 1 }],
  desajuste_px: fiel ? 2 : 40,
  enlace_px: 30,
  razon_enlaces: fiel ? 0.07 : 1.3,
  fiel,
  pose: { registro: 1, afinidad_kcal_mol: -6, sdf_sha256: "0".repeat(64), task_id: "t", validez_fisica: null },
});

describe("MiniaturaElevable: una pose que no se levanta se enseña en 3D", () => {
  beforeEach(() => {
    vi.mocked(fetchBackend).mockReset();
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => window.setTimeout(() => cb(performance.now()), 16));
    vi.stubGlobal("cancelAnimationFrame", (id: number) => window.clearTimeout(id));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sin levantar: al pasar el cursor gira la pose, y el título dice por qué no se levanta", async () => {
    vi.mocked(fetchBackend).mockResolvedValue({ ok: true, status: 200, json: async () => pose(false) } as unknown as Response);
    render(<MiniaturaElevable moleculeId="m-no-fiel" taskId="t" imgSrc="blob:x" alt="x" />);
    const ficha = screen.getByTestId("moldex-miniatura");

    fireEvent.pointerEnter(ficha);

    await vi.waitFor(() => expect(ficha.getAttribute("data-elevada")).toBe("true"));
    expect(ficha.getAttribute("title")).toContain("el_no_fiel");
    expect(ficha.getAttribute("title")).toContain("el_validez_fisica_sin");
  });
});
