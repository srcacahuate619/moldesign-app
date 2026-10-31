import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/auth", () => ({ useAuth: () => ({ isLoading: false, user: null }) }));
import { LanguageProvider, useLanguage } from "../../../context/LanguageContext";
import { frontendMessage } from "../../../lib/frontendError";
import { CaseError } from "../../../lib/cases/types";
import { CreateCaseDialog } from "../CreateCaseDialog";

function CambiarIdioma() {
  const { setLocale } = useLanguage();
  return <button onClick={() => setLocale("en")}>Switch language</button>;
}

function montar(onPickDirectory: () => Promise<never>, hijos?: ReactNode) {
  return render(<LanguageProvider><CambiarIdioma />
    <CreateCaseDialog open onClose={vi.fn()} onCreate={vi.fn().mockResolvedValue(true)} requiresDirectory
      storageLabel="Navegador" onPickDirectory={onPickDirectory} />{hijos}
  </LanguageProvider>);
}

function errorPropio() {
  return new CaseError("UNSAFE_NAME", frontendMessage("case_schema_11", { v0: "CON" }));
}

beforeEach(() => vi.spyOn(window.navigator, "language", "get").mockReturnValue("es-ES"));
afterEach(() => vi.restoreAllMocks());

describe("idioma de un error al crear un caso", () => {
  it("actualiza el diagnóstico propio ya visible al cambiar de idioma", async () => {
    montar(vi.fn().mockRejectedValue(errorPropio()));
    fireEvent.click(screen.getByRole("button", { name: /elegir carpeta/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent('"CON" es un nombre reservado');
    fireEvent.click(screen.getByRole("button", { name: "Switch language" }));
    expect(screen.getByRole("alert")).toHaveTextContent('"CON" is a name reserved');
  });

  it("presenta en el idioma actual un fallo que llega después de cambiarlo", async () => {
    let rechazar!: (error: unknown) => void;
    montar(() => new Promise<never>((_resolver, reject) => { rechazar = reject; }));
    fireEvent.click(screen.getByRole("button", { name: /elegir carpeta/i }));
    fireEvent.click(screen.getByRole("button", { name: "Switch language" }));
    await act(async () => { rechazar(errorPropio()); });
    expect(await screen.findByRole("alert")).toHaveTextContent('"CON" is a name reserved');
  });

  it("no traduce ni altera el texto de un error externo", async () => {
    montar(vi.fn().mockRejectedValue(new Error("Error externo: ruta C:\\destino")));
    fireEvent.click(screen.getByRole("button", { name: /elegir carpeta/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Error externo: ruta C:\\destino");
    fireEvent.click(screen.getByRole("button", { name: "Switch language" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Error externo: ruta C:\\destino");
  });

  it("no muestra una alerta vacía cuando un error externo carece de mensaje", async () => {
    const rechazar = vi.fn().mockRejectedValue(new Error(""));
    montar(rechazar);
    fireEvent.click(screen.getByRole("button", { name: /elegir carpeta/i }));
    await act(async () => { await Promise.resolve(); });
    expect(rechazar).toHaveBeenCalledOnce();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("actualiza también el aviso propio cuando la creación devuelve false", async () => {
    render(<LanguageProvider><CambiarIdioma />
      <CreateCaseDialog open onClose={vi.fn()} onCreate={vi.fn().mockResolvedValue(false)} requiresDirectory={false} storageLabel="Browser" />
    </LanguageProvider>);
    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Caso A" } });
    fireEvent.click(screen.getByRole("button", { name: /^crear/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo crear el caso.");
    fireEvent.click(screen.getByRole("button", { name: "Switch language" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Could not create case.");
  });
});
