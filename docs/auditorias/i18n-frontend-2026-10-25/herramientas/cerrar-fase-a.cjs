const {archivo: archivoExterno}=require('./archivo-fase-a.cjs');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../../../..');
const AUD=ROOT+'/docs/auditorias/i18n-frontend-2026-10-25';
const tool=require('./auditar-i18n-fase-a.cjs');
const review=require('./revisar-a1.cjs');
const rows=review.rows;
const entries=[];
const evidence=name=>JSON.parse(fs.readFileSync(archivoExterno('evidencia/'+name+'.json'),'utf8'));
const states=JSON.parse(fs.readFileSync(AUD+'/evidencia/estados.json','utf8'));
const snapshots=states.map(s=>evidence(s.name));
const conditions={};
function baseSteps(surface){
 const prefix='Desde una cápsula nueva: abrir http://localhost:13011; Opciones → English; recargar y comprobar html[lang=en]. ';
 if(surface.includes('Previous evaluations'))return prefix+'Evaluación → New case → I18N QA → seleccionar 8HFI en Demo → SMILES CC(=O)Oc1ccccc1C(=O)O → Run evaluation (ex=8, poses=9, seed=42); cancelar una corrida y completar otra. Abrir Previous evaluations. '+surface+'.';
 if(surface.startsWith('Casos')&&surface.includes('Dossier'))return prefix+'Crear I18N QA en Evaluación con 8HFI y CC(=O)Oc1ccccc1C(=O)O; ejecutar Vina (ex=8, poses=9, seed=42), esperar el resultado y abrir Dossier. '+surface+'.';
 if(surface.includes('Choose receptor'))return prefix+'Evaluación → New case → I18N QA → Create a case → Choose a receptor → Demo. Buscar 8HFI para listo; para las otras dos ramas recorrer las insignias de revisión/sin datos del listado sin filtro (captura 15 y su volcado de atributos). Leer title de la insignia de preparación. No hace falta ejecutar.';
 if(surface.includes('Evaluation parameters'))return prefix+'Crear caso en Evaluación → Choose a receptor → Demo → 8HFI → Choose receptor. Abrir Evaluation parameters y la lista de residuos antes de ejecutar.';
 if(surface.startsWith('Casos'))return prefix+'Evaluación → New case → I18N QA → Create a case. '+surface.slice(8)+'.';
 if(surface.startsWith('MolChat'))return prefix+'Abrir el botón flotante MolChat. '+surface.slice(9)+'.';
 if(surface.startsWith('Moldex'))return prefix+'Crear I18N QA (8HFI, aspirina) e I18N Copia (6SXC, aspirina); ejecutar Vina ex=8, poses=9, seed=42; guardar ambas en Moldex. '+surface.slice(8)+'.';
 if(surface.startsWith('Evaluación'))return prefix+'Evaluación → New case → I18N QA → elegir 8HFI en Demo → SMILES CC(=O)Oc1ccccc1C(=O)O → Run evaluation (Vina, ex=8, poses=9, seed=42). '+surface.slice(12)+'.';
 return prefix+surface+'.';
}
function add(o){
 const origin=o.origen|| (o.archivo.startsWith('frontend/lib/')||o.archivo.startsWith('frontend/context/')?'frontend_lib':'frontend_tsx');
 entries.push({texto:o.texto,origen:origin,archivo:o.archivo,superficie:o.superficie,como_llegar:o.como_llegar||baseSteps(o.superficie),captura:o.captura?`capturas/${o.captura}.png`:null,visto_por:o.visto_por||(o.captura?'ambos':'estatico'),propuesta:o.propuesta||'clave nueva',estado:origin==='backend'?'backend':origin==='rust'?'rust':'pendiente',...o,origen:origin,captura:o.captura?`capturas/${o.captura}.png`:null});
}
function select(file,start,end,surface,consumer,opts={}){
 const selected=rows.filter(r=>r.archivo===file&&r.linea>=start&&r.linea<=end&&(!opts.filter||opts.filter(r)));
 const seen=new Set();
 for(const r of selected){
   if(seen.has(r.texto))continue;seen.add(r.texto);
   const en=tool.pares.find(([es])=>es===r.texto)?.[1]||[];
   add({archivo:'frontend/'+file+':'+r.linea,texto:r.texto,superficie:surface,consumidor:consumer,propuesta:en.length?'clave existente':'clave nueva',claves_candidatas:en.map(x=>x.key),plantilla:r.tipo==='template',...opts.entry});
   conditions[file+':'+r.linea+':'+r.texto]='hallazgo: '+consumer;
 }
}
const human=r=>!r.texto.includes('cursor-')&&!/^(?:[a-z][a-z0-9_-]*|\$\{[^}]+\})$/.test(r.texto)&&r.tipo!=='jsx'&&r.pista!=='literal de tipo'&&r.pista!=='sólo consola'&&!/^auto_|^[a-z]+_/.test(r.texto);

// Cada rango se cotejó con la salida del consumidor indicada; no es una lista de tildes.
select('lib/moldex.ts',303,341,'Moldex > Compare > motivos','components/MolecularComparison.tsx:187 imprime veredicto.motivos sin t()', {filter:r=>r.texto!=='sin target',entry:{captura:'89-moldex-seleccion-comparacion'}});
// Sólo tres motivos se observaron: los demás conservan evidencia estática.
for(const e of entries)if(e.archivo.match(/moldex.ts:(313|326|340)$/)){e.captura=null;e.visto_por='estatico';e.limite='La rama necesita un registro legacy sin hash/protocolo o una calibración distinta; no se fabricó ese resultado.';}
select('components/MolecularComparison.tsx',89,99,'Moldex > Compare > tabla','filaComparativa imprime el nombre de fila recibido sin traducir',{filter:r=>/PESO|ÍNDICE/.test(r.texto),entry:{captura:'89-moldex-seleccion-comparacion'}});
select('components/interfaces/pro/ProXaiTab.tsx',49,58,'Evaluación > Analysis > Explainability','ShapContributionChart label() y el diálogo llaman t() con la frase ya interpolada; el alias sólo conoce frases completas fijas',{filter:r=>r.tipo==='template',entry:{captura:'94-explicabilidad'}});
select('components/interfaces/pro/EstadoDelLigando.tsx',45,48,'Evaluación > Properties and chemical state','EstadoDelLigando.tsx:89 imprime carga.texto directamente',{filter:r=>r.tipo==='template'||['carga sin determinar','especie neutra'].includes(r.texto)});
for(const e of entries)if(e.archivo.includes('EstadoDelLigando')&&e.texto.startsWith('anión')){e.captura='capturas/39-propiedades.png';e.visto_por='ambos';e.ejemplo='anión −1';}
select('components/interfaces/pro/ProAlertsTab.tsx',85,92,'Evaluación > avisos derivados','ProAlertsTab.tsx:121 imprime aviso.mensaje; no usa el código para estos dos mensajes',{entry:{captura:'39-propiedades'}});
entries.at(-2).captura=null;entries.at(-2).visto_por='estatico';
select('components/interfaces/pro/TargetSelectorModal.tsx',55,60,'Evaluación > Choose receptor > tooltip de preparación','calibrationTooltip() se asigna a title en la fila del receptor',{entry:{captura:'15-catalogo-secciones',canal:'title'}});
select('components/interfaces/pro/TargetSelectorModal.tsx',175,187,'Evaluación > Your receptors > compartir','setShareMessage() se imprime en el modal; requiere fallo/repetición del envío',{filter:human});
select('components/interfaces/pro/ProOptionsModal.tsx',1020,1020,'Evaluación > Evaluation parameters > residuos','title del botón del hotspot',{entry:{captura:'28-parametros',canal:'title'}});
select('components/ui/Ayuda.tsx',125,125,'Evaluación > ayudas contextuales','aria-label del botón de Ayuda compone texto castellano aunque titulo ya esté en inglés',{entry:{captura:'100-controles-no-evaluados',canal:'ariaLabel'}});
select('components/cases/CaseSidebar.tsx',263,263,'Casos > lista lateral > accesibilidad','aria-label con el número de casos activos',{entry:{captura:'14-caso-creado',canal:'ariaLabel'}});
select('components/cases/CaseWorkspace.tsx',387,387,'Casos > bloqueo durante una corrida','workLockedReason se muestra al bloquear el cambio de caso',{entry:{captura:'29-preflight-progreso'}});
select('components/cases/CaseContextPanel.tsx',68,70,'Casos > Dossier > indicador de guardado','SaveIndicator imprime text directamente');
for(const e of entries)if(e.archivo.endsWith('CaseContextPanel.tsx:69')){e.captura='capturas/110-contexto-guardando.png';e.visto_por='ambos';}
select('components/cases/CaseContextPanel.tsx',57,57,'Casos > Dossier > campos opcionales','t(SEVERITY_LABEL.info) devuelve el propio texto: no hay alias de Contexto opcional',{entry:{captura:'109-contexto-caso'}});
select('components/cases/CaseContextPanel.tsx',237,238,'Casos > Dossier > resumen de preguntas','El dd compone advertencia(s)/opcional con un sufijo traducido separado',{filter:r=>r.tipo==='template'||r.texto==='ninguna',entry:{captura:'109-contexto-caso'}});
select('components/cases/CaseRunHistoryModal.tsx',73,79,'Casos > Previous evaluations > estados','STATE_LABELS se imprime en filas y opciones del filtro');
for(const e of entries)if(/CaseRunHistoryModal.tsx:(77|79)$/.test(e.archivo)){e.captura='capturas/102-historial-corridas-formato.png';e.visto_por='ambos';}
select('components/cases/CaseRunHistoryModal.tsx',95,95,'Casos > Previous evaluations > fecha inválida','formatRunMoment devuelve el texto y la fila lo imprime');
select('components/cases/CaseRunHistoryModal.tsx',114,126,'Casos > Previous evaluations > corrida que no se puede abrir','whyRunCannotOpen se imprime directamente en el detalle');
for(const e of entries)if(e.archivo.endsWith('CaseRunHistoryModal.tsx:117')){e.captura='capturas/102-historial-corridas-formato.png';e.visto_por='ambos';}
select('components/cases/CaseRunHistoryModal.tsx',181,181,'Casos > Previous evaluations > error al recuperar','El catch coloca el fallback en detail.message; se imprime sin t()');
select('components/cases/CaseDossierViewer.tsx',270,270,'Casos > Dossier > Export ZIP package > error','catch usa el fallback en el aviso de exportación');
select('components/ai/ProviderBadge.tsx',53,120,'MolChat > insignia del proveedor','ProviderBadge.tsx:142 imprime statusText sin traductor',{filter:r=>r.tipo==='template'||['Generando...','No configurado','llama.cpp no detectado','Cargando en GPU...','Cargando modelo...','Disponible'].includes(r.texto)});
for(const e of entries)if(e.texto==='llama.cpp no detectado'){e.captura='capturas/70-molchat-inicial.png';e.visto_por='ambos';}
select('components/ai/AISettingsModal.tsx',66,359,'MolChat > Settings > errores','setSettingsError → role=alert; mensajeDeError devuelve el Error.message sin traducción',{filter:r=>/^(No se |La descarga)/.test(r.texto)});
select('components/ai/AISettingsModal.tsx',896,896,'MolChat > Settings > Keep model loaded > error','setSettingsError → alerta sin t()');
select('context/motivoDeTurno.ts',32,36,'MolChat > turno HTTP fallido sin detail','AIContext.tsx:673 → turnoFallido.motivo → ChatPanel lo imprime');
select('context/AIContext.tsx',387,387,'MolChat > aviso de saldo','SET_WARNING → ChatPanel imprime state.warning');
select('context/AIContext.tsx',523,524,'MolChat > historial de conversaciones > error','SET_WARNING/SET_ERROR propagados al panel');
select('context/AIContext.tsx',597,598,'MolChat > nueva conversación > error','SET_WARNING propagado al panel');
select('context/AIContext.tsx',730,733,'MolChat > turno con backend parado','SET_TURNO_FALLIDO.motivo → ChatPanel',{filter:r=>r.tipo==='template',entry:{captura:'103-backend-detenido-molchat'}});
select('lib/reporteDeIA.ts',46,46,'MolChat > Report answer > borrador de correo','recortar añade el marcador al cuerpo de mailto; BotonDeReporte sí pasa los demás encabezados traducidos',{entry:{limite:'No se abrió ni envió correo. Requiere una respuesta de más de 1200 caracteres.'}});
select('components/ai/BloqueDeEvidencia.tsx',106,106,'MolChat > bloque de evidencia sin clase','El parser añade clase sin clasificar; BloqueDeEvidencia.tsx:172 imprime e.clase',{entry:{limite:'No hay motor local en la cápsula; no se simuló una respuesta LLM.'}});
select('components/ai/ChatMessage.tsx',51,51,'MolChat > aceptar una propuesta','handleAccept envía sí; AIContext añade el mensaje como burbuja de usuario',{entry:{limite:'Texto generado por el frontend; no se atribuye al investigador. No se alcanzó una propuesta con el motor local ausente.'}});
select('components/interfaces/pro/ProSelectivityPanel.tsx',61,85,'Evaluación > Analysis > Selectivity > detalle de una anti-diana','selectedDetail.at.targetFunction/bioDetails/mitigationSar se imprimen en 1057/1068/1080 sin t(); risk del API tiene prioridad',{filter:r=>/^(Canal de potasio|El bloqueo|Estrategias|Isoenzima|La inhibición|Receptor serotoninérgico|El agonismo)/.test(r.texto)});
select('components/interfaces/pro/ProSelectivityPanel.tsx',470,472,'Evaluación > Analysis > Selectivity > veredicto sin diana principal','claveDeVeredicto no conoce estas dos frases; el JSX devuelve verdict sin t()', {filter:human});
select('components/interfaces/pro/ProSelectivityPanel.tsx',448,448,'Evaluación > Analysis > Selectivity > safety flags','safetyFlags se persiste y el panel las imprime; el prefijo/gramática es del frontend',{filter:r=>r.tipo==='template'});
select('lib/admetEtiquetas.ts',17,28,'Evaluación > Properties > ADMET > PPB','ResultPropertiesPanel.tsx:31 muestra etiquetaPPB sin t(); también ProParametersTab/PropertiesPanel',{filter:r=>r.tipo==='string'&&!/^case$/.test(r.texto)&&!['extreme','high','medium','low'].includes(r.texto)});
select('components/interfaces/pro/ResultPropertiesPanel.tsx',104,104,'Evaluación > Properties > ADMET > procedencia','LiquidOrb imprime source sin traducción');
select('components/interfaces/pro/ProParametersTab.tsx',331,331,'Evaluación > Properties > ADMET > procedencia legacy','La fuente fija se entrega al panel de propiedad sin traductor');
select('components/interfaces/pro/Web3DViewer.tsx',222,222,'Evaluación > View Web3D > leyenda de residuos','formatResidueLabel se imprime en la leyenda y el detalle',{entry:{captura:'112-visor-web3d'}});
select('components/interfaces/pro/Web3DViewer.tsx',198,228,'Evaluación > View Web3D > tipo de residuo','El JSX 1166/1295 imprime el tipo y 1297 el nombre; desc sí pasa por t()',{filter:r=>r.tipo==='string'&&r.texto.length<30&&r.texto!==r.texto.toUpperCase()&&!r.dict.some(d=>/desc/.test(d.key)),entry:{limite:'Los tipos presentes en 8HFI se observaron; nombres y otros tipos requieren seleccionar un residuo o otro receptor.'}});
// Se revisan los campos exactos de AA_INFO abajo para no confundir descripciones con nombres.
for(let i=entries.length-1;i>=0;i--){const e=entries[i];if(e.archivo.includes('Web3DViewer')&&e.superficie.endsWith('tipo de residuo')&&e.texto.includes(' ' )&&e.texto.endsWith('.'))entries.splice(i,1);}
select('lib/preflight.ts',205,206,'Evaluación > comprobación previa > HTTP fallido','CaseEvaluationRunner.tsx:1202 muestra PreflightError.message',{entry:{limite:'El cuerpo de respuesta no se reemplazó; esta es la rama frontend para HTTP no OK.'}});
select('lib/preflight.ts',256,256,'Evaluación > Configuration > caja derivada del PDB','ConfigurationPresentation.tsx:101 y PreparationPanel.tsx:261 imprimen gridLabel persistida sin t()');
select('lib/dossier.ts',406,417,'Preparación / Casos > Dossier > HTTP fallido sin detalle','fallbackMessage → DossierError.message → mensaje(error) / CaseDossierViewer',{filter:human});
select('lib/dossier.ts',474,480,'Casos > Dossier > contexto mayor que el límite','verificarLimitesDelContexto rechaza antes de HTTP; el aviso muestra DossierError.message',{filter:r=>r.tipo==='template'});
select('lib/dossier.ts',514,514,'Preparación / Casos > Dossier > conexión fallida','sendProjection lanza DossierError que se imprime sin t()');
select('lib/dossier.ts',552,552,'Preparación > respuesta incompatible','requestPreparacion → DossierError → mensaje(error) sin t()');
select('lib/cohorts.ts',297,299,'Batch > operación HTTP sin detalle','CohortError.message → mensajeDeError del asistente; no se trata de texto del backend');
select('lib/cohorts.ts',322,341,'Batch > conexión fallida','CohortError.message → aviso de la operación / descarga',{filter:human});
select('lib/proApi.ts',131,135,'Evaluación > Analysis > error de transporte','customFetch → catch de Selectivity/SAR/ADMET muestra Error.message',{filter:r=>r.tipo==='template'||r.texto.startsWith('Comprueba')||r.texto.startsWith('operación')});
select('lib/api.ts',857,857,'Evaluación > descargar certificado > HTTP fallido','Error.message → catch de CaseEvaluationRunner.tsx:1608');
select('lib/api.ts',904,904,'Evaluación > vista previa PDF > HTTP fallido','Error.message → PDFReportViewer error; sin t()');
select('components/evaluation/CaseEvaluationRunner.tsx',108,112,'Evaluación > recuperar corrida > plazo agotado','withRecoveryDeadline compone label y segundos y el error se presenta en el runner',{filter:r=>r.tipo==='template'});
select('components/evaluation/CaseEvaluationRunner.tsx',557,557,'Evaluación > interrupción del seguimiento','setError → alerta del runner');
select('components/evaluation/CaseEvaluationRunner.tsx',905,905,'Evaluación > recuperar corrida > respuesta incompleta','throw Error → catch → setError');
select('components/evaluation/CaseEvaluationRunner.tsx',950,954,'Evaluación > recuperar corrida > sesión/motor no disponible','recoverError se muestra en el aviso con acción de recuperación',{filter:human});
select('components/evaluation/CaseEvaluationRunner.tsx',1119,1120,'Evaluación > cancelar > error','setError compone prefijo castellano y causa',{filter:r=>r.tipo==='template'});
select('components/evaluation/CaseEvaluationRunner.tsx',1608,1616,'Evaluación > descargas > error','setError concatena el prefijo castellano con Error.message',{filter:r=>r.tipo==='template'});
select('app/comunidad/page.tsx',42,42,'Comunidad > HTTP fallido','setError → alerta de la página');
select('app/comunidad/page.tsx',67,67,'Comunidad > descargar receptor > error','setError → alerta de la página');
select('lib/registro.ts',157,157,'Registro científico > índice no disponible','cargarIndice → catch de RegistroCientifico → aviso de error');
select('components/ui/ExternalLink.tsx',49,49,'Opciones / Legal > enlace externo > error','ExternalLink imprime fallo junto al enlace; las razones de openExternal sólo van a console.error');
select('components/ui/LocalDocViewer.tsx',75,76,'Opciones > Legal > Licenses > documento local ausente','catch del fetch del asset → p role=alert',{filter:r=>r.tipo==='template'});
select('components/ui/OptionsMenu.tsx',165,165,'Opciones > Export library as JSON/CSV','anchor.download contiene bioteca; el alcance incluye nombres propuestos de descarga');
select('components/ui/OptionsMenu.tsx',169,174,'Opciones > Export / Clear legacy local data > diálogo','window.alert y window.confirm son mensajes frontend',{filter:human});
select('lib/molcy.ts',278,280,'Molcy > Photo studio > abrir una foto > error','PhotoStudio.tsx:145 captura y muestra Error.message; miniaturas/vistas sí absorben estos errores sin mostrarlos');
select('lib/molcy.ts',435,435,'Molcy > Renderer settings > contrato incompatible','RendererSettings.tsx:30/46 muestra Error.message');
select('lib/webgl.ts',111,149,'Moldex > Structure 3D > equipo sin WebGL','MoleculeViewer3D.tsx:359 imprime estadoWebGL.motivo',{filter:r=>r.texto.includes('equipo no expone')||r.tipo==='template'});
select('context/DownloadProvider.tsx',51,57,'Inicio / global > estado del motor','EngineStatusBar.tsx:63 imprime ENGINE_LABELS[engine.state] sin t()',{filter:r=>!['Motor en espera','Motor listo'].includes(r.texto),entry:{limite:'idle y ready no montan la barra; se excluyen. Los estados nativos no se reprodujeron en la cápsula web.'}});
select('context/DownloadProvider.tsx',87,87,'Inicio / global > estado de motor incompatible','engine.detail → EngineStatusBar sin t()');
select('context/DownloadProvider.tsx',542,542,'Inicio / global > motor desconectado','El sondeo genera engine.detail y la barra lo muestra sin t()');
select('components/EngineStatusBar.tsx',31,37,'Inicio / global > explicación del motor','ENGINE_EXPLANATION[engine.state] se imprime sin t()', {filter:human});
select('context/CaseContext.tsx',205,205,'Casos > intentar cambiar durante una corrida','guardLiveWork → setError → aviso del workspace');
select('context/CaseContext.tsx',314,316,'Casos > cola de guardado fallida','setError añade un sufijo al error de E/S; sólo el sufijo es propiedad frontend',{filter:r=>/cambio no se ha perdido/.test(r.texto),entry:{captura:'87-cola-guardado-error'}});
select('context/CaseContext.tsx',375,1041,'Casos > errores y recuperación','setError/throw → describeError → aviso del workspace; no se traduce por código',{filter:r=>human(r)&&!['CaseProvider requiere una sesión autenticada.'].includes(r.texto)&&r.tipo!=='jsx'&&!/^(?:relocate|repair|forget)$/.test(r.texto)});
select('lib/traspaso.ts',213,213,'Casos > traspaso del invitado > error','TraspasoInvitado muestra la causa del error; requiere datos legacy reales');
select('components/TraspasoInvitado.tsx',150,150,'Casos > traspaso del invitado > resumen','El componente concatena con resultado guardado sin t()');

select('components/interfaces/pro/AdvancedMolstarViewer.tsx',423,451,'Evaluación > Mol* > nombres de estructuras y tooltip','dataLabel se entrega a Mol* desde el frontend; no es texto original del tercero',{filter:r=>r.texto.includes('(')});
select('components/science/ProtocoloM5Zn.tsx',44,101,'Evaluación > Provenance and data > Pipeline > M5-Zn','ProtocoloM5Zn.tsx:125/128 imprime explicacion.titulo y explicacion.detalle sin t()', {filter:r=>r.tipo==='template'||(r.tipo==='string'&&r.texto.includes(' '))});
// Datos sin acento que se localizaron al leer AA_INFO; la heurística léxica no los garantiza.
const webLines=fs.readFileSync(ROOT+'/frontend/components/interfaces/pro/Web3DViewer.tsx','utf8').split(/\r?\n/);
for(let i=197;i<218;i++){
 const match=/name: "([^"]+)"/.exec(webLines[i]||'');if(!match)continue;
 if(entries.some(e=>e.archivo===`frontend/components/interfaces/pro/Web3DViewer.tsx:${i+1}`&&e.texto===match[1]))continue;
 add({texto:match[1],archivo:`frontend/components/interfaces/pro/Web3DViewer.tsx:${i+1}`,superficie:'Evaluación > View Web3D > nombre de aminoácido',consumidor:'aaInfoFromName → selectedInfo.name, Web3DViewer.tsx:1297, sin traductor',visto_por:'estatico',propuesta:'clave nueva',limite:'Requiere pulsar un hotspot en el canvas. No se completó la selección de cada aminoácido; la escena y su leyenda sí se observaron. La referencia de código se revisó.'});
}
if(!entries.some(e=>e.texto==='Extrema (>99 %)'))add({texto:'Extrema (>99 %)',archivo:'frontend/lib/admetEtiquetas.ts:21',superficie:'Evaluación > Properties > ADMET > PPB',consumidor:'ResultPropertiesPanel.tsx:31 muestra etiquetaPPB sin t(); rama extreme',visto_por:'estatico'});
add({texto:'· y',archivo:'frontend/components/TraspasoInvitado.tsx:160',superficie:'Casos > traspaso del invitado > más de cinco casos',consumidor:'JSX concatena y con el contador; no es dato aportado por el usuario',visto_por:'estatico'});

// Consolidar fragmentos del MISMO mensaje compuesto; conservar cada ruta de origen.
function merge(file,lines){
 const found=entries.filter(e=>lines.some(n=>e.archivo===`frontend/${file}:${n}`));if(found.length<2)return;
 const first=found[0];first.texto=found.map(e=>e.texto).join(' ');first.archivos=found.map(e=>e.archivo);
 for(const e of found.slice(1))entries.splice(entries.indexOf(e),1);
}
merge('lib/preflight.ts',[205,206]);merge('lib/proApi.ts',[131,132]);merge('lib/proApi.ts',[133,134,135]);merge('lib/dossier.ts',[479,480]);merge('components/ui/LocalDocViewer.tsx',[75,76]);merge('context/CaseContext.tsx',[376,378]);

// La disponibilidad del navegador y las defensas sin entrada de usuario no prueban un estado de escritorio.
const deferred=[];
for(let i=entries.length-1;i>=0;i--){const e=entries[i];if(/CaseContext.tsx:(747|789|832)$/.test(e.archivo)||/ProParametersTab.tsx:331$/.test(e.archivo)||/ProSelectivityPanel.tsx:(73|74|75)$/.test(e.archivo)){
 deferred.unshift({...e,motivo_fuera_del_total:'No se demostró un estado actual de escritorio que alcance esta rama: capability del repositorio, panel legacy o CYP3A4 ausente del panel por defecto. Se conserva como pista.'});entries.splice(i,1);
}}
// No confundir un estado VALIDATED sin productor actual con una fuga medida del producto.
// Las explicaciones de M5 incluidas son estados de revisión/abstención y el respaldo desconocido.

const scan=JSON.parse(fs.readFileSync(archivoExterno('evidencia/barrido-estatico-v3.json'),'utf8'));
for(const f of scan.formatos.filter(f=>f.clasificacion==='revisar'&&!/ProEvaluation|ReproducibilityInfo/.test(f.archivo))){
 const name=f.archivo.includes('ChatPanel')?'MolChat > historial de conversaciones > fecha':f.archivo.includes('CaseRunHistory')?'Casos > Previous evaluations > fecha':f.archivo.includes('CaseDisposition')?'Casos > Dossier > fecha de disposición':f.archivo.includes('Web3D')?'Evaluación > View Web3D > contador de átomos':'Evaluación / Moldex > vista elevada > números';
 const capture=f.archivo.includes('CaseRunHistory')?'102-historial-corridas-formato':f.archivo.includes('CaseDisposition')&&f.linea===96?'115-disposicion-formato':null;
 add({texto:capture&&f.archivo.includes('CaseRunHistory')?'25 oct 2026, 05:21 p.m.':capture?'25/10/2026, 8:36:49 p.m.':f.codigo,origen:'formato',archivo:'frontend/'+f.archivo+':'+f.linea,superficie:name,consumidor:f.codigo,captura:capture,visto_por:capture?'ambos':'estatico',propuesta:'usar locale de la aplicación',limite:!capture?'Dependencia del locale del sistema demostrada en código. Con navegador es-MX las cifras decimales pueden coincidir con en-US; no se afirma una diferencia visual en ese caso.':undefined});
}

add({texto:'MolDesign · código fuente: github.com/srcacahuate619/moldesign-molcy',archivo:'frontend/lib/softwareCatalog.ts:291',superficie:'Opciones > About MolDesign > Platform and visualization',consumidor:'AboutModal.tsx:163 imprime card.credit y Motor Molcy no tiene override de credit',captura:'106-about-2'});
for(const [file,line,text,capture] of [
 ['frontend/public/legal/THIRD_PARTY_NOTICES.md',1,'# MolDesign — avisos de software y modelos de terceros','107-legal-doc-0'],
 ['frontend/public/legal/SOURCE_CODE_AND_RELINKING.md',1,'# Código fuente, modificaciones y licencias','108-legal-doc-0'],
 ['frontend/public/registro/index.json',4,'El cociente GO/NO_GO del manifest NO es una tasa de aciertos: mezcla prerregistros -sellados GO al declararse-, mediciones sin gate y experimentos con gate real. Esta vista separa las tres poblaciones.','76-registro-inicial']]){
 add({texto:text,origen:'frontend_lib',subtipo:'public',archivo:file+':'+line,superficie:file.includes('/registro/')?'Registro científico > advertencia general':'Opciones > Legal > Licenses > documento local',consumidor:file.includes('/registro/')?'RegistroCientifico imprime indice.advertencia como explicación de la vista':'LocalDocViewer imprime el asset en pre; los textos de licencia originales de terceros se excluyen',captura:capture,unidad:file.includes('/legal/')?'documento propio sin variante por idioma; el encabezado es el ejemplo literal':'frase',propuesta:'clave nueva / variante inglesa del documento propio'});
}

const network=JSON.parse(fs.readFileSync(archivoExterno('evidencia/red.json'),'utf8'));
const backendEvidence=[];
function backend(text,endpoint,field,surface,capture,reference,code){
 add({texto:text,origen:'backend',archivo:endpoint+' → '+field,superficie:surface,captura:capture,visto_por:'dinamico',propuesta:code?'traducir por código':'inventariar',codigo:code,referencia_backend:reference,consumidor:'Respuesta HTTP capturada con Accept-Language: en; el frontend imprime el campo humano sin traducción adicional'});
 backendEvidence.push({endpoint,campo:field,texto:text,codigo:code,referencia:reference});
}
const pre=network.find(r=>r.url.endsWith('/evaluation/preflight')&&r.status===200).body;
for(const c of pre.controls)if(tool.spanish(c.title)||c.title==='Motor de docking')backend(c.title,'POST /evaluation/preflight',`controls[code=${c.code}].title`,'Evaluación > comprobación previa > Show details','30-preflight-detalle','backend/services/docking/preflight.py (Control por code)',c.code);
for(const [code,ref]of [['RECEPTOR_FUENTE_DISPONIBLE','backend/services/docking/preflight.py:595'],['GRID_EFECTIVO','backend/services/docking/preflight.py:1871'],['HOTSPOTS_EFECTIVOS','backend/services/docking/preflight.py'],['MOTOR_DOCKING_DISPONIBLE','backend/services/docking/preflight.py'],['PREPARADOR_RECEPTOR_DISPONIBLE','backend/services/docking/preflight.py']]){
 const c=pre.controls.find(c=>c.code===code);backend(c.observation,'POST /evaluation/preflight',`controls[code=${code}].observation`,'Evaluación > comprobación previa > Show details','30-preflight-detalle',ref);
}
const preparation=network.find(r=>r.url.includes('/evaluation/dossier/')&&r.url.endsWith('/preparacion')&&r.status===200).body;
for(const [bi,ri,cap,ref] of [[0,0,'63-preparacion-metal','backend/services/dossier/preparacion.py:743'],[4,5,'64-prep-metal-bloque-5','backend/services/dossier/preparacion.py:1690']]){
 const req=preparation.bloques[bi].requisitos[ri];backend(req.valor,'POST /evaluation/dossier/{molecule_id}/preparacion',`bloques[${bi}].requisitos[${ri}].valor`,'Preparación > bloques 1 y 5',cap,ref);
}
const prepCopia=network.find(r=>r.url.includes('/evaluation/dossier/c69159a9')&&r.url.endsWith('/preparacion')&&r.status===200)?.body;
if(prepCopia)backend(prepCopia.bloques[1].requisitos[0].valor,'POST /evaluation/dossier/{molecule_id}/preparacion','bloques[1].requisitos[0].valor','Preparación > Ligando > identidad','65-prep-copia-bloque-2','backend/services/dossier/preparacion.py:1120');
const result=network.find(r=>r.url.includes('/evaluation/result/404f4e38')&&r.status===200)?.body;
if(result)backend(result.pose_selection.model.name,'GET /evaluation/result/{molecule_id}?task_id={task_id}','pose_selection.model.name (también version)','Evaluación > Structural evidence / title del margen','44-evidencia-estructural','Identidad del modelo: conservar el identificador; separar descripción humana en un encargo backend.');
const startup=network.find(r=>r.url.endsWith('/ai/startup')&&r.body?.reason);
if(startup)backend(startup.body.reason,'GET /ai/startup','reason','MolChat > primer uso sin API key','70-molchat-inicial','backend/services/ai/startup_detection.py:172');
const providers=network.find(r=>r.url.endsWith('/ai/providers')&&r.status===200)?.body;
const providerList=Array.isArray(providers)?providers:providers?.providers||[];
for(const id of ['local','ollama']){
 const p=providerList.find(p=>p.id===id);if(p?.estado)backend(p.estado,'GET /ai/providers',`[id=${id}].estado`,'MolChat > Settings > proveedor '+id,id==='local'?'70-molchat-inicial':'74-molchat-ollama',id==='ollama'?'backend/services/ai/providers/ollama_provider.py:89':'backend/services/ai/local_llm.py:840');
}
const failed=evidence('71-molchat-turno-fallido').text.split('\n').find(s=>s.startsWith('MolChat Local no está disponible.'));
if(failed)backend(failed,'POST /ai/chat','SSE event=warning → data (prefijo __WARNING__:)','MolChat > enviar sin motor local > aviso SSE','71-molchat-turno-fallido','backend/services/ai/chat_service.py:1196; causa en backend/services/ai/local_llm.py:840. AIContext.tsx:717 retira __WARNING__: y lo muestra en warning banner; no es prosa del LLM.');
const antiBody=network.find(r=>r.url.includes('/pro/anti-targets')&&r.status===200)?.body;
const anti=antiBody?.anti_targets||[];
const observedText=evidence('40-analisis').text;
const seenReasons=new Set();
for(const a of anti){
 for(const field of ['motivo_no_disponible','motivo','risk'])if(a[field]&&tool.spanish(a[field])&&observedText.includes(a[field])&&!seenReasons.has(a[field])){seenReasons.add(a[field]);backend(a[field],'GET /pro/anti-targets',`anti_targets[${a.pdb_id?'pdb_id='+a.pdb_id:'name='+a.name}].${field}`,'Evaluación > Analysis > Selectivity > catálogo / motivo','40-analisis','backend/services/docking/selectivity.py y catálogo de anti-dianas');}
}
const ion=anti.find(a=>a.category?.includes('Canal iónico'));
if(ion)backend(ion.category,'GET /pro/anti-targets','anti_targets[].category','Evaluación > Analysis > Selectivity > familia','40-analisis','La categoría humana llega en la respuesta; no hay un código de familia separado.');

// Referencias de Rust: revisión estática del camino IPC, sin fingir ejecución en WebView2.
for(const [line,text,code,steps] of [
 [277,'UNAUTHORIZED: la carpeta no está autorizada en esta sesión. Vuelve a elegirla.','UNAUTHORIZED','Abrir una carpeta con un token ya revocado.'],
 [628,'UNSAFE_NAME: el nombre de la carpeta está vacío.','UNSAFE_NAME','IPC case_create con nombre rechazado por validate_folder_name; el formulario normal ya lo impide.'],
 [1403,'IO_ERROR: no se pudo escribir `case.json` de forma atómica ({e}).','IO_ERROR','Editar un caso cuya carpeta no permite escritura.']]){
 add({texto:text,origen:'rust',archivo:'frontend/src-tauri/src/cases.rs:'+line,superficie:'Casos > error nativo de carpeta',como_llegar:steps+' Sólo trazado por código, no reproducido en la cápsula web.',consumidor:'tauriCaseRepository.ts:73 toCaseError conserva rest; CaseContext.describeError → aviso',visto_por:'estatico',propuesta:'traducir por código',codigo:code,limite:'Los diálogos nativos/Rust están fuera de alcance. El error EPERM de 87 procede del puente de la cápsula y no prueba este mensaje Rust.'});
}

select('lib/api.ts',617,617,'Evaluación > PDB complex > error','downloadComplexFile vuelve a lanzar el Error en el catch; CaseEvaluationRunner lo muestra con otro prefijo castellano');
select('lib/auth.tsx',99,103,'Acceso > validación del formulario','extractErrorDetail convierte mensajes de validación en castellano; LoginForm muestra error sin t()', {filter:r=>r.tipo==='template'});
select('lib/auth.tsx',240,240,'Acceso > cuenta no registrada','Error.message se propaga hasta el formulario de acceso');
select('app/login/page.tsx',95,95,'Acceso > error inesperado','El catch usa el fallback y el formulario lo muestra');
select('lib/config.ts',88,88,'Inicio / global > puerto no utilizable','getApiUrl lanza Error; un consumidor de fetchBackend puede mostrar el message en el aviso de operación');
select('lib/config.ts',121,121,'Inicio / global > puente de escritorio roto','getApiUrl lanza Error; los consumidores que pintan message conservan el texto');
select('lib/tauri.ts',80,81,'Inicio / global > puente de escritorio no disponible','invoke → ensureEngine catch → engine.detail → EngineStatusBar');
merge('lib/tauri.ts',[80,81]);
select('components/ai/ProviderBadge.tsx',80,84,'MolChat > insignia del proveedor > recursos','ProviderBadge.tsx:142 imprime statusText sin t()',{filter:r=>r.tipo==='template'});
select('components/interfaces/pro/Web3DViewer.tsx',92,93,'Evaluación > View Web3D > leyenda de interacciones','INTERACTION_LABELS pasa por t(), pero estos cuatro valores no tienen alias exacto',{filter:r=>['Hidrofóbico','Puente salino','Catión-π','Halógeno'].includes(r.texto)});
for(const [line,text]of [[80,'GPU · ${gpu_name} libre ${freeDisplay}'],[83,'CPU · ${ram_free_gb?.toFixed(1) ?? t("auto_5bab61eb5317")}G libre / ${ram_total_gb?.toFixed(0) ?? t("auto_5bab61eb5317")}G']])if(!entries.some(e=>e.texto===text))add({texto:text,archivo:'frontend/components/ai/ProviderBadge.tsx:'+line,superficie:'MolChat > insignia del proveedor > recursos',consumidor:'statusText se imprime en ProviderBadge.tsx:142; el término libre no pasa por t()',visto_por:'estatico'});
select('components/evaluation/CaseEvaluationRunner.tsx',750,750,'Evaluación > catálogo no disponible','loadTargets catch → setError → alerta del runner');
select('components/evaluation/CaseEvaluationRunner.tsx',955,955,'Evaluación > recuperar corrida > otra causa','El fallback final se muestra en resultRecovery.error');
select('context/AIContext.tsx',337,337,'MolChat > Settings > proveedores HTTP fallido','loadProviders lanza Error; AISettingsModal lo imprime');
select('context/AIContext.tsx',400,400,'MolChat > arranque sin conexión','SET_STARTUP_MODE.message → ChatPanel.tsx:801');
select('context/AIContext.tsx',412,412,'MolChat > Settings > activar proveedor > error','setActiveProvider → catch de AISettingsModal → settingsError');
select('context/AIContext.tsx',491,491,'MolChat > Settings > guardar configuración > error','updateProviderConfig → catch de AISettingsModal → settingsError');
select('context/AIContext.tsx',571,571,'MolChat > Settings > carga persistente > error','setKeepLoaded → catch de AISettingsModal → settingsError');
select('context/AIContext.tsx',611,611,'MolChat > nueva conversación > otra causa','SET_WARNING_BANNER.warning → ChatPanel');
select('lib/auth.tsx',102,103,'Acceso > email inválido','translateValidationMsg produce el mensaje; formulario de acceso lo imprime');
select('components/interfaces/pro/ProSarTab.tsx',170,170,'Evaluación > Analysis > SAR > resultado de la consulta','El contador cambia de la clave LOADING a una plantilla castellana cuando loading=false');
select('components/interfaces/pro/ProSelectivityPanel.tsx',61,61,'Evaluación > Analysis > Selectivity > detalle hERG','El detalle usa la ficha conocida del frontend',{entry:{captura:'90-analisis-desplegado'}});
select('components/interfaces/pro/ProSelectivityPanel.tsx',81,81,'Evaluación > Analysis > Selectivity > detalle 5-HT2B','El detalle usa la ficha conocida del frontend',{entry:{captura:'90-analisis-desplegado'}});
select('components/interfaces/pro/ProSelectivityPanel.tsx',796,796,'Evaluación > Analysis > Selectivity > cobertura incompleta','Plantilla del contador de anti-dianas no evaluadas',{filter:r=>r.tipo==='template'});
select('app/evaluation/batch/page.tsx',523,529,'Batch > Report > nombres de descarga de respaldo','fallback del nombre al no recibir filename en Content-Disposition',{filter:r=>/\.pdf|\.zip/.test(r.texto),entry:{limite:'En las descargas reales hubo nombre del backend; se documenta la rama fallback del frontend, sin afirmar que se observó.'}});
select('components/interfaces/pro/RunDataExplorer.tsx',51,51,'Evaluación > Provenance and data > Export JSON','Nombre propio del archivo que propone el frontend al descargar los datos consultables');
select('components/interfaces/pro/AdvancedMolstarViewer.tsx',123,123,'Evaluación > Mol* > título SDF del candidato','patchSdfTitle fija este título en el SDF que carga Mol*; el nombre lo genera el frontend');

// Las etiquetas de las etapas sí se localizan por alias; la frase del skip añade texto sin traducir.
select('components/interfaces/pro/PipelineTimeline.tsx',203,203,'Evaluación > progreso > etapa omitida con motivo','El JSX compone no se calculó por + message; requiere una etapa skip que llegue a ese orb',{filter:r=>r.tipo==='template'});
select('lib/pipelineStream.ts',101,103,'Evaluación > progreso > fallback de etapa fallida/omitida','stageEventToOrbUpdate → stageMessages → PipelineTimeline.tsx:203; el mensaje no pasa por t()',{filter:r=>['Error en la etapa','no se calculó'].includes(r.texto)});
select('components/interfaces/pro/PipelineTimeline.tsx',20,20,'Evaluación > progreso > propiedades con ADMET','t(s.label) recibe Propiedades / ADMET, sin alias exacto en el diccionario',{entry:{limite:'Requiere stage_params.properties.run_admet_ai=true en el protocolo guardado. No se ejecutó ADMET ni se descargaron modelos; el protocolo por defecto usa false.'}});
select('components/interfaces/pro/PoseComparisonDialog.tsx',98,98,'Evaluación > Compare poses > coordenadas no disponibles','El catch asigna message y el error se imprime en el diálogo');
add({texto:'y #',archivo:'frontend/components/interfaces/pro/PoseComparisonDialog.tsx:138',superficie:'Evaluación > Compare poses > encabezado',consumidor:'JSX concatena y entre los dos rangos después del prefijo traducido',captura:'45-comparar-poses',visto_por:'ambos',propuesta:'clave nueva con ambos rangos interpolados'});
select('lib/api.ts',141,141,'Casos > Previous evaluations > conexión fallida al abrir resultado','getEvaluationResult propaga ERROR_DE_CONEXION → detail.message sin t(). El Historial principal sí usa t(error), comprobado en captura 104.');
const sarReply=network.findLast(r=>r.url.includes('/sar/')&&r.status===200)?.body;
if(sarReply?.analogs?.[0]?.highlight)backend(sarReply.analogs[0].highlight,'GET /sar/{molecule_id}','analogs[].highlight (también results[].highlight)','Evaluación > Analysis > SAR > consulta terminada','117-sar-consulta-terminada','backend/services/sar/comparabilidad.py:45','comparison_state=descriptive');
for(let i=entries.length-1;i>=0;i--){const e=entries[i];if(e.archivo.endsWith('BloqueDeEvidencia.tsx:106')||e.archivo.endsWith('AdvancedMolstarViewer.tsx:123')||e.archivo.endsWith('lib/traspaso.ts:213')){
 deferred.unshift({...e,motivo_fuera_del_total:e.archivo.includes('Bloque')?'La rama no verificada muestra t(auto_280145ccad5c), no e.clase.':'Marcador SDF de identificación o defensa de una capability que ambos repositorios actuales implementan; no se demostró fuga de presentación.'});entries.splice(i,1);
}}
for(const e of entries){if(e.archivo.endsWith('ProSarTab.tsx:170'))e.captura='capturas/117-sar-consulta-terminada.png';if(e.archivo.endsWith('ProSarTab.tsx:170'))e.visto_por='ambos';}

// El padre sólo monta M5 cuando protocoloRegistrado devuelve M5-Zn, no por tener un estado de revisión.
for(let i=entries.length-1;i>=0;i--)if(entries[i].archivo.includes('/ProtocoloM5Zn.tsx:')){
 deferred.unshift({...entries[i],motivo_fuera_del_total:'PipelineDeLaCorrida.tsx:24 exige protocolo M5-Zn. La corrida real 1BN1 es M4 (captura 116); no se demostró un registro actual que monte este panel. No se cuenta la tabla interna como fuga actual.'});entries.splice(i,1);
}

// Capturas verificadas por búsqueda del texto exacto o del ejemplo interpolado.
for(const e of entries){
 const old=e.captura;const s=old&&snapshots.find(s=>'capturas/'+s.name+'.png'===old);
 if(s){
   const all=s.text+'\n'+JSON.stringify(s.attributes);
   if(!all.includes(e.ejemplo||e.texto)&&!e.plantilla&&!e.unidad&&!e.codigo&&!e.texto.includes('${')){
     // Una captura de la superficie no es prueba del literal ausente.
     e.captura_superficie=old;e.captura=null;e.visto_por=e.origen==='backend'?'dinamico':'estatico';
     e.limite=(e.limite?e.limite+' ':'')+'El PNG de la superficie no acredita este literal; se conserva como referencia, sin contarlo como observado.';
   }
 }
}
for(const e of entries){
 if(!e.captura)continue;
 const s=snapshots.find(s=>'capturas/'+s.name+'.png'===e.captura);if(!s)continue;
 const all=[...s.text.split('\n'),...s.attributes.flatMap(a=>[a.title,a.ariaLabel,a.ariaDescription,a.placeholder,a.alt].filter(Boolean))];
 let sample=e.ejemplo;
 if(!sample&&e.texto.includes('${')){
   const prefix=e.texto.split('${')[0];
   sample=prefix.length>=6?all.find(t=>t.startsWith(prefix)):undefined;
   if(e.archivo.includes('CaseSidebar'))sample=all.find(t=>/^\d+ casos$/.test(t));
   if(e.archivo.includes('ProOptionsModal'))sample=all.find(t=>/ · importancia /.test(t));
   if(e.archivo.includes('Web3DViewer'))sample=all.find(t=>/ · cadena /.test(t));
   if(e.archivo.includes('CaseContextPanel'))sample=all.find(t=>/\d+ advertencia/.test(t));
   if(e.archivo.includes('CaseContext.tsx:314'))sample=all.find(t=>/El cambio no se ha perdido/.test(t));
   if(e.archivo.includes('AIContext'))sample=all.find(t=>t.includes('No se pudo conectar con el motor'));
 }
 if(sample&&e.texto!==sample){e.texto_fuente=e.texto;e.texto=sample;e.ejemplo=sample;}
 e.recorrido_dinamico=Number(s.name.split('-')[0])<=88?'A2 inicial independiente':'A2b dirigido por A1';
}
entries.sort((a,b)=>a.archivo.localeCompare(b.archivo, 'en')||a.texto.localeCompare(b.texto,'en'));
entries.forEach((e,i)=>{e.id='I18N-'+String(i+1).padStart(3,'0');if(!e.captura&&e.visto_por==='estatico'&&!e.limite)e.limite='Rama de interfaz trazada hasta su consumidor; no se provocó este fallo/estado durante A2.';});
const output={entries,conditions,deferred,backendEvidence};
if(require.main===module){fs.writeFileSync(path.join(AUD,'evidencia/inventario-compilacion.json'),JSON.stringify(output,null,2));console.log(JSON.stringify({hallazgos:entries.length,porArchivo:entries.reduce((a,e)=>(a[e.archivo.replace(/:\d+$/,'')]=(a[e.archivo.replace(/:\d+$/,'')]||0)+1,a),{})},null,2));}
module.exports={ROOT,AUD,rows,entries,conditions,deferred,backendEvidence,tool,states,snapshots,evidence,add};
