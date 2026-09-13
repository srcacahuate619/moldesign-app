import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

// Vitest config para MolDesign frontend.
//
// Decisiones:
// - environment: jsdom. Necesario porque AIContext, DownloadProvider y la
//   mayoria de los componentes usan `window`, `localStorage`, `fetch`.
// - setupFiles: vitest.setup.ts. Instala mocks globales (Tauri invoke, fetch,
//   localStorage) y @testing-library/jest-dom matchers.
// - plugins: @vitejs/plugin-react. Necesario para JSX/TSX. Vitest no transforma
//   JSX out-of-the-box.
// - resolve.alias respeta los mismos paths que tsconfig.json
//   ("@/components/*" etc.) para que los imports del codigo real funcionen
//   en tests sin cambios.
// - exclude: node_modules y .next son obvios; sacamos src-tauri para que no
//   se cuelen .rs files en el discover.
//
// Notas:
// - NO agregamos coverage en este config. Se añade despues si hace falta.
// - NO usamos globals: true para evitar el acoplamiento de `describe`/`it`/
//   `expect` como globales sin import. Mejores practicas de TS: el linter
//   falla si falta el import. En los tests hacemos
//   `import { describe, it, expect } from "vitest"`.

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.{test,spec}.{ts,tsx}"],
    testTimeout: 15000,
    exclude: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "src-tauri/**",
      "e2e/**",
      "dist/**",
    ],
    // ── EMFILE en Windows ────────────────────────────────────────────
    //
    // `lucide-react` resuelve CADA icono a su propio modulo. Con 37 archivos de
    // prueba en paralelo, cada worker abria cientos de archivos diminutos y
    // Windows agotaba los descriptores: la suite fallaba con
    // `EMFILE: too many open files` en un archivo distinto cada vez.
    //
    // Se ataca la causa —muchos archivos— y no el sintoma: prebundlear
    // `lucide-react` lo convierte en un modulo unico, en vez de bajar la
    // concurrencia y hacer la suite mas lenta para todos.
    deps: {
      optimizer: {
        web: {
          enabled: true,
          include: ["lucide-react"],
        },
      },
    },
    server: {
      deps: {
        // Inlinea los modulos que next.config.js marca como noParse
        // (paper.js y molstar/build). Vitest con esbuild los transforma sin
        // problema, pero esto evita race conditions con la config de Next.
        inline: [/paper[\\/]dist/, /molstar[\\/]build/],
      },
    },
  },
  resolve: {
    alias: {
      "@/components": resolve(rootDir, "components"),
      "@/lib": resolve(rootDir, "lib"),
      "@/context": resolve(rootDir, "context"),
      "@/hooks": resolve(rootDir, "hooks"),
    },
  },
});
