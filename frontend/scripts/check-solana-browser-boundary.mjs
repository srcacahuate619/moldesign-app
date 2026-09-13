import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MARCADORES_PROHIBIDOS = [
  "react-native/Libraries",
  "StreamValues",
];

async function javascriptBajo(directorio) {
  const archivos = [];
  for (const entrada of await readdir(directorio, { withFileTypes: true })) {
    const absoluto = path.join(directorio, entrada.name);
    if (entrada.isDirectory()) archivos.push(...await javascriptBajo(absoluto));
    else if (entrada.isFile() && entrada.name.endsWith(".js")) archivos.push(absoluto);
  }
  return archivos;
}

export async function hallarFugas(raiz) {
  const fugas = [];
  for (const archivo of await javascriptBajo(raiz)) {
    const contenido = await readFile(archivo, "utf8");
    for (const marcador of MARCADORES_PROHIBIDOS) {
      if (contenido.includes(marcador)) fugas.push({ archivo: path.relative(raiz, archivo), marcador });
    }  }
   return fugas;
}

async function autotest() {
  const temporal = await mkdtemp(path.join(os.tmpdir(), "moldesign-solana-boundary-"));
  try {
    await mkdir(path.join(temporal, "chunks"));
    await writeFile(path.join(temporal, "chunks", "limpio.js"), "SolanaMobileWalletAdapter", "utf8");
    if ((await hallarFugas(temporal)).length !== 0) throw new Error("falso positivo en muestra limpia");
    await writeFile(path.join(temporal, "chunks", "sucio.js"), "react-native/Libraries StreamValues", "utf8");
    if ((await hallarFugas(temporal)).length !== 2) throw new Error("el autotest no detecto ambas fugas");
  } finally {
    await rm(temporal, { recursive: true, force: true });
  }
}

async function main() {
  await autotest();
  const aqui = path.dirname(fileURLToPath(import.meta.url));
  const raiz = path.resolve(aqui, "..", "out");
  const fugas = await hallarFugas(raiz);
  if (fugas.length) {
    for (const fuga of fugas) console.error(`[check-solana-browser-boundary] ${fuga.marcador} en ${fuga.archivo}`);
    process.exit(1);
  }
  console.log(`[check-solana-browser-boundary] autotest OK; export sin React Native/Metro ni stream-json (${MARCADORES_PROHIBIDOS.length} marcadores).`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`[check-solana-browser-boundary] ${error.message}`);
    process.exit(1);
  });
}