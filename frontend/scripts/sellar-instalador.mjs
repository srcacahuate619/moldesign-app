// scripts/sellar-instalador.mjs
// =============================================================================
// Sella el instalador recién construido: SHA-256 + manifiesto de release.
//
// EL FALLO QUE ARREGLA. El `.sha256` que había junto al instalador se generaba
// A MANO. El 2026-09-01, tras reconstruir, el archivo seguía siendo del 25 de
// agosto: declaraba `53C51F21…` para un binario que era `565B2536…`.
//
// Eso es PEOR que no publicar hash. MolDesign no lleva firma Authenticode, así
// que el SHA-256 es la única prueba de integridad que recibe quien descarga
// desde GitHub. Un hash que no cuadra no se lee como «el archivo del autor está
// desactualizado»: se lee como «este binario ha sido manipulado». El fallo
// silencioso destruye justo la confianza que el hash existía para dar.
//
// Por eso este paso va ENCADENADO al build (ver `tauri:build` en package.json)
// y no en la memoria de nadie. Si el instalador se reconstruye, el sello se
// rehace; si no se puede rehacer, el build falla.
//
// ATADO A LA VERSION. El nombre del artefacto que produce NSIS lleva la versión
// de `tauri.conf.json`. Aquí se comprueba que coinciden: si alguien sube la
// versión en la configuración y el artefacto encontrado es de otra, el sello se
// niega. Sellar el binario equivocado con el número nuevo es exactamente la
// clase de mentira que este archivo existe para impedir.
//
// Salida, junto al instalador:
//   <nombre>.exe.sha256      formato `sha256sum` (verificable con -c)
//   release-manifest.json    version, archivo, bytes, sha256, fecha, commit
//
// Exit: 0 = sellado, 1 = no se pudo sellar (detiene el build).
// =============================================================================

import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, readdir, stat, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(AQUI, "..");
const NSIS = path.join(FRONTEND, "src-tauri", "target", "release", "bundle", "nsis");

function fallar(msg) {
  console.error(`[sellar-instalador] ERROR: ${msg}`);
  process.exit(1);
}

async function sha256(archivo) {
  return new Promise((res, rej) => {
    const h = createHash("sha256");
    createReadStream(archivo)
      .on("data", (d) => h.update(d))
      .on("end", () => res(h.digest("hex")))
      .on("error", rej);
  });
}

function commitActual() {
  try {
    const sha = execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: FRONTEND, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    let sucio = false;
    try {
      sucio = execFileSync("git", ["status", "--porcelain"], {
        cwd: FRONTEND, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"],
      }).trim().length > 0;
    } catch {}
    // `sucio` no es un detalle: un instalador construido desde un arbol con
    // cambios sin commitear NO es reproducible, y quien lo descargue no puede
    // llegar al codigo que lo produjo. Se declara en vez de callarse.
    return { commit: sha, arbol_limpio: !sucio };
  } catch {
    return { commit: null, arbol_limpio: null };
  }
}

const config = JSON.parse(
  await readFile(path.join(FRONTEND, "src-tauri", "tauri.conf.json"), "utf-8"),
);
const version = config.version;
if (!version) fallar("tauri.conf.json no declara `version`.");

let entradas;
try {
  entradas = await readdir(NSIS);
} catch {
  fallar(`no existe ${NSIS}. Este paso corre DESPUES de \`tauri build\`.`);
}

const instaladores = entradas.filter((n) => n.toLowerCase().endsWith("-setup.exe"));
if (instaladores.length === 0) fallar(`no se encontro ningun *-setup.exe en ${NSIS}.`);
if (instaladores.length > 1) {
  fallar(
    `hay ${instaladores.length} instaladores en ${NSIS} (${instaladores.join(", ")}). ` +
      "No se puede saber cual sellar: limpia los antiguos antes de construir."
  );
}

const nombre = instaladores[0];
const exe = path.join(NSIS, nombre);

if (!nombre.includes(version)) {
  fallar(
    `el artefacto \`${nombre}\` no lleva la version \`${version}\` que declara ` +
      "tauri.conf.json. Sellarlo con este numero afirmaria algo falso."
  );
}

const info = await stat(exe);
const hash = await sha256(exe);
const { commit, arbol_limpio } = commitActual();

// Formato `sha256sum`: dos espacios entre hash y nombre. Se verifica con
// `sha256sum -c` en Linux/macOS y con Get-FileHash en PowerShell.
await writeFile(`${exe}.sha256`, `${hash}  ${nombre}\n`, "utf-8");

const manifiesto = {
  producto: config.productName ?? "MolDesign AI",
  version,
  archivo: nombre,
  bytes: info.size,
  sha256: hash,
  construido_en: new Date().toISOString(),
  commit,
  arbol_limpio,
  firmado_authenticode: false,
  nota_verificacion:
    "Este instalador NO lleva firma Authenticode. El SHA-256 de este manifiesto " +
    "es la unica prueba de integridad: comprobalo antes de ejecutar con " +
    `Get-FileHash ".\\${nombre}" -Algorithm SHA256`,
};
await writeFile(
  path.join(NSIS, "release-manifest.json"),
  JSON.stringify(manifiesto, null, 2) + "\n",
  "utf-8",
);

// Autocomprobacion: se relee lo escrito y se contrasta. Un sello que no se
// verifica a si mismo es una promesa sin respaldo, y ya nos paso con un
// guardian que anunciaba «limpio» estando roto.
const releido = (await readFile(`${exe}.sha256`, "utf-8")).trim().split(/\s+/)[0];
if (releido !== hash) fallar("el .sha256 escrito no coincide con lo calculado.");

console.log(`[sellar-instalador] ${nombre}`);
console.log(`[sellar-instalador]   version : ${version}`);
console.log(`[sellar-instalador]   tamano  : ${info.size.toLocaleString("es-ES")} bytes`);
console.log(`[sellar-instalador]   sha256  : ${hash}`);
console.log(`[sellar-instalador]   commit  : ${commit ?? "desconocido"}${arbol_limpio === false ? "  (ARBOL CON CAMBIOS SIN COMMITEAR)" : ""}`);
if (arbol_limpio === false) {
  console.warn(
    "[sellar-instalador] AVISO: construido desde un arbol con cambios sin " +
      "commitear. Este instalador no es reproducible desde el repositorio."
  );
}
process.exit(0);
