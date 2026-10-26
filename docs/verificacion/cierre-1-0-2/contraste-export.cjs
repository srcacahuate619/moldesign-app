// Comprueba estilos calculados del export servido, no el TSX ni un DOM simulado.
module.exports = async label => {
  const readings=await page.getByRole('dialog').evaluate(dialog=>{
    const canvas=document.createElement('canvas'); canvas.width=canvas.height=1;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    const rgba=color=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].map((v,i)=>i===3?v/255:v);};
    const over=(front,back)=>front.slice(0,3).map((v,i)=>v*front[3]+back[i]*(1-front[3]));
    const luminance=rgb=>rgb.map(v=>{v/=255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[0.2126,0.7152,0.0722][i],0);
    const nodes=[...dialog.querySelectorAll('h2,input[type=text],input[type=number],select,p.text-amber-800,summary.text-amber-800,span.text-emerald-800')].filter(e=>!e.disabled && e.getBoundingClientRect().width>0);
    return nodes.map(e=>{
      let background=[255,255,255];const chain=[];
      for(let p=e;p;p=p.parentElement)chain.unshift(p);
      for(const p of chain)background=over(rgba(getComputedStyle(p).backgroundColor),background);
      const style=getComputedStyle(e);const foreground=over(rgba(style.color),background);
      const a=luminance(foreground),b=luminance(background),ratio=(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
      return {tag:e.tagName,id:e.id,text:e instanceof HTMLInputElement || e instanceof HTMLSelectElement ? e.value : e.textContent,foreground,background,ratio:+ratio.toFixed(3),passes:ratio>=4.5};
    });
  });
  const manifest=JSON.parse(fs.readFileSync('D:/moldesign-build/.worktrees/.sandbox/agente3/manifest.json','utf8'));
  const result={label,commit:manifest.repositorio.commit,export:manifest.export.huella,viewport:page.viewportSize(),locale:await page.evaluate(()=>document.documentElement.lang),theme:await page.evaluate(()=>document.documentElement.className),readings,passes:readings.length>0 && readings.every(r=>r.passes)};
  fs.writeFileSync(proof+`/contraste-${label}.json`,JSON.stringify(result,null,2));
  return result;
};
