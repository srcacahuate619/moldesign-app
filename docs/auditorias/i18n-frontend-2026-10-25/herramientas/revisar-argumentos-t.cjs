// Revisión de argumentos de t(): sigue inicializadores y retornos con el checker de TypeScript.
// No resuelve parámetros arbitrarios ni genera una prueba de exhaustividad dinámica.
const path=require('node:path');
const ROOT=path.resolve(__dirname,'../../../..');
process.chdir(ROOT);
const ts=require(path.join(ROOT,'frontend/node_modules/typescript'));
const cfg=ts.readConfigFile('frontend/tsconfig.json',ts.sys.readFile),parsed=ts.parseJsonConfigFileContent(cfg.config,ts.sys,'frontend'),p=ts.createProgram(parsed.fileNames,parsed.options),checker=p.getTypeChecker(),known=new Set();
function value(n){if(ts.isStringLiteralLike(n))return n.text;if(ts.isParenthesizedExpression(n))return value(n.expression);if(ts.isBinaryExpression(n)&&n.operatorToken.kind===ts.SyntaxKind.PlusToken){const a=value(n.left),b=value(n.right);return a===undefined||b===undefined?undefined:a+b;}}
for(const sf of p.getSourceFiles().filter(f=>/context[\\/](traducciones[\\/]|LanguageContext)/.test(f.fileName))){function v(n){if(ts.isPropertyAssignment(n)&&ts.isObjectLiteralExpression(n.initializer)&&['es','en'].includes(n.name.getText(sf).replace(/['"]/g,''))){for(const q of n.initializer.properties)if(ts.isPropertyAssignment(q)){known.add(q.name.getText(sf).replace(/['"]/g,''));const val=value(q.initializer);if(val!==undefined)known.add(val);}}ts.forEachChild(n,v)}v(sf)}
const suspects=[];let calls=0;
function leaves(n,seen=new Set(),depth=0){
 if(!n||seen.has(n)||depth>16)return [];seen=new Set(seen).add(n);
 if(ts.isStringLiteralLike(n))return [{text:n.text,node:n}];
 if(ts.isTemplateExpression(n))return [{text:n.head.text+n.templateSpans.map(s=>'${value}'+s.literal.text).join(''),node:n}];
 if(ts.isParenthesizedExpression(n)||ts.isAsExpression(n)||ts.isNonNullExpression(n))return leaves(n.expression,seen,depth+1);
 if(ts.isConditionalExpression(n))return [...leaves(n.whenTrue,seen,depth+1),...leaves(n.whenFalse,seen,depth+1)];
 if(ts.isBinaryExpression(n))return [...leaves(n.left,seen,depth+1),...leaves(n.right,seen,depth+1)];
 if(ts.isCallExpression(n)){if(/^(t|interpolar)$/.test(n.expression.getText()))return [];let sym=checker.getSymbolAtLocation(n.expression);if(sym?.flags&ts.SymbolFlags.Alias)sym=checker.getAliasedSymbol(sym);const out=[];for(const d of sym?.declarations||[])if(d.body){function v(c){if(ts.isReturnStatement(c)&&c.expression)out.push(...leaves(c.expression,seen,depth+1));else if(c===d.body||!ts.isFunctionLike(c))ts.forEachChild(c,v)}v(d.body)}return out;}
 if(ts.isIdentifier(n)||ts.isPropertyAccessExpression(n)||ts.isElementAccessExpression(n)){let sym=checker.getSymbolAtLocation(ts.isPropertyAccessExpression(n)?n.name:n);if(sym?.flags&ts.SymbolFlags.Alias)sym=checker.getAliasedSymbol(sym);let out=[];for(const d of sym?.declarations||[])if(d.initializer)out.push(...leaves(d.initializer,seen,depth+1));if(ts.isElementAccessExpression(n)){const sy=checker.getSymbolAtLocation(n.expression);for(const d of sy?.declarations||[]){let init=d.initializer;while(init&&(ts.isAsExpression(init)||ts.isParenthesizedExpression(init)))init=init.expression;if(init&&ts.isObjectLiteralExpression(init))for(const q of init.properties)if(ts.isPropertyAssignment(q))out.push(...leaves(q.initializer,seen,depth+1));}}return out;}return [];
}
for(const sf of p.getSourceFiles().filter(f=>/frontend[\\/](app|components|lib|context|hooks)[\\/]/.test(f.fileName)&&!/[\\/](__tests__|traducciones)[\\/]/.test(f.fileName))){function v(n){if(ts.isCallExpression(n)&&n.expression.getText(sf)==='t'){calls++;for(const l of leaves(n.arguments[0]))if(!known.has(l.text)&&(/[áéíóúñ¿¡]|\b(?:Sin|Requiere|Listo|No se)\b/.test(l.text)))suspects.push({call:sf.fileName+':'+(sf.getLineAndCharacterOfPosition(n.getStart()).line+1),arg:n.arguments[0].getText(sf),text:l.text,source:l.node.getSourceFile().fileName+':'+(l.node.getSourceFile().getLineAndCharacterOfPosition(l.node.getStart()).line+1)})}ts.forEachChild(n,v)}v(sf)}
console.log(JSON.stringify({calls,keysAndAliases:known.size,suspects:[...new Map(suspects.map(x=>[JSON.stringify(x),x])).values()]},null,2));