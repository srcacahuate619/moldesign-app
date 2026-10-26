// Comprueba el fetch que usa Tauri en Windows con las CSP que realmente servimos.
// El destino IPC se intercepta en Playwright; no se invoca ningún comando Rust.
// Esto acredita el permiso CSP sobre el fetch usado por el protocolo, no la
// ejecución del puente nativo ni que un aviso de fallback causara una evaluación
// fallida. Alcance y medidas: docs/auditorias/arranque_idioma_ipc_2026-10-07.md.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function cspNext() {
  const ts = require("typescript");
  const source = await readFile(path.join(frontend, "proxy.ts"), "utf8");
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText.replace('"next/server"', JSON.stringify(pathToFileURL(require.resolve("next/server")).href));
  const { proxy } = await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);
  const { NextRequest } = require("next/server");
  return proxy(new NextRequest("http://localhost:3000/")).headers.get("Content-Security-Policy");
}

export async function comprobarIpcCsp(browser) {
  const policies = [["Next dev", await cspNext()]];
  for (const name of ["tauri.conf.json", "tauri.conf.prod.json", "tauri.conf.msix.json"]) {
    const config = JSON.parse(await readFile(path.join(frontend, "src-tauri", name), "utf8"));
    policies.push([name, config.app.security.csp]);
  }
  // Un caso bloqueado acredita que esta prueba detecta exactamente la regresión.
  policies.push(["autotest: IPC bloqueado", "default-src 'self'; connect-src 'self'"]);
  const results = [];
  const server = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "text/html", "Cache-Control": "no-store",
      "Content-Security-Policy": policies[0]?.[1] ?? "default-src 'none'" });
    response.end("<!doctype html><html><title>IPC CSP</title></html>");
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try {
    const page = await browser.newPage();
    await page.route("http://ipc.localhost/**", route => route.fulfill({
      status: 200, body: '{"port":8007}',
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "POST, OPTIONS" },
    }));
    while (policies.length) {
      const [name] = policies[0];
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      const connected = await page.evaluate(async () => {
        try {
          const response = await fetch("http://ipc.localhost/ensure_backend", {
            method: "POST", body: "{}", headers: {
              "Content-Type": "application/json", "Tauri-Callback": "1", "Tauri-Error": "2",
              "Tauri-Invoke-Key": "test-only",
            },
          });
          return response.ok && (await response.json()).port === 8007;
        } catch { return false; }
      });
      const expected = name !== "autotest: IPC bloqueado";
      results.push({ nombre: `IPC con CSP de ${name}`, ok: connected === expected,
        detalle: connected ? "fetch permitido" : "fetch bloqueado" });
      policies.shift();
    }
    await page.close();
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
  return results;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    const results = await comprobarIpcCsp(browser);
    for (const result of results) console.log(`${result.ok ? "OK" : "FALLA"} ${result.nombre}: ${result.detalle}`);
    if (results.some(result => !result.ok)) process.exitCode = 1;
  } finally { await browser.close(); }
}
