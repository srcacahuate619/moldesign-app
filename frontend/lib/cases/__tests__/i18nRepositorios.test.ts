import { describe, expect, it } from "vitest";

import { interpolar, TRANSLATIONS } from "../../../context/LanguageContext";
import { presentError } from "../../frontendError";
import { createBrowserCaseRepository } from "../browserCaseRepository";
import { createTauriCaseRepository } from "../tauriCaseRepository";
import { mockTauriInvoke, setTauriEnv } from "../../../vitest.setup";

const en = (key: string, values?: Readonly<Record<string, string | number>>) =>
  interpolar(TRANSLATIONS.en[key] ?? key, values);

describe("errores locales de los repositorios de casos", () => {
  it("presenta en inglés un caso ausente conservando su id", async () => {
    const repository = createBrowserCaseRepository("owner-diagnostics-test");
    await expect(repository.readCase("case-123")).rejects.toSatisfy((error: unknown) =>
      presentError(error, en) === "There is no case with id case-123 in this browser.");
  });

  it("presenta en inglés la carpeta necesaria al crear un caso de escritorio", async () => {
    const repository = createTauriCaseRepository({ ownerUserId: "owner-diagnostics-test" });
    await expect(repository.createCase({ name: "Case", studyKind: "explore-hypothesis" })).rejects.toSatisfy((error: unknown) =>
      presentError(error, en) === "Choose a folder where the case will be created.");
  });

  it("mantiene el mensaje localizado del puente al envolverlo en CaseError", async () => {
    setTauriEnv(false);
    const repository = createTauriCaseRepository({ ownerUserId: "owner-diagnostics-test" });
    const error = await repository.pickParentDirectory!().catch((e: unknown) => e);
    expect(presentError(error, en)).toBe("The desktop bridge is not available (command `case_pick_parent_directory`). This feature requires the desktop application.");
  });

  it("preserva literalmente los errores externos de Rust", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockRejectedValueOnce("IO_ERROR: Mensaje externo / path");
    const repository = createTauriCaseRepository({ ownerUserId: "owner-diagnostics-test" });
    const error = await repository.pickParentDirectory!().catch((e: unknown) => e);
    expect(presentError(error, en)).toBe("Mensaje externo / path");
  });
});
