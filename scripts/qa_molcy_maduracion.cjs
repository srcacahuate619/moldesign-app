// QA real en Edge y Next dev. Las credenciales se mantienen sólo en memoria.
const { chromium } = require('../frontend/node_modules/@playwright/test');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const root = 'D:/moldesign-build/dist/molcy-maduracion-20260929';
(async () => {
  const session = await (await fetch('http://127.0.0.1:8037/qa/sesion')).json();
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  await context.addInitScript(data => localStorage.setItem('moldesign_auth',JSON.stringify({token:data.token,user:data.user})),session);
  const page = await context.newPage();
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('http://localhost:3001/molcy',{waitUntil:'domcontentloaded',timeout:120000});
  await page.getByLabel('Selecciona una fuente').waitFor({timeout:120000});
  console.log('Página cargada');
  const options=await page.locator('select option').allTextContents();
  console.log('Fuentes:',JSON.stringify(options));
  await page.getByLabel('Selecciona una fuente').selectOption(session.task_id);
  await page.getByRole('button',{name:'Prueba · 3 s'}).click();
  for (const device of ['gpu','cpu']) {
    await page.getByRole('button',{name: device==='gpu' ? /GPU · EEVEE/ : /CPU · Cycles/}).click();
    const responsePromise=page.waitForResponse(response=>response.url().endsWith('/molcy/trabajos')&&response.request().method()==='POST',{timeout:120000});
    await page.getByRole('button',{name:'Generar video',exact:true}).click();
    const response=await responsePromise;
    const created=await response.json();
    if(response.status()!==202) throw new Error('No comenzó el render: '+JSON.stringify(created));
    const started=Date.now();
    console.log('Render real',device,created.id);
    let job;
    do {
      await new Promise(resolve=>setTimeout(resolve,5000));
      const result=await fetch('http://127.0.0.1:8037/molcy/trabajos/'+created.id,{headers:{Authorization:'Bearer '+session.token}});
      job=await result.json();
      if(Date.now()-started>3600000) throw new Error('Render excedió una hora');
    } while(['en_cola','renderizando'].includes(job.estado));
    if(job.estado!=='completo') throw new Error('Render falló: '+JSON.stringify(job));
    const elapsed=(Date.now()-started)/1000;
    fs.writeFileSync(path.join(root,'trabajo-'+device+'.json'),JSON.stringify(job,null,2));
    await page.getByRole('button',{name:'Descargar MP4',exact:true}).waitFor({timeout:20000});
    const downloadPromise=page.waitForEvent('download',{timeout:30000});
    await page.getByRole('button',{name:'Descargar MP4',exact:true}).click();
    const download=await downloadPromise;
    const output=path.join(root,'molcy-moldex-'+device+'.mp4');
    await download.saveAs(output);
    const digest=crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex');
    if(digest!==job.video_sha256) throw new Error('Hash de descarga distinto del acta');
    const provenance=await (await fetch('http://127.0.0.1:8037/molcy/trabajos/'+job.id+'/procedencia',{headers:{Authorization:'Bearer '+session.token}})).json();
    fs.writeFileSync(path.join(root,'procedencia-'+device+'.json'),JSON.stringify(provenance,null,2));
    await page.screenshot({path:path.join(root,'interfaz-'+device+'.png'),fullPage:true});
    console.log(JSON.stringify({device,elapsed,sha256:digest,bytes:fs.statSync(output).size,duration:provenance.build.video.segundos||provenance.build.duracion_s}));
  }
  fs.writeFileSync(path.join(root,'errores-interfaz.json'),JSON.stringify(errors));
  await browser.close();
})().catch(error=>{console.error(error.message);process.exit(1);});
