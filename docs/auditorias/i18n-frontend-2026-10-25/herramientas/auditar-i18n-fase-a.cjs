/* Herramienta de inventario de fase A: no migra ni modifica fuentes. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const args = process.argv.slice(2);
const value = (flag, fallback) => args.includes(flag) ? args[args.indexOf(flag) + 1] : fallback;
const ROOT = path.resolve(value('--root', path.resolve(__dirname, '../../../../frontend')));
const requireFront = createRequire(path.join(ROOT, 'package.json'));
const ts = requireFront('typescript');
const original = path.join(ROOT, 'scripts/finish-i18n-frontend.cjs');
const moduleCopy = { exports: {} };
vm.runInNewContext(fs.readFileSync(original, 'utf8') + '\nmodule.exports.audit = {column, valueOf, visibleLiteral, inTranslator, seCompara};', {
  require: requireFront, module: moduleCopy, exports: moduleCopy.exports,
  __dirname: path.dirname(original), process: { argv: [], exit: code => {throw Error('exit '+code);} }, console,
}, { filename: original });
const legacy = moduleCopy.exports;
const { column, valueOf, visibleLiteral, inTranslator, seCompara } = legacy.audit;
const ES = /[\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00fc\u00bf\u00a1\u00c1\u00c9\u00cd\u00d3\u00da\u00d1]|\b(el|la|los|las|una|del|que|para|con|por|sin|se|son|como|pero|este|esta|todo|hay|desde|cuando|puede|tiene|sobre|entre|cada|otro|otra|datos|guardad[oa]s?|pendientes?|completad[oa]s?|cargando|preparando|cancelad[oa]|ligando|buscando|coordenadas|listo|baja|alta|ninguno|ninguna|leer|escribir|fallo|fallido|no evaluado)\b/i;
const EXENTOS = new Set(['Español', 'es', 'es-MX', 'es-ES', 'Receptor', 'receptor', 'experimental', 'Experimental']);
const VOCABULARIO_ES = new Set();
function spanish(text) {
  const tokens=text.toLowerCase().match(/[a-záéíóúñü]{4,}/g)||[];
  return !EXENTOS.has(text.trim()) && !/^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/.test(text.trim()) && (ES.test(text)||tokens.some(word=>VOCABULARIO_ES.has(word)));
}
const pairs = new Map();
const keys = new Map();
const todos = [];
function dictionary(file) {
  const es = column(file, 'es'), en = column(file, 'en');
  for(const [key,text] of es)if(en.has(key))todos.push({es:text,en:en.get(key),key,archivo:path.relative(ROOT,file).replaceAll('\\','/')});
  for(const [key,text] of en)keys.set(key,text);
  for (const [key, text] of es) if (en.has(key) && en.get(key) !== text) {
    const list = pairs.get(text) || [];
    list.push({ key, en: en.get(key), archivo: path.relative(ROOT,file).replaceAll('\\','/') });
    pairs.set(text, list);
  }
}
function walk(dir, extensions) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e => {
    if (['__tests__','traducciones','node_modules','e2e','out','.next','src-tauri'].includes(e.name)) return [];
    const file = path.join(dir,e.name);
    return e.isDirectory() ? walk(file,extensions) : extensions.test(file) && !/\.(test|spec)\./.test(file) ? [file] : [];
  });
}
dictionary(path.join(ROOT,'context/LanguageContext.tsx'));
for (const name of fs.readdirSync(path.join(ROOT,'context/traducciones'))) {
  if (name.endsWith('.ts') && name !== 'index.ts') dictionary(path.join(ROOT,'context/traducciones',name));
}
for(const [key,text] of column(path.join(ROOT,'context/LanguageContext.tsx'),'en'))keys.set(key,text);
const englishWords=new Set([...pairs.values()].flatMap(rows=>rows.flatMap(row=>row.en.toLowerCase().match(/[a-záéíóúñü]{4,}/g)||[])));
for(const text of pairs.keys())for(const word of text.toLowerCase().match(/[a-záéíóúñü]{4,}/g)||[])if(!englishWords.has(word))VOCABULARIO_ES.add(word);
function collect(source, file) {
  const sf = ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const rows = [];
  function inspect(node,text,kind) {
    text = text.trim();
    if (!spanish(text) && !pairs.has(text)) return;
    let exclusion = null;
    if (inTranslator(node)) exclusion = 'argumento de t(): revisar la traducción en el diccionario';
    if (seCompara(node)) exclusion = 'comparación o case: contrato/lógica, no salida por sí misma';
    if (node.parent && ts.isLiteralTypeNode(node.parent)) exclusion = 'literal de tipo';
    if (node.parent && ((ts.isPropertyAssignment(node.parent) && node.parent.name === node) || ts.isImportDeclaration(node.parent) || ts.isExportDeclaration(node.parent))) exclusion = 'identificador o importación';
    let cursor=node.parent, scope=null, call=null;
    while(cursor){
      if(ts.isPropertyAssignment(cursor) && ['es','en'].includes(cursor.name.getText(sf).replaceAll('"','').replaceAll("'",'')) && file.endsWith('LanguageContext.tsx')) { exclusion='diccionario histórico';break; }
      if(ts.isCallExpression(cursor) || ts.isNewExpression(cursor)) {
        const callee=cursor.expression.getText(sf);
        call ||= callee;
        if(/^(console\.|logger\.)/.test(callee)) {exclusion='sólo consola';break;}
      }
      if(!scope && ts.isFunctionLike(cursor)) scope=cursor.name?.getText(sf) || cursor.parent?.name?.getText(sf) || '(anónima)';
      cursor=cursor.parent;
    }
    const technical = legacy.isTechnicalOnly(text) || /^\[[^\]]+\]/.test(text);
    if(technical && !exclusion) exclusion='literal técnico: verificar manualmente';
    const line=sf.getLineAndCharacterOfPosition(node.getStart(sf)).line+1;
    const context=[];let tArgument=null;cursor=node.parent;
    while(cursor){
      if(tArgument===null&&ts.isCallExpression(cursor)&&cursor.expression.getText(sf)==='t')tArgument=cursor.arguments.findIndex(a=>node.pos>=a.pos&&node.end<=a.end);
      if(ts.isPropertyAssignment(cursor)&&['es','en'].includes(cursor.name.getText(sf).replaceAll('"','').replaceAll("'",'')))context.push({tipo:'columna',idioma:cursor.name.getText(sf),linea:sf.getLineAndCharacterOfPosition(cursor.getStart(sf)).line+1});
      if(ts.isConditionalExpression(cursor))context.push({tipo:'condicion',condicion:cursor.condition.getText(sf),rama:node.pos>=cursor.whenTrue.pos&&node.end<=cursor.whenTrue.end?'verdadera':'falsa',linea:sf.getLineAndCharacterOfPosition(cursor.getStart(sf)).line+1});
      cursor=cursor.parent;
    }
    rows.push({ archivo:path.relative(ROOT,file).replaceAll('\\','/'),linea:line,texto:text,codigo:node.getText(sf),tipo:kind,funcion:scope,llamada:call,contexto:context,argumento_t:tArgument,clave_existente:keys.has(text)?keys.get(text):null,visible_segun_guardian_anterior:visibleLiteral(node,kind==='jsx'?'jsx':'string'),dict:pairs.get(text)||[],clasificacion:exclusion?'excluir-provisional':'revisar',motivo:exclusion });
  }
  function visit(node) {
    if(ts.isBinaryExpression(node)&&node.operatorToken.kind===ts.SyntaxKind.PlusToken){const full=valueOf(node);if(full!==undefined){inspect(node,full,'concatenacion-constante');return;}}
    if (ts.isJsxText(node)) inspect(node,node.text,'jsx');
    else if(ts.isTemplateExpression(node)) {
      inspect(node,node.head.text+node.templateSpans.map(s=>'${'+s.expression.getText(sf)+'}'+s.literal.text).join(''),'template');
      for(const span of node.templateSpans) visit(span.expression);
      return;
    } else if(ts.isStringLiteral(node)||ts.isNoSubstitutionTemplateLiteral(node)) inspect(node,node.text,'string');
    ts.forEachChild(node,visit);
  }
  visit(sf);return rows;
}
function selftest() {
  const positive=['Sin datos','Hay trabajo en curso en este caso.','Coordenadas','No evaluado','Añadir ligando','Capa Distancia O-N (4-8 Å)','PESO MOL. (Da)'];
  const negative=['No results yet','Open Babel','Español','VALIDADOR_EXCEDIO_EL_PLAZO','Your receptor','Van der Waals'];
  positive.forEach(x=>assert.equal(spanish(x),true,x));negative.forEach(x=>assert.equal(spanish(x),false,x));
  const sample='// Sin datos en comentario\nexport function label(){return "Sin datos";} export function error(){throw new Error("No se pudo guardar");} console.warn("Fallo de consola");';
  const rows=collect(sample,path.join(ROOT,'lib/muestra-auditoria.ts'));
  assert(rows.some(r=>r.texto==='Sin datos'&&r.clasificacion==='revisar'));
  assert(rows.some(r=>r.texto==='No se pudo guardar'&&r.clasificacion==='revisar'));
  assert(rows.some(r=>r.texto==='Fallo de consola'&&r.motivo==='sólo consola'));
  assert(!rows.some(r=>r.texto.includes('comentario')));
  const formats=collectFormats('new Intl.NumberFormat; new Intl.DateTimeFormat(undefined); value.toLocaleString(); value.toLocaleDateString(locale); text.toLocaleLowerCase();',path.join(ROOT,'lib/muestra-auditoria.ts'));
  assert.equal(formats.length,4);
  assert.equal(formats.filter(r=>r.clasificacion==='revisar').length,3);
  assert.equal(formats[3].locale,'locale');
  assert(!formats.some(r=>r.codigo.includes('toLocaleLowerCase')));
  const dom=inspectSnapshot({name:'control',text:'No results yet\nSin datos',attributes:[{tag:'BUTTON',title:'Capa Distancia O-N (4-8 Å)',ariaLabel:'No results yet',placeholder:'Añadir ligando',alt:'Español'}]},'control.json');
  assert.equal(dom.length,3);
  assert.deepEqual(dom.map(r=>r.canal),['innerText','title','placeholder']);
  console.log('Autotest fase A: 13 muestras lingüísticas + 4 comprobaciones AST + 4 de formato + 2 de DOM, OK.');
}
function collectFormats(source,file){
  const sf=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,file.endsWith('.tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
  const locales=[];
  function visit(n){
    if((ts.isCallExpression(n)&&ts.isPropertyAccessExpression(n.expression)&&/^toLocale(String|DateString|TimeString)$/.test(n.expression.name.text))||(ts.isNewExpression(n)&&/^Intl\.(NumberFormat|DateTimeFormat)$/.test(n.expression.getText(sf)))){
      const first=n.arguments?.[0]?.getText(sf)||null;
      locales.push({archivo:path.relative(ROOT,file).replaceAll('\\','/'),linea:sf.getLineAndCharacterOfPosition(n.getStart(sf)).line+1,codigo:n.getText(sf),locale:first,clasificacion:first===null||first==='undefined'||/^['"]es(?:-[A-Z]+)?['"]$/.test(first)?'revisar':'condicionado: revisar implementación'});
    }
    ts.forEachChild(n,visit);
  }
  visit(sf);return locales;
}
function staticScan() {
  const files=['app','components','hooks','lib','context'].flatMap(d=>walk(path.join(ROOT,d),/\.tsx?$/));
  const rows=files.flatMap(file=>collect(fs.readFileSync(file,'utf8'),file));
  const locales=files.flatMap(file=>collectFormats(fs.readFileSync(file,'utf8'),file));
  return {fuente:'4fc7a928 (ver HEAD por separado)',archivos:files.length,literales:rows,formatos:locales};
}
function inspectSnapshot(d,name){
  if(typeof d.text!=='string')return [];
  const items=d.text.split('\n').map(text=>({canal:'innerText',texto:text.trim()}));
  for(const a of d.attributes||[])for(const prop of ['title','ariaLabel','ariaDescription','placeholder','alt'])if(a[prop])items.push({canal:prop,texto:a[prop],elemento:a.tag,id:a.id});
  return items.filter(x=>spanish(x.texto)).map(x=>({estado:d.name,archivo:name,...x}));
}
function dynamicScan(dir){
  return fs.readdirSync(dir).filter(n=>/\.json$/.test(n)&&!['red.json','estados.json'].includes(n)).flatMap(name=>{
    const d=JSON.parse(fs.readFileSync(path.join(dir,name),'utf8'));
    return inspectSnapshot(d,name);
  });
}
if(require.main===module){
  selftest();
  if(args.includes('--autotest'))process.exit(0);
  const output=args.includes('--dom')?dynamicScan(value('--dom')):staticScan();
  const dest=value('--salida',null);
  if(dest){fs.writeFileSync(dest,JSON.stringify(output,null,2)+'\n');console.log('Escrito '+dest);}
  else console.log(JSON.stringify(output,null,2));
}
module.exports={spanish,collect,collectFormats,inspectSnapshot,staticScan,dynamicScan,selftest,pares:[...pairs],todos,claves:Object.fromEntries(keys)};
