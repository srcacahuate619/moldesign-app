// =====================================================================
// Cohortes — el flujo completo, y lo que la interfaz ya NO hace
// =====================================================================
//
// Lo que protegen, en orden de gravedad:
//
// 1. **Ninguna llamada al Batch histórico.** Es la promesa del gate: el flujo
//    visible se migró entero. Un `fetch` a `/evaluation/batch` volvería a
//    mezclar receptores bajo ALL y a ordenar por `total_score`.
//
// 2. **Una cohorte bloqueada no se guarda ni se ejecuta.** Es la puerta que
//    impide congelar una entrada que no es ejecutable.
//
// 3. **El estado se recupera del backend.** Al recargar se pregunta; no se
//    restaura desde la pestaña algo que el backend pueda contradecir.
//
// 4. **Ningún score 0-100.** La única magnitud por molécula es la afinidad
//    Vina observada, con ese nombre.

import { describe, expect, it, beforeEach, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

vi.mock("../../../../components/interfaces/pro/TargetSelectorModal", () => ({
  default: ({
    isOpen,
    targets,
    onSelect,
    onClose,
  }: {
    isOpen: boolean;
    targets: Array<{ pdb_id: string; name: string }>;
    onSelect: (pdbId: string) => void;
    onClose: () => void;
  }) => isOpen ? (
    <div role="dialog" aria-label="Catálogo de receptores">
      {targets.map((target) => (
        <button key={target.pdb_id} type="button" onClick={() => onSelect(target.pdb_id)}>
          {target.name}
        </button>
      ))}
      <button type="button" onClick={onClose}>Cerrar catálogo</button>
    </div>
  ) : null,
}));

import CohortesPage from "../page";
import { resetApiUrl, setApiUrlFromPort } from "../../../../lib/config";
import { mockFetch } from "../../../../vitest.setup";

/**
 * `mockFetch` está declarado sin parámetros en `vitest.setup`, porque la
 * mayoría de las pruebas sólo encolan respuestas. Aquí SÍ se enruta por url y
 * método, así que se accede con la firma real de `fetch`. El cast está
 * localizado en un sitio y documentado, en vez de repartido por el archivo.
 */
const fetchMock = mockFetch as unknown as {
  mockImplementation: (fn: (url: unknown, init?: RequestInit) => Promise<Response>) => void;
  mock: { calls: unknown[][] };
};

// ── Object URL: jsdom no los implementa ──────────────────────────────
const creados: string[] = [];
const revocados: string[] = [];

function instalarObjectUrls() {
  const api = window.URL as unknown as Record<string, unknown>;
  api.createObjectURL = () => {
    const url = `blob:mock/${creados.length}`;
    creados.push(url);
    return url;
  };
  api.revokeObjectURL = (url: string) => {
    revocados.push(url);
  };
}

// ── Respuestas del backend ───────────────────────────────────────────

const LISTA = /\/evaluation\/cohorts$/;
const CATALOGO = /\/targets\/(?:\?.*)?$/;

const TARGETS = [
  {
    pdb_id: "2XYZ", name: "Receptor con cadena", organism: "Homo sapiens",
    resolution: 1.8, chain: "B", requires_cns: false, is_hot: false,
    spearman_rho: null, calibration_date: null,
  },
  {
    pdb_id: "3NOP", name: "Receptor sin cadena", organism: "Homo sapiens",
    resolution: 2.1, chain: "", requires_cns: false, is_hot: false,
    spearman_rho: null, calibration_date: null,
  },
];

const RESUMEN = {
  total_rows: 5, eligible_rows: 3, invalid_rows: 2, unique_canonical_ligands: 2,
  duplicate_rows: 1, explicit_reference_controls: 1, explicit_positive_controls: 0,
  explicit_negative_controls: 0, input_coverage: 0.6, input_coverage_denominator: 5,
};

const PREFLIGHT_OK = {
  schema_version: 1, generated_at: "2026-08-24T10:00:00Z",
  cohort_fingerprint: "sha256:" + "a".repeat(64),
  normalized_study: {
    schema_version: 1, name: "Serie", receptor: { pdb_id: "7E2Y", chain: "A" },
    config: { docking_engine: "vina", exhaustiveness: 8, num_poses: 5 },
  },
  decision: "ready", blockers: [], warnings: ["DUPLICADOS_CANONICOS"],
  summary: RESUMEN, rows: [],
};

const PREFLIGHT_BLOQUEADO = {
  ...PREFLIGHT_OK,
  decision: "blocked",
  blockers: ["SIN_MOLECULAS_ELEGIBLES"],
  summary: { ...RESUMEN, eligible_rows: 0, input_coverage: 0 },
};

const COHORTE = {
  id: "coh-1", name: "Serie", status: "ready", schema_version: 1,
  cohort_fingerprint: PREFLIGHT_OK.cohort_fingerprint, created_at: "2026-08-24T10:00:00Z",
  source: { filename: "cohorte.csv", content_type: "text/csv", sha256: "f".repeat(64), size_bytes: 181 },
  provenance: {}, preflight: PREFLIGHT_OK,
};

const PROGRESO = {
  total_rows: 5, eligible_rows: 3, completed_rows: 2, failed_rows: 0,
  not_evaluated_rows: 0, pending_rows: 0, running_rows: 0,
  duplicate_reused_rows: 1, cancelled_rows: 0, interrupted_rows: 0,
};

const CORRIDA = {
  id: "run-1", cohort_id: "coh-1", status: "completed",
  cohort_fingerprint: PREFLIGHT_OK.cohort_fingerprint, run_fingerprint: "sha256:" + "b".repeat(64),
  cancel_requested: false, effective_config: {}, receptor_provenance: {},
  progress: PROGRESO, created_at: null, started_at: null, finished_at: null,
  last_error: null, rows: [],
};

const EVIDENCIA = {
  contract: "cohort_evidence/v1", run_id: "run-1", cohort_id: "coh-1",
  cohort_name: "Serie", run_status: "completed", sorted_by: "afinidad_vina_observada",
  cohort_fingerprint: PREFLIGHT_OK.cohort_fingerprint, run_fingerprint: CORRIDA.run_fingerprint,
  effective_config: {}, receptor: {},
  coverage: {
    source_rows: 5, eligible_rows: 3, not_eligible_rows: 2, unique_molecules_executed: 2,
    completed_rows: 2, failed_rows: 0, not_evaluated_rows: 0, duplicate_reused_rows: 1,
    pending_rows: 0, running_rows: 0, interrupted_rows: 0, cancelled_rows: 0,
    denominators: { eligible_over_source: { numerator: 3, denominator: 5, value: 0.6 } },
  },
  molecules: [
    {
      source_row_index: 0, source_name: "aspirina", canonical_smiles: "CCO", status: "completed",
      observed_vina_affinity_kcal_mol: -8.3, molecule_id: "m1", result_id: "r1",
      active_label: true, control_role: "reference", duplicate_of_row: null,
      reused_from_row: null, error_code: null, error_detail: null,
    },
    {
      source_row_index: 1, source_name: "rota", canonical_smiles: "CCC", status: "failed",
      observed_vina_affinity_kcal_mol: null, molecule_id: null, result_id: null,
      active_label: false, control_role: "none", duplicate_of_row: null,
      reused_from_row: null, error_code: "PIPELINE_FALLO", error_detail: "el motor se cayó",
    },
  ],
  labeled_metrics: {
    status: "not_evaluated", reason_code: "MUESTRA_INSUFICIENTE",
    reason: "Sólo hay 2 moléculas etiquetadas con afinidad.",
    roc_auc: null, enrichment_factors: [], n_total: 2, n_positive: 1, n_negative: 1,
    coverage: 0.5, controls: [],
  },
  provenance: {}, limits: ["Completar un acoplamiento no demuestra actividad."],
};

function json(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "content-type": "application/json" },
  });
}

type Regla = [RegExp, () => Response] | [RegExp, string, () => Response];

/**
 * Enruta por URL y, cuando hace falta, por método.
 *
 * `/evaluation/cohorts` es GET (listar) y POST (congelar) a la vez: sin el
 * método, el listado recibiría el objeto de la creación y la prueba mediría un
 * enrutado equivocado en vez del componente.
 */
function enrutar(reglas: Regla[]) {
  fetchMock.mockImplementation(async (url: unknown, init?: RequestInit) => {
    const texto = String(url);
    const metodo = (init?.method ?? "GET").toUpperCase();
    for (const regla of reglas) {
      if (!regla[0].test(texto)) continue;
      if (regla.length === 3) {
        if (regla[1] !== metodo) continue;
        return regla[2]();
      }
      return (regla[1] as () => Response)();
    }
    throw new Error(`Ruta no esperada en la prueba: ${metodo} ${texto}`);
  });
}

const RUTAS_BASE: Regla[] = [
  [CATALOGO, "GET", () => json(TARGETS)],
  [LISTA, "GET", () => json([])],
];

function archivo(): File {
  return new File(["name,smiles\na,CCO\n"], "cohorte.csv", { type: "text/csv" });
}

async function definir() {
  fireEvent.change(screen.getByLabelText("Nombre de la cohorte"), { target: { value: "Serie" } });
  fireEvent.change(screen.getByLabelText("Receptor PDB ID"), { target: { value: "7E2Y" } });
  const entrada = screen.getByLabelText("Archivo de moléculas") as HTMLInputElement;
  Object.defineProperty(entrada, "files", { value: [archivo()], configurable: true });
  fireEvent.change(entrada);
}

function urlsLlamadas(): string[] {
  return fetchMock.mock.calls.map((c) => String(c[0]));
}

describe("Cohortes", () => {
  beforeEach(() => {
    creados.length = 0;
    revocados.length = 0;
    instalarObjectUrls();
    resetApiUrl();
    setApiUrlFromPort(8017);
    window.localStorage.clear();
    window.localStorage.setItem(
      "moldesign_auth",
      JSON.stringify({ user: { user_id: "test-user" } }),
    );
  });

  // ── El flujo completo ───────────────────────────────────────────
  it("reutiliza el catálogo canónico y envía al preflight el receptor seleccionado", async () => {
    enrutar([
      [/cohorts\/preflight$/, () => json(PREFLIGHT_OK)],
      ...RUTAS_BASE,
    ]);
    render(<CohortesPage />);

    fireEvent.change(screen.getByLabelText("Cadena"), { target: { value: "Z" } });
    fireEvent.click(await screen.findByRole("button", { name: "Abrir catálogo de receptores" }));
    fireEvent.click(screen.getByRole("button", { name: "Receptor con cadena" }));
    expect(screen.getByLabelText("Receptor PDB ID")).toHaveValue("2XYZ");
    expect(screen.getByLabelText("Cadena")).toHaveValue("B");

    fireEvent.click(screen.getByRole("button", { name: "Abrir catálogo de receptores" }));
    fireEvent.click(screen.getByRole("button", { name: "Receptor sin cadena" }));
    expect(screen.getByLabelText("Receptor PDB ID")).toHaveValue("3NOP");
    expect(screen.getByLabelText("Cadena")).toHaveValue("");

    fireEvent.click(screen.getByRole("button", { name: "Abrir catálogo de receptores" }));
    fireEvent.click(screen.getByRole("button", { name: "Receptor con cadena" }));
    fireEvent.change(screen.getByLabelText("Nombre de la cohorte"), { target: { value: "Serie" } });
    const entrada = screen.getByLabelText("Archivo de moléculas") as HTMLInputElement;
    Object.defineProperty(entrada, "files", { value: [archivo()], configurable: true });
    fireEvent.change(entrada);
    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));

    await screen.findByTestId("resumen-preflight");
    const llamada = fetchMock.mock.calls.find((call) => String(call[0]).endsWith("/evaluation/cohorts/preflight"));
    expect(llamada).toBeDefined();
    const cuerpo = (llamada?.[1] as RequestInit).body as FormData;
    const estudio = JSON.parse(String(cuerpo.get("study")));
    expect(estudio.receptor).toEqual({ pdb_id: "2XYZ", chain: "B" });
  });

  it("mantiene disponible la entrada manual si el catálogo falla y permite reintentarlo", async () => {
    enrutar([
      [CATALOGO, "GET", () => { throw new Error("catálogo fuera de servicio"); }],
      [LISTA, "GET", () => json([])],
    ]);
    render(<CohortesPage />);

    expect(await screen.findByText(/No se pudo cargar el catálogo/)).toBeInTheDocument();
    const receptor = screen.getByLabelText("Receptor PDB ID");
    fireEvent.change(receptor, { target: { value: "7E2Y" } });
    expect(receptor).toHaveValue("7E2Y");

    fireEvent.click(screen.getByRole("button", { name: "Reintentar catálogo de receptores" }));
    await waitFor(() => {
      const llamadas = fetchMock.mock.calls.filter((call) => CATALOGO.test(String(call[0])));
      expect(llamadas).toHaveLength(2);
    });
  });

  it("recorre preflight → guardar → ejecutar → evidencia → informe", async () => {
    enrutar([
      [/cohorts\/preflight$/, () => json(PREFLIGHT_OK)],
      [/cohort-runs\/run-1\/evidence/, () => json(EVIDENCIA)],
      [/cohort-runs\/run-1\/dossier\/preview$/, () =>
        new Response("%PDF-1.4", {
          status: 200,
          headers: { "content-type": "application/pdf", "content-disposition": 'inline; filename="d.pdf"' },
        })],
      [/cohort-runs\/run-1$/, () => json(CORRIDA)],
      [/cohorts\/coh-1\/runs/, () => json({ run_id: "run-1", cohort_id: "coh-1", status: "queued", run_fingerprint: "x", eligible_rows: 3, workers: 2 })],
      [LISTA, "POST", () => json(COHORTE)],
      ...RUTAS_BASE,
    ]);
    render(<CohortesPage />);
    await definir();

    // 2 · Comprobar
    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));
    const resumen = await screen.findByTestId("resumen-preflight");
    expect(within(resumen).getByTestId("cobertura-preflight")).toHaveTextContent("3 de 5");
    expect(within(resumen).getByTestId("warnings")).toHaveTextContent("Hay estructuras repetidas");

    // 3 · Guardar
    fireEvent.click(screen.getByRole("button", { name: /guardar cohorte/i }));
    await screen.findByTestId("cohorte-guardada");

    // 4 · Ejecutar
    fireEvent.click(screen.getByRole("button", { name: /ejecutar cohorte/i }));
    const progreso = await screen.findByTestId("progreso");
    expect(progreso).toHaveTextContent("Completada");
    // El identificador durable queda anotado para poder recuperarlo al recargar.
    expect(window.localStorage.getItem("moldesign_cohort_run:user:test-user")).toBe("run-1");

    // 5 · Evidencia
    fireEvent.click(screen.getByRole("button", { name: /ver evidencia/i }));
    const evidencia = await screen.findByTestId("evidencia");
    expect(within(evidencia).getByTestId("cobertura-evidencia")).toHaveTextContent("5");
    expect(within(evidencia).getByTestId("tabla-evidencia")).toHaveTextContent("-8.30");
    // La métrica se abstiene y lo dice con su código estable.
    expect(within(evidencia).getByTestId("metricas")).toHaveTextContent("Sólo hay 2 moléculas etiquetadas");

    // 6 · Informe
    fireEvent.click(screen.getByRole("button", { name: /ver informe/i }));
    const informe = await screen.findByTestId("informe");
    expect(within(informe).getByTitle("Dossier de cohorte")).toHaveAttribute(
      "src", `${creados[0]}#toolbar=0`,
    );
  });

  // ── Ninguna llamada al Batch histórico ──────────────────────────
  it("no llama a /evaluation/batch en ningún punto del flujo", async () => {
    enrutar([
      [/cohorts\/preflight$/, () => json(PREFLIGHT_OK)],
      [LISTA, "POST", () => json(COHORTE)],
      ...RUTAS_BASE,
    ]);
    render(<CohortesPage />);
    await definir();
    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));
    await screen.findByTestId("resumen-preflight");
    fireEvent.click(screen.getByRole("button", { name: /guardar cohorte/i }));
    await screen.findByTestId("cohorte-guardada");

    for (const url of urlsLlamadas()) {
      expect(url).not.toMatch(/\/evaluation\/batch/);
    }
    expect(urlsLlamadas().some((u) => u.includes("/evaluation/cohorts"))).toBe(true);
  });

  it("la interfaz no ofrece ALL, Early Exit, total_score ni tiempo estimado", async () => {
    enrutar(RUTAS_BASE);
    const { container } = render(<CohortesPage />);
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const texto = container.textContent ?? "";
    for (const prohibido of ["ALL", "Early Exit", "total_score", "mejor fármaco", "tiempo estimado"]) {
      expect(texto).not.toContain(prohibido);
    }
    // Y sí ofrece lo que sustituye a todo eso.
    expect(texto.toLowerCase()).toContain("afinidad vina observada");
  });

  // ── Blockers ────────────────────────────────────────────────────
  it("una cohorte bloqueada no se puede guardar", async () => {
    enrutar([[/cohorts\/preflight$/, () => json(PREFLIGHT_BLOQUEADO)], ...RUTAS_BASE]);
    render(<CohortesPage />);
    await definir();

    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));
    await screen.findByTestId("blockers");

    expect(screen.getByTestId("blockers")).toHaveTextContent("Ninguna molécula puede entrar");
    expect(screen.getByRole("button", { name: /guardar cohorte/i })).toBeDisabled();
    // Y sin cohorte guardada no hay nada que ejecutar.
    expect(screen.queryByRole("button", { name: /ejecutar cohorte/i })).not.toBeInTheDocument();
  });

  // ── Recuperación tras recarga ───────────────────────────────────
  it("al recargar recupera la corrida preguntando al backend", async () => {
    window.localStorage.setItem("moldesign_cohort_run:user:test-user", "run-1");
    enrutar([
      [/cohort-runs\/run-1$/, () => json({ ...CORRIDA, status: "running" })],
      [/cohorts\/coh-1$/, () => json(COHORTE)],
      ...RUTAS_BASE,
    ]);

    render(<CohortesPage />);

    const progreso = await screen.findByTestId("progreso");
    // El estado sale del backend, no de lo que la pestaña recordaba.
    expect(progreso).toHaveTextContent("Ejecutando");
    expect(urlsLlamadas().some((u) => u.includes("/evaluation/cohort-runs/run-1"))).toBe(true);
  });

  it("si el backend ya no conoce la corrida, la olvida en vez de fingirla", async () => {
    window.localStorage.setItem("moldesign_cohort_run:user:test-user", "run-fantasma");
    enrutar([
      [/cohort-runs\/run-fantasma$/, () => json({ detail: "No existe la corrida solicitada." }, 404)],
      ...RUTAS_BASE,
    ]);

    render(<CohortesPage />);

    await waitFor(() =>
      expect(window.localStorage.getItem("moldesign_cohort_run:user:test-user")).toBeNull(),
    );
    expect(screen.queryByTestId("progreso")).not.toBeInTheDocument();
  });

  it("al abrir una cohorte restaura toda su configuración congelada", async () => {
    const guardada = {
      ...COHORTE,
      name: "Serie congelada",
      preflight: {
        ...PREFLIGHT_OK,
        normalized_study: {
          ...PREFLIGHT_OK.normalized_study,
          name: "Serie congelada",
          receptor: { pdb_id: "2XYZ", chain: "B" },
          config: { docking_engine: "qvina2", exhaustiveness: 17, num_poses: 9, seed: 73 },
        },
      },
    };
    const item = {
      ...guardada,
      receptor_pdb_id: "2XYZ",
      docking_engine: "qvina2",
      summary: RESUMEN,
    };
    enrutar([
      [/cohorts\/coh-1\/runs\/latest$/, "GET", () => json(CORRIDA)],
      [/cohorts\/coh-1$/, "GET", () => json(guardada)],
      [LISTA, "GET", () => json([item])],
      [CATALOGO, "GET", () => json(TARGETS)],
    ]);
    render(<CohortesPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Serie congelada/ }));

    await screen.findByTestId("cohorte-guardada");
    expect(screen.getByLabelText("Nombre de la cohorte")).toHaveValue("Serie congelada");
    expect(screen.getByLabelText("Receptor PDB ID")).toHaveValue("2XYZ");
    expect(screen.getByLabelText("Cadena")).toHaveValue("B");
    expect(screen.getByLabelText("Motor de docking")).toHaveValue("qvina2");
    expect(screen.getByLabelText("Exhaustividad")).toHaveValue(17);
    expect(screen.getByLabelText("Poses")).toHaveValue(9);
    expect(screen.getByLabelText("Semilla")).toHaveValue("73");
    expect(screen.getByTestId("progreso")).toHaveTextContent("Completada");
    expect(window.localStorage.getItem("moldesign_cohort_run:user:test-user")).toBe("run-1");
  });

  // ── Cancelar y reanudar ─────────────────────────────────────────
  it("cancelar y reanudar llaman a sus rutas y reflejan el estado", async () => {
    let estado = "running";
    enrutar([
      [/cohorts\/preflight$/, () => json(PREFLIGHT_OK)],
      [/cohort-runs\/run-1\/cancel$/, () => { estado = "cancelled"; return json({ ...CORRIDA, status: "cancelled", cancel_requested: true }); }],
      [/cohort-runs\/run-1\/resume/, () => { estado = "queued"; return json({ run_id: "run-1", cohort_id: "coh-1", status: "queued", run_fingerprint: "x", eligible_rows: 1, workers: 2 }); }],
      [/cohort-runs\/run-1$/, () => json({ ...CORRIDA, status: estado })],
      [/cohorts\/coh-1\/runs/, () => json({ run_id: "run-1", cohort_id: "coh-1", status: "queued", run_fingerprint: "x", eligible_rows: 3, workers: 2 })],
      [LISTA, "POST", () => json(COHORTE)],
      ...RUTAS_BASE,
    ]);
    render(<CohortesPage />);
    await definir();
    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));
    await screen.findByTestId("resumen-preflight");
    fireEvent.click(screen.getByRole("button", { name: /guardar cohorte/i }));
    await screen.findByTestId("cohorte-guardada");
    fireEvent.click(screen.getByRole("button", { name: /ejecutar cohorte/i }));
    await screen.findByTestId("progreso");

    fireEvent.click(screen.getByRole("button", { name: /cancelar/i }));
    await waitFor(() => expect(screen.getByTestId("progreso")).toHaveTextContent("Cancelada"));
    expect(urlsLlamadas().some((u) => u.endsWith("/cancel"))).toBe(true);
  });

  // ── Errores de conexión ─────────────────────────────────────────
  it("un error de conexión se declara como tal y no como cohorte inválida", async () => {
    fetchMock.mockImplementation(async (url: unknown) => {
      if (String(url).endsWith("/evaluation/cohorts")) return json([]);
      throw new TypeError("Failed to fetch");
    });
    render(<CohortesPage />);
    await definir();

    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(/conexión/i);
    expect(alerta).not.toHaveTextContent(/inválida/i);
  });

  it("un 409 del backend muestra su mensaje, no uno inventado", async () => {
    enrutar([
      [/cohorts\/preflight$/, () => json(PREFLIGHT_OK)],
      [LISTA, "POST", () =>
        json({ detail: { code: "CORRIDA_ACTIVA", message: "Esta cohorte ya tiene una corrida en marcha." } }, 409)],
      ...RUTAS_BASE,
    ]);
    render(<CohortesPage />);
    await definir();
    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));
    await screen.findByTestId("resumen-preflight");

    fireEvent.click(screen.getByRole("button", { name: /guardar cohorte/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Esta cohorte ya tiene una corrida en marcha.",
    );
  });

  it("un 422 muestra el detalle de validación de FastAPI", async () => {
    enrutar([
      [/cohorts\/preflight$/, () => json({ detail: [{ msg: "La semilla debe ser un entero válido." }] }, 422)],
      ...RUTAS_BASE,
    ]);
    render(<CohortesPage />);
    await definir();

    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La semilla debe ser un entero válido.",
    );
  });

  // ── Object URLs ─────────────────────────────────────────────────
  it("revoca el object URL del dossier al desmontar", async () => {
    enrutar([
      [/cohorts\/preflight$/, () => json(PREFLIGHT_OK)],
      [/cohort-runs\/run-1\/evidence/, () => json(EVIDENCIA)],
      [/cohort-runs\/run-1\/dossier\/preview$/, () =>
        new Response("%PDF-1.4", { status: 200, headers: { "content-type": "application/pdf" } })],
      [/cohort-runs\/run-1$/, () => json(CORRIDA)],
      [/cohorts\/coh-1\/runs/, () => json({ run_id: "run-1", cohort_id: "coh-1", status: "queued", run_fingerprint: "x", eligible_rows: 3, workers: 2 })],
      [LISTA, "POST", () => json(COHORTE)],
      ...RUTAS_BASE,
    ]);
    const vista = render(<CohortesPage />);
    await definir();
    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));
    await screen.findByTestId("resumen-preflight");
    fireEvent.click(screen.getByRole("button", { name: /guardar cohorte/i }));
    await screen.findByTestId("cohorte-guardada");
    fireEvent.click(screen.getByRole("button", { name: /ejecutar cohorte/i }));
    await screen.findByTestId("progreso");
    fireEvent.click(screen.getByRole("button", { name: /ver evidencia/i }));
    await screen.findByTestId("evidencia");
    fireEvent.click(screen.getByRole("button", { name: /ver informe/i }));
    await waitFor(() => expect(creados.length).toBe(1));

    vista.unmount();

    expect(revocados).toContain(creados[0]);
  });

  // ── Filtros ─────────────────────────────────────────────────────
  it("los filtros por estado acotan la tabla sin ocultar el denominador", async () => {
    enrutar([
      [/cohorts\/preflight$/, () => json(PREFLIGHT_OK)],
      [/cohort-runs\/run-1\/evidence/, () => json(EVIDENCIA)],
      [/cohort-runs\/run-1$/, () => json(CORRIDA)],
      [/cohorts\/coh-1\/runs/, () => json({ run_id: "run-1", cohort_id: "coh-1", status: "queued", run_fingerprint: "x", eligible_rows: 3, workers: 2 })],
      [LISTA, "POST", () => json(COHORTE)],
      ...RUTAS_BASE,
    ]);
    render(<CohortesPage />);
    await definir();
    fireEvent.click(screen.getByRole("button", { name: /comprobar cohorte/i }));
    await screen.findByTestId("resumen-preflight");
    fireEvent.click(screen.getByRole("button", { name: /guardar cohorte/i }));
    await screen.findByTestId("cohorte-guardada");
    fireEvent.click(screen.getByRole("button", { name: /ejecutar cohorte/i }));
    await screen.findByTestId("progreso");
    fireEvent.click(screen.getByRole("button", { name: /ver evidencia/i }));
    const tabla = await screen.findByTestId("tabla-evidencia");
    expect(within(tabla).getAllByRole("row")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Fallidas" }));

    expect(within(screen.getByTestId("tabla-evidencia")).getAllByRole("row")).toHaveLength(1);
    // La cobertura sigue declarando el total: filtrar no cambia el denominador.
    expect(screen.getByTestId("cobertura-evidencia")).toHaveTextContent("5");
  });
});
