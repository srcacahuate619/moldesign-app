import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// «Solo veo 3 anti-targets» (propietario, probando 1.0.2 en modo dev).
//
// El panel de selectividad de después del docking tenía las anti-dianas ESCRITAS A
// MANO en el componente: hERG, CYP3A4 y 5-HT2B. Tres, siendo CYP3A4 una que el backend
// ya no lleva por defecto, mientras `GET /pro/anti-targets` ofrece las 44 de Bowes 2012
// (40 seleccionables) y el selector de «Parámetros de la evaluación» ya las mostraba.
// Además `computeMetrics` sólo recorría esas tres: una anti-diana adicional salía en
// su tarjeta pero no entraba en el peor caso, el veredicto ni las alertas.

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

const MOLECULA = "33333333-3333-3333-3333-333333333333";

/** Las 44 del API: hERG y 5-HT2B por defecto, 38 opcionales disponibles y 4 sin estructura. */
const filas = Array.from({ length: 44 }, (_, i) => ({
  pdb_id: i === 0 ? "5VA1" : i === 1 ? "7SRQ" : i < 40 ? `X${i}` : null,
  name: i === 0 ? "hERG (KCNH2)" : i === 1 ? "5-HT2B (HTR2B)" : `Diana ${i}`,
  category: i < 2 ? "Cardiac" : "Bowes 2012 · GPCR",
  risk: i < 2 ? "Riesgo declarado del panel." : "Diana del panel mínimo de Bowes et al. 2012.",
  threshold_kcal: i === 1 ? -7.5 : -7,
  por_defecto: i < 2,
  disponible: i < 40,
  seleccionable: i < 40,
  motivo_no_disponible: i < 40 ? null : "Sin estructura humana",
}));

function conApi(anti_targets: unknown[] | "falla") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => (anti_targets === "falla"
      ? { ok: false, json: async () => ({}) }
      : { ok: true, json: async () => ({ anti_targets }) })),
  );
}

const tarjetas = () => screen.getAllByRole("button", { name: /^(Evaluar|Reevaluar)$/ });

beforeEach(() => {
  dockSingleAntiTarget.mockReset();
  saveSelectivityResults.mockReset().mockResolvedValue({ success: true });
  getEvaluationResult.mockReset().mockResolvedValue(null);
});
afterEach(() => vi.unstubAllGlobals());

describe("el panel sale del API, no de tres filas escritas a mano", () => {
  it("por defecto muestra hERG y 5-HT2B (no CYP3A4) y ofrece elegir entre las demás", async () => {
    conApi(filas);
    render(<ProSelectivityPanel moleculeId={MOLECULA} />);

    await waitFor(() => expect(tarjetas()).toHaveLength(2));
    expect(within(screen.getByRole("region", { name: "Mi panel" })).getByText("hERG (KCNH2)")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Mi panel" })).getByText("5-HT2B (HTR2B)")).toBeInTheDocument();
    expect(screen.queryByText("CYP3A4")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Catálogo de anti-dianas" })).toBeInTheDocument();
  });

  it("el catálogo visible enseña las 44, con las 4 sin estructura deshabilitadas, y marcar una la añade al panel", async () => {
    conApi(filas);
    render(<ProSelectivityPanel moleculeId={MOLECULA} />);
    await waitFor(() => expect(tarjetas()).toHaveLength(2));

    const casillas = await screen.findAllByRole("checkbox");
    expect(casillas).toHaveLength(44);
    expect(casillas.filter((c) => (c as HTMLInputElement).checked)).toHaveLength(2);
    expect(casillas.filter((c) => (c as HTMLInputElement).disabled)).toHaveLength(4);

    fireEvent.click(screen.getByRole("checkbox", { name: /Diana 7/ }));
    await waitFor(() => expect(tarjetas()).toHaveLength(3));
    expect(screen.getAllByText("Diana 7").length).toBeGreaterThan(0);
    // El contador del resumen cuenta sobre las tres del panel, no sobre un número escrito a mano.
    expect(screen.getByText("0/3")).toBeInTheDocument();
  });

  it("«Ninguna» deja el panel vacío y lo dice, en vez de volver a las de siempre", async () => {
    conApi(filas);
    render(<ProSelectivityPanel moleculeId={MOLECULA} />);
    await waitFor(() => expect(tarjetas()).toHaveLength(2));
    fireEvent.click(await screen.findByRole("button", { name: "Ninguna" }));

    await waitFor(() => expect(screen.queryAllByRole("button", { name: /^(Evaluar|Reevaluar)$/ })).toHaveLength(0));
    expect(screen.getByText(/No hay ninguna anti-diana elegida/)).toBeInTheDocument();
  });

  it("«Evaluar seleccionadas» acopla sólo las elegidas, no las 44", async () => {
    conApi(filas);
    dockSingleAntiTarget.mockImplementation(async (_m: string, pdb: string) => ({
      target: { pdb_id: pdb, name: pdb, affinity: -6, status: "ok", threshold: -7 },
    }));
    render(<ProSelectivityPanel moleculeId={MOLECULA} />);
    await waitFor(() => expect(tarjetas()).toHaveLength(2));

    fireEvent.click(screen.getByRole("button", { name: /evaluar seleccionadas/i }));
    await waitFor(() => expect(dockSingleAntiTarget).toHaveBeenCalledTimes(2));
    expect(dockSingleAntiTarget.mock.calls.map((c) => c[1])).toEqual(["5VA1", "7SRQ"]);
  });
});

describe("las métricas cuentan TODAS las anti-dianas del panel", () => {
  it("muestra los recuentos del catálogo y permite buscar por PDB y filtrar por familia sin perder la selección", async () => {
    conApi(filas);
    render(<ProSelectivityPanel moleculeId={MOLECULA} />);
    await screen.findAllByRole("checkbox");
    expect(screen.getByText("44 en catálogo")).toBeInTheDocument();
    expect(screen.getByText("40 disponibles")).toBeInTheDocument();
    expect(screen.getByText("4 no disponibles")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Buscar anti-diana" }), { target: { value: "x7" } });
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    fireEvent.click(screen.getByRole("checkbox", { name: /Diana 7/ }));
    expect(dockSingleAntiTarget).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Evaluar seleccionadas (3)" })).toBeEnabled();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Familia" }), { target: { value: "Cardiac" } });
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
    expect(within(screen.getByRole("region", { name: "Mi panel" })).getByText("Diana 7")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Familia" }), { target: { value: "" } });
    expect(screen.getByRole("checkbox", { name: /Diana 7/ })).toBeChecked();
  });

  it("una búsqueda sin resultados conserva el panel y los totales del catálogo", async () => {
    conApi(filas);
    render(<ProSelectivityPanel moleculeId={MOLECULA} />);
    await screen.findAllByRole("checkbox");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no existe" } });
    expect(screen.getByText(/No hay coincidencias/)).toBeInTheDocument();
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(tarjetas()).toHaveLength(2);
    expect(screen.getByText("44 en catálogo")).toBeInTheDocument();
  });

  it("conserva un resultado fuera de la selección y no lo vuelve a calcular al evaluar las seleccionadas", async () => {
    conApi(filas);
    dockSingleAntiTarget.mockImplementation(async (_m: string, pdb: string) => ({ target: { pdb_id: pdb, affinity: -6, status: "ok", threshold: -7 } }));
    render(<ProSelectivityPanel moleculeId={MOLECULA} initialResult={{ off_targets: [{ pdb_id: "X7", name: "Diana 7", affinity: -5, status: "ok", threshold: -7 }] }} />);
    await screen.findAllByRole("checkbox");
    const panel = within(screen.getByRole("region", { name: "Mi panel" }));
    expect(panel.getByText("Diana 7")).toBeInTheDocument();
    expect(panel.getByText(/Resultado anterior · fuera/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Diana 7/ })).not.toBeChecked();
    const evaluar = screen.getByRole("button", { name: "Evaluar seleccionadas (2)" });
    fireEvent.click(evaluar);
    await waitFor(() => expect(dockSingleAntiTarget).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByRole("button", { name: "Evaluar seleccionadas (2)" })).toBeEnabled());
    expect(dockSingleAntiTarget.mock.calls.map((call) => call[1])).toEqual(["5VA1", "7SRQ"]);
    expect(panel.getByText("Diana 7")).toBeInTheDocument();
    expect(saveSelectivityResults.mock.calls.at(-1)?.[1].off_targets.some((row: any) => row.pdb_id === "X7" && row.affinity === -5)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Ninguna" }));
    expect(screen.getByRole("button", { name: "Evaluar seleccionadas (0)" })).toBeDisabled();
    expect(panel.getByText("Diana 7")).toBeInTheDocument();
  });

  it("una adicional que rebasa su umbral entra en las alertas aunque no sea una de las tres de siempre", async () => {
    conApi(filas);
    render(
      <ProSelectivityPanel
        moleculeId={MOLECULA}
        onTargetAffinity={-6}
        initialResult={{
          off_targets: [
            { pdb_id: "5VA1", name: "hERG (KCNH2)", affinity: -5, status: "ok", threshold: -7 },
            { pdb_id: "X7", name: "Diana 7", category: "GPCR", affinity: -9.2, status: "ok", threshold: -7 },
          ],
        }}
      />,
    );

    // Antes la alerta (y el peor caso) sólo miraba hERG/CYP3A4/5-HT2B: «Diana 7» quedaba fuera del veredicto.
    expect(await screen.findByText(/ALERTA Diana 7/)).toBeInTheDocument();
    // Y cuenta en el progreso: hERG, 5-HT2B (sin resultado) y Diana 7.
    expect(screen.getByText("2/3")).toBeInTheDocument();
  });
});

describe("si el API no responde", () => {
  it("el panel cae al por defecto del backend (hERG y 5-HT2B) y el selector pide reintentar", async () => {
    conApi("falla");
    render(<ProSelectivityPanel moleculeId={MOLECULA} />);

    await waitFor(() => expect(tarjetas()).toHaveLength(2));
    expect(screen.queryByText("CYP3A4")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});

describe("«Saber más» de una anti-diana sin ficha propia", () => {
  it("enseña el riesgo que declara el panel y dice que no hay ficha, no tres secciones vacías", async () => {
    conApi(filas);
    render(
      <ProSelectivityPanel
        moleculeId={MOLECULA}
        initialResult={{ off_targets: [{ pdb_id: "X7", name: "Diana 7", category: "GPCR", affinity: null, status: "sin_sitio" }] }}
      />,
    );
    await within(screen.getByRole("region", { name: "Mi panel" })).findByText("Diana 7");
    // Orden del panel: hERG, 5-HT2B (por defecto) y, detrás, lo que sólo está en los resultados: Diana 7.
    const sabeMas = screen.getAllByRole("button", { name: /saber más/i });
    expect(sabeMas).toHaveLength(3);
    fireEvent.click(sabeMas[2]);

    expect(await screen.findByText(/no tiene una ficha explicativa propia/)).toBeInTheDocument();
    expect(screen.queryByText(/Estrategias de Optimización SAR/)).not.toBeInTheDocument();
  });
});
