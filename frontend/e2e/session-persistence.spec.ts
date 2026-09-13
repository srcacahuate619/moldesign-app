import { expect, test, type Page, type Route } from "@playwright/test";

type Researcher = "alice" | "bob";

const API = "http://127.0.0.1:8999";

function authFor(user: Researcher) {
  return {
    token: `token-${user}`,
    refreshToken: `refresh-${user}`,
    user: { user_id: user, username: user, email: `${user}@local.test` },
  };
}

async function switchSession(page: Page, user: Researcher) {
  await page.evaluate((auth) => localStorage.setItem("moldesign_auth", JSON.stringify(auth)), authFor(user));
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Casos", exact: true })).toBeVisible();
}

async function createCase(page: Page, name: string) {
  await page.getByRole("button", { name: /crear caso|nuevo caso/i }).first().click();
  const dialog = page.getByRole("dialog", { name: "Nuevo caso" });
  await dialog.getByLabel("Nombre").fill(name);
  await dialog.getByRole("button", { name: "Crear caso" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

function persistedResult() {
  return {
    id: "result-alice",
    molecule_id: "molecule-alice",
    smiles_hash: "sha256:alice",
    target_name: "Receptor persistido",
    target_spearman_rho: null,
    target_pdb_id: "7E2Y",
    affinity_kcal: -8.4,
    affinity_score: 84,
    docking_poses: [{ rank: 1, affinity: -8.4, rmsd_lb: 0, rmsd_ub: 0 }],
    parsing_source: "sdf",
    vina_version: "test",
    vina_random_seed: 42,
    scientific_warnings: [],
    task_id: "task-alice",
    molecular_weight: 46.07,
    log_p: -0.3,
    tpsa: 20.2,
    hbd: 1,
    hba: 1,
    rotatable_bonds: 0,
    heavy_atom_count: 3,
    ring_count: 0,
    lipinski_pass: true,
    veber_pass: true,
    ghose_pass: null,
    egan_pass: null,
    muegge_pass: null,
    muegge_score: null,
    fsp3: null,
    is_pains: false,
    pains_matches: [],
    qed: 0.4,
    sa_score: 1.2,
    sa_reasons: [],
    adme_score: null,
    druglikeness_score: null,
    blood_viability_score: null,
    total_score: 84,
    gnn_score: null,
    xgb_score: null,
    clgnn_score: null,
    quantum_score: null,
    ums_score: null,
    mmgbsa_score: null,
    target_family: null,
    engine_used: "vina",
    fallback_reason: null,
    in_applicability_domain: true,
    model_used: "vina",
    specificity_score: null,
    hotspots_hit: [],
    target_hotspots: [],
    shap_values: null,
    gnn_attention: null,
    gnn_attention_svg: null,
    gnn_pharmacophores: null,
    selectivity_ratio: null,
    selectivity_verdict: null,
    anti_target_results: [],
    selectivity_ran: false,
    poses_file_path: null,
    is_control: false,
    ai_report: null,
    blockchain_tx_id: null,
    error_message: null,
    evaluated_at: "2026-08-27T12:00:00.000Z",
  };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "Access-Control-Allow-Origin": "http://127.0.0.1:3100" },
    body: JSON.stringify(body),
  });
}

test("cada cuenta conserva sus casos y Alice recupera su corrida tras reiniciar", async ({ page }) => {
  // La sesión debe existir antes de que React hidrate AuthProvider. Inyectarla
  // después de la primera carga deja al provider con un snapshot obsoleto y no
  // reproduce un arranque real de la aplicación.
  await page.addInitScript((auth) => {
    if (!localStorage.getItem("moldesign_auth")) {
      localStorage.setItem("moldesign_auth", JSON.stringify(auth));
    }
  }, authFor("alice"));

  const authorization: string[] = [];
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const bearer = request.headers().authorization;
    if (bearer) authorization.push(`${path}:${bearer}`);

    if (path === "/ai/providers" || path === "/ai/conversations") return json(route, []);
    if (path === "/ai/startup") return json(route, { mode: "manual" });
    if (path === "/targets" || path === "/targets/") {
      return json(route, [{
        pdb_id: "7E2Y", name: "5-HT1A", organism: "Homo sapiens", resolution: 3,
        chain: "R", requires_cns: false, structural_family: "gpcr",
        therapeutic_family: "psiquiatria", is_hot: false, spearman_rho: null,
        calibration_date: null,
      }]);
    }
    if (path === "/evaluation/status/task-alice") {
      return json(route, {
        task_id: "task-alice", status: "SUCCESS", progress: 100,
        result: persistedResult(), error: null,
        started_at: "2026-08-27T11:59:00.000Z", finished_at: "2026-08-27T12:00:00.000Z",
      });
    }
    if (path === "/evaluation/result/molecule-alice") {
      return json(route, persistedResult());
    }
    if (path === "/evaluation/stream/task-alice") {
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: { "Access-Control-Allow-Origin": "http://127.0.0.1:3100" },
        body: 'data: {"type":"pipeline_done","timestamp":"2026-08-27T12:00:00Z"}\n\n',
      });
    }
    return json(route, {});
  });

  await page.goto("/evaluation", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Casos", exact: true })).toBeVisible();
  await createCase(page, "Caso de Alice");

  await page.evaluate(() => {
    const key = Object.keys(localStorage).find((item) => item.startsWith("moldesign_case:alice:"));
    if (!key) throw new Error("No se persistió el caso de Alice");
    const record = JSON.parse(localStorage.getItem(key) as string);
    record.activeRun = {
      taskId: "task-alice",
      moleculeId: "molecule-alice",
      executionState: "completed",
      startedAt: "2026-08-27T11:59:00.000Z",
      completedAt: "2026-08-27T12:00:00.000Z",
    };
    localStorage.setItem(key, JSON.stringify(record));
  });

  await switchSession(page, "bob");
  await expect(page.getByText("Caso de Alice", { exact: true })).toHaveCount(0);
  await createCase(page, "Caso de Bob");

  await switchSession(page, "alice");
  await expect(page.getByText("Caso de Bob", { exact: true })).toHaveCount(0);
  await page.getByText("Caso de Alice", { exact: true }).first().click();

  await expect(page.getByText(/Receptor persistido/).first()).toBeVisible();
  await expect(page.getByText(/La evaluación terminó sin resultados/)).toHaveCount(0);
  await expect.poll(() => authorization).toContain(
    "/evaluation/result/molecule-alice:Bearer token-alice",
  );
  await expect.poll(() => authorization).toContain(
    "/evaluation/stream/task-alice:Bearer token-alice",
  );
  // La aplicación mantiene un fetch SSE abierto por diseño. Cerrar la página
  // de forma explícita libera el stream antes del teardown del worker (Edge en
  // Windows puede conservar el handle si se deja sólo al cierre implícito).
  await page.close();
});
