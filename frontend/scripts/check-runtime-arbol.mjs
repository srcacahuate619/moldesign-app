// scripts/check-runtime-arbol.mjs
// =============================================================================
// PRIMERA puerta del build: ¿existe el runtime que las otras doce dan por hecho?
//
// EL FALLO QUE EVITA
//
// Nueve de los scripts npm invocan `..\python-embed\python.exe` por ruta
// directa. En un clon limpio ese archivo no existe —`python-embed/` está en
// `.gitignore`— y npm falla con:
//
//   '..\python-embed\python.exe' is not recognized as an internal or external
//   command
//
// El primero en reventar es `check:csp`, así que quien clona el repositorio y
// ejecuta `npm run tauri:build` recibe un error sobre la política de seguridad
// de contenido cuando el problema real es que le faltan 2,2 GB de runtime. El
// diagnóstico correcto está a nueve puertas de distancia del mensaje.
//
// Esta guarda va ANTES que todas y traduce el fallo. No comprueba nada que las
// demás comprueben: sólo que el suelo sobre el que pisan existe.
//
// POR QUÉ CON EL PYTHON DEL SISTEMA
//
// Porque comprueba, entre otras cosas, si el intérprete embebido está. Llamarla
// con `..\python-embed\python.exe` sería preguntarle a quien puede que no esté,
// y devolvería el mismo error ilegible que pretende sustituir. El precio es
// necesitar un Python 3.9+ en el PATH del que construye, que ya hace falta para
// aprovisionar el árbol.
//
// Exit code: 0 = el árbol puede construir. 1 = no, y dice qué falta.
// =============================================================================

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, "..", "..");
const BOOTSTRAP = path.join(RAIZ, "scripts", "bootstrap_dev_tree.py");

// El intérprete embebido, por la MISMA ruta que usan los otros scripts npm. Si
// esto cambia, cambia ahí también: es una sola decisión escrita en dos sitios y
// esta guarda existe justamente para que no diverjan en silencio.
const EMBEBIDO = path.join(RAIZ, "python-embed", "python.exe");

function pythonDelSistema() {
  // `py -3` es el lanzador oficial en Windows y sobrevive a que `python` sea el
  // alias de la Microsoft Store, que no ejecuta nada y abre una tienda.
  for (const [orden, args] of [["py", ["-3", "-V"]], ["python", ["-V"]], ["python3", ["-V"]]]) {
    const r = spawnSync(orden, args, { encoding: "utf8" });
    if (r.status === 0) return [orden, args.slice(0, -1)];
  }
  return null;
}

function fallar(lineas) {
  console.error("\n[check:runtime-arbol] el árbol NO puede construir el instalador.\n");
  for (const linea of lineas) console.error(`  ${linea}`);
  console.error(
    "\n  Las doce puertas siguientes dan por hecho el runtime. Sin él fallan" +
    "\n  con errores sobre CSP, goldens o Open Babel que no describen la causa." +
    "\n"
  );
  process.exit(1);
}

if (!existsSync(EMBEBIDO)) {
  const py = pythonDelSistema();
  if (!py) {
    fallar([
      `falta ${path.relative(RAIZ, EMBEBIDO)}`,
      "y tampoco hay un Python de sistema con el que aprovisionarlo.",
      "",
      "Instala Python 3.9+ y luego:",
      "  python scripts/provision_python_embed.py --fetch",
    ]);
  }
  fallar([
    `falta ${path.relative(RAIZ, EMBEBIDO)} — el intérprete embebido.`,
    "",
    "Un clon limpio no lo trae: son ~2,2 GB que no viajan en el repositorio.",
    "Dos vías, las dos documentadas en docs/82_CLON_LIMPIO_CONSTRUIBLE.md:",
    "",
    "  python scripts/provision_python_embed.py --fetch     (python.org + PyPI)",
    "  python scripts/bootstrap_dev_tree.py --fetch         (artefacto publicado)",
    "",
    "La segunda es más rápida y determinista, pero hoy se niega a correr:",
    "`runtime-base-v1.1.0.zip` no está publicado y no hay SHA-256 que verificar.",
  ]);
}

// El intérprete está. Que el resto del árbol esté lo sabe el bootstrap, que ya
// distingue AUSENTE de INCOMPLETO de CORRUPTO. No se reimplementa aquí.
const py = pythonDelSistema();
if (!py) {
  console.log(
    "[check:runtime-arbol] intérprete embebido presente; sin Python de sistema " +
    "no se pudo medir el resto del árbol. SALTA — saltar no es aprobar."
  );
  process.exit(0);
}

const [orden, previos] = py;
const r = spawnSync(orden, [...previos, BOOTSTRAP, "--check"], {
  cwd: RAIZ,
  encoding: "utf8",
});
if (r.status !== 0) {
  process.stdout.write(r.stdout ?? "");
  process.stderr.write(r.stderr ?? "");
  fallar([
    "`scripts/bootstrap_dev_tree.py --check` devolvió " + r.status + ".",
    "El informe de arriba dice qué pieza falta y de dónde sale.",
  ]);
}
console.log("[check:runtime-arbol] el runtime está y el árbol puede construir.");
