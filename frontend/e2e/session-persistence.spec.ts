import { persistedResult } from "./fixtures/persisted-result.mjs";
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
  await dialog.getByRole("button", { name: "Crear un caso", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
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
    // Esquema v7: la corrida vive en el LIBRO (`runs`). `activeRun` ya no se lee
    // del manifiesto, se deriva de la última fila (lib/cases/schema.ts). Esta
    // prueba seguía escribiendo el `activeRun` de la v6, que la aplicación
    // ignora con razón, y fallaba desde que entró la v7.
    record.runs = [{
      taskId: "task-alice",
      moleculeId: "molecule-alice",
      executionState: "completed",
      startedAt: "2026-08-27T11:59:00.000Z",
      finishedAt: "2026-08-27T12:00:00.000Z",
    }];
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
