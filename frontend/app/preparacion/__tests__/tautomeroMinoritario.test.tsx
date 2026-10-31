import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import type { CaseRecord } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en", read: vi.fn(), request: vi.fn(), list: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "owner" }, isLoading: false }) }));
const repository = { listCases: mocks.list, readCase: mocks.read };
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => repository }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  const t = (key: string) => real.TRANSLATIONS[mocks.locale][key] ?? key;
  return { ...real, useLanguage: () => ({ locale: mocks.locale, t }) };
});
import PreparacionPage from "../page";
import {
  escucharPeticionesDeEvaluacion,
  olvidarPeticionesDeEvaluacion,
  type PeticionRecibida,
} from "@/lib/peticionDeEvaluacion";

type Opcion = { tautomero: "entrada"; smiles: string };

function auditoria(clave: string, reevaluar?: Opcion[]): AuditoriaPreparacion {
  return {
    schema: "preparacion/v1", estado: "BLOQUEADO", razon: "cause", alcance: "scope", transferencia_fep_demostrada: false,
    bloqueantes: [clave], en_revision: [], corrida: { task_id: "exact" },
    bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({
      id, estado: id === clave.split(".")[0] ? "BLOQUEADO" : "REVISION",
      requisitos: id === clave.split(".")[0] ? [{
        clave, estado: "ABSTENCION", imprescindible: true, etiqueta: "x",
        valor: "Forma minoritaria acoplada: Oc1ccccn1 (hidroxiazina en vez de su forma oxo)", valor_es_clasificacion: true,
        razon: "minor", accion_recomendada: "Vuelve a evaluar con la forma mayoritaria: O=c1cccc[nH]1", fuente: "f",
        ...(reevaluar ? { reevaluar } : {}),
      }] : [],
    })),
    paquete: { rotulo: "package", aviso: "limit" },
  } as unknown as AuditoriaPreparacion;
}

async function abrir(clave: string, reevaluar?: Opcion[]) {
  mocks.locale = "es";
  mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }]);
  mocks.read.mockResolvedValue({ id: "case", name: "Caso", context: {}, runs: [], activeRun: { taskId: "exact", moleculeId: "molecule", executionState: "completed" } } as unknown as CaseRecord);
  mocks.request.mockResolvedValue(auditoria(clave, reevaluar));
  render(<PreparacionPage />);
  fireEvent.change(await screen.findByRole("combobox"), { target: { value: "case" } });
  if (clave.startsWith("ligando")) fireEvent.click(screen.getByRole("button", { name: /Estado químico/ }));
  await screen.findByText("Vuelve a evaluar con la forma mayoritaria: O=c1cccc[nH]1");
}

describe("Preparación: tautómero sin población", () => {
  it("la acción del tautómero lleva a Evaluación, donde se vuelve a evaluar", async () => {
    await abrir("ligando.tautomero");
    expect(screen.getByRole("link", { name: "Ir a Evaluación" })).toHaveAttribute("href", "/evaluation");
  });

  it("con la acción en datos, el enlace abre el caso en Evaluación con la forma mayoritaria puesta", async () => {
    olvidarPeticionesDeEvaluacion();
    await abrir("ligando.tautomero", [{ tautomero: "entrada", smiles: "O=c1cccc[nH]1" }]);
    const enlace = screen.getByRole("link", { name: /Volver a evaluar en este caso con O=c1cccc\[nH\]1/ });
    expect(enlace).toHaveAttribute("href", "/evaluation");
    expect(screen.queryByRole("link", { name: "Ir a Evaluación" })).toBeNull();

    fireEvent.click(enlace);
    const recibidas: PeticionRecibida[] = [];
    const dejar = escucharPeticionesDeEvaluacion((p) => recibidas.push(p));
    expect(recibidas).toEqual([{ casoId: "case", tautomero: "entrada", smiles: "O=c1cccc[nH]1", nonce: expect.any(Number) }]);
    dejar();
  });

  it("varias formas plausibles: un enlace por forma", async () => {
    await abrir("ligando.tautomero", [
      { tautomero: "entrada", smiles: "Nc1nc2n(COCCO)cnc2c(=O)[nH]1" },
      { tautomero: "entrada", smiles: "Nc1nc(=O)c2ncn(COCCO)c2[nH]1" },
    ]);
    expect(screen.getAllByRole("link", { name: /Volver a evaluar en este caso con/ })).toHaveLength(2);
  });

  it("otras acciones no llevan ese acceso", async () => {
    await abrir("receptor.huecos");
    expect(screen.queryByRole("link", { name: "Ir a Evaluación" })).toBeNull();
  });
});
