/**
 * Traspaso del invitado — las reglas que no pueden romperse.
 *
 * El backend ya está probado (`test_traspaso_del_invitado.py`). Lo que se prueba
 * aquí es lo que sólo existe en el cliente:
 *
 * - que **nada se mueva sin que el investigador lo pida**;
 * - que un fallo del backend **no deje casos huérfanos** apuntando a moléculas
 *   que siguen siendo de otra cuenta;
 * - que el ofrecimiento **no se ofrezca a sí mismo** cuando la sesión es la del
 *   invitado, que es lo que el backend rechaza con 403;
 * - que un caso que no se puede mover **se cuente**, en vez de desaparecer.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CaseIndexEntry, CaseRecord } from "../cases/types";
import type { CaseRepository } from "../cases/repository";
import {
  CLAVE_INVITADO,
  ejecutarTraspaso,
  inventarioDelInvitado,
  invitadoPendienteDeTraspaso,
  invitadoRecordado,
  olvidarInvitado,
  recordarInvitado,
} from "../traspaso";

const INVITADO = "11111111-1111-4111-8111-111111111111";
const CUENTA = "22222222-2222-4222-8222-222222222222";

function caso(id: string, ownerUserId: string, moleculeId?: string): CaseRecord {
  return {
    schemaVersion: 6,
    id,
    ownerUserId,
    name: `Caso ${id}`,
    studyKind: "evaluation",
    status: "draft",
    createdAt: "2026-09-01T00:00:00.000Z",
    updatedAt: "2026-09-01T00:00:00.000Z",
    lastOpenedAt: "2026-09-01T00:00:00.000Z",
    archived: false,
    storage: { mode: "browser" },
    ...(moleculeId
      ? {
          activeRun: {
            taskId: `task-${id}`,
            moleculeId,
            executionState: "completed" as const,
            startedAt: "2026-09-01T00:00:00.000Z",
          },
        }
      : {}),
  } as unknown as CaseRecord;
}

/** Repositorio en memoria con la parte del contrato que usa el traspaso. */
function repoFalso(ownerUserId: string, registros: CaseRecord[] = []) {
  const almacen = new Map<string, CaseRecord>(registros.map((r) => [r.id, r]));
  const repo = {
    id: "browser" as const,
    capabilities: { canOpenFolder: false, canRevealInFileManager: false, storageLabel: "test" },
    async listCases(): Promise<CaseIndexEntry[]> {
      return [...almacen.values()].map((r) => ({
        id: r.id,
        ownerUserId: r.ownerUserId,
        name: r.name,
        status: r.status,
        createdAt: r.createdAt,
        updatedAt: r.updatedAt,
        lastOpenedAt: r.lastOpenedAt,
        archived: r.archived,
        storageMode: "browser",
        ...(r.activeRun ? { activeRun: r.activeRun } : {}),
      })) as CaseIndexEntry[];
    },
    async readCase(id: string): Promise<CaseRecord> {
      const r = almacen.get(id);
      if (!r) throw new Error(`no existe ${id}`);
      return r;
    },
    async adoptCase(record: CaseRecord): Promise<CaseRecord> {
      if (record.ownerUserId !== ownerUserId) throw new Error("dueño equivocado");
      almacen.set(record.id, record);
      return record;
    },
    async forgetCase(id: string): Promise<void> {
      almacen.delete(id);
    },
  };
  return { repo: repo as unknown as CaseRepository, almacen };
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("memoria de la cuenta invitada", () => {
  it("recuerda al invitado y lo ofrece a una cuenta distinta", () => {
    recordarInvitado({ user_id: INVITADO, username: "invitado" });
    expect(invitadoRecordado()?.user_id).toBe(INVITADO);
    expect(invitadoPendienteDeTraspaso(CUENTA)?.user_id).toBe(INVITADO);
  });

  it("no se ofrece a sí mismo: el backend rechaza ese traspaso con 403", () => {
    recordarInvitado({ user_id: INVITADO });
    expect(invitadoPendienteDeTraspaso(INVITADO)).toBeNull();
  });

  it("no ofrece nada si no hay sesión", () => {
    recordarInvitado({ user_id: INVITADO });
    expect(invitadoPendienteDeTraspaso(null)).toBeNull();
  });

  it("descartar olvida el ofrecimiento y no vuelve", () => {
    recordarInvitado({ user_id: INVITADO });
    olvidarInvitado();
    expect(invitadoPendienteDeTraspaso(CUENTA)).toBeNull();
    expect(window.localStorage.getItem(CLAVE_INVITADO)).toBeNull();
  });
});

describe("inventario", () => {
  it("cuenta aparte los casos sin resultado en vez de insinuar que los hay", async () => {
    const { repo } = repoFalso(INVITADO, [
      caso("a", INVITADO, "mol-1"),
      caso("b", INVITADO, "mol-2"),
      caso("c", INVITADO),
    ]);
    const inv = await inventarioDelInvitado(repo);
    expect(inv.casos).toHaveLength(3);
    expect([...inv.moleculeIds].sort()).toEqual(["mol-1", "mol-2"]);
    expect(inv.casosSinResultado).toBe(1);
  });

  it("no repite una molécula evaluada en dos casos", async () => {
    const { repo } = repoFalso(INVITADO, [
      caso("a", INVITADO, "mol-1"),
      caso("b", INVITADO, "mol-1"),
    ]);
    expect((await inventarioDelInvitado(repo)).moleculeIds).toEqual(["mol-1"]);
  });
});

describe("ejecución", () => {
  it("mueve backend y casos, y olvida el ofrecimiento", async () => {
    recordarInvitado({ user_id: INVITADO });
    const origen = repoFalso(INVITADO, [caso("a", INVITADO, "mol-1")]);
    const destino = repoFalso(CUENTA);
    const llamarBackend = vi
      .fn()
      .mockResolvedValue({ moleculas_traspasadas: 1, cohortes_traspasadas: 0 });

    const res = await ejecutarTraspaso({
      destinoUserId: CUENTA,
      repoInvitado: origen.repo,
      repoDestino: destino.repo,
      moleculeIds: ["mol-1"],
      llamarBackend,
    });

    expect(llamarBackend).toHaveBeenCalledWith({ molecule_ids: ["mol-1"], cohort_ids: [] });
    expect(res).toMatchObject({ moleculasTraspasadas: 1, casosMovidos: 1, casosNoMovidos: [] });
    expect(destino.almacen.get("a")?.ownerUserId).toBe(CUENTA);
    expect(origen.almacen.has("a")).toBe(false);
    expect(invitadoRecordado()).toBeNull();
  });

  it("si el backend falla, el caso sigue siendo del invitado", async () => {
    recordarInvitado({ user_id: INVITADO });
    const origen = repoFalso(INVITADO, [caso("a", INVITADO, "mol-1")]);
    const destino = repoFalso(CUENTA);

    await expect(
      ejecutarTraspaso({
        destinoUserId: CUENTA,
        repoInvitado: origen.repo,
        repoDestino: destino.repo,
        moleculeIds: ["mol-1"],
        llamarBackend: vi.fn().mockRejectedValue(new Error("503")),
      }),
    ).rejects.toThrow("503");

    // Ni un caso movido, ni el ofrecimiento perdido: reintentar es seguro
    // porque el endpoint del backend es idempotente.
    expect(origen.almacen.get("a")?.ownerUserId).toBe(INVITADO);
    expect(destino.almacen.size).toBe(0);
    expect(invitadoRecordado()?.user_id).toBe(INVITADO);
  });

  it("un caso que no se puede mover se cuenta y no detiene a los demás", async () => {
    recordarInvitado({ user_id: INVITADO });
    const origen = repoFalso(INVITADO, [
      caso("a", INVITADO, "mol-1"),
      caso("roto", INVITADO, "mol-2"),
      caso("c", INVITADO, "mol-3"),
    ]);
    const destino = repoFalso(CUENTA);
    const adoptar = destino.repo.adoptCase.bind(destino.repo);
    destino.repo.adoptCase = async (record: CaseRecord) => {
      if (record.id === "roto") throw new Error("IO_ERROR");
      return adoptar(record);
    };

    const res = await ejecutarTraspaso({
      destinoUserId: CUENTA,
      repoInvitado: origen.repo,
      repoDestino: destino.repo,
      moleculeIds: ["mol-1", "mol-2", "mol-3"],
      llamarBackend: vi
        .fn()
        .mockResolvedValue({ moleculas_traspasadas: 3, cohortes_traspasadas: 0 }),
    });

    expect(res.casosMovidos).toBe(2);
    expect(res.casosNoMovidos).toEqual(["roto"]);
    expect(origen.almacen.has("roto")).toBe(true);
  });

  it("no llama al backend ni toca nada si nadie lo pide", async () => {
    recordarInvitado({ user_id: INVITADO });
    const origen = repoFalso(INVITADO, [caso("a", INVITADO, "mol-1")]);
    // No se ejecuta el traspaso: sólo se consulta el inventario, que es lo que
    // hace la interfaz antes de preguntar.
    await inventarioDelInvitado(origen.repo);
    expect(origen.almacen.get("a")?.ownerUserId).toBe(INVITADO);
    expect(invitadoRecordado()?.user_id).toBe(INVITADO);
  });
});
