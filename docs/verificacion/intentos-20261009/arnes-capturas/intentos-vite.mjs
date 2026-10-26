import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const root = process.cwd();
const intentos = JSON.parse(await readFile(resolve(root, "../backend/data/intentos_de_verificacion.json"), "utf8"));
const aliases = JSON.parse(await readFile(resolve(root, "../backend/data/target_aliases.json"), "utf8"));
const alias = aliases.find(target => target.pdb_id === "8HFI");
if (!alias) throw new Error("Falta el nombre de 8HFI en target_aliases");
await writeFile(resolve(root, ".tmp/intentos-datos.json"), JSON.stringify({ targets: [{ pdb_id: alias.pdb_id, name: alias.name, structural_family: alias.family,
  seccion_catalogo: "demostracion", intentos_verificacion: intentos.intentos.filter(i => i.pdb_id === alias.pdb_id) }] }));
const server = await createServer({ configFile: false, root: resolve(root, ".tmp"), publicDir: resolve(root, "public"), cacheDir: resolve(root, ".tmp/intentos-vite-cache"),
  plugins: [react()], define: { "process.env": "{}" }, resolve: { alias: { "@": root } }, css: { postcss: root },
  server: { host: "127.0.0.1", port: 5192, strictPort: true, fs: { allow: [root, "D:/moldesign-build/frontend/node_modules"] } },
});
await server.listen();
console.log("Intentos: http://127.0.0.1:5192/intentos-preview.html");
