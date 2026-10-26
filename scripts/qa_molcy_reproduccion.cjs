// Comprueba videos existentes en Edge; no inicia ningún render.
const { chromium } = require('../frontend/node_modules/@playwright/test');
const fs = require('fs');
const root = 'D:/moldesign-build/dist/molcy-maduracion-20260929';
(async () => {
  const session = await (await fetch('http://127.0.0.1:8037/qa/sesion')).json();
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const results = [];
  try {
    for (const device of ['gpu','cpu']) {
      const job = JSON.parse(fs.readFileSync(root+'/trabajo-'+device+'.json','utf8'));
      const context = await browser.newContext({viewport:{width:1440,height:1000}});
      await context.addInitScript(data => {
        localStorage.setItem('moldesign_auth',JSON.stringify({token:data.session.token,user:data.session.user}));
        localStorage.setItem('molcy-job:'+data.session.user.user_id,data.id);
      },{session,id:job.id});
      const page=await context.newPage();
      const violations=[]; const consoleErrors=[];
      await page.addInitScript(() => {
        window.__molcyCsp=[];
        document.addEventListener('securitypolicyviolation',e=>window.__molcyCsp.push(e.violatedDirective));
      });
      page.on('pageerror',error=>violations.push(error.message));
      page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text().split('\n')[0].replace(/\/molcy\/medios\/[A-Za-z0-9_-]+/g,'/molcy/medios/[acceso]'));});
      await page.goto('http://localhost:3001/molcy',{waitUntil:'domcontentloaded',timeout:120000});
      const video=page.locator('video');
      await video.waitFor({timeout:120000});
      await page.waitForFunction(()=>{const v=document.querySelector('video');return v&&v.readyState>=2&&v.videoWidth>0;},null,{timeout:30000});
      await video.evaluate(async v=>{v.muted=true;await v.play();});
      await page.waitForFunction(()=>document.querySelector('video').currentTime>0.3,null,{timeout:15000});
      const media=await video.evaluate(v=>({width:v.videoWidth,height:v.videoHeight,duration:v.duration,currentTime:v.currentTime,error:v.error?.code||null}));
      if(media.width!==720||media.height!==720||media.error) throw new Error('Video inválido '+JSON.stringify(media));
      if(device==='cpu'&&Math.abs(media.duration-6.6)>.05) throw new Error('Duración CPU incumple 3s + outro');
      await video.evaluate(v=>{v.pause();v.currentTime=v.duration-.5;});
      await page.waitForFunction(()=>!document.querySelector('video').seeking,null,{timeout:15000});
      const csp=await page.evaluate(()=>window.__molcyCsp);
      if(csp.some(value=>value.startsWith('media-src'))) throw new Error('CSP bloqueó reproducción');
      if(violations.length) throw new Error('Errores de página: '+JSON.stringify(violations));
      await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('CPU · Cycles')&&!b.disabled),null,{timeout:120000});
      await page.getByLabel('Selecciona una fuente').selectOption(session.task_id);
      await page.getByRole('button',{name:'Prueba · 3 s'}).click();
      await page.getByRole('button',{name:device==='cpu'?/CPU · Cycles/:/GPU · EEVEE/}).click();
      await video.evaluate(v=>{v.currentTime=1.5;});
      await page.waitForFunction(()=>!document.querySelector('video').seeking,null,{timeout:15000});
      await video.screenshot({path:root+'/fotograma-'+device+'.png'});
      await page.screenshot({path:root+'/reproduccion-'+device+'.png',fullPage:true});
      results.push({device,...media,cspMediaBlocked:false,seek:true,consoleErrors});
      await context.close();
    }
    fs.writeFileSync(root+'/reproduccion-resultados.json',JSON.stringify(results,null,2));
    console.log(JSON.stringify(results));
  } finally {await browser.close();}
})().catch(error=>{console.error(error.message);process.exit(1);});
