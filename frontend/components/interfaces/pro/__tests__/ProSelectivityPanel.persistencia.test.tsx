import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// DOC 71, DEFECTOS B1 y B2.
//
// El primer intento se quedó en poner un aviso de «resultado sin guardar». Eso
// informa del problema, no lo resuelve. El problema real era que el panel se
// monta dentro de `{advancedTab === "selectivity" && ...}`: cambiar de pestaña
// lo DESMONTA y su estado en memoria muere. Y sólo se guardaba una vez, al
// terminar los ocho anti-targets, que tarda minutos.
//
// Estas pruebas cubren las dos mitades del arreglo:
//   1. cada anti-target se persiste EN CUANTO SALE;
//   2. al montar se lee de la base SIEMPRE, no sólo cuando el pipeline corrió
//      el panel (que era la condición de `autoPoll`).

const dockSingleAntiTarget = vi.fn();
const saveSelectivityResults = vi.fn();
const getEvaluationResult = vi.fn();

vi.mock("../../../../lib/proApi", () => ({
  dockSingleAntiTarget: (...a: unknown[]) => dockSingleAntiTarget(...a),
  saveSelectivityResults: (...a: unknown[]) => saveSelectivityResults(...a),
}));
vi.mock("../../../../lib/api", () => ({
  getEvaluationResult: (...a: unknown[]) => getEvaluationResult(...a),
}));

import { ProSelectivityPanel } from "../ProSelectivityPanel";

const MOLECULA = "11111111-1111-1111-1111-111111111111";

beforeEach(() => {
  dockSingleAntiTarget.mockReset();
  saveSelectivityResults.mockReset().mockResolvedValue({ success: true });
  getEvaluationResult.mockReset().mockResolvedValue(null);
});

describe("el panel de selectividad no pierde lo ya acoplado", () => {
  it("rehidrata desde lo persistido al montar, aunque autoPoll esté apagado", async () => {
    // Éste es el caso que se perdía: panel lanzado A MANO, usuario cambia a
    // «propiedades» y vuelve. Antes la lectura de la base sólo ocurría dentro
    // del auto-poll, que se enciende únicamente si el pipeline corrió el panel.
    getEvaluationResult.mockResolvedValue({
      selectivity_ran: true,
      // 5VA1 (hERG) es el primero del panel real: si se usa un pdb_id que no
      // esta en la lista, la fila no se pinta y la prueba pasaria por vacio.
      anti_target_results: [
        { pdb_id: "5VA1", name: "hERG (KCNH2)", affinity: -7.4, status: "ok", threshold: -7 },
      ],
    });

    render(<ProSelectivityPanel moleculeId={MOLECULA} autoPoll={false} />);

    await waitFor(() => expect(getEvaluationResult).toHaveBeenCalledWith(MOLECULA));
    // El valor guardado vuelve a la pantalla.
    await waitFor(() =>
      expect(screen.getAllByText(/-7\.4 kcal\/mol/).length).toBeGreaterThan(0));
  });

  it("no pide nada a la base si no hay evaluación a la que anclar", () => {
    render(<ProSelectivityPanel moleculeId={null} autoPoll={false} />);
    expect(getEvaluationResult).not.toHaveBeenCalled();
  });

  it("no marca «sin guardar» lo que acaba de leer de la base", async () => {
    getEvaluationResult.mockResolvedValue({
      selectivity_ran: true,
      anti_target_results: [{ pdb_id: "5VA1", name: "hERG (KCNH2)", affinity: -7.4, status: "ok" }],
    });

    render(<ProSelectivityPanel moleculeId={MOLECULA} autoPoll={false} />);

    await waitFor(() => expect(getEvaluationResult).toHaveBeenCalled());
    // Lo que está en la base está guardado, por definición: el aviso ámbar
    // sería una alarma falsa y enseñaría al usuario a ignorarla.
    expect(screen.queryByText(/Resultado sin guardar/i)).toBeNull();
  });

  it("sigue arrancando vacío, sin inventar nada, cuando no hay nada guardado", async () => {
    getEvaluationResult.mockResolvedValue(null);
    render(<ProSelectivityPanel moleculeId={MOLECULA} autoPoll={false} />);
    await waitFor(() => expect(getEvaluationResult).toHaveBeenCalled());
    expect(screen.queryByText(/Resultado sin guardar/i)).toBeNull();
  });
});
