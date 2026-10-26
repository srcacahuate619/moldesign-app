import { chromium } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import assert from "node:assert/strict";
const out = resolve("../docs/capturas/intentos-20261009");
await mkdir(out, { recursive: true });
const fuente = await readFile(resolve("../backend/data/intentos_de_verificacion.json"));
const real = JSON.parse(fuente).intentos.filter(i => i.pdb_id === "8HFI");
const datos = JSON.parse(await readFile(resolve(".tmp/intentos-datos.json"), "utf8"));
assert.deepEqual(datos.targets[0].intentos_verificacion, real);
const checks = [];
for (const lang of ["es", "en"]) for (const width of [1440, 375]) {
  const browser = await chromium.launch({ channel: "msedge", headless: true, args: ["--disable-gpu", "--disable-lcd-text", "--font-render-hinting=none"] });
  try {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, locale: lang === "es" ? "es-MX" : "en-US", reducedMotion: "reduce" });
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.route("**/*", route => { const url = new URL(route.request().url()); return url.hostname === "127.0.0.1" && url.port === "5192" ? route.continue() : route.abort(); });
    await page.goto("http://127.0.0.1:5192/intentos-preview.html", { waitUntil: "networkidle" });
    const block = page.getByRole("region", { name: lang === "es" ? "Intentos publicados" : "Published attempts" });
    try { await block.waitFor({ timeout: 15000 }); }
    catch (error) { console.log(JSON.stringify({ errors, text: await page.locator("body").innerText() })); throw error; }
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(500);
    const text = await block.innerText();
    for (const value of ["ρ = 0.13", "-0.16–0.41", "n = 57", "CHEMBL853189", "CAL-8HFI-01", "0.6, 0.5, 4.1, 0.6, 3.7 Å"]) assert(text.includes(value), value);
    const card = page.locator(".target-card");
    await card.scrollIntoViewIfNeeded();
    assert.equal(await card.locator('[role="note"]').innerText(), lang === "es" ? "Verificación intentada: no superó la calibración" : "Verification attempted: did not pass calibration");
    assert.equal(await card.getByText(lang === "es" ? "Verificado" : "Verified", { exact: true }).count(), 0);
    const demo = await card.evaluate(node => node.closest("section").getAttribute("aria-label"));
    assert.equal(demo, lang === "es" ? "Demostración" : "Demo");
    await page.screenshot({ path: resolve(out, `selector-${lang}-${width}.png`) });
    const layout = await page.evaluate(() => {
      const root = document.getElementById("root"), dialog = document.querySelector('[role="dialog"]'), block = document.querySelector('section[aria-label="Intentos publicados"], section[aria-label="Published attempts"]'), card = document.querySelector(".target-card");
      const originalDialogWidth = dialog.getBoundingClientRect().width;
      const body = document.createElement("main");
      body.id = "captura-fragmentos";
      body.style.cssText = `width:${innerWidth}px;padding:16px;box-sizing:border-box;background:var(--bg);color:var(--text)`;
      for (const [source, id] of [[block, "fragmento-intento"], [card, "fragmento-tarjeta"]]) {
        const copy = source.cloneNode(true);
        copy.id = id;
        copy.style.width = `${Math.min(source.getBoundingClientRect().width, innerWidth - 32)}px`;
        copy.style.margin = "0 auto 24px";
        body.appendChild(copy);
      }
      root.style.display = "none";
      document.body.appendChild(body);
      return { viewport: innerWidth, originalDialogWidth, scrollWidth: document.documentElement.scrollWidth,
        title: card.querySelector('[role="note"]').title, ariaLabel: card.querySelector('[role="note"]').getAttribute("aria-label") };
    });
    assert(layout.scrollWidth <= width, JSON.stringify(layout));
    assert.equal(layout.title, layout.ariaLabel);
    assert(layout.title.includes("n = 57") && layout.title.includes("CAL-8HFI-01"));
    await page.locator("#fragmento-intento").screenshot({ path: resolve(out, `intento-${lang}-${width}.png`) });
    await page.locator("#fragmento-tarjeta").screenshot({ path: resolve(out, `tarjeta-${lang}-${width}.png`) });
    assert.deepEqual(errors, []);
    checks.push({ lang, width, ...layout, pageErrors: errors });
  } finally { await browser.close(); }
}
await writeFile(resolve(out, "comprobaciones.json"), JSON.stringify({ fuente: "backend/data/intentos_de_verificacion.json", fuente_sha256: createHash("sha256").update(fuente).digest("hex"),
  nombre: "backend/data/target_aliases.json; sin completar metadata ausente", componente: "TargetSelectorModal real y providers reales; subset 8HFI", capturas: "selector en su viewport; fragmentos de su DOM copiados sin recorte del contenedor de scroll", checks }, null, 2) + "\n");
console.log(JSON.stringify({ out, escenarios: checks.length, errores: 0 }));
