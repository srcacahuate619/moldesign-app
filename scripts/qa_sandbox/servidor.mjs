// scripts/qa_sandbox/servidor.mjs
// =============================================================================
// Servidor de la cápsula: sirve el export estático (`frontend/out`) con la CSP
// de producción, inyecta el shim de Tauri y contesta los comandos de Tauri que
// un navegador no tiene (`POST /__sandbox/invoke`).
//
// Es lo más parecido a la app instalada que se puede montar sin instalarla, con
// las diferencias que `README.md` enumera. La principal: se sirve desde
// `http://localhost:<puerto>` y no desde `http://tauri.localhost`, así que la
// política de CORS de producción para el origen de Tauri NO se ejerce aquí.
// =============================================================================

import { createServer } from "node:http";
import fs from "node:fs";
import path from "node:path";
import { evaluarPeticion, generarShim, inyectarShim, rutaSegura, RUTA_SHIM } from "./lib.mjs";
import { RegistroDeCasos, ErrorDeRust } from "./casos.mjs";

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

const MAX_CUERPO = 8 * 1024 * 1024;

function responder(res, status, cuerpo, cabeceras = {}) {
  res.writeHead(status, { "cache-control": "no-store", ...cabeceras });
  res.end(cuerpo);
}

function json(res, status, objeto) {
  responder(res, status, JSON.stringify(objeto), { "content-type": "application/json; charset=utf-8" });
}

function leerCuerpo(req) {
  return new Promise((resolve, reject) => {
    const trozos = [];
    let total = 0;
    req.on("data", (t) => {
      total += t.length;
      if (total > MAX_CUERPO) {
        reject(new Error("cuerpo demasiado grande"));
        req.destroy();
        return;
      }
      trozos.push(t);
    });
    req.on("end", () => resolve(Buffer.concat(trozos).toString("utf8")));
    req.on("error", reject);
  });
}

/** Localiza el archivo de `<raiz>/<ruta>` como lo hace el router estático de Tauri. */
function resolverArchivo(raiz, urlPath) {
  let rel = urlPath.split("?")[0];
  if (rel.endsWith("/")) rel += "index.html";
  const abs = rutaSegura(raiz, rel);
  if (!abs) return null;
  const esArchivo = (p) => fs.statSync(p, { throwIfNoEntry: false })?.isFile();
  const esDir = (p) => fs.statSync(p, { throwIfNoEntry: false })?.isDirectory();
  if (esArchivo(abs)) return abs;
  if (esDir(abs)) {
    // Next 16 crea directorios RSC junto a `<ruta>.html`: sólo se usa
    // `index.html` cuando existe de verdad.
    if (esArchivo(path.join(abs, "index.html"))) return path.join(abs, "index.html");
    if (esArchivo(`${abs}.html`)) return `${abs}.html`;
    return null;
  }
  if (esArchivo(`${abs}.html`)) return `${abs}.html`;
  return null;
}

/** Comandos de Tauri que NO son de casos y que la cápsula sabe contestar. */
function comandoDeSistema(cmd, args, ctx) {
  const dentroDeRaices = (p) => {
    if (typeof p !== "string" || !path.isAbsolute(p)) return false;
    const q = path.resolve(p);
    return ctx.raicesLegibles.some((r) => q === path.resolve(r) || q.startsWith(path.resolve(r) + path.sep));
  };
  switch (cmd) {
    case "get_resource_dir":
      return { ok: true, resultado: ctx.runtimeRoot };
    // `verify_model` en Rust comprueba el SHA-256; aquí sólo la existencia (hashear 8,4 GB en
    // cada carga de página distorsionaría lo que se audita). Queda declarado en el README.
    case "file_exists":
    case "verify_model":
      if (!dentroDeRaices(args?.dest)) return { ok: false, status: 403, error: "UNAUTHORIZED: ruta fuera de las carpetas que la cápsula puede consultar." };
      return { ok: true, resultado: fs.existsSync(args.dest) };
    default:
      return null;
  }
}

/**
 * @param {object} cfg
 * @param {string} cfg.outDir          export estático a servir
 * @param {string} cfg.csp             CSP de producción
 * @param {number} cfg.puertoFront
 * @param {number} cfg.puertoBack
 * @param {string} cfg.token           `MOLDESIGN_LAUNCH_TOKEN` del backend de esta cápsula
 * @param {string} cfg.runtimeRoot
 * @param {string[]} cfg.raicesLegibles
 * @param {RegistroDeCasos} cfg.casos
 * @param {string} [cfg.archivoManifiesto]
 * @param {string} [cfg.archivoNoEmulados]
 */
export function crearServidor(cfg) {
  const ctx = { runtimeRoot: cfg.runtimeRoot, raicesLegibles: cfg.raicesLegibles ?? [cfg.runtimeRoot] };

  return createServer(async (req, res) => {
    try {
      const decision = evaluarPeticion(
        { host: req.headers.host, secFetchSite: req.headers["sec-fetch-site"], url: req.url },
        cfg.puertoFront,
      );
      if (decision.accion === "redirigir") return responder(res, 308, "", { location: decision.location });
      if (decision.accion === "rechazar") return responder(res, decision.status, decision.motivo, { "content-type": "text/plain; charset=utf-8" });

      const ruta = (req.url || "/").split("?")[0];

      if (ruta === RUTA_SHIM) {
        return responder(res, 200, generarShim({ puertoBackend: cfg.puertoBack, token: cfg.token }), {
          "content-type": TIPOS[".js"],
        });
      }

      if (ruta === "/__sandbox/manifest.json") {
        try {
          return responder(res, 200, fs.readFileSync(cfg.archivoManifiesto), { "content-type": TIPOS[".json"] });
        } catch {
          return json(res, 404, { error: "la cápsula aún no escribió su manifiesto" });
        }
      }

      if (ruta === "/__sandbox/invoke") {
        if (req.method !== "POST") return json(res, 405, { error: "sólo POST" });
        let cuerpo;
        try {
          cuerpo = JSON.parse(await leerCuerpo(req));
        } catch (e) {
          return json(res, 400, { error: `IO_ERROR: petición ilegible (${e.message})` });
        }
        const { cmd, args } = cuerpo ?? {};
        if (typeof cmd !== "string") return json(res, 400, { error: "IO_ERROR: falta `cmd`." });
        if (RegistroDeCasos.comandos.includes(cmd)) {
          try {
            return json(res, 200, { resultado: cfg.casos.invocar(cmd, args ?? {}) ?? null });
          } catch (e) {
            if (e instanceof ErrorDeRust) return json(res, 400, { error: e.message });
            return json(res, 500, { error: `IO_ERROR: ${e.message}` });
          }
        }
        const sistema = comandoDeSistema(cmd, args, ctx);
        if (sistema) {
          return sistema.ok ? json(res, 200, { resultado: sistema.resultado }) : json(res, sistema.status, { error: sistema.error });
        }
        if (cfg.archivoNoEmulados) {
          try { fs.appendFileSync(cfg.archivoNoEmulados, `${new Date().toISOString()} ${cmd}\n`); } catch { /* el registro es ayuda, no requisito */ }
        }
        return json(res, 501, { noSimulado: true, error: `[sandbox] comando de Tauri no emulado: ${cmd}` });
      }

      if (req.method !== "GET" && req.method !== "HEAD") return responder(res, 405, "método no permitido");
      const archivo = resolverArchivo(cfg.outDir, req.url || "/");
      if (!archivo) return responder(res, 404, "no encontrado", { "content-type": "text/plain; charset=utf-8" });

      const ext = path.extname(archivo).toLowerCase();
      const tipo = TIPOS[ext] || "application/octet-stream";
      if (ext === ".html") {
        const html = inyectarShim(fs.readFileSync(archivo, "utf8"));
        // La CSP viaja SOLO con el documento, igual que la pone el WebView.
        return responder(res, 200, req.method === "HEAD" ? "" : html, { "content-type": tipo, "content-security-policy": cfg.csp });
      }
      return responder(res, 200, req.method === "HEAD" ? "" : fs.readFileSync(archivo), { "content-type": tipo });
    } catch (e) {
      return responder(res, 500, `error interno de la cápsula: ${e.message}`, { "content-type": "text/plain; charset=utf-8" });
    }
  });
}
