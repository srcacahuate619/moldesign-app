/**
 * Capturas del tutorial de Molcy de la pestaña Inicio, tomadas de la aplicación de verdad.
 *
 * Recorre lo que hace un usuario nuevo: crear un caso en Evaluación, elegir el receptor, ejecutar una evaluación (Vina
 * real), guardar la corrida en Moldex, elegirla en Molcy y generar el vídeo. En cada paso guarda la pantalla y la caja del control que el
 * tutorial señala. Se ejecuta contra una cápsula de QA (backend real, export estático, datos nuevos), una NUEVA por
 * idioma, porque el primer paso es la pestaña Evaluación sin ningún caso:
 *
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 5 --capsula D:\moldesign-qa\tutorial-es
 *   cd frontend && node scripts/capturas-tutorial-molcy.mjs --idioma es --app http://localhost:13015 --backend http://127.0.0.1:18015
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 5 --capsula D:\moldesign-qa\tutorial-es --down
 *
 * y lo mismo con `en` en otra carpeta. Al llegar a Molcy instala el Blender de MolDesign y Molecular Nodes por la API de
 * la cápsula, como haría ese usuario (unos 400 MB de blender.org).
 *
 * Escribe `public/tutorial/molcy/{es,en}/<paso>.webp` y `lib/tutorial/molcy-marcas.json`. Con `--depuracion <carpeta>`
 * deja además una captura de cada pantalla intermedia.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import sharp from "sharp";

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ANCHO = 1440;
const ALTO = 900;
const IDIOMAS = { es: "es-ES", en: "en-US" };

const args = process.argv.slice(2);
const valor = (nombre, defecto) => (args.includes(nombre) ? args[args.indexOf(nombre) + 1] : defecto);
const APP = valor("--app", "http://localhost:13014");
const BACKEND = valor("--backend", "http://127.0.0.1:18014");
const DEPURACION = valor("--depuracion", null);
const SOLO = valor("--idioma", null);
// Para repetir el recorrido en una cápsula que ya tiene el caso (depuración): el nombre lleva un número.
const NOMBRE_UNICO = args.includes("--nombre-unico");

async function depurar(page, nombre) {
  if (!DEPURACION) return;
  await mkdir(DEPURACION, { recursive: true });
  await page.screenshot({ path: path.join(DEPURACION, `${nombre}.png`) });
}

/** La pantalla y la caja del botón, en píxeles de la captura. */
async function capturar(page, idioma, paso, boton, marcas) {
  // Centrado: pegado al borde inferior lo tapa el botón flotante de MolChat.
  await boton.evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
  await page.waitForTimeout(400);
  await difuminarRutas(page);
  const caja = await boton.boundingBox();
  if (!caja) throw new Error(`${idioma}/${paso}: el botón no está a la vista`);
  const encima = await tapadoPor(boton);
  if (encima) throw new Error(`${idioma}/${paso}: el botón señalado queda bajo un elemento flotante (${encima})`);
  const png = await page.screenshot();
  const destino = path.join(FRONTEND, "public", "tutorial", "molcy", idioma);
  await mkdir(destino, { recursive: true });
  await sharp(png).webp({ quality: 82 }).toFile(path.join(destino, `${paso}.webp`));
  marcas[idioma][paso] = { ancho: ANCHO, alto: ALTO, caja: [caja.x, caja.y, caja.width, caja.height].map(Math.round) };
  console.log(`  ${idioma}/${paso}: botón en ${marcas[idioma][paso].caja.join(", ")}`);
}

async function recorrido(browser, idioma, marcas, textos) {
  const contexto = await browser.newContext({ viewport: { width: ANCHO, height: ALTO }, locale: IDIOMAS[idioma] });
  const page = await contexto.newPage();
  page.setDefaultTimeout(60_000);

  // 1. Crear un caso.
  await page.goto(`${APP}/evaluation`);
  const crear = page.getByRole("button", { name: textos.crear, exact: true });
  await crear.waitFor();
  await capturar(page, idioma, "caso", crear, marcas);
  await crear.click();
  const nombre = NOMBRE_UNICO ? `${textos.nombreDelCaso} ${Date.now() % 100000}` : textos.nombreDelCaso;
  await page.locator("#case-name").fill(nombre);
  await depurar(page, `${idioma}-dialogo`);
  await page.getByRole("dialog").getByRole("button", { name: textos.crear, exact: true }).click();
  await page.waitForTimeout(2000);
  await depurar(page, `${idioma}-caso-creado`);

  // 2. Elegir el receptor.
  const elegirReceptor = page.getByRole("button", { name: textos.elegirReceptor }).first();
  await elegirReceptor.waitFor();
  await capturar(page, idioma, "receptor", elegirReceptor, marcas);
  await elegirReceptor.click();
  await page.getByPlaceholder(textos.buscar).fill(RECEPTOR);
  await page.getByText(RECEPTOR, { exact: true }).first().click();
  await page.waitForTimeout(1500);

  // 3. La molécula, y ejecutar la evaluación.
  const campo = page.locator(`input[value="${SMILES_DE_EJEMPLO}"]`);
  if (await campo.count()) {
    const smiles = await campo.first().elementHandle();
    await smiles.fill(LIGANDO);
    await smiles.press("Enter");
  }
  // La tarjeta dice «Cargando 8HFI…» mientras llega el receptor: la captura es la de un receptor ya cargado.
  await page.getByText(textos.receptorCargado, { exact: true }).first().waitFor({ timeout: 120_000 });
  await page.waitForTimeout(1500);
  await depurar(page, `${idioma}-receptor-elegido`);
  const ejecutar = page.getByRole("button", { name: textos.ejecutar, exact: true }).first();
  await capturar(page, idioma, "evaluar", ejecutar, marcas);
  await ejecutar.click();

  // 4. Esperar el resultado (Vina de verdad) y guardarlo en Moldex.
  const guardar = page.getByRole("button", { name: textos.guardar, exact: true }).first();
  await guardar.waitFor({ timeout: 15 * 60_000 });
  await page.waitForTimeout(2500);
  await capturar(page, idioma, "guardar", guardar, marcas);
  await guardar.click();
  await page.waitForTimeout(2500);
  await depurar(page, `${idioma}-guardado`);

  // 5 y 6. Elegir la corrida guardada en Molcy (con Blender y Molecular Nodes instalados desde la app, si faltan).
  await prepararMolcy(page);
  await page.goto(`${APP}/molcy`);
  const fuente = page.locator("#molcy-source");
  await page.waitForFunction(() => (document.querySelector("#molcy-source")?.options.length ?? 0) > 1, null, { timeout: 120_000 });
  await fuente.selectOption({ index: 1 });
  // La corrida guardada pertenece al caso del paso 1: Molcy lo dice y guarda el vídeo en su carpeta.
  await page.getByText(textos.enElCaso(nombre)).first().waitFor({ timeout: 60_000 });
  await page.waitForTimeout(1000);
  await capturar(page, idioma, "corrida", fuente, marcas);
  const generar = page.getByRole("button", { name: textos.generar, exact: true });
  await page.waitForFunction(() => [...document.querySelectorAll("button")].some(b => /Generar video|Generate video/.test(b.textContent || "") && !b.disabled),
    null, { timeout: 120_000 });
  await page.waitForTimeout(2000);
  await depurar(page, `${idioma}-molcy`);
  await capturar(page, idioma, "molcy", generar, marcas);
  await contexto.close();
}

/**
 * Lo que haría un usuario nuevo la primera vez que abre Molcy: el Blender de MolDesign y Molecular Nodes, instalados
 * por la propia aplicación (`/molcy/blender` y `/molcy/addon`). Una cápsula redirige el perfil, así que no ve el
 * Blender de esta máquina.
 */
async function prepararMolcy(page) {
  const { token } = JSON.parse(await page.evaluate(() => localStorage.getItem("moldesign_auth")));
  const api = async (metodo, ruta, cuerpo) => {
    const respuesta = await fetch(`${BACKEND}${ruta}`, {
      method: metodo, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    });
    if (!respuesta.ok) throw new Error(`${metodo} ${ruta}: HTTP ${respuesta.status} ${await respuesta.text()}`);
    return respuesta.json();
  };
  const esperar = async (ruta) => {
    for (let i = 0; i < 360; i++) {
      const estado = await api("GET", ruta);
      if (estado.estado !== "instalando") return estado;
      await new Promise(r => setTimeout(r, 5000));
    }
    throw new Error(`${ruta}: sin terminar`);
  };
  if ((await api("GET", "/molcy/renderizador?recomprobar=true")).disponible) return;
  console.log("  Molcy: instalando el Blender de MolDesign y Molecular Nodes, como la primera vez");
  await api("PUT", "/molcy/configuracion", { modo: "administrado" });
  await api("POST", "/molcy/blender");
  const blender = await esperar("/molcy/blender");
  if (blender.estado !== "completo") throw new Error(`Blender: ${blender.motivo}`);
  await api("POST", "/molcy/addon");
  const addon = await esperar("/molcy/addon");
  if (addon.estado !== "completo") throw new Error(`Molecular Nodes: ${addon.motivo}`);
  const render = await api("GET", "/molcy/renderizador?recomprobar=true");
  if (!render.disponible) throw new Error(`Molcy sigue sin renderizador: ${render.motivo}`);
}

/**
 * ¿Qué tapa el control? Mira cinco puntos de su caja con `elementFromPoint`: si arriba hay otra cosa (el botón flotante de
 * MolChat, un aviso), la flecha señalaría algo que el usuario no ve. Devuelve una descripción o null.
 */
async function tapadoPor(control) {
  return control.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const puntos = [[0.5, 0.5], [0.08, 0.2], [0.92, 0.2], [0.08, 0.8], [0.92, 0.8]];
    for (const [fx, fy] of puntos) {
      const arriba = document.elementFromPoint(r.left + r.width * fx, r.top + r.height * fy);
      if (arriba && !el.contains(arriba) && !arriba.contains(el)) {
        return `${arriba.tagName.toLowerCase()}${arriba.getAttribute("aria-label") ? ` «${arriba.getAttribute("aria-label")}»` : ""}`;
      }
    }
    return null;
  });
}

/** Una ruta de esta máquina no va en una imagen del producto: se difumina antes de cada captura. */
async function difuminarRutas(page) {
  await page.evaluate(() => {
    for (const el of document.querySelectorAll("body *")) {
      if (el.children.length === 0 && /\.sandbox|moldesign-build|[A-Z]:\\/.test(el.textContent || "")) {
        el.style.filter = "blur(6px)";
      }
    }
  });
}

const RECEPTOR = "8HFI";
const SMILES_DE_EJEMPLO = "CC(=O)Oc1ccccc1C(=O)O";
const LIGANDO = "CNCCCN1c2ccccc2CCc2ccccc21"; // desipramina, el ligando del cristal de 8HFI

const TEXTOS = {
  es: { crear: "Crear un caso", ejecutar: "Ejecutar evaluación", nombreDelCaso: "Serie A · NET", elegirReceptor: /Elige receptor/i,
        buscar: "Buscar por PDB ID, nombre de la proteína, o familia...", receptorCargado: `Receptor elegido: ${RECEPTOR}`,
        guardar: "Guardar en MolDex", enElCaso: (caso) => `se guardarán en el caso «${caso}»`, generar: "Generar video" },
  en: { crear: "Create a case", ejecutar: "Run evaluation", nombreDelCaso: "Series A · NET", elegirReceptor: /Choose a receptor/i,
        buscar: "Search by PDB ID, protein name or family...", receptorCargado: `Receptor: ${RECEPTOR}`,
        guardar: "Save to MolDex", enElCaso: (caso) => `will be saved in case “${caso}”`, generar: "Generate video" },
};

const RUTA_MARCAS = path.join(FRONTEND, "lib", "tutorial", "molcy-marcas.json");
const browser = await chromium.launch({ channel: "msedge" });
let marcas = { es: {}, en: {} };
try {
  // Un recorrido de un solo idioma conserva las marcas del otro.
  marcas = { ...marcas, ...JSON.parse(await readFile(RUTA_MARCAS, "utf8")) };
} catch { /* primera vez */ }
try {
  for (const idioma of SOLO ? [SOLO] : Object.keys(IDIOMAS)) {
    console.log(`Recorrido en ${idioma}`);
    marcas[idioma] = {};
    await recorrido(browser, idioma, marcas, TEXTOS[idioma]);
  }
  await mkdir(path.dirname(RUTA_MARCAS), { recursive: true });
  await writeFile(RUTA_MARCAS, JSON.stringify(marcas, null, 2) + "\n", "utf8");
  console.log(`Marcas: ${RUTA_MARCAS}`);
} finally {
  await browser.close();
}
