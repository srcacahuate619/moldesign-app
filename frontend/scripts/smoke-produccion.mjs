// scripts/smoke-produccion.mjs
// =============================================================================
// Smoke test del ARTEFACTO, montando el entorno real de la aplicación instalada.
//
// POR QUE EXISTE. Las 688 pruebas del frontend y las 1308 del backend estaban
// verdes mientras la aplicación instalada tenía, a la vez:
//
//   - el botón de MolChat sin posición ni color, en el flujo del documento;
//   - Ketcher pintando un SVG diagonal que ocupaba el lienzo;
//   - el registro científico contestando «Failed to fetch»;
//   - el frontend hablando con el backend de OTRO producto en el puerto 8000;
//   - una petición a Google Fonts en cada arranque.
//
// Ninguna prueba los vio porque todas corren sobre el CODIGO. Estos cinco
// fallos sólo existen en la combinación que nadie ejercitaba: el export
// estático + la CSP de producción + el contenedor de Tauri. Tres instaladores
// costó aprenderlo.
//
// QUE MONTA. Lo más parecido a la aplicación instalada que se puede montar sin
// instalarla:
//   1. El backend con el python EMPAQUETADO, desde `src-tauri/resources`.
//   2. El export estático `out/` servido con la CSP de `tauri.conf.prod.json`.
//   3. Un `window.__TAURI__` que contesta `ensure_backend` con el puerto real.
//
// LO QUE NO CUBRE, y conviene no olvidarlo: WebView2 no es Chrome, aunque
// compartan motor; el instalador NSIS no se ejercita; y una máquina limpia
// sigue siendo la única prueba de que la instalación funciona. Esto detecta la
// clase de fallo que nos ha mordido tres veces, no todas las clases.
//
// Uso:  node scripts/smoke-produccion.mjs
// Exit: 0 = todo bien, 1 = alguna comprobación falló.
// =============================================================================

import { chromium } from "playwright";
import { createServer } from "node:http";
import { mkdtemp, readdir, readFile, rm, stat } from "node:fs/promises";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { comprobarIpcCsp } from "./smoke-ipc-csp.mjs";

const require_ = createRequire(import.meta.url);
const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(AQUI, "..");
const OUT = path.join(FRONTEND, "out");
const RECURSOS = path.join(FRONTEND, "src-tauri", "resources");

const TIPOS = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".wasm": "application/wasm",
  ".txt": "text/plain; charset=utf-8",
};

const resultados = [];
function comprobar(nombre, ok, detalle = "") {
  resultados.push({ nombre, ok, detalle });
  console.log(`  ${ok ? "OK  " : "FALLA"}  ${nombre}${detalle ? `  ->  ${detalle}` : ""}`);
}

async function puertoLibre() {
  return new Promise((res) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => {
      const p = s.address().port;
      s.close(() => res(p));
    });
  });
}

function cspDeProduccion() {
  const base = require_(path.join(FRONTEND, "src-tauri", "tauri.conf.json"));
  const prod = require_(path.join(FRONTEND, "src-tauri", "tauri.conf.prod.json"));
  return prod?.app?.security?.csp ?? base?.app?.security?.csp;
}

// --- 1. Backend, con el python empaquetado -----------------------------------
async function arrancarBackend() {
  const py = path.join(RECURSOS, "python", "python.exe");
  const backend = path.join(RECURSOS, "backend");
  try {
    await stat(py);
    await stat(path.join(backend, "api", "main.py"));
  } catch {
    return { error: `falta el runtime empaquetado en ${RECURSOS}. Corre \`npm run stage:desktop\`.` };
  }
  const puerto = await puertoLibre();
  // Los DATOS, en cambio, no pueden ser los del usuario. Sin LOCAL_DATA_DIR el
  // backend abre —y migra— `~\MolDesign\data\moldesign_local.db`, la base de
  // quien ejecuta la prueba (medido el 2026-09-23). La carpeta temporal simula
  // además lo que de verdad ve una instalación nueva: una base vacía.
  // SECRET_KEY por lo mismo: sin ella el backend lee o CREA
  // `~\.moldesign\secret_key`. Hasta `f2b6479` varios almacenes (la siembra de
  // `molgraph.db`, `limbic.json`, las cachés de IA) ignoraban LOCAL_DATA_DIR y
  // escribían en `~\MolDesign\data` igual. Desde ahí salen de
  // `core.config.directorio_de_datos()`. Pero ojo: este smoke ejecuta el
  // backend EMPAQUETADO, así que el arreglo sólo cuenta aquí cuando
  // `stage:desktop` haya vuelto a copiar el backend.
  const datos = await mkdtemp(path.join(os.tmpdir(), "moldesign-smoke-"));
  // El entorno tiene que ser EL MISMO que prepara Rust en
  // `src-tauri/src/backend.rs`. Si no, esto no simula la aplicacion: simula
  // otra cosa. El primer intento uso `MOLDESIGN_APP_MODE` en vez de `APP_MODE`
  // y omitio `VINA_EXECUTABLE_PATH`, y /health contesto 503 -correctamente,
  // porque sin Vina el backend NO esta sano. La prueba fallaba por culpa de la
  // prueba, que es la unica forma de fallar que no ensena nada.
  const vinaExe = path.join(RECURSOS, "tools", "vina", process.platform === "win32" ? "vina.exe" : "vina");
  const launchToken = randomBytes(32).toString("hex");
  const proc = spawn(
    py,
    ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", String(puerto),
     "--log-level", "warning", "--loop", "asyncio", "--app-dir", backend],
    {
      cwd: backend,
      env: {
        ...process.env,
        APP_MODE: "DESKTOP",
        // Rust comunica la carpeta del programa, pero el Blender administrado de Molcy ya
        // NO vive allí (WindowsApps es de sólo lectura): vive en LOCAL_DATA_DIR.
        MOLDESIGN_INSTALL_DIR: RECURSOS,
        ENVIRONMENT: "production",
        PYTHONPATH: backend,
        // Igual que en la instalacion: los recursos son inmutables y Python no
        // puede cachear bytecode. Por eso el bundle lo trae precompilado.
        PYTHONDONTWRITEBYTECODE: "1",
        VINA_EXECUTABLE_PATH: vinaExe,
        // Open Babel, igual que en `backend.rs`. Si esta variable falta aqui, el
        // smoke deja de reproducir el entorno de produccion en un punto que
        // importa: el adaptador tiene una resolucion por defecto que funciona,
        // asi que su ausencia NO se notaria y la diferencia viajaria callada.
        // (Que la resolucion por defecto tambien funcione lo comprueba
        // `verify_desktop_bundle.validate_open_babel`, que la borra a proposito.)
        MOLDESIGN_OPENBABEL_DIR: path.join(RECURSOS, "tools", "openbabel"),
        // El motor Molcy, igual que `backend.rs` (molcy_dir). Sólo es un lugar donde mirar: el backend lo usa si coincide con su manifiesto.
        MOLDESIGN_MOLCY_DIR: path.join(RECURSOS, "tools", "molcy"),
        TABPFN_NO_BROWSER: "true",
        PYTHONIOENCODING: "utf-8",
        LOCAL_DATA_DIR: datos,
        SECRET_KEY: randomBytes(32).toString("hex"),
        MOLDESIGN_LAUNCH_TOKEN: launchToken,
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let salida = "";
  proc.stdout.on("data", (d) => (salida += d));
  proc.stderr.on("data", (d) => (salida += d));

  const t0 = Date.now();
  const limite = t0 + 180000;
  while (Date.now() < limite) {
    if (proc.exitCode !== null) return { error: `el backend murio:\n${salida.slice(-1500)}`, datos };
    try {
      const r = await fetch(`http://127.0.0.1:${puerto}/health`, { signal: AbortSignal.timeout(2000) });
      if (r.ok) return { puerto, proc, datos, launchToken, segundos: (Date.now() - t0) / 1000 };
    } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  proc.kill();
  return { error: `el backend no respondio en 180 s:\n${salida.slice(-1500)}`, datos };
}

// --- 2. Servidor estatico con la CSP de produccion ---------------------------
async function servirExport(csp) {
  // El ORIGEN importa. La aplicacion instalada se sirve desde
  // `http://tauri.localhost`, que el backend trae en su lista de CORS
  // (`core/config.py: cors_origins`). Un puerto aleatorio de 127.0.0.1 NO esta
  // en esa lista: el primer intento de esta prueba fallaba con
  //
  //     Access to fetch at 'http://127.0.0.1:59224/stats/global' from origin
  //     'http://127.0.0.1:59294' has been blocked by CORS policy
  //
  // ...que es el backend comportandose CORRECTAMENTE ante un origen que no
  // conoce. No se puede usar `tauri.localhost` sin puerto sin ocupar el 80, asi
  // que se usa `localhost:3001`, que tambien esta declarado. Es una diferencia
  // real con la instalacion y conviene tenerla presente: esta prueba no valida
  // la politica de CORS para el origen de Tauri, solo que el resto funciona a
  // traves de un origen permitido.
  const PREFERIDO = 3001;
  let puerto = PREFERIDO;
  try {
    const sonda = net.createServer();
    await new Promise((res, rej) => {
      sonda.once("error", rej);
      sonda.listen(PREFERIDO, "127.0.0.1", res);
    });
    await new Promise((res) => sonda.close(res));
  } catch {
    puerto = await puertoLibre();
    console.log(`  AVISO: el puerto ${PREFERIDO} esta ocupado; se usa ${puerto} y CORS fallara.`);
  }
  const servidor = createServer(async (req, res) => {
    let rel = decodeURIComponent(req.url.split("?")[0]);
    if (rel.endsWith("/")) rel += "index.html";
    let archivo = path.join(OUT, rel);
    try {
      const info = await stat(archivo);
      // Next 16 crea directorios RSC junto a `<ruta>.html`; sólo usamos
      // index.html cuando realmente existe.
      if (info.isDirectory()) {
        const indice = path.join(archivo, "index.html");
        try {
          await stat(indice);
          archivo = indice;
        } catch {
          await stat(`${archivo}.html`);
          archivo = `${archivo}.html`;
        }
      }
    } catch {
      // Tauri sirve `<ruta>.html` para las rutas del router estatico.
      try {
        await stat(`${archivo}.html`);
        archivo = `${archivo}.html`;
      } catch {
        res.writeHead(404).end("no encontrado");
        return;
      }
    }
    const ext = path.extname(archivo).toLowerCase();
    const cabeceras = { "content-type": TIPOS[ext] || "application/octet-stream" };
    // La CSP viaja SOLO con el documento, igual que la pone el WebView.
    if (ext === ".html") cabeceras["content-security-policy"] = csp;
    res.writeHead(200, cabeceras).end(await readFile(archivo));
  });
  await new Promise((r) => servidor.listen(puerto, "127.0.0.1", r));
  return { puerto, servidor };
}

/** Rutas navegables del export: cada `<ruta>.html` / `<ruta>/index.html` de `out/`. */
async function rutasExportadas() {
  const rutas = new Set();
  const recorrer = async (dir, prefijo) => {
    for (const e of await readdir(dir, { withFileTypes: true })) {
      if (e.isDirectory()) {
        if (e.name === "_next" || e.name.startsWith("__next")) continue;
        await recorrer(path.join(dir, e.name), `${prefijo}/${e.name}`);
      } else if (e.name.endsWith(".html")) {
        const base = e.name === "index.html" ? prefijo : `${prefijo}/${e.name.slice(0, -5)}`;
        if (/(^|\/)(404|_not-found|_global-error)$/.test(base)) continue;
        rutas.add(base || "/");
      }
    }
  };
  await recorrer(OUT, "");
  return [...rutas];
}

// --- 3. La prueba ------------------------------------------------------------
async function main() {
  console.log("=".repeat(72));
  console.log("SMOKE DE PRODUCCION — export estatico + CSP real + backend empaquetado");
  console.log("=".repeat(72));

  const csp = cspDeProduccion();
  if (!csp) {
    console.error("no se pudo leer la CSP de produccion");
    process.exit(1);
  }
  console.log(`\nCSP:\n  ${csp.slice(0, 160)}...\n`);

  try {
    await stat(path.join(OUT, "index.html"));
  } catch {
    console.error(`falta ${OUT}. Corre \`npm run build:desktop\` antes.`);
    process.exit(1);
  }

  console.log("[1/3] Arrancando el backend empaquetado...");
  const back = await arrancarBackend();
  if (back.error) {
    comprobar("el backend empaquetado arranca y responde /health", false, back.error.split("\n")[0]);
    console.error(back.error);
    if (back.datos) console.error(`(datos de esta prueba, conservados: ${back.datos})`);
    process.exit(1);
  }
  comprobar("el backend empaquetado arranca y responde /health", true, `${back.segundos.toFixed(1)} s`);
  comprobar("arranque por debajo de 15 s", back.segundos < 15, `${back.segundos.toFixed(1)} s`);
  // Que el aislamiento se vea, no que se suponga: si el backend ignorase
  // LOCAL_DATA_DIR, la base no aparecería aquí y estaría tocando la del usuario.
  const baseAislada = await stat(path.join(back.datos, "moldesign_local.db")).then(() => true, () => false);
  comprobar("la base de datos es la temporal de la prueba", baseAislada, back.datos);
  const loginUrl = "http://127.0.0.1:" + back.puerto + "/auth/desktop-login";
  const sinSecreto = await fetch(loginUrl);
  comprobar("login de escritorio rechaza peticion sin secreto", sinSecreto.status === 403,
    String(sinSecreto.status));
  const conSecreto = await fetch(loginUrl, {
    headers: { "X-MolDesign-Launch": back.launchToken },
  });
  comprobar("login de escritorio acepta secreto de este arranque", conSecreto.status === 200,
    String(conSecreto.status));
  if (conSecreto.ok) {
    const login = await conSecreto.json();
    const molcy = await fetch(`http://127.0.0.1:${back.puerto}/molcy/blender`, {
      headers: { Authorization: `Bearer ${login.access_token}` },
    });
    comprobar("Molcy responde desde el runtime empaquetado", molcy.status === 200,
      String(molcy.status));
    if (molcy.ok) {
      const instalacion = await molcy.json();
      const esperada = path.join(back.datos, "molcy", "blender",
        `blender-${instalacion.version}-windows-x64`, "blender.exe");
      comprobar("Molcy instala su Blender en la carpeta de datos, no junto al programa (sólo lectura en la Store)",
        instalacion.ruta === esperada, instalacion.ruta ?? "sin ruta");
    }
    // El motor Molcy viaja en el runtime y el backend empaquetado lo encuentra (aunque aquí no haya Blender que sondear).
    const motor = await fetch(`http://127.0.0.1:${back.puerto}/molcy/renderizador`, {
      headers: { Authorization: `Bearer ${login.access_token}` },
    });
    if (motor.ok) {
      const cuerpo = await motor.json();
      comprobar("El motor Molcy viaja en el runtime y el backend empaquetado lo encuentra",
        cuerpo.motor_incluido === true, JSON.stringify({ motor_incluido: cuerpo.motor_incluido, motivo: cuerpo.motivo }));
      comprobar("El motor Molcy incluido no se declara alterado", cuerpo.motivo_codigo !== "motor_alterado",
        String(cuerpo.motivo_codigo ?? "íntegro o sin Blender que sondear"));
      comprobar("El backend empaquetado declara gestión automática de VRAM", cuerpo.gpu_memoria === "automatica",
        String(cuerpo.gpu_memoria ?? "sin política de memoria"));
    } else {
      comprobar("El motor Molcy viaja en el runtime y el backend empaquetado lo encuentra", false, String(motor.status));
    }
    const recursos = await fetch(`http://127.0.0.1:${back.puerto}/molcy/recursos`, {
      headers: { Authorization: `Bearer ${login.access_token}` },
    });
    comprobar("El runtime empaquetado consulta recursos de Molcy sin Blender", recursos.status === 200,
      String(recursos.status));
    if (recursos.ok) {
      const r = await recursos.json();
      comprobar("Molcy conserva margen CPU y declara si puede vigilar VRAM",
        Number.isInteger(r.cpu_hilos_maximos) && r.cpu_hilos_maximos >= 1 &&
        r.cpu_hilos_maximos <= Math.max(1, Math.floor(r.cpu_hilos_disponibles * 0.75)) &&
        r.cpu_hilos >= 1 && r.cpu_hilos <= r.cpu_hilos_maximos && typeof r.gpu_vram_monitorizable === "boolean",
        JSON.stringify({maximos:r.cpu_hilos_maximos,disponibles:r.cpu_hilos_disponibles,monitor_vram:r.gpu_vram_monitorizable}));
    }
  }

  console.log("[2/3] Sirviendo el export con la CSP de produccion...");
  const web = await servirExport(csp);

  console.log("[3/3] Cargando la aplicacion...\n");
  let navegador = null;
  for (const canal of ["chrome", "msedge"]) {
    try {
      navegador = await chromium.launch({ channel: canal });
      console.log(`  (navegador: ${canal})\n`);
      break;
    } catch {}
  }
  if (!navegador) {
    console.error("no hay Chrome ni Edge. `npx playwright install chromium` tambien vale.");
    back.proc.kill();
    web.servidor.close();
    process.exit(1);
  }

  for (const result of await comprobarIpcCsp(navegador)) {
    comprobar(result.nombre, result.ok, result.detalle);
  }
  const contexto = await navegador.newContext({ viewport: { width: 1400, height: 900 } });
  await contexto.addInitScript(({ puerto, launchToken }) => {
    window.__TAURI_INTERNALS__ = {};
    window.__TAURI__ = {
      core: {
        invoke: async (cmd) => {
          if (cmd === "ensure_backend" || cmd === "restart_backend") {
            return { state: "ready", port: puerto, detail: null };
          }
          if (cmd === "backend_status") return { state: "ready", port: puerto, detail: null };
          if (cmd === "backend_launch_token") return launchToken;
          throw new Error(`comando no simulado: ${cmd}`);
        },
      },
      event: { listen: async () => () => {} },
    };
  }, { puerto: back.puerto, launchToken: back.launchToken });

  const pagina = await contexto.newPage();
  const erroresCsp = [];
  const erroresConsola = [];
  const peticionesRemotas = [];
  const fallosDeRed = [];
  const fallosHttpBackend = [];

  pagina.on("console", (m) => {
    const texto = m.text();
    if (/Content Security Policy/i.test(texto)) erroresCsp.push(texto.slice(0, 200));
    else if (m.type() === "error") {
      const origen = m.location().url;
      erroresConsola.push(`${texto.slice(0, 160)}${origen ? ` [${origen}]` : ""}`);
    }
  });
  pagina.on("pageerror", (e) => erroresConsola.push(`pageerror: ${String(e).slice(0, 200)}`));
  pagina.on("request", (r) => {
    const u = r.url();
    if (/^https?:\/\//.test(u) && !u.includes("127.0.0.1") && !u.includes("localhost")) {
      peticionesRemotas.push(u.slice(0, 120));
    }
  });
  pagina.on("requestfailed", (r) => {
    const u = r.url();
    // Navegar cancela prefetch y streams. Un fallo de conexión con el motor,
    // en cambio, tiene que invalidar el smoke aunque ocurra fuera de Inicio.
    const error = r.failure()?.errorText;
    if (error !== "net::ERR_ABORTED") fallosDeRed.push(`${u.slice(-100)} :: ${error}`);
  });
  // SOL-11. Todo lo que el export pide a SU PROPIO origen tiene que existir en
  // `out/`. Los 404 de prefetch RSC (`/<ruta>/__next.<ruta>.__PAGE__.txt`) ya
  // salían en la consola, pero la comprobación de consola se pierde en el
  // ruido; esta lista los nombra uno por uno.
  const origenDelExport = `http://localhost:${web.puerto}`;
  const recursosInexistentes = new Set();
  pagina.on("response", (r) => {
    if (r.status() >= 500 && r.url().startsWith(`http://127.0.0.1:${back.puerto}/`)) {
      fallosHttpBackend.push(`${r.status()} ${new URL(r.url()).pathname}`);
    }
    if (r.status() === 404 && r.url().startsWith(origenDelExport)) {
      recursosInexistentes.add(r.url().replace(origenDelExport, "").split("?")[0]);
    }
  });

  await pagina.goto(`http://localhost:${web.puerto}/index.html`, {
    waitUntil: "networkidle",
    timeout: 60000,
  });
  await pagina.waitForTimeout(4000);

  // --- Invariantes ---------------------------------------------------------
  comprobar("ningun recurso remoto pedido al cargar", peticionesRemotas.length === 0,
    peticionesRemotas.slice(0, 2).join(" | "));
  comprobar("ninguna violacion de CSP", erroresCsp.length === 0, erroresCsp.slice(0, 2).join(" | "));

  // El boton de MolChat: el canario de los estilos en linea. Si Tauri inyecta
  // un nonce en style-src, `'unsafe-inline'` se anula y este boton pierde
  // `position: fixed` y su fondo. Es exactamente lo que paso en produccion.
  const boton = pagina.locator('button[title*="MolChat"]');
  const hayBoton = (await boton.count()) > 0;
  comprobar("el boton de MolChat existe", hayBoton);
  if (hayBoton) {
    const est = await boton.first().evaluate((el) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return {
        position: s.position,
        bg: s.backgroundColor,
        derecha: innerWidth - r.right,
        abajo: innerHeight - r.bottom,
        dentro: r.top >= 0 && r.bottom <= innerHeight,
      };
    });
    comprobar("...con position:fixed (los estilos en linea se aplican)",
      est.position === "fixed", `position=${est.position}`);
    comprobar("...con fondo visible, no transparente",
      est.bg !== "rgba(0, 0, 0, 0)" && est.bg !== "transparent", `bg=${est.bg}`);
    comprobar("...anclado abajo a la derecha y dentro de la ventana",
      est.dentro && est.derecha < 80 && est.abajo < 80,
      `derecha=${Math.round(est.derecha)} abajo=${Math.round(est.abajo)} dentro=${est.dentro}`);
  }

  // El registro cientifico usa `fetch` con ruta RELATIVA: si `connect-src` no
  // trae el origen propio, contesta «Failed to fetch» con el archivo al lado.
  const registro = await pagina.evaluate(async () => {
    try {
      const r = await fetch("/registro/index.json", { cache: "no-store" });
      if (!r.ok) return `HTTP ${r.status}`;
      const j = await r.json();
      return { entradas: Array.isArray(j) ? j.length : Object.keys(j).length };
    } catch (e) {
      return `excepcion: ${String(e).slice(0, 100)}`;
    }
  });
  comprobar("el registro cientifico se puede pedir (connect-src trae el origen)",
    typeof registro === "object", typeof registro === "object" ? `${registro.entradas} entradas` : registro);

  // El backend, a traves del puente, en el puerto que dice Rust.
  const objetivos = await pagina.evaluate(async (puerto) => {
    try {
      const r = await fetch(`http://127.0.0.1:${puerto}/health`);
      return r.ok ? "200" : `HTTP ${r.status}`;
    } catch (e) {
      return `excepcion: ${String(e).slice(0, 80)}`;
    }
  }, back.puerto);
  comprobar("la pagina alcanza el backend en el puerto de Rust", objetivos === "200", objetivos);

  // Las hojas de estilo del export tienen que estar ENLAZADAS, no inyectadas
  // por Webpack en ejecucion: el CSS de Ketcher vivia en un chunk que el HTML
  // no enlazaba y el editor salia sin estilos.
  const hojas = await pagina.evaluate(() =>
    [...document.querySelectorAll('link[rel="stylesheet"]')].map((l) => l.getAttribute("href")),
  );
  const ketcher = await pagina.evaluate(() =>
    [...document.styleSheets].some((h) => {
      try {
        return [...h.cssRules].some((r) => (r.selectorText || "").includes("ketcher"));
      } catch {
        return false;
      }
    }),
  );
  comprobar("el CSS de Ketcher esta en las hojas cargadas", ketcher, `${hojas.length} hojas`);

  comprobar("sin errores de consola inesperados", erroresConsola.length === 0,
    erroresConsola.slice(0, 2).join(" | "));

  // Regresión 2026-10-05: una corrida con Búsqueda hacía que el validador del
  // frontend rechazara TODAS las fuentes, incluidos los receptores. La base
  // temporal vacía no lo veía. Estas respuestas de prueba atraviesan el código
  // REAL del export; no requieren Blender ni generan un vídeo. Las comprobaciones
  // de API anteriores siguen usando el backend empaquetado sin interceptar.
  const cpuMolcy = { cpu_hilos:4, cpu_hilos_disponibles:8, cpu_hilos_maximos:6, gpu_vram_monitorizable:false };
  const espacioMolcy = Object.fromEntries(["biblioteca", "social_vertical", "previsualizacion"].map(
    key => [key, { libre_bytes:20e9, necesario_bytes:8e9, disponible:true }]));
  const respuestasMolcy = {
    fuentes: {
      moldex:[{id:"smoke-molecule", task_id:"smoke-search-run", nombre:"Corrida QA con traza", receptor:"4CA8",
        disponible:true, motivo:null, escenas_disponibles:["resultado","receptor","busqueda"]}],
      receptores:[{id:"QA_RECEPTOR", nombre:"Receptor QA", propio:true, disponible:true, motivo:null}],
    },
    renderizador:{...cpuMolcy, disponible:true, motivo:null, cpu_disponible:true, gpu_disponible:true,
      gpu_memoria:"automatica", espacio:espacioMolcy},
    recursos:{...cpuMolcy, espacio:espacioMolcy, espacio_task_id:"smoke-search-run", espacio_salida_id:null},
  };
  const rutasMolcy = Object.keys(respuestasMolcy).map(key => `**/molcy/${key}*`);
  for (const [key, value] of Object.entries(respuestasMolcy)) {
    await pagina.route(`**/molcy/${key}*`, route => route.fulfill({contentType:"application/json", body:JSON.stringify(value)}));
  }
  try {
    await pagina.goto(`${origenDelExport}/molcy`, {waitUntil:"networkidle", timeout:60000});
    const fuente = pagina.locator("#molcy-source");
    await fuente.locator('option[value="smoke-search-run"]').waitFor({state:"attached", timeout:15000});
    comprobar("Molcy del export carga Moldex cuando una corrida incluye Búsqueda", true);
    await fuente.selectOption("smoke-search-run");
    const busqueda = pagina.getByRole("button", {name:/Búsqueda.*03|Search.*03/});
    comprobar("El export ofrece Búsqueda para la corrida con traza", await busqueda.isEnabled());
    const generarVideo = pagina.getByRole("button", {name:/^Generar video$|^Generate video$/});
    await generarVideo.waitFor({state:"visible"});
    await pagina.waitForFunction(() => [...document.querySelectorAll("button")].some(button =>
      /^(Generar video|Generate video)$/.test(button.textContent?.trim() ?? "") && !button.disabled));
    comprobar("El export permite vídeo con GPU aunque no haya telemetría VRAM",
      await generarVideo.isEnabled() &&
      await pagina.getByText(/^(El vídeo se genera con la GPU|Video is rendered on the GPU)/).isVisible() &&
      await pagina.getByRole("button", {name:/^CPU$/}).count() === 0);
    comprobar("La VRAM automática se muestra sin selector de presupuesto",
      await pagina.getByText(/^(Gestión automática de VRAM|Automatic VRAM management)$/).isVisible() &&
      await pagina.getByRole("slider").count() === 0);
    await pagina.getByRole("button", {name:/^Receptores$|^Receptors$/}).click();
    comprobar("El catálogo de Molcy abre en Demostración",
      await pagina.getByRole("tab", {name:/^Demostración$|^Demo$/}).getAttribute("aria-selected") === "true");
    await pagina.getByRole("tab", {name:/^Mis Receptores$|^My receptors$/}).click();
    comprobar("El export conserva el catálogo de receptores junto a la corrida con traza",
      await pagina.getByRole("button", {name:/Receptor QA.*QA_RECEPTOR/}).isEnabled());
  } catch (error) {
    comprobar("Las fuentes y GPU de Molcy funcionan en el export poblado", false, String(error).slice(0,300));
  } finally {
    for (const ruta of rutasMolcy) await pagina.unroute(ruta);
  }

  // El input nativo de archivos hereda el idioma del SO. El export debe
  // cubrirlo con textos del idioma de la app sin perder foco ni carga real.
  for (const [locale, label, choose, empty] of [
    ["en", "Molecule file", "Choose file", "No file selected"],
    ["es", "Archivo de moléculas", "Elegir archivo", "No se eligió ningún archivo"],
  ]) {
    try {
      await pagina.evaluate((language) => {
        const auth = JSON.parse(localStorage.getItem("moldesign_auth") || "{}");
        if (!auth.user?.user_id) throw new Error("No desktop session for locale preference");
        localStorage.setItem(`moldesign_locale:user:${auth.user.user_id}`, language);
      }, locale);
      await pagina.goto(`${origenDelExport}/evaluation/batch`, { waitUntil: "networkidle", timeout: 60000 });
      const file = pagina.getByLabel(label, { exact: true });
      await file.waitFor({ state: "attached", timeout: 15000 });
      await pagina.getByText(choose, { exact: true }).waitFor({ state: "visible" });
      const translated = await pagina.getByText(empty, { exact: true }).isVisible();
      await file.focus();
      const nativeHiddenAndFocusable = await file.evaluate(el =>
        getComputedStyle(el).opacity === "0" && document.activeElement === el);
      await file.setInputFiles({ name: "translation-smoke.csv", mimeType: "text/csv", buffer: Buffer.from("smiles,name\nCCO,Ethanol\n") });
      const selected = await pagina.getByText("translation-smoke.csv", { exact: true }).isVisible();
      comprobar(`Batch: selector traducido y operable en ${locale}`, translated && nativeHiddenAndFocusable && selected);

      // No fijar Accept-Language aquí: debe añadirlo el LanguageProvider REAL
      // del export recién cargado. Esto ejercita fetch, autenticación, CORS y
      // traducción del backend empaquetado, con los headers del cliente JSON.
      const api = await pagina.evaluate(async (puerto) => {
        const auth = JSON.parse(localStorage.getItem("moldesign_auth") || "{}");
        const headers = {
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true",
          Authorization: `Bearer ${auth.token}`,
        };
        const probes = [
          ["/health"], ["/targets/"], ["/evaluation/engines"],
          ["/pro/anti-targets"], ["/moldex"], ["/history/stats"],
          ["/molcy/fuentes"], ["/molcy/trabajos"],
          ["/ai/providers"], ["/ai/conversations"],
          ["/chem/validate", { smiles: "CC(=O)Oc1ccccc1C(=O)O" }],
          ["/evaluation/preflight", {
            smiles: "CC(=O)Oc1ccccc1C(=O)O", target_pdb_id: "3F75", chain: "A",
          }],
        ];
        const results = [];
        for (const [endpoint, body] of probes) {
          try {
            const r = await fetch(`http://127.0.0.1:${puerto}${endpoint}`, {
              headers, method: body ? "POST" : "GET",
              ...(body ? { body: JSON.stringify(body) } : {}),
              signal: AbortSignal.timeout(15000),
            });
            const json = await r.json();
            results.push({ endpoint, ok: r.ok && json !== null,
              status: r.status, language: r.headers.get("content-language") });
          } catch (error) {
            results.push({ endpoint, ok: false, error: String(error) });
          }
        }
        return results;
      }, back.puerto);
      for (const probe of api) {
        comprobar(`API ${locale}: ${probe.endpoint}`, probe.ok && probe.language === locale,
          probe.error ?? `HTTP ${probe.status}, idioma=${probe.language}`);
      }
    } catch (error) {
      comprobar(`Batch: selector traducido y operable en ${locale}`, false, String(error).slice(0, 300));
    }
  }

  // Barrido de rutas: cada ruta exportada se carga directa (no sólo la
  // portada), porque el prefetch de Next sólo pide los segmentos de las rutas
  // que SU página enlaza. Las páginas internas de Next (`_not-found`, `404`) no
  // son destinos de navegación.
  const rutas = (await rutasExportadas()).sort();
  for (const locale of ["en", "es"]) {
    await pagina.evaluate((language) => {
      const auth = JSON.parse(localStorage.getItem("moldesign_auth") || "{}");
      localStorage.setItem(`moldesign_locale:user:${auth.user.user_id}`, language);
    }, locale);
    for (const ruta of rutas) {
      await pagina.goto(`${origenDelExport}${ruta}`, { waitUntil: "networkidle", timeout: 60000 });
      await pagina.waitForFunction(language => document.documentElement.lang === language, locale);
      await pagina.waitForTimeout(1500);
    }
    console.log(`  (barrido: ${rutas.length} rutas en ${locale})`);
  }
  comprobar(`el export no pide recursos inexistentes (${rutas.length} rutas recorridas)`,
    recursosInexistentes.size === 0, [...recursosInexistentes].slice(0, 4).join(" | "));

  comprobar("sin fallos de red en todas las pestañas y ambos idiomas",
    fallosDeRed.length === 0, fallosDeRed.slice(0, 4).join(" | "));
  comprobar("sin errores HTTP 5xx del backend en todas las pestañas",
    fallosHttpBackend.length === 0, fallosHttpBackend.slice(0, 4).join(" | "));
  comprobar("sin violaciones de CSP al recorrer todas las pestañas",
    erroresCsp.length === 0, erroresCsp.slice(0, 2).join(" | "));

  await navegador.close();
  back.proc.kill();
  web.servidor.close();

  const fallos = resultados.filter((r) => !r.ok);
  console.log("\n" + "=".repeat(72));
  console.log(`${resultados.length - fallos.length}/${resultados.length} comprobaciones pasan`);
  console.log("=".repeat(72));
  if (fallos.length) {
    for (const f of fallos) console.log(`  FALLA  ${f.nombre}  ${f.detalle}`);
    console.log(`  (datos de esta prueba, conservados: ${back.datos})`);
    process.exit(1);
  }
  // En Windows el proceso tarda en soltar el SQLite: reintentos, y si aun asi
  // no se puede borrar, se dice. Un resto en %TEMP% no invalida el resultado.
  await rm(back.datos, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 })
    .catch((e) => console.log(`  (no se pudo borrar ${back.datos}: ${e.code ?? e.message})`));
  process.exit(0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
