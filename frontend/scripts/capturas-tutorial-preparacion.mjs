/**
 * Capturas del tutorial de Preparación de la pestaña Inicio, tomadas de la aplicación de verdad.
 *
 * Recorre lo que hace el investigador: evalúa la tetrabenazina contra 8T69 (Vina real), abre la pestaña Preparación,
 * elige el caso, lee la auditoría, asume una incertidumbre con una razón escrita, descarga el paquete de la corrida y
 * comprueba que el estado sigue en revisión. En cada paso guarda la pantalla y la caja del control que el tutorial señala.
 * Se ejecuta contra una cápsula de QA (backend real, export estático, datos nuevos):
 *
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 5 --capsula D:\moldesign-qa\tutorial-prep
 *   cd frontend && node scripts/capturas-tutorial-preparacion.mjs --app http://localhost:13015
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 5 --capsula D:\moldesign-qa\tutorial-prep --down
 *
 * Escribe `public/tutorial/preparacion/{es,en}/<paso>.webp` y `lib/tutorial/preparacion-marcas.json`. Con
 * `--idioma es|en` repite sólo ese idioma; el otro conserva sus marcas. El paquete descargado queda en `--zip <carpeta>`
 * (por defecto, la carpeta temporal del sistema) para comprobar lo que dice el tutorial.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
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
const APP = valor("--app", "http://localhost:13015");
const SOLO = valor("--idioma", null);
const CARPETA_ZIP = valor("--zip", path.join(os.tmpdir(), "tutorial-preparacion"));

const RECEPTOR = "8T69";
const SMILES = "COc1cc2c(cc1OC)C1CC(=O)C(CC(C)C)CN1CC2"; // tetrabenazina: el caso de la grabación del vídeo de Preparación
const SMILES_DE_EJEMPLO = "CC(=O)Oc1ccccc1C(=O)O";

const TEXTOS = {
  es: {
    caso: "Tetrabenazina · VMAT2", crear: "Crear un caso", elegirReceptor: /Elige receptor/i,
    buscar: "Buscar por PDB ID, nombre de la proteína, o familia...", receptorCargado: `Receptor elegido: ${RECEPTOR}`,
    ejecutar: "Ejecutar evaluación", guardar: "Guardar en MolDex", preparacion: "Preparación",
    elige: "Elige un caso…", revision: "Revisión", asumir: "Asumir esta incertidumbre", registrar: "Registrar",
    paquete: "Descargar paquete de la corrida", cerrarAviso: "Cerrar aviso",
    patronAviso: "Descargando archivo|Descarga completada",
    justificacion: "Se acepta la ausencia de bicapa: la serie se compara sólo entre análogos de este caso.",
  },
  en: {
    caso: "Tetrabenazine · VMAT2", crear: "Create a case", elegirReceptor: /Choose a receptor/i,
    buscar: "Search by PDB ID, protein name or family...", receptorCargado: `Receptor: ${RECEPTOR}`,
    ejecutar: "Run evaluation", guardar: "Save to MolDex", preparacion: "Preparation",
    elige: "Choose a case…", revision: "Review", asumir: "Accept this uncertainty", registrar: "Record",
    paquete: "Download the run package", cerrarAviso: "Close notice",
    patronAviso: "Downloading file|Download completed",
    justificacion: "The missing bilayer is accepted: the series is compared only among analogues in this case.",
  },
};

const RUTA_MARCAS = path.join(FRONTEND, "lib", "tutorial", "preparacion-marcas.json");

/** La pantalla y la caja del control, en píxeles de la captura. */
async function capturar(page, idioma, paso, control, marcas) {
  // Centrado: pegado a un borde lo taparía la barra o el botón flotante de MolChat.
  await control.evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
  await page.waitForTimeout(400);
  await difuminarRutas(page);
  const caja = await control.boundingBox();
  if (!caja) throw new Error(`${idioma}/${paso}: el control no está a la vista`);
  const encima = await tapadoPor(control);
  if (encima) throw new Error(`${idioma}/${paso}: el control señalado queda bajo un elemento (${encima})`);
  const png = await page.screenshot();
  const destino = path.join(FRONTEND, "public", "tutorial", "preparacion", idioma);
  await mkdir(destino, { recursive: true });
  await sharp(png).webp({ quality: 82 }).toFile(path.join(destino, `${paso}.webp`));
  marcas[idioma][paso] = { ancho: ANCHO, alto: ALTO, caja: [caja.x, caja.y, caja.width, caja.height].map(Math.round) };
  console.log(`  ${idioma}/${paso}: control en ${marcas[idioma][paso].caja.join(", ")}`);
}

/** La última página abierta: si un paso falla, se guarda una captura de lo que se ve en ese momento. */
let paginaActual = null;

async function recorrido(browser, idioma, marcas, textos) {
  const contexto = await browser.newContext({ viewport: { width: ANCHO, height: ALTO }, locale: IDIOMAS[idioma], acceptDownloads: true });
  const page = await contexto.newPage();
  paginaActual = page;
  page.setDefaultTimeout(60_000);

  // 1. Una evaluación de verdad, en un caso nuevo, para que Preparación tenga corrida que auditar.
  await page.goto(`${APP}/evaluation`);
  for (const aviso of await page.getByRole("button", { name: textos.cerrarAviso }).all()) await aviso.click().catch(() => {});
  await page.getByRole("button", { name: textos.crear, exact: true }).click();
  await page.locator("#case-name").fill(textos.caso);
  await page.getByRole("dialog").getByRole("button", { name: textos.crear, exact: true }).click();
  await page.waitForTimeout(2000);

  // 8T69 es de Verificados: se abre el catálogo, esa pestaña y la tarjeta del receptor.
  await page.getByRole("button", { name: textos.elegirReceptor }).first().click();
  // La pestaña lleva su contador pegado («Verificados1»): por eso el nombre se casa por prefijo.
  await page.getByRole("tab", { name: /^(Verificados|Verified)/ }).first().click();
  await page.getByRole("button", { name: new RegExp(`receptor · ${RECEPTOR}`, "i") }).first().click();
  await page.waitForTimeout(1500);

  const campo = await page.locator(`input[value="${SMILES_DE_EJEMPLO}"]`).first().elementHandle();
  await campo.fill(SMILES);
  await campo.press("Enter");
  await page.getByText(textos.receptorCargado, { exact: true }).first().waitFor({ timeout: 120_000 });
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: textos.ejecutar, exact: true }).first().click();

  // Vina de verdad: unos cuarenta segundos en este equipo.
  const guardar = page.getByRole("button", { name: textos.guardar, exact: true }).first();
  await guardar.waitFor({ timeout: 15 * 60_000 });
  await page.waitForTimeout(2500);
  await guardar.click();
  await page.waitForTimeout(2500);

  // 2. Paso uno: la pestaña Preparación, en la barra superior de Evaluación.
  const pestana = page.getByRole("link", { name: textos.preparacion, exact: true }).first();
  await capturar(page, idioma, "pestana", pestana, marcas);
  await pestana.click();
  await page.waitForURL(/\/preparacion/, { timeout: 60_000 });

  // 3. Paso dos: elegir el caso.
  const selector = page.locator("select").filter({ has: page.locator("option", { hasText: textos.elige }) }).first();
  await selector.waitFor();
  await capturar(page, idioma, "caso", selector, marcas);
  const opciones = await selector.locator("option").allTextContents();
  await selector.selectOption({ index: opciones.findIndex((o) => o.includes(textos.caso)) });

  // 4. Paso tres: la auditoría termina cuando aparece el estado de revisión.
  const estado = page.locator("section[aria-live='polite']").first();
  await page.waitForFunction((palabra) => document.querySelector("section[aria-live='polite']")?.innerText.includes(palabra),
    textos.revision, { timeout: 180_000 });
  await page.waitForTimeout(1500);
  await capturar(page, idioma, "auditoria", estado, marcas);

  // 5. Paso cuatro: abrir el bloque con un requisito decidible, asumirlo y registrar la razón escrita.
  const idPanel = await page.evaluate((texto) => {
    for (const panel of document.querySelectorAll("[id^='prep-details-']")) {
      if ([...panel.querySelectorAll("button")].some((b) => b.textContent.includes(texto))) return panel.id;
    }
    return null;
  }, textos.asumir);
  if (!idPanel) throw new Error(`${idioma}: ningún requisito admite «${textos.asumir}»`);
  const bloque = page.locator(`button[aria-controls="${idPanel}"]`);
  if ((await bloque.getAttribute("aria-expanded")) !== "true") await bloque.click();
  await page.waitForTimeout(600);
  const requisito = page.locator(`#${idPanel} li`).filter({ has: page.getByRole("button", { name: textos.asumir }) }).first();
  await requisito.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await requisito.getByRole("button", { name: textos.asumir }).click();
  // Al asumirla, el botón «Asumir» se cambia por el formulario: la fila se localiza ahora por su campo de texto.
  const fila = page.locator(`#${idPanel} li`).filter({ has: page.locator("textarea") }).first();
  const area = fila.locator("textarea");
  await area.waitFor();
  await area.fill(textos.justificacion);
  const registrar = fila.getByRole("button", { name: textos.registrar, exact: true });
  await capturar(page, idioma, "decision", registrar, marcas);
  await registrar.click();
  await page.waitForTimeout(3000);

  // 6. Paso cinco: el paquete de la corrida. Se descarga de verdad para comprobar que trae sumas por archivo.
  const exportar = page.getByRole("button", { name: textos.paquete, exact: true }).first();
  await capturar(page, idioma, "paquete", exportar, marcas);
  const descarga = page.waitForEvent("download", { timeout: 300_000 });
  await exportar.click();
  const archivo = await descarga;
  await mkdir(CARPETA_ZIP, { recursive: true });
  await archivo.saveAs(path.join(CARPETA_ZIP, `paquete-${idioma}.zip`));
  console.log(`  paquete ${idioma}: ${path.join(CARPETA_ZIP, `paquete-${idioma}.zip`)}`);

  // 7. Paso seis: el aviso de la descarga, en la esquina superior derecha. Se marca la tarjeta que lo contiene (con borde,
  // estrecha y con el nombre del ZIP dentro), así que la caja cubre el aviso entero y no sólo su texto.
  await page.waitForTimeout(800);
  const marcado = await page.evaluate((patron) => {
    const nodo = [...document.querySelectorAll("body *")].reverse()
      .find((e) => e.children.length === 0 && new RegExp(patron).test(e.textContent || ""));
    let tarjeta = nodo;
    while (tarjeta && !(getComputedStyle(tarjeta).borderTopWidth !== "0px" && tarjeta.getBoundingClientRect().width < 600
      && tarjeta.textContent.includes(".zip"))) tarjeta = tarjeta.parentElement;
    if (!tarjeta) return false;
    tarjeta.setAttribute("data-tutorial-aviso", "");
    return true;
  }, textos.patronAviso);
  if (!marcado) throw new Error(`${idioma}: no aparece el aviso de la descarga («${textos.patronAviso}»)`);
  await capturar(page, idioma, "aviso", page.locator("[data-tutorial-aviso]"), marcas);
  await contexto.close();
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
      if (el.children.length === 0 && /\.sandbox|moldesign-build|moldesign-qa|[A-Z]:\\/.test(el.textContent || "")) {
        el.style.filter = "blur(6px)";
      }
    }
  });
}

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
    await recorrido(browser, idioma, marcas, TEXTOS[idioma]).catch(async (error) => {
      const fallo = path.join(CARPETA_ZIP, `fallo-${idioma}.png`);
      await mkdir(CARPETA_ZIP, { recursive: true });
      await paginaActual?.screenshot({ path: fallo }).catch(() => {});
      console.error(`Fallo en ${idioma}. Pantalla en ${fallo}`);
      throw error;
    });
  }
  await mkdir(path.dirname(RUTA_MARCAS), { recursive: true });
  await writeFile(RUTA_MARCAS, JSON.stringify(marcas, null, 2) + "\n", "utf8");
  console.log(`Marcas: ${RUTA_MARCAS}`);
} finally {
  await browser.close();
}
