// @vitest-environment node
import { execFileSync } from "node:child_process";
import { copyFileSync, linkSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

describe("procedencia del sello NSIS", () => {
  let temporal: string;
  let frontend: string;
  let ejecutableGit: string;
  let manifiesto: string;

  beforeAll(() => {
    temporal = mkdtempSync(path.join(os.tmpdir(), "moldesign-sello-test-"));
    frontend = path.join(temporal, "frontend");
    const scripts = path.join(frontend, "scripts");
    const nsis = path.join(frontend, "src-tauri", "target", "release", "bundle", "nsis");
    const bin = path.join(temporal, "bin");
    mkdirSync(scripts, { recursive: true });
    mkdirSync(nsis, { recursive: true });
    mkdirSync(bin);
    copyFileSync(path.resolve("scripts/sellar-instalador.mjs"), path.join(scripts, "sellar-instalador.mjs"));
    writeFileSync(path.join(frontend, "src-tauri", "tauri.conf.json"), JSON.stringify({ version: "1.0.4" }));
    writeFileSync(path.join(nsis, "MolDesign_1.0.4_x64-setup.exe"), "instalador de prueba");
    manifiesto = path.join(nsis, "release-manifest.json");

    // Un ejecutable real en PATH que se comporta como Git: Node ejecuta el
    // archivo cuyo nombre es el primer argumento (rev-parse o status).
    ejecutableGit = path.join(bin, process.platform === "win32" ? "git.exe" : "git");
    try { linkSync(process.execPath, ejecutableGit); } catch { copyFileSync(process.execPath, ejecutableGit); }
    writeFileSync(path.join(frontend, "rev-parse"), 'process.stdout.write("abc123\\n");');
    writeFileSync(path.join(frontend, "status"), [
      'if (process.env.TEST_GIT_STATUS === "error") process.exit(1);',
      'if (process.env.TEST_GIT_STATUS === "dirty") process.stdout.write(" M archivo\\n");',
    ].join("\n"));
  });

  afterAll(() => rmSync(temporal, { recursive: true, force: true }));

  function sellar(estado: string) {
    execFileSync(process.execPath, [path.join(frontend, "scripts", "sellar-instalador.mjs")], {
      cwd: frontend,
      env: { ...process.env, PATH: `${path.dirname(ejecutableGit)}${path.delimiter}${process.env.PATH}`, TEST_GIT_STATUS: estado },
      encoding: "utf8",
    });
    return JSON.parse(readFileSync(manifiesto, "utf8"));
  }

  it("declara limpio sólo cuando Git comprueba que no hay cambios", () => {
    expect(sellar("clean")).toMatchObject({ commit: "abc123", arbol_limpio: true });
    expect(sellar("dirty")).toMatchObject({ commit: "abc123", arbol_limpio: false });
  });

  it("conserva el commit y declara desconocido el estado si falla git status", () => {
    expect(sellar("error")).toMatchObject({ commit: "abc123", arbol_limpio: null });
  });
});
