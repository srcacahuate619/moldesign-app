import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { casos } from "@/context/traducciones/casos";
import { CreateCaseDialog } from "../CreateCaseDialog";
const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string) => casos[mocks.locale][key] ?? key }) }));
afterEach(cleanup);
describe("tipos de estudio visibles, identificadores persistidos", () => {
  it.each(["es", "en"] as const)("traduce cada opción y conserva el tipo seleccionado en %s", async locale => {
    mocks.locale = locale;
    const create = vi.fn().mockResolvedValue(true);
    render(<CreateCaseDialog open onClose={vi.fn()} onCreate={create} requiresDirectory={false} storageLabel="local" />);
    for (const key of ["ca_kind_explore", "ca_kind_compare", "ca_kind_review", "ca_kind_prepare"]) expect(screen.getByRole("radio", {name:casos[locale][key]})).toBeVisible();
    fireEvent.click(screen.getByRole("radio", {name:casos[locale].ca_kind_compare}));
    fireEvent.change(screen.getByRole("textbox"), {target:{value:"QA"}});
    fireEvent.click(screen.getByRole("button", {name:casos[locale].ca_crear_boton}));
    await waitFor(() => expect(create).toHaveBeenCalledWith("QA", "compare-series", undefined));
  });
  it.each(["es", "en"] as const)("el nombre de carpeta inválido avisa en %s", locale => {
    mocks.locale = locale;
    render(<CreateCaseDialog open onClose={vi.fn()} onCreate={vi.fn()} requiresDirectory storageLabel="local" />);
    fireEvent.change(screen.getByRole("textbox"), {target:{value:"CON"}});
    expect(screen.getByText(casos[locale].ca_nombre_carpeta_invalido)).toBeVisible();
  });
});
