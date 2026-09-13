import { access, copyFile, mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

async function archivosBajo(directorio) {
  const resultado = [];
  for (const entrada of await readdir(directorio, { withFileTypes: true })) {
    const absoluto = path.join(directorio, entrada.name);
    if (entrada.isDirectory()) resultado.push(...await archivosBajo(absoluto));
    else if (entrada.isFile()) resultado.push(absoluto);
  }
  return resultado;
}

export async function normalizarSegmentosRsc(raiz) {
  const creados = [];
  for (const origen of await archivosBajo(raiz)) {
    const partes = path.relative(raiz, origen).split(path.sep);
    const indice = partes.findIndex((parte) => parte.startsWith("__next."));
    if (indice < 0 || indice === partes.length - 1) continue;

    const destino = path.join(raiz, ...partes.slice(0, indice), partes.slice(indice).join("."));
    try {
      const [existente, nuevo] = await Promise.all([readFile(destino), readFile(origen)]);
      if (!existente.equals(nuevo)) {
        throw new Error(`colision RSC con contenido distinto: ${path.relative(raiz, destino)}`);
      }
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
      await copyFile(origen, destino);
      creados.push(path.relative(raiz, destino));
    }
  }
  return creados;
}

async function autotest() {
  const temporal = await mkdtemp(path.join(os.tmpdir(), "moldesign-rsc-export-"));
  try {
    const anidado = path.join(temporal, "ruta", "__next.ruta", "__PAGE__.txt");
    await mkdir(path.dirname(anidado), { recursive: true });
    await writeFile(anidado, "payload-rsc", "utf8");
    const creados = await normalizarSegmentosRsc(temporal);
    const plano = path.join(temporal, "ruta", "__next.ruta.__PAGE__.txt");
    await access(plano);
    if ((await readFile(plano, "utf8")) !== "payload-rsc" || creados.length !== 1) {
      throw new Error("el autotest no materializo exactamente un segmento RSC plano");
    }
  } finally {
    await rm(temporal, { recursive: true, force: true });
  }
}

async function main() {
  await autotest();
  const aqui = path.dirname(fileURLToPath(import.meta.url));
  const raiz = path.resolve(aqui, "..", "out");
  await access(raiz);
  const creados = await normalizarSegmentosRsc(raiz);
  console.log(`[normalize-next-rsc-export] autotest OK; ${creados.length} segmentos planos materializados.`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`[normalize-next-rsc-export] ${error.message}`);
    process.exit(1);
  });
}