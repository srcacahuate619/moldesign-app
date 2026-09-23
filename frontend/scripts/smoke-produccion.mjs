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
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

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
  const proc = spawn(
    py,
    ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", String(puerto),
     "--log-level", "warning", "--loop", "asyncio", "--app-dir", backend],
    {
      cwd: backend,
      env: {
        ...process.env,
        APP_MODE: "DESKTOP",
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
        TABPFN_NO_BROWSER: "true",
        PYTHONIOENCODING: "utf-8",
        LOCAL_DATA_DIR: datos,
        SECRET_KEY: randomBytes(32).toString("hex"),
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
      if (r.ok) return { puerto, proc, datos, segundos: (Date.now() - t0) / 1000 };
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

  const contexto = await navegador.newContext({ viewport: { width: 1400, height: 900 } });
  await contexto.addInitScript((puerto) => {
    window.__TAURI_INTERNALS__ = {};
    window.__TAURI__ = {
      core: {
        invoke: async (cmd) => {
          if (cmd === "ensure_backend" || cmd === "restart_backend") {
            return { state: "ready", port: puerto, detail: null };
          }
          if (cmd === "backend_status") return { state: "ready", port: puerto, detail: null };
          throw new Error(`comando no simulado: ${cmd}`);
        },
      },
      event: { listen: async () => () => {} },
    };
  }, back.puerto);

  const pagina = await contexto.newPage();
  const erroresCsp = [];
  const erroresConsola = [];
  const peticionesRemotas = [];
  const fallosDeRed = [];

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
    if (!u.includes(`:${back.puerto}`)) fallosDeRed.push(`${u.slice(-70)} :: ${r.failure()?.errorText}`);
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

  if (fallosDeRed.length) {
    console.log(`\n  (peticiones fallidas, informativo: ${fallosDeRed.slice(0, 3).join(" | ")})`);
  }

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
