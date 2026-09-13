import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextCoreWebVitals,
  {
    // These rules enforce React Compiler constraints. MolDesign targets
    // React 19 but does not enable the compiler; keep the established
    // hooks correctness rules while avoiding a false migration requirement.
    rules: {
      "react-hooks/globals": "off",
      "react-hooks/immutability": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/purity": "off",
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
    },
  },
  globalIgnores([
    ".backups/**",
    ".trash-*/**",
    ".next/**",
    ".next-dev/**",
    ".next-e2e/**",
    "out/**",
    "test-results/**",
    "src-tauri/resources/**",
    "src-tauri/target/**",
    "public/3Dmol-min.js",
    "public/molstar*.js",
    "public/molstar/**",
    "next-env.d.ts",
  ]),
]);