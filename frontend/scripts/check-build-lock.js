// scripts/check-build-lock.js
// =============================================================================
// Guardia previa al build: falla RÁPIDO si el directorio de salida está tomado.
//
// EL FALLO QUE EVITA
//
// `next build` y `next dev` escriben el mismo directorio de trabajo. En Windows
// los archivos que abre el servidor de desarrollo —`trace` el primero— quedan
// con bloqueo exclusivo, y entonces el build hace una de dos cosas, ninguna
// buena:
//
//   · revienta con `EPERM: operation not permitted, open '...\.next\trace'`, o
//   · se queda en «Creating an optimized production build…» sin devolver nunca
//     ni un error ni un código de salida.
//
// La segunda es la peor: no hay nada que leer, nada que buscar y nada que
// arreglar. Se diagnostica sólo mirando qué procesos hay vivos, que es
// exactamente lo que nadie hace cuando una build «tarda».
//
// Desde este sprint, `dev` escribe en `.next-dev` y el build en `.next`, así
// que la colisión estructural ya no puede ocurrir. Esta guardia cubre lo que
// queda: dos builds simultáneos, un proceso zombi que no soltó el directorio,
// o un antivirus reteniéndolo. Convierte un cuelgue mudo en un mensaje.
//
// No modifica nada. Sólo mira y, si algo tiene el directorio tomado, lo dice y
// devuelve 1.
// =============================================================================

const fs = require("fs");
const path = require("path");

const DIST_DIR = process.env.NEXT_DIST_DIR || ".next";
const distPath = path.join(__dirname, "..", DIST_DIR);

/**
 * ¿Se puede escribir en este archivo AHORA MISMO?
 *
 * Se abre en modo `r+` en vez de mirar permisos: en Windows un bloqueo
 * exclusivo no se ve en los metadatos del archivo, sólo al intentar abrirlo.
 * Preguntar por los permisos habría dado «sí, se puede» justo en el caso que
 * hay que detectar.
 */
function lockedBy(filePath) {
  let handle;
  try {
    handle = fs.openSync(filePath, "r+");
    return null;
  } catch (error) {
    if (error.code === "EPERM" || error.code === "EBUSY" || error.code === "EACCES") {
      return error.code;
    }
    // ENOENT y demás: el archivo no está, que es el caso normal.
    return null;
  } finally {
    if (handle !== undefined) fs.closeSync(handle);
  }
}

function main() {
  if (!fs.existsSync(distPath)) return; // primer build: nada que comprobar

  // `trace` es el primero que abre Next y el que se queda bloqueado.
  const suspects = ["trace", "build-manifest.json", "package.json"];
  const blocked = suspects
    .map((name) => path.join(distPath, name))
    .filter((file) => fs.existsSync(file))
    .map((file) => ({ file, code: lockedBy(file) }))
    .filter((entry) => entry.code !== null);

  if (blocked.length === 0) return;

  const detail = blocked
    .map((entry) => `  · ${path.relative(path.join(__dirname, ".."), entry.file)} (${entry.code})`)
    .join("\n");

  process.stderr.write(
    "\n" +
      "El directorio de salida del build está tomado por otro proceso:\n\n" +
      detail +
      "\n\n" +
      "Otro `next` está escribiendo en `" +
      DIST_DIR +
      "`. Si el build continuara se quedaría\n" +
      "colgado en «Creating an optimized production build…» sin devolver error.\n\n" +
      "Qué hacer:\n" +
      "  1. Cierra cualquier `npm run dev`, `next start` o `npx tauri dev` abierto\n" +
      "     sobre este proyecto (el servidor de desarrollo usa `.next-dev`, pero\n" +
      "     una sesión anterior a este cambio todavía puede estar usando `.next`).\n" +
      "  2. Comprueba que no queda ninguno:  Get-Process node\n" +
      "  3. Vuelve a lanzar el build.\n\n",
  );
  process.exit(1);
}

main();
