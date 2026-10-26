#!/usr/bin/env node
// scripts/qa_sandbox/autotest.mjs
// =============================================================================
// Autotest de integración de la cápsula. Levanta una cápsula REAL (agente 9, en
// una carpeta temporal), la ejerce por HTTP y con un navegador, la apaga y
// comprueba que no ha tocado el perfil real del usuario.
//
//   node scripts/qa_sandbox/autotest.mjs [--out DIR] [--estricto]
//
// Cada comprobación termina en OK, FALLA o NO EJECUTADO. «No ejecutado» no es
// verde: sale en el resumen con su motivo, y con --estricto cuenta como fallo.
// Hay muestras que DEBEN fallar (origen ajeno, token erróneo, `..\`) además de
// las que deben pasar: una guardia que sólo ha dicho «limpio» no ha demostrado
// que ve (restricción 2 del AGENTS.md).
//
// La comprobación con navegador crea un caso por la INTERFAZ y exige que
// `case.json` aparezca en disco: es lo que detecta que el manifiesto emulado
// (casos.mjs) se desvía de lo que el frontend acepta. Si la interfaz de casos
// cambia de textos, esa comprobación falla y dice qué no encontró.
// =============================================================================

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import net from "node:net";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { carpetasDe, diferencias, esCapsulaBorrable, hayDiferencias, instantanea, origenDe, puertosDe } from "./lib.mjs";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(AQUI, "..", "..");
const AGENTE = 9;
const puertos = puertosDe(AGENTE);
const origen = origenDe(puertos);

const argv = process.argv.slice(2);
const estricto = argv.includes("--estricto");
const iOut = argv.indexOf("--out");

const resultados = [];
function comprobar(nombre, estado, detalle = "") {
  resultados.push({ nombre, estado, detalle });
  const etiqueta = { OK: "OK          ", FALLA: "FALLA       ", "NO EJECUTADO": "NO EJECUTADO" }[estado];
  console.log(`  ${etiqueta}  ${nombre}${detalle ? `  ->  ${detalle}` : ""}`);
}
const ok = (nombre, condicion, detalle = "") => comprobar(nombre, condicion ? "OK" : "FALLA", condicion ? "" : detalle);

function raizDelRuntime() {
  if (process.env.MOLDESIGN_RUNTIME_ROOT) return path.resolve(process.env.MOLDESIGN_RUNTIME_ROOT);
  const comun = path.resolve(REPO, execFileSync("git", ["rev-parse", "--git-common-dir"], { cwd: REPO, encoding: "utf8" }).trim());
  return path.basename(comun) === ".git" ? path.dirname(comun) : REPO;
}

const puertoOcupado = (p) => new Promise((resolve) => {
  const s = net.createConnection({ host: "127.0.0.1", port: p });
  s.on("connect", () => { s.destroy(); resolve(true); });
  s.on("error", () => resolve(false));
});

/** `fetch` con `Host` y cabeceras que `fetch` no deja fijar: se usa `http`. */
async function http(url, { host, headers = {}, method = "GET", body } = {}) {
  const { default: nodeHttp } = await import("node:http");
  const u = new URL(url);
  return new Promise((resolve, reject) => {
    const req = nodeHttp.request({ host: u.hostname, port: u.port, path: u.pathname + u.search, method, headers: { ...(host ? { Host: host } : {}), ...headers } }, (res) => {
      const t = [];
      res.on("data", (c) => t.push(c));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(t).toString("utf8") }));
    });
    req.on("error", reject);
    if (body !== undefined) req.write(body);
    req.end();
  });
}

const sandboxUp = (...args) => execFileSync(process.execPath, [path.join(AQUI, "sandbox-up.mjs"), ...args], { encoding: "utf8", stdio: "pipe", cwd: REPO });

async function main() {
  console.log("=".repeat(72));
  console.log(`Autotest de la cápsula (agente ${AGENTE}: backend ${puertos.back}, frontend ${puertos.front})`);
  console.log("=".repeat(72));

  const rt = raizDelRuntime();
  const out = iOut >= 0 ? path.resolve(argv[iOut + 1]) : path.join(rt, "frontend", "out");
  if (!fs.existsSync(path.join(out, "index.html"))) {
    comprobar("hay un export que servir", "FALLA", `no existe ${out}\\index.html: construye el frontend o pasa --out`);
    return;
  }
  for (const p of [puertos.back, puertos.front]) {
    if (await puertoOcupado(p)) { comprobar(`el puerto ${p} está libre antes de empezar`, "FALLA", "otra cápsula 9 viva: apágala con --agente 9 --down"); return; }
  }

  // --- foto del perfil REAL antes ----------------------------------------------------
  const home = os.homedir();
  const vigilados = [".moldesign", "MolDesign", path.join(".cache", "huggingface")].map((r) => path.join(home, r));
  const antes = new Map(vigilados.map((d) => [d, instantanea(d)]));
  const capsula = path.join(os.tmpdir(), `moldesign-qa-autotest-${crypto.randomBytes(4).toString("hex")}`);
  const c = carpetasDe(capsula);
  let levantada = false;

  try {
    // --- levantar ------------------------------------------------------------------------
    console.log("\n[1/5] Levantando la cápsula…");
    let salida;
    try {
      salida = sandboxUp("--agente", String(AGENTE), "--capsula", capsula, "--out", out);
      levantada = true;
    } catch (e) {
      comprobar("la cápsula levanta", "FALLA", String(e.stdout ?? e.message).split("\n").slice(-12).join(" | "));
      return;
    }
    ok("la cápsula levanta y termina el lanzador", /LISTA/.test(salida));
    const manifiesto = JSON.parse(fs.readFileSync(path.join(capsula, "manifest.json"), "utf8"));
    ok("el manifiesto declara las desviaciones respecto a la app instalada", manifiesto.desviaciones_respecto_a_la_app_instalada?.length >= 5);
    ok("autoverificación del propio lanzador", manifiesto.autoverificacion.desktop_login === 200 && manifiesto.autoverificacion.cors_origen_propio === true && manifiesto.autoverificacion.cors_origen_ajeno_bloqueado === true, JSON.stringify(manifiesto.autoverificacion));

    // --- backend: salud, CORS y login -----------------------------------------------------
    console.log("\n[2/5] Backend: salud, CORS y login…");
    const back = `http://127.0.0.1:${puertos.back}`;
    ok("/health responde 200", (await http(`${back}/health`)).status === 200);
    for (const [nombre, o, permitido] of [
      ["origen propio", origen, true],
      ["otro puerto de localhost", `http://localhost:${puertos.front + 1}`, false],
      ["127.0.0.1 en vez de localhost", `http://127.0.0.1:${puertos.front}`, false],
      ["un dominio ajeno", "http://evil.example", false],
      ["el origen de la cápsula del agente 1", `http://localhost:${puertosDe(1).front}`, false],
    ]) {
      const r = await http(`${back}/health`, { headers: { Origin: o } });
      const acao = r.headers["access-control-allow-origin"];
      ok(`CORS ${permitido ? "permite" : "BLOQUEA"} ${nombre}`, permitido ? acao === o : acao === undefined, `access-control-allow-origin=${acao}`);
    }
    const shim = await http(`${origen}/__sandbox_tauri_shim.js`, { headers: { "Sec-Fetch-Site": "same-origin" } });
    const token = /var TOKEN = "([0-9a-f]+)"/.exec(shim.body)?.[1];
    ok("el shim sirve el secreto del backend al propio origen", !!token);
    // El manifiesto lleva la huella SHA-256 del export (64 hex legítimos): se busca el secreto exacto, no «algo que lo parezca».
    ok("el manifiesto NO contiene el secreto del backend", !!token && !fs.readFileSync(path.join(capsula, "manifest.json"), "utf8").includes(token), "el secreto aparece en manifest.json");
    ok("login con el secreto correcto: 200", (await http(`${back}/auth/desktop-login`, { headers: { "X-MolDesign-Launch": token ?? "" } })).status === 200);
    const malo = await http(`${back}/auth/desktop-login`, { headers: { "X-MolDesign-Launch": "0".repeat(64) } });
    ok("login con un secreto erróneo: NO es 200", malo.status !== 200, `status ${malo.status}`);
    ok("login sin secreto: NO es 200", (await http(`${back}/auth/desktop-login`)).status !== 200);

    // --- servidor del export -----------------------------------------------------------------
    console.log("\n[3/5] Servidor del export…");
    const confProd = JSON.parse(fs.readFileSync(path.join(REPO, "frontend", "src-tauri", "tauri.conf.prod.json"), "utf8"));
    const cspProd = confProd?.app?.security?.csp;
    const indice = await http(`${origen}/index.html`);
    ok("el documento lleva la CSP de producción tal cual", indice.headers["content-security-policy"] === cspProd);
    ok("el shim es el primer hijo de <head>", /<head[^>]*><script src="\/__sandbox_tauri_shim\.js"><\/script>/.test(indice.body));
    ok("sin caché: un rebuild se ve al recargar", indice.headers["cache-control"] === "no-store");
    ok("Host ajeno: 421", (await http(`${origen}/index.html`, { host: "evil.example" })).status === 421);
    const redir = await http(`${origen}/index.html`, { host: `127.0.0.1:${puertos.front}` });
    ok("127.0.0.1 redirige a localhost", redir.status === 308 && redir.headers.location === `${origen}/index.html`, `${redir.status} ${redir.headers.location}`);
    ok("shim con Sec-Fetch-Site cross-site: 403", (await http(`${origen}/__sandbox_tauri_shim.js`, { headers: { "Sec-Fetch-Site": "cross-site" } })).status === 403);
    const trav = await http(`${origen}/..%2f..%2fpackage.json`);
    ok("`..%2f` no sale de la raíz del export", trav.status !== 200 || !/"name"\s*:/.test(trav.body), `status ${trav.status}`);
    const invocar = async (cmd, args) => JSON.parse((await http(`${origen}/__sandbox/invoke`, { method: "POST", body: JSON.stringify({ cmd, args }) })).body);
    const padre = (await invocar("case_pick_parent_directory", {})).resultado;
    const creado = await invocar("case_create", { token: padre?.token, folderName: "Autotest HTTP", name: "Autotest HTTP", studyKind: "review-pose", ownerUserId: "autotest" });
    ok("invoke: case_create crea el caso en la cápsula", !!creado.resultado && creado.resultado.path.startsWith(c.casos), JSON.stringify(creado).slice(0, 160));
    ok("invoke: un comando sin emular se declara", (await invocar("download_model", {})).noSimulado === true);

    // --- navegador -----------------------------------------------------------------------------
    console.log("\n[4/5] Navegador (la app de verdad, con el shim y la CSP)…");
    let chromium = null;
    try {
      chromium = createRequire(path.join(rt, "frontend", "package.json"))("playwright").chromium;
    } catch {
      comprobar("playwright disponible", "NO EJECUTADO", `no se resuelve desde ${rt}\\frontend`);
    }
    if (chromium) {
      let navegador = null;
      for (const canal of ["chrome", "msedge"]) {
        try { navegador = await chromium.launch({ channel: canal }); break; } catch { /* siguiente */ }
      }
      if (!navegador) {
        comprobar("hay Chrome o Edge para Playwright", "NO EJECUTADO", "ninguno de los dos se pudo lanzar");
      } else {
        try {
          const pagina = await (await navegador.newContext({ viewport: { width: 1400, height: 900 } })).newPage();
          const csp = [];
          const remotas = [];
          const logins = [];
          pagina.on("console", (m) => { if (/Content Security Policy/i.test(m.text())) csp.push(m.text().slice(0, 160)); });
          pagina.on("request", (r) => { const u = r.url(); if (/^https?:\/\//.test(u) && !/^https?:\/\/(localhost|127\.0\.0\.1)[:/]/.test(u)) remotas.push(u.slice(0, 100)); });
          pagina.on("response", (r) => { if (r.url().includes("/auth/desktop-login")) logins.push(r.status()); });
          await pagina.goto(`${origen}/evaluation`, { waitUntil: "networkidle", timeout: 90000 });
          await pagina.waitForTimeout(2500);
          ok("la app obtiene su puerto del shim", await pagina.evaluate(async () => (await window.__TAURI__.core.invoke("ensure_backend"))?.port) === puertos.back);
          ok("la app inicia sesión de escritorio (200)", logins.includes(200), JSON.stringify(logins));
          ok("ninguna violación de CSP", csp.length === 0, csp.join(" | "));
          ok("ninguna petición a un origen remoto", remotas.length === 0, remotas.slice(0, 3).join(" | "));
          ok("la app usa el repositorio de Tauri (el de producción)", (await pagina.locator("text=/carpeta en este equipo/i").count()) > 0);
          const sinEmular = await pagina.evaluate(() => window.__SANDBOX_NO_SIMULADO__);
          ok("al cargar /evaluation no se pide ningún comando sin emular", sinEmular.length === 0, JSON.stringify(sinEmular));

          // Crear un caso por la interfaz: el detector de deriva del manifiesto emulado.
          await pagina.getByRole("button", { name: "Crear un caso" }).first().click({ timeout: 15000 });
          await pagina.getByPlaceholder(/Serie de inhibidores/).fill("Autotest interfaz");
          await pagina.getByRole("button", { name: /Elegir carpeta/ }).click();
          await pagina.locator('button[type="submit"]', { hasText: "Crear un caso" }).click();
          // El texto de ayuda del diálogo («La carpeta se llamará Autotest interfaz») también casa con el
          // nombre: se espera a que el diálogo se CIERRE y al archivo, no al primer texto que coincida.
          await pagina.getByText(/La carpeta se llamará/).waitFor({ state: "detached", timeout: 15000 });
          const manifiestoEnDisco = path.join(c.casos, "Autotest interfaz", "case.json");
          for (let i = 0; i < 30 && !fs.existsSync(manifiestoEnDisco); i++) await new Promise((r) => setTimeout(r, 500));
          ok("el caso creado por la interfaz existe en disco y el frontend lo aceptó", fs.existsSync(manifiestoEnDisco), `no existe ${manifiestoEnDisco}`);
          if (fs.existsSync(manifiestoEnDisco)) {
            const m = JSON.parse(fs.readFileSync(manifiestoEnDisco, "utf8"));
            ok("...con el esquema que declara cases.rs", Number.isInteger(m.schemaVersion) && m.name === "Autotest interfaz");
          }
          // Recargar: el registro persiste y la lista vuelve a mostrar el caso.
          await pagina.reload({ waitUntil: "networkidle" });
          await pagina.waitForTimeout(1500);
          ok("tras recargar el caso sigue en la lista", (await pagina.getByText("Autotest interfaz").count()) > 0);
        } catch (e) {
          comprobar("la comprobación con navegador termina", "FALLA", String(e.message).split("\n")[0]);
        } finally {
          await navegador.close();
        }
      }
    }
  } finally {
    // --- apagar y aislamiento -----------------------------------------------------------------
    console.log("\n[5/5] Apagado y aislamiento…");
    if (levantada) {
      try { sandboxUp("--agente", String(AGENTE), "--capsula", capsula, "--down"); } catch (e) { comprobar("--down", "FALLA", String(e.message).split("\n")[0]); }
      await new Promise((r) => setTimeout(r, 1500));
      ok("tras --down los dos puertos quedan libres", !(await puertoOcupado(puertos.back)) && !(await puertoOcupado(puertos.front)));
      ok("el backend escribió su base en la CÁPSULA (control positivo de la foto)", fs.existsSync(path.join(c.data, "moldesign_local.db")));
      const hayEnv = fs.existsSync(path.join(REPO, "backend", ".env"));
      if (hayEnv) comprobar("el backend creó su clave en el perfil de la cápsula", "NO EJECUTADO", "backend/.env existe y aporta SECRET_KEY: sólo se ejerce desde un worktree");
      else ok("el backend creó su clave en el perfil de la cápsula", fs.existsSync(path.join(c.home, ".moldesign", "secret_key")));
    }
    for (const d of vigilados) {
      const dif = diferencias(antes.get(d), instantanea(d));
      ok(`el perfil real no cambió: ${path.relative(home, d)}`, !hayDiferencias(dif),
        `nuevos=${dif.nuevos.slice(0, 3)} cambiados=${dif.cambiados.slice(0, 3)} borrados=${dif.borrados.slice(0, 3)} (¿actividad ajena durante la prueba?)`);
    }
    const veredicto = esCapsulaBorrable(capsula, { protegidas: [REPO, rt], noContener: [home] });
    if (veredicto.ok) fs.rmSync(capsula, { recursive: true, force: true });
    else console.log(`  (no se borra ${capsula}: ${veredicto.motivo})`);
  }
}

await main();
const fallas = resultados.filter((r) => r.estado === "FALLA").length;
const noEjecutadas = resultados.filter((r) => r.estado === "NO EJECUTADO").length;
console.log("\n" + "=".repeat(72));
console.log(`${resultados.length - fallas - noEjecutadas} OK · ${fallas} FALLA · ${noEjecutadas} NO EJECUTADO`);
for (const r of resultados.filter((x) => x.estado === "NO EJECUTADO")) console.log(`  no ejecutado: ${r.nombre} — ${r.detalle}`);
console.log("=".repeat(72));
process.exit(fallas > 0 || (estricto && noEjecutadas > 0) ? 1 : 0);
