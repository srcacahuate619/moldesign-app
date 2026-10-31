import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { AuthProvider } from "../../lib/auth";
import { createBrowserCaseRepository } from "../../lib/cases/browserCaseRepository";
import { CaseError } from "../../lib/cases/types";
import { FrontendError, frontendMessage } from "../../lib/frontendError";
import { CaseProvider, useCases } from "../CaseContext";
import { LanguageProvider, useLanguage } from "../LanguageContext";

function Controles() {
  const { error, repairCase, selectCase, createCase, updateContext, retrySave, activeCase } = useCases();
  const { setLocale } = useLanguage();
  return <>
    <button onClick={() => void repairCase("x")}>repair</button>
    <button onClick={() => void selectCase("case-123")}>open</button>
    <button onClick={() => setLocale("en")}>english</button>
    <button onClick={() => void createCase("Test", "explore-hypothesis")}>create</button>
    <button onClick={() => updateContext({ question: "Una pregunta" })}>edit</button>
    <button onClick={() => void retrySave()}>retry</button>
    <p data-testid="active-case">{activeCase?.name}</p>
    <p role="status">{error}</p>
  </>;
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.localStorage.clear(); });

it("actualiza el aviso de funcionalidad no disponible al cambiar el idioma", async () => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue("es-MX");
  const repo = createBrowserCaseRepository("idioma-contexto");
  render(<AuthProvider><LanguageProvider><CaseProvider repository={repo}><Controles /></CaseProvider></LanguageProvider></AuthProvider>);
  fireEvent.click(screen.getByText("repair"));
  expect(await screen.findByRole("status")).toHaveTextContent("Este almacenamiento no guarda copias de seguridad");
  fireEvent.click(screen.getByText("english"));
  expect(screen.getByRole("status")).toHaveTextContent("This storage does not keep backups");
});

it("mantiene el cambio pendiente y traduce el aviso de guardado al cambiar de idioma", async () => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue("es-MX");
  const repo = createBrowserCaseRepository("idioma-guardado");
  repo.updateCase = vi.fn().mockRejectedValue(new FrontendError(frontendMessage("ca_diag_save_unstable")));
  render(<AuthProvider><LanguageProvider><CaseProvider repository={repo} autosaveDelayMs={0}><Controles /></CaseProvider></LanguageProvider></AuthProvider>);
  fireEvent.click(screen.getByText("create"));
  expect(await screen.findByTestId("active-case")).toHaveTextContent("Test");
  fireEvent.click(screen.getByText("edit"));
  expect(await screen.findByText(/El caso no dejó de cambiar mientras se guardaba/)).toHaveTextContent("El cambio no se ha perdido");
  fireEvent.click(screen.getByText("english"));
  expect(screen.getByRole("status")).toHaveTextContent("The case kept changing while it was being saved.");
  expect(screen.getByRole("status")).toHaveTextContent("The change has not been lost: you can retry.");
  fireEvent.click(screen.getByText("retry"));
  expect(await screen.findByText(/The retry failed again; the change is still pending/)).toBeInTheDocument();
  expect(repo.updateCase).toHaveBeenCalledTimes(2);
});

it("traduce mensaje y detalle locales al cambiar de idioma sin perder los valores", async () => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue("es-MX");
  const repo = createBrowserCaseRepository("idioma-detalle");
  repo.openCase = vi.fn().mockRejectedValue(new CaseError("INVALID_MANIFEST",
    frontendMessage("ca_diag_case_not_found", { id: "case-123" }), frontendMessage("ca_diag_choose_folder")));
  render(<AuthProvider><LanguageProvider><CaseProvider repository={repo}><Controles /></CaseProvider></LanguageProvider></AuthProvider>);
  fireEvent.click(screen.getByText("open"));
  expect(await screen.findByText(/No existe un caso con id case-123/)).toHaveTextContent("Elige una carpeta");
  fireEvent.click(screen.getByText("english"));
  expect(screen.getByRole("status")).toHaveTextContent("There is no case with id case-123 in this browser.");
  expect(screen.getByRole("status")).toHaveTextContent("Choose a folder where the case will be created.");
});

it("conserva literalmente el mensaje externo al cambiar de idioma", async () => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue("es-MX");
  const repo = createBrowserCaseRepository("idioma-externo");
  repo.openCase = vi.fn().mockRejectedValue(new CaseError("IO_ERROR", "Fallo externo de Rust", "detalle ajeno"));
  render(<AuthProvider><LanguageProvider><CaseProvider repository={repo}><Controles /></CaseProvider></LanguageProvider></AuthProvider>);
  fireEvent.click(screen.getByText("open"));
  expect(await screen.findByText("Fallo externo de Rust (detalle ajeno)")).toBeInTheDocument();
  fireEvent.click(screen.getByText("english"));
  expect(screen.getByRole("status")).toHaveTextContent("Fallo externo de Rust (detalle ajeno)");
});
