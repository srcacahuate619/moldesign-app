const fs=require('node:fs');
const path=require('node:path');

/** Caller supplies a real Playwright page and waits for the intended terminal state. */
async function capturarEstado(page,destino,nombre,notas=''){
  if(!/^[a-zA-Z0-9][a-zA-Z0-9_-]+$/.test(nombre))throw new Error('Nombre de evidencia inválido');
  const root=path.resolve(destino);
  fs.mkdirSync(path.join(root,'evidencia'),{recursive:true});
  fs.mkdirSync(path.join(root,'capturas'),{recursive:true});
  const data=await page.evaluate(()=>({
    url:location.href,lang:document.documentElement.lang,text:document.body.innerText,
    attributes:[...document.querySelectorAll('[title],[aria-label],[aria-description],[placeholder],[alt]')]
      .filter(el=>el.getClientRects().length)
      .map(el=>({tag:el.tagName,id:el.id,title:el.getAttribute('title'),ariaLabel:el.getAttribute('aria-label'),ariaDescription:el.getAttribute('aria-description'),placeholder:el.getAttribute('placeholder'),alt:el.getAttribute('alt')})),
  }));
  Object.assign(data,{name:nombre,notes:notas,timestamp:new Date().toISOString()});
  fs.writeFileSync(path.join(root,'evidencia',nombre+'.json'),JSON.stringify(data,null,2)+'\n');
  await page.screenshot({path:path.join(root,'capturas',nombre+'.png'),fullPage:true,timeout:10000,animations:'disabled'});
  return data;
}
module.exports={capturarEstado};
