// scripts/qa_sandbox/sandbox.test.mjs
// =============================================================================
// Pruebas de la cápsula de QA. `node --test scripts/qa_sandbox/`
//
// Una guardia tiene que demostrar que VE (restricción 2 del AGENTS.md): cada
// bloque trae muestras que deben saltar y muestras que no. Un detector que sólo
// se ha visto decir «limpio» no ha demostrado nada.
// =============================================================================

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import net from "node:net";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import {
  MARCA_CAPSULA, carpetasDe, diferencias, entornoBackend, esCapsulaBorrable, evaluarPeticion, generarShim,
  hayDiferencias, inyectarShim, instantanea, parseArgs, puertosDe, rutaSegura,
} from "./lib.mjs";
import { ErrorDeRust, RegistroDeCasos, validarManifiesto, validarNombreDeCarpeta, versionDeEsquema } from "./casos.mjs";
import { crearServidor } from "./servidor.mjs";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const CASES_RS = path.resolve(AQUI, "..", "..", "frontend", "src-tauri", "src", "cases.rs");

const temporal = (prefijo) => fs.mkdtempSync(path.join(os.tmpdir(), `qa-sandbox-${prefijo}-`));
const limpiar = (d) => fs.rmSync(d, { recursive: true, force: true });

// --- puertos y argumentos --------------------------------------------------------

test("los puertos de cada cápsula quedan fuera de todo lo reservado y no se solapan", () => {
  const reservados = new Set([3000, 3001, 8001, 8100, 8300, 8400]);
  const vistos = new Set();
  for (let n = 1; n <= 9; n++) {
    const p = puertosDe(n);
    for (const v of Object.values(p)) {
      assert.ok(!(v >= 8000 && v <= 8019), `${v} cae en el rango que Rust reserva para el backend instalado`);
      assert.ok(!reservados.has(v), `${v} es un puerto reservado`);
      assert.ok(!vistos.has(v), `${v} se repite entre cápsulas`);
      vistos.add(v);
    }
  }
  assert.deepEqual(puertosDe(2), { back: 18012, front: 13012, llama: 18112 });
});

test("--agente fuera de rango o no entero se rechaza", () => {
  for (const malo of [0, 10, 2.5, -1, NaN, null, undefined]) {
    assert.throws(() => puertosDe(malo), /--agente/, `debió rechazar ${malo}`);
  }
});

test("parseArgs: lo normal, los valores por defecto y los errores", () => {
  assert.deepEqual(
    { ...parseArgs(["--agente", "2"]) },
    { agente: 2, accion: "up", reset: false, rebuild: false, noBuild: false, out: null, capsula: null, limpiar: false, primerPlano: false, vinaCpu: 4, servirConfig: null, ayuda: false },
  );
  assert.equal(parseArgs(["--agente", "1", "--down", "--limpiar"]).accion, "down");
  assert.equal(parseArgs(["--agente", "3", "--vina-cpu", "6"]).vinaCpu, 6);
  assert.equal(parseArgs(["--_servir", "x.json"]).accion, "servir");
  assert.throws(() => parseArgs(["--agente", "2", "--nada"]), /desconocido/);
  assert.throws(() => parseArgs(["--agente"]), /necesita un valor/);
  assert.throws(() => parseArgs(["--agente", "--down"]), /necesita un valor/);
  assert.throws(() => parseArgs([]), /--agente/);
  assert.throws(() => parseArgs(["--agente", "2", "--rebuild", "--no-build"]), /contradicen/);
  assert.throws(() => parseArgs(["--agente", "2", "--vina-cpu", "0"]), /--vina-cpu/);
});

// --- el shim en el HTML -----------------------------------------------------------

test("inyectarShim: el script queda como PRIMER hijo de <head>, con o sin atributos", () => {
  const etiqueta = '<script src="/__sandbox_tauri_shim.js"></script>';
  assert.equal(inyectarShim("<!DOCTYPE html><html><head><meta charSet=utf-8></head></html>"),
    `<!DOCTYPE html><html><head>${etiqueta}<meta charSet=utf-8></head></html>`);
  assert.match(inyectarShim('<html lang="es"><head data-x="1"><title>t</title></head>'), new RegExp(`<head data-x="1">${etiqueta.replace(/[/.]/g, "\\$&")}<title>`));
});

test("inyectarShim: sin <head> lo crea; sin <html> lo antepone; no confunde <header> con <head>", () => {
  const etiqueta = '<script src="/__sandbox_tauri_shim.js"></script>';
  assert.equal(inyectarShim("<html><body>x</body></html>"), `<html><head>${etiqueta}</head><body>x</body></html>`);
  assert.equal(inyectarShim("<p>fragmento</p>"), `${etiqueta}<p>fragmento</p>`);
  const conHeader = inyectarShim("<html><body><header>h</header></body></html>");
  assert.ok(conHeader.startsWith(`<html><head>${etiqueta}</head>`), "un <header> no es un <head>");
});

// --- política de red del servidor ---------------------------------------------------

test("evaluarPeticion: Host, redirección a localhost y rutas sensibles", () => {
  const P = 13012;
  const e = (host, url = "/", secFetchSite) => evaluarPeticion({ host, secFetchSite, url }, P);
  assert.equal(e(`localhost:${P}`).accion, "servir");
  assert.deepEqual(e(`127.0.0.1:${P}`, "/historial?x=1"), { accion: "redirigir", location: `http://localhost:${P}/historial?x=1` });
  assert.equal(e("evil.example").status, 421);
  assert.equal(e(`localhost:${P + 1}`).status, 421, "otro puerto, otro servidor");
  assert.equal(e(undefined).status, 421);
  // Muestras que DEBEN rechazarse:
  for (const sitio of ["cross-site", "same-site"]) {
    assert.equal(e(`localhost:${P}`, "/__sandbox_tauri_shim.js", sitio).status, 403, `shim con ${sitio}`);
    assert.equal(e(`localhost:${P}`, "/__sandbox/invoke", sitio).status, 403, `invoke con ${sitio}`);
    assert.equal(e(`localhost:${P}`, "/__sandbox/manifest.json?a=b", sitio).status, 403, `manifest con ${sitio}`);
  }
  // Muestras que NO deben rechazarse:
  for (const sitio of [undefined, "same-origin", "none"]) {
    assert.equal(e(`localhost:${P}`, "/__sandbox_tauri_shim.js", sitio).accion, "servir", `shim con ${sitio}`);
  }
  assert.equal(e(`localhost:${P}`, "/index.html", "cross-site").accion, "servir", "el HTML no lleva secretos");
});

test("rutaSegura: lo que sale de la raíz, no; lo que está dentro, sí", () => {
  const raiz = temporal("ruta");
  try {
    for (const mala of ["/../x", "/%2e%2e/x", "/..%5cx", "/a/../../x", "/a/%2e%2e/%2e%2e/x", "/x%00.html", "/archivo::$DATA", "/C:/Windows/win.ini", "/%E0%A4%A"]) {
      assert.equal(rutaSegura(raiz, mala), null, `debió rechazar ${mala}`);
    }
    for (const buena of ["/", "/index.html", "/_next/static/a.js", "/a/../index.html", "/x?y=1", "/historial/"]) {
      const r = rutaSegura(raiz, buena);
      assert.ok(r && (r === raiz || r.startsWith(raiz + path.sep)), `${buena} debió resolverse dentro de la raíz (${r})`);
    }
  } finally {
    limpiar(raiz);
  }
});

// --- el shim de Tauri ejecutado de verdad ---------------------------------------------

test("el shim contesta lo del backend, reenvía lo demás y anota lo no emulado", async () => {
  const llamadas = [];
  const ventana = {};
  const contexto = vm.createContext({
    window: ventana,
    console: { warn() {} },
    fetch: async (url, opciones) => {
      const { cmd } = JSON.parse(opciones.body);
      llamadas.push({ url, cmd });
      if (cmd === "case_read") return { ok: true, status: 200, json: async () => ({ resultado: { case_id: "c1" } }) };
      if (cmd === "case_create") return { ok: false, status: 400, json: async () => ({ error: "UNSAFE_NAME: vacío" }) };
      return { ok: false, status: 501, json: async () => ({ noSimulado: true, error: `[sandbox] comando de Tauri no emulado: ${cmd}` }) };
    },
  });
  vm.runInContext(generarShim({ puertoBackend: 18012, token: "tok-secreto" }), contexto);
  const invoke = ventana.__TAURI__.core.invoke;
  // Los objetos nacen en otro realm de `vm`: se comparan por JSON, no por prototipo.
  const comoJson = (v) => JSON.parse(JSON.stringify(v));
  assert.deepEqual(comoJson(await invoke("ensure_backend")), { state: "ready", port: 18012, detail: null });
  assert.deepEqual(comoJson(await invoke("restart_backend")), { state: "ready", port: 18012, detail: null });
  assert.equal(await invoke("backend_launch_token"), "tok-secreto");
  assert.equal(llamadas.length, 0, "lo del backend no sale a la red");
  assert.deepEqual(comoJson(await invoke("case_read", { caseId: "x" })), { case_id: "c1" });
  // El error de Rust llega como CADENA con prefijo, que es lo que parsea la app.
  await assert.rejects(invoke("case_create", {}), (e) => e === "UNSAFE_NAME: vacío");
  await assert.rejects(invoke("download_model", {}), (e) => typeof e === "string" && e.includes("no emulado"));
  assert.deepEqual([...ventana.__SANDBOX_NO_SIMULADO__], ["download_model"]);
  assert.ok("__TAURI_INTERNALS__" in ventana, "isDesktopRuntime() mira __TAURI_INTERNALS__");
});

// --- el entorno del backend -------------------------------------------------------------

test("entornoBackend aísla datos, perfil y temporales, y no hereda lo que contaminaría", () => {
  const capsula = path.join("D:\\", "moldesign-worktrees", ".sandbox", "agente2");
  const base = { PATH: "C:\\Windows", Userprofile: "C:\\Users\\real", MOLDESIGN_TESTING: "1", LOCAL_DATA_DIR: "C:\\real", secret_key: "x", SECRET_KEY: "y", CORS_ORIGINS: '["*"]', TEMP: "C:\\T" };
  const env = entornoBackend({
    base, repoRoot: "D:\\moldesign-worktrees\\sandbox-agente2", runtimeRoot: "D:\\moldesign-build", capsula,
    puertos: puertosDe(2), token: "abc", vinaCpu: 4,
  });
  const c = carpetasDe(capsula);
  assert.equal(env.PATH, "C:\\Windows", "lo neutro se hereda");
  assert.equal(env.MOLDESIGN_TESTING, undefined, "MOLDESIGN_TESTING cambiaría el almacén de datos");
  assert.equal(env.SECRET_KEY, undefined, "la clave la crea el backend en el perfil de la cápsula, como en el primer arranque real");
  assert.equal(env.LOCAL_DATA_DIR, c.data);
  assert.equal(env.USERPROFILE, c.home);
  assert.equal(env.HOME, c.home);
  assert.equal(env.APPDATA, c.appdata);
  assert.equal(env.LOCALAPPDATA, c.localappdata);
  assert.equal(env.TEMP, c.tmp);
  assert.equal(Object.keys(env).filter((k) => k.toLowerCase() === "userprofile").length, 1, "sin duplicados por mayúsculas");
  assert.deepEqual(JSON.parse(env.CORS_ORIGINS), ["http://localhost:13012"], "exactamente el origen del frontend de ESTA cápsula");
  assert.equal(env.LLAMA_SERVER_PORT, "18112");
  assert.equal(env.VINA_CPU, "4");
  assert.equal(env.MOLDESIGN_RECURSOS, "D:\\moldesign-build");
  assert.equal(env.VINA_EXECUTABLE_PATH, path.join("D:\\moldesign-build", "tools", "vina", "vina.exe"));
  assert.equal(env.PYTHONDONTWRITEBYTECODE, undefined, "desviación declarada: el árbol no trae el bytecode del bundle");
  assert.equal(env.MOLDESIGN_MOLCY_DIR, path.join("D:\\moldesign-worktrees\\sandbox-agente2", "tools", "molcy"),
    "el motor Molcy es el del REPOSITORIO de la cápsula (versionado), no el del runtime compartido");
  const heredada = entornoBackend({
    base: { ...base, MOLDESIGN_MOLCY_DIR: "C:\\otro\\motor" }, repoRoot: "R", runtimeRoot: "Z", capsula, puertos: puertosDe(2), token: "t", vinaCpu: 4,
  });
  assert.equal(heredada.MOLDESIGN_MOLCY_DIR, path.join("R", "tools", "molcy"), "una variable del shell no pisa el motor de la cápsula");
  assert.equal(env.MOLDESIGN_CASE_REGISTRY, path.join(c.registroCasos, "authorized_cases.json"),
    "como Rust, el backend lee el registro de casos: sin él Molcy no asocia una corrida a su caso");
  for (const k of ["USERPROFILE", "LOCAL_DATA_DIR", "MOLDESIGN_LOG_DIR", "TEMP", "APPDATA", "LOCALAPPDATA", "MOLDESIGN_INSTALL_DIR", "MOLDESIGN_CASE_REGISTRY"]) {
    assert.ok(env[k].startsWith(capsula + path.sep), `${k}=${env[k]} debe vivir dentro de la cápsula`);
  }
  // Dos cápsulas jamás comparten origen ni puerto.
  const otro = entornoBackend({ base, repoRoot: "x", runtimeRoot: "y", capsula: path.join(path.dirname(capsula), "agente1"), puertos: puertosDe(1), token: "z", vinaCpu: 4 });
  assert.notEqual(otro.CORS_ORIGINS, env.CORS_ORIGINS);
  assert.notEqual(otro.LLAMA_SERVER_PORT, env.LLAMA_SERVER_PORT);
  assert.notEqual(otro.LOCAL_DATA_DIR, env.LOCAL_DATA_DIR);
});

// --- borrado seguro ------------------------------------------------------------------------

test("esCapsulaBorrable: sólo una carpeta con la marca, que no sea ni contenga nada protegido", () => {
  const raiz = temporal("borrable");
  try {
    const capsula = path.join(raiz, "ws", ".sandbox", "agente1");
    fs.mkdirSync(capsula, { recursive: true });
    // Sin marca: NO.
    assert.equal(esCapsulaBorrable(capsula).ok, false);
    assert.match(esCapsulaBorrable(capsula).motivo, /marca/);
    fs.writeFileSync(path.join(capsula, MARCA_CAPSULA), "x");
    // Con marca: SÍ.
    assert.equal(esCapsulaBorrable(capsula).ok, true);
    // Relativa, demasiado superficial, o marca que es una carpeta: NO.
    assert.equal(esCapsulaBorrable("agente1").ok, false);
    assert.equal(esCapsulaBorrable(path.parse(raiz).root).ok, false);
    const falsa = path.join(raiz, "ws", "falsa");
    fs.mkdirSync(path.join(falsa, MARCA_CAPSULA), { recursive: true });
    assert.equal(esCapsulaBorrable(falsa).ok, false, "la marca tiene que ser un archivo");
    // Protegidas: ni dentro, ni encima, ni iguales.
    const repo = path.join(raiz, "ws", "sandbox-agente1");
    fs.mkdirSync(repo, { recursive: true });
    assert.equal(esCapsulaBorrable(capsula, { protegidas: [repo] }).ok, true, "un hermano no molesta");
    assert.equal(esCapsulaBorrable(capsula, { protegidas: [capsula] }).ok, false, "es la protegida");
    assert.equal(esCapsulaBorrable(capsula, { protegidas: [path.join(capsula, "data")] }).ok, false, "la protegida está dentro");
    assert.equal(esCapsulaBorrable(capsula, { protegidas: [path.join(raiz, "ws")] }).ok, false, "está dentro de la protegida");
    // noContener: la cápsula puede vivir DENTRO del perfil (un autotest usa %TEMP%), pero no ser ni contener el perfil.
    assert.equal(esCapsulaBorrable(capsula, { noContener: [raiz] }).ok, true, "el perfil está por encima: bien");
    assert.equal(esCapsulaBorrable(capsula, { noContener: [path.join(capsula, "home")] }).ok, false, "contiene el perfil: mal");
  } finally {
    limpiar(raiz);
  }
});

// --- la foto de aislamiento ------------------------------------------------------------------

test("instantanea/diferencias: ve lo nuevo, lo cambiado y lo borrado — y no inventa nada", () => {
  const d = temporal("foto");
  try {
    fs.mkdirSync(path.join(d, "sub"));
    fs.writeFileSync(path.join(d, "a.txt"), "uno");
    fs.writeFileSync(path.join(d, "sub", "b.txt"), "dos");
    const antes = instantanea(d);
    // Control NEGATIVO: sin tocar nada, ninguna diferencia (un detector que siempre salta no vale).
    assert.equal(hayDiferencias(diferencias(antes, instantanea(d))), false);

    fs.writeFileSync(path.join(d, "nuevo.txt"), "n");
    fs.mkdirSync(path.join(d, "carpeta-nueva"));
    fs.writeFileSync(path.join(d, "a.txt"), "uno cambiado");
    fs.rmSync(path.join(d, "sub", "b.txt"));
    const dif = diferencias(antes, instantanea(d));
    assert.deepEqual(dif.nuevos.sort(), ["carpeta-nueva/", "nuevo.txt"]);
    assert.deepEqual(dif.cambiados, ["a.txt"]);
    assert.deepEqual(dif.borrados, ["sub/b.txt"]);
    assert.equal(hayDiferencias(dif), true);
    // Una carpeta inexistente es una foto vacía, no un error.
    assert.equal(instantanea(path.join(d, "no-existe")).size, 0);
  } finally {
    limpiar(d);
  }
});

// --- la emulación de casos -----------------------------------------------------------------------

function registroNuevo(extra = {}) {
  const raiz = temporal("casos");
  const reg = new RegistroDeCasos({
    dirRegistro: path.join(raiz, "registro"), dirPadre: path.join(raiz, "casos"),
    archivoSiguiente: path.join(raiz, "siguiente-carpeta.txt"), versionEsquema: versionDeEsquema(CASES_RS), ...extra,
  });
  return { raiz, reg };
}
const crear = (reg, nombre, dueno = "u1", tipo = "explore-hypothesis") => {
  const { token } = reg.invocar("case_pick_parent_directory");
  return reg.invocar("case_create", { token, folderName: nombre, name: nombre, studyKind: tipo, ownerUserId: dueno });
};
const codigoDe = (fn) => { try { fn(); } catch (e) { return e instanceof ErrorDeRust ? e.codigo : `otro: ${e.message}`; } return "no falló"; };

test("casos: la carpeta por defecto no abre diálogo, ignora siguiente-carpeta.txt y permite crear", () => {
  const { raiz, reg } = registroNuevo();
  try {
    fs.writeFileSync(path.join(raiz, "siguiente-carpeta.txt"), path.join(raiz, "otra"));
    const propuesta = reg.invocar("case_default_parent_directory");
    assert.equal(propuesta.has_manifest, false);
    assert.equal(fs.realpathSync(propuesta.display_path), fs.realpathSync(path.join(raiz, "casos")));
    // El archivo que sustituye al diálogo NO se consume: la carpeta por defecto no es una elección.
    assert.equal(fs.existsSync(path.join(raiz, "siguiente-carpeta.txt")), true);
    const abierto = reg.invocar("case_create", { token: propuesta.token, folderName: "Caso por defecto", name: "Caso por defecto", studyKind: "explore-hypothesis", ownerUserId: "u1" });
    assert.equal(path.dirname(fs.realpathSync(abierto.path)), fs.realpathSync(propuesta.display_path));
    // Control negativo: un token inventado no autoriza nada.
    assert.equal(codigoDe(() => reg.invocar("case_create", { token: "inventado", folderName: "X", name: "X", studyKind: "explore-hypothesis", ownerUserId: "u1" })), "UNAUTHORIZED");
    assert.ok(RegistroDeCasos.comandos.includes("case_default_parent_directory"));
  } finally {
    limpiar(raiz);
  }
});

test("la versión de esquema se LEE de cases.rs, y sin la constante la emulación se niega", () => {
  assert.ok(versionDeEsquema(CASES_RS) >= 7);
  const d = temporal("version");
  try {
    const falso = path.join(d, "cases.rs");
    fs.writeFileSync(falso, "// sin constante\n");
    assert.throws(() => versionDeEsquema(falso), /CURRENT_CASE_SCHEMA_VERSION/);
    fs.writeFileSync(falso, "const CURRENT_CASE_SCHEMA_VERSION: u64 = 9;\n");
    assert.equal(versionDeEsquema(falso), 9);
  } finally {
    limpiar(d);
  }
});

test("casos: crear, leer, listar y persistir entre reinicios", () => {
  const { raiz, reg } = registroNuevo();
  try {
    assert.deepEqual(reg.invocar("case_registry_health"), { state: "first_run" });
    const abierto = crear(reg, "Mi caso", "u1");
    assert.equal(abierto.recovered_from_backup, false);
    const m = validarManifiesto(abierto.manifest, reg.version);
    assert.equal(m.schemaVersion, reg.version);
    assert.equal(m.ownerUserId, "u1");
    assert.equal(m.status, "draft");
    assert.equal(m.activeView, "evaluation");
    for (const sub of ["inputs", "runs", "evidence", "reports", "exports"]) assert.ok(fs.existsSync(path.join(abierto.path, sub)), sub);

    assert.equal(reg.invocar("case_read", { caseId: abierto.case_id, ownerUserId: "u1" }).case_id, abierto.case_id);
    assert.deepEqual(reg.invocar("case_list_authorized", { ownerUserId: "u1" }).map((c) => c.case_id), [abierto.case_id]);
    assert.deepEqual(reg.invocar("case_registry_health"), { state: "ok" });
    // El formato de `PersistedRegistry` (cases.rs): `storage.casos` del backend exige `version: 1`.
    const persistido = JSON.parse(fs.readFileSync(path.join(reg.dirRegistro, "authorized_cases.json"), "utf8"));
    assert.equal(persistido.version, 1);
    assert.deepEqual(Object.keys(persistido.cases), [abierto.case_id]);

    // Un proceso nuevo ve el mismo registro (en Rust persiste en app data).
    const otro = new RegistroDeCasos({ dirRegistro: reg.dirRegistro, dirPadre: reg.dirPadre, archivoSiguiente: reg.archivoSiguiente, versionEsquema: reg.version });
    assert.deepEqual(otro.invocar("case_registry_health"), { state: "ok" });
    assert.deepEqual(otro.invocar("case_list_authorized", { ownerUserId: "u1" }).map((c) => c.case_id), [abierto.case_id]);
  } finally {
    limpiar(raiz);
  }
});

test("casos: nombres de carpeta peligrosos, duplicados y tipos de estudio inválidos se rechazan con su código", () => {
  const { raiz, reg } = registroNuevo();
  try {
    for (const malo of ["", "   ", ".", "..", "a/b", "a\\b", "a:b", "con", "COM1", "x.", "a<b", "a|b", "a\u0007b", "x".repeat(65)]) {
      assert.equal(codigoDe(() => validarNombreDeCarpeta(malo)), "UNSAFE_NAME", `debió rechazar ${JSON.stringify(malo)}`);
    }
    for (const bueno of ["Mi caso", "caso-1", "ACE inhibidores 2026", "x".repeat(64)]) {
      assert.equal(validarNombreDeCarpeta(bueno), bueno);
    }
    crear(reg, "duplicado");
    assert.equal(codigoDe(() => crear(reg, "duplicado")), "ALREADY_EXISTS");
    assert.equal(codigoDe(() => crear(reg, "otro", "u1", "no-existe")), "INVALID_MANIFEST");
    assert.equal(codigoDe(() => reg.invocar("case_create", { token: "token-inventado", folderName: "x", name: "x", studyKind: "review-pose", ownerUserId: "u1" })), "UNAUTHORIZED");
  } finally {
    limpiar(raiz);
  }
});

test("casos: un caso de otra cuenta no se lee, no se escribe y no aparece en la lista", () => {
  const { raiz, reg } = registroNuevo();
  try {
    const ajeno = crear(reg, "de u1", "u1");
    assert.equal(codigoDe(() => reg.invocar("case_read", { caseId: ajeno.case_id, ownerUserId: "u2" })), "UNAUTHORIZED");
    assert.equal(codigoDe(() => reg.invocar("case_read", { caseId: ajeno.case_id, ownerUserId: "" })), "UNAUTHORIZED");
    assert.equal(codigoDe(() => reg.invocar("case_write", { caseId: ajeno.case_id, contents: ajeno.manifest, ownerUserId: "u2" })), "UNAUTHORIZED");
    assert.deepEqual(reg.invocar("case_list_authorized", { ownerUserId: "u2" }), []);
    assert.equal(codigoDe(() => reg.invocar("case_forget", { caseId: ajeno.case_id, ownerUserId: "u2" })), "UNAUTHORIZED");
    assert.equal(codigoDe(() => reg.invocar("case_read", { caseId: "inexistente", ownerUserId: "u1" })), "NOT_FOUND");
  } finally {
    limpiar(raiz);
  }
});

test("casos: escribir deja copia, y un case.json corrupto se recupera de ella y se DICE", () => {
  const { raiz, reg } = registroNuevo();
  try {
    const abierto = crear(reg, "recuperable");
    const m = JSON.parse(abierto.manifest);
    const v2 = { ...m, name: "renombrado", updatedAt: new Date().toISOString() };
    reg.invocar("case_write", { caseId: abierto.case_id, contents: JSON.stringify(v2), ownerUserId: "u1" });
    const copia = path.join(abierto.path, ".case.json.bak");
    assert.ok(fs.existsSync(copia), "la escritura respalda el contenido anterior válido");
    assert.equal(JSON.parse(fs.readFileSync(copia, "utf8")).name, "recuperable");

    fs.writeFileSync(path.join(abierto.path, "case.json"), "{ esto no es json");
    const leido = reg.invocar("case_read", { caseId: abierto.case_id, ownerUserId: "u1" });
    assert.equal(leido.recovered_from_backup, true, "un caso salvado del backup no se presenta como si nada");
    assert.equal(JSON.parse(leido.manifest).name, "recuperable");
    assert.equal(reg.invocar("case_read", { caseId: abierto.case_id, ownerUserId: "u1" }).recovered_from_backup, false, "ya restaurado");

    // FIEL A cases.rs, y por eso aquí documentado: `case_list_authorized` también llama a
    // `read_manifest_with_recovery`, que RESTAURA en disco y descarta el indicador. Como `listCases`
    // llama a `case_read` después, la fila nunca llega con `recoveredFromBackup`. Candidato a defecto
    // de la app (Historial); no se arregla aquí: la cápsula reproduce, no corrige.
    fs.writeFileSync(path.join(abierto.path, "case.json"), "{ otra vez roto");
    assert.equal(reg.invocar("case_list_authorized", { ownerUserId: "u1" })[0].can_repair, true);
    assert.equal(reg.invocar("case_read", { caseId: abierto.case_id, ownerUserId: "u1" }).recovered_from_backup, false);

    // Sin backup válido, el error es el del principal (no se inventa nada).
    fs.writeFileSync(path.join(abierto.path, "case.json"), "roto");
    fs.writeFileSync(copia, "también roto");
    assert.equal(codigoDe(() => reg.invocar("case_read", { caseId: abierto.case_id, ownerUserId: "u1" })), "INVALID_MANIFEST");
    // Un backup de OTRO caso nunca se restaura.
    const otro = crear(reg, "otro caso");
    fs.writeFileSync(copia, otro.manifest);
    assert.equal(codigoDe(() => reg.invocar("case_repair", { caseId: abierto.case_id, ownerUserId: "u1" })), "UNAUTHORIZED");
    assert.equal(fs.readFileSync(path.join(abierto.path, "case.json"), "utf8"), "roto", "no se escribió nada");
  } finally {
    limpiar(raiz);
  }
});

test("casos: olvidar retira del registro pero NO borra la carpeta", () => {
  const { raiz, reg } = registroNuevo();
  try {
    const a = crear(reg, "olvidable");
    reg.invocar("case_forget", { caseId: a.case_id, ownerUserId: "u1" });
    assert.ok(fs.existsSync(path.join(a.path, "case.json")), "la carpeta sigue ahí");
    assert.deepEqual(reg.invocar("case_list_authorized", { ownerUserId: "u1" }), []);
    assert.equal(codigoDe(() => reg.invocar("case_read", { caseId: a.case_id, ownerUserId: "u1" })), "NOT_FOUND");
  } finally {
    limpiar(raiz);
  }
});

test("casos: el diálogo nativo se sustituye por siguiente-carpeta.txt, que vale para UN diálogo", () => {
  const { raiz, reg } = registroNuevo();
  try {
    assert.equal(reg.invocar("case_pick_directory"), null, "sin elección, «el usuario canceló»");
    const origen = crear(reg, "para-abrir");
    const copia = path.join(raiz, "copia");
    fs.cpSync(origen.path, copia, { recursive: true });

    fs.writeFileSync(reg.archivoSiguiente, copia);
    const elegida = reg.invocar("case_pick_directory");
    assert.equal(elegida.has_manifest, true);
    assert.equal(fs.existsSync(reg.archivoSiguiente), false, "se consume");
    assert.equal(reg.invocar("case_pick_directory"), null, "el segundo diálogo ya no la ve");

    // El mismo case_id ya está registrado en OTRA carpeta: conflicto, y el registro no se mueve.
    const abierto = reg.invocar("case_open_token", { token: elegida.token, ownerUserId: "u1" });
    assert.equal(abierto.conflicting_path, origen.path);
    assert.equal(reg.invocar("case_list_authorized", { ownerUserId: "u1" })[0].path, origen.path);
    // Reubicar con el id equivocado: error y registro intacto.
    assert.equal(codigoDe(() => reg.invocar("case_relocate", { token: elegida.token, expectedCaseId: "otro-id", ownerUserId: "u1" })), "UNAUTHORIZED");
    // Reubicar con el id correcto sí mueve el registro.
    reg.invocar("case_relocate", { token: elegida.token, expectedCaseId: origen.case_id, ownerUserId: "u1" });
    assert.equal(reg.invocar("case_list_authorized", { ownerUserId: "u1" })[0].path, fs.realpathSync(copia));

    // Una carpeta vacía se inicializa; el caso queda a nombre de quien lo inicializa.
    const vacia = path.join(raiz, "vacia");
    fs.mkdirSync(vacia);
    fs.writeFileSync(reg.archivoSiguiente, vacia);
    const v = reg.invocar("case_pick_directory");
    assert.equal(v.has_manifest, false);
    const inicializado = reg.invocar("case_initialize", { token: v.token, name: "inicializado", studyKind: "compare-series", ownerUserId: "u1" });
    assert.equal(JSON.parse(inicializado.manifest).ownerUserId, "u1");
    // Una ruta que no existe es un error, no una cancelación silenciosa.
    fs.writeFileSync(reg.archivoSiguiente, path.join(raiz, "no-existe"));
    assert.equal(codigoDe(() => reg.invocar("case_pick_directory")), "IO_ERROR");
  } finally {
    limpiar(raiz);
  }
});

// --- el servidor, con red de verdad -----------------------------------------------------------------

const puertoLibre = () => new Promise((resolve) => {
  const s = net.createServer();
  s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => resolve(p)); });
});

function pedir({ puerto, host, ruta = "/", metodo = "GET", cabeceras = {}, cuerpo }) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port: puerto, path: ruta, method: metodo, headers: { Host: host ?? `localhost:${puerto}`, ...cabeceras } }, (res) => {
      const trozos = [];
      res.on("data", (t) => trozos.push(t));
      res.on("end", () => resolve({ status: res.statusCode, cabeceras: res.headers, cuerpo: Buffer.concat(trozos).toString("utf8") }));
    });
    req.on("error", reject);
    if (cuerpo !== undefined) req.write(cuerpo);
    req.end();
  });
}

async function conServidor(fn) {
  const raiz = temporal("servidor");
  const out = path.join(raiz, "out");
  fs.mkdirSync(path.join(out, "historial"), { recursive: true });
  fs.writeFileSync(path.join(out, "index.html"), "<!DOCTYPE html><html><head><title>t</title></head><body>inicio</body></html>");
  fs.writeFileSync(path.join(out, "historial.html"), "<html><head></head><body>historial</body></html>");
  fs.writeFileSync(path.join(out, "ok.txt"), "dentro");
  fs.writeFileSync(path.join(raiz, "secreto.txt"), "FUERA-DE-LA-RAIZ");
  const archivoManifiesto = path.join(raiz, "manifest.json");
  const archivoNoEmulados = path.join(raiz, "no-emulados.log");
  const puerto = await puertoLibre();
  const casos = new RegistroDeCasos({
    dirRegistro: path.join(raiz, "registro"), dirPadre: path.join(raiz, "casos"),
    archivoSiguiente: path.join(raiz, "siguiente-carpeta.txt"), versionEsquema: versionDeEsquema(CASES_RS),
  });
  const runtimeRoot = path.join(raiz, "runtime");
  fs.mkdirSync(runtimeRoot);
  fs.writeFileSync(path.join(runtimeRoot, "pesos.bin"), "x");
  const csp = "default-src 'self'; script-src 'self'";
  const servidor = crearServidor({ outDir: out, csp, puertoFront: puerto, puertoBack: 18999, token: "TOKEN-DE-PRUEBA", runtimeRoot, raicesLegibles: [runtimeRoot, raiz + path.sep + "legible"], casos, archivoManifiesto, archivoNoEmulados });
  await new Promise((r) => servidor.listen(puerto, "127.0.0.1", r));
  try {
    await fn({ puerto, raiz, csp, archivoManifiesto, archivoNoEmulados, runtimeRoot });
  } finally {
    await new Promise((r) => servidor.close(r));
    limpiar(raiz);
  }
}

test("servidor: HTML con shim primero, CSP en el documento, sin caché; y las rutas del router estático", async () => {
  await conServidor(async ({ puerto, csp }) => {
    const r = await pedir({ puerto, ruta: "/index.html" });
    assert.equal(r.status, 200);
    assert.equal(r.cabeceras["content-security-policy"], csp);
    assert.equal(r.cabeceras["cache-control"], "no-store", "tras un rebuild se ve el código nuevo, no el de la caché");
    assert.ok(r.cuerpo.includes('<head><script src="/__sandbox_tauri_shim.js"></script><title>'));
    assert.equal((await pedir({ puerto, ruta: "/" })).status, 200);
    assert.ok((await pedir({ puerto, ruta: "/historial" })).cuerpo.includes("historial"), "<ruta>.html cuando hay carpeta homónima");
    const txt = await pedir({ puerto, ruta: "/ok.txt" });
    assert.equal(txt.cuerpo, "dentro");
    assert.equal(txt.cabeceras["content-security-policy"], undefined, "la CSP viaja sólo con el documento");
    assert.equal((await pedir({ puerto, ruta: "/no-existe" })).status, 404);
    assert.equal((await pedir({ puerto, ruta: "/index.html", metodo: "DELETE" })).status, 405);
  });
});

test("servidor: Host ajeno 421, 127.0.0.1 redirige a localhost, y nada sale de la raíz", async () => {
  await conServidor(async ({ puerto }) => {
    assert.equal((await pedir({ puerto, host: "evil.example" })).status, 421);
    const redir = await pedir({ puerto, host: `127.0.0.1:${puerto}`, ruta: "/historial" });
    assert.equal(redir.status, 308);
    assert.equal(redir.cabeceras.location, `http://localhost:${puerto}/historial`);
    for (const intento of ["/..%2fsecreto.txt", "/%2e%2e/secreto.txt", "/..%5csecreto.txt", "/ok.txt/../../secreto.txt"]) {
      const r = await pedir({ puerto, ruta: intento });
      assert.ok(!r.cuerpo.includes("FUERA-DE-LA-RAIZ"), `${intento} filtró un archivo de fuera de la raíz`);
      assert.notEqual(r.status, 200, `${intento}`);
    }
  });
});

test("servidor: shim, manifiesto e invoke sólo se sirven al propio origen", async () => {
  await conServidor(async ({ puerto, archivoManifiesto }) => {
    fs.writeFileSync(archivoManifiesto, JSON.stringify({ agente: 9 }));
    const ajeno = { "Sec-Fetch-Site": "cross-site" };
    assert.equal((await pedir({ puerto, ruta: "/__sandbox_tauri_shim.js", cabeceras: ajeno })).status, 403);
    assert.equal((await pedir({ puerto, ruta: "/__sandbox/manifest.json", cabeceras: ajeno })).status, 403);
    assert.equal((await pedir({ puerto, ruta: "/__sandbox/invoke", metodo: "POST", cabeceras: ajeno, cuerpo: "{}" })).status, 403);
    // Control positivo: del propio origen, sí — y el shim trae el secreto del backend.
    const shim = await pedir({ puerto, ruta: "/__sandbox_tauri_shim.js", cabeceras: { "Sec-Fetch-Site": "same-origin" } });
    assert.equal(shim.status, 200);
    assert.ok(shim.cuerpo.includes("TOKEN-DE-PRUEBA") && shim.cuerpo.includes("18999"));
    assert.equal(JSON.parse((await pedir({ puerto, ruta: "/__sandbox/manifest.json" })).cuerpo).agente, 9);
    assert.ok(!(await pedir({ puerto, ruta: "/__sandbox/manifest.json" })).cuerpo.includes("TOKEN"), "el manifiesto no lleva secretos");
  });
});

test("servidor: invoke emula casos y sistema, y declara lo que no emula", async () => {
  await conServidor(async ({ puerto, runtimeRoot, archivoNoEmulados, raiz }) => {
    const invocar = async (cmd, args) => {
      const r = await pedir({ puerto, ruta: "/__sandbox/invoke", metodo: "POST", cuerpo: JSON.stringify({ cmd, args }) });
      return { status: r.status, ...JSON.parse(r.cuerpo) };
    };
    const padre = (await invocar("case_pick_parent_directory", {})).resultado;
    const creado = await invocar("case_create", { token: padre.token, folderName: "Caso HTTP", name: "Caso HTTP", studyKind: "review-pose", ownerUserId: "u1" });
    assert.equal(creado.status, 200);
    const lista = await invocar("case_list_authorized", { ownerUserId: "u1" });
    assert.equal(lista.resultado.length, 1);
    // Error de Rust: HTTP 400 con el prefijo de código.
    const mal = await invocar("case_create", { token: padre.token, folderName: "..", name: "x", studyKind: "review-pose", ownerUserId: "u1" });
    assert.equal(mal.status, 400);
    assert.match(mal.error, /^UNSAFE_NAME: /);

    assert.equal((await invocar("get_resource_dir", {})).resultado, runtimeRoot);
    assert.equal((await invocar("file_exists", { dest: path.join(runtimeRoot, "pesos.bin") })).resultado, true);
    assert.equal((await invocar("file_exists", { dest: path.join(runtimeRoot, "nada.bin") })).resultado, false);
    assert.equal((await invocar("verify_model", { dest: path.join(runtimeRoot, "pesos.bin"), sha256: "x" })).resultado, true);
    const fuera = await invocar("file_exists", { dest: path.join(raiz, "secreto.txt") });
    assert.equal(fuera.status, 403, "no se consulta cualquier ruta del disco");
    assert.match(fuera.error, /^UNAUTHORIZED/);

    for (const cmd of ["download_model", "cancel_download", "extract_archive"]) {
      const r = await invocar(cmd, {});
      assert.equal(r.status, 501);
      assert.equal(r.noSimulado, true);
    }
    assert.match(fs.readFileSync(archivoNoEmulados, "utf8"), /download_model/);
    assert.equal((await pedir({ puerto, ruta: "/__sandbox/invoke" })).status, 405);
    assert.equal((await pedir({ puerto, ruta: "/__sandbox/invoke", metodo: "POST", cuerpo: "no es json" })).status, 400);
  });
});
