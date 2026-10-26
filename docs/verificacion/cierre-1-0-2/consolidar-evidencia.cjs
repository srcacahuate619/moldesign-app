// Registra la revisión ya realizada y comprueba la integridad de sus archivos.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = __dirname;
const read = name => JSON.parse(fs.readFileSync(path.join(root,name),'utf8').replace(/^\uFEFF/,''));
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex');
const pattern = /^(inicio|opciones|acerca|molchat|evaluacion|resultado|nuevo-caso|detalles|parametros|parametros-final|motores|hotspots|dossier|historial|moldex|moldex-final|lotes|lote-fila|lote-dossier|catalogo-8hfi|catalogo-intento|catalogo-1uzj|preparacion-especie|preparacion-receptor|ciencia|ciencia-paper|molcy-8hfi|molcy-1uzj|molcy-corrida|lanzador)-(es|en)-(dark|light)-(1024|1440)$/;
const captures = [];
for (const file of fs.readdirSync(path.join(root,'capturas'))) {
  if (!file.endsWith('.json')) continue;
  const match = pattern.exec(file.slice(0,-5));
  if (!match) continue;
  const meta = read('capturas/'+file);
  if (meta.name!==file.slice(0,-5)) throw Error('Identidad de captura incoherente: '+file);
  captures.push({area:match[1],locale:match[2],theme:match[3],width:Number(match[4]),height:meta.viewport?.height??meta.size?.height,commit:meta.commit,export:meta.export,time:meta.time,archivo:'capturas/'+meta.name+'.png',sha256:hash('capturas/'+meta.name+'.png')});
}
captures.sort((a,b)=>a.archivo.localeCompare(b.archivo));
const areas = [...new Set(captures.map(c=>c.area))].sort();
if(areas.length!==30||captures.length!==240||areas.some(a=>captures.filter(c=>c.area===a).length!==8))throw Error('Matriz incompleta');
const seen = read('paneles-revisados.json');
if(seen.paneles.length!==60||new Set(seen.paneles).size!==60)throw Error('Paneles de revisión incompletos');
const ledger = {utc_consolidacion:new Date().toISOString(),metodo:seen.metodo,alcance:'240 visitas registradas; inspección directa de los 60 paneles. En páginas altas los paneles reúnen bandas de cabecera, centro y final; se conservan las capturas completas y su texto. La visita no acredita todas las ramas funcionales.',areas,capturas:captures,paneles:seen.paneles.map(name=>({archivo:'paneles/'+name,sha256:hash('paneles/'+name),revisado:true})),pdfs:{archivos:['dossier-es.pdf','dossier-en.pdf'].map(archivo=>({archivo,sha256:hash(archivo),paginas_revisadas:9})),observacion:seen.pdfs,defectos:'B01: frases del otro idioma; B05: línea huérfana. F09: visor del caso a 1024 no uniforme y visor del lote gris; no se declara comprobado el render nativo.'}};
fs.writeFileSync(path.join(root,'revision-visual.json'),JSON.stringify(ledger,null,2)+'\n');
for (const prefix of ['93b004cf','33be61be']) {
  const name = 'worktree-'+prefix+'-resultados.json';
  const rows = read(name);
  for(const row of rows){ row.registro=row.registro.replace('worktree-cierre-','worktree-'+prefix+'-'); if(!fs.existsSync(path.join(root,row.registro)))throw Error('Falta log '+row.registro); }
  fs.writeFileSync(path.join(root,name),JSON.stringify(rows,null,2)+'\n');
}
for(const p of read('paquetes-originales.json')) {
  if(hash(p.archivo)!==p.sha256||fs.statSync(path.join(root,p.archivo)).size!==p.bytes)throw Error('Paquete no íntegro '+p.archivo);
}
let checksums = 0;
const dossierDir = 'dossier-en/moldesign_case_350e8d04-4273-41f5-b818-72ab44f3c95e_run_27c62c96-a89/';
for(const line of fs.readFileSync(path.join(root,dossierDir+'checksums.sha256'),'utf8').trim().split(/\r?\n/)) {
  const match = /^([a-f0-9]{64})\s+(.+)$/.exec(line);
  if(!match||hash(dossierDir+match[2])!==match[1])throw Error('Checksum del dossier no íntegro');
  checksums++;
}
console.log(JSON.stringify({areas:areas.length,capturas:captures.length,paneles:seen.paneles.length,paquetes_verificados:4,checksums_dossier:checksums}));
