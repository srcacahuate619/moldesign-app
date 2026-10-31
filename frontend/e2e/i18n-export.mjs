import { persistedResult } from "./fixtures/persisted-result.mjs";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import net from "node:net";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { chromium } from "@playwright/test";
import { crearServidor } from "../../scripts/qa_sandbox/servidor.mjs";
import { RegistroDeCasos } from "../../scripts/qa_sandbox/casos.mjs";

const require = createRequire(import.meta.url);
const { inspectItems } = require("../scripts/i18n-dom.cjs");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "out");
const config = JSON.parse(await fs.readFile(path.join(root, "src-tauri/tauri.conf.prod.json"), "utf8"));
const baseConfig = JSON.parse(await fs.readFile(path.join(root, "src-tauri/tauri.conf.json"), "utf8"));
const csp = config.app?.security?.csp ?? baseConfig.app.security.csp;
await fs.access(path.join(out, "index.html")); // El guardián nunca sustituye out/ por next dev/start.

const index = JSON.parse(await fs.readFile(path.join(out, "registro/index.json"), "utf8"));
const dataTexts = new Set();
for (const entry of index.experimentos) for (const key of ["id", "hipotesis", "razonamiento", "gate", "titulo", "resumen", "entradilla"]) {
  if (typeof entry[key] === "string") dataTexts.add(entry[key].replace(/\s+/g, " ").trim());
}
async function freePort() {
  const socket = net.createServer();
  await new Promise(resolve => socket.listen(0, "127.0.0.1", resolve));
  const port = socket.address().port;
  await new Promise(resolve => socket.close(resolve));
  return port;
}
const frontPort = await freePort(), backPort = await freePort();
// El panel actual es la UI vendorizada, servida por un sidecar local. Las
// respuestas son sintéticas, pero los archivos de interfaz son los que viajan.
const molchatDist = path.resolve(root, "../tools/molchat/ui/dist");
const molchatToken = "i18n-sidecar-fixture";
const sidecar = createServer(async (req, res) => {
  const pathname = new URL(req.url, "http://127.0.0.1").pathname;
  if (pathname.startsWith("/v1/")) {
    if (pathname !== "/v1/version" && req.headers.authorization !== `Bearer ${molchatToken}`) {
      res.writeHead(401).end(); return;
    }
    let body;
    if (pathname === "/v1/catalog" || pathname === "/v1/conversations") body = [];
    else if (pathname === "/v1/version") body = { stt: "none" };
    else { res.writeHead(404).end(); return; }
    res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(body));
    return;
  }
  const file = path.resolve(molchatDist, pathname === "/" ? "index.html" : "." + pathname);
  if (!file.startsWith(molchatDist + path.sep)) { res.writeHead(404).end(); return; }
  try {
    const body = await fs.readFile(file);
    const type = file.endsWith(".html") ? "text/html" : file.endsWith(".js")
      ? "text/javascript" : file.endsWith(".css") ? "text/css" : "application/octet-stream";
    res.writeHead(200, { "content-type": type }).end(body);
  } catch { res.writeHead(404).end(); }
});
await new Promise(resolve => sidecar.listen(0, "127.0.0.1", resolve));
const sidecarUrl = `http://127.0.0.1:${sidecar.address().port}`;
const temp = await fs.mkdtemp(path.join(os.tmpdir(), "moldesign-i18n-export-"));
const cases = new RegistroDeCasos({ dirRegistro: path.join(temp, "registry"), dirPadre: path.join(temp, "cases"),
  archivoSiguiente: path.join(temp, "next.txt"), versionEsquema: 7 });
const server = crearServidor({ outDir: out, csp, puertoFront: frontPort, puertoBack: backPort,
  token: "i18n-fixture", runtimeRoot: temp, raicesLegibles: [temp], casos: cases });
await new Promise(resolve => server.listen(frontPort, "127.0.0.1", resolve));
const url = "http://localhost:" + frontPort;
const states = [], errors = [], unhandled = new Set();
let browser;
let apiFailure = false;
const auth = { access_token: "i18n-fixture", refresh_token: "i18n-refresh", user_id: "i18n-export", username: "QA", email: "qa@local.test" };
const result = { ...persistedResult(), target_name: "QA saved receptor", structural_evidence: { stage_status: "failed", poses_produced: 1, poses_evaluated: 1, validation_engine: "posebusters", poses: [{ rank: 1, status: "failed", checks: [{ check: "internal_energy", estado: "FALLA" }] }] } };
const contract = { keys: new Set(), strings: new Set() };
function collectContract(value) {
  if (typeof value === "string") contract.strings.add(value);
  else if (value && typeof value === "object") for (const [key, item] of Object.entries(value)) { contract.keys.add(key); collectContract(item); }
}
collectContract(result);
const target = { pdb_id: "8T69", name: "VMAT2", organism: "Homo sapiens", resolution: 2.5, chain: "A",
  requires_cns: false, structural_family: "transporter", therapeutic_family: "", is_hot: false, spearman_rho: null,
  calibration_date: null, is_prepared: true, calibration_status: "listo", hotspot_count: 8, hotspots: [],
  grid_center: [0, 0, 0], grid_size: [20, 20, 20], catalog_section: "demostracion" };

async function collect(page) {
  return page.evaluate(() => {
    const items = [];
    const hidden = el => {
      const style = getComputedStyle(el);
      return style.display === "none" || style.visibility === "hidden";
    };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode, parent = node.parentElement;
      if (!parent || parent.closest("script,style,noscript") || hidden(parent) || parent.getClientRects().length === 0) continue;
      const text = node.textContent?.trim();
      if (text) items.push({ channel: "innerText", text, element: parent.tagName, dataField: parent.closest("[data-field-key]")?.getAttribute("data-field-key") });
    }
    // Incluye atributos de controles fuera del viewport y los tooltips sin abrir.
    for (const el of document.body.querySelectorAll("[title],[aria-label],[placeholder]")) {
      for (const attr of ["title", "aria-label", "placeholder"]) {
        const text = el.getAttribute(attr);
        if (text) items.push({ channel: attr, text, element: el.tagName, dataField: el.closest("[data-field-key]")?.getAttribute("data-field-key") });
      }
    }
    return items;
  });
}
async function scan(page, name, screenshotPage = page) {
  await page.waitForFunction(() => document.documentElement.lang === "en");
  await page.waitForTimeout(300);
  const result = inspectItems(await collect(page), dataTexts, contract);
  states.push({ name, findings: result.findings, exclusions: result.exclusions });
  const reportArg = process.argv.find(arg => arg.startsWith("--report="));
  if (result.findings.length && reportArg && result.findings[0].channel === "innerText") await page.getByText(result.findings[0].text, { exact: true }).first().scrollIntoViewIfNeeded();
  if (result.findings.length && reportArg) await screenshotPage.screenshot({ path: path.resolve(reportArg.slice(9)).replace(/\.json$/, ".jpg"), type: "jpeg", quality: 72 });
  if (reportArg && name === "legal: pestaña 3") await page.screenshot({ path: path.join(path.dirname(path.resolve(reportArg.slice(9))), "I18N-402-despues.jpg"), type: "jpeg", quality: 72 });
  if (reportArg && !result.findings.length && name === "detalle de la pose fallida") {
    await page.getByRole("button", { name: "View failed checks (1)", exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(path.dirname(path.resolve(reportArg.slice(9))), "I18N-403-despues.jpg"), type: "jpeg", quality: 72 });
  }
  assert.equal(result.findings.length, 0, name + ": castellano en export\n" + JSON.stringify(result.findings, null, 2));
  console.log("OK " + name);
}
async function open(page, route, name) {
  const response = await page.goto(url + route, { waitUntil: "networkidle" });
  assert.equal(response.status(), 200, route);
  assert.equal(response.headers()["content-security-policy"], csp, "El export debe servirse con CSP de producción");
  await page.waitForFunction(() => document.querySelector("main") || document.querySelector("nav"));
  await scan(page, name);
}
try {
  browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : undefined, headless: true });
  const context = await browser.newContext({ locale: "es-MX", viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(() => {
    if (!localStorage.getItem("moldesign_locale:user:i18n-export")) localStorage.setItem("moldesign_locale:user:i18n-export", "en");
  });
  await page.route("http://127.0.0.1:" + backPort + "/**", async route => {
    const request = route.request(), p = new URL(request.url()).pathname;
    let body;
    if (p === "/evaluation/status/task-alice") return route.fulfill({ status: 200, json: { task_id: "task-alice", status: "SUCCESS", progress: 100, result, error: null } });
    if (p === "/evaluation/result/molecule-alice") return route.fulfill({ status: 200, json: result });
    if (p === "/evaluation/stream/task-alice") return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'data: {"type":"pipeline_done","timestamp":"2026-08-27T12:00:00Z"}' + String.fromCharCode(10, 10) });
    if (p.startsWith("/evaluation/files/") || p.startsWith("/evaluation/interactions/") || p.startsWith("/evaluation/ligand-elevation/")) return route.fulfill({ status: 404, json: { detail: "Synthetic fixture has no structure files" } });
    if (apiFailure === "network" && p === "/history/evaluations") return route.abort("failed");
    if (p === "/auth/desktop-login") body = auth;
    else if (p === "/health") body = { status: "healthy", version: "1.0.4", components: { mode: { value: "DESKTOP" } } };
    else if (p === "/targets" || p === "/targets/") body = [target, { ...target, pdb_id: "7E2Y", name: "QA review", calibration_status: "revisar", hotspot_count: 3 },
      { ...target, pdb_id: "1BN1", name: "QA no data", calibration_status: "sin_datos", hotspot_count: 0, is_prepared: false }];
    else if (p === "/targets/community" || p === "/moldex" || p === "/cohorts" || p === "/evaluation/cohorts" || p === "/pro/anti-targets") body = [];
    else if (p === "/blockchain/health") body = { connected: false, network: "devnet", status: "offline" };
    else if (p === "/ai/speech-to-text/status") body = { available: false };
    else if (p === "/molchat-host/status") body = { disponible: true, motivo: "ok" };
    else if (p === "/molchat-host/session") body = { url: sidecarUrl, token: molchatToken, expira_en_s: 3600 };
    else if (p === "/sar/molecule-alice") body = { results: [], total: 0 };
    else if (p === "/history/evaluations") body = { items: [], total: 0, page: 1, page_size: 20 };
    else if (p === "/history/stats") body = { total_evaluations: 0, completed_evaluations: 0, failed_evaluations: 0, unique_targets: 0 };
    else if (p === "/molcy/fuentes") body = { moldex: [], receptores: [] };
    else if (p === "/molcy/trabajos") body = { trabajos: [] };
    else if (p === "/molcy/salida") body = { disponible: true, predeterminada: "C:\\QA\\Molcy", global: null };
    else if (p === "/molcy/addon") body = { estado: "inactivo" };
    else if (p === "/molcy/renderizador") body = { disponible: false, motivo: "Blender is not installed", motivo_codigo: "falta_blender", gpu_disponible: false, foto_disponible: false, blenders_encontrados: [] };
    else if (p === "/molcy/recursos") body = {};
    else if (p === "/molcy/blender") body = { estado: "inactivo", ruta: null, version: "5.2.0", descarga_bytes: 0, reserva_bytes: 0, instalado: false, configuracion: {} };
    else if (p.startsWith("/evaluation/engines")) body = [];
    else { unhandled.add(p); body = { detail: "Fixture endpoint not declared" }; }
    await route.fulfill({ status: p.startsWith("/molcy/") && "detail" in body ? 503 : apiFailure && p === "/history/evaluations" ? 500 : 200,
      headers: { "content-type": "application/json", "access-control-allow-origin": url }, body: JSON.stringify(body) });
  });
  // Toda red fuera del origen local/fixture se bloquea: ninguna descarga o proveedor real.
  await page.route("https://**", route => route.abort());
  await open(page, "/", "primer uso");
  await page.reload({ waitUntil: "networkidle" });
  assert.equal(await page.locator("html").getAttribute("lang"), "en");
  await scan(page, "English persistente tras recarga");
  for (let step = 2; step <= 6; step++) {
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await scan(page, "tutorial: controles del paso " + step);
  }
  for (const [route, name] of [["/evaluation", "casos vacíos"], ["/preparacion", "preparación vacía"],
    ["/evaluation/batch", "lotes vacíos"], ["/moldex", "Moldex vacío"], ["/molcy", "Molcy sin renderizador"],
    ["/history", "historial vacío"], ["/comunidad", "comunidad vacía"], ["/ciencia", "registro científico"]]) {
    await open(page, route, name);
  }
  await open(page, "/evaluation", "abrir caso");
  await page.getByRole("button", { name: /new case|create case/i }).first().click();
  await scan(page, "diálogo nuevo caso");
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill("I18N QA");
  await dialog.getByRole("button", { name: /create a case|create case/i }).click();
  await dialog.waitFor({ state: "hidden" });
  await scan(page, "caso creado");
  await page.getByRole("button", { name: /choose.*receptor/i }).first().click();
  await scan(page, "selector receptor y tooltips");
  for (const section of ["propios", "verificado"]) {
    await page.locator("#target-selector-tab-" + section).click();
    await scan(page, "selector receptor: " + section);
  }
  await page.keyboard.press("Escape");

  const caseFiles = (await fs.readdir(path.join(temp, "cases"), { recursive: true })).filter(file => path.basename(file) === "case.json");
  assert.equal(caseFiles.length, 1);
  const caseFile = path.join(temp, "cases", caseFiles[0]);
  const savedCase = JSON.parse(await fs.readFile(caseFile, "utf8"));
  savedCase.runs = [{ taskId: "task-alice", moleculeId: "molecule-alice", executionState: "completed", startedAt: "2026-08-27T11:59:00.000Z", finishedAt: "2026-08-27T12:00:00.000Z" }];
  await fs.writeFile(caseFile, JSON.stringify(savedCase));
  await page.reload({ waitUntil: "networkidle" });
  await page.getByText("I18N QA", { exact: true }).first().click();
  await page.getByText("QA saved receptor", { exact: false }).first().waitFor();
  await scan(page, "resultado sintético reabierto");
  await page.getByRole("button", { name: "View physical checks for pose #1", exact: true }).click();
  await scan(page, "detalle de la pose fallida");
  await page.getByRole("button", { name: "View failed checks (1)", exact: true }).click();
  await scan(page, "controles físicos de pose fallida");
  const areaLabels = ["Poses and checks", "Properties and chemical state", "Analysis", "Provenance and data"];
  for (const area of areaLabels) {
    await page.getByRole("tab", { name: area, exact: true }).click();
    await scan(page, "resultado: " + area);
    if (area === "Analysis") {
      const methods = page.locator('[id^="advanced-tab-"]');
      for (let i = 0; i < await methods.count(); i++) { await methods.nth(i).click(); await scan(page, "método avanzado " + (i + 1)); }
    }
  }
  await page.getByRole("button", { name: /options/i }).first().click();
  await scan(page, "opciones");
  const language = page.getByRole("button", { name: /English/i }).first();
  await language.click();
  await scan(page, "selector de idiomas");
  await page.keyboard.press("Escape");
  for (const [button, name] of [[/About MolDesign/i, "acerca de"], [/Legal, privacy and licenses/i, "legal: interfaz"], [/Support and help/i, "soporte y ayuda"]]) {
    await page.goto(url + "/evaluation", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /options/i }).first().click();
    await page.getByRole("button", { name: button }).click();
    await scan(page, name);
    const modal = page.getByRole("dialog").last();
    if (name === "acerca de") {
      const sections = modal.locator("nav button");
      const total = await sections.count();
      assert(total > 1, "Acerca de sin secciones");
      for (let i = 1; i < total; i++) { await sections.nth(i).click(); await scan(page, "acerca de: sección " + (i + 1)); }
    }
    if (name === "legal: interfaz") {
      const tabs = modal.getByRole("tab");
      const total = await tabs.count();
      assert(total > 1, "Legal sin pestañas");
      for (let i = 1; i < total; i++) { await tabs.nth(i).click(); await scan(page, "legal: pestaña " + (i + 1)); }
    }
    await page.keyboard.press("Escape");
  }
  await page.goto(url + "/evaluation", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Open MolChat", exact: true }).click();
  const marco = page.frameLocator('iframe[title="MolChat (external)"]');
  await marco.getByRole("button", { name: "Settings", exact: true }).click();
  const ventanaMolchat = page.frames().find(frame => frame.url().startsWith(sidecarUrl));
  assert(ventanaMolchat, "El sidecar vendorizado no abrió su iframe");
  await scan(ventanaMolchat, "ajustes de MolChat en inglés", page);
  await page.goto(url + "/evaluation", { waitUntil: "networkidle" });
  apiFailure = true;
  await open(page, "/history", "historial con HTTP 500");
  apiFailure = "network";
  await open(page, "/history", "historial sin conexión");
  apiFailure = false;

  // Control positivo sobre el mismo DOM y los cuatro canales del guardián.
  await page.evaluate(() => {
    const pre = document.createElement("pre"); pre.id = "i18n-control";
    pre.textContent = "No se pudo guardar el caso";
    pre.title = "Falta un receptor";
    pre.setAttribute("aria-label", "Sin datos de entrada");
    const input = document.createElement("input"); input.placeholder = "Escribe el nombre del caso"; pre.append(input);
    document.body.append(pre);
  });
  const planted = inspectItems(await collect(page), dataTexts).findings;
  for (const channel of ["innerText", "title", "aria-label", "placeholder"]) assert(planted.some(row => row.channel === channel), "Control ciego: " + channel);
  await page.locator("#i18n-control").evaluate(el => el.remove());
  const proofArg = process.argv.find(arg => arg.startsWith("--report="));
  if (proofArg) await page.screenshot({ path: path.resolve(proofArg.slice(9)).replace(/\.json$/, ".jpg"), type: "jpeg", quality: 72 });
  console.log("OK control positivo: innerText/title/aria-label/placeholder");
  assert.deepEqual(errors, [], "Errores de página");
  assert.deepEqual([...unhandled], [], "Endpoints sin fixture explícito");
  console.log(JSON.stringify({ states: states.length, positiveChannels: 4, originalDataExclusions: dataTexts.size, unhandled: [...unhandled] }));
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
  await new Promise(resolve => sidecar.close(resolve));
  const real = await fs.realpath(temp), allowed = await fs.realpath(os.tmpdir());
  assert(real.startsWith(allowed + path.sep), "Carpeta temporal fuera de TEMP");
  await fs.rm(real, { recursive: true, force: true });
  const reportArg = process.argv.find(arg => arg.startsWith("--report="));
  if (reportArg) await fs.writeFile(path.resolve(reportArg.slice(9)), JSON.stringify({ states, errors, unhandled: [...unhandled] }, null, 2) + "\n");
}
