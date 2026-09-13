import { spawn } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const playwrightCli = require.resolve("@playwright/test/cli");
const baseUrl = "http://127.0.0.1:3100";

const server = spawn(
  process.execPath,
  ["node_modules/next/dist/bin/next", "start", "-p", "3100"],
  {
    cwd: new URL("..", import.meta.url),
    env: { ...process.env, NEXT_DIST_DIR: ".next-e2e" },
    stdio: "inherit",
  },
);

let serverExit;
server.once("exit", (code, signal) => {
  serverExit = { code, signal };
});

async function waitForServer() {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (serverExit) {
      throw new Error(
        `Next terminó antes de estar listo (${serverExit.signal ?? serverExit.code}).`,
      );
    }
    try {
      const response = await fetch(baseUrl, { signal: AbortSignal.timeout(2_000) });
      if (response.ok) return;
    } catch {
      // El puerto todavía no está listo.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Next no respondió en ${baseUrl} durante 30 segundos.`);
}

async function stopServer() {
  if (serverExit) return;
  server.kill("SIGTERM");
  await Promise.race([
    new Promise((resolve) => server.once("exit", resolve)),
    new Promise((resolve) => setTimeout(resolve, 5_000)),
  ]);
  if (!serverExit) server.kill("SIGKILL");
}

let exitCode = 1;
try {
  await waitForServer();
  exitCode = await new Promise((resolve, reject) => {
    const test = spawn(process.execPath, [playwrightCli, "test", ...process.argv.slice(2)], {
      cwd: new URL("..", import.meta.url),
      env: { ...process.env, PLAYWRIGHT_EXTERNAL_SERVER: "1" },
      stdio: "inherit",
    });
    test.once("error", reject);
    test.once("exit", (code, signal) => {
      if (signal) reject(new Error(`Playwright terminó por señal ${signal}.`));
      else resolve(code ?? 1);
    });
  });
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
} finally {
  await stopServer();
}

process.exitCode = exitCode;
