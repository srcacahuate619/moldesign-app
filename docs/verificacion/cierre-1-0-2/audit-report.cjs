const fs=require('node:fs');
const root=__dirname;
const audit=JSON.parse(fs.readFileSync(root+'/audit-original.json'));
const modules=JSON.parse(fs.readFileSync(root+'/bundle-modules.json'));
const explanations=JSON.parse(fs.readFileSync(root+'/explain-all.json'));
const lock=JSON.parse(fs.readFileSync('D:/moldesign-ci/sol-1-0-2/frontend/package-lock.json'));
function advisories(name,seen=new Set()) {
  if(seen.has(name)) return [];
  seen.add(name);
  return (audit.vulnerabilities[name]?.via||[]).flatMap(v=>typeof v==='string'?advisories(v,seen):[v]);
}
function paths(v,tail=[],seen=new Set()) {
  const id=v.location||v.name;
  if(seen.has(id)) return [];
  const route=[v.name?`${v.name}@${v.version}`:'frontend',...tail];
  const deps=(v.dependents||[]).filter(d=>d.type!=='dev' && d.from);
  if(!deps.length) return [route.join(' → ')];
  return deps.flatMap(d=>paths(d.from,route,new Set([...seen,id])));
}
const fixes={
  'brace-expansion':'Sí: 5.0.12 satisface ^5.0.8; sólo construcción.',
  compression:'Sí: 1.8.2 satisface ^1.8.1; sólo servidor Molstar.',
  'fast-uri':'Sí: 3.1.8 satisface ^3.0.1; sólo utilidades de esquema/construcción.',
  'image-size':'No en los padres actuales ^1.0.2: el último 1.x es 1.2.1; requiere actualizar el padre para 2.0.3 o posterior. audit fixAvailable=true no demuestra compatibilidad con cada padre.',
  sharp:'Sí: 0.35.5 satisface ^0.35.4; servidor/optimización de imágenes de Next.',
  'source-map-js':'Sí: 1.2.2 satisface ^1.2.1; procesamiento CSS durante construcción.',
  uuid:'No: jayson exige ^8.3.2; el parche 11.1.1 requiere cambiar el padre y su contrato.',
  'stream-json':'No: jayson exige ^1.0.2; los tres avisos requieren 3.5.0, 3.5.1 y 3.6.0 respectivamente, fuera del rango.',
  braces:'No: audit no ofrece parche; requiere una versión corregida compatible de braces/micromatch o cambiar los padres. No se añade override.',
};
const records=[];
for(const [name,v] of Object.entries(audit.vulnerabilities)) {
  const matches=modules.filter(m=>(m.name||'').replaceAll('\\','/').includes(`node_modules/${name}/`));
  const routes=[...new Set(explanations.filter(e=>e.name===name && v.nodes.includes(e.location)).flatMap(e=>paths(e)))];
  const via=advisories(name);
  const versions=[...new Set(v.nodes.map(p=>lock.packages[p]?.version).filter(Boolean))];
  records.push({name,versions,severity:v.severity,nodes:v.nodes,routes,advisories:via,matches,fixAvailable:v.fixAvailable});
}
fs.writeFileSync(root+'/npm-evidence.json',JSON.stringify(records,null,2));
let doc='# Auditoría npm de producción\n\nMedida en el clon Windows `D:/moldesign-ci/sol-1-0-2`, commit `645bc1f2`, con `npm audit --omit=dev --json`: 0 críticas, 18 altas y 11 moderadas (29 entradas afectadas, 14 avisos directos). El export instrumentado de ese mismo commit identifica 2.790 módulos emitidos por el compilador cliente, incluidos módulos concatenados, mediante el chunkGraph de webpack. La instrumentación observa; no modifica next.config ni el código emitido.\n\nFuentes locales: [audit](audit-original.json), [npm explain](explain-all.json), [módulos y chunks](bundle-modules.json), [evidencia por paquete y todos sus caminos](npm-evidence.json), [instrumentación reproducible](inspect-bundle.cjs). `node_modules` no forma parte de los recursos de Tauri; se distribuye `out/`. `next.config.js` declara output export e imágenes sin optimización, y las importaciones del cliente están en WalletProvider, CertificationModal y KetcherEditorInner.\n\n| Paquete y versiones | Camino representativo (todos en evidencia) | Gravedad / aviso | Qué viaja / prueba | Arreglo dentro del rango sin force ni override |\n|---|---|---|---|---|\n';
for(const r of records) {
  const own=r.advisories.filter(v=>v.name===r.name);
  const list=own.length?own:[null];
  for(const a of list) {
    const links=(a?[a]:r.advisories).map(v=>`[${v.url.split('/').at(-1)}](${v.url})`);
    const ids=[...new Set(links)].join(', ');
    const shipment=r.matches.length?`Sí, ${r.matches.length} módulos cliente: ${[...new Set(r.matches.flatMap(m=>m.chunks))].join(', ')}. ${r.name==='uuid'?'Sólo index/v4/validate/stringify/regex/rng/native; no v3/v5/v6 afectados.':r.name==='jayson'?'Sólo cliente browser: no servidor ni stream-json.':'Entrada browser; la propagación de audit desde React Native/Metro no implica que ese código Node viaje.'}`:`No: cero módulos emitidos. ${/metro|react-native/.test(r.name)?'Herramientas nativas móviles/Metro, ausentes del export.':r.name==='stream-json'?'Node de jayson; ausente del cliente browser.':'Construcción/servidor Node; no existe ese servidor en Tauri.'}`;
    const fix=fixes[r.name]||`No disponible en audit; hereda ${[...new Set(r.advisories.map(v=>v.name))].join(', ')}. Requiere corregir esos paquetes y actualizar sus padres a rangos compatibles; no se fuerza la resolución.`;
    doc+=`| ${r.name} ${r.versions.join(', ')} | ${r.routes[0]||'Ver caminos detallados en npm-evidence.json'} | ${a?a.severity:r.severity}; ${own.length?'':'hereda '}${ids} | ${shipment} | ${fix} |\n`;
  }
}
doc+='\nLa búsqueda por nombre sin más no demuestra ausencia en código minificado: por eso se usa el conjunto completo de módulos emitidos y se asigna el archivo de chunk real. El árbol cliente no incluye braces, brace-expansion, compression, fast-uri, image-size, sharp, source-map-js, stream-json, React Native ni Metro. UUID 8.3.2 sí se incluye parcialmente; el advisory afecta v3/v5/v6 y sus buffers, que no aparecen entre los módulos emitidos. Esta diferencia reduce el alcance observado, sin convertir la auditoría de dependencias en un resultado limpio.\n\nNo se cambia el lockfile: ningún paquete con código emitido y aviso restante tiene una corrección dentro del rango exigido por sus padres. El salto de UUID exige una versión compatible de jayson/Solana; el de stream-json exige cambiar el contrato de jayson; braces requiere una corrección upstream. Se conserva el umbral de la CI y se repiten sus ocho pasos sobre el código final. Las fuentes primarias y sus límites están enlazados en cada aviso; la clasificación de qué viaja es una medición local, no una afirmación de GitHub.\n';
fs.writeFileSync(root+'/auditoria-npm.md',doc);
console.log(JSON.stringify({packages:records.length,direct:records.reduce((n,r)=>n+r.advisories.filter(v=>v.name===r.name).length,0),shipped:records.filter(r=>r.matches.length).map(r=>r.name)}));
