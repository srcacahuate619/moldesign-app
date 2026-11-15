import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { getContactMap } from "@/lib/api";
import type { InteractionsReport } from "@/lib/types";
import { KeepAliveContext } from "@/context/KeepAliveContext";
import { ContactMapPanel } from "../ContactMapPanel";
import type { EvaluationResult } from "@/lib/types";
import { ProXaiTab } from "../ProXaiTab";
import { ProModelsTab } from "../ProModelsTab";
import { ShapContributionChart, notaDeSalidaShap } from "../ShapContributionChart";
import { ResultReadingPresentation } from "../ResultReadingPresentation";

vi.mock("@/lib/api", () => ({ getContactMap: vi.fn(), getGnnAttentionSvg: vi.fn() }));
const api = vi.mocked(getContactMap);
const hash = "a".repeat(64);

beforeAll(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); } });
});
beforeEach(() => api.mockReset());

function informe(task = "run-a", rank = 1): InteractionsReport {
  return {
    molecule_id: "mol-a", task_id: task, target_pdb_id: "TEST", pose_rank: rank,
    pose_source_path: "runs/poses.sdf", pose_source_sha256: hash, protein_source_path: "runs/receptor.pdbqt", protein_source_sha256: hash,
    protein_filter: "ATOM_only", engine: "distancias_sin_quimica", hydrogen_model: null,
    total_interactions: 1, summary: { polar_contact: 1 }, interactions_by_type: {}, pharmacophore_features: {}, analysis_ligand_sha256: hash,
    interactions: [{ type: "polar_contact", residue: "SER1A", residue_name: "SER", residue_number: 1, residue_chain: "A", distance: 2.9, angle: null, strength: null, ligand_atom_indices: [0], protein_atom: "OG", ligand_coords: { x: 0, y: 0, z: 0 }, protein_coords: { x: 2.9, y: 0, z: 0 }, geometry: { distance: 2.9 } }],
    contact_map: { status: "ready", analysis_ligand_sha256: hash, svg: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>', width: 100, height: 100, renderer: "rdkit:test", atoms: [{ index: 0, element: "O", x: 20, y: 20 }, { index: 1, element: "O", x: 80, y: 80 }], contacts: [{ contact_index: 0, atom_indices: [0], hidden_hydrogen_indices: [], reason: null }], highlighted_atom_indices: [0] },
  };
}

type Dominio = boolean | null | undefined;
// El SHAP se lee dentro de la ficha de la regresión en «Modelos» (ya no en «Explicabilidad»).
const pestaña = (opts: { shapOutput?: string | null; dominio?: Dominio; valores?: Record<string, number> | null } = {}) => (
  <ResultReadingPresentation>
    <ProModelsTab result={{
      ml_pki: 6.2,
      shap_values: opts.valores === undefined ? { ecif_N_don_C: 0.12, vina_best_score: -0.2 } : opts.valores,
      shap_output: opts.shapOutput,
      in_applicability_domain: opts.dominio,
    } as unknown as EvaluationResult} />
  </ResultReadingPresentation>
);

// El texto que explica cómo leer el SHAP vive en un «?»: hay que abrirlo para leerlo (se pinta en un portal).
const abrirAyudaShap = () => fireEvent.click(screen.getByRole("button", { name: "Cómo leer las contribuciones SHAP" }));
const enAyuda = (selector: string) => document.body.querySelector(selector);

describe("controles de explicabilidad · pestaña", () => {
  it("P01 la nota dice QUÉ explica el SHAP según shap_output y no inventa magnitud si falta", () => {
    expect(notaDeSalidaShap("delta_pKi")).toBe("xai_delta_note");
    expect(notaDeSalidaShap("pKi")).toBe("xai_pki_note");
    for (const raro of [null, undefined, "", "affinity", "DELTA_PKI"]) expect(notaDeSalidaShap(raro)).toBe("xai_unknown_output_note");
  });

  it("P02 delta_pKi: la nota habla de la corrección sobre Vina y del valor base", () => {
    render(pestaña({ shapOutput: "delta_pKi", dominio: true }));
    abrirAyudaShap();
    const nota = enAyuda('[data-shap-output="delta_pKi"]');
    expect(nota).not.toBeNull();
    expect(nota!.textContent).toMatch(/corrección/);
    expect(nota!.textContent).toMatch(/Vina/);
    expect(nota!.textContent).toMatch(/valor base/);
  });

  it("P03 pKi: la nota habla del pKi directo y no menciona la corrección sobre Vina", () => {
    render(pestaña({ shapOutput: "pKi", dominio: true }));
    abrirAyudaShap();
    const nota = enAyuda('[data-shap-output="pKi"]');
    expect(nota).not.toBeNull();
    expect(nota!.textContent).toMatch(/pKi directamente/);
    expect(nota!.textContent).not.toMatch(/corrección/);
  });

  it("P04 sin shap_output (resultado antiguo) se declara que no consta, sin suponer delta", () => {
    for (const salida of [undefined, null]) {
      const { unmount } = render(pestaña({ shapOutput: salida, dominio: true }));
      abrirAyudaShap();
      const nota = enAyuda('[data-shap-output="unknown"]');
      expect(nota).not.toBeNull();
      expect(nota!.textContent).toMatch(/No consta/);
      expect(nota!.textContent).not.toMatch(/corrección/);
      unmount();
    }
  });

  it("P05 el gráfico suelto advierte fuera del dominio o sin determinar; dentro del dominio no", () => {
    const grafica = (dominio: Dominio) => <ResultReadingPresentation><ShapContributionChart values={{ mw: 0.1 }} shapOutput="delta_pKi" inApplicabilityDomain={dominio} /></ResultReadingPresentation>;
    const fuera = render(grafica(false));
    expect(fuera.container.querySelector('[data-shap-domain="out"]')).not.toBeNull();
    fuera.unmount();
    for (const d of [null, undefined] as const) {
      const r = render(grafica(d));
      expect(r.container.querySelector('[data-shap-domain="unknown"]')).not.toBeNull();
      r.unmount();
    }
    const dentro = render(grafica(true));
    expect(dentro.container.querySelector("[data-shap-domain]")).toBeNull();
  });

  it("P05b en «Modelos» el dominio se advierte UNA vez, en la ficha, y no otra vez dentro del gráfico", () => {
    const { container } = render(pestaña({ shapOutput: "delta_pKi", dominio: false }));
    expect(container.querySelectorAll('[role="note"]')).toHaveLength(1);
    expect(container.querySelector('[data-model-domain="out"]')).not.toBeNull();
    expect(container.querySelector("[data-shap-domain]")).toBeNull();
  });

  it("P06 la nota de truncamiento cita cuántas barras hay y que su suma no reproduce la salida", () => {
    const claves = ["ecif_C_ali_C", "ecif_C_aro_C", "ecif_S_O", "ecif_other_N", "ecif_N_acc_F", "ecif_O_don_S", "ecif_O_acc_Hal"];
    const valores = Object.fromEntries(claves.map((clave, i) => [clave, 0.01 * (i + 1)]));
    render(pestaña({ shapOutput: "delta_pKi", dominio: true, valores }));
    abrirAyudaShap();
    const nota = enAyuda('[data-shap-truncation="true"]');
    expect(nota).not.toBeNull();
    expect(nota!.textContent).toContain("7");
    expect(nota!.textContent).toMatch(/no reproduce la salida del modelo/);
    expect(nota!.textContent).toMatch(/valor base/);
  });

  it("P07 la fila y el detalle salen de la misma explicación: proteína primero y sin afirmar lo no medido", async () => {
    render(pestaña({ shapOutput: "delta_pKi", dominio: true, valores: { ecif_N_don_C: 0.12 } }));
    const fila = screen.getByRole("button", { name: /Proteína: nitrógeno con hidrógeno/ });
    expect(fila.getAttribute("aria-label")).toContain("Ligando: carbono");
    fireEvent.click(fila);
    const dialogo = await screen.findByRole("dialog");
    expect(within(dialogo).getByRole("heading", { name: /Proteína: nitrógeno con hidrógeno \(potencial donador\) · Ligando: carbono/ })).toBeInTheDocument();
    expect(dialogo.textContent).toMatch(/empaquetamiento, no un puente/);
    expect(dialogo.textContent).not.toMatch(/donadores del ligando|interactuando fuertemente|borde del solvente/);
  });

  it("P08 una clave que el modelo todavía no describe se muestra tal cual, sin descripción inventada", async () => {
    render(pestaña({ shapOutput: "delta_pKi", dominio: true, valores: { nueva_caracteristica_x: 0.3 } }));
    fireEvent.click(screen.getByRole("button", { name: /nueva caracteristica x/ }));
    const dialogo = await screen.findByRole("dialog");
    expect(dialogo.textContent).toContain("Característica del modelo sin descripción registrada.");
    expect(dialogo.textContent).toContain("nueva_caracteristica_x");
  });

  it("P09 el mapa de contactos se muestra sin ningún modelo (la pestaña no depende de ellos)", async () => {
    api.mockResolvedValue(informe());
    render(
      <ResultReadingPresentation>
        <ProXaiTab moleculeId="mol-a" taskId="run-a" poses={[{ rank: 1 }]} />
      </ResultReadingPresentation>,
    );
    expect(await screen.findByRole("img")).toBeInTheDocument();
    expect(api).toHaveBeenCalledTimes(1);
  });
});

describe("controles de explicabilidad · mapa de contactos y KeepAlive", () => {
  const panel = (activo: boolean, task = "run-a") => (
    <KeepAliveContext.Provider value={activo}>
      <ResultReadingPresentation>
        <ContactMapPanel moleculeId="mol-a" taskId={task} poses={[{ rank: 1 }, { rank: 2 }]} />
      </ResultReadingPresentation>
    </KeepAliveContext.Provider>
  );

  it("C01 ocultar y volver a mostrar la pestaña NO repite la consulta de la misma pose", async () => {
    api.mockResolvedValue(informe());
    const { rerender } = render(panel(true));
    await screen.findByRole("img");
    expect(api).toHaveBeenCalledTimes(1);
    rerender(panel(false));
    rerender(panel(true));
    await screen.findByRole("img");
    expect(api).toHaveBeenCalledTimes(1);
  });

  it("C02 otra pose sí consulta, y volver a la primera ya está verificada y no consulta", async () => {
    api.mockResolvedValue(informe());
    render(panel(true));
    await screen.findByRole("img");
    api.mockResolvedValue(informe("run-a", 2));
    fireEvent.change(screen.getByLabelText("Pose del mapa"), { target: { value: "2" } });
    await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    await screen.findByRole("img");
    fireEvent.change(screen.getByLabelText("Pose del mapa"), { target: { value: "1" } });
    await screen.findByRole("img");
    expect(api).toHaveBeenCalledTimes(2);
  });

  it("C03 una respuesta que no coincide con la corrida no se guarda: reintentar vuelve a consultar", async () => {
    api.mockResolvedValue(informe("otra-corrida"));
    render(panel(true));
    expect(await screen.findByText(/La respuesta no coincide/)).toBeVisible();
    api.mockResolvedValue(informe());
    fireEvent.click(screen.getByRole("button", { name: "Reintentar lectura" }));
    await screen.findByRole("img");
    expect(api).toHaveBeenCalledTimes(2);
  });
});
