// scripts/qa_sandbox/casos.mjs
// =============================================================================
// Emulación, en Node, de la frontera de casos de Rust
// (`frontend/src-tauri/src/cases.rs`).
//
// POR QUÉ EXISTE. En la app instalada el almacenamiento de casos (la pestaña
// Historial) pasa ENTERO por comandos de Rust: `case_create`, `case_read`,
// `case_write`... Un navegador sin Tauri no los tiene, y entonces la app cae a
// `browserCaseRepository`, que es OTRO código —el de producción nunca lo
// ejecuta—. Auditar Historial así sería auditar una app que nadie usa. Con el
// shim, `isTauriAvailable()` es verdadero, la app usa `tauriCaseRepository`
// (el real) y esta emulación hace de Rust.
//
// LO QUE ES FIEL: los nombres y las formas de los comandos, los códigos de error
// con prefijo (`UNSAFE_NAME: …`), la validación del nombre de carpeta, el
// manifiesto inicial, la escritura con copia `.case.json.bak` y la lectura con
// recuperación, el registro de autorizaciones por `case_id`, los tokens de
// sesión y el control de propietario.
//
// LO QUE NO ES, y no debe presentarse como cubierto: no hay `ensure_within`
// contra symlinks, ni escritura atómica con `sync_all`, ni el diálogo nativo de
// carpetas (se sustituye por una carpeta fija o por `siguiente-carpeta.txt`), ni
// el Explorador de Windows en `case_reveal`. Un defecto de esas partes sólo se
// ve en la app instalada.
//
// El esquema se lee de `cases.rs` en vez de copiarse: si Rust sube de versión,
// la emulación sube con él o se niega a arrancar.
// =============================================================================

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

export const MANIFEST_FILE = "case.json";
export const BACKUP_FILE = ".case.json.bak";
const SUBDIRS = ["inputs", "runs", "evidence", "reports", "exports"];
const MAX_FOLDER_NAME_LEN = 64;
const MAX_MANIFEST_BYTES = 4 * 1024 * 1024;
const RESERVED_NAMES = new Set([
  "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8",
  "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
]);
const STATUSES = new Set(["draft", "qualifying", "ready", "running", "review", "completed", "abstained"]);
const STUDY_KINDS = new Set(["explore-hypothesis", "compare-series", "review-pose", "prepare-evidence"]);
const ISO_8601 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

/** Lee `CURRENT_CASE_SCHEMA_VERSION` de `cases.rs`. Falla si no lo encuentra. */
export function versionDeEsquema(casesRs) {
  const m = /const\s+CURRENT_CASE_SCHEMA_VERSION:\s*u64\s*=\s*(\d+)\s*;/.exec(fs.readFileSync(casesRs, "utf8"));
  if (!m) throw new Error(`no encuentro CURRENT_CASE_SCHEMA_VERSION en ${casesRs}: la emulación de casos ya no sabe qué esquema escribir.`);
  return Number(m[1]);
}

/** `Err(String)` de Rust: el mensaje lleva el código como prefijo. */
export class ErrorDeRust extends Error {
  constructor(codigo, mensaje) {
    super(`${codigo}: ${mensaje}`);
    this.name = "ErrorDeRust";
    this.codigo = codigo;
  }
}
const falla = (codigo, mensaje) => new ErrorDeRust(codigo, mensaje);

export function validarNombreDeCarpeta(nombre) {
  const t = String(nombre ?? "").trim();
  if (!t) throw falla("UNSAFE_NAME", "el nombre de la carpeta está vacío.");
  if (Buffer.byteLength(t) > MAX_FOLDER_NAME_LEN) throw falla("UNSAFE_NAME", `el nombre supera ${MAX_FOLDER_NAME_LEN} caracteres.`);
  if (t === "." || t === "..") throw falla("UNSAFE_NAME", "`.` y `..` no son nombres de carpeta válidos.");
  if (t.includes("/") || t.includes("\\")) throw falla("UNSAFE_NAME", "el nombre no puede contener separadores de ruta.");
  if (t.includes(":")) throw falla("UNSAFE_NAME", "el nombre no puede contener `:`.");
  for (const ch of t) {
    const cp = ch.codePointAt(0);
    if (cp < 32 || cp === 127) throw falla("UNSAFE_NAME", "el nombre contiene caracteres de control.");
    if ('<>"|?*'.includes(ch)) throw falla("UNSAFE_NAME", `el carácter \`${ch}\` no está permitido.`);
  }
  if (t.endsWith(".")) throw falla("UNSAFE_NAME", "el nombre no puede terminar en punto.");
  if (RESERVED_NAMES.has(t.toLowerCase())) throw falla("UNSAFE_NAME", `\`${t}\` es un nombre reservado por el sistema operativo.`);
  return t;
}

export function validarTipoDeEstudio(tipo) {
  if (!STUDY_KINDS.has(tipo)) throw falla("INVALID_MANIFEST", `tipo de estudio desconocido: ${tipo}`);
  return tipo;
}

/** Parte de `validate_manifest` de Rust: la que decide si algo es un caso. El frontend vuelve a validar el resto. */
export function validarManifiesto(texto, versionActual) {
  if (Buffer.byteLength(texto) > MAX_MANIFEST_BYTES) throw falla("INVALID_MANIFEST", "`case.json` es sospechosamente grande.");
  let v;
  try {
    v = JSON.parse(texto);
  } catch (e) {
    throw falla("INVALID_MANIFEST", `\`case.json\` no es JSON válido (${e.message}).`);
  }
  if (v === null || typeof v !== "object" || Array.isArray(v)) throw falla("INVALID_MANIFEST", "`case.json` no contiene un objeto.");
  if (!Number.isInteger(v.schemaVersion)) throw falla("INVALID_MANIFEST", "falta una `schemaVersion` entera.");
  if (v.schemaVersion < 1 || v.schemaVersion > versionActual) {
    throw falla("UNSUPPORTED_VERSION", `esquema v${v.schemaVersion}; este build soporta hasta v${versionActual}.`);
  }
  for (const k of ["id", "name"]) {
    if (typeof v[k] !== "string" || !v[k]) throw falla("INVALID_MANIFEST", `falta \`${k}\` o no es una cadena.`);
  }
  if (v.schemaVersion >= 6 && (typeof v.ownerUserId !== "string" || !v.ownerUserId.trim())) {
    throw falla("INVALID_MANIFEST", "un manifiesto v6 requiere `ownerUserId`.");
  }
  for (const k of ["createdAt", "updatedAt", "lastOpenedAt"]) {
    if (typeof v[k] !== "string") throw falla("INVALID_MANIFEST", `falta \`${k}\` o no es una cadena.`);
    if (!ISO_8601.test(v[k]) || Number.isNaN(Date.parse(v[k]))) throw falla("INVALID_MANIFEST", `\`${k}\` no es una fecha ISO 8601: ${v[k]}.`);
  }
  if (v.status !== undefined && !STATUSES.has(v.status)) throw falla("INVALID_MANIFEST", `estado desconocido: ${v.status}`);
  return v;
}

function asegurarPropietario(texto, esperado, permitirLegacy) {
  if (!String(esperado ?? "").trim()) throw falla("UNAUTHORIZED", "falta la identidad de la sesión.");
  let v;
  try {
    v = JSON.parse(texto);
  } catch {
    throw falla("INVALID_MANIFEST", "no se pudo comprobar el propietario.");
  }
  const dueno = v?.ownerUserId;
  if (typeof dueno === "string") {
    if (dueno === esperado) return;
    throw falla("UNAUTHORIZED", "este caso pertenece a otra cuenta.");
  }
  if (permitirLegacy) return;
  throw falla("UNAUTHORIZED", "el caso no declara un propietario.");
}

function escribirAtomico(destino, contenido) {
  const tmp = `${destino}.${process.pid}.${crypto.randomBytes(4).toString("hex")}.tmp`;
  fs.writeFileSync(tmp, contenido);
  fs.renameSync(tmp, destino);
}

export class RegistroDeCasos {
  /**
   * @param {object} o
   * @param {string} o.dirRegistro   dónde persiste `authorized_cases.json` (en Rust, app data)
   * @param {string} o.dirPadre      carpeta que ofrece `case_pick_parent_directory`
   * @param {string} o.archivoSiguiente  `siguiente-carpeta.txt`: sustituye al diálogo nativo
   * @param {number} o.versionEsquema
   */
  constructor({ dirRegistro, dirPadre, archivoSiguiente, versionEsquema, ahora = () => new Date().toISOString() }) {
    this.dirRegistro = dirRegistro;
    this.dirPadre = dirPadre;
    this.archivoSiguiente = archivoSiguiente;
    this.version = versionEsquema;
    this.ahora = ahora;
    this.grants = new Map();
    this.casos = new Map();
    this.salud = { state: "first_run" };
    this.cargar();
  }

  get #principal() { return path.join(this.dirRegistro, "authorized_cases.json"); }
  get #copia() { return path.join(this.dirRegistro, "authorized_cases.json.bak"); }

  cargar() {
    const leer = (p) => {
      const j = JSON.parse(fs.readFileSync(p, "utf8"));
      if (!j || typeof j.cases !== "object") throw new Error("registro sin `cases`");
      return j.cases;
    };
    const existia = fs.existsSync(this.#principal) || fs.existsSync(this.#copia);
    let cases = null;
    try {
      cases = leer(this.#principal);
      this.salud = { state: "ok" };
    } catch (primario) {
      try {
        cases = leer(this.#copia);
        this.salud = { state: "recovered_from_backup", detail: String(primario.message ?? primario) };
      } catch (secundario) {
        this.salud = existia
          ? { state: "corrupted", detail: `${primario.message ?? primario} · copia de seguridad: ${secundario.message ?? secundario}` }
          : { state: "first_run" };
      }
    }
    this.casos = new Map(Object.entries(cases ?? {}));
  }

  persistir() {
    fs.mkdirSync(this.dirRegistro, { recursive: true });
    if (fs.existsSync(this.#principal)) {
      try {
        JSON.parse(fs.readFileSync(this.#principal, "utf8"));
        fs.copyFileSync(this.#principal, this.#copia);
      } catch { /* sólo se respalda contenido válido */ }
    }
    // El mismo formato que `PersistedRegistry` de cases.rs: el backend (Molcy) rechaza un registro sin `version: 1`.
    escribirAtomico(this.#principal, JSON.stringify({ version: 1, cases: Object.fromEntries(this.casos) }, null, 2));
    if (this.salud.state === "first_run" || this.salud.state === "corrupted") this.salud = { state: "ok" };
  }

  #conceder(dir) {
    const canonica = fs.realpathSync(dir);
    const token = crypto.randomUUID();
    this.grants.set(token, canonica);
    return { token, display_path: canonica, has_manifest: fs.existsSync(path.join(canonica, MANIFEST_FILE)) };
  }

  #resolverGrant(token) {
    const d = this.grants.get(token);
    if (!d) throw falla("UNAUTHORIZED", "la autorización de carpeta no existe o caducó.");
    return d;
  }

  #resolverCaso(id) {
    const d = this.casos.get(id);
    if (!d) throw falla("NOT_FOUND", "el caso no está autorizado en este equipo.");
    return d;
  }

  #registrar(id, dir) {
    this.casos.set(id, dir);
    this.persistir();
  }

  /** `siguiente-carpeta.txt` se consume al leerse: una elección vale para UN diálogo. */
  #siguienteCarpeta() {
    let texto;
    try {
      texto = fs.readFileSync(this.archivoSiguiente, "utf8").trim();
    } catch {
      return null;
    }
    fs.rmSync(this.archivoSiguiente, { force: true });
    if (!texto) return null;
    if (!path.isAbsolute(texto) || !fs.statSync(texto, { throwIfNoEntry: false })?.isDirectory()) {
      throw falla("IO_ERROR", `siguiente-carpeta.txt apunta a una carpeta que no existe: ${texto}`);
    }
    return texto;
  }

  #abierto(id, dir, manifiesto, recuperado, conflicto = null) {
    return { case_id: id, path: dir, manifest: manifiesto, recovered_from_backup: recuperado, conflicting_path: conflicto };
  }

  #manifiestoInicial(id, nombre, tipo, dir, dueno) {
    const ahora = this.ahora();
    return `${JSON.stringify({
      schemaVersion: this.version,
      id,
      ownerUserId: dueno,
      name: nombre,
      createdAt: ahora,
      updatedAt: ahora,
      lastOpenedAt: ahora,
      status: "draft",
      storage: { mode: "folder", path: dir },
      activeView: "evaluation",
      context: { studyKind: tipo },
      archived: false,
    }, null, 2)}\n`;
  }

  #preparar(dir, permitirExistente) {
    if (fs.existsSync(path.join(dir, MANIFEST_FILE))) throw falla("ALREADY_EXISTS", `ya hay un caso en ${dir}. No se sobrescribe.`);
    if (fs.existsSync(dir) && !permitirExistente) throw falla("ALREADY_EXISTS", `la carpeta ${dir} ya existe.`);
    fs.mkdirSync(dir, { recursive: true });
    for (const s of SUBDIRS) fs.mkdirSync(path.join(dir, s), { recursive: true });
  }

  #escribirManifiesto(dir, texto) {
    const nuevo = validarManifiesto(texto, this.version);
    if (!fs.statSync(dir, { throwIfNoEntry: false })?.isDirectory()) throw falla("NOT_FOUND", `la carpeta del caso no existe: ${dir}`);
    const final = path.join(dir, MANIFEST_FILE);
    if (fs.existsSync(final)) {
      try {
        const previo = fs.readFileSync(final, "utf8");
        if (validarManifiesto(previo, this.version).id === nuevo.id) fs.writeFileSync(path.join(dir, BACKUP_FILE), previo);
      } catch { /* sólo se respalda contenido válido del MISMO caso */ }
    }
    escribirAtomico(final, texto);
  }

  /** Devuelve [texto, recuperadoDelBackup]. */
  #leerConRecuperacion(dir, idEsperado) {
    const final = path.join(dir, MANIFEST_FILE);
    const copia = path.join(dir, BACKUP_FILE);
    const valido = (p) => {
      const t = fs.readFileSync(p, "utf8");
      validarManifiesto(t, this.version);
      return t;
    };
    let errorPrimario;
    if (fs.existsSync(final)) {
      try {
        return [valido(final), false];
      } catch (e) {
        errorPrimario = e;
      }
    } else {
      errorPrimario = falla("NOT_FOUND", `no hay \`case.json\` en ${dir}`);
    }
    if (fs.existsSync(copia)) {
      let texto = null;
      try { texto = valido(copia); } catch { /* backup inservible */ }
      if (texto !== null) {
        const encontrado = JSON.parse(texto).id;
        if (idEsperado && encontrado !== idEsperado) {
          throw falla("UNAUTHORIZED", `la copia de seguridad es del caso ${encontrado}, no de ${idEsperado}. No se ha restaurado nada.`);
        }
        try { this.#escribirManifiesto(dir, texto); } catch { /* se devuelve el backup igualmente */ }
        return [texto, true];
      }
    }
    throw errorPrimario instanceof ErrorDeRust ? errorPrimario : falla("IO_ERROR", String(errorPrimario?.message ?? errorPrimario));
  }

  /** Despacho. `args` llega en camelCase, igual que desde la app. */
  invocar(cmd, args = {}) {
    switch (cmd) {
      case "case_pick_parent_directory": {
        const elegida = this.#siguienteCarpeta();
        if (!elegida) fs.mkdirSync(this.dirPadre, { recursive: true });
        return this.#conceder(elegida ?? this.dirPadre);
      }
      case "case_default_parent_directory": {
        // Como en Rust: sin argumentos, sin diálogo y sin `siguiente-carpeta.txt`. La carpeta es SIEMPRE
        // la fija de la cápsula (en la app real, `Documentos\\MolDesign\\Casos`).
        fs.mkdirSync(this.dirPadre, { recursive: true });
        return this.#conceder(this.dirPadre);
      }
      case "case_pick_directory": {
        const elegida = this.#siguienteCarpeta();
        return elegida ? this.#conceder(elegida) : null; // sin elección: «el usuario canceló»
      }
      case "case_create": {
        const padre = this.#resolverGrant(args.token);
        const tipo = validarTipoDeEstudio(args.studyKind);
        const carpeta = validarNombreDeCarpeta(args.folderName);
        const dir = path.join(padre, carpeta);
        this.#preparar(dir, false);
        const canonica = fs.realpathSync(dir);
        if (path.dirname(canonica) !== fs.realpathSync(padre)) {
          fs.rmSync(dir, { recursive: true, force: true });
          throw falla("UNAUTHORIZED", "la carpeta del caso queda fuera de la carpeta autorizada.");
        }
        const id = crypto.randomUUID();
        const texto = this.#manifiestoInicial(id, String(args.name ?? "").trim(), tipo, canonica, args.ownerUserId);
        this.#escribirManifiesto(canonica, texto);
        this.#registrar(id, canonica);
        return this.#abierto(id, canonica, texto, false);
      }
      case "case_initialize": {
        const dir = this.#resolverGrant(args.token);
        const tipo = validarTipoDeEstudio(args.studyKind);
        this.#preparar(dir, true);
        const id = crypto.randomUUID();
        const texto = this.#manifiestoInicial(id, String(args.name ?? "").trim(), tipo, dir, args.ownerUserId);
        this.#escribirManifiesto(dir, texto);
        this.#registrar(id, dir);
        return this.#abierto(id, dir, texto, false);
      }
      case "case_open_token": {
        const dir = this.#resolverGrant(args.token);
        const [texto, recuperado] = this.#leerConRecuperacion(dir, null);
        asegurarPropietario(texto, args.ownerUserId, true);
        const id = JSON.parse(texto).id;
        const previo = this.casos.get(id);
        if (previo && previo !== dir) return this.#abierto(id, dir, texto, recuperado, previo);
        this.#registrar(id, dir);
        return this.#abierto(id, dir, texto, recuperado);
      }
      case "case_relocate": {
        const dir = this.#resolverGrant(args.token);
        const [texto] = this.#leerConRecuperacion(dir, null);
        const id = JSON.parse(texto).id;
        if (id !== args.expectedCaseId) throw falla("UNAUTHORIZED", `la carpeta contiene el caso ${id}, no ${args.expectedCaseId}.`);
        asegurarPropietario(texto, args.ownerUserId, true);
        this.#registrar(args.expectedCaseId, dir);
        return this.#abierto(args.expectedCaseId, dir, texto, false);
      }
      case "case_read": {
        const dir = this.#resolverCaso(args.caseId);
        const [texto, recuperado] = this.#leerConRecuperacion(dir, args.caseId);
        if (JSON.parse(texto).id !== args.caseId) throw falla("UNAUTHORIZED", "el manifiesto no es de este caso.");
        asegurarPropietario(texto, args.ownerUserId, true);
        return this.#abierto(args.caseId, dir, texto, recuperado);
      }
      case "case_write": {
        const dir = this.#resolverCaso(args.caseId);
        asegurarPropietario(args.contents, args.ownerUserId, false);
        if (validarManifiesto(args.contents, this.version).id !== args.caseId) {
          throw falla("UNAUTHORIZED", "el manifiesto que se escribe no es de este caso.");
        }
        this.#escribirManifiesto(dir, args.contents);
        return null;
      }
      case "case_repair": {
        const dir = this.#resolverCaso(args.caseId);
        const copia = path.join(dir, BACKUP_FILE);
        if (!fs.existsSync(copia)) throw falla("NOT_FOUND", "no hay copia de seguridad de la que restaurar.");
        const texto = fs.readFileSync(copia, "utf8");
        const v = validarManifiesto(texto, this.version);
        if (v.id !== args.caseId) throw falla("UNAUTHORIZED", `la copia de seguridad es del caso ${v.id}, no de ${args.caseId}.`);
        asegurarPropietario(texto, args.ownerUserId, true);
        escribirAtomico(path.join(dir, MANIFEST_FILE), texto);
        return this.#abierto(args.caseId, dir, texto, true);
      }
      case "case_list_authorized": {
        const lista = [];
        for (const [id, dir] of this.casos) {
          try {
            const [texto] = this.#leerConRecuperacion(dir, id);
            asegurarPropietario(texto, args.ownerUserId, true);
          } catch {
            continue; // no visible para esta sesión
          }
          lista.push({
            case_id: id,
            path: dir,
            available: fs.existsSync(path.join(dir, MANIFEST_FILE)),
            can_repair: fs.existsSync(path.join(dir, BACKUP_FILE)),
          });
        }
        return lista;
      }
      case "case_registry_health":
        return this.salud;
      case "case_forget": {
        const dir = this.#resolverCaso(args.caseId);
        const [texto] = this.#leerConRecuperacion(dir, args.caseId);
        asegurarPropietario(texto, args.ownerUserId, true);
        this.casos.delete(args.caseId);
        this.persistir();
        return null;
      }
      case "case_reveal": {
        const dir = this.#resolverCaso(args.caseId);
        const [texto] = this.#leerConRecuperacion(dir, args.caseId);
        asegurarPropietario(texto, args.ownerUserId, true);
        if (!fs.statSync(dir, { throwIfNoEntry: false })?.isDirectory()) throw falla("NOT_FOUND", "la carpeta del caso ya no existe.");
        return null; // Rust abre el Explorador; aquí no se abren ventanas ajenas a la prueba
      }
      default:
        return undefined;
    }
  }

  static comandos = [
    "case_pick_parent_directory", "case_default_parent_directory", "case_pick_directory", "case_create", "case_initialize", "case_open_token",
    "case_relocate", "case_read", "case_write", "case_repair", "case_list_authorized", "case_registry_health",
    "case_forget", "case_reveal",
  ];
}
