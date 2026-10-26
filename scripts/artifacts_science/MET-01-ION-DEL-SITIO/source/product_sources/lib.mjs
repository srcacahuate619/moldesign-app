// scripts/qa_sandbox/lib.mjs
// =============================================================================
// Funciones PURAS de la cápsula de QA. Nada aquí arranca procesos ni abre
// puertos: así las pruebas (`sandbox.test.mjs`) pueden ejercerlas sin montar
// nada, y `sandbox-up.mjs` queda como el único sitio con efectos.
//
// Qué es una cápsula: un backend + un frontend + datos propios, con un puerto y
// una carpeta por agente, para que dos auditores usen la app a la vez sin
// pisarse. Ver `README.md` para lo que replica de la aplicación instalada y lo
// que NO.
// =============================================================================

import fs from "node:fs";
import path from "node:path";

export const AGENTE_MIN = 1;
export const AGENTE_MAX = 9;
export const MARCA_CAPSULA = ".capsula-moldesign";
export const RUTA_SHIM = "/__sandbox_tauri_shim.js";

/**
 * Puertos de una cápsula. Quedan FUERA de 8000-8019 (el rango que Rust
 * reserva para el backend de la app instalada), de 3000/3001 (los únicos
 * orígenes que el backend trae en CORS) y de los fijos de los sidecars
 * (8001, 8100, 8300, 8400).
 */
export function puertosDe(agente) {
  if (!Number.isInteger(agente) || agente < AGENTE_MIN || agente > AGENTE_MAX) {
    throw new Error(`--agente debe ser un entero entre ${AGENTE_MIN} y ${AGENTE_MAX}.`);
  }
  return { back: 18010 + agente, front: 13010 + agente, llama: 18110 + agente };
}

export function origenDe(puertos) {
  return `http://localhost:${puertos.front}`;
}

const BANDERAS_CON_VALOR = new Set(["--agente", "--out", "--capsula", "--vina-cpu", "--_servir"]);
const BANDERAS_BOOLEANAS = new Set([
  "--down", "--estado", "--reset", "--rebuild", "--no-build", "--limpiar", "--primer-plano", "--help",
]);

export function parseArgs(argv) {
  const r = {
    agente: null, accion: "up", reset: false, rebuild: false, noBuild: false, out: null,
    capsula: null, limpiar: false, primerPlano: false, vinaCpu: 4, servirConfig: null, ayuda: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (BANDERAS_CON_VALOR.has(a)) {
      const v = argv[++i];
      if (v === undefined || v.startsWith("--")) throw new Error(`${a} necesita un valor.`);
      if (a === "--agente") r.agente = Number(v);
      else if (a === "--out") r.out = v;
      else if (a === "--capsula") r.capsula = v;
      else if (a === "--vina-cpu") {
        r.vinaCpu = Number(v);
        if (!Number.isInteger(r.vinaCpu) || r.vinaCpu < 1) throw new Error("--vina-cpu debe ser un entero >= 1.");
      } else if (a === "--_servir") { r.accion = "servir"; r.servirConfig = v; }
    } else if (BANDERAS_BOOLEANAS.has(a)) {
      if (a === "--down") r.accion = "down";
      else if (a === "--estado") r.accion = "estado";
      else if (a === "--reset") r.reset = true;
      else if (a === "--rebuild") r.rebuild = true;
      else if (a === "--no-build") r.noBuild = true;
      else if (a === "--limpiar") r.limpiar = true;
      else if (a === "--primer-plano") r.primerPlano = true;
      else if (a === "--help") r.ayuda = true;
    } else {
      throw new Error(`argumento desconocido: ${a}`);
    }
  }
  if (r.rebuild && r.noBuild) throw new Error("--rebuild y --no-build se contradicen.");
  if (!r.ayuda && r.accion !== "servir") puertosDe(r.agente); // valida --agente
  return r;
}

// --- El servidor estático ----------------------------------------------------

/**
 * Inserta el shim de Tauri como PRIMER elemento de `<head>`. Un script clásico
 * y síncrono se ejecuta antes que los `defer`/`async` del export, que es lo que
 * necesita la app: `isTauriAvailable()` se consulta al cargar el módulo.
 */
export function inyectarShim(html, src = RUTA_SHIM) {
  const etiqueta = `<script src="${src}"></script>`;
  const head = /<head(\s[^>]*)?>/i.exec(html);
  if (head) {
    const i = head.index + head[0].length;
    return html.slice(0, i) + etiqueta + html.slice(i);
  }
  const apertura = /<html(\s[^>]*)?>/i.exec(html);
  if (apertura) {
    const i = apertura.index + apertura[0].length;
    return `${html.slice(0, i)}<head>${etiqueta}</head>${html.slice(i)}`;
  }
  const doctype = /^\s*<!doctype[^>]*>/i.exec(html);
  if (doctype) return html.slice(0, doctype[0].length) + etiqueta + html.slice(doctype[0].length);
  return etiqueta + html;
}

/**
 * Decide qué hacer con una petición al servidor de la cápsula.
 *  - `Host` desconocido -> 421: es la defensa contra DNS rebinding (una página
 *    ajena que resuelva su dominio a 127.0.0.1 no puede leer el shim, que lleva
 *    el secreto del backend).
 *  - `127.0.0.1:<puerto>` se redirige a `localhost:<puerto>`: el ORIGEN es lo
 *    que lleva CORS y `localStorage`; dos orígenes para la misma app producen
 *    estados duplicados y un CORS que falla sin motivo aparente.
 *  - Lo que lleva secretos o ejecuta comandos (`/__sandbox*`) sólo se sirve a
 *    peticiones del propio origen.
 */
export function evaluarPeticion({ host, secFetchSite, url }, puertoFront) {
  const permitido = `localhost:${puertoFront}`;
  if (host === `127.0.0.1:${puertoFront}`) {
    return { accion: "redirigir", location: `http://${permitido}${url}` };
  }
  if (host !== permitido) return { accion: "rechazar", status: 421, motivo: "Host no permitido" };
  const ruta = (url || "/").split("?")[0];
  if (ruta.startsWith("/__sandbox")) {
    const ok = secFetchSite === undefined || secFetchSite === "same-origin" || secFetchSite === "none";
    if (!ok) return { accion: "rechazar", status: 403, motivo: "sólo del propio origen" };
  }
  return { accion: "servir" };
}

/**
 * Ruta de `urlPath` DENTRO de `raiz`, o `null` si se sale. El smoke de
 * producción une `raiz` con la URL tal cual; aquí el servidor escucha en un
 * puerto fijo durante días y no puede permitirse leer `..\..\algo`.
 */
export function rutaSegura(raiz, urlPath) {
  let decodificada;
  try {
    decodificada = decodeURIComponent((urlPath || "/").split("?")[0].split("#")[0]);
  } catch {
    return null;
  }
  // `:` abre flujos alternativos de NTFS (`archivo::$DATA`); ninguna ruta
  // legítima del export lo lleva.
  if (decodificada.includes("\0") || decodificada.includes(":")) return null;
  const base = path.resolve(raiz);
  const abs = path.resolve(base, "." + path.sep + decodificada.replace(/^[\\/]+/, ""));
  if (abs !== base && !abs.startsWith(base + path.sep)) return null;
  return abs;
}

/**
 * Sustituto de `window.__TAURI__` para un navegador. Contesta lo que Rust
 * contestaría sobre el backend y reenvía el resto al servidor de la cápsula
 * (que emula los comandos de casos). Todo comando que NADIE emula queda anotado
 * en `window.__SANDBOX_NO_SIMULADO__`: la lista de lo que este montaje no
 * ejerce, para que no se confunda con un defecto de la app.
 *
 * Los errores se lanzan como CADENA, no como `Error`: Tauri rechaza con el
 * `String` del `Err(...)` de Rust, y el código de la app lo trata así
 * (`/^([A-Z_]+):\s*(.*)$/` sobre el texto).
 */
export function generarShim({ puertoBackend, token }) {
  return `(function () {
  "use strict";
  var PUERTO = ${JSON.stringify(puertoBackend)};
  var TOKEN = ${JSON.stringify(token)};
  var noSimulado = (window.__SANDBOX_NO_SIMULADO__ = window.__SANDBOX_NO_SIMULADO__ || []);
  var estado = { state: "ready", port: PUERTO, detail: null };
  async function remoto(cmd, args) {
    var r = await fetch("/__sandbox/invoke", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ cmd: cmd, args: args || {} }),
      cache: "no-store"
    });
    var j = null;
    try { j = await r.json(); } catch (e) {}
    if (!r.ok) {
      if (j && j.noSimulado) {
        if (noSimulado.indexOf(cmd) < 0) noSimulado.push(cmd);
        console.warn("[sandbox] comando de Tauri no emulado: " + cmd);
      }
      throw (j && j.error) || ("[sandbox] HTTP " + r.status);
    }
    return j.resultado;
  }
  window.__TAURI_INTERNALS__ = {};
  window.__TAURI__ = {
    core: {
      invoke: async function (cmd, args) {
        if (cmd === "ensure_backend" || cmd === "restart_backend" || cmd === "backend_status") return estado;
        if (cmd === "backend_launch_token") return TOKEN;
        return remoto(cmd, args);
      }
    },
    event: { listen: async function () { return function () {}; } }
  };
})();
`;
}

// --- El entorno del backend --------------------------------------------------

/** Copia de `base` sin las claves de `nombres` (sin distinguir mayúsculas: en Windows `Path` y `PATH` son la misma). */
export function sinClaves(base, nombres) {
  const fuera = new Set(nombres.map((n) => n.toLowerCase()));
  return Object.fromEntries(Object.entries(base).filter(([k]) => !fuera.has(k.toLowerCase())));
}

/** Carpetas de una cápsula. Una sola definición: el lanzador, el reset y las pruebas la comparten. */
export function carpetasDe(capsula) {
  return {
    raiz: capsula,
    data: path.join(capsula, "data"),
    logs: path.join(capsula, "logs"),
    tmp: path.join(capsula, "tmp"),
    install: path.join(capsula, "install"),
    casos: path.join(capsula, "casos"),
    registroCasos: path.join(capsula, "registro-casos"),
    home: path.join(capsula, "home"),
    appdata: path.join(capsula, "home", "AppData", "Roaming"),
    localappdata: path.join(capsula, "home", "AppData", "Local"),
  };
}

/** Las que `--reset` vacía. `logs` NO: es la evidencia de la sesión anterior. */
export const CARPETAS_DE_RESET = ["data", "tmp", "install", "casos", "registroCasos", "home"];

/**
 * Entorno del backend. Replica el de `src-tauri/src/backend.rs` (`spawn_backend`)
 * y añade el aislamiento que la app instalada no necesita porque sólo hay una.
 *
 * Desviaciones deliberadas respecto de Rust, todas declaradas en el manifiesto:
 *  - NO se fija `PYTHONDONTWRITEBYTECODE`: el backend corre desde el árbol, sin
 *    el bytecode precompilado del bundle, y sin caché cada arranque tardaría
 *    decenas de segundos.
 *  - El PERFIL de usuario se redirige a la cápsula. `LOCAL_DATA_DIR` no basta:
 *    `provider_config_store` escribe en `~\\.moldesign` sin consultar ningún
 *    ajuste. La consecuencia buena es que el backend ve un usuario NUEVO, que es
 *    lo que ve quien instala la app por primera vez.
 *  - `SECRET_KEY` no se fija por lo mismo: el backend la crea en el perfil de la
 *    cápsula, como hace al primer arranque de verdad.
 */
export function entornoBackend({ base, repoRoot, runtimeRoot, capsula, puertos, token, vinaCpu }) {
  const c = carpetasDe(capsula);
  const limpio = sinClaves(base, [
    "MOLDESIGN_TESTING", "LOCAL_DATA_DIR", "SECRET_KEY", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT",
    "VIRTUAL_ENV", "CONDA_PREFIX", "VINA_CPU", "VINA_TEMP_DIR", "CORS_ORIGINS", "LLAMA_SERVER_PORT",
    "MOLDESIGN_RECURSOS", "MOLDESIGN_INSTALL_DIR", "MOLDESIGN_LOG_DIR", "MOLDESIGN_LAUNCH_TOKEN", "MOLDESIGN_MOLCY_DIR",
    "MOLDESIGN_CASE_REGISTRY", "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
  ]);
  const unidad = path.parse(c.home).root.replace(/[\\/]+$/, "");
  return {
    ...limpio,
    APP_MODE: "DESKTOP",
    ENVIRONMENT: "production",
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    PYTHONPATH: path.join(repoRoot, "backend"),
    TABPFN_NO_BROWSER: "true",
    MOLDESIGN_LAUNCH_TOKEN: token,
    MOLDESIGN_INSTALL_DIR: c.install,
    MOLDESIGN_RECURSOS: runtimeRoot,
    VINA_EXECUTABLE_PATH: path.join(runtimeRoot, "tools", "vina", "vina.exe"),
    MOLDESIGN_OPENBABEL_DIR: path.join(runtimeRoot, "tools", "openbabel"),
    // El motor Molcy está VERSIONADO en el repositorio (tools/molcy): la cápsula corre el backend del repositorio, así que apunta a SU
    // copia y no a la del runtime compartido, que puede ser de otro árbol.
    MOLDESIGN_MOLCY_DIR: path.join(repoRoot, "tools", "molcy"),
    // Rust le pasa el registro de casos autorizados (`backend.rs`, `CASE_REGISTRY_PATH`); sin él Molcy no ve el caso de una corrida.
    MOLDESIGN_CASE_REGISTRY: path.join(c.registroCasos, "authorized_cases.json"),
    LOCAL_DATA_DIR: c.data,
    MOLDESIGN_LOG_DIR: c.logs,
    VINA_CPU: String(vinaCpu),
    CORS_ORIGINS: JSON.stringify([origenDe(puertos)]),
    LLAMA_SERVER_PORT: String(puertos.llama),
    USERPROFILE: c.home,
    HOME: c.home,
    HOMEDRIVE: unidad,
    HOMEPATH: c.home.slice(unidad.length),
    APPDATA: c.appdata,
    LOCALAPPDATA: c.localappdata,
    TEMP: c.tmp,
    TMP: c.tmp,
    TMPDIR: c.tmp,
  };
}

// --- Borrado seguro ----------------------------------------------------------

/**
 * ¿Se puede vaciar esta carpeta de cápsula? `--reset` borra recursivamente, así
 * que no basta con que la ruta "parezca" una cápsula: tiene que llevar la marca
 * que escribió el lanzador y no puede ser —ni contener— nada que importe.
 *
 * `protegidas`: rutas que ni pueden quedar dentro de lo borrado NI contener la
 * cápsula (el árbol del repositorio, el runtime compartido). `noContener`: rutas
 * que la cápsula puede tener por encima pero que jamás puede ser ni contener (el
 * perfil real del usuario: una cápsula temporal vive dentro de él).
 */
export function esCapsulaBorrable(dir, { protegidas = [], noContener = [] } = {}) {
  if (typeof dir !== "string" || !path.isAbsolute(dir)) return { ok: false, motivo: "la ruta no es absoluta" };
  const d = path.resolve(dir);
  const partes = d.split(path.sep).filter(Boolean);
  if (partes.length < 3) return { ok: false, motivo: "la ruta es demasiado superficial" };
  let marca;
  try {
    marca = fs.statSync(path.join(d, MARCA_CAPSULA));
  } catch {
    return { ok: false, motivo: `falta la marca ${MARCA_CAPSULA}: no es una cápsula creada por el lanzador` };
  }
  if (!marca.isFile()) return { ok: false, motivo: `${MARCA_CAPSULA} no es un archivo` };
  for (const p of protegidas.filter(Boolean)) {
    const q = path.resolve(p);
    if (q === d || q.startsWith(d + path.sep)) {
      return { ok: false, motivo: `contiene o es una ruta protegida: ${q}` };
    }
    if (d.startsWith(q + path.sep)) {
      return { ok: false, motivo: `está dentro de una ruta protegida: ${q}` };
    }
  }
  for (const p of noContener.filter(Boolean)) {
    const q = path.resolve(p);
    if (q === d || q.startsWith(d + path.sep)) {
      return { ok: false, motivo: `es o contiene una ruta que no se puede borrar: ${q}` };
    }
  }
  return { ok: true, motivo: "" };
}

// --- Prueba de aislamiento ---------------------------------------------------

/**
 * Foto de una carpeta: ruta relativa -> "tamaño:mtime". Sólo `stat`, nunca
 * contenido: `~\\MolDesign\\models` pesa gigas y la foto tiene que ser barata.
 * Una carpeta inexistente da un mapa vacío; eso también es una foto válida.
 */
export function instantanea(dir, { limite = 300000 } = {}) {
  const fotos = new Map();
  const visitar = (actual, rel) => {
    let entradas;
    try {
      entradas = fs.readdirSync(actual, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entradas) {
      if (fotos.size >= limite) throw new Error(`instantanea: más de ${limite} entradas en ${dir}`);
      const r = rel ? `${rel}/${e.name}` : e.name;
      const abs = path.join(actual, e.name);
      if (e.isDirectory()) {
        fotos.set(`${r}/`, "dir");
        visitar(abs, r);
      } else {
        try {
          const s = fs.statSync(abs);
          fotos.set(r, `${s.size}:${Math.round(s.mtimeMs)}`);
        } catch {
          fotos.set(r, "ilegible");
        }
      }
    }
  };
  visitar(dir, "");
  return fotos;
}

export function diferencias(antes, despues) {
  const nuevos = [];
  const borrados = [];
  const cambiados = [];
  for (const [k, v] of despues) {
    if (!antes.has(k)) nuevos.push(k);
    else if (antes.get(k) !== v) cambiados.push(k);
  }
  for (const k of antes.keys()) if (!despues.has(k)) borrados.push(k);
  return { nuevos, borrados, cambiados };
}

export function hayDiferencias(d) {
  return d.nuevos.length + d.borrados.length + d.cambiados.length > 0;
}
