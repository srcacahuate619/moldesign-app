// Consolida evidencia existente; sólo consulta Git, sin ejecutar ciencia, CI ni descargas.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const proof = __dirname;
const root = path.resolve(proof, '../../..');
const read = name => fs.readFileSync(path.join(proof,name),'utf8').replace(/^\uFEFF/,'');
const json = name => JSON.parse(read(name));
const write = (name,value) => fs.writeFileSync(path.join(proof,name),value+'\n');
const git = args => execFileSync('git',['-c','core.fsmonitor=false',...args],{cwd:root,encoding:'utf8'}).trim();
const code = git(['rev-parse','HEAD']);
const checked = '44c3a97e715e7dfd4a6a2dacd9c461bae06120ac';
if(code!==checked)throw Error('Este informe identifica el código final 44c3a97e; no se debe atribuir a otro árbol.');

let qa=read('qa.md');
qa=qa.replace(/Código final: `[^`]+`/,`Código final: \`${code}\``)
 .replace('[Manifiesto final](capsula-manifiesto-final.json), [arranque final](capsula-cierre-repetida.log)', '[Manifiestos por export](capsula-manifiesto-cierre.json), [export de modelos](capsula-manifiesto-modelos.json), [arranque de modelos](capsula-modelos-final.log)')
 .replace(/El export final tiene huella `[^`]+`\./,'Cada captura registra el commit y la huella de fuentes del export servido. La matriz combina comprobaciones sobre 66c682ae, 873d2307, 93b004cf y 33be61be; la regresión de contraste de anti-dianas se repite sobre 44c3a97e. No se atribuyen capturas anteriores al commit final.')
 .replace('pruebas de caducidad real e invalidación','pruebas de caducidad con reloj controlado e invalidación, [repetición real de 332.066 ms](ttl-catalogo-real.json)')
 .replace('Repetición con cinco minutos reales documentada al terminar la matriz.','En la misma página montada, sin modificar Date.now, a los 332.066 ms sale otra petición GET /targets/ y vuelven el aviso de 1UZJ y CAL-8HFI-01.')
 .replace('[caso repetido](dossier-idioma-corregido.json).','[caso repetido](dossier-idioma-corregido.json), [lote repetido](lote-idioma-corregido.json).');
qa=qa.replace('[arranque de modelos](capsula-modelos-final.log)', '[arranque de modelos](capsula-modelos-final.log), [manifiesto sobre 44c3a97e](capsula-manifiesto-contraste.json), [arranque sobre 44c3a97e](capsula-contraste-final.log)');
qa=qa.replace('Matriz lanzador anterior en el historial de QA y repetición sobre 33be61be', 'Causa identificada en el catálogo recibido de la API y el diff; no se conserva una captura anterior específica. Matriz lanzador repetida sobre 33be61be');
const newRows=[
'| F10 · bloquea 1.0.2 | Tema claro → Catálogo 1UZJ y Parámetros. | Título y campos legibles. Antes título/fondo tenían contraste 1,004:1 y campos 1,056:1 por combinar fondo oscuro y reglas de texto claro. | [Catálogo antes](capturas/defecto-contraste-catalogo-1uzj-en-light-1024.png), [Parámetros antes](capturas/defecto-contraste-parametros-en-light-1024.png), [medición antes](contraste-parametros-antes-en-light-1024.json), archivos contraste-*-despues-* y matriz final. | Arreglado 9628aa1c; 67 pruebas existentes y mediciones del export en las ocho combinaciones. |',
'| F11 · debería entrar | Abrir MolChat a 1024 o 1440: el panel tiene ancho fijo. | Razonamiento y Cerrar dentro del panel. Antes Cerrar excedía la ventana a x=1037 en 1024. | [Antes](capturas/defecto-molchat-fuera-1024.png), ocho archivos molchat-controles-*.json y matriz molchat. | Arreglado 873d2307; 7 pruebas existentes, límites reales de controles y cierre por su botón. |',
'| F12 · debería entrar | Inglés → Detalles del caso. | Las siete preguntas y ayudas en inglés; seguían en castellano. El texto escrito por el investigador se conserva. | Matriz detalles, incluida [repetición EN](capturas/detalles-en-light-1024.png); prueba CaseContextIdiomas. | Arreglado b2b58703; 8 pruebas relacionadas. |',
'| F13 · bloquea 1.0.2 | Tema claro → resumen, Detalles y ayudas de Parámetros. | Advertencias científicas legibles; antes texto pálido sobre superficie clara. | [Antes](capturas/defecto-avisos-y-barra-en-light-1024.png), matriz resultado/detalles posterior y mediciones de Parámetros. | Arreglado e87223e5; 19 pruebas existentes, se conservan motivos y gravedad. |',
'| F14 · bloquea 1.0.2 | Caso abierto a 1024 → barra de Parámetros/anteriores/Ejecutar. | Todas las acciones accesibles dentro de la ventana; Ejecutar quedaba cortado. | [Antes](capturas/defecto-avisos-y-barra-en-light-1024.png), ocho archivos acciones-evaluacion-*.json, matriz resultado. | Arreglado c79e4370; 9 pruebas existentes y medidas de los botones reales. |',
'| F15 · bloquea 1.0.2 | Lotes con corrida restaurada → elegir cohorte → Ver evidencia antes de terminar la apertura. | Esperar la cohorte elegida y conservar su identidad. Antes pedía la corrida anterior y la respuesta podía desaparecer. Una recuperación tardía también podía sustituir la elección explícita. | Dos pruebas con respuestas retenidas en cohortes.test.tsx; repetición real lote-fila sobre 33be61be con task_id 4fdb58ad. El fallo inicial ocurrió al repetir EN/claro/1440; no se fabricó captura anterior. | Arreglado 93b004cf; 46 pruebas, serialización y testigo de elección. |',
'| F16 · debería entrar | Inglés → Gestionar descargas. | Nombre de pesos de ESMFold y descripciones de modelos en inglés; permanecían en castellano. | Matriz lanzador anterior en el historial de QA y repetición sobre 33be61be; DownloadCardIdiomas.test.tsx. | Arreglado 33be61be; dos pruebas de idioma, ID de descarga y manifiesto intacto; 21 relacionadas y 15 de guardianes. |',
'| F17 · bloquea 1.0.2 | Tema claro → Parámetros → final del selector de anti-dianas. | Aviso sobre pose cristalográfica y reservas legibles; seguían con el tono pálido del tema oscuro. | [Antes](capturas/defecto-antidianas-contraste-en-light-1024.png), matriz parametros-final y contraste de la regresión. | Arreglado 44c3a97e; 26 pruebas existentes de selector y guardianes, regresión sobre export en las ocho combinaciones. |'
];
qa=qa.replace(/^\| F09 .*$/m,'| F09 · debería entrar | Informe/PDF incrustado a 1024, también Lotes. | Leer la columna Estado sin recorte. Se solicita view=FitH, pero el visor nativo de Edge automatizado conserva al 100 % algunas aperturas del caso; el visor del lote queda gris en las ocho capturas finales. | [Antes](capturas/defecto-dossier-ancho-1024.png), [sondeo con frame nuevo](capturas/sondeo-pdf-frame-nuevo.png), matriz dossier/lote-dossier y PDF del caso descargables renderizados completos. Los sondeos modifican sólo el DOM de diagnóstico, no la fuente ni los datos. | Parcial 7ac99021/66c682ae: parámetros del iframe y pruebas correctos; ajuste y render uniformes del visor nativo NO confirmados. Pendiente comprobar WebView2 en smoke de Claude. No se atribuye el recorte al PDF generado ni se declara cerrado. |');
if(!qa.includes('| F10 '))qa=qa.replace('| B02 ·',newRows.join('\n')+'\n| B02 ·');
// Mantener el orden por gravedad, sin alterar el contenido de cada evidencia.
const lines=qa.split('\n'), first=lines.findIndex(l=>/^\| [BF]\d\d /.test(l));
const rows=lines.filter(l=>/^\| [BF]\d\d /.test(l));
const rank=r=>r.includes('bloquea 1.0.2')?0:r.includes('debería entrar')?1:2;
rows.sort((a,b)=>rank(a)-rank(b));
const without=lines.filter(l=>!/^\| [BF]\d\d /.test(l)); without.splice(first,0,...rows); qa=without.join('\n');

const results=[
['PASS','Inicio y acceso a Ciencia; ocho combinaciones.'],
['PASS con límites','Navegación y modelos traducidos tras F16; motivos recibidos de la API siguen con B02.'],
['PASS parcial','Corregidos F10/F13/F14/F17. No se afirma una auditoría WCAG completa de todo control.'],
['PASS parcial','Identidad local y estadísticas de los tres cálculos propios; aislamiento entre cuentas cubierto en CI, no con dos investigadores reales.'],
['PASS parcial','Acerca de en ocho combinaciones; panel y créditos visibles. No se abrieron todas las ayudas fisiológicas.'],
['PASS','SMILES de la corrida legible y editable en los dos temas.'],
['PASS','Preflight y Vina reales mediante Ejecutar; sin botón separado.'],
['NO VERIFICADO en vivo','Sondeo incompleto en un segundo caso en borrador: se escribió un SMILES malformado, pero no se completó la selección de receptor ni el envío. No se afirma probado el rechazo de evaluación; el rechazo por menos de cinco átomos pesados en importación es otro control.'],
['PASS','Selector único Evaluación/Informe en el caso.'],
['PASS con B02','Resumen, protocolo 8/9/42 y pesos reales; persisten motivos castellanos enviados por API.'],
['PASS','Pesos de Vina 1 y modelos exploratorios 0 en la corrida, señal CL-GNN experimental.'],
['PARCIAL','Vina ejecutado; ESMFold visible, no ejecutado. API externa sin configurar; ningún motor adicional se habilita.'],
['PASS visual','Parámetros, muestreo y etiquetas Experimental; no se ejecutó una evaluación ADMET.'],
['PARCIAL','Estimación serial visible y semilla/preparación persistidas; no es un benchmark de tiempo.'],
['PASS visual','Todas/por defecto/Ninguna visibles; corrida real ejecutada expresamente sin selectividad.'],
['PARCIAL','Secciones, familias y búsqueda; no hay anti-dianas propias ni corrida contra ellas.'],
['NO VERIFICADO en vivo','No se disparó Guardar selectividad sin evaluación.'],
['NO VERIFICADO','UI MolChat en ocho combinaciones; llama.cpp no detectado, sin descargar LLM ni probar las ocho estructuras con el modelo.'],
['PASS','Verificados vacío, Tus receptores vacío y Demostración 381; Catálogo y Molcy.'],
['PASS','Búsqueda 8HFI/1UZJ conserva secciones y familias.'],
['PASS parcial','Aviso real de 1UZJ inspeccionado; no se recorrieron individualmente los otros quince avisos.'],
['PASS','CAL-8HFI-01, NO_GO, cifras/condiciones y ninguna promoción.'],
['CONTRATO','Registro real vacío; sello sólo con fixtures sintéticos de la suite.'],
['PASS parcial','Organismo, preparación y disponibilidad de 8HFI/1UZJ; no todos los receptores.'],
['FUERA DE ALCANCE','Subida reservada a otra sesión; no modificada ni declarada cerrada.'],
['PASS con B03','Tres corridas y sólo la guardada marcada Moldex; serialización de fecha sin zona pendiente.'],
['PARCIAL','Caso/corrida recuperados tras recargas y reinicio; no todas las variantes de recuperación histórica.'],
['PASS','Demostración, atribución y protocolo de la corrida exacta.'],
['PARCIAL','Una corrida guardada real; no dos evaluaciones del mismo ligando guardadas.'],
['PARCIAL','Ficha, pose, detalle y PDF; no comparación entre dos fichas reales.'],
['PASS','0,76 experimental, sin peso ni porcentaje de probabilidad.'],
['PASS visual','Barras y proximidad polar visibles en ocho combinaciones; no medición exhaustiva de cada modo de visor.'],
['PARCIAL','Ubicación y límites del registro visibles; no se emite certificación Solana.'],
['CONTRATO','Detalle accesible observado en Demostración; Verificados vacío, igualdad/diferencia/ausencia sólo en fixtures.'],
['PARCIAL','QuickVina 2 no disponible para una cohorte nueva; no hay una cohorte antigua real de ese motor.'],
['PARCIAL','CSV válido de dos controles; población de métricas vacía y abstención. Sin duplicados ni caso real del umbral EF.'],
['PASS parcial','2/2 Vina, cadena A y semilla 42; no se indujeron fallos o cancelación del motor.'],
['PASS','Fila real 4fdb58ad, sección y evidencia de la corrida; recuperación F02/F15 repetida.'],
['PASS','Preparación conserva task_id y archivos de la corrida elegida.'],
['PASS','REVIEW, nueve reservas y cero imprescindibles sin resolver; ninguna promesa FEP.'],
['PARCIAL','Aguas retiradas y distancias declaradas; esta estructura no demuestra los casos positivos de metal/cofactor.'],
['NO VERIFICADO positivo','Sin cloruro retenido en esta corrida; no se produjo un caso positivo.'],
['PASS parcial','Hueco físico LEU191→TYR202 con distancia; no caso positivo de cadena lateral truncada.'],
['PASS','Amina con CF3 en beta, especie protonada y motivo de REVIEW.'],
['PARCIAL','Estado enumerado de esta molécula; no corrida real multestado o excediendo 32.'],
['PASS','Demostración REVIEW no bloqueante; 8HFI explícito y consistente.'],
['CONTRATO','Verificados vacío; matriz de sello exacto cubierta con fixtures.'],
['PASS','PDF/ZIP reales con estructura, especie, procedencia y límites; no señales ficticias.'],
['DEFECTO B01/F09 parcial','Portada muestra sección en ES/EN; documentos mezclan frases y ajuste nativo no uniforme.'],
['NO VERIFICADO en vivo','No se emite certificado devnet; pruebas del visor por idioma separadas.'],
['PASS','Selector MolDex/receptor con tres secciones e intento, misma corrida guardada.'],
['PASS','Demostración, fuente y disponibilidad declaradas; no render.'],
['PARCIAL','Controles de escenas según evidencia; no se verifica animación de traza/ensamble.'],
['PASS parcial','Blender 5.2.2 del host detectado; falta addon Molecular Nodes. No instalación.'],
['PARCIAL','Formato/estimación visibles; no contraste con un render producido.'],
['NO VERIFICADO render','Sin jobs reales: reproducción, descarga, cancelación y limpieza de renders pendientes.'],
['NO VERIFICADO nativo','Selector de carpeta no emulado en la cápsula.'],
['NO VERIFICADO render','Rótulos, pausas y vuelta final pendientes por falta de addon.'],
['NO VERIFICADO render','Reutilización de fotogramas/fundidos no medida.'],
['PARCIAL','Modos y límites visibles; no foto CPU/GPU ni vídeo GPU real.'],
['NO VERIFICADO render','No se comprueban marca de foto ni cierre de vídeo sin archivos producidos.'],
['PASS parcial','Registro real: 168 sellados y papers accesibles; no se abrieron los siete papers incorporados.'],
['PASS','CAL-8HFI-01 como refutación, paper con n=57 y condiciones 8/9/42.']
];
if(results.length!==63)throw Error('Inventario incompleto');
qa=qa.split('\n## Resultado por fila del inventario')[0].trimEnd();
qa+='\n\n## Resultado por fila del inventario\n\nPASS describe el caso y alcance indicado; PARCIAL y NO VERIFICADO no se convierten en aprobaciones mediante pruebas unitarias. Las treinta superficies se revisan en ES/EN × claro/oscuro × 1024×768/1440×900; esto no ejecuta todas las ramas de cada función. El [registro de revisión visual](revision-visual.json) identifica las capturas realmente vistas.\n\n| ID | Resultado | Evidencia y límite |\n|---|---|---|\n';
qa+=results.map((r,i)=>`| I${String(i+1).padStart(2,'0')} | ${r[0]} | ${r[1]} |`).join('\n');
write('qa.md',qa);
write('auditoria-npm.md',read('auditoria-npm.md').replace('hasta 8c4e9734',`hasta ${checked.slice(0,8)}`).trimEnd());

if(!process.argv.includes('--entrega'))process.exit(0);
const ci=json('cierre-final-ci-resultados.json'), wt=json('worktree-cierre-resultados.json'), cleanup=json('limpieza-capsula.json');
if(ci.length!==8||wt.length!==3||[...ci,...wt].some(r=>r.salida!==0||r.commit!==checked))throw Error('Falta la verificación del código final');
const commits=git(['log','--reverse','--format=%H%x09%s','4126c839..HEAD']).split('\n').map(line=>{
  const [hash,subject]=line.split('\t');
  const files=git(['diff-tree','--no-commit-id','--name-only','-r',hash]).split('\n');
  return {hash,subject,files};
});
write('commits.json',JSON.stringify(commits,null,2));
const prefix='docs/verificacion/cierre-1-0-2/';
const commands=(title,rows)=>`## ${title}\n\nTodos los pasos de esta tabla corrieron sobre \`${checked}\`.\n\n| Comando | Salida | Segundos | Salida completa |\n|---|---:|---:|---|\n`+rows.map(r=>`| ${r.comando} | ${r.salida} | ${r.segundos} | [log](${prefix+r.registro}) |`).join('\n');
const defectLines=qa.split('\n').filter(l=>/^\| [BF]\d\d /.test(l)).map(l=>l.replace(/\]\((?!https?:)([^)]+)\)/g,`](${prefix}$1)`));
let entrega=`# Entrega de cierre frontend de 1.0.2\n\nRama \`sol/cierre-qa\`, base \`4126c839\`, código verificado \`${checked}\`. El commit final de documentación añade esta entrega y evidencia; no cambia ese código. No declara GO de release: **B01 bloquea 1.0.2**, por frases mezcladas del backend en los PDF. El ajuste nativo del visor PDF permanece parcialmente verificado (F09).\n\nEl [inventario de 63 cambios visibles](${prefix}inventario.md) se preparó antes de la QA. [QA real y límites por cada fila](${prefix}qa.md), [triaje npm](${prefix}auditoria-npm.md) y [revisión visual](${prefix}revision-visual.json). Se ejecutó Vina real individual y un lote de dos ligandos con datos propios, se guardó la corrida en MolDex y se revisaron treinta superficies en las ocho combinaciones. La repetición de caché montada pasó con 332.066 ms reales; los E2E con fixtures se informan separados.\n\n## Commits y archivos\n\n[Registro completo con hashes y rutas](${prefix}commits.json). Cada causa tiene su fila en [cambios de 1.0.2](docs/versions/1.0.2_cambios.md).\n\n| Commit | Cambio | Archivos |\n|---|---|---|\n`;
entrega+=commits.map(c=>`| \`${c.hash.slice(0,8)}\` | ${c.subject} | ${c.files.map(f=>`[${f}](${f})`).join('; ')} |`).join('\n');
entrega+='\n\n## Defectos de QA, ordenados por gravedad\n\n| ID / gravedad | Dónde y reproducción | Esperado y observado | Evidencia | Estado / propietario |\n|---|---|---|---|---|\n'+defectLines.join('\n');
entrega+='\n\n'+commands('Verificación del worktree',wt)+'\n\n1814 pruebas en 194 archivos, TypeScript limpio. Lint: cero errores, 39 avisos; no se ocultaron ni se relajó el umbral.\n\n'+commands('Ocho pasos del clon limpio',ci);
entrega+='\n\nClon `D:\\moldesign-ci\\sol-1-0-2`, checkout detached inmutable del commit de cada paso, core.autocrlf=true, Node 24.20.0 / npm 11.19.0 / Next 16.3.8. Suite 1814/194, E2E 13, UX 12; build:desktop produce el export estático. La auditoría de producción tiene salida cero al umbral critical: conserva 18 altas y 11 moderadas, cero críticas. Ningún aviso observado en código emitido tiene parche dentro del rango de sus padres; no se cambia package-lock, ni se usan force/overrides. Los módulos y hashes del análisis instrumentado pertenecen a 645bc1f2 y están identificados como tales.\n\n## Fallos intermedios y repetición\n\n- `final-v7-ci` sobre 9628aa1c falló en la prueba Molcy de liberación del preview. 8c4e9734 espera URL exacta y efecto de revocación; conserva las aserciones y tiempos.\n- `worktree-v9` sobre 873d2307 falló en recuperación del workspace por usar el callback de la sesión anterior aún montada. ba2f8f9c desmonta antes del reinicio simulado; conserva las aserciones y tiempos.\n- `final-v2-ci` se detuvo en npm ci porque la junction del worktree retenía la DLL SWC del clon. Se pasó al node_modules del árbol principal, alternativa expresamente autorizada. Los logs de fallos y las series posteriores se conservan con su commit.\n- Un build de cápsula coincidió con la mutación temporal del guardián durante la suite del mismo worktree; se repitió después de finalizar la suite. CI y cápsula se ejecutaron después sobre árboles distintos.\n\n[Resultados intermedios 93b004cf]('+prefix+'final-cierre-ci-resultados.json), [33be61be]('+prefix+'cierre-entrega-ci-resultados.json), resultados finales y logs permiten distinguir cada repetición. Ningún fallo se cuenta como aprobado por una repetición aislada.\n\n## Lo que no pudo verificarse y trabajo de integración\n\nPDF backend: B01/B02 y fecha sin zona B03; motivo de abstención de métricas B04 y línea huérfana B05 quedan documentados sin tocar backend. F09 solicita FitH y tiene pruebas del iframe, pero el visor nativo de Edge conserva escala de algunas aperturas: pendiente WebView2. Las nueve páginas de cada PDF descargado se renderizaron e inspeccionaron; no hay datos cortados en el archivo.\n\nMolcy detecta Blender del host 5.2.2 y carece de Molecular Nodes; renderer.disponible=false. No se descarga addon ni se producen fotos/vídeos: marca, cierre, animación, cancelación, recuperación y rendimiento de render NO verificados. MolChat no tiene llama.cpp operativo; no se ejecutó el reconocimiento de ocho moléculas. No se emite transacción Solana, no se descarga ni ejecuta ESMFold, ni se modifica CustomReceptorModal. Verificados permanece vacío; el ajuste de BatchRowResult usa fixtures declaradamente sintéticos para antes/después, igualdad, diferencia, ausencia, fallo y cambio de fila. Los motivos del fallo quedan en title y aria-label, sin afirmar un sello no comprobado.\n\nClaude conserva SBOM, versión 1.0.2, integración, smoke:prod, empaquetado y build del instalador. La QA usa runtime embebido con backend del worktree y export con CSP de producción; no equivale a ejecutar el runtime staged, Rust o el instalador. No se ejecutaron tauri:build, stage:desktop, smoke:prod ni cargo; no se cambió versión, no hubo push/fusión/rebase. El smoke requerido por AGENTS para estilos queda pendiente de Claude porque el encargo lo prohíbe expresamente aquí.\n\n## Cápsula apagada y diferencias con el encargo\n\nSe ejecutó `node scripts/qa_sandbox/sandbox-up.mjs --agente 3 --down --limpiar`. [Log]('+prefix+'capsula-limpieza.log), [estado y contenido restante]('+prefix+'limpieza-capsula.json).\n\n';
entrega+=`Quedan en \`D:\\moldesign-build\\.worktrees\\.sandbox\\agente3\` los archivos propios de QA: ${cleanup.directorios.join(', ')}; ${cleanup.archivos} archivos y ${cleanup.bytes} bytes regulares. Se retiran las junctions registradas y la junction propia de node_modules; no se borran sus destinos compartidos ni datos ajenos. Los puertos 13013/18013 quedan cerrados; el servicio ajeno 3123 se conserva. El clon limpio y sus artefactos de build permanecen para revisión.\n\nSe hicieron varias repeticiones de CI porque la QA encontró más causas después de las primeras suites. Cada tabla final identifica un único commit. El PDF inglés falla el criterio solicitado y la falta de Molecular Nodes impide completar las filas de render: estas diferencias están declaradas por ID, sin convertir comprobaciones de contrato o capturas en evidencia de ejecuciones no hechas.\n`;
entrega=entrega.replace('## Fallos intermedios y repetición', `El export final pasó también los guardianes de [dirección de API](${prefix}export-final-api-url.log) y [recursos remotos](${prefix}export-final-no-remote.log). [Paquetes originales y hashes](${prefix}paquetes-originales.json) conserva tres bundles internos de Vina y el ZIP del dossier descargado mediante la interfaz; se distinguen sus funciones.\n\n## Fallos intermedios y repetición`);
entrega=entrega.replace('el visor nativo de Edge conserva escala de algunas aperturas: pendiente WebView2. Las nueve páginas de cada PDF descargado se renderizaron e inspeccionaron; no hay datos cortados en el archivo.', 'el visor nativo de Edge conserva escala de algunas aperturas del caso y el visor del lote queda gris en las ocho capturas: pendiente WebView2. Las nueve páginas de cada PDF del caso descargado se renderizaron e inspeccionaron; no hay datos cortados en el archivo. No se afirma inspeccionado un PDF descargado del lote.');
fs.writeFileSync(path.join(root,'ENTREGA_SOL_CIERRE.md'),entrega);
