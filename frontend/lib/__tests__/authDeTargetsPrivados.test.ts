// =====================================================================
// Los clientes del receptor privado envían la sesión (SOL-01)
// =====================================================================
//
// LA AUDITORÍA (DevOps SOL, 2026-09-30): el backend protege bien el target
// privado — con el token del propietario la comprobación devuelve 200, sin
// token devuelve 404 — pero la INTERFAZ pedía receptor y preflight sin
// credenciales. El dueño recibía un 404 de SU propia variante desde la
// pestaña Evaluación, y el flujo quedaba bloqueado aunque la API lo
// autorizaba. `proApi` ya había pasado por esto («el único cliente de la app
// que no adjuntaba el token», ver `proApiAuth.test.ts`); los que quedaban
// eran `requestPreflight` y `getTargetPdb`.
//
// Lo que este archivo fija:
//
// 1. Con sesión activa en `moldesign_auth`, ambos clientes envían
//    `Authorization: Bearer <token>`.
// 2. Sin sesión, NINGUNO inventa credenciales: los targets públicos siguen
//    siendo comprobables para cualquiera.
//
// El lado del servidor — propietario 200 con origen «privado», ajeno y
// anónimo 404 uniforme — lo fija
// `backend/tests/test_preflight_targets_privados.py`.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:9999" }));

import { getTargetPdb } from "../api";
import { requestPreflight } from "../preflight";

function authorizationFromCall(call: unknown[]): string | null {
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers).get("Authorization");
}

function iniciarSesionDelPropietario() {
  window.localStorage.setItem(
    "moldesign_auth",
    JSON.stringify({ token: "token-del-propietario" }),
  );
}

/** Informe mínimo: `requestPreflight` sólo transporta el JSON del servidor. */
function informeMinimo() {
  return {
    schema_version: 4,
    generated_at: "2026-10-02T00:00:00.000Z",
    execution_route: "docking_vina",
    input_fingerprint: "sha256:abc",
    input_document: "{}",
    receptor: {
      reference: null,
      pdb_id: "USR_TEST",
      chain: "A",
      origin: "privado",
      source_available: false,
      source_sha256: null,
      prepared_available: false,
      prepared_sha256: null,
      prepared_compatible: null,
      prepared_chains: [],
    },
    ligand: {
      input_smiles: "CC(=O)Oc1ccccc1C(=O)O",
      canonical_smiles: "CC(=O)Oc1ccccc1C(=O)O",
      smiles_hash: "hash",
      molecular_formula: "C9H8O4",
      heavy_atom_count: 13,
      error: null,
      vina_atom_compatibility: { evaluated: true, supported: true, unsupported_elements: [] },
    },
    effective_config: {
      grid_center: [1, 2, 3],
      grid_size: [20, 20, 20],
      grid_center_origin: "override_usuario",
      grid_size_origin: "override_usuario",
      derived_box: null,
      hotspots: [],
      hotspots_origin: "ninguno",
      docking_engine: "vina",
      exhaustiveness: 8,
      num_poses: 9,
      seed: 42,
      conformers: 1,
      heteroatom_policy: {
        route: "docking_vina",
        waters: "eliminadas",
        metals: "conservados_solo_whitelist",
        organic_cofactors: "bloqueados_sin_plantilla_local",
        organic_cofactors_kept: [],
        cofactors_whitelist_declared: [],
        cofactors_whitelist_applied: true,
        source: "test",
      },
    },
    preparation_diff: {
      state: "no_evaluado",
      reason: "sin fuente",
      source: null,
      route_input: null,
      removed: null,
      preserved: null,
    },
    controls: [],
    technical_blockers: [],
    warnings: [],
    not_evaluated: [],
  };
}

describe("SOL-01: los clientes del flujo privado llevan la sesión", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("requestPreflight envía la sesión del propietario", async () => {
    iniciarSesionDelPropietario();
    const fetchSpy = vi.fn(async () =>
      new Response(JSON.stringify(informeMinimo()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = fetchSpy as typeof fetch;

    await requestPreflight({ smiles: "CCO", targetPdbId: "USR_TEST" });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:9999/evaluation/preflight");
    // Sin credenciales, el backend oculta el privado con el MISMO 404 que a
    // un anónimo: la comprobación del dueño contra su propio receptor muere
    // aquí. Con la sesión, llega.
    expect(authorizationFromCall(fetchSpy.mock.calls[0])).toBe("Bearer token-del-propietario");
    // Y no se pierde el Content-Type del POST JSON.
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("getTargetPdb envía la sesión del propietario", async () => {
    iniciarSesionDelPropietario();
    const fetchSpy = vi.fn(async () =>
      new Response("ATOM      1  N   ALA A   1", { status: 200 }),
    );
    global.fetch = fetchSpy as typeof fetch;

    await getTargetPdb("USR_TEST");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url] = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:9999/targets/USR_TEST/pdb");
    expect(authorizationFromCall(fetchSpy.mock.calls[0])).toBe("Bearer token-del-propietario");
  });

  it("sin sesión, ningún cliente inventa credenciales", async () => {
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) =>
      new Response(
        String(input).includes("preflight")
          ? JSON.stringify(informeMinimo())
          : "ATOM      1  N   ALA A   1",
        { status: 200 },
      ),
    );
    global.fetch = fetchSpy as typeof fetch;

    await requestPreflight({ smiles: "CCO", targetPdbId: "7E2Y" });
    await getTargetPdb("7E2Y");

    // Los targets públicos siguen siendo comprobables por cualquiera: la
    // ausencia de sesión no fabrica un token vacío ni rompe la petición.
    expect(authorizationFromCall(fetchSpy.mock.calls[0])).toBeNull();
    expect(authorizationFromCall(fetchSpy.mock.calls[1])).toBeNull();
  });
});
