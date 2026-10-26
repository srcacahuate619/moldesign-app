// scripts/check-npm-audit.mjs
// =============================================================================
// Guardia de la CI: ningún aviso CRÍTICO en las dependencias de producción, salvo
// los declarados uno por uno en `audit-excepciones.json`.
//
// POR QUE EXISTE. La CI corría `npm audit --omit=dev --audit-level=critical`, que
// es todo o nada. El 2026-10-25 salieron dos RCE de `next` 16.3.8 que sólo afectan
// a su servidor (MolDesign exporta estático) y el paso, que va segundo, dejaba sin
// correr CSP, tipos, pruebas, Playwright y el build: quien auditaba desde el
// repositorio público veía «frontend falla» y nada más.
//
// LO QUE SE COMPRUEBA. Cada aviso crítico tiene que estar exceptuado, y cada
// excepción tiene que seguir siendo verdad: falla si ha caducado, si la versión
// instalada del paquete ya no es la que se juzgó, o si el aviso ya no aparece
// (entonces sobra y hay que quitarla). Los avisos «high» o menores no bloquean,
// igual que antes.
//
// Lo que NO cubre: si el motivo de una excepción es cierto. Eso es una decisión
// del propietario, escrita en el propio fichero.
//
// Uso:  node scripts/check-npm-audit.mjs                 (corre npm audit)
//       node scripts/check-npm-audit.mjs --desde X.json  (lee un informe ya hecho)
// Exit code: 0 = limpio o todo exceptuado, 1 = bloquea.
// =============================================================================

import { execSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(AQUI, "..");
const EXCEPCIONES = path.join(FRONTEND, "audit-excepciones.json");

/** Los avisos críticos del informe JSON de npm audit, sin repetir: {aviso, paquete, titulo}. */
export function avisosCriticos(informe) {
  const vistos = new Map();
  for (const [paquete, vuln] of Object.entries(informe.vulnerabilities ?? {})) {
    for (const via of vuln.via ?? []) {
      if (typeof via === "string" || via.severity !== "critical") continue;
      const aviso = (String(via.url ?? "").match(/GHSA-[\w-]+/) ?? [String(via.source)])[0];
      if (!vistos.has(aviso)) vistos.set(aviso, { aviso, paquete: via.name ?? paquete, titulo: via.title ?? "" });
    }
  }
  return [...vistos.values()];
}

/** Compara el informe con las excepciones. `version(paquete)` da la versión instalada. */
export function evaluar(informe, excepciones, hoy, version) {
  const criticos = avisosCriticos(informe);
  const porAviso = new Map(excepciones.map((e) => [e.aviso, e]));
  const errores = [];
  const exceptuados = [];
  for (const c of criticos) {
    const e = porAviso.get(c.aviso);
    if (!e) {
      errores.push(`${c.aviso} (${c.paquete}): ${c.titulo} — crítico y sin excepción`);
      continue;
    }
    if (e.paquete !== c.paquete) errores.push(`${c.aviso}: la excepción es para ${e.paquete} y el aviso es de ${c.paquete}`);
    else if (version(e.paquete) !== e.version_instalada)
      errores.push(`${c.aviso}: se juzgó ${e.paquete}@${e.version_instalada} y hay ${version(e.paquete)}; vuelve a juzgarla`);
    else if (!e.caduca || hoy > e.caduca) errores.push(`${c.aviso}: la excepción caducó el ${e.caduca}`);
    else if (!e.motivo || !e.decision) errores.push(`${c.aviso}: la excepción no dice su motivo y quién la decidió`);
    else exceptuados.push(c);
  }
  const vivos = new Set(criticos.map((c) => c.aviso));
  for (const e of excepciones) {
    if (!vivos.has(e.aviso)) errores.push(`${e.aviso}: la excepción sobra (el aviso ya no aparece); quítala`);
  }
  return { errores, exceptuados };
}

/**
 * AUTOTEST - un guardian que no demuestra que ve, no sirve (AGENTS.md, restricción 2).
 */
function autotest() {
  const via = (ghsa, severity, name = "next") => ({ source: 1, name, severity, title: "t", url: `https://github.com/advisories/${ghsa}` });
  const informe = {
    vulnerabilities: {
      next: { via: [via("GHSA-aaaa-bbbb-cccc", "critical"), via("GHSA-dddd-eeee-ffff", "high")] },
      "next-auth": { via: ["next"] },
    },
  };
  const exc = { aviso: "GHSA-aaaa-bbbb-cccc", paquete: "next", version_instalada: "1.0.0", motivo: "m", decision: "d", caduca: "2026-12-31" };
  const v = () => "1.0.0";
  const casos = [
    ["crítico sin excepción", evaluar(informe, [], "2026-10-25", v), 1],
    ["crítico exceptuado", evaluar(informe, [exc], "2026-10-25", v), 0],
    ["caducada", evaluar(informe, [exc], "2027-01-01", v), 1],
    ["otra versión instalada", evaluar(informe, [exc], "2026-10-25", () => "1.0.1"), 1],
    ["sin motivo", evaluar(informe, [{ ...exc, motivo: "" }], "2026-10-25", v), 1],
    ["sobra", evaluar({ vulnerabilities: {} }, [exc], "2026-10-25", v), 1],
    ["sólo high", evaluar({ vulnerabilities: { next: { via: [via("GHSA-dddd-eeee-ffff", "high")] } } }, [], "2026-10-25", v), 0],
  ];
  for (const [nombre, r, esperados] of casos) {
    if (r.errores.length !== esperados) throw new Error(`autotest «${nombre}»: ${r.errores.length} errores, se esperaban ${esperados}`);
  }
  if (avisosCriticos(informe).length !== 1) throw new Error("autotest: el aviso transitivo de next-auth no debe contar aparte");
}

function informeDeNpm() {
  // npm audit sale con 1 cuando hay avisos: el JSON llega igual por stdout.
  try {
    return execSync("npm audit --omit=dev --json", { cwd: FRONTEND, encoding: "utf8", maxBuffer: 64 << 20 });
  } catch (error) {
    if (error.stdout) return error.stdout;
    throw error;
  }
}

function versionInstalada(paquete) {
  const ruta = path.join(FRONTEND, "node_modules", paquete, "package.json");
  return existsSync(ruta) ? JSON.parse(readFileSync(ruta, "utf8")).version : "(no instalado)";
}

function main() {
  autotest();
  const i = process.argv.indexOf("--desde");
  const crudo = i > 0 ? readFileSync(process.argv[i + 1], "utf8") : informeDeNpm();
  const informe = JSON.parse(crudo);
  if (informe.error) throw new Error(`npm audit no respondió: ${informe.error.summary ?? JSON.stringify(informe.error)}`);
  const { excepciones } = JSON.parse(readFileSync(EXCEPCIONES, "utf8"));
  const hoy = new Date().toISOString().slice(0, 10);
  const { errores, exceptuados } = evaluar(informe, excepciones, hoy, versionInstalada);
  for (const c of exceptuados) console.log(`[check-npm-audit] exceptuado ${c.aviso} (${c.paquete}): ${c.titulo}`);
  if (errores.length) {
    for (const e of errores) console.error(`[check-npm-audit] ERROR: ${e}`);
    console.error("\nUn aviso crítico se arregla actualizando, o se exceptúa en audit-excepciones.json con su motivo, la versión juzgada y una fecha de caducidad.");
    process.exit(1);
  }
  console.log(`[check-npm-audit] autotest OK; ningún aviso crítico sin excepción (${exceptuados.length} exceptuados).`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    console.error(`[check-npm-audit] ${error.message}`);
    process.exit(1);
  }
}
