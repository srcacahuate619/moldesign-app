import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

// AMP-09 / AMP-10.
//
// AMP-10. En una corrida histórica, «Reevaluar hERG» devolvía 409 («La corrida
// cambió; no se calcula selectividad para otra evaluación») y el panel pasaba a
// mostrar hERG como «Sin evaluar», aunque la base seguía guardando su resultado.
// Un rechazo de una ampliación no puede borrar evidencia ya registrada, y quien
// pulsa tiene que enterarse de por qué no se puede.
//
// AMP-09. El contador de progreso tenía el denominador escrito a mano (5) en un
// panel de TRES anti-dianas: tras reabrir, «Progreso: 2/5 evaluados» declaraba
// dos cosas pendientes que no existen.

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

const MOLECULA = "22222222-2222-2222-2222-222222222222";
const MOTIVO_409 = "La corrida cambió; no se calcula selectividad para otra evaluación.";

/** Lo que `ProApiError` lleva: un `Error` con `status`. */
function rechazo409(): Error {
  return Object.assign(new Error(MOTIVO_409), { status: 409 });
}

const REABIERTO = {
  off_targets: [
    { pdb_id: "5VA1", name: "hERG (KCNH2)", affinity: -7.4, status: "ok", threshold: -7 },
    { pdb_id: "7SRQ", name: "5-HT2B", affinity: -5.6, status: "ok", threshold: -8 },
    { pdb_id: "4NY4", name: "M1", affinity: null, status: "sin_sitio" },
  ],
};

// El panel se arma con la lista del API; aquí, la del panel por defecto del backend (hERG y 5-HT2B).
const PANEL_POR_DEFECTO = [
  { pdb_id: "5VA1", name: "hERG (KCNH2)", category: "Cardiac", risk: "", threshold_kcal: -7, por_defecto: true, disponible: true },
  { pdb_id: "7SRQ", name: "5-HT2B (HTR2B)", category: "CNS/Safety", risk: "", threshold_kcal: -7.5, por_defecto: true, disponible: true },
];

beforeEach(() => {
  dockSingleAntiTarget.mockReset();
  saveSelectivityResults.mockReset().mockResolvedValue({ success: true });
  getEvaluationResult.mockReset().mockResolvedValue(null);
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ anti_targets: PANEL_POR_DEFECTO }) })));
});

afterEach(() => vi.unstubAllGlobals());

function abrirReabierto() {
  return render(
    <ProSelectivityPanel moleculeId={MOLECULA} onTargetAffinity={-5.4} initialResult={REABIERTO} />,
  );
}

describe("AMP-09: el progreso de lo recuperado cuenta sobre el panel real", () => {
  it("dos de tres anti-dianas con afinidad dicen 2/3, no 2/5", () => {
    abrirReabierto();
    expect(screen.getByText("2/3")).toBeInTheDocument();
    expect(screen.queryByText("2/5")).not.toBeInTheDocument();
  });

  it("un panel recuperado sin ninguna afinidad dice 0/2 (hERG y 5-HT2B), no 0/0 ni 0/5", async () => {
    render(
      <ProSelectivityPanel
        moleculeId={MOLECULA}
        initialResult={{ off_targets: [{ pdb_id: "5VA1", name: "hERG", affinity: null, status: "sin_sitio" }] }}
      />,
    );
    expect(await screen.findByText("0/2")).toBeInTheDocument();
  });

  it("la barra y el contador usan el mismo total", () => {
    abrirReabierto();
    const barra = document.querySelector<HTMLElement>(".bg-purple-500.h-full");
    expect(barra?.style.width).toBe(`${(2 / 3) * 100}%`);
  });
});

describe("AMP-10: un rechazo de la ampliación no borra lo registrado", () => {
  it("el 409 conserva la afinidad anterior de hERG y dice por qué no se puede ampliar", async () => {
    dockSingleAntiTarget.mockRejectedValueOnce(rechazo409());
    abrirReabierto();
    expect(screen.getAllByText(/-7\.4 kcal\/mol/).length).toBeGreaterThan(0);

    const botones = screen.getAllByRole("button", { name: "Reevaluar" });
    fireEvent.click(botones[0]);

    const aviso = await screen.findByText(/No se puede ampliar esta evaluación/);
    expect(aviso.closest("[role=alert]")).toHaveTextContent(MOTIVO_409);
    expect(aviso.closest("[role=alert]")).toHaveTextContent("se conservan tal como están");
    // La evidencia sigue ahí: hERG NO pasó a «Sin evaluar».
    expect(screen.getAllByText(/-7\.4 kcal\/mol/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Se conserva el resultado anterior/)).toBeInTheDocument();
    // Y el contador no retrocede.
    expect(screen.getByText("2/3")).toBeInTheDocument();
  });

  it("tras el 409 la ampliación queda apagada para todo el panel, con el motivo visible", async () => {
    dockSingleAntiTarget.mockRejectedValueOnce(rechazo409());
    abrirReabierto();
    fireEvent.click(screen.getAllByRole("button", { name: "Reevaluar" })[0]);
    await screen.findByText(/No se puede ampliar esta evaluación/);

    for (const boton of screen.getAllByRole("button", { name: /Reevaluar|Evaluar$/ })) {
      expect(boton).toBeDisabled();
    }
    expect(screen.getByRole("button", { name: /evaluar seleccionadas/i })).toBeDisabled();
    expect(dockSingleAntiTarget).toHaveBeenCalledTimes(1);
  });

  it("«evaluar seleccionadas» se detiene en el primer 409 y no repite el rechazo contra las demás", async () => {
    dockSingleAntiTarget.mockRejectedValue(rechazo409());
    abrirReabierto();
    fireEvent.click(screen.getByRole("button", { name: /evaluar seleccionadas/i }));
    await screen.findByText(/No se puede ampliar esta evaluación/);
    await waitFor(() => expect(dockSingleAntiTarget).toHaveBeenCalledTimes(1));
    // Lo previo sigue en pantalla y nada se guardó encima.
    expect(screen.getAllByText(/-7\.4 kcal\/mol/).length).toBeGreaterThan(0);
    expect(saveSelectivityResults).not.toHaveBeenCalled();
  });

  it("un fallo que NO es 409 sobre un resultado previo también lo conserva, sin apagar la ampliación", async () => {
    dockSingleAntiTarget.mockRejectedValueOnce(new Error("Vina no respondió"));
    abrirReabierto();
    fireEvent.click(screen.getAllByRole("button", { name: "Reevaluar" })[0]);
    expect(await screen.findByText(/Vina no respondió/)).toBeInTheDocument();
    expect(screen.getAllByText(/-7\.4 kcal\/mol/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/No se puede ampliar esta evaluación/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Reevaluar" })[0]).not.toBeDisabled();
  });

  it("una anti-diana SIN resultado previo que falla sigue quedando fallida, como siempre", async () => {
    dockSingleAntiTarget.mockRejectedValueOnce(new Error("sin caja"));
    abrirReabierto();
    // 4NY4 es la que no tenía afinidad: su botón dice «Evaluar», no «Reevaluar».
    const botones = screen.getAllByRole("button", { name: "Evaluar" });
    fireEvent.click(botones[botones.length - 1]);
    await waitFor(() => expect(dockSingleAntiTarget).toHaveBeenCalled());
    expect(screen.queryByText(/Se conserva el resultado anterior/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/-7\.4 kcal\/mol/).length).toBeGreaterThan(0);
  });

  it("una reevaluación que sale bien limpia el aviso anterior", async () => {
    dockSingleAntiTarget
      .mockRejectedValueOnce(new Error("Vina no respondió"))
      .mockResolvedValueOnce({ target: { pdb_id: "5VA1", name: "hERG (KCNH2)", affinity: -7.9, status: "ok", threshold: -7 } });
    abrirReabierto();
    fireEvent.click(screen.getAllByRole("button", { name: "Reevaluar" })[0]);
    await screen.findByText(/Vina no respondió/);
    fireEvent.click(screen.getAllByRole("button", { name: "Reevaluar" })[0]);
    await waitFor(() => expect(screen.getAllByText(/-7\.9 kcal\/mol/).length).toBeGreaterThan(0));
    expect(screen.queryByText(/Vina no respondió/)).not.toBeInTheDocument();
  });
});
