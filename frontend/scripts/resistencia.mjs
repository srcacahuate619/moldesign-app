/**
 * Prueba de resistencia: lo que le pasa a la aplicación con el tiempo, no en un instante.
 *
 * POR QUÉ EXISTE. Los tres fallos graves de la interfaz fueron de comportamiento en el tiempo y los encontró alguien
 * midiendo a mano, con todas las pruebas en verde: el sondeo a Ketcher que tumbó la VM a la hora (+200 MB/min en
 * reposo), Web3D gastando entre 9 y 11 núcleos con la escena quieta y la retención de ~21 MB por cada cambio de caso
 * (2026-11-10). Ninguna prueba mira la memoria o el procesador al cabo de minutos. Ésta sí, y falla si se pasan de un
 * presupuesto.
 *
 * QUÉ HACE, en este orden:
 *   1. crea dos casos (8HFI y 1RKP) y evalúa unos cuantos ligandos en el primero;
 *   2. cambia de caso N veces (30 por defecto) y mide, tras recoger la basura, cuánto queda retenido por cambio;
 *   3. alterna Mol* y el visor ligero unas cuantas veces (crear y destruir sigue existiendo ahí);
 *   4. deja la aplicación quieta: Mol* con un resultado, el visor ligero y otra pestaña con Evaluación oculta.
 *
 * DÓNDE CORRE. Contra el export servido por una cápsula de QA, con Edge (el Chromium de WebView2):
 *
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 4
 *   cd frontend && node scripts/resistencia.mjs --app http://localhost:13014
 *
 * o contra la ventana de verdad, conectándose por depuración remota a su WebView2. Lanzando el binario con un perfil
 * de prueba que no toca el del usuario (ver `MOLDESIGN_PERFIL_DE_PRUEBA` en `src-tauri/src/perfil_de_prueba.rs`):
 *
 *   node scripts/resistencia.mjs --binario src-tauri/target/release/moldesign.exe
 *
 * (el de depuración, `target/debug/moldesign.exe`, carga la interfaz de `http://localhost:3000`: hace falta `npm run dev`
 * en marcha, y mide `next dev`, no el export),
 *
 * o a una ventana ya abierta con `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222`:
 *
 *   node scripts/resistencia.mjs --cdp http://127.0.0.1:9222
 *
 * `--autotest` demuestra que el guardián ve (restricción 2 del AGENTS.md): una pasada corta sin trampas debe pasar, y
 * otra con una fuga, un worker cargado y un consumo plantados debe fallar por los tres. Termina con código 1 si no es así.
 *
 * Opciones: --cambios N (30), --evaluaciones N (3), --reposo-mol N, --reposo-web3d N, --reposo-oculta N (minutos: 4, 3
 * y 3), --sin-gpu (sólo con --app), --salida DIR, --corta (6 cambios, 1 evaluación, 20 s por reposo).
 *
 * Qué mide: memoria privada del proceso de la página (no `usedJSHeapSize`: la fuga de Ketcher vivía fuera del montón de
 * JS), montón de JS y nodos del DOM tras forzar la recogida de basura, oyentes de eventos vivos, visores de Mol* y
 * contextos WebGL creados, y procesador de los procesos del navegador en % de UN núcleo. Con la ventana tapada o
 * minimizada Chromium puede dejar de dibujar y el reposo saldría mejor de lo que es: la ventana tiene que estar visible.
 */
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const args = process.argv.slice(2);
const valor = (nombre, defecto) => (args.includes(nombre) ? args[args.indexOf(nombre) + 1] : defecto);
const tiene = (nombre) => args.includes(nombre);

/**
 * EL PRESUPUESTO. Cada cifra sale de medir la aplicación arreglada (ver `docs/auditorias/resistencia-2026-11-10.md`),
 * con margen, y cada una habría saltado con uno de los fallos que motivan este guion.
 */
export const PRESUPUESTO = {
  /**
   * MB de memoria privada de la página retenidos por cambio de caso tras recoger la basura (pendiente de la recta).
   * Antes: ~21 (la pantalla del caso) y luego 5–8 (el worker de Indigo). Es la medida que ve lo que no es JavaScript,
   * pero oscila ±25 MB entre muestras, y el propio instrumento le suma: Playwright activa el dominio Network de
   * DevTools, que guarda el cuerpo de cada respuesta (medido: +1,4 MB/cambio con Playwright, −0,8 sin depurador). Las
   * deterministas son las de abajo.
   */
  retenidoPorCambioMb: 4,
  /** MB del montón de JavaScript retenidos por cambio de caso tras recoger la basura. Medido después: 0,26. */
  montonPorCambioMb: 2,
  /** Nodos del DOM que quedan vivos por cambio de caso (pendiente). Un caso entero son miles. */
  nodosPorCambio: 150,
  /** Oyentes de eventos que quedan vivos por cambio de caso (pendiente). Antes: 4 de Ketcher por cambio. */
  oyentesPorCambio: 1,
  /** MB enviados a los workers por cambio de caso. El de Indigo los retiene. Antes del arreglo: 5,2–6,6. */
  mbAlWorkerPorCambio: 1,
  /** Visores de Mol* creados durante los cambios de caso. Antes: uno por cambio. */
  visoresMolstarEnLosCambios: 0,
  /** Procesador en reposo, en % de un núcleo, sumando página, GPU y navegador, en cualquiera de los tres reposos. */
  reposoCpuPct: 12,
  /** Crecimiento de la memoria privada de la página en reposo, MB por minuto. Ketcher sondeado: ~200. */
  reposoMbPorMinuto: 3,
};

const CORTA = tiene("--corta") || tiene("--autotest");
const CAMBIOS = Number(valor("--cambios", CORTA ? 8 : 30));
const EVALUACIONES = Number(valor("--evaluaciones", CORTA ? 0 : 3));
const REPOSOS = {
  molstar: Number(valor("--reposo-mol", CORTA ? 1 / 3 : 4)),
  web3d: Number(valor("--reposo-web3d", CORTA ? 1 / 3 : 3)),
  oculta: Number(valor("--reposo-oculta", CORTA ? 1 / 3 : 3)),
};
const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SALIDA = path.resolve(valor("--salida", path.join(RAIZ, "medidas-resistencia", new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-"))));
const LIGANDOS = [
  "CNCCCN1c2ccccc2CCc2ccccc21",       // desipramina, el ligando del cristal de 8HFI
  "CN(C)CCCN1c2ccccc2CCc2ccccc21",    // imipramina
  "CNCCC=C1c2ccccc2CCc2ccccc21",      // nortriptilina
  "CN(C)CCC=C1c2ccccc2CCc2ccccc21",   // amitriptilina
];
const ms = (t0) => Math.round(performance.now() - t0);

// ── Lo que se inyecta en la página antes de que cargue ───────────────────────────────────────────────────────────
// Cuenta visores de Mol* y contextos WebGL. No cambia nada de lo que hace la aplicación.
const CONTADORES = `(() => {
  if (window.__resistencia) return;
  const m = window.__resistencia = { molstar: 0, webgl: 0, mbAlWorker: 0 };
  // Lo que se envía a los workers. El de Indigo se queda con todo lo que recibe (no libera sus mapas de opciones):
  // contarlo ve esa fuga sin depender de la memoria privada, que oscila.
  const enviar = Worker.prototype.postMessage;
  Worker.prototype.postMessage = function (msg, ...resto) {
    try { m.mbAlWorker += JSON.stringify(msg).length / 1048576; } catch { /* no serializable */ }
    return enviar.call(this, msg, ...resto);
  };
  let real;
  Object.defineProperty(window, "molstar", {
    configurable: true,
    get() { return real; },
    set(v) {
      real = v;
      const crear = v && v.Viewer && v.Viewer.create;
      if (!crear || crear.__contado) return;
      const envuelto = async function (...a) { const r = await crear.apply(this, a); m.molstar++; return r; };
      envuelto.__contado = true;
      v.Viewer.create = envuelto;
    },
  });
  const vistos = new WeakSet();
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (tipo, ...resto) {
    const ctx = getContext.call(this, tipo, ...resto);
    if (ctx && /webgl/.test(String(tipo)) && !vistos.has(this)) { vistos.add(this); m.webgl++; }
    return ctx;
  };
})();`;

// Las trampas del autotest: una fuga de ~16 MB por clic, 2 MB por clic a un worker y un bucle que gasta media CPU cuando
// la página está quieta.
const TRAMPAS = `(() => {
  const retenido = window.__fugaPlantada = [];
  // ~16 MB de números de JavaScript por clic: los ven el montón y la memoria privada.
  document.addEventListener("click", () => { retenido.push(new Array(2_000_000).fill(Math.random())); }, true);
  // Y 2 MB por clic a un worker, como hacía Ketcher con el de Indigo.
  const sumidero = new Worker(URL.createObjectURL(new Blob(["onmessage = () => {};"], { type: "text/javascript" })));
  document.addEventListener("click", () => { sumidero.postMessage({ relleno: "x".repeat(2_000_000) }); }, true);
  let ultimo = performance.now();
  document.addEventListener("pointermove", () => { ultimo = performance.now(); }, true);
  setInterval(() => {
    if (performance.now() - ultimo < 2000) return;
    const fin = performance.now() + 30;
    while (performance.now() < fin) { /* gasta */ }
  }, 50);
})();`;

// ── Conexión ─────────────────────────────────────────────────────────────────────────────────────────────────────
async function conectar({ app, cdp, binario, sinGpu, conTrampas }) {
  let browser, proceso = null, perfil = null, origen;
  if (binario) {
    perfil = fs.mkdtempSync(path.join(os.tmpdir(), "moldesign-resistencia-"));
    const puerto = 9300 + Math.floor(Math.random() * 400);
    proceso = spawn(path.resolve(binario), [], {
      env: {
        ...process.env,
        MOLDESIGN_PERFIL_DE_PRUEBA: perfil,
        WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${puerto}`,
      },
      stdio: "ignore",
    });
    cdp = `http://127.0.0.1:${puerto}`;
    const limite = Date.now() + 120_000;
    for (;;) {
      try { const r = await fetch(`${cdp}/json/version`); if (r.ok) break; } catch { /* aún no */ }
      if (Date.now() > limite) throw new Error(`la ventana no abrió la depuración remota en ${cdp} en 2 min`);
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  if (cdp) {
    browser = await chromium.connectOverCDP(cdp);
    const contexto = browser.contexts()[0];
    let page = contexto.pages().find((p) => !p.url().startsWith("devtools:"));
    const limite = Date.now() + 60_000;
    while (!page && Date.now() < limite) { await new Promise((r) => setTimeout(r, 500)); page = contexto.pages()[0]; }
    if (!page) throw new Error("no hay ninguna página en la ventana");
    // Recién abierta, la ventana está en `about:blank` hasta que Tauri le carga la interfaz.
    while (!/^https?:/.test(page.url()) && Date.now() < limite + 60_000) await new Promise((r) => setTimeout(r, 500));
    if (!/^https?:/.test(page.url())) throw new Error(`la ventana no cargó la interfaz (sigue en ${page.url()})`);
    origen = new URL(page.url()).origin;
    // Se aplican en la siguiente carga, que es la de `irAEvaluacion`.
    await page.addInitScript(CONTADORES);
    if (conTrampas) await page.addInitScript(TRAMPAS);
    return { browser, contexto, page, origen, proceso, perfil, modo: binario ? "binario" : "cdp" };
  }
  browser = await chromium.launch({
    channel: process.platform === "win32" ? "msedge" : undefined,
    headless: true,
    args: sinGpu ? ["--disable-gpu", "--enable-unsafe-swiftshader"] : [],
  });
  const contexto = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "es-ES" });
  const page = await contexto.newPage();
  await page.addInitScript(CONTADORES);
  if (conTrampas) await page.addInitScript(TRAMPAS);
  return { browser, contexto, page, origen: app, proceso: null, perfil: null, modo: sinGpu ? "export-sin-gpu" : "export" };
}

/**
 * Cierra la aplicación como lo haría el usuario: un cierre de ventana, que Tauri recibe y con el que apaga su backend.
 * Matarla a la fuerza dejaría el proceso de Python vivo y con el puerto ocupado. Si en 30 s no ha salido, se mata el
 * árbol entero.
 */
async function cerrarElBinario(proceso) {
  if (proceso.exitCode !== null) return;
  const salio = new Promise((ok) => proceso.once("exit", ok));
  const espera = (ms) => new Promise((ok) => setTimeout(ok, ms));
  if (process.platform === "win32") {
    try { execFileSync("taskkill", ["/PID", String(proceso.pid)], { stdio: "ignore" }); } catch { /* ya no estaba */ }
    if (await Promise.race([salio.then(() => true), espera(30_000).then(() => false)])) return;
    try { execFileSync("taskkill", ["/F", "/T", "/PID", String(proceso.pid)], { stdio: "ignore" }); } catch { /* ya no estaba */ }
  } else {
    proceso.kill("SIGTERM");
    if (await Promise.race([salio.then(() => true), espera(30_000).then(() => false)])) return;
    proceso.kill("SIGKILL");
  }
}

// ── Medidas ──────────────────────────────────────────────────────────────────────────────────────────────────────
function memoriaPrivadaMb(pids) {
  if (process.platform !== "win32" || pids.length === 0) return {};
  try {
    const salida = execFileSync("powershell", ["-NoProfile", "-Command",
      `Get-Process -Id ${pids.join(",")} -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Id) $([math]::Round($_.PrivateMemorySize64/1MB))" }`], { encoding: "utf8" });
    return Object.fromEntries(salida.trim().split(/\r?\n/).filter(Boolean).map((l) => l.trim().split(" ").map(Number)));
  } catch { return {}; }
}

function medidor(browser, contexto, page) {
  let cdpNavegador = null, cdpPagina = null;
  const sesiones = async () => {
    cdpNavegador ??= await browser.newBrowserCDPSession();
    cdpPagina ??= await contexto.newCDPSession(page);
    return { cdpNavegador, cdpPagina };
  };
  /** CPU acumulada (s) por tipo de proceso y memoria privada de la página (el renderer mayor). */
  const procesos = async () => {
    const { cdpNavegador } = await sesiones();
    const { processInfo } = await cdpNavegador.send("SystemInfo.getProcessInfo");
    const mb = memoriaPrivadaMb(processInfo.map((p) => p.id));
    const cpu = {};
    let pagina = 0;
    for (const p of processInfo) {
      cpu[p.type] = (cpu[p.type] ?? 0) + p.cpuTime;
      if (p.type === "renderer") pagina = Math.max(pagina, mb[p.id] ?? 0);
    }
    return { cpu, paginaMb: pagina };
  };
  /** Lo que queda vivo de verdad: se recoge la basura dos veces y se mira el montón, el DOM y los oyentes. */
  const retenido = async () => {
    const { cdpPagina } = await sesiones();
    for (let i = 0; i < 2; i++) { await cdpPagina.send("HeapProfiler.collectGarbage"); await page.waitForTimeout(800); }
    const { usedSize } = await cdpPagina.send("Runtime.getHeapUsage");
    const dom = await cdpPagina.send("Memory.getDOMCounters");
    const { paginaMb } = await procesos();
    const contadores = await page.evaluate(() => ({ ...(window.__resistencia ?? {}) }));
    return { paginaMb, montonMb: +(usedSize / 1048576).toFixed(1), nodos: dom.nodes, oyentes: dom.jsEventListeners, documentos: dom.documents, ...contadores };
  };
  /** Procesador y memoria durante `minutos` sin tocar nada. */
  /** Memoria privada de la página tras recoger la basura: sin esto, el diente de sierra del recolector parece una fuga. */
  const memoriaTrasRecoger = async () => {
    const { cdpPagina } = await sesiones();
    for (let i = 0; i < 2; i++) { await cdpPagina.send("HeapProfiler.collectGarbage"); await page.waitForTimeout(800); }
    return (await procesos()).paginaMb;
  };
  const reposo = async (minutos) => {
    const seg = Math.max(10, Math.round(minutos * 60));
    // La recolección se fuerza fuera de la ventana en que se mide el procesador: su trabajo no cuenta como reposo.
    const mbInicio = await memoriaTrasRecoger();
    const a = await procesos();
    const muestras = [{ t: 0, mb: a.paginaMb }];
    const t0 = performance.now();
    while (performance.now() - t0 < seg * 1000) {
      await page.waitForTimeout(Math.min(15_000, seg * 1000 - (performance.now() - t0)));
      const p = await procesos();
      muestras.push({ t: (performance.now() - t0) / 60000, mb: p.paginaMb });
    }
    const b = await procesos();
    const pct = (tipo) => +((((b.cpu[tipo] ?? 0) - (a.cpu[tipo] ?? 0)) / seg) * 100).toFixed(1);
    const cpu = { pagina: pct("renderer"), gpu: pct("GPU"), navegador: pct("browser") };
    const mbFin = await memoriaTrasRecoger();
    // `memoria` es la curva sin recoger, para leerla; el veredicto usa los dos extremos recogidos. Medido el 2026-11-10:
    // con Mol* la curva sube ~12 MB/min y cae de golpe al recolectar (su bucle de dibujo genera basura en cada fotograma).
    return { segundos: seg, cpu, cpuTotalPct: +(cpu.pagina + cpu.gpu + cpu.navegador).toFixed(1), mbPorMinuto: +((mbFin - mbInicio) / (seg / 60)).toFixed(2), mbInicio, mbFin, memoria: muestras.map((m) => m.mb), pendienteSinRecoger: +pendiente(muestras.map((m) => [m.t, m.mb])).toFixed(2) };
  };
  return { retenido, reposo };
}

/** Pendiente de la recta de mínimos cuadrados. */
function pendiente(puntos) {
  const n = puntos.length;
  if (n < 2) return 0;
  const mx = puntos.reduce((s, [x]) => s + x, 0) / n, my = puntos.reduce((s, [, y]) => s + y, 0) / n;
  const sxx = puntos.reduce((s, [x]) => s + (x - mx) ** 2, 0);
  return sxx === 0 ? 0 : puntos.reduce((s, [x, y]) => s + (x - mx) * (y - my), 0) / sxx;
}

// ── La aplicación ────────────────────────────────────────────────────────────────────────────────────────────────
async function irAEvaluacion(page, origen) {
  // Con `next dev` (binario de depuración), la primera visita compila la ruta: puede tardar minutos.
  await page.goto(`${origen}/evaluation`, { waitUntil: "domcontentloaded", timeout: 300_000 });
  await page.getByRole("button", { name: /Crear un caso|Nuevo caso/ }).first().waitFor({ timeout: 120_000 });
}

async function crearCaso(page, nombre, receptor) {
  await page.getByRole("button", { name: /Crear un caso|Nuevo caso/ }).first().click();
  await page.locator("#case-name").fill(nombre);
  await page.getByRole("dialog").getByRole("button", { name: "Crear un caso", exact: true }).click();
  await page.getByRole("button", { name: /Elige receptor/i }).first().click();
  await page.getByPlaceholder("Buscar por PDB ID, nombre de la proteína, o familia...").fill(receptor);
  await page.getByText(receptor, { exact: true }).first().click({ timeout: 30_000 });
  await esperarReceptor(page, receptor);
}

async function esperarReceptor(page, receptor) {
  await page.getByText(`Receptor elegido: ${receptor}`, { exact: true }).first().waitFor({ timeout: 120_000 });
  await page.waitForFunction(() => {
    const lienzo = document.querySelector(".msp-viewport canvas, canvas[data-engine], [data-testid='visor-sin-webgl'] canvas");
    return lienzo && !lienzo.closest(".isolate")?.querySelector(".animate-spin");
  }, null, { timeout: 120_000 });
  await page.waitForTimeout(1500);
}

async function evaluar(page, smiles) {
  const campo = page.locator('input[id$="-smiles"]').first();
  await campo.fill(smiles);
  await campo.press("Enter");
  await page.waitForTimeout(1000);
  const t0 = performance.now();
  const ejecutar = page.getByRole("button", { name: "Ejecutar evaluación", exact: true }).first();
  await ejecutar.scrollIntoViewIfNeeded();
  await ejecutar.click();
  await page.getByRole("button", { name: "Guardar en MolDex", exact: true }).first().waitFor({ timeout: 20 * 60_000 });
  await page.waitForTimeout(3000);
  return ms(t0);
}

async function cambiarDeVisor(page, a) {
  const boton = page.getByRole("button", { name: a === "web3d" ? /Web3D/ : /MolStar/ }).last();
  await boton.click();
  await page.waitForSelector(a === "web3d" ? "canvas[data-engine]" : ".msp-viewport canvas", { timeout: 30_000 });
  await page.waitForTimeout(1500);
}

// ── Una pasada ───────────────────────────────────────────────────────────────────────────────────────────────────
async function pasada({ etiqueta, conTrampas, carpeta }) {
  fs.mkdirSync(carpeta, { recursive: true });
  const r = { etiqueta, modo: null, cambios: CAMBIOS, evaluaciones: [], retenido: [], visores: [], reposo: {}, errores: [], consola: [], fallos: [] };
  const app = valor("--app", null), cdp = valor("--cdp", null), binario = valor("--binario", null);
  if (!app && !cdp && !binario) { console.error("Hace falta --app URL, --cdp URL o --binario RUTA"); process.exit(2); }
  const c = await conectar({ app, cdp, binario, sinGpu: tiene("--sin-gpu"), conTrampas });
  r.modo = c.modo;
  const { page } = c;
  page.setDefaultTimeout(90_000);
  page.on("pageerror", (e) => r.errores.push(String(e.message).slice(0, 300)));
  page.on("console", (m) => { if (m.type() === "error") r.consola.push(m.text().slice(0, 240)); });
  const m = medidor(c.browser, c.contexto, page);
  const foto = (n) => page.screenshot({ path: path.join(carpeta, `${n}.png`) }).catch(() => {});
  try {
    await irAEvaluacion(page, c.origen);
    const sello = Date.now() % 100000;
    const A = `Resistencia A ${sello}`, B = `Resistencia B ${sello}`;
    await crearCaso(page, A, "8HFI");
    await crearCaso(page, B, "1RKP");
    await page.getByText(A, { exact: true }).first().click();
    await esperarReceptor(page, "8HFI");

    // 1. Evaluaciones en el caso A.
    for (let i = 0; i < EVALUACIONES; i++) {
      const smiles = LIGANDOS[i % LIGANDOS.length];
      const duracion = await evaluar(page, smiles);
      r.evaluaciones.push({ smiles, ms: duracion });
      console.log(`evaluación ${i + 1}: ${(duracion / 1000).toFixed(1)} s`);
    }
    await foto("1-evaluado");

    // 2. Cambios de caso. Los dos primeros calientan (cachés, trozos de código que cargan una vez).
    const base = await m.retenido();
    r.retenido.push({ cambio: 0, ...base });
    console.log("antes de cambiar:", JSON.stringify(base));
    for (let i = 1; i <= CAMBIOS; i++) {
      const destino = i % 2 === 1 ? B : A;
      await page.getByText(destino, { exact: true }).first().click();
      await esperarReceptor(page, destino === A ? "8HFI" : "1RKP");
      if (i % 2 === 0 || i === CAMBIOS) {
        const fila = { cambio: i, ...(await m.retenido()) };
        r.retenido.push(fila);
        console.log(`cambio ${i}:`, JSON.stringify(fila));
      }
    }
    await foto("2-cambios");
    const tras = r.retenido.filter((f) => f.cambio >= 2);
    const recta = (campo) => +pendiente(tras.map((f) => [f.cambio, f[campo]])).toFixed(2);
    r.porCambio = {
      paginaMb: recta("paginaMb"), montonMb: recta("montonMb"), nodos: recta("nodos"), oyentes: recta("oyentes"),
      visoresMolstar: (r.retenido.at(-1).molstar ?? 0) - (base.molstar ?? 0),
      mbAlWorker: +(((r.retenido.at(-1).mbAlWorker ?? 0) - (base.mbAlWorker ?? 0)) / CAMBIOS).toFixed(2),
      contextosWebgl: (r.retenido.at(-1).webgl ?? 0) - (base.webgl ?? 0),
    };
    console.log("por cambio:", JSON.stringify(r.porCambio));

    // 3. Mol* ↔ visor ligero.
    if (!CORTA) {
      for (let i = 0; i < 6; i++) { await cambiarDeVisor(page, "web3d"); await cambiarDeVisor(page, "molstar"); }
      r.visores = { tras: await m.retenido() };
      console.log("tras alternar visores:", JSON.stringify(r.visores.tras));
    }

    // 4. Reposo. Se vuelve al caso con resultado (A) y se deja quieta.
    if (CAMBIOS % 2 === 1) { await page.getByText(A, { exact: true }).first().click(); await esperarReceptor(page, "8HFI"); }
    await page.mouse.move(5, 5);
    r.reposo.molstar = await m.reposo(REPOSOS.molstar);
    console.log("reposo con Mol*:", JSON.stringify(r.reposo.molstar));
    await cambiarDeVisor(page, "web3d");
    await page.mouse.move(5, 5);
    r.reposo.web3d = await m.reposo(REPOSOS.web3d);
    console.log("reposo con el visor ligero:", JSON.stringify(r.reposo.web3d));
    await foto("3-web3d");
    // Otra pestaña: Evaluación sigue montada, oculta (keep-alive). Ahí vivía el sondeo de Ketcher.
    await page.getByRole("link", { name: /^Inicio$|^Home$/ }).first().click().catch(async () => { await page.goto(`${c.origen}/`); });
    await page.waitForTimeout(2000);
    await page.mouse.move(5, 5);
    r.reposo.oculta = await m.reposo(REPOSOS.oculta);
    console.log("reposo con Evaluación oculta:", JSON.stringify(r.reposo.oculta));
  } catch (e) {
    r.errores.push(`GUION: ${String(e?.message ?? e).slice(0, 500)}`);
    await foto("error");
  } finally {
    await c.browser.close().catch(() => {});
    if (c.proceso) await cerrarElBinario(c.proceso);
  }

  // ── El veredicto ──
  const P = PRESUPUESTO;
  const exigir = (cond, texto) => { if (!cond) r.fallos.push(texto); };
  if (r.errores.some((e) => e.startsWith("GUION"))) r.fallos.push(`el guion no terminó: ${r.errores.find((e) => e.startsWith("GUION"))}`);
  // Un guardián tiene que demostrar que ve: sin contadores, «0 visores creados» no significa nada.
  if (r.retenido.length > 0 && r.retenido.at(-1).molstar === undefined) r.fallos.push("los contadores de visores no llegaron a la página: no se puede saber cuántos Mol* se crearon");
  if (r.porCambio) {
    exigir(r.porCambio.paginaMb <= P.retenidoPorCambioMb, `memoria retenida por cambio de caso: ${r.porCambio.paginaMb} MB (presupuesto ${P.retenidoPorCambioMb})`);
    exigir(r.porCambio.montonMb <= P.montonPorCambioMb, `montón de JavaScript retenido por cambio: ${r.porCambio.montonMb} MB (presupuesto ${P.montonPorCambioMb})`);
    exigir(r.porCambio.nodos <= P.nodosPorCambio, `nodos del DOM retenidos por cambio: ${r.porCambio.nodos} (presupuesto ${P.nodosPorCambio})`);
    exigir(r.porCambio.oyentes <= P.oyentesPorCambio, `oyentes retenidos por cambio: ${r.porCambio.oyentes} (presupuesto ${P.oyentesPorCambio})`);
    exigir(r.porCambio.mbAlWorker <= P.mbAlWorkerPorCambio, `enviado a los workers por cambio de caso: ${r.porCambio.mbAlWorker} MB (presupuesto ${P.mbAlWorkerPorCambio})`);
    exigir(r.porCambio.visoresMolstar <= P.visoresMolstarEnLosCambios, `visores de Mol* creados al cambiar de caso: ${r.porCambio.visoresMolstar} (presupuesto ${P.visoresMolstarEnLosCambios})`);
  }
  for (const [fase, med] of Object.entries(r.reposo)) {
    exigir(med.cpuTotalPct <= P.reposoCpuPct, `procesador en reposo (${fase}): ${med.cpuTotalPct} % de un núcleo (presupuesto ${P.reposoCpuPct})`);
    // Con reposos cortos la pendiente es ruido: sólo cuenta a partir de 2 min.
    if (med.segundos >= 120) exigir(med.mbPorMinuto <= P.reposoMbPorMinuto, `memoria en reposo (${fase}): ${med.mbPorMinuto} MB/min (presupuesto ${P.reposoMbPorMinuto})`);
  }
  if (c.perfil) r.perfil = c.perfil;
  fs.writeFileSync(path.join(carpeta, "resistencia.json"), JSON.stringify({ presupuesto: P, ...r }, null, 1));
  return r;
}

// ── Principal ────────────────────────────────────────────────────────────────────────────────────────────────────
if (tiene("--autotest")) {
  console.log("== autotest: pasada limpia (debe pasar)");
  const limpia = await pasada({ etiqueta: "limpia", conTrampas: false, carpeta: path.join(SALIDA, "limpia") });
  console.log("== autotest: pasada con una fuga, un worker y un consumo plantados (debe fallar por los tres)");
  const trampa = await pasada({ etiqueta: "trampa", conTrampas: true, carpeta: path.join(SALIDA, "trampa") });
  // La memoria privada oscila ±25 MB y en una pasada corta puede no verla (medido: su pendiente salió negativa con la
  // fuga plantada dentro); el montón de JavaScript sí. Basta con que la vea una de las dos.
  const vioLaFuga = trampa.fallos.some((f) => f.startsWith("memoria retenida por cambio") || f.startsWith("montón de JavaScript retenido"));
  const vioElConsumo = trampa.fallos.some((f) => f.startsWith("procesador en reposo"));
  const vioElWorker = trampa.fallos.some((f) => f.startsWith("enviado a los workers"));
  const ok = limpia.fallos.length === 0 && vioLaFuga && vioElConsumo && vioElWorker;
  console.log(`\n  ${limpia.fallos.length === 0 ? "OK   " : "FALLA"} la pasada limpia pasa${limpia.fallos.length ? `: ${limpia.fallos.join("; ")}` : ""}`);
  console.log(`  ${vioLaFuga ? "OK   " : "FALLA"} ve la fuga plantada`);
  console.log(`  ${vioElConsumo ? "OK   " : "FALLA"} ve el consumo plantado`);
  console.log(`  ${vioElWorker ? "OK   " : "FALLA"} ve lo plantado en el worker`);
  console.log(`\nResultados en ${SALIDA}`);
  process.exit(ok ? 0 : 1);
} else {
  const r = await pasada({ etiqueta: "resistencia", conTrampas: false, carpeta: SALIDA });
  console.log(r.fallos.length ? `\nFALLA (${r.fallos.length}):\n  - ${r.fallos.join("\n  - ")}` : "\nOK: dentro del presupuesto");
  console.log(`Resultados en ${SALIDA}`);
  process.exit(r.fallos.length ? 1 : 0);
}
