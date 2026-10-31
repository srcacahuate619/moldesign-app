import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync, execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.dirname(root);
const reportDir = path.join(repo, "docs/auditorias/i18n-frontend-2026-10-25/evidencia");
const connection = process.argv.includes("--connection");
const file = connection ? "lib/api.ts" : "components/interfaces/pro/ProAnalysisTabs.tsx";
const targetFile = path.join(root, file);
const original = await fs.readFile(targetFile, "utf8");
const head = execFileSync("git", ["show", "HEAD:frontend/" + file], { cwd: repo, encoding: "utf8" });
assert.equal(original.replace(/\r\n/g, "\n"), head.replace(/\r\n/g, "\n"), file + " tiene cambios ajenos; no mutarlo.");
const base = execFileSync("git", ["show", "4fc7a928:frontend/" + file], { cwd: repo, encoding: "utf8" });
const q = String.fromCharCode(96), dollar = String.fromCharCode(36);
const pattern = connection ? /const ERROR_DE_CONEXION =[\s\S]*?;\r?\n/
  : 't("rx_open_failed_checks", { count: estadoDeLaPoseActiva.failedCount })';
const oldValue = connection ? base.match(pattern)?.[0]
  : q + "Ver los " + dollar + "{estadoDeLaPoseActiva.failedCount} controles que fallan" + q;
assert(oldValue && base.includes(oldValue), "El literal anterior no está en la base.");
assert(connection ? original.match(pattern)?.[0].includes('frontendMessage("pg_hist_error_conexion")') : original.includes(pattern));
const phrase = connection ? "Error de conexión" : "controles que fallan";
const state = connection ? "historial sin conexión" : "detalle de la pose fallida";
const testPattern = connection ? "toda revisión coincide" : "texto pendiente de traducir";
const suffix = connection ? "-conexion" : "";
const record = { reverted: file, base: "4fc7a928", checks: [] };
function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: "utf8", maxBuffer: 12 * 1024 * 1024 });
  if (result.error) throw result.error;
  return { status: result.status, output: (result.stdout ?? "") + (result.stderr ?? "") };
}
function build() {
  const result = run("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", "npm run build:desktop"]);
  assert.equal(result.status, 0, "Falló el build:\n" + result.output.slice(-5000));
}
const mutant = original.replace(pattern, oldValue).replace(/\r\n/g, "\n");
let changed = false;
try {
  await fs.writeFile(targetFile, mutant);
  changed = true;
  const scan = run(process.execPath, ["scripts/finish-i18n-frontend.cjs", "--json"]);
  const signatures = JSON.parse(scan.output);
  assert(signatures.some(text => text.includes(phrase)));
  const vitest = path.join(path.dirname(require.resolve("vitest/package.json")), "vitest.mjs");
  const ratchet = run(process.execPath, [vitest, "run", "lib/__tests__/interfazSinTextoFijo.test.ts",
    "-t", testPattern, "--maxWorkers", "1", "--reporter", "dot"]);
  assert.equal(ratchet.status, 1, ratchet.output);
  assert(ratchet.output.includes(phrase), "El fallo estático no es la regresión esperada");
  record.checks.push({ command: "vitest run lib/__tests__/interfazSinTextoFijo.test.ts -t '" + testPattern + "' --maxWorkers 1 --reporter dot",
    expectedExit: 1, actualExit: ratchet.status, output: ratchet.output.slice(-4500) });
  console.log("OK el trinquete falla al revertir el arreglo real");
  console.log("Construyendo export con el literal anterior...");
  build();
  const artifact = run(process.execPath, ["e2e/i18n-export.mjs", "--report=" + path.join(reportDir, "export-c-mutante" + suffix + ".json")]);
  assert.equal(artifact.status, 1, artifact.output);
  assert(artifact.output.includes(state) && artifact.output.includes(phrase),
    "El export falló por otra causa:\n" + artifact.output.slice(-4500));
  record.checks.push({ command: "node e2e/i18n-export.mjs (export con el literal de 4fc7a928)",
    expectedExit: 1, actualExit: artifact.status, output: artifact.output.slice(-4500) });
  console.log("OK el guardián del export falla en " + state);
} finally {
  if (changed) {
    assert.equal(await fs.readFile(targetFile, "utf8"), mutant, "El archivo cambió durante la prueba; conservarlo y revisar antes de restaurar.");
    await fs.writeFile(targetFile, head);
    console.log("Arreglo restaurado; reconstruyendo export limpio...");
    build();
  }
  await fs.writeFile(path.join(reportDir, "control-regresion-c" + suffix + ".json"), JSON.stringify(record, null, 2) + "\n");
}
const clean = run(process.execPath, ["e2e/i18n-export.mjs", "--report=" + path.join(reportDir, "export-c.json")]);
assert.equal(clean.status, 0, clean.output);
record.checks.push({ command: "node e2e/i18n-export.mjs (export limpio reconstruido)", expectedExit: 0, actualExit: clean.status,
  output: clean.output.slice(-4000) });
await fs.writeFile(path.join(reportDir, "control-regresion-c" + suffix + ".json"), JSON.stringify(record, null, 2) + "\n");
console.log(clean.output);
