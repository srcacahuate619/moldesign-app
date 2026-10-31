const {archivo: archivoExterno}=require('./archivo-fase-a.cjs');
const fs=require('node:fs'),path=require('node:path');
const {createRequire}=require('node:module');
const ROOT=path.resolve(__dirname,'../../../../frontend');
const AUD=path.resolve(ROOT,'../docs/auditorias/i18n-frontend-2026-10-25');
const ts=createRequire(ROOT+'/package.json')('typescript');
const data=JSON.parse(fs.readFileSync(archivoExterno('evidencia/barrido-estatico-v3.json'),'utf8'));
const all=[];
function walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){if(['__tests__','node_modules','traducciones'].includes(e.name))continue;const p=path.join(dir,e.name);if(e.isDirectory())walk(p);else if(/\.tsx?$/.test(p)&&!p.includes('.test.'))all.push(p);}}
for(const d of ['app','components','hooks','lib','context'])walk(ROOT+'/'+d);
const imports={};
for(const file of all){
  const sf=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,file.endsWith('.tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
  const refs=[];
  function add(s){if(!s.startsWith('.')&&!s.startsWith('@/'))return;const base=s.startsWith('@/')?ROOT+'/'+s.slice(2):path.resolve(path.dirname(file),s);const found=[base,base+'.ts',base+'.tsx',base+'/index.ts',base+'/index.tsx'].find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());if(found)refs.push(path.relative(ROOT,found).replaceAll('\\','/'));}
  function visit(n){if((ts.isImportDeclaration(n)||ts.isExportDeclaration(n))&&n.moduleSpecifier&&ts.isStringLiteral(n.moduleSpecifier))add(n.moduleSpecifier.text);if(ts.isCallExpression(n)&&(n.expression.kind===ts.SyntaxKind.ImportKeyword||n.expression.getText(sf)==='require')&&n.arguments[0]&&ts.isStringLiteral(n.arguments[0]))add(n.arguments[0].text);ts.forEachChild(n,visit);}visit(sf);
  imports[path.relative(ROOT,file).replaceAll('\\','/')]=refs;
}
const roots=all.filter(p=>/[/\\]app[/\\].*[/\\](page|layout|loading|error|not-found)\.tsx$/.test(p)||/[/\\]app[/\\](page|layout|loading|error|not-found)\.tsx$/.test(p)).map(p=>path.relative(ROOT,p).replaceAll('\\','/'));
const reachable=new Set(),queue=[...roots];while(queue.length){const f=queue.shift();if(reachable.has(f))continue;reachable.add(f);queue.push(...imports[f]||[]);}
const rows=data.literales.map((r,index)=>{
  let pista=r.clasificacion==='excluir-provisional'?r.motivo:'pendiente';
  if(r.motivo?.startsWith('argumento de t()'))pista=r.argumento_t===0&&(r.clave_existente!==null||r.dict.length>0)?'clave/alias de t existente':'pendiente';
  if(!reachable.has(r.archivo))pista='sin importación desde las rutas';
  else if(r.contexto?.some(c=>c.tipo==='columna'&&c.idioma.replaceAll('"','').replaceAll("'",'')==='es'))pista='columna es: comprobar selector';
  else if(r.contexto?.some(c=>c.tipo==='condicion'&&/locale|isEnglish|idioma|lang/.test(c.condicion)))pista='condición de idioma: comprobar rama';
  return {...r,indice:index,pista};
});
const argv=process.argv.slice(2);
if(argv[0]==='--summary'){
  const groups={};for(const r of rows)groups[r.pista]=(groups[r.pista]||0)+1;
  const files={};for(const r of rows.filter(r=>r.pista==='pendiente'))files[r.archivo]=(files[r.archivo]||0)+1;
  console.log(JSON.stringify({total:rows.length,grupos:groups,pendientes:files,alcanzables:reachable.size},null,2));
}else if(argv[0]==='--file'){
  const file=argv[1],lines=fs.readFileSync(ROOT+'/'+file,'utf8').split(/\r?\n/);
  for(const r of rows.filter(r=>r.archivo===file&&(argv.includes('--all')||r.pista==='pendiente'))){console.log(JSON.stringify({i:r.indice,line:r.linea,text:r.texto,dict:r.dict.map(d=>d.key),pista:r.pista,contexto:r.contexto}));if(argv.includes('--context'))console.log(lines.slice(Math.max(0,r.linea-3),r.linea+2).map((l,i)=>`${Math.max(1,r.linea-2)+i}: ${l}`).join('\n'));}
}else if(argv[0]==='--write'){
  const outIndex=argv.indexOf('--salida-dir');if(outIndex<0)throw new Error('Use --salida-dir fuera del repositorio');const outputDir=path.resolve(argv[outIndex+1]);if(outputDir.startsWith(path.resolve(ROOT,'..')+path.sep))throw new Error('La salida pesada debe quedar fuera del repositorio');fs.mkdirSync(outputDir,{recursive:true});
  fs.writeFileSync(path.join(outputDir,'triage-a1.json'),JSON.stringify(rows,null,2));fs.writeFileSync(path.join(outputDir,'grafo-importaciones.json'),JSON.stringify({roots,imports,alcanzables:[...reachable]},null,2));console.log('Triage y grafo escritos. Son pistas, no decisiones finales.');
}
module.exports={rows,imports,reachable};
