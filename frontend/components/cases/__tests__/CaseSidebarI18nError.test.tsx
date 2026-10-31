import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { LanguageProvider } from "../../../context/LanguageContext";
import { AuthProvider } from "../../../lib/auth";
import { frontendMessage } from "../../../lib/frontendError";
import { CaseError, type CaseIndexEntry } from "../../../lib/cases/types";
import { CaseSidebar } from "../CaseSidebar";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.localStorage.clear(); });

it("muestra en inglés mensajes y detalles locales de un caso no disponible", async () => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue("en-US");
  const error = new CaseError("INVALID_MANIFEST", frontendMessage("ca_diag_no_storage"), frontendMessage("ca_diag_choose_folder"));
  const entry: CaseIndexEntry = {
    id: "case-1", name: "Case", status: "draft", archived: false, storageMode: "browser",
    createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z", lastOpenedAt: "1970-01-01T00:00:00Z",
    unavailable: { code: error.code, message: error.message, detail: error.detail, error, actions: [] },
  };
  render(<AuthProvider><LanguageProvider><CaseSidebar cases={[entry]} activeCaseId={null} loading={false}
    onSelect={vi.fn()} onCreate={vi.fn()} onArchive={vi.fn()} onRecover={vi.fn()} canReveal={false} workLocked={false} />
  </LanguageProvider></AuthProvider>);
  expect(await screen.findByText("Local storage is not available in this environment.")).toBeInTheDocument();
  expect(screen.getByText("Choose a folder where the case will be created.")).toBeInTheDocument();
});

it("traduce el nombre generado sin modificar un nombre real de usuario", async () => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue("en-US");
  const base = { status: "draft", archived: false, storageMode: "browser", createdAt: "1970-01-01T00:00:00Z",
    updatedAt: "1970-01-01T00:00:00Z", lastOpenedAt: "1970-01-01T00:00:00Z" } as const;
  const entries: CaseIndexEntry[] = [
    { ...base, id: "deadbeef-abcd", name: "Caso deadbeef", generatedName: true,
      unavailable: { code: "INVALID_MANIFEST", message: "external", actions: [] } },
    { ...base, id: "user", name: "Caso Real" },
  ];
  render(<AuthProvider><LanguageProvider><CaseSidebar cases={entries} activeCaseId={null} loading={false}
    onSelect={vi.fn()} onCreate={vi.fn()} onArchive={vi.fn()} onRecover={vi.fn()} canReveal={false} workLocked={false} />
  </LanguageProvider></AuthProvider>);
  expect(await screen.findByText("Case deadbeef")).toBeInTheDocument();
  expect(screen.getByText("Caso Real")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Case deadbeef" } });
  expect(screen.getByText("Case deadbeef")).toBeInTheDocument();
  expect(screen.queryByText("Caso Real")).not.toBeInTheDocument();
});
