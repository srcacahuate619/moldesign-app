// =====================================================================
// Elegir un receptor no decide por la investigadora los residuos de referencia
// =====================================================================
//
// QA1-007. Medido en la cápsula de QA con la petición real a `/evaluation/submit`:
// una corrida lanzada sin tocar «Opciones» enviaba `custom_hotspots: []`. El
// backend distingue `null` («nunca se abrió Opciones»: hereda los del catálogo) de
// `[]` («no quiero residuos de referencia»: una decisión), y `setTarget` fijaba `[]`
// al elegir el receptor. Resultado: el preflight decía «0 residuos por decisión del
// investigador», «Opciones» decía «15/15 activos», y la corrida iba sin residuos de
// referencia —sin análisis de contactos— sin que nadie lo hubiera decidido.
//
// `ProEvaluation` se mockea: aquí se prueba lo que el runner guarda en el caso al
// elegir receptor, no la interfaz de evaluación.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const getTargets = vi.fn();
const authState = vi.hoisted(() => ({
  isLoading: false,
  token: "token-prueba",
  user: { user_id: "usuario-prueba" },
  logout: vi.fn(),
}));

vi.mock("../../../lib/auth", () => ({ useAuth: () => authState }));

vi.mock("../../../lib/api", () => ({
  ApiError: class extends Error {},
  getJobStatus: vi.fn(),
  getEvaluationResult: vi.fn(),
  getTargets: () => getTargets(),
  submitEvaluation: vi.fn(),
  validateSmiles: vi.fn(),
  cancelEvaluation: vi.fn(),
  certifyMolecule: vi.fn(),
  downloadCertificate: vi.fn(),
  getComplexFile: vi.fn(),
  saveMolecule: vi.fn(),
}));

vi.mock("../../../lib/sounds", () => ({ playSound: vi.fn() }));

vi.mock("../../interfaces/pro/ProEvaluation", () => ({
  default: ({ setTarget }: { setTarget: (id: string) => void }) => (
    <button onClick={() => setTarget("4AZY")}>Elegir 4AZY</button>
  ),
}));

import CaseEvaluationRunner from "../CaseEvaluationRunner";
import { invalidarCatalogo } from "../../../lib/catalogoDeReceptores";

const BACE1 = {
  id: "id-4azy",
  pdb_id: "4AZY",
  name: "BACE1",
  chain: "A",
  grid_center_x: 5.427,
  grid_center_y: 1.673,
  grid_center_z: -21.014,
  grid_size_x: 30,
  grid_size_y: 30,
  grid_size_z: 30,
  hotspots: [{ name: "A:ASP32", importance: 0.94 }],
};

beforeEach(() => {
  invalidarCatalogo();
  getTargets.mockReset();
  getTargets.mockResolvedValue([BACE1]);
});

describe("elegir un receptor (QA1-007)", () => {
  it("guarda la caja del catálogo pero NO fija una selección de residuos", async () => {
    const onInputsChange = vi.fn();
    render(<CaseEvaluationRunner caseId="caso-1" onInputsChange={onInputsChange} />);
    await waitFor(() => expect(getTargets).toHaveBeenCalled());

    fireEvent.click(await screen.findByText("Elegir 4AZY"));

    await waitFor(() => expect(onInputsChange).toHaveBeenCalled());
    const patch = onInputsChange.mock.calls[0][0];

    expect(patch.receptor.pdbId).toBe("4AZY");
    expect(patch.grid).toEqual({ center: [5.427, 1.673, -21.014], size: [30, 30, 30] });

    // La clave tiene que VIAJAR (con `undefined`) para borrar la selección del
    // receptor anterior, pero su valor no puede ser `[]`: `[]` es la decisión «ninguno».
    expect(Object.prototype.hasOwnProperty.call(patch, "customHotspots")).toBe(true);
    expect(patch.customHotspots).toBeUndefined();
    expect(patch.customHotspots).not.toEqual([]);
  });
});
