// Comprueba el iframe realmente vendorizado con la CSP de producción y el
// origen Windows de Tauri. Servidores y credenciales son sólo de prueba.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const dist = join(root, "tools/molchat/ui/dist");
const config = JSON.parse(await readFile(join(root, "frontend/src-tauri/tauri.conf.prod.json"), "utf8"));
const csp = config.app.security.csp;
const token = "test-session";
const server = createServer(async (req, res) => {
  const path = new URL(req.url, "http://127.0.0.1").pathname;
  if (path === "/v1/catalog" || path === "/v1/version") {
    if (path === "/v1/catalog" && req.headers.authorization !== `Bearer ${token}`) {
      res.writeHead(401).end();
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(path.endsWith("catalog") ? [] : { stt: "none" }));
    return;
  }
  const file = resolve(dist, path === "/" ? "index.html" : "." + path);
  if (!file.startsWith(dist + sep)) { res.writeHead(404).end(); return; }
  try {
    const body = await readFile(file);
    const mime = file.endsWith(".html") ? "text/html" : file.endsWith(".js")
      ? "text/javascript" : file.endsWith(".css") ? "text/css" : "application/octet-stream";
    res.writeHead(200, { "content-type": mime }).end(body);
  } catch { res.writeHead(404).end(); }
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
let browser;
let hostServer;
try {
  const sidecar = `http://127.0.0.1:${server.address().port}`;
  const html = `<!doctype html><html><body><iframe id="molchat" src="${sidecar}" style="width:420px;height:720px;border:0"></iframe>
    <script>window.addEventListener('message', e => {
      const f = document.getElementById('molchat');
      if (e.source === f.contentWindow && e.origin === '${sidecar}' && e.data?.type === 'molchat-ui-ready')
        f.contentWindow.postMessage({type:'molchat-host-session', token:'${token}', locale:'en', theme:'dark'}, '${sidecar}');
    });</script></body></html>`;
  // El servidor real en loopback evita simular con route.fulfill un origen
  // que Chromium clasificaría como red pública en su control de red local.
  hostServer = createServer((_req, res) => res.writeHead(200, {
    "content-type": "text/html", "content-security-policy": csp,
  }).end(html));
  await new Promise((ok, fail) => {
    hostServer.once("error", fail);
    hostServer.listen(80, "127.0.0.1", ok);
  });
  browser = await chromium.launch({ headless: true,
    ...(process.env.MOLCHAT_TEST_BROWSER ? { executablePath: process.env.MOLCHAT_TEST_BROWSER } : {}) });
  const page = await browser.newPage();
  const diagnostics = [];
  page.on("console", msg => diagnostics.push(`console ${msg.type()}: ${msg.text()}`));
  page.on("pageerror", err => diagnostics.push(`pageerror: ${err.message}`));
  page.on("requestfailed", req => diagnostics.push(`requestfailed ${req.url()}: ${req.failure()?.errorText}`));
  await page.goto("http://tauri.localhost/");
  const frame = page.frameLocator("#molchat");
  try {
    await frame.locator("header").waitFor({ timeout: 15000 });
  } catch (error) {
    console.error("CSP MolChat diagnóstico:", diagnostics.join(" | "),
      "frames:", page.frames().map(f => f.url()).join(", "));
    throw error;
  }
  const child = page.frames().find(f => f.url().startsWith(sidecar));
  assert.ok(child, "el iframe no cargó el sidecar vendorizado");
  assert.equal(await child.evaluate(() => sessionStorage.getItem("molchat.session")), token);
  assert.equal(await child.locator("html").getAttribute("lang"), "en");
  assert.equal(await child.locator("html").getAttribute("data-theme"), "dark");
  for (const width of [420, 360, 320]) {
    await page.locator("#molchat").evaluate((frame, width) => { frame.style.width = `${width}px`; }, width);
    const layout = await child.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
    assert.ok(layout.scroll <= layout.width, `el contenido desborda a ${width}px: ${JSON.stringify(layout)}`);
  }
  await child.getByRole("button", { name: "Show history" }).click();
  await child.getByRole("button", { name: "New conversation" }).click();
  await child.getByRole("button", { name: "Settings", exact: true }).click();
  await child.getByRole("heading", { name: "Settings", exact: true }).waitFor();
  console.log("CSP MolChat: UI vendorizada cargada; sesión, idioma y tema recibidos; panel sin desbordamiento");
} finally {
  if (browser) await browser.close();
  if (hostServer?.listening) await new Promise((ok) => hostServer.close(ok));
  await new Promise((ok) => server.close(ok));
}
