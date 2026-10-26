#!/usr/bin/env node
// scripts/qa_sandbox/sandbox-up.mjs
// =============================================================================
// Levanta, inspecciona o apaga una CÁPSULA de QA: backend + frontend + datos
// propios, con puertos y carpeta por agente. Ver `README.md` para el contrato
// completo y para lo que NO replica de la aplicación instalada.
//
//   node scripts/qa_sandbox/sandbox-up.mjs --agente N             levanta (construye `out/` si hace falta)
//   node scripts/qa_sandbox/sandbox-up.mjs --agente N --estado    qué está vivo y qué commit sirve
//   node scripts/qa_sandbox/sandbox-up.mjs --agente N --down      apaga (--limpiar retira las junctions)
//   node scripts/qa_sandbox/sandbox-up.mjs --agente N --reset     apaga y vuelve a «primer uso»
// =============================================================================

import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import {
  CARPETAS_DE_RESET, MARCA_CAPSULA, carpetasDe, entornoBackend, esCapsulaBorrable, origenDe, parseArgs,
  puertosDe, sinClaves,
} from "./lib.mjs";
import { RegistroDeCasos, versionDeEsquema } from "./casos.mjs";
import { crearServidor } from "./servidor.mjs";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(AQUI, "..", "..");

const AYUDA = `Uso:
  node scripts/qa_sandbox/sandbox-up.mjs --agente N [opciones]      (N entre 1 y 9; el 9 lo usa el autotest)

Acciones (por defecto: levantar)
  --estado          muestra qué está vivo, el commit servido y la salud del backend
  --down            apaga la cápsula (--limpiar además retira las junctions que creó)
  --reset           apaga y borra datos, perfil, casos y temporales: vuelve a primer uso

Opciones
  --rebuild         reconstruye \`frontend/out\` aunque la huella no haya cambiado
  --no-build        no construye: usa el \`out/\` que haya (el manifiesto avisa si está viejo)
  --out DIR         sirve un export ya construido (autotest; el manifiesto lo marca «externo»)
  --capsula DIR     carpeta de la cápsula (por defecto ..\\.sandbox\\agenteN junto al worktree)
  --vina-cpu N      núcleos de Vina del backend (por defecto 4)
  --primer-plano    no termina: apaga la cápsula al recibir Ctrl+C
`;

const log = (...a) => console.log(...a);
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
const marca = () => new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "").replace("T", "_");

class ErrorDeCapsula extends Error {}
const muere = (m) => { throw new ErrorDeCapsula(m); };

// --- git y procesos -----------------------------------------------------------

function git(args, cwd = REPO) {
  return execFileSync("git", args, { cwd, encoding: "utf8", maxBuffer: 512 * 1024 * 1024 }).trim();
}

function ps(script) {
  return execFileSync("powershell", ["-NoProfile", "-NonInteractive", "-Command", script], { encoding: "utf8" }).trim();
}

function procesoVivo(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM";
  }
}

function lineaDeComando(pid) {
  try {
    return ps(`(Get-CimInstance Win32_Process -Filter "ProcessId=${Number(pid)}").CommandLine`) || null;
  } catch {
    return null;
  }
}

/** Quién escucha en `puerto`, o `null`. La consulta de red manda; el intento de `bind` en 127.0.0.1 miente en Windows si el otro escucha en 0.0.0.0. */
function ocupantePuerto(puerto) {
  try {
    const pid = Number(ps(`Get-NetTCPConnection -LocalPort ${Number(puerto)} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess`));
    if (!pid) return null;
    return { pid, linea: lineaDeComando(pid) ?? "(sin línea de comando visible)" };
  } catch {
    return null;
  }
}

function leerJson(p) {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return null;
  }
}

function escribirJson(p, v) {
  fs.writeFileSync(p, `${JSON.stringify(v, null, 2)}\n`);
}

// --- rutas y runtime ----------------------------------------------------------

function raizDelRuntime() {
  if (process.env.MOLDESIGN_RUNTIME_ROOT) return path.resolve(process.env.MOLDESIGN_RUNTIME_ROOT);
  // El worktree no trae `python-embed`, `tools/vina` ni los pesos (están en .gitignore): se usan los
  // del árbol principal, en sólo lectura. `--git-common-dir` apunta siempre a su `.git`.
  const comun = path.resolve(REPO, git(["rev-parse", "--git-common-dir"]));
  return path.basename(comun) === ".git" ? path.dirname(comun) : REPO;
}

function validarRuntime(rt) {
  const necesarios = [
    ["python-embed/python.exe", "el Python embebido (npm run provision:runtime)"],
    ["tools/vina/vina.exe", "AutoDock Vina"],
    ["tools/openbabel/bin/obabel.exe", "Open Babel (python scripts/stage_openbabel_tool.py)"],
  ];
  const faltan = necesarios.filter(([rel]) => !fs.existsSync(path.join(rt, rel))).map(([rel, que]) => `${rel} — ${que}`);
  if (faltan.length) muere(`el runtime compartido en ${rt} está incompleto:\n  - ${faltan.join("\n  - ")}`);
}

function rutaCapsula(args) {
  return args.capsula ? path.resolve(args.capsula) : path.resolve(REPO, "..", ".sandbox", `agente${args.agente}`);
}

function prepararCarpetas(capsula) {
  const c = carpetasDe(capsula);
  for (const d of Object.values(c)) fs.mkdirSync(d, { recursive: true });
  fs.mkdirSync(path.join(c.home, ".moldesign"), { recursive: true });
  const m = path.join(capsula, MARCA_CAPSULA);
  if (!fs.existsSync(m)) fs.writeFileSync(m, "Creada por scripts/qa_sandbox/sandbox-up.mjs. `--reset` sólo borra carpetas con esta marca.\n");
  return c;
}

function cspDeProduccion() {
  const dir = path.join(REPO, "frontend", "src-tauri");
  const prod = leerJson(path.join(dir, "tauri.conf.prod.json"));
  const base = leerJson(path.join(dir, "tauri.conf.json"));
  const csp = prod?.app?.security?.csp ?? base?.app?.security?.csp;
  if (typeof csp !== "string" || !csp) muere("no encuentro la CSP de producción en frontend/src-tauri/tauri.conf*.json");
  return csp;
}

// --- completar el worktree ------------------------------------------------------

/**
 * Un worktree nace sin lo que git ignora. Se completa con lo mínimo, y todo lo que se crea
 * queda anotado en `enlaces.json` para poder retirarlo después.
 *   - `data/molgraph_seed.db` (copia): sin ella Moldex pierde el corpus público.
 *   - `frontend/node_modules` y `models/` (junction): dependencias del build y LLM de MolChat.
 *     Se leen, no se escriben; las descargas de modelos están vetadas a los agentes.
 */
function completarWorktree(rt, capsula) {
  const registro = leerJson(path.join(capsula, "enlaces.json")) ?? { creados: [] };
  const nota = (e) => { registro.creados.push(e); log(`  + ${e.tipo}: ${e.destino}`); };
  if (path.resolve(REPO) !== path.resolve(rt)) {
    const semillaOrigen = path.join(rt, "data", "molgraph_seed.db");
    const semillaDestino = path.join(REPO, "data", "molgraph_seed.db");
    if (fs.existsSync(semillaOrigen) && !fs.existsSync(semillaDestino)) {
      fs.mkdirSync(path.dirname(semillaDestino), { recursive: true });
      fs.copyFileSync(semillaOrigen, semillaDestino);
      nota({ tipo: "copia", destino: semillaDestino, origen: semillaOrigen });
    }
    for (const rel of ["frontend/node_modules", "models"]) {
      const origen = path.join(rt, rel);
      const destino = path.join(REPO, rel);
      if (fs.existsSync(origen) && !fs.existsSync(destino)) {
        fs.symlinkSync(origen, destino, "junction");
        nota({ tipo: "junction", destino, origen });
      }
    }
  }
  escribirJson(path.join(capsula, "enlaces.json"), registro);
}

function retirarEnlaces(capsula) {
  const registro = leerJson(path.join(capsula, "enlaces.json"));
  if (!registro) return;
  for (const e of registro.creados.filter((x) => x.tipo === "junction")) {
    try {
      // `rmdir` NO recursivo: retira el enlace sin tocar lo que hay al otro lado.
      fs.rmdirSync(e.destino);
      log(`  - junction retirada: ${e.destino}`);
    } catch (err) {
      log(`  ! no se pudo retirar ${e.destino}: ${err.message}`);
    }
  }
  registro.creados = registro.creados.filter((x) => x.tipo !== "junction");
  escribirJson(path.join(capsula, "enlaces.json"), registro);
}

// --- el export estático ------------------------------------------------------------

/**
 * Huella de lo que `out/` debería reflejar: el commit, los cambios sin commitear y los archivos
 * nuevos de `frontend/`. Un `out/` viejo es el camino más corto a auditar código que ya no existe
 * (restricción 1 del AGENTS.md: lo que se verifica tiene que ser lo que se entrega).
 */
function huellaDeFuentes(enlaces) {
  const commit = git(["rev-parse", "HEAD"]);
  const diff = execFileSync("git", ["diff", "HEAD", "--binary", "--", "frontend"], { cwd: REPO, maxBuffer: 512 * 1024 * 1024 });
  const nuevos = git(["ls-files", "--others", "--exclude-standard", "--", "frontend"]).split("\n").filter(Boolean)
    .map((f) => {
      const s = fs.statSync(path.join(REPO, f), { throwIfNoEntry: false });
      return `${f}:${s?.size}:${Math.round(s?.mtimeMs ?? 0)}`;
    });
  const huella = crypto.createHash("sha256").update(commit).update("\0").update(diff).update("\0").update(nuevos.join("\n")).digest("hex");
  // Las junctions que creó el propio lanzador no «ensucian» el árbol.
  const propios = new Set(enlaces.map((e) => path.relative(REPO, e.destino).replaceAll("\\", "/")));
  const sucias = git(["status", "--porcelain"]).split("\n").filter(Boolean)
    .filter((l) => !propios.has(l.slice(3).replace(/\/$/, "")));
  return { commit, huella, arbolLimpio: sucias.length === 0 };
}

async function construir(c) {
  const frontend = path.join(REPO, "frontend");
  if (!fs.existsSync(path.join(frontend, "node_modules"))) muere("falta frontend/node_modules: sin él no se puede construir el export.");
  const archivo = path.join(c.logs, `build_${marca()}.log`);
  const fd = fs.openSync(archivo, "a");
  log(`  construyendo el export (npm run build:desktop; unos minutos). Log: ${archivo}`);
  const env = sinClaves(process.env, ["NEXT_PUBLIC_API_URL", "NEXT_DIST_DIR", "BUILD_TARGET"]);
  // Una sola cadena: con `shell: true`, Node 24 avisa (DEP0190) si se le pasa un array de argumentos.
  const hijo = spawn("npm run build:desktop", { cwd: frontend, env, stdio: ["ignore", fd, fd], shell: true, windowsHide: true });
  const t0 = Date.now();
  const latido = setInterval(() => log(`  … construyendo (${Math.round((Date.now() - t0) / 1000)} s)`), 30000);
  const codigo = await new Promise((r) => hijo.on("exit", r));
  clearInterval(latido);
  fs.closeSync(fd);
  if (codigo !== 0) {
    const cola = fs.readFileSync(archivo, "utf8").split("\n").slice(-40).join("\n");
    muere(`el build terminó con código ${codigo}. Últimas líneas de ${archivo}:\n${cola}`);
  }
  return Math.round((Date.now() - t0) / 1000);
}

function comprobarExport(outDir) {
  if (!fs.existsSync(path.join(outDir, "index.html"))) muere(`no hay export en ${outDir} (falta index.html).`);
  // La puerta del build: ningún puerto de backend horneado en el export.
  try {
    execFileSync(process.execPath, ["scripts/check-exported-api-url.js"], { cwd: path.join(REPO, "frontend"), encoding: "utf8", stdio: "pipe" });
    return "ok";
  } catch (e) {
    return `FALLA: ${String(e.stdout ?? e.message).trim().split("\n").slice(-3).join(" | ")}`;
  }
}

// --- arranque ----------------------------------------------------------------------

async function esperar(url, { opciones = {}, limiteMs, vivo, nombre }) {
  const fin = Date.now() + limiteMs;
  while (Date.now() < fin) {
    if (vivo && !vivo()) return { ok: false, motivo: `${nombre} se detuvo antes de estar listo` };
    try {
      const r = await fetch(url, { ...opciones, signal: AbortSignal.timeout(2500) });
      if (r.ok) return { ok: true, respuesta: r };
    } catch { /* aún no escucha */ }
    await dormir(400);
  }
  return { ok: false, motivo: `${nombre} no respondió en ${Math.round(limiteMs / 1000)} s` };
}

function colaDe(archivo, n = 30) {
  try {
    return fs.readFileSync(archivo, "utf8").split("\n").slice(-n).join("\n");
  } catch {
    return "(sin log)";
  }
}

function leerPids(capsula) {
  return leerJson(path.join(capsula, "pids.json"));
}

function hayCapsulaViva(capsula) {
  const p = leerPids(capsula);
  return !!p && Object.values(p.procesos ?? {}).some((x) => procesoVivo(x.pid) && (lineaDeComando(x.pid) ?? "").includes(x.fragmentos[0]));
}

async function bajar(capsula, puertos) {
  const p = leerPids(capsula);
  if (p) {
    for (const [nombre, x] of Object.entries(p.procesos ?? {})) {
      if (!procesoVivo(x.pid)) continue;
      const linea = lineaDeComando(x.pid) ?? "";
      if (!x.fragmentos.every((f) => linea.includes(f))) {
        log(`  ! el pid ${x.pid} (${nombre}) ya no es nuestro proceso; no se toca.`);
        continue;
      }
      try {
        execFileSync("taskkill", ["/PID", String(x.pid), "/T", "/F"], { stdio: "pipe" });
        log(`  - ${nombre} detenido (pid ${x.pid})`);
      } catch (e) {
        log(`  ! taskkill falló para ${nombre} (pid ${x.pid}): ${e.message}`);
      }
    }
    fs.rmSync(path.join(capsula, "pids.json"), { force: true });
  }
  const fin = Date.now() + 15000;
  while (Date.now() < fin && [puertos.back, puertos.front].some((q) => ocupantePuerto(q))) await dormir(500);
}

function reiniciarDatos(capsula, rt) {
  const veredicto = esCapsulaBorrable(capsula, { protegidas: [REPO, rt], noContener: [os.homedir()] });
  if (!veredicto.ok) muere(`--reset se niega a borrar ${capsula}: ${veredicto.motivo}.`);
  const c = carpetasDe(capsula);
  for (const k of CARPETAS_DE_RESET) {
    const dir = c[k];
    if (!fs.existsSync(dir)) continue;
    if (fs.lstatSync(dir).isSymbolicLink()) muere(`--reset se niega: ${dir} es un enlace simbólico.`);
    fs.rmSync(dir, { recursive: true, force: true });
    log(`  - borrado ${dir}`);
  }
  fs.rmSync(path.join(capsula, "siguiente-carpeta.txt"), { force: true });
}

const DESVIACIONES = [
  "El backend corre desde el árbol (python-embed del árbol principal + backend/ de este worktree), no desde el runtime staged del instalador.",
  "Python se ejecuta con -B para no escribir bytecode en runtimes o bibliotecas compartidas; el primer arranque puede tardar más.",
  "El perfil de usuario (USERPROFILE, APPDATA, LOCALAPPDATA, TEMP) apunta a la cápsula: el backend ve un usuario NUEVO.",
  "Tauri está SIMULADO: el shim contesta ensure_backend/backend_launch_token y el servidor emula los comandos case_* de cases.rs, get_resource_dir, file_exists y verify_model (sólo existencia, sin SHA-256). Descargas, extracción, diálogos nativos y el Explorador NO se emulan.",
  "El selector nativo de carpetas se sustituye por una carpeta fija (casos/) o por siguiente-carpeta.txt.",
  "Se sirve desde http://localhost:<puerto>, no desde http://tauri.localhost: el CORS de producción para el origen de Tauri no se ejerce.",
  "WebView2 no es Chrome: el navegador de la prueba es otro motor de renderizado.",
  "Sidecars con puerto fijo (ESMFold 8100, ESMFold-Pro 8300): sólo UNA cápsula a la vez debe usarlos.",
];

async function levantar(args) {
  const puertos = puertosDe(args.agente);
  const rt = raizDelRuntime();
  validarRuntime(rt);
  const capsula = rutaCapsula(args);
  const c = prepararCarpetas(capsula);

  log(`Cápsula del agente ${args.agente}  (${capsula})`);
  const viva = hayCapsulaViva(capsula);
  if (viva && !args.reset && !args.rebuild) {
    log("  Ya está levantada. Usa --estado para ver el detalle, o --rebuild / --reset para rehacerla.");
    return mostrarEstado(args, capsula, puertos);
  }
  if (viva || leerPids(capsula)) { log("  apagando la instancia anterior…"); await bajar(capsula, puertos); }
  if (args.reset) {
    reiniciarDatos(capsula, rt);
    prepararCarpetas(capsula);
  }

  for (const [nombre, puerto] of [["backend", puertos.back], ["frontend", puertos.front]]) {
    const o = ocupantePuerto(puerto);
    if (o) muere(`el puerto ${puerto} (${nombre}) ya lo ocupa el pid ${o.pid}: ${o.linea}`);
  }

  // El instalador excluye todo `.env` (bundle_helper) y un worktree no los trae porque git los ignora. En el
  // árbol principal sí existen, y pydantic los carga desde el directorio del backend: la cápsula leería
  // `SECRET_KEY` y `SOLANA_PRIVATE_KEY` del desarrollador y dejaría de parecerse a una instalación.
  const envsPresentes = [".env", ".env.desktop"].filter((f) => fs.existsSync(path.join(REPO, "backend", f)));
  if (envsPresentes.length) {
    log(`  ! backend/${envsPresentes.join(" y backend/")} existe${envsPresentes.length > 1 ? "n" : ""} y el backend lo(s) cargará: NO es el entorno de la app instalada.`);
    log("    Lanza la cápsula desde un worktree (git worktree add …), donde esos archivos no existen.");
  }

  log("Preparando el worktree…");
  completarWorktree(rt, capsula);
  const enlaces = leerJson(path.join(capsula, "enlaces.json"))?.creados ?? [];

  // --- export ---------------------------------------------------------------------
  const fuentes = huellaDeFuentes(enlaces);
  let outDir;
  const exportInfo = { origen: null, dir: null, huella: fuentes.huella, construidoEnSegundos: null, advertencia: null };
  if (args.out) {
    outDir = path.resolve(args.out);
    exportInfo.origen = "externo";
    exportInfo.advertencia = "export externo (--out): no se garantiza que corresponda a este commit.";
  } else {
    outDir = path.join(REPO, "frontend", "out");
    const sello = leerJson(path.join(capsula, "build-stamp.json"));
    const hayOut = fs.existsSync(path.join(outDir, "index.html"));
    const vigente = hayOut && sello?.huella === fuentes.huella;
    if (args.noBuild) {
      exportInfo.origen = "existente";
      if (!hayOut) muere("--no-build pero no hay frontend/out.");
      if (!vigente) exportInfo.advertencia = "el export NO corresponde al código actual (la huella cambió desde el último build).";
    } else if (args.rebuild || !vigente) {
      log("Export estático…");
      exportInfo.construidoEnSegundos = await construir(c);
      exportInfo.origen = "construido";
      escribirJson(path.join(capsula, "build-stamp.json"), { huella: fuentes.huella, commit: fuentes.commit, construido: new Date().toISOString() });
    } else {
      exportInfo.origen = "reutilizado";
      log("Export estático: vigente (misma huella), se reutiliza.");
    }
  }
  exportInfo.dir = outDir;
  exportInfo.check_api_url = comprobarExport(outDir);
  if (exportInfo.check_api_url !== "ok") log(`  ! check-exported-api-url: ${exportInfo.check_api_url}`);

  // --- backend --------------------------------------------------------------------
  const token = crypto.randomBytes(32).toString("hex");
  const env = entornoBackend({ base: process.env, repoRoot: REPO, runtimeRoot: rt, capsula, puertos, token, vinaCpu: args.vinaCpu });
  const sello = marca();
  const logBack = path.join(c.logs, `backend_${sello}.log`);
  const fdBack = fs.openSync(logBack, "a");
  log(`Backend en 127.0.0.1:${puertos.back}…  (log: ${logBack})`);
  const back = spawn(path.join(rt, "python-embed", "python.exe"),
    ["-B", "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", String(puertos.back), "--loop", "asyncio", "--app-dir", path.join(REPO, "backend")],
    { cwd: path.join(REPO, "backend"), env, detached: true, stdio: ["ignore", fdBack, fdBack], windowsHide: true });
  back.unref();
  fs.closeSync(fdBack);
  const procesos = { backend: { pid: back.pid, fragmentos: ["uvicorn", `--port ${puertos.back}`] } };
  escribirJson(path.join(capsula, "pids.json"), { iniciado: new Date().toISOString(), procesos });
  const t0 = Date.now();
  const salud = await esperar(`http://127.0.0.1:${puertos.back}/health`, { limiteMs: 240000, vivo: () => procesoVivo(back.pid), nombre: "el backend" });
  if (!salud.ok) {
    await bajar(capsula, puertos);
    muere(`${salud.motivo}. Últimas líneas del log:\n${colaDe(logBack)}`);
  }
  log(`  backend listo en ${Math.round((Date.now() - t0) / 1000)} s`);

  // --- servidor del frontend ---------------------------------------------------------
  const archivoManifiesto = path.join(capsula, "manifest.json");
  fs.rmSync(archivoManifiesto, { force: true });
  const servirJson = path.join(capsula, "serve.json");
  escribirJson(servirJson, {
    outDir, csp: cspDeProduccion(), puertoFront: puertos.front, puertoBack: puertos.back, token, runtimeRoot: rt,
    raicesLegibles: [rt, capsula], archivoManifiesto, archivoNoEmulados: path.join(c.logs, "no-emulados.log"),
    casesRs: path.join(REPO, "frontend", "src-tauri", "src", "cases.rs"), dirRegistro: c.registroCasos, dirPadre: c.casos,
    archivoSiguiente: path.join(capsula, "siguiente-carpeta.txt"),
  });
  const logFront = path.join(c.logs, `frontend_${sello}.log`);
  const fdFront = fs.openSync(logFront, "a");
  log(`Servidor del export en localhost:${puertos.front}…`);
  const front = spawn(process.execPath, [fileURLToPath(import.meta.url), "--_servir", servirJson],
    { cwd: REPO, detached: true, stdio: ["ignore", fdFront, fdFront], windowsHide: true });
  front.unref();
  fs.closeSync(fdFront);
  procesos.frontend = { pid: front.pid, fragmentos: ["--_servir", servirJson] };
  escribirJson(path.join(capsula, "pids.json"), { iniciado: new Date().toISOString(), procesos });
  const listo = await esperar(`http://localhost:${puertos.front}/index.html`, { limiteMs: 30000, vivo: () => procesoVivo(front.pid), nombre: "el servidor del export" });
  if (!listo.ok) {
    await bajar(capsula, puertos);
    muere(`${listo.motivo}. Últimas líneas del log:\n${colaDe(logFront)}`);
  }

  // --- autoverificación ------------------------------------------------------------------
  const origen = origenDe(puertos);
  const comprobaciones = {};
  const login = await fetch(`http://127.0.0.1:${puertos.back}/auth/desktop-login`, { headers: { "X-MolDesign-Launch": token } });
  comprobaciones.desktop_login = login.status;
  const cors = await fetch(`http://127.0.0.1:${puertos.back}/health`, { headers: { Origin: origen } });
  comprobaciones.cors_origen_propio = cors.headers.get("access-control-allow-origin") === origen;
  const ajeno = await fetch(`http://127.0.0.1:${puertos.back}/health`, { headers: { Origin: `http://localhost:${puertos.front + 1000}` } });
  comprobaciones.cors_origen_ajeno_bloqueado = ajeno.headers.get("access-control-allow-origin") === null;
  const cuerpoSalud = await cors.json().catch(() => null);
  comprobaciones.health = cuerpoSalud?.status ?? cuerpoSalud?.estado ?? "ver /health";
  if (login.status !== 200 || !comprobaciones.cors_origen_propio || !comprobaciones.cors_origen_ajeno_bloqueado) {
    await bajar(capsula, puertos);
    muere(`la autoverificación falló: ${JSON.stringify(comprobaciones)}. Log del backend:\n${colaDe(logBack)}`);
  }

  // --- manifiesto ------------------------------------------------------------------------
  const manifiesto = {
    agente: args.agente,
    levantada: new Date().toISOString(),
    repositorio: { raiz: REPO, rama: git(["rev-parse", "--abbrev-ref", "HEAD"]), commit: fuentes.commit, arbol_limpio: fuentes.arbolLimpio },
    runtime_compartido: { raiz: rt, python: path.join(rt, "python-embed", "python.exe"), vina: path.join(rt, "tools", "vina", "vina.exe") },
    export: exportInfo,
    puertos: { backend: puertos.back, frontend: puertos.front, llama: puertos.llama },
    urls: { app: origen, backend: `http://127.0.0.1:${puertos.back}` },
    capsula: { raiz: capsula, datos: c.data, logs: c.logs, perfil: c.home, casos: c.casos, temporales: c.tmp },
    vina_cpu: args.vinaCpu,
    cors_origins: [origen],
    enlaces_creados: enlaces,
    advertencias: envsPresentes.map((f) => `backend/${f} presente: lo carga el backend; la app instalada no lo tiene.`),
    autoverificacion: comprobaciones,
    desviaciones_respecto_a_la_app_instalada: DESVIACIONES,
  };
  escribirJson(archivoManifiesto, manifiesto);

  log("");
  log("=".repeat(72));
  log(`CÁPSULA ${args.agente} LISTA`);
  log(`  App:        ${origen}      (abre SIEMPRE esta dirección, no 127.0.0.1)`);
  log(`  Backend:    http://127.0.0.1:${puertos.back}`);
  log(`  Commit:     ${fuentes.commit.slice(0, 10)}  (${manifiesto.repositorio.rama})  árbol limpio: ${fuentes.arbolLimpio}`);
  log(`  Export:     ${exportInfo.origen}${exportInfo.construidoEnSegundos ? ` en ${exportInfo.construidoEnSegundos} s` : ""}  · check de puerto horneado: ${exportInfo.check_api_url}`);
  if (exportInfo.advertencia) log(`  AVISO:      ${exportInfo.advertencia}`);
  log(`  Datos:      ${c.data}`);
  log(`  Logs:       ${c.logs}`);
  log(`  Manifiesto: ${archivoManifiesto}`);
  log(`  Autoverificación: ${JSON.stringify(comprobaciones)}`);
  log("  Comandos de Tauri sin emular: en el navegador, `window.__SANDBOX_NO_SIMULADO__`.");
  log("=".repeat(72));

  if (args.primerPlano) {
    log("Modo primer plano: Ctrl+C apaga la cápsula.");
    const apagar = async () => { await bajar(capsula, puertos); process.exit(0); };
    process.on("SIGINT", apagar);
    process.on("SIGTERM", apagar);
    await new Promise(() => {});
  }
  return 0;
}

async function mostrarEstado(args, capsula, puertos) {
  const pids = leerPids(capsula);
  const manifiesto = leerJson(path.join(capsula, "manifest.json"));
  log(`Cápsula del agente ${args.agente}  (${capsula})`);
  for (const [nombre, x] of Object.entries(pids?.procesos ?? {})) {
    const vivo = procesoVivo(x.pid) && x.fragmentos.every((f) => (lineaDeComando(x.pid) ?? "").includes(f));
    log(`  ${nombre.padEnd(9)} pid ${x.pid}  ${vivo ? "VIVO" : "muerto"}`);
  }
  if (!pids) log("  sin procesos registrados");
  try {
    const r = await fetch(`http://127.0.0.1:${puertos.back}/health`, { signal: AbortSignal.timeout(3000) });
    log(`  /health   HTTP ${r.status}`);
  } catch {
    log("  /health   sin respuesta");
  }
  if (manifiesto) {
    log(`  commit servido: ${manifiesto.repositorio.commit.slice(0, 10)}  árbol limpio: ${manifiesto.repositorio.arbol_limpio}`);
    log(`  export: ${manifiesto.export.origen}  ${manifiesto.export.advertencia ?? ""}`);
    log(`  app: ${manifiesto.urls.app}`);
  }
  return 0;
}

async function servir(rutaConfig) {
  const cfg = leerJson(rutaConfig);
  if (!cfg) muere(`no puedo leer ${rutaConfig}`);
  const casos = new RegistroDeCasos({
    dirRegistro: cfg.dirRegistro, dirPadre: cfg.dirPadre, archivoSiguiente: cfg.archivoSiguiente,
    versionEsquema: versionDeEsquema(cfg.casesRs),
  });
  const servidor = crearServidor({ ...cfg, casos });
  servidor.on("error", (e) => { console.error(`el servidor no pudo escuchar: ${e.message}`); process.exit(1); });
  servidor.listen(cfg.puertoFront, "127.0.0.1", () => console.log(`servidor del export escuchando en 127.0.0.1:${cfg.puertoFront}`));
}

async function main() {
  if (process.platform !== "win32") muere("la cápsula sólo está implementada para Windows (python.exe, taskkill, PowerShell).");
  const args = parseArgs(process.argv.slice(2));
  if (args.ayuda) { log(AYUDA); return 0; }
  if (args.accion === "servir") { await servir(args.servirConfig); return null; } // sigue vivo
  const puertos = puertosDe(args.agente);
  const capsula = rutaCapsula(args);
  if (args.accion === "estado") return mostrarEstado(args, capsula, puertos);
  if (args.accion === "down") {
    log(`Apagando la cápsula del agente ${args.agente}…`);
    await bajar(capsula, puertos);
    if (args.limpiar) retirarEnlaces(capsula);
    return 0;
  }
  return levantar(args);
}

main().then(
  (codigo) => { if (codigo !== null) process.exit(codigo); },
  (e) => {
    console.error(e instanceof ErrorDeCapsula ? `\nERROR: ${e.message}` : `\nERROR inesperado: ${e.stack ?? e}`);
    process.exit(1);
  },
);
