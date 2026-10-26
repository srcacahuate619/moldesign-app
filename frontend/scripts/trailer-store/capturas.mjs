/**
 * Tomas del tráiler de la Microsoft Store: el recorrido del tutorial de Molcy («Del caso al vídeo, en seis pasos»),
 * capturado de la aplicación de verdad para montarlo en vídeo.
 *
 * Es el mismo recorrido que `scripts/capturas-tutorial-molcy.mjs` (crear un caso, elegir 8HFI, acoplar la desipramina con
 * Vina real, guardar en Moldex, elegir la corrida en Molcy y generar el vídeo), con tres diferencias:
 *   - pantalla 16:9 (1440×810) a densidad 2, para que el montaje pueda acercarse a cada control sin perder nitidez;
 *   - guarda también los estados intermedios (el nombre tecleado, la búsqueda, la evaluación en curso, el render de Molcy);
 *   - pide el vídeo HORIZONTAL (1920×1080, el formato «biblioteca» de Molcy) y lo descarga del backend con su procedencia.
 *
 * Se ejecuta contra una cápsula de QA NUEVA (el primer paso es Evaluación sin ningún caso), con el Blender de esta máquina:
 *
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 5 --capsula D:\moldesign-qa\trailer-es
 *   cd frontend && node scripts/trailer-store/capturas.mjs --idioma es --app http://localhost:13015 \
 *     --backend http://127.0.0.1:18015 --blender E:\blender.exe --salida D:\moldesign-qa\trailer-es\tomas
 *
 * La cápsula redirige el perfil: para que el Blender existente vea Molecular Nodes, lánzala con BLENDER_USER_EXTENSIONS
 * apuntando a las extensiones reales (también después de un `--reset`). Escribe `<salida>/<toma>.png` y
 * `<salida>/tomas.json` (orden, caja del control en píxeles CSS, instante), y `<salida>/molcy/` con el MP4 y su estado.
 *
 * Después, con la misma cápsula y la misma corrida, `--solo-pose` añade las tomas de «Identificar mi diseño» y el giro
 * alrededor del ligando acoplado (`04b-*`), que el montaje usa en el paso 4.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const ANCHO = 1440;
const ALTO = 810;
const DENSIDAD = 2;
const IDIOMAS = { es: "es-ES", en: "en-US" };

const args = process.argv.slice(2);
const valor = (nombre, defecto) => (args.includes(nombre) ? args[args.indexOf(nombre) + 1] : defecto);
const APP = valor("--app", "http://localhost:13015");
const BACKEND = valor("--backend", "http://127.0.0.1:18015");
const IDIOMA = valor("--idioma", "es");
const SALIDA = path.resolve(valor("--salida", "tomas-trailer"));
const BLENDER = valor("--blender", null);
const ESPERA_RENDER_MIN = Number(valor("--espera-render-min", "90"));

const RECEPTOR = "8HFI";
const SMILES_DE_EJEMPLO = "CC(=O)Oc1ccccc1C(=O)O";
const LIGANDO = "CNCCCN1c2ccccc2CCc2ccccc21"; // desipramina, el ligando del cristal de 8HFI

const TEXTOS = {
  es: { crear: "Crear un caso", ejecutar: "Ejecutar evaluación", nombreDelCaso: "Serie A · NET", elegirReceptor: /Elige receptor/i,
        buscar: "Buscar por PDB ID, nombre de la proteína, o familia...", receptorCargado: `Receptor elegido: ${RECEPTOR}`,
        guardar: "Guardar en MolDex", enElCaso: (caso) => `se guardarán en el caso «${caso}»`, generar: "Generar video",
        horizontal: "Horizontal" },
  en: { crear: "Create a case", ejecutar: "Run evaluation", nombreDelCaso: "Series A · NET", elegirReceptor: /Choose a receptor/i,
        buscar: "Search by PDB ID, protein name or family...", receptorCargado: `Receptor: ${RECEPTOR}`,
        guardar: "Save to MolDex", enElCaso: (caso) => `will be saved in case “${caso}”`, generar: "Generate video",
        horizontal: "Horizontal" },
};

const inicio = Date.now();
const tomas = [];

async function guardarRegistro(extra = {}) {
  await writeFile(path.join(SALIDA, "tomas.json"), JSON.stringify({
    idioma: IDIOMA, ancho: ANCHO, alto: ALTO, densidad: DENSIDAD, receptor: RECEPTOR, ligando: LIGANDO,
    app: APP, tomas, ...extra,
  }, null, 2) + "\n", "utf8");
}

/** Una toma: la pantalla entera y, si se da, la caja del control que el montaje señala (en píxeles CSS). */
async function tomar(page, id, control = null, { centrar = true } = {}) {
  let caja = null;
  if (control) {
    if (centrar) await control.evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
    await page.waitForTimeout(350);
    const b = await control.boundingBox();
    if (!b) throw new Error(`${id}: el control no está a la vista`);
    caja = [b.x, b.y, b.width, b.height].map((v) => Math.round(v * 10) / 10);
  }
  await difuminarRutas(page);
  const archivo = `${id}.png`;
  await page.screenshot({ path: path.join(SALIDA, archivo) });
  tomas.push({ id, archivo, caja, t_ms: Date.now() - inicio });
  console.log(`  ${id}${caja ? `  caja ${caja.join(", ")}` : ""}`);
  await guardarRegistro();
}

/** Una ruta de esta máquina no va en una imagen del producto: se difumina antes de cada toma (como en el tutorial). */
async function difuminarRutas(page) {
  await page.evaluate(() => {
    for (const el of document.querySelectorAll("body *")) {
      if (el.children.length === 0 && /\.sandbox|moldesign-|[A-Z]:\\/.test(el.textContent || "")) {
        el.style.filter = "blur(6px)";
      }
    }
  });
}

/** La aplicación no se desplaza en `window` sino en sus contenedores: todos arriba del todo. */
async function subirDelTodo(page) {
  await page.evaluate(() => {
    window.scrollTo({ top: 0 });
    for (const el of document.querySelectorAll("*")) {
      if (el.scrollTop > 0) el.scrollTop = 0;
    }
  });
}

/** El lienzo WebGL más grande a la vista: el visor 3D de la corrida. */
async function visorMasGrande(page) {
  return page.evaluate(() => {
    let mejor = null;
    for (const c of document.querySelectorAll("canvas")) {
      const r = c.getBoundingClientRect();
      if (r.width < 200 || r.height < 150 || r.bottom < 0 || r.top > innerHeight) continue;
      if (!mejor || r.width * r.height > mejor.width * mejor.height) mejor = { x: r.x, y: r.y, width: r.width, height: r.height };
    }
    return mejor;
  });
}

async function api(page, metodo, ruta, cuerpo) {
  const { token } = JSON.parse(await page.evaluate(() => localStorage.getItem("moldesign_auth")));
  const respuesta = await fetch(`${BACKEND}${ruta}`, {
    method: metodo, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  });
  if (!respuesta.ok) throw new Error(`${metodo} ${ruta}: HTTP ${respuesta.status} ${await respuesta.text()}`);
  return respuesta;
}

/** Molcy con el Blender de esta máquina (modo «existente»): no se descarga nada. */
async function prepararMolcy(page) {
  const actual = await (await api(page, "GET", "/molcy/renderizador?recomprobar=true")).json();
  if (actual.disponible && actual.gpu_disponible) return actual;
  if (!BLENDER) throw new Error(`Molcy no tiene renderizador (${actual.motivo}); pasa --blender <blender.exe>`);
  await api(page, "PUT", "/molcy/configuracion", { modo: "existente", blender: BLENDER });
  const render = await (await api(page, "GET", "/molcy/renderizador?recomprobar=true")).json();
  if (!render.disponible) throw new Error(`Molcy sigue sin renderizador: ${render.motivo}`);
  if (!render.gpu_disponible) throw new Error(`Molcy no ve la GPU (el vídeo es sólo con GPU): ${render.motivo_gpu}`);
  console.log(`  Molcy: Blender ${render.version_blender?.join(".")}, Molecular Nodes ${render.molecular_nodes}, GPU ${render.gpu_nombre}`);
  return render;
}

async function recorrido(browser, textos) {
  const contexto = await browser.newContext({
    viewport: { width: ANCHO, height: ALTO }, deviceScaleFactor: DENSIDAD, locale: IDIOMAS[IDIOMA],
  });
  const page = await contexto.newPage();
  page.setDefaultTimeout(60_000);

  // 1. Crear un caso.
  await page.goto(`${APP}/evaluation`);
  const crear = page.getByRole("button", { name: textos.crear, exact: true });
  await crear.waitFor();
  await page.waitForTimeout(1200);
  await tomar(page, "01-caso", crear);
  await crear.click();
  const campoNombre = page.locator("#case-name");
  await campoNombre.waitFor();
  await page.waitForTimeout(500);
  await tomar(page, "01-dialogo-vacio", campoNombre, { centrar: false });
  // El nombre se teclea letra a letra: el montaje lo enseña escribiéndose.
  const nombre = textos.nombreDelCaso;
  for (let i = 1; i <= nombre.length; i++) {
    await campoNombre.fill(nombre.slice(0, i));
    await tomar(page, `01-tecleo-${String(i).padStart(2, "0")}`);
  }
  const confirmar = page.getByRole("dialog").getByRole("button", { name: textos.crear, exact: true });
  await tomar(page, "01-dialogo-lleno", confirmar, { centrar: false });
  await confirmar.click();
  await page.waitForTimeout(2000);

  // 2. Elegir el receptor.
  const elegirReceptor = page.getByRole("button", { name: textos.elegirReceptor }).first();
  await elegirReceptor.waitFor();
  await tomar(page, "02-receptor", elegirReceptor);
  await elegirReceptor.click();
  const buscador = page.getByPlaceholder(textos.buscar);
  await buscador.waitFor();
  await page.waitForTimeout(800);
  await tomar(page, "02-buscador", buscador, { centrar: false });
  await buscador.fill(RECEPTOR);
  await page.waitForTimeout(1200);
  const fila = page.getByText(RECEPTOR, { exact: true }).first();
  await tomar(page, "02-encontrado", fila, { centrar: false });
  await fila.click();
  await page.waitForTimeout(1500);

  // 3. La molécula y la evaluación.
  const campo = page.locator(`input[value="${SMILES_DE_EJEMPLO}"]`);
  if (await campo.count()) {
    const smiles = page.locator(`input[value="${SMILES_DE_EJEMPLO}"]`).first();
    await tomar(page, "03-smiles-ejemplo", smiles);
    const handle = await smiles.elementHandle();
    await handle.fill(LIGANDO);
    await handle.press("Enter");
  }
  await page.getByText(textos.receptorCargado, { exact: true }).first().waitFor({ timeout: 120_000 });
  await page.waitForTimeout(2500);
  const campoLigando = page.locator(`input[value="${LIGANDO}"]`).first();
  if (await campoLigando.count()) await tomar(page, "03-smiles-ligando", campoLigando);
  const ejecutar = page.getByRole("button", { name: textos.ejecutar, exact: true }).first();
  await tomar(page, "03-evaluar", ejecutar);
  await ejecutar.click();

  // La evaluación en curso (Vina real): el botón «Evaluando…» y, después, una toma cada ~2 s desde arriba (el visor con el
  // receptor y la caja) hasta que aparece el resultado.
  const guardar = page.getByRole("button", { name: textos.guardar, exact: true }).first();
  const cajaEjecutar = tomas.at(-1).caja;
  await page.waitForTimeout(800);
  await tomar(page, "03-evaluando-boton"); // el botón ya dice «Evaluando…»: se señala donde estaba
  tomas.at(-1).caja = cajaEjecutar;
  for (let i = 0; i < 600; i++) {
    if (await guardar.isVisible().catch(() => false)) break;
    await subirDelTodo(page);
    await tomar(page, `03-evaluando-${String(i).padStart(3, "0")}`);
    await page.waitForTimeout(1500);
  }
  await guardar.waitFor({ timeout: 20 * 60_000 });
  await page.waitForTimeout(3000);

  // El resultado, desde arriba: el visor con la pose acoplada, que se gira arrastrando como lo haría el usuario.
  await subirDelTodo(page);
  await page.waitForTimeout(2500);
  await tomar(page, "04-resultado-arriba");
  const visor = await visorMasGrande(page);
  if (visor) {
    const cx = visor.x + visor.width / 2;
    const cy = visor.y + visor.height / 2;
    await page.mouse.move(cx - 90, cy);
    await page.mouse.down();
    for (let i = 1; i <= 36; i++) {
      await page.mouse.move(cx - 90 + i * 5, cy + Math.sin(i / 6) * 4);
      await page.waitForTimeout(60);
      await tomar(page, `04-giro-${String(i).padStart(2, "0")}`);
    }
    await page.mouse.up();
    tomas.at(-1).visor = [visor.x, visor.y, visor.width, visor.height].map(Math.round);
  }
  for (let i = 1; i <= 6; i++) {
    await page.mouse.move(700, 500);
    await page.mouse.wheel(0, 260);
    await page.waitForTimeout(500);
    await tomar(page, `04-resultado-${String(i).padStart(2, "0")}`);
  }

  // 4. Guardar en Moldex. Al pulsarlo, el botón cambia de nombre: la toma de después no lo busca.
  await tomar(page, "04-guardar", guardar);
  const cajaGuardar = tomas.at(-1).caja;
  await guardar.click();
  await page.waitForTimeout(2500);
  await tomar(page, "04-guardado");
  tomas.at(-1).caja = cajaGuardar;

  // 5 y 6. Molcy: la corrida guardada, el formato horizontal y «Generar video».
  await prepararMolcy(page);
  await page.goto(`${APP}/molcy`);
  const fuente = page.locator("#molcy-source");
  await page.waitForFunction(() => (document.querySelector("#molcy-source")?.options.length ?? 0) > 1, null, { timeout: 120_000 });
  await page.waitForTimeout(1200);
  await tomar(page, "05-molcy-sin-fuente", fuente);
  await fuente.selectOption({ index: 1 });
  await page.getByText(textos.enElCaso(nombre)).first().waitFor({ timeout: 60_000 });
  await page.waitForTimeout(1200);
  await tomar(page, "05-corrida", fuente);

  const horizontal = page.getByRole("group", { name: /Formato de entrega|Delivery format/ })
    .getByRole("button", { name: new RegExp(textos.horizontal) });
  await tomar(page, "06-formato-vertical", horizontal);
  await horizontal.click();
  await page.waitForTimeout(1200);
  await tomar(page, "06-formato-horizontal", horizontal);

  const generar = page.getByRole("button", { name: textos.generar, exact: true });
  await page.waitForFunction(() => [...document.querySelectorAll("button")].some(b => /Generar video|Generate video/.test(b.textContent || "") && !b.disabled),
    null, { timeout: 120_000 });
  await page.waitForTimeout(1500);
  await tomar(page, "06-generar", generar);
  const pedido = Date.now();
  await generar.click();

  // El render (GPU): una toma cada 20 s, con el fotograma en vivo que enseña Molcy, hasta que el vídeo está listo.
  const listo = page.locator("video");
  let n = 0;
  while (Date.now() - pedido < ESPERA_RENDER_MIN * 60_000) {
    if (await listo.count()) break;
    await page.waitForTimeout(n === 0 ? 4000 : 20_000);
    await subirDelTodo(page);
    await tomar(page, `07-render-${String(n++).padStart(3, "0")}`);
    // Dónde está el fotograma en vivo: el montaje encuadra el render ahí.
    const vivo = await page.locator('section[aria-labelledby="molcy-preview-title"] figure img').first().boundingBox().catch(() => null);
    if (vivo) tomas.at(-1).vivo = [vivo.x, vivo.y, vivo.width, vivo.height].map(Math.round);
  }
  if (!(await listo.count())) throw new Error(`Molcy no terminó en ${ESPERA_RENDER_MIN} min`);
  const minutos = (Date.now() - pedido) / 60_000;
  await page.waitForTimeout(3000);
  await subirDelTodo(page);
  await tomar(page, "07-completo", listo.first());

  // El vídeo y su estado, del backend (con SHA-256 y procedencia), para el final del tráiler.
  const { trabajos } = await (await api(page, "GET", "/molcy/trabajos")).json();
  // La lista llega del más reciente al más antiguo (`creado_s`).
  const trabajo = trabajos.find((t) => t.estado === "completo" && ["biblioteca", "horizontal"].includes(t.formato));
  if (!trabajo) throw new Error("No hay un trabajo horizontal completo");
  const destino = path.join(SALIDA, "molcy");
  await mkdir(destino, { recursive: true });
  const estado = await (await api(page, "GET", `/molcy/trabajos/${trabajo.id}`)).json();
  await writeFile(path.join(destino, "trabajo.json"), JSON.stringify(estado, null, 2) + "\n", "utf8");
  const mp4 = Buffer.from(await (await api(page, "GET", `/molcy/trabajos/${trabajo.id}/video`)).arrayBuffer());
  await writeFile(path.join(destino, "molcy.mp4"), mp4);
  console.log(`  Molcy: ${mp4.length} bytes en ${minutos.toFixed(1)} min de render`);
  await guardarRegistro({ render_min: Math.round(minutos * 10) / 10, molcy_trabajo: trabajo.id });
  await contexto.close();
}

/**
 * `--solo-pose`: sobre la corrida que ya dejó el recorrido (misma cápsula), abre el caso, pulsa «Identificar mi diseño»
 * en el visor del resultado y gira la vista alrededor del ligando acoplado. Añade las tomas `04b-*` al registro.
 */
async function pose(browser, textos) {
  const previo = JSON.parse(await readFile(path.join(SALIDA, "tomas.json"), "utf8"));
  const { tomas: anteriores, ...extra } = previo;
  tomas.push(...anteriores.filter((t) => !t.id.startsWith("04b-")));
  const contexto = await browser.newContext({
    viewport: { width: ANCHO, height: ALTO }, deviceScaleFactor: DENSIDAD, locale: IDIOMAS[IDIOMA],
  });
  const page = await contexto.newPage();
  page.setDefaultTimeout(60_000);
  await page.goto(`${APP}/evaluation`);
  await page.getByText(textos.nombreDelCaso, { exact: true }).first().click();
  const identificar = page.getByRole("button", { name: /Identificar mi diseño|Identify my design/i }).first();
  await identificar.waitFor({ timeout: 120_000 });
  await subirDelTodo(page);
  await page.waitForTimeout(4000);
  await tomar(page, "04b-pose-antes", identificar, { centrar: false });
  const visor = await visorMasGrande(page);
  await identificar.click();
  for (let i = 1; i <= 18; i++) {
    await page.waitForTimeout(70);
    await tomar(page, `04b-enfoque-${String(i).padStart(2, "0")}`);
  }
  await page.waitForTimeout(800);
  const cx = visor.x + visor.width / 2;
  const cy = visor.y + visor.height / 2;
  await page.mouse.move(cx - 100, cy);
  await page.mouse.down();
  for (let i = 1; i <= 45; i++) {
    await page.mouse.move(cx - 100 + i * 4.5, cy + Math.sin(i / 7) * 5);
    await page.waitForTimeout(60);
    await tomar(page, `04b-giro-${String(i).padStart(2, "0")}`);
  }
  await page.mouse.up();
  tomas.at(-1).visor = [visor.x, visor.y, visor.width, visor.height].map(Math.round);
  await guardarRegistro(extra);
  await contexto.close();
}

await mkdir(SALIDA, { recursive: true });
const browser = await chromium.launch({ channel: "msedge" });
try {
  console.log(`Tomas del tráiler (${IDIOMA}) en ${SALIDA}`);
  if (args.includes("--solo-pose")) await pose(browser, TEXTOS[IDIOMA]);
  else await recorrido(browser, TEXTOS[IDIOMA]);
} finally {
  await browser.close();
}
