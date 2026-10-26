// =====================================================================
// Preparación → Evaluación: «vuelve a evaluar este caso con este tautómero»
// =====================================================================
//
// Preparación bloquea un tautómero sin población y propone la forma
// mayoritaria. El enlace abre el caso en Evaluación con el ligando y el modo
// puestos; la persona revisa y ejecuta. Aquí se fija la mitad del runner:
//
//   1. el ligando entra como si se escribiera (se persiste en los inputs);
//   2. el modo llega a ProEvaluation, que lo aplica como desde Opciones;
//   3. cada petición se aplica una vez: cerrar el aviso no la repite.
//
// `ProEvaluation` se mockea como en `configuracionEfectivaPipeline.test.tsx`;
// su mitad (aplicar el modo por el camino de Opciones) se lee del fuente.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { CaseInputs } from "../../../lib/cases/types";
import {
  escucharPeticionesDeEvaluacion,
  olvidarPeticionesDeEvaluacion,
  pedirEvaluacion,
  type PeticionRecibida,
} from "../../../lib/peticionDeEvaluacion";

const authState = vi.hoisted(() => ({
  isLoading: false,
  token: "token-prueba",
  user: { user_id: "usuario-prueba" },
  logout: vi.fn(),
}));

vi.mock("../../../lib/auth", () => ({
  useAuth: () => authState,
}));

vi.mock("../../../lib/api", () => ({
  ApiError: class extends Error {
    readonly status: number;
    constructor(status: number, message = `HTTP ${status}`) {
      super(message);
      this.status = status;
    }
  },
  getJobStatus: vi.fn(),
  getEvaluationResult: vi.fn(),
  getTargets: vi.fn(async () => []),
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
  default: ({
    smiles,
    tautomeroPedido,
  }: {
    smiles: string;
    tautomeroPedido?: { modo: string; nonce: number };
  }) => (
    <div>
      <span data-testid="smiles">{smiles}</span>
      <span data-testid="modo-pedido">{tautomeroPedido ? `${tautomeroPedido.modo}#${tautomeroPedido.nonce}` : ""}</span>
    </div>
  ),
}));

import CaseEvaluationRunner from "../CaseEvaluationRunner";
import { invalidarCatalogo } from "../../../lib/catalogoDeReceptores";

const INPUTS: CaseInputs = {
  receptor: { pdbId: "3F75", origin: "curado", chain: "A" },
  ligand: { inputSmiles: "Oc1ccccn1" },
};

function peticion(nonce: number, smiles = "O=c1cccc[nH]1"): PeticionRecibida {
  return { casoId: "caso", tautomero: "entrada", smiles, nonce };
}

beforeEach(() => {
  invalidarCatalogo();
  olvidarPeticionesDeEvaluacion();
});

describe("el runner aplica la petición de Preparación", () => {
  it("pone el ligando como si se escribiera y pasa el modo a Evaluación", async () => {
    const onInputsChange = vi.fn();
    render(<CaseEvaluationRunner caseId="caso" inputs={INPUTS} onInputsChange={onInputsChange} peticion={peticion(1)} />);

    await waitFor(() => expect(screen.getByTestId("smiles")).toHaveTextContent("O=c1cccc[nH]1"));
    expect(onInputsChange).toHaveBeenCalledWith({ ligand: { inputSmiles: "O=c1cccc[nH]1" } });
    expect(screen.getByTestId("modo-pedido")).toHaveTextContent("entrada#1");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Desde Preparación: se cargó el ligando O=c1cccc[nH]1 con «Tautómero del ligando: Por defecto (conservar el tautómero que escribí)».",
    );
  });

  it("cerrar el aviso no vuelve a aplicar la petición; una nueva sí se aplica", async () => {
    const onInputsChange = vi.fn();
    const { rerender } = render(
      <CaseEvaluationRunner caseId="caso" inputs={INPUTS} onInputsChange={onInputsChange} peticion={peticion(1)} />,
    );
    await waitFor(() => expect(onInputsChange).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByText(/Desde Preparación/)).toBeNull();
    rerender(<CaseEvaluationRunner caseId="caso" inputs={INPUTS} onInputsChange={onInputsChange} peticion={peticion(1)} />);
    expect(onInputsChange).toHaveBeenCalledTimes(1);

    rerender(
      <CaseEvaluationRunner caseId="caso" inputs={INPUTS} onInputsChange={onInputsChange}
        peticion={peticion(2, "Oc1ccccn1")} />,
    );
    await waitFor(() => expect(onInputsChange).toHaveBeenCalledTimes(2));
    expect(onInputsChange).toHaveBeenLastCalledWith({ ligand: { inputSmiles: "Oc1ccccn1" } });
  });
});

describe("Evaluación aplica el modo por el camino de Opciones", () => {
  const proSource = readFileSync(
    resolve(process.cwd(), "components/interfaces/pro/ProEvaluation.tsx"),
    "utf8",
  );

  it("el modal y la petición comparten la misma función, que persiste la configuración", () => {
    expect(proSource).toContain("onApply={aplicarOpciones}");
    expect(proSource).toContain(
      "aplicarOpciones(dockingEngine, gridBox, { ...advancedOpts, tautomerMode: tautomeroPedido.modo }, customHotspots);",
    );
  });

  it("espera a que las anti-dianas estén resueltas: aplicarlas pendientes guardaría «ninguna»", () => {
    expect(proSource).toContain("if (advancedOpts.antiTargetsPending) return;");
  });
});

describe("el canal entre pestañas", () => {
  it("una petición sin oyente espera y la toma el primero que escucha", () => {
    pedirEvaluacion({ casoId: "a", tautomero: "entrada", smiles: "C" });
    const recibidas: PeticionRecibida[] = [];
    const dejar = escucharPeticionesDeEvaluacion((p) => recibidas.push(p));
    expect(recibidas.map((p) => p.casoId)).toEqual(["a"]);

    // Ya consumida: un segundo oyente no la recibe otra vez.
    const otras: PeticionRecibida[] = [];
    escucharPeticionesDeEvaluacion((p) => otras.push(p));
    expect(otras).toEqual([]);
    dejar();
  });

  it("con oyente llega en el acto, y dos peticiones iguales son dos", () => {
    const recibidas: PeticionRecibida[] = [];
    const dejar = escucharPeticionesDeEvaluacion((p) => recibidas.push(p));
    pedirEvaluacion({ casoId: "a", tautomero: "entrada", smiles: "C" });
    pedirEvaluacion({ casoId: "a", tautomero: "entrada", smiles: "C" });
    expect(recibidas).toHaveLength(2);
    expect(recibidas[0].nonce).not.toBe(recibidas[1].nonce);
    dejar();

    pedirEvaluacion({ casoId: "b", tautomero: "entrada", smiles: "C" });
    expect(recibidas).toHaveLength(2);
  });
});
