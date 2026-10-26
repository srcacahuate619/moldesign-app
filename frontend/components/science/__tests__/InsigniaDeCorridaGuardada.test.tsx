import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import { verificacionDePrueba as sello } from "@/lib/__tests__/fixtures/verificacionReceptor";
import { InsigniaDeCorridaGuardada } from "../InsigniaDeCorridaGuardada";

const mocks = vi.hoisted(() => ({ getResult: vi.fn(), locale: "es" as "es" | "en", userId: "alice", verificado: true }));
vi.mock("@/lib/api", () => ({ getEvaluationResult: mocks.getResult }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: mocks.userId } }) }));
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => [{ pdb_id: "8HFI", seccion_catalogo: mocks.verificado ? "verificado" : "demostracion", verificacion: sello }] }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string, params: Record<string, string | number> = {}) => (catalogo[mocks.locale][key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`)) }) }));
const igual = { receptor_sha256: sello.receptor_sha256, docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 } };
beforeEach(() => { mocks.getResult.mockReset(); mocks.locale = "es"; mocks.userId = "alice"; mocks.verificado = true; });

describe("sello de una corrida guardada identificada", () => {
  it("consulta ambos IDs y sólo confirma después de recibir todos los campos iguales", async () => {
    mocks.getResult.mockResolvedValue(igual);
    render(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="run/old" />);
    expect(screen.getByText(catalogo.es.cat_receptor_sin_declarar)).toBeVisible();
    await waitFor(() => expect(screen.queryByText(catalogo.es.cat_receptor_sin_declarar)).toBeNull());
    expect(screen.queryByText(catalogo.es.cat_parametros_sin_declarar)).toBeNull();
    expect(mocks.getResult).toHaveBeenCalledExactlyOnceWith("mol", "run/old");
  });
  it.each(["es", "en"] as const)("conserva diferencias y campos ausentes del snapshot en %s", async locale => {
    mocks.locale = locale;
    mocks.getResult.mockResolvedValue({ receptor_sha256: "otro", docking_protocol: { exhaustiveness: 32, num_poses: 9 } });
    render(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="exact" />);
    expect(await screen.findByText(catalogo[locale].cat_receptor_distinto)).toBeVisible();
    expect(screen.getByText(catalogo[locale].cat_parametros_distintos)).toBeVisible();
    expect(screen.getByText(catalogo[locale].cat_parametros_sin_declarar)).toBeVisible();
    expect(screen.queryByText(catalogo[locale].cat_receptor_sin_declarar)).toBeNull();
  });
  it.each([undefined, null, ""])("sin task_id (%j) no consulta la proyección actual", taskId => {
    render(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId={taskId} />);
    expect(mocks.getResult).not.toHaveBeenCalled();
    expect(screen.getByText(catalogo.es.cat_receptor_sin_declarar)).toBeVisible();
  });
  it("sin molecule_id tampoco consulta", () => {
    render(<InsigniaDeCorridaGuardada pdbId="8HFI" taskId="exact" />);
    expect(mocks.getResult).not.toHaveBeenCalled();
  });
  it("sin receptor verificado no añade una consulta de resultado", () => {
    mocks.verificado = false;
    render(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="exact" />);
    expect(screen.getByText("Demostración")).toBeVisible();
    expect(mocks.getResult).not.toHaveBeenCalled();
  });
  it("si el snapshot falla conserva la incertidumbre y no hace otra consulta", async () => {
    mocks.getResult.mockRejectedValue(new Error("snapshot no disponible"));
    render(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="exact" />);
    await act(async () => {});
    expect(screen.getByText(catalogo.es.cat_receptor_sin_declarar)).toBeVisible();
    expect(screen.getByText(catalogo.es.cat_parametros_sin_declarar)).toBeVisible();
    expect(mocks.getResult).toHaveBeenCalledTimes(1);
  });
  it("una respuesta tardía de otra corrida no confirma el sello de la seleccionada", async () => {
    let anterior!: (value: object) => void;
    let actual!: (value: object) => void;
    mocks.getResult.mockImplementationOnce(() => new Promise(resolve => { anterior = resolve; })).mockImplementationOnce(() => new Promise(resolve => { actual = resolve; }));
    const view = render(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="old" />);
    view.rerender(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="new" />);
    await act(async () => { anterior(igual); });
    expect(screen.getByText(catalogo.es.cat_receptor_sin_declarar)).toBeVisible();
    await act(async () => { actual({}); });
    expect(screen.getByText(catalogo.es.cat_parametros_sin_declarar)).toBeVisible();
    expect(mocks.getResult.mock.calls).toEqual([["mol", "old"], ["mol", "new"]]);
  });
  it("al cambiar de cuenta no muestra el resultado confirmado de la anterior", async () => {
    mocks.getResult.mockResolvedValueOnce(igual).mockImplementationOnce(() => new Promise(() => {}));
    const view = render(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="exact" />);
    await waitFor(() => expect(screen.queryByText(catalogo.es.cat_receptor_sin_declarar)).toBeNull());
    mocks.userId = "bob";
    view.rerender(<InsigniaDeCorridaGuardada pdbId="8HFI" moleculeId="mol" taskId="exact" />);
    expect(screen.getByText(catalogo.es.cat_receptor_sin_declarar)).toBeVisible();
    expect(mocks.getResult).toHaveBeenCalledTimes(2);
  });
});
