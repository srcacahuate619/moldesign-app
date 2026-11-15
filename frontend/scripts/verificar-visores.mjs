/**
 * Comprueba en el export real que el visor de Evaluación nunca acaba en un recuadro sin salida.
 *
 * Cada caso estropea una cosa distinta y mira en qué visor termina la pantalla. Corre contra una cápsula de QA con el
 * motor de WebView2 (Edge):
 *
 *   node scripts/qa_sandbox/sandbox-up.mjs --agente 4
 *   cd frontend && node scripts/verificar-visores.mjs todos --app http://localhost:13014 --salida <carpeta>
 *
 * Casos (o `todos`):
 *   sin-webgl          el equipo no da ningún contexto WebGL → vista simplificada (lienzo 2D), y se puede girar
 *   molstar-falla      Mol* no consigue contexto al arrancar → se abre el visor ligero
 *   molstar-sin-lienzo la sonda consigue contexto pero los motores no → vista simplificada; la pestaña sigue en pie
 *   contexto-perdido   el equipo retira el contexto con el visor abierto → ligero → simplificada → «Reintentar 3D»
 *   web3d              el visor ligero responde al ratón y, quieto, no dibuja
 *
 * Termina con código 1 si algún caso no acaba donde debe. Es Edge y no la ventana de Tauri: prueba el export, no el
 * instalador.
 */
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const args = process.argv.slice(2);
const valor = (nombre, defecto) => (args.includes(nombre) ? args[args.indexOf(nombre) + 1] : defecto);
const APP = valor("--app", "http://localhost:13014");
const SALIDA = path.resolve(valor("--salida", "verificacion-visores"));
const RECEPTOR = valor("--receptor", "8HFI");
const CASOS = ["sin-webgl", "molstar-falla", "molstar-sin-lienzo", "contexto-perdido", "web3d"];
const pedidos = args[0] === "todos" ? CASOS : CASOS.includes(args[0]) ? [args[0]] : null;
if (!pedidos) { console.error(`Uso: node scripts/verificar-visores.mjs <todos|${CASOS.join("|")}> [--app URL] [--salida DIR]`); process.exit(2); }

const fallos = [];
function exigir(caso, condicion, que) {
  console.log(`  ${condicion ? "OK   " : "FALLA"} ${que}`);
  if (!condicion) fallos.push(`${caso}: ${que}`);
}

/**
 * Un punto del lienzo que de verdad es lienzo.
 *
 * POR QUÉ EXISTE. La primera versión arrastraba desde el centro de la caja del lienzo y comparaba capturas. Con la página
 * desplazada, ese centro quedaba bajo la cabecera fija del caso: el arrastre seleccionaba texto, la captura cambiaba por
 * el resaltado y la comprobación decía «gira» sin que el lienzo hubiera recibido nada. Ahora se centra el lienzo, se
 * pregunta al navegador qué hay en el punto y sólo se arrastra si es el lienzo.
 */
async function puntoLibre(page, lienzo) {
  await lienzo.evaluate((c) => c.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(300);
  return lienzo.evaluate((c) => {
    const b = c.getBoundingClientRect();
    for (const [fx, fy] of [[0.5, 0.5], [0.6, 0.6], [0.5, 0.7], [0.4, 0.6], [0.6, 0.45]]) {
      const x = b.left + b.width * fx, y = b.top + b.height * fy;
      if (document.elementFromPoint(x, y) === c) return { x, y };
    }
    return null;
  });
}

async function arrastrar(page, desde, dx, dy) {
  await page.mouse.move(desde.x, desde.y);
  await page.mouse.down();
  await page.mouse.move(desde.x + dx, desde.y + dy, { steps: 14 });
  await page.mouse.up();
}

/** Los píxeles del lienzo 2D, resumidos. Una captura no vale: cambia con un resaltado de selección o un desplazamiento. */
const huella2D = (lienzo) => lienzo.evaluate((c) => {
  const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
  let h = 0;
  for (let i = 0; i < d.length; i++) h = (Math.imul(h, 31) + d[i]) >>> 0;
  return h;
});

const textoSeleccionado = (page) => page.evaluate(() => String(window.getSelection()).length);

async function correr(caso) {
  console.log(`\n== ${caso}`);
  const carpeta = path.join(SALIDA, caso);
  fs.mkdirSync(carpeta, { recursive: true });
  const banderas = caso === "sin-webgl" ? ["--disable-gpu", "--disable-software-rasterizer"] : [];
  const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : undefined, headless: true, args: banderas });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "es-ES" })).newPage();
  page.setDefaultTimeout(60_000);

  if (caso === "molstar-falla") {
    await page.route("**/molstar.js", (route) => route.fulfill({ contentType: "text/javascript",
      body: 'window.molstar = { Viewer: { create: async () => { throw new Error("Could not create a WebGL rendering context"); } } };' }));
  }
  if (caso === "molstar-sin-lienzo") {
    // La sonda pide el contexto sin atributos y lo consigue; Mol* y three lo piden con `powerPreference` y no.
    await page.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (tipo, atributos) {
        if (/webgl/.test(String(tipo)) && atributos && "powerPreference" in atributos) return null;
        return original.call(this, tipo, atributos);
      };
    });
  }

  const visor = () => page.evaluate(() => ({
    molstar: !!document.querySelector(".msp-viewport canvas"),
    web3d: !!document.querySelector("canvas[data-engine]"),
    simplificada: !!document.querySelector('[data-testid="visor-sin-webgl"] canvas'),
    mensajeDeLaLibreria: /does not seem to be available/i.test(document.body.innerText),
    algoSalioMal: /Algo salió mal/.test(document.body.innerText),
  }));
  const foto = (n) => page.screenshot({ path: path.join(carpeta, `${n}.png`) }).catch(() => {});
  const perderContexto = (selector) => page.evaluate((s) => {
    const lienzo = document.querySelector(s);
    const gl = lienzo.getContext("webgl2") || lienzo.getContext("webgl");
    gl.getExtension("WEBGL_lose_context").loseContext();
  }, selector);

  try {
    await page.goto(`${APP}/evaluation`);
    const crear = page.getByRole("button", { name: "Crear un caso", exact: true });
    await crear.waitFor();
    await crear.click();
    await page.locator("#case-name").fill(`Visores ${caso} ${Date.now() % 100000}`);
    await page.getByRole("dialog").getByRole("button", { name: "Crear un caso", exact: true }).click();
    await page.getByRole("button", { name: /Elige receptor/i }).first().click();
    await page.getByPlaceholder("Buscar por PDB ID, nombre de la proteína, o familia...").fill(RECEPTOR);
    await page.getByText(RECEPTOR, { exact: true }).first().click();
    await page.getByText(`Receptor elegido: ${RECEPTOR}`, { exact: true }).first().waitFor({ timeout: 120_000 });
    await page.waitForTimeout(3500);

    if (caso === "sin-webgl") {
      const v = await visor();
      exigir(caso, v.simplificada && !v.molstar && !v.web3d, "sin WebGL se abre la vista simplificada y ningún motor 3D");
      const lienzo = page.locator('[data-testid="visor-sin-webgl"] canvas');
      const pintados = await lienzo.evaluate((c) => {
        const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
        let n = 0;
        for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
        return n;
      });
      exigir(caso, pintados > 1000, `el lienzo tiene dibujo (${pintados} píxeles)`);
      const explicacion = page.locator('[data-testid="visor-sin-webgl"] [role="status"]');
      exigir(caso, await explicacion.count() === 1, "al abrirse explica qué es esta vista y por qué se está viendo");
      const punto = await puntoLibre(page, lienzo);
      exigir(caso, !!punto, "hay un punto del lienzo sin nada encima desde el que arrastrar");
      if (punto) {
        const quieto = await huella2D(lienzo);
        await page.waitForTimeout(400);
        exigir(caso, quieto === await huella2D(lienzo), "quieto, el dibujo no cambia");
        // Control: el fallo que tuvo esta comprobación. Un arrastre que no cae en el lienzo no puede contar como giro.
        await arrastrar(page, { x: 300, y: 28 }, 160, 30);
        await page.waitForTimeout(300);
        exigir(caso, quieto === await huella2D(lienzo), "control: arrastrar fuera del lienzo no cambia el dibujo");
        await page.evaluate(() => window.getSelection().removeAllRanges());
        await arrastrar(page, punto, 160, 60);
        await page.waitForTimeout(300);
        exigir(caso, quieto !== await huella2D(lienzo), "arrastrar sobre el lienzo gira la estructura (cambian sus píxeles)");
        exigir(caso, await textoSeleccionado(page) === 0, "arrastrar no selecciona texto de la página");
        exigir(caso, await explicacion.count() === 0, "al empezar a girar, la explicación se recoge y deja ver la estructura");
      }
      exigir(caso, (await page.evaluate(() => document.documentElement.dataset.dibujo)) === "software", "queda anunciado que la pantalla la compone el procesador");
    }

    if (caso === "molstar-falla") {
      await page.waitForSelector("canvas[data-engine]", { timeout: 20_000 }).catch(() => {});
      const v = await visor();
      exigir(caso, v.web3d && !v.molstar, "al fallar Mol* se abre el visor ligero");
      exigir(caso, await page.getByText("Mol* no pudo dibujar en este equipo; se abrió el visor ligero.").count() > 0, "y se dice por qué");
    }

    if (caso === "molstar-sin-lienzo") {
      await page.waitForSelector('[data-testid="visor-sin-webgl"] canvas', { timeout: 30_000 }).catch(() => {});
      const v = await visor();
      exigir(caso, v.simplificada, "sin ningún motor capaz, se acaba en la vista simplificada");
      exigir(caso, !v.mensajeDeLaLibreria, "el mensaje crudo de Mol* no llega al usuario");
      exigir(caso, !v.algoSalioMal && await page.locator('[data-testid="editor-del-caso"]').count() === 1, "el resto de la pestaña sigue en pie");
    }

    if (caso === "contexto-perdido") {
      await perderContexto(".msp-viewport canvas");
      await page.waitForTimeout(1500);
      exigir(caso, (await visor()).molstar, "da tiempo a que el navegador devuelva el contexto antes de cambiar nada");
      await page.waitForSelector("canvas[data-engine]", { timeout: 15_000 }).catch(() => {});
      exigir(caso, (await visor()).web3d, "si no vuelve, abre el visor ligero");
      await perderContexto("canvas[data-engine]");
      await page.waitForSelector('[data-testid="visor-sin-webgl"] canvas', { timeout: 15_000 }).catch(() => {});
      exigir(caso, (await visor()).simplificada, "si el ligero también lo pierde, vista simplificada");
      await page.getByRole("button", { name: "Reintentar 3D" }).click();
      await page.waitForSelector(".msp-viewport canvas", { timeout: 30_000 }).catch(() => {});
      exigir(caso, (await visor()).molstar, "«Reintentar 3D» vuelve a Mol* cuando el equipo ya puede");
    }

    if (caso === "web3d") {
      await page.getByRole("button", { name: /Web3D/ }).last().click();
      await page.waitForSelector("canvas[data-engine]", { timeout: 30_000 });
      await page.waitForTimeout(2500);
      const lienzo = page.locator("canvas[data-engine]");
      // El mismo contador mide las dos cosas: si al arrastrar cuenta y quieto da cero, es que ve.
      await page.evaluate(() => {
        const c = document.querySelector("canvas[data-engine]");
        const gl = c.getContext("webgl2") || c.getContext("webgl");
        window.__dibujos = 0;
        for (const nombre of ["drawElements", "drawArrays", "drawElementsInstanced", "drawArraysInstanced"]) {
          const original = gl[nombre].bind(gl);
          gl[nombre] = (...a) => { window.__dibujos++; return original(...a); };
        }
      });
      const contar = async (ms) => {
        await page.evaluate(() => { window.__dibujos = 0; });
        await page.waitForTimeout(ms);
        return page.evaluate(() => window.__dibujos);
      };
      const punto = await puntoLibre(page, lienzo);
      exigir(caso, !!punto, "hay un punto del lienzo sin nada encima desde el que arrastrar");
      if (punto) {
        await page.evaluate(() => window.getSelection().removeAllRanges());
        const antes = await lienzo.screenshot();
        await page.evaluate(() => { window.__dibujos = 0; });
        await arrastrar(page, punto, 180, 40);
        const alArrastrar = await page.evaluate(() => window.__dibujos);
        await page.waitForTimeout(1200);
        exigir(caso, alArrastrar > 0, `arrastrar sobre el lienzo hace dibujar al visor (${alArrastrar} llamadas de dibujo)`);
        exigir(caso, await textoSeleccionado(page) === 0, "arrastrar no selecciona texto de la página");
        exigir(caso, !antes.equals(await lienzo.screenshot()), "y la escena queda girada");
      }
      await page.waitForTimeout(6000); // que termine la inercia del gesto
      const dibujos = await contar(3000);
      exigir(caso, dibujos === 0, `quieto no dibuja (${dibujos} llamadas de dibujo en 3 s)`);
    }
    await foto("final");
  } catch (e) {
    exigir(caso, false, `el guion no terminó: ${String(e?.message ?? e).slice(0, 200)}`);
    await foto("error");
  } finally {
    await browser.close();
  }
}

for (const caso of pedidos) await correr(caso);
console.log(fallos.length ? `\n${fallos.length} comprobación(es) en FALLA:\n- ${fallos.join("\n- ")}` : "\nTodos los casos acaban en un visor que dibuja.");
process.exit(fallos.length ? 1 : 0);
