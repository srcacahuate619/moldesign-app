/**
 * Mide la pestaña Evaluación en el export real: carga, visores, procesador en reposo y una evaluación entera.
 *
 * Existe para que las cifras que citan `Web3DViewer.tsx`, `lib/webgl.ts` y `globals.css` se puedan volver a medir. Corre
 * contra una cápsula de QA (backend real, export estático, Vina real) con el motor de WebView2 (Edge), con y sin GPU:
 *
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 4
 *   cd frontend && node scripts/medir-evaluacion.mjs sin-gpu --app http://localhost:13014 --salida <carpeta>
 *
 * Modos:
 *   gpu        el equipo tal cual
 *   sin-gpu    `--disable-gpu`: WebGL por software (SwiftShader), como una máquina virtual sin GPU virtualizada
 *   sin-webgl  además `--disable-software-rasterizer`: ningún contexto WebGL, como cuando el proceso de GPU cae varias veces
 *
 * Opciones: `--ligando <SMILES>` (el acoplamiento se guarda en caché: para medir una corrida de verdad hay que cambiar de
 * molécula en cada pasada), `--sin-evaluar`, `--perfil` (perfil de CPU del hilo principal durante la evaluación).
 *
 * Qué mide y qué no: el procesador es el de los procesos del navegador (página, GPU, navegador), leído por CDP, en % de UN
 * núcleo. Es Edge, no la ventana de Tauri; `--disable-gpu` aproxima un equipo sin GPU, no lo sustituye.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const args = process.argv.slice(2);
const valor = (nombre, defecto) => (args.includes(nombre) ? args[args.indexOf(nombre) + 1] : defecto);
const MODOS = {
  "gpu": [],
  "sin-gpu": ["--disable-gpu", "--enable-unsafe-swiftshader"],
  "sin-webgl": ["--disable-gpu", "--disable-software-rasterizer", "--enable-unsafe-swiftshader"],
};
const modo = args[0];
if (!MODOS[modo]) { console.error("Uso: node scripts/medir-evaluacion.mjs <gpu|sin-gpu|sin-webgl> [--app URL] [--salida DIR] [--ligando SMILES] [--sin-evaluar] [--perfil]"); process.exit(2); }
const APP = valor("--app", "http://localhost:13014");
const SALIDA = path.resolve(valor("--salida", path.join("medidas-evaluacion", modo)));
const RECEPTOR = valor("--receptor", "8HFI");
const LIGANDO = valor("--ligando", "CNCCCN1c2ccccc2CCc2ccccc21"); // desipramina, el ligando del cristal de 8HFI
const SIN_EVALUAR = args.includes("--sin-evaluar");
const PERFIL = args.includes("--perfil");
fs.mkdirSync(SALIDA, { recursive: true });

const r = { modo, banderas: MODOS[modo], receptor: RECEPTOR, ligando: LIGANDO, pasos: {}, errores: [], consola: [] };
const ms = (t0) => Math.round(performance.now() - t0);

const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : undefined, headless: true, args: MODOS[modo] });
const contexto = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "es-ES" });
const page = await contexto.newPage();
page.setDefaultTimeout(60_000);
page.on("pageerror", (e) => r.errores.push(String(e.message).slice(0, 300)));
page.on("console", (m) => { if (m.type() === "error") r.consola.push(m.text().slice(0, 240)); });
const cdpNavegador = await browser.newBrowserCDPSession();
const cdpPagina = await contexto.newCDPSession(page);
await cdpPagina.send("Performance.enable");

/** CPU acumulada (s) y memoria privada (MB) por tipo de proceso del navegador. */
async function procesos() {
  const { processInfo } = await cdpNavegador.send("SystemInfo.getProcessInfo");
  const memoria = {};
  if (process.platform === "win32") {
    try {
      const salida = execFileSync("powershell", ["-NoProfile", "-Command",
        `Get-Process -Id ${processInfo.map((p) => p.id).join(",")} -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Id) $([math]::Round($_.PrivateMemorySize64/1MB))" }`], { encoding: "utf8" });
      for (const linea of salida.trim().split(/\r?\n/)) { const [id, mb] = linea.trim().split(" "); memoria[id] = Number(mb); }
    } catch { /* sin memoria: la CPU se mide igual */ }
  }
  const porTipo = {};
  for (const p of processInfo) {
    const t = porTipo[p.type] ??= { cpu: 0, mb: 0 };
    t.cpu += p.cpuTime; t.mb += memoria[p.id] ?? 0;
  }
  return porTipo;
}
/** Procesador gastado durante `seg` segundos sin tocar nada, en % de UN núcleo, por tipo de proceso. */
async function reposo(nombre, seg = 10) {
  const a = await procesos();
  await page.waitForTimeout(seg * 1000);
  const b = await procesos();
  const out = { segundos: seg };
  for (const tipo of ["renderer", "GPU", "browser"]) {
    if (b[tipo]) out[tipo] = { cpu_pct: +(((b[tipo].cpu - (a[tipo]?.cpu ?? 0)) / seg) * 100).toFixed(1), mb: b[tipo].mb };
  }
  r.pasos[nombre] = out;
  console.log(nombre, JSON.stringify(out));
}
const foto = (n) => page.screenshot({ path: path.join(SALIDA, `${n}.png`) }).catch(() => {});
const estadoDelVisor = () => page.evaluate(() => ({
  molstar: !!document.querySelector(".msp-viewport canvas"),
  web3d: document.querySelector("canvas[data-engine]")?.getAttribute("data-engine") ?? null,
  simplificada: !!document.querySelector('[data-testid="visor-sin-webgl"] canvas'),
  dibujo: document.documentElement.dataset.dibujo ?? null,
  scriptDeMolstar: !!document.getElementById("molstar-js"),
}));

try {
  // 1. Arranque de la pestaña.
  let t0 = performance.now();
  await page.goto(`${APP}/evaluation`);
  const crear = page.getByRole("button", { name: "Crear un caso", exact: true });
  await crear.waitFor();
  r.pasos.arranque_ms = ms(t0);

  // 2. Caso nuevo: el editor 2D.
  await crear.click();
  await page.locator("#case-name").fill(`Medida ${modo} ${Date.now() % 100000}`);
  t0 = performance.now();
  await page.getByRole("dialog").getByRole("button", { name: "Crear un caso", exact: true }).click();
  await page.locator('[data-testid="editor-del-caso"]').waitFor();
  await page.waitForFunction(() => !!document.querySelector('[data-testid="editor-del-caso"] [class*="Ketcher"]'), null, { timeout: 120_000 })
    .then(() => { r.pasos.editor_listo_ms = ms(t0); }).catch(() => { r.pasos.editor_listo_ms = null; });

  // 3. Receptor: el visor 3D.
  await page.getByRole("button", { name: /Elige receptor/i }).first().click();
  await page.getByPlaceholder("Buscar por PDB ID, nombre de la proteína, o familia...").fill(RECEPTOR);
  t0 = performance.now();
  await page.getByText(RECEPTOR, { exact: true }).first().click();
  await page.getByText(`Receptor elegido: ${RECEPTOR}`, { exact: true }).first().waitFor({ timeout: 120_000 });
  await page.waitForFunction(() => {
    const molstar = document.querySelector(".msp-viewport canvas");
    if (molstar) return !molstar.closest(".isolate")?.querySelector(".animate-spin");
    return !!document.querySelector('[data-testid="visor-sin-webgl"] canvas');
  }, null, { timeout: 120_000 }).then(() => { r.pasos.visor_con_receptor_ms = ms(t0); }).catch(() => { r.pasos.visor_con_receptor_ms = null; });
  await page.waitForTimeout(1500);
  r.pasos.visor = await estadoDelVisor();
  r.pasos.javascript_cargado = await page.evaluate(() => {
    const js = performance.getEntriesByType("resource").filter((e) => /\.js(\?|$)/.test(e.name));
    const mayores = [...js].sort((a, b) => (b.decodedBodySize || 0) - (a.decodedBodySize || 0)).slice(0, 6)
      .map((e) => ({ archivo: e.name.split("/").pop().slice(0, 40), mb: +((e.decodedBodySize || 0) / 1048576).toFixed(2) }));
    return { archivos: js.length, mb: +(js.reduce((s, e) => s + (e.decodedBodySize || 0), 0) / 1048576).toFixed(2), mayores };
  });
  await foto("1-receptor");

  const campo = page.locator('input[id$="-smiles"]').first();
  await campo.fill(LIGANDO);
  await campo.press("Enter");
  await page.waitForTimeout(1500);

  // 4. Procesador en reposo con cada visor.
  await reposo("reposo_visor_inicial");
  if (modo !== "sin-webgl") {
    const aWeb3d = page.getByRole("button", { name: /Web3D/ }).last();
    if (await aWeb3d.count()) {
      await aWeb3d.click();
      await page.waitForSelector("canvas[data-engine]", { timeout: 30_000 }).catch(() => {});
      await page.waitForTimeout(6000); // que pase la inercia del primer encuadre
      await foto("2-web3d");
      await reposo("reposo_web3d");
      const aMolstar = page.getByRole("button", { name: /MolStar/ }).last();
      if (await aMolstar.count()) { await aMolstar.click(); await page.waitForTimeout(2500); }
    }
  }

  // 5. Una evaluación entera.
  if (!SIN_EVALUAR) {
    let flujo = null;
    page.on("response", (resp) => { if (resp.url().includes("/evaluation/stream/")) flujo = resp; });
    if (PERFIL) { await cdpPagina.send("Profiler.enable"); await cdpPagina.send("Profiler.start"); }
    const ejecutar = page.getByRole("button", { name: "Ejecutar evaluación", exact: true }).first();
    await ejecutar.scrollIntoViewIfNeeded();
    t0 = performance.now();
    await ejecutar.click();
    const guardar = page.getByRole("button", { name: "Guardar en MolDex", exact: true }).first();
    // La pantalla «evaluando», ya estable: doce segundos a partir del tercero. Sólo cuenta si la corrida dura tanto
    // (una molécula ya acoplada sale de la caché en unos segundos).
    await page.waitForTimeout(3000);
    const a = await procesos();
    await page.waitForTimeout(12_000);
    const b = await procesos();
    if (await page.locator('[data-testid="orbe-evaluacion"]').count()) {
      const evaluando = {};
      for (const tipo of ["renderer", "GPU", "browser"]) evaluando[tipo] = +(((b[tipo].cpu - a[tipo].cpu) / 12) * 100).toFixed(1);
      r.pasos.pantalla_evaluando_cpu_pct = { ...evaluando, total: +(evaluando.renderer + evaluando.GPU + evaluando.browser).toFixed(1) };
    }
    await guardar.waitFor({ timeout: 20 * 60_000 });
    r.pasos.evaluacion = { total_ms: ms(t0) };
    if (PERFIL) {
      const { profile } = await cdpPagina.send("Profiler.stop");
      const porNodo = new Map();
      profile.samples.forEach((id, i) => porNodo.set(id, (porNodo.get(id) ?? 0) + (profile.timeDeltas[i] ?? 0)));
      const porFuncion = new Map();
      for (const n of profile.nodes) {
        const us = porNodo.get(n.id) ?? 0;
        if (!us) continue;
        const clave = `${n.callFrame.functionName || "(anónima)"} @ ${(n.callFrame.url.split("/").pop() || "").slice(0, 34)}`;
        porFuncion.set(clave, (porFuncion.get(clave) ?? 0) + us);
      }
      r.pasos.perfil = [...porFuncion.entries()].sort((x, y) => y[1] - x[1]).slice(0, 20).map(([clave, us]) => `${(us / 1000).toFixed(0)} ms  ${clave}`);
    }
    if (flujo) {
      const eventos = (await flujo.text().catch(() => "")).split(/\r?\n\r?\n/).map((f) => f.replace(/^data:\s*/, "")).filter(Boolean)
        .map((f) => { try { return JSON.parse(f); } catch { return null; } }).filter(Boolean);
      const etapas = eventos.filter((e) => e.type === "stage_done").map((e) => ({ etapa: e.stage_id, ms: e.duration_ms ?? null }));
      const inicio = eventos.find((e) => e.type === "pipeline_started");
      const fin = eventos.find((e) => e.type === "pipeline_done" || e.type === "pipeline_error");
      const enEtapas = etapas.reduce((s, e) => s + (e.ms ?? 0), 0);
      const pipeline = inicio && fin ? new Date(fin.timestamp) - new Date(inicio.timestamp) : null;
      // Lo que el backend hace después de la última etapa (validación física de las poses, selección de pose, guardar)
      // no emite ningún evento: es la diferencia.
      Object.assign(r.pasos.evaluacion, { pipeline_ms: pipeline, etapas, fuera_de_las_etapas_ms: pipeline === null ? null : pipeline - enEtapas });
    }
    console.log("evaluacion", JSON.stringify(r.pasos.evaluacion));
    await page.waitForTimeout(4000);
    await page.evaluate(() => window.scrollTo(0, 0));
    await foto("3-resultado");
    await reposo("reposo_con_resultado");
  }
} catch (e) {
  r.errores.push(`GUION: ${String(e?.message ?? e).slice(0, 500)}`);
  await foto("error");
} finally {
  fs.writeFileSync(path.join(SALIDA, "medida.json"), JSON.stringify(r, null, 1));
  console.log(JSON.stringify(r, null, 1));
  await browser.close();
}
