import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  // Playwright usa bundles de producción precompilados. Si una transición no
  // aparece en 20 s, es un fallo funcional y no una compilación incremental.
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? "github" : "line",
  use: {
    baseURL: "http://127.0.0.1:3100",
    channel: "msedge",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: process.env.PLAYWRIGHT_EXTERNAL_SERVER ? undefined : {
    // Ejecutar Node directamente evita que `cross-env` deje a `next start`
    // huérfano en Windows cuando Playwright cierra el servidor.
    command: "node node_modules/next/dist/bin/next start -p 3100",
    env: { NEXT_DIST_DIR: ".next-e2e" },
    url: "http://127.0.0.1:3100/",
    timeout: 30_000,
    reuseExistingServer: !process.env.CI,
  },
});
