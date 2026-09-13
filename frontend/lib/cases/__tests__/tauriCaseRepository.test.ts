// =====================================================================
// Tests del repositorio de casos en ESCRITORIO
// =====================================================================
//
// LO QUE ESTOS TESTS DEFIENDEN es que el webview YA NO ENVÍA RUTAS. La versión
// anterior pasaba `casePath` a los comandos: cualquiera con acceso al webview
// —un XSS, o la consola del devtools— podía leer o escribir cualquier archivo
// del disco. Ahora todo viaja por `caseId` o por un `token` que sólo el diálogo
// nativo puede emitir.
//
// Cubre también que un caso movido o corrupto NO desaparece del listado.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTauriCaseRepository } from "../tauriCaseRepository";
import { createCaseRecord, serializeCaseManifest } from "../schema";
import { mockTauriInvoke, setTauriEnv } from "../../../vitest.setup";

const PATH = "/casos/serie-a";

function manifestFor(id: string, name = "Serie A"): string {
  const record = createCaseRecord({
    ownerUserId: "test-owner",
    name,
    studyKind: "compare-series",
    storage: { mode: "folder", path: PATH },
    id,
    now: "2026-08-23T12:00:00.000Z",
  });
  return serializeCaseManifest(record);
}

function legacyManifestFor(id: string, { withRun = true }: { withRun?: boolean } = {}): string {
  const value = JSON.parse(manifestFor(id, "Caso legacy"));
  value.schemaVersion = 5;
  delete value.ownerUserId;
  if (withRun) {
    value.activeRun = {
      taskId: `task-${id}`,
      moleculeId: `molecule-${id}`,
      executionState: "completed",
      startedAt: "2026-08-23T12:00:00.000Z",
    };
  }
  return JSON.stringify(value);
}

function repo() {
  return createTauriCaseRepository({ ownerUserId: "test-owner" });
}

describe("la frontera: nada de rutas desde el webview", () => {
  beforeEach(() => setTauriEnv(true));

  it("`readCase` manda `caseId`, nunca una ruta", async () => {
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      expect(cmd).toBe("case_read");
      // Lo que viaja es el identificador. Ninguna clave con forma de ruta.
      expect(args).toEqual({ caseId: "abc", ownerUserId: "test-owner" });
      expect(JSON.stringify(args)).not.toMatch(/casePath|path/);
      return { case_id: "abc", path: PATH, manifest: manifestFor("abc"), recovered_from_backup: false, conflicting_path: null };
    });
    const record = await repo().readCase("abc");
    expect(record.id).toBe("abc");
    expect(record.storage).toEqual({ mode: "folder", path: PATH });
  });

  it("`updateCase` manda `caseId` y contenido, no la carpeta", async () => {
    const calls: Array<{ cmd: string; args?: Record<string, unknown> }> = [];
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      calls.push({ cmd, args });
      return null;
    });
    const record = JSON.parse(manifestFor("abc"));
    await repo().updateCase({ ...record, storage: { mode: "folder", path: PATH } });
    expect(calls[0].cmd).toBe("case_write");
    expect(Object.keys(calls[0].args ?? {}).sort()).toEqual(["caseId", "contents", "ownerUserId"]);
  });

  it("`createCase` manda el TOKEN del diálogo, no la carpeta padre", async () => {
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      expect(cmd).toBe("case_create");
      expect(args?.token).toBe("token-de-sesion");
      // El nombre de carpeta va saneado; la ruta padre no aparece.
      expect(args?.folderName).toBe("Serie A");
      expect(JSON.stringify(args)).not.toContain("/casos");
      return { case_id: "nuevo", path: PATH, manifest: manifestFor("nuevo"), recovered_from_backup: false, conflicting_path: null };
    });
    const created = await repo().createCase({
      name: "Serie A",
      studyKind: "compare-series",
      parentDirectory: "token-de-sesion",
    });
    expect(created.id).toBe("nuevo");
  });

  it("`revealInFileManager` manda `caseId`", async () => {
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      expect(cmd).toBe("case_reveal");
      expect(args).toEqual({ caseId: "abc", ownerUserId: "test-owner" });
      return null;
    });
    await repo().revealInFileManager?.("abc");
  });
});

describe("errores de Rust traducidos", () => {
  beforeEach(() => setTauriEnv(true));

  it("un caso no autorizado llega como UNAUTHORIZED, no como error genérico", async () => {
    mockTauriInvoke.mockImplementation(async () => {
      throw new Error("UNAUTHORIZED: el caso abc no está autorizado en este equipo.");
    });
    await expect(repo().readCase("abc")).rejects.toMatchObject({ code: "UNAUTHORIZED" });
  });

  it("un manifiesto inválido llega como INVALID_MANIFEST", async () => {
    mockTauriInvoke.mockImplementation(async () => {
      throw new Error("INVALID_MANIFEST: falta `status`.");
    });
    await expect(repo().readCase("abc")).rejects.toMatchObject({ code: "INVALID_MANIFEST" });
  });

  it("sin puente de escritorio, el error lo dice en vez de degradar en silencio", async () => {
    setTauriEnv(false);
    await expect(repo().readCase("abc")).rejects.toMatchObject({
      code: "UNSUPPORTED_OPERATION",
    });
  });
});

describe("listado: un caso roto no desaparece", () => {
  beforeEach(() => setTauriEnv(true));

  it("marca como NO DISPONIBLE el caso cuya carpeta ya no está", async () => {
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      if (cmd === "case_list_authorized") {
        return [
          { case_id: "bueno", path: "/casos/bueno", available: true, can_repair: false },
          { case_id: "movido", path: "/casos/movido", available: false, can_repair: false },
        ];
      }
      if (cmd === "case_read") {
        if (args?.caseId === "bueno") {
          return {
            case_id: "bueno", path: "/casos/bueno",
            manifest: manifestFor("bueno", "Bueno"), recovered_from_backup: false, conflicting_path: null,
          };
        }
        throw new Error("NOT_FOUND: no hay `case.json` en /casos/movido");
      }
      throw new Error(`comando inesperado: ${cmd}`);
    });

    const list = await repo().listCases();
    // LOS DOS están en la lista. Omitir el roto lo hacía desaparecer sin
    // explicación y sin forma de recuperarlo.
    expect(list).toHaveLength(2);
    const roto = list.find((entry) => entry.id === "movido");
    expect(roto?.unavailable?.code).toBe("NOT_FOUND");
    expect(roto?.unavailable?.actions).toContain("relocate");
    expect(roto?.unavailable?.actions).toContain("forget");
    expect(roto?.path).toBe("/casos/movido");
  });

  it("`forgetCase` retira del registro de Rust sin borrar la carpeta", async () => {
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      expect(cmd).toBe("case_forget");
      expect(args).toEqual({ caseId: "movido", ownerUserId: "test-owner" });
      return null;
    });
    await repo().forgetCase("movido");
  });

  it("`relocateCase` delega la identidad en Rust y NO abre antes de verificar", async () => {
    const invoked: string[] = [];
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      invoked.push(cmd);
      if (cmd === "case_pick_directory") {
        return { token: "tok", display_path: "/casos/otro", has_manifest: true };
      }
      if (cmd === "case_relocate") {
        // Rust recibe el id ESPERADO y es él quien rechaza.
        expect(args).toEqual({ token: "tok", expectedCaseId: "movido", ownerUserId: "test-owner" });
        throw new Error(
          "UNAUTHORIZED: esa carpeta contiene el caso otro-distinto, no movido. El registro no se ha modificado.",
        );
      }
      throw new Error(`comando inesperado: ${cmd}`);
    });

    await expect(repo().relocateCase?.("movido")).rejects.toMatchObject({
      code: "UNAUTHORIZED",
    });
    // NUNCA se llamó a `case_open_token`: abrir con `acceptRelocation` movía el
    // mapping ANTES de comprobar el id, así que la carpeta equivocada quedaba
    // registrada y el rechazo llegaba tarde.
    expect(invoked).not.toContain("case_open_token");
    expect(invoked).toEqual(["case_pick_directory", "case_relocate"]);
  });

  it("`relocateCase` mueve el registro cuando la carpeta sí es la del caso", async () => {
    mockTauriInvoke.mockImplementation(async (cmd) => {
      if (cmd === "case_pick_directory") {
        return { token: "tok", display_path: "/casos/nueva", has_manifest: true };
      }
      if (cmd === "case_relocate") {
        return {
          case_id: "movido", path: "/casos/nueva",
          manifest: manifestFor("movido"), recovered_from_backup: false, conflicting_path: null,
        };
      }
      throw new Error(`comando inesperado: ${cmd}`);
    });
    const outcome = await repo().relocateCase?.("movido");
    expect(outcome?.kind).toBe("opened");
  });
});

describe("abrir una carpeta", () => {
  beforeEach(() => setTauriEnv(true));

  it("una carpeta sin `case.json` NO se importa: devuelve `empty`", async () => {
    mockTauriInvoke.mockImplementation(async (cmd) => {
      if (cmd === "case_pick_directory") {
        return { token: "tok-vacia", display_path: "/casos/vacia", has_manifest: false };
      }
      throw new Error(`no debería invocarse ${cmd}`);
    });
    const outcome = await repo().openExistingFolder?.();
    expect(outcome?.kind).toBe("empty");
    // Token y ruta van SEPARADOS: el token autoriza, la ruta sólo se enseña.
    if (outcome?.kind !== "empty") throw new Error("esperaba `empty`");
    expect(outcome.token).toBe("tok-vacia");
    expect(outcome.displayPath).toBe("/casos/vacia");
    // Y el token NUNCA es la ruta: enseñarlo pondría un UUID donde va una
    // ubicación.
    expect(outcome.displayPath).not.toBe(outcome.token);
  });

  it("cancelar el diálogo no es un error", async () => {
    mockTauriInvoke.mockImplementation(async () => null);
    const outcome = await repo().openExistingFolder?.();
    expect(outcome?.kind).toBe("cancelled");
  });

  it("un caso recuperado del backup se abre igualmente", async () => {
    mockTauriInvoke.mockImplementation(async (cmd) => {
      if (cmd === "case_pick_directory") {
        return { token: "tok", display_path: PATH, has_manifest: true };
      }
      if (cmd === "case_open_token") {
        return {
          case_id: "abc", path: PATH,
          manifest: manifestFor("abc"), recovered_from_backup: true, conflicting_path: null,
        };
      }
      throw new Error(`comando inesperado: ${cmd}`);
    });
    const outcome = await repo().openExistingFolder?.();
    expect(outcome?.kind).toBe("opened");
  });
});

describe("migración legacy y aislamiento por cuenta", () => {
  beforeEach(() => setTauriEnv(true));

  it("reclama un caso legacy sólo después de que la sesión confirma su taskId", async () => {
    const canClaim = vi.fn(async (_record: unknown) => true);
    let writtenManifest: string | null = null;
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      if (cmd === "case_list_authorized") {
        expect(args).toEqual({ ownerUserId: "alice" });
        return [{ case_id: "legacy", path: PATH, available: true, can_repair: false }];
      }
      if (cmd === "case_read") {
        expect(args).toEqual({ caseId: "legacy", ownerUserId: "alice" });
        return { case_id: "legacy", path: PATH, manifest: legacyManifestFor("legacy"), recovered_from_backup: false, conflicting_path: null };
      }
      if (cmd === "case_write") {
        writtenManifest = String(args?.contents);
        expect(args?.ownerUserId).toBe("alice");
        return null;
      }
      throw new Error(`comando inesperado: ${cmd}`);
    });

    const repository = createTauriCaseRepository({ ownerUserId: "alice", canClaimLegacyCase: canClaim });
    const cases = await repository.listCases();

    expect(canClaim).toHaveBeenCalledWith(expect.objectContaining({ id: "legacy" }));
    expect(canClaim.mock.calls[0][0]).not.toHaveProperty("ownerUserId");
    expect(cases).toMatchObject([{ id: "legacy", ownerUserId: "alice" }]);
    if (writtenManifest === null) throw new Error("la migración no persistió el manifiesto");
    expect(JSON.parse(writtenManifest).ownerUserId).toBe("alice");
  });

  it("un caso legacy que el backend no reconoce queda completamente fuera del listado", async () => {
    const canClaim = vi.fn(async () => false);
    const invoked: string[] = [];
    mockTauriInvoke.mockImplementation(async (cmd) => {
      invoked.push(cmd);
      if (cmd === "case_list_authorized") {
        return [{ case_id: "legacy", path: "/secreto/alice", available: true, can_repair: false }];
      }
      if (cmd === "case_read") {
        return { case_id: "legacy", path: "/secreto/alice", manifest: legacyManifestFor("legacy"), recovered_from_backup: false, conflicting_path: null };
      }
      throw new Error(`no debería invocarse ${cmd}`);
    });

    const repository = createTauriCaseRepository({ ownerUserId: "bob", canClaimLegacyCase: canClaim });
    await expect(repository.listCases()).resolves.toEqual([]);
    expect(invoked).not.toContain("case_write");
  });

  it("un manifiesto ya asignado a otra cuenta no consulta siquiera la migración", async () => {
    const canClaim = vi.fn(async () => true);
    const foreign = JSON.parse(manifestFor("foreign"));
    foreign.ownerUserId = "alice";
    mockTauriInvoke.mockImplementation(async (cmd) => {
      if (cmd === "case_list_authorized") {
        return [{ case_id: "foreign", path: PATH, available: true, can_repair: false }];
      }
      if (cmd === "case_read") {
        return { case_id: "foreign", path: PATH, manifest: JSON.stringify(foreign), recovered_from_backup: false, conflicting_path: null };
      }
      throw new Error(`no debería invocarse ${cmd}`);
    });

    const repository = createTauriCaseRepository({ ownerUserId: "bob", canClaimLegacyCase: canClaim });
    await expect(repository.listCases()).resolves.toEqual([]);
    expect(canClaim).not.toHaveBeenCalled();
  });

  it("elegir físicamente una carpeta no permite apropiarse de una corrida ajena", async () => {
    mockTauriInvoke.mockImplementation(async (cmd) => {
      if (cmd === "case_pick_directory") {
        return { token: "picked", display_path: PATH, has_manifest: true };
      }
      if (cmd === "case_open_token") {
        return { case_id: "legacy", path: PATH, manifest: legacyManifestFor("legacy"), recovered_from_backup: false, conflicting_path: null };
      }
      throw new Error(`no debería invocarse ${cmd}`);
    });
    const repository = createTauriCaseRepository({
      ownerUserId: "bob",
      canClaimLegacyCase: async () => false,
    });

    await expect(repository.openExistingFolder?.()).rejects.toMatchObject({ code: "UNAUTHORIZED" });
  });

  it("una carpeta legacy sin corrida puede asignarse mediante selección explícita", async () => {
    let claimed = false;
    mockTauriInvoke.mockImplementation(async (cmd, args) => {
      if (cmd === "case_pick_directory") {
        return { token: "picked", display_path: PATH, has_manifest: true };
      }
      if (cmd === "case_open_token") {
        return { case_id: "manual", path: PATH, manifest: legacyManifestFor("manual", { withRun: false }), recovered_from_backup: false, conflicting_path: null };
      }
      if (cmd === "case_write") {
        claimed = JSON.parse(String(args?.contents)).ownerUserId === "alice";
        return null;
      }
      throw new Error(`comando inesperado: ${cmd}`);
    });
    const repository = createTauriCaseRepository({ ownerUserId: "alice" });

    const outcome = await repository.openExistingFolder?.();
    expect(outcome?.kind).toBe("opened");
    expect(claimed).toBe(true);
  });
});
