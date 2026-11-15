// =====================================================================
// Comparador 3D, fase 3: núcleo común, poses cercanas, contactos y resumen
// =====================================================================
//
// 1. El núcleo común sólo se resalta cuando el backend lo midió (dos ligandos distintos, mismo receptor) y el usuario
//    puede apagarlo; cada visor recibe SUS átomos.
// 2. Cada ficha de pose dice a qué distancia está de la pose elegida del otro lado, la más cercana se marca, y cambiar
//    la pose elegida borra lo anterior en vez de dejar una distancia que ya no es de esa pose. Sin el mismo receptor no
//    se pregunta.
// 3. Los contactos se calculan al pedirlos, sólo con el mismo receptor, se agrupan (sólo izquierda / en las dos / sólo
//    derecha), se dibujan si el usuario quiere, y valen para ESAS dos poses.
// 4. El resumen que se copia lleva lo mismo que la pantalla, con sus límites; si el portapapeles falla, se dice.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  poses: vi.fn(), protein: vi.fn(), resultado: vi.fn(), interactions: vi.fn(),
  same: vi.fn(), run: vi.fn(), analog: vi.fn(), matches: vi.fn(),
}));
vi.mock("../../../../lib/api", () => ({
  getPoseFile: api.poses, getProteinFile: api.protein, getEvaluationResult: api.resultado, getInteractions: api.interactions,
}));
vi.mock("../../../../lib/proApi", () => ({
  getSameRunPoseComparison: api.same, getRunPoseComparison: api.run, getAnalogPoseComparison: api.analog, getPoseMatches: api.matches,
}));
vi.mock("../../../MoleculeViewer3D", () => ({
  MoleculeViewer3D: (props: {
    poseData: string; overlayPoseData?: string; primaryCoreAtoms?: number[]; overlayCoreAtoms?: number[]; contactLines?: unknown[];
  }) => (
    <pre
      data-testid="pose-input"
      data-overlay={props.overlayPoseData ?? ""}
      data-nucleo={JSON.stringify(props.primaryCoreAtoms ?? null)}
      data-nucleo-superpuesto={JSON.stringify(props.overlayCoreAtoms ?? null)}
      data-lineas={String(props.contactLines?.length ?? 0)}
    >
      {props.poseData}
    </pre>
  ),
}));

import { PoseComparisonDialog } from "../PoseComparisonDialog";

const sdf = (id: string, n = 9) => Array.from({ length: n }, (_, i) => `${id}-${i + 1}\nAudit\n\nM  END\n$$$$\n`).join("");
const fuente = (taskId: string, moleculeId = "mol") => ({ taskId, moleculeId, etiqueta: `Corrida ${taskId}` });
const visores = () => screen.getAllByTestId("pose-input");

const medidaMisma = (frame: "same" | "different" = "same") => ({
  frame,
  a: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -6 },
  difference: {
    b_minus_a_vina_kcal_mol: 1,
    pose_rmsd_between_runs: frame === "same"
      ? { available: true, reason_code: null, rmsd_angstrom: 0.42, heavy_atoms: 10 }
      : { available: false, reason_code: "DIFFERENT_RECEPTOR", rmsd_angstrom: null, heavy_atoms: null },
  },
  protocol_differences: [{ field: "seed", a: 42, b: 7 }],
});
const medidaAnalogos = (frame: "same" | "different" = "same") => ({
  frame,
  a: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -7.4 },
  difference: {
    b_minus_a_vina_kcal_mol: -0.4,
    affinity_delta_comparable: true,
    core_rmsd: frame === "same"
      ? {
        available: true, reason_code: null, rmsd_angstrom: 1.1, core_heavy_atoms: 12, core_fraction_of_smaller: 0.9,
        core_atoms: { a: [0, 1, 2], b: [0, 1, 7], index_basis: "sdf_atom_index_zero_based" },
      }
      : { available: false, reason_code: "DIFFERENT_RECEPTOR", rmsd_angstrom: null },
  },
  protocol_differences: [],
});

const dato = (type: string, name: string, number: number, distance: number) => ({
  type, residue: `${name}${number}A`, residue_name: name, residue_number: number, residue_chain: "A",
  distance, angle: null, strength: null, ligand_atom: "O1", protein_atom: "OG",
  ligand_coords: { x: 0, y: 0, z: number }, protein_coords: { x: 2, y: 0, z: number },
});
const informe = (interactions: unknown[], extra: Record<string, unknown> = {}) => ({
  engine: "prolif:2.0.3", protein_source_sha256: "rec", contact_coverage: "first_match_per_type_and_residue",
  hydrogen_model: "rdkit_add_hs_coordinates", interactions, ...extra,
});

/** Las poses de la corrida B contra la pose elegida de A: la 4 es la más cercana. */
const coincidencias = (cercana: number) => ({
  kind: "molecule", frame: "same", available: true, reason_code: null,
  matches: Array.from({ length: 9 }, (_, i) => ({
    rank: i + 1, available: true, reason_code: null, rmsd_angstrom: i + 1 === cercana ? 0.31 : 2 + (i + 1) / 10,
  })),
  closest_rank: cercana, closest_rmsd_angstrom: 0.31,
});

beforeEach(() => {
  api.poses.mockReset().mockImplementation(async (_m: string, taskId: string) => sdf(taskId));
  api.protein.mockReset().mockImplementation(async (_m: string, taskId: string) => `PROTEIN ${taskId}\nEND\n`);
  api.resultado.mockReset().mockResolvedValue({ docking_poses: Array.from({ length: 9 }, (_, i) => ({ rank: i + 1, affinity: -7 + i * 0.1 })) });
  api.same.mockReset();
  api.run.mockReset().mockResolvedValue(medidaMisma());
  api.analog.mockReset().mockResolvedValue(medidaAnalogos());
  api.matches.mockReset().mockResolvedValue(coincidencias(4));
  api.interactions.mockReset();
});
afterEach(cleanup);

const abrir = (extra: Record<string, unknown> = {}) => render(
  <PoseComparisonDialog
    moleculeId="mol" taskId="run-A" leftRank={1} rightRank={1}
    rightSource={fuente("run-B")} runs={[fuente("run-B"), fuente("run-C")]} onClose={() => {}} {...extra}
  />,
);
const abrirAnalogos = (extra: Record<string, unknown> = {}) => abrir({ rightSource: fuente("run-X", "otra"), runs: [fuente("run-X", "otra")], ...extra });
const fichasDe = (lado: 0 | 1) => within(screen.getAllByRole("group", { name: "Poses de esta evaluación" })[lado]);

// ── 1. Núcleo común ─────────────────────────────────────────────────────────────────────────────────────────────

describe("núcleo común", () => {
  it("cada visor recibe los átomos de SU ligando", async () => {
    abrirAnalogos();
    await waitFor(() => expect(visores()[0]).toHaveAttribute("data-nucleo", "[0,1,2]"));
    expect(visores()[1]).toHaveAttribute("data-nucleo", "[0,1,7]");
    expect(screen.getByText(/Varillas finas y tenues: el núcleo común/)).toBeInTheDocument();
  });

  it("se puede apagar, y entonces los dos ligandos se dibujan como siempre", async () => {
    abrirAnalogos();
    const casilla = await screen.findByRole("checkbox", { name: "Resaltar el núcleo común" });
    expect(casilla).toBeChecked();
    fireEvent.click(casilla);
    expect(visores()[0]).toHaveAttribute("data-nucleo", "null");
    expect(visores()[1]).toHaveAttribute("data-nucleo", "null");
    expect(screen.queryByText(/Varillas finas y tenues/)).toBeNull();
  });

  it("en la vista superpuesta la izquierda es el primer ligando y la derecha el segundo", async () => {
    abrirAnalogos();
    const superponer = await screen.findByRole("button", { name: "Superpuestas" });
    await waitFor(() => expect(superponer).toBeEnabled());
    fireEvent.click(superponer);
    await waitFor(() => expect(visores()).toHaveLength(1));
    expect(visores()[0]).toHaveAttribute("data-nucleo", "[0,1,2]");
    expect(visores()[0]).toHaveAttribute("data-nucleo-superpuesto", "[0,1,7]");
  });

  it("con otro receptor no hay núcleo que resaltar ni casilla", async () => {
    api.analog.mockResolvedValue(medidaAnalogos("different"));
    abrirAnalogos();
    await screen.findByText(/receptores preparados distintos/);
    expect(screen.queryByRole("checkbox", { name: "Resaltar el núcleo común" })).toBeNull();
    expect(visores()[0]).toHaveAttribute("data-nucleo", "null");
  });

  it("la misma molécula en otra corrida no tiene núcleo distinto de sí misma: sin casilla", async () => {
    abrir();
    await screen.findByText("0.42 Å");
    expect(screen.queryByRole("checkbox", { name: "Resaltar el núcleo común" })).toBeNull();
  });
});

// ── 2. Qué pose de la otra evaluación se parece más ─────────────────────────────────────────────────────────────

describe("poses cercanas", () => {
  it("cada ficha dice su distancia a la pose elegida del otro lado y la más cercana se marca", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    const cercana = await fichasDe(1).findByRole("button", { name: /Pose n\.º 4.*0\.31 Å de la pose elegida del otro lado, la más cercana/ });
    expect(cercana).toHaveTextContent("0.31 Å");
    expect(fichasDe(1).getByRole("button", { name: /Pose n\.º 1: .*2\.10 Å de la pose elegida del otro lado$/ })).toBeInTheDocument();
    expect(api.matches).toHaveBeenCalledWith("run-A", "run-B", 1);
    // Y al revés: las poses de la izquierda frente a la elegida de la derecha.
    expect(api.matches).toHaveBeenCalledWith("run-B", "run-A", 1);
    expect(screen.getByText(/no es una pose más válida/)).toBeInTheDocument();
  });

  it("cambiar la pose elegida borra las distancias que eran de la anterior y pide las nuevas", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    await fichasDe(1).findByRole("button", { name: /Pose n\.º 4.*la más cercana/ });

    let resolver: (valor: unknown) => void = () => {};
    api.matches.mockImplementationOnce(() => new Promise((resolve) => { resolver = resolve; }));
    fireEvent.click(fichasDe(0).getByRole("button", { name: /Pose n\.º 6/ }));

    await waitFor(() => expect(api.matches).toHaveBeenCalledWith("run-A", "run-B", 6));
    // Mientras llega la respuesta, ninguna ficha de la derecha enseña una distancia (serían de la pose 1).
    expect(fichasDe(1).queryByRole("button", { name: /la más cercana/ })).toBeNull();
    expect(fichasDe(1).queryAllByText(/Å$/)).toHaveLength(0);

    await act(async () => { resolver(coincidencias(2)); });
    expect(await fichasDe(1).findByRole("button", { name: /Pose n\.º 2.*la más cercana/ })).toBeInTheDocument();
  });

  it("con otro receptor no se pregunta nada y las fichas quedan como antes", async () => {
    api.run.mockResolvedValue(medidaMisma("different"));
    abrir();
    await screen.findByText(/receptores preparados distintos/);
    expect(api.matches).not.toHaveBeenCalled();
    expect(fichasDe(1).getByRole("button", { name: "Pose n.º 4: -6.70 kcal/mol" })).toBeInTheDocument();
  });

  it("si el backend se abstiene o falla, las fichas siguen sin distancia y no hay aviso de error", async () => {
    api.matches.mockRejectedValue(new Error("boom"));
    abrir();
    await waitFor(() => expect(api.matches).toHaveBeenCalled());
    expect(fichasDe(1).getByRole("button", { name: "Pose n.º 4: -6.70 kcal/mol" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("dos poses de una misma corrida no tienen «otra evaluación» con la que comparar", async () => {
    api.same.mockResolvedValue({
      task_id: "run-A", left: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, right: { rank: 2, found: true, vina_affinity_kcal_mol: -6.9 },
      difference: { right_minus_left_vina_kcal_mol: 0.1, pose_rmsd_between_poses: { available: true, reason_code: null, rmsd_angstrom: 1.5 } },
    });
    render(<PoseComparisonDialog moleculeId="mol" taskId="run-A" leftRank={1} rightRank={2} onClose={() => {}} />);
    await screen.findByText("1.50 Å");
    expect(api.matches).not.toHaveBeenCalled();
  });
});

// ── 3. Contactos ────────────────────────────────────────────────────────────────────────────────────────────────

describe("contactos que una pose gana o pierde", () => {
  const botonContactos = () => screen.getByRole("button", { name: "Comparar contactos" });
  const prepararContactos = () => api.interactions
    .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9), dato("hydrophobic", "LEU", 20, 3.8)]))
    .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 3.1), dato("salt_bridge", "ASP", 30, 3.4)]));

  it("se piden al pulsar, con la pose y la corrida de cada lado, y se agrupan", async () => {
    prepararContactos();
    abrir();
    await waitFor(() => expect(botonContactos()).toBeEnabled());
    expect(api.interactions).not.toHaveBeenCalled();
    fireEvent.click(botonContactos());

    expect(await screen.findByText("Sólo en la pose de la izquierda (1)")).toBeInTheDocument();
    expect(api.interactions).toHaveBeenCalledWith("mol", 1, "run-A");
    expect(api.interactions).toHaveBeenCalledWith("mol", 1, "run-B");
    expect(screen.getByText("En las dos poses (1)")).toBeInTheDocument();
    expect(screen.getByText("Sólo en la pose de la derecha (1)")).toBeInTheDocument();
    expect(screen.getByText("LEU20A")).toBeInTheDocument();
    expect(screen.getByText("ASP30A")).toBeInTheDocument();
    expect(screen.getByText("2.9 → 3.1 Å")).toBeInTheDocument();
    expect(screen.getByText(/criterios geométricos \(prolif:2\.0\.3\), no energías/)).toBeInTheDocument();
  });

  it("cada visor dibuja los contactos de su pose, y se pueden apagar", async () => {
    prepararContactos();
    abrir();
    await waitFor(() => expect(botonContactos()).toBeEnabled());
    fireEvent.click(botonContactos());
    await screen.findByText("En las dos poses (1)");
    // Izquierda: el suyo y el compartido. Derecha: el compartido y el suyo.
    expect(visores()[0]).toHaveAttribute("data-lineas", "2");
    expect(visores()[1]).toHaveAttribute("data-lineas", "2");

    fireEvent.click(screen.getByRole("checkbox", { name: "Dibujar los contactos en el visor" }));
    expect(visores()[0]).toHaveAttribute("data-lineas", "0");
    expect(visores()[1]).toHaveAttribute("data-lineas", "0");
  });

  it("en la vista superpuesta se dibujan los tres en una sola escena", async () => {
    prepararContactos();
    abrir();
    const superponer = await screen.findByRole("button", { name: "Superpuestas" });
    await waitFor(() => expect(superponer).toBeEnabled());
    fireEvent.click(superponer);
    await waitFor(() => expect(botonContactos()).toBeEnabled());
    fireEvent.click(botonContactos());
    await screen.findByText("En las dos poses (1)");
    expect(visores()[0]).toHaveAttribute("data-lineas", "3");
  });

  it("valen para esas dos poses: al cambiar una, hay que volver a pedirlos", async () => {
    prepararContactos();
    abrir();
    await waitFor(() => expect(botonContactos()).toBeEnabled());
    fireEvent.click(botonContactos());
    await screen.findByText("En las dos poses (1)");

    fireEvent.click(fichasDe(1).getByRole("button", { name: /Pose n\.º 5/ }));
    await waitFor(() => expect(screen.queryByText("En las dos poses (1)")).toBeNull());
    expect(botonContactos()).toBeEnabled();
  });

  it("con otro receptor no se ofrece y se dice la condición", async () => {
    api.run.mockResolvedValue(medidaMisma("different"));
    abrir();
    await screen.findByText(/receptores preparados distintos/);
    expect(botonContactos()).toBeDisabled();
    expect(screen.getByText("Los contactos sólo se comparan entre poses calculadas contra el mismo receptor preparado.")).toBeInTheDocument();
    expect(api.interactions).not.toHaveBeenCalled();
  });

  it("si los dos análisis usaron receptores distintos, no se compara aunque hayan salido", async () => {
    api.interactions
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9)]))
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 3.1)], { protein_source_sha256: "otro" }));
    abrir();
    await waitFor(() => expect(botonContactos()).toBeEnabled());
    fireEvent.click(botonContactos());
    expect(await screen.findByText("No se comparan los contactos: cada análisis usó un receptor preparado distinto.")).toBeInTheDocument();
    expect(screen.queryByText(/Sólo en la pose de la izquierda/)).toBeNull();
  });

  it("si un análisis no se puede leer, se dice y se puede reintentar", async () => {
    api.interactions.mockResolvedValue(null);
    abrir();
    await waitFor(() => expect(botonContactos()).toBeEnabled());
    fireEvent.click(botonContactos());
    expect(await screen.findByText("No se pudieron leer los contactos de una de las dos poses.")).toBeInTheDocument();
    expect(botonContactos()).toBeEnabled();
  });
});

// ── 4. Copiar el resumen ────────────────────────────────────────────────────────────────────────────────────────

describe("copiar el resumen", () => {
  const conPortapapeles = (writeText: (texto: string) => Promise<void>) =>
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

  it("deja en el portapapeles lo que se ve, con sus límites, y lo confirma", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    conPortapapeles(writeText);
    abrir();
    await screen.findByText("0.42 Å");
    fireEvent.click(screen.getByRole("button", { name: "Copiar resumen" }));

    expect(await screen.findByText("Resumen copiado")).toBeInTheDocument();
    const texto = writeText.mock.calls[0][0] as string;
    expect(texto).toContain("MolDesign · Comparación de poses");
    expect(texto).toContain("Izquierda: Evaluación actual");
    expect(texto).toContain("Derecha: Corrida run-B");
    expect(texto).toContain("(run-B)");
    expect(texto).toContain("RMSD entre las dos poses: 0.42 Å");
    expect(texto).toContain("Semilla: 42 → 7");
    expect(texto).toContain("no valida una pose");
  });

  it("incluye los contactos cuando ya se calcularon", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    conPortapapeles(writeText);
    api.interactions
      .mockResolvedValueOnce(informe([dato("hbond", "SER", 10, 2.9)]))
      .mockResolvedValueOnce(informe([dato("salt_bridge", "ASP", 30, 3.4)]));
    abrir();
    await waitFor(() => expect(screen.getByRole("button", { name: "Comparar contactos" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Comparar contactos" }));
    await screen.findByText("Sólo en la pose de la derecha (1)");
    fireEvent.click(screen.getByRole("button", { name: "Copiar resumen" }));
    await screen.findByText("Resumen copiado");
    const texto = writeText.mock.calls[0][0] as string;
    expect(texto).toContain("SER10A (Puente de hidrógeno según ProLIF)");
    expect(texto).toContain("ASP30A (Contacto iónico)");
  });

  it("si el portapapeles falla, lo dice", async () => {
    conPortapapeles(vi.fn().mockRejectedValue(new Error("denegado")));
    abrir();
    await screen.findByText("0.42 Å");
    fireEvent.click(screen.getByRole("button", { name: "Copiar resumen" }));
    expect(await screen.findByText("No se pudo copiar el resumen.")).toBeInTheDocument();
  });
});
