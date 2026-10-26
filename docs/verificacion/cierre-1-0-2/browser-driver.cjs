// QA manual asistida: navegador real, sin interceptar la API ni inyectar resultados.
const fs = require('node:fs');
const readline = require('node:readline');
const pw = require('D:/moldesign-build/frontend/node_modules/playwright');
(async () => {
  global.browser = await pw.chromium.launch({channel:'msedge', headless:true});
  global.context = await browser.newContext({viewport:{width:1440,height:900}, locale:'es-MX', acceptDownloads:true});
  global.page = await context.newPage();
  global.fs = fs;
  global.errors = [];
  page.on('pageerror', e=>errors.push(String(e)));
  console.log('READY '+await browser.version());
  const input = readline.createInterface({input:process.stdin});
  for await (const line of input) {
    try { const result = await new (Object.getPrototypeOf(async function(){}).constructor)(line)(); console.log(JSON.stringify(result??null)); }
    catch(e) { console.log(JSON.stringify({error:String(e),stack:e.stack})); }
  }
  await browser.close();
})();
