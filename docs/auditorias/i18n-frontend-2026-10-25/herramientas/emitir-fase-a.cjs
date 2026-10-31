const {archivo: archivoExterno}=require('./archivo-fase-a.cjs');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const data=require('./clasificar-a1.cjs');
const {ROOT,AUD,entries,ledger,remaining,deferred,backendEvidence,tool,states,snapshots}=data;
const write=(file,text)=>fs.writeFileSync(path.join(AUD,file),file.endsWith('.md')?text.replaceAll(String.fromCharCode(92,92),String.fromCharCode(92)):text);
const archivedGenerated=new Set(['evidencia/decisiones-a1.json','evidencia/correspondencias-es-en.json','evidencia/diccionario-completo.json']);
const json=(file,value)=>{if(!archivedGenerated.has(file))write(file,JSON.stringify(value,null,2)+'\n');};
const norm=s=>String(s).normalize('NFKC').replace(/\s+/g,' ').toLocaleLowerCase('en-US');
const dom=s=>s.text+'\n'+s.attributes.flatMap(a=>[a.title,a.ariaLabel,a.ariaDescription,a.placeholder,a.alt].filter(Boolean)).join('\n');
const initial=snapshots.filter(s=>Number(s.name.split('-')[0])<=88);
const counts=(items,key)=>Object.fromEntries([...items.reduce((m,e)=>m.set(key(e),(m.get(key(e))||0)+1),new Map())].sort((a,b)=>a[0].localeCompare(b[0],'en')));
function surface(e){if(e.superficie.startsWith('Preparación'))return 'Preparación y dossier';if(e.superficie.startsWith('Inicio'))return 'Estado del motor';if(e.superficie.startsWith('Opciones'))return 'Opciones y legal';return e.superficie.split(' > ')[0];}
const table=o=>'| Categoría | Entradas |\n|---|---:|\n'+Object.entries(o).map(([k,v])=>`| ${k} | ${v} |`).join('\n');
const id=(file,line)=>entries.find(e=>e.archivo===file+':'+line)?.id||'ver inventario';
// La captura final enfocada sustituye a la vista cuyo literal quedaba fuera del viewport.
for(const e of entries){
 if(e.archivo.endsWith('ProSarTab.tsx:170')||e.archivo.startsWith('GET /sar/'))e.captura='capturas/118-sar-visible.png';
 if(e.archivo.endsWith('CaseContextPanel.tsx:57'))e.captura='capturas/119-contexto-opcional-visible.png';
 if(e.archivo.endsWith('MolecularComparison.tsx:89'))e.captura='capturas/120-comparacion-indice-visible.png';
 if(e.superficie.endsWith('tipo de residuo')&&['Hidrofóbico','Aromático','Estructural','Ácido'].includes(e.texto)){e.captura='capturas/114-visor-leyenda-tipos.png';e.visto_por='ambos';}
 if(e.captura){const s=snapshots.find(s=>e.captura==='capturas/'+s.name+'.png');if(s)e.evidencia_dom='evidencia/'+s.name+'.json';}
 e.presente_en_dom_A2_inicial=initial.some(s=>{const text=norm(dom(s));return text.includes(norm(e.ejemplo||e.texto))&&norm(e.texto).length>3;});
 if(!e.captura&&e.visto_por==='estatico'&&!e.limite)e.limite='Se trazó el consumidor; no se reprodujo esta rama en A2.';
}
const perOrigin=counts(entries,e=>e.origen),perSurface=counts(entries,surface),perSeen=counts(entries,e=>e.visto_por);
const screenshotNames=states.map(s=>s.name).filter(n=>n!=='84-batch-informe'&&fs.existsSync(archivoExterno('capturas/'+n+'.png')));
const missing=states.filter(s=>!(s.name!=='84-batch-informe'&&fs.existsSync(archivoExterno('capturas/'+s.name+'.png')))).map(s=>s.name);
const matrix=counts(entries,e=>(e.origen==='backend'?'sin productor en A1':'trazado en A1')+' / '+(e.presente_en_dom_A2_inicial?'presente en DOM A2 inicial':'ausente del DOM A2 inicial'));
const summary={base:'4fc7a9281fecb209a94784d15983475d64b517e8',rama:'sol/i18n-frontend',fase:'A',entradas:entries.length,por_origen:perOrigin,por_superficie:perSurface,por_barrido:perSeen,candidatos_estaticos:ledger.length,filas_estaticas_inventariadas:ledger.filter(r=>r.decision==='inventariado').length,filas_estaticas_excluidas:ledger.filter(r=>r.decision==='excluido').length,candidatos_sin_decision:remaining.length,estados:states.length,png_con_estado:screenshotNames.length,png_faltantes:missing,estados_A2_inicial:initial.length,matriz_presencia:matrix};

function validate(){
 assert.equal(remaining.length,0,'Quedan candidatos sin decisión');
 assert.equal(new Set(entries.map(e=>e.id)).size,entries.length);
 const origins=new Set(['frontend_tsx','frontend_lib','formato','backend','rust','tercero']);
 for(const e of entries){
  for(const key of ['id','texto','origen','archivo','superficie','como_llegar','visto_por','propuesta'])assert(e[key],e.id+' sin '+key);
  assert(origins.has(e.origen),e.id+' origen');
  if(e.captura)assert(fs.existsSync(archivoExterno(e.captura)),e.id+' PNG ausente');
  if(e.evidencia_dom)assert(fs.existsSync(archivoExterno(e.evidencia_dom)),e.id+' DOM ausente');
  if(e.archivo.startsWith('frontend/')){const m=/^(.*):(\d+)$/.exec(e.archivo);assert(m,e.id+' ruta:línea');const lines=fs.readFileSync(ROOT+'/'+m[1],'utf8').split(/\r?\n/);assert(Number(m[2])>0&&Number(m[2])<=lines.length,e.id+' línea inválida');}
  if(e.origen==='backend')assert(e.archivo.includes(' → '),e.id+' campo backend');
 }
 // Controles del ledger: ve fugas y conserva negativos de los caminos ya localizados.
 for(const [file,line]of [['frontend/lib/moldex.ts',304],['frontend/components/cases/CaseContextPanel.tsx',69],['frontend/lib/preflight.ts',256]])assert(ledger.some(r=>r.archivo===file&&r.linea===line&&r.decision==='inventariado'),file);
 for(const file of ['frontend/lib/errors.ts','frontend/lib/evaluationEvidence.ts','frontend/lib/resultFieldPresentation.ts'])assert(ledger.some(r=>r.archivo===file&&r.decision==='excluido'),file);
 assert(ledger.some(r=>r.razon==='sólo consola'));
 assert(ledger.some(r=>r.razon==='literal de tipo'));
 console.log('Validación Fase A: esquema, IDs, rutas/líneas, PNG/DOM y 8 controles del ledger, OK.');
}
validate();
for(const entry of entries)for(const key of ['captura','captura_superficie','evidencia_dom'])if(entry[key])entry[key]=archivoExterno(entry[key]).replaceAll('\\','/');
json('inventario.json',entries);
json('evidencia/decisiones-a1.json',ledger);
json('evidencia/pistas-sin-estado-demostrado.json',deferred);
json('evidencia/campos-backend.json',backendEvidence);
json('evidencia/resumen.json',summary);
json('evidencia/correspondencias-es-en.json',tool.pares);
json('evidencia/diccionario-completo.json',tool.todos);

write('INFORME_FASE_A.md',`# Fase A — inventario de castellano con la app en English

La aplicación sí presenta castellano en English. El inventario contiene **${entries.length} entradas**: mensajes o plantillas de presentación, campos humanos de API y seis dependencias de formato. No es un recuento de palabras ni el número de ocurrencias: una plantilla con números distintos cuenta una vez; un documento propio sin variante inglesa cuenta una vez. Las ramas no reproducidas se distinguen de lo observado. No se ha cambiado producto, diccionario, backend, Rust ni ciencia.

Base comprobada: \`4fc7a9281fecb209a94784d15983475d64b517e8\`, rama \`sol/i18n-frontend\`, worktree \`D:\\moldesign-worktrees\\sol-i18n\`. El literal \`D:\\moldesign-build\\..\\docs\\encargos\\…\` no existía; se leyó el archivo del mismo nombre que está en \`D:\\moldesign-build\\docs\\encargos\\\`. AGENTS.md se leyó completo y coincidía entre main y worktree. Esta entrega cierra A y se detiene para revisión; B y C siguen sin iniciar.

## Recuento y alcance de la evidencia

${table(perOrigin)}

\`frontend_lib\` incluye los módulos TS de context y tres recursos de public. Los nombres de receptor/molécula/caso, prosa del LLM, textos de papers, códigos científicos y claves de archivos no cuentan como fugas. Los tres registros Rust son referencias estáticas del camino IPC, no observaciones del instalador. Cero entradas de tercero significa que no se observó castellano atribuible a esos componentes en el recorrido; no certifica todos sus menús.

${table(perSurface)}

${table(perSeen)}

Cada entrada lleva ruta:línea o endpoint/campo, consumidor, navegación, propuesta y limitación cuando procede. \`captura: null\` significa que no se obtuvo una imagen del literal; una captura de la superficie se guarda aparte y no acredita ese texto. El JSON de cada estado conserva también title, aria-label, aria-description, placeholder y alt. Un atributo accesible no necesita tener texto visible en el PNG para ser una fuga.

Hay **${states.length} estados** y **${screenshotNames.length} PNG asociados**. Falta PNG de: ${missing.join(', ')||'ningún estado'}. Los contenedores de la app tienen scroll interno: \`innerText\` puede incluir texto fuera del viewport. Se añadieron capturas enfocadas para SAR, contexto opcional, leyenda y tabla comparativa; no se afirma que cada frase de un control largo quepa en un solo PNG.

## Cómo se midió

Se usó el export estático real, con CSP de producción, servido por la cápsula agente 1: app \`http://localhost:13011\`, backend \`http://127.0.0.1:18011\`. No se usó next dev. Se seleccionó English por la UI y persistió al recargar. Chrome 156 con locale del navegador \`es-MX\`, distinto del idioma de la app, permitió detectar las fechas dependientes del sistema. Esto prueba el export en Chrome, no WebView2 ni el instalador.

La cápsula fue reseteada antes del primer recorrido. El primer export se construyó en 123 s; el manifiesto limpio después del reset documenta su reutilización. Al parar el backend se detuvo sólo el PID/puerto verificado de la cápsula; se restauró con \`--rebuild\` (75 s). El segundo manifiesto tiene árbol no limpio por los nuevos archivos de auditoría; no hubo diferencias de producto. Los logs y el manifiesto inicial se conservan como evidencia.

Se ejecutó Vina real con ex=8, 9 poses y semilla 42 para 8HFI/aspirina, 1BN1/aspirina, 6SXC/aspirina y 8T69/4-67, además del lote CSV (dos moléculas únicas y una reutilización). Hubo una cancelación. La corrida de 4-67 alcanzó controles físicos \`not_evaluated\` por plazo; no es un reanálisis ni una repetición científica del experimento sellado, cuyos archivos sólo se leyeron. Se guardaron corridas de QA en Moldex. La preparación dio revisión o bloqueo; no se demostró un sistema global READY para FEP. Los controles técnicos que pasan no se confunden con readiness global.

Las subidas propias A/B/C y un rechazo se recorrieron con fixtures locales. Se comprobó CSV con duplicados/excepciones, SDF duplicado, cohorte guardada, ejecución y resultados. Se dibujó un anillo con Benzene en Ketcher y su SMILES quedó \`C1C=CC=CC=1\`; no se ejecutó ese dibujo. Se recorrieron Molcy, configuración de renderizador, fotos CPU y estados ausentes, MolChat/proveedores/voz deshabilitada/turno fallido, Historial, Comunidad, Registro y la vista inicial de certificación. Las descargas individual y de cohorte recibieron HTTP 200 con **Accept-Language: en**; no se audita ni reescribe el PDF backend.

El fallo de cola fue real: sólo se hizo readonly el manifiesto del caso sintético I18N Unavailable, se provocó el guardado, se capturó el sufijo castellano y se restauraron sus atributos Archive; Retry recuperó la cola. La disposición de I18N QA se guardó sólo para comprobar su fecha y declara expresamente que es QA, no una conclusión científica.

## Independencia y comparación de los barridos

Se conserva A2 inicial (capturas 01–88, ${initial.length} estados) como material recogido antes de la revisión de candidatos A1. Por prudencia, **todas las capturas 89 en adelante se consideran A2b dirigido por A1**, aunque algunas completan una acción ya prevista. No se presentan esas comprobaciones como descubrimientos independientes. PROGRESO.md anterior situaba el corte en 101; se corrige aquí de forma conservadora.

La copia A1 amplía los roots a app/components/hooks/lib/context y .ts/.tsx, excluye traducciones/tests y conserva literales devueltos, throws y plantillas. v3 produjo **${ledger.length} candidatos en 243 archivos**, y 17 llamadas de formato. Son candidatos, no defectos. Tras abrir productores y consumidores: ${summary.filas_estaticas_inventariadas} filas AST se relacionan con entradas y ${summary.filas_estaticas_excluidas} se excluyen con motivo en decisiones-a1.json; quedan ${remaining.length} sin decisión en ese ledger. Varias entradas manuales no tienen fila del detector: nombres sin tilde, el conector «y #», recursos public y errores backend/Rust.

Esta matriz mide **presencia de la cadena en el DOM inicial guardado**, no memoria humana de haberla advertido entonces, ni precisión/recall del detector:

${table(matrix)}

- A2 inicial contiene títulos castellanos de preflight, valores de Preparación, motivos de anti-dianas, estado del proveedor y la insignia de carga «anión −1». A1 de frontend no inspecciona los productores backend; ver ${id('frontend/components/interfaces/pro/EstadoDelLigando.tsx',47)} para la carga frontend y las entradas POST /evaluation/preflight para la API.
- A1 trazó errores de HTTP/transporte, recuperación, autenticación, indicadores de guardado, nombres de descarga, fechas sin locale y comparaciones crudas que A2 inicial no activó. Cada uno conserva su condición; no se fabricaron resultados para obtener una captura.
- A2b confirmó la comparación de Moldex (${id('frontend/lib/moldex.ts',304)}), los fallbacks SHAP (${entries.find(e=>e.archivo.includes('/ProXaiTab.tsx:'))?.id}), el historial de corridas, los textos del contexto, el visor Web3D y SAR después de terminar la consulta. En SAR, 93 sólo acreditaba LOADING; 117/118 acreditan el resultado. No se reutiliza 93 como prueba de «2 análogos».
- A1 v1 no veía «Capa Distancia» ni «PESO MOL.»: carecen de tildes y palabras función. v2/v3 añadieron vocabulario diferencial es/en y controles positivos. Aun así la heurística no garantiza reconocer nombres como Alanina o el conector y: se añadieron por lectura y búsqueda AST adicional.
- A2 léxico produjo falsos positivos como \`Del\` en atajos de Ketcher, \`principal\` en una frase inglesa de Mol*, nombres I18N y claves \`protocolo\`. Se excluyeron por contexto, no mediante presupuestos nuevos.

## Por qué los guardianes anteriores están verdes

Se volvió a medir \`finish-i18n-frontend.cjs --json\`: **[]**, \`--autotest\`: **60 muestras**; las tres suites de i18n pasan **18/18**. Sus rutas reales son lib/__tests__, no context/__tests__ como citaba el encargo. Los recibos están en evidencia/verificacion.

1. El barrido y trinquete previos miran .tsx de app/components/hooks. No cubren módulos TS de lib/context, recursos public ni productores backend/Rust.
2. Su heurística de visibilidad no sigue retorno/helper/variable hasta JSX, ni resuelve una plantilla que se compone antes de llamar t(). Tener la misma frase base en el diccionario no traduce el resultado ya interpolado.
3. La paridad de claves es real, pero no prueba que los consumidores usen una clave o un alias existente. El diccionario también puede contener inglés de baja calidad: Earrings, It's, grafías británicas.
4. Las fechas sin locale no contienen necesariamente una palabra castellana en el código. Adoptan el locale del navegador/sistema y necesitan revisar la llamada y contrastar el render.
5. Un recorrido que captura sólo el estado de carga pierde el resultado posterior, como ocurrió con SAR. Los textos de error y metadatos accesibles requieren acciones y estados adicionales.

También hubo falsos candidatos importantes: evaluationEvidence se localiza al final y su consumidor pasa t; resultFieldPresentation tiene columnas es/en; sitioDelReceptor desvía a funciones inglesas; errors.ts no tiene consumidores; el panel readiness antiguo no se monta. La tabla M5-Zn y defensas legacy están en pistas-sin-estado-demostrado.json: el padre exige un protocolo que no produjo la corrida M4 actual, por lo que no se contaron sus frases internas como fuga de esa pantalla.

## Verificación y siguiente puerta

La herramienta aparte tiene **23 comprobaciones** positivas/negativas (13 lingüísticas, 4 AST, 4 formato, 2 DOM). La compilación del inventario valida esquema, IDs, rutas/líneas existentes, PNG/DOM y ocho controles del ledger. No sustituye un guardián general: el ledger es una revisión curada del commit base. No se tocó el detector original, su inventario ni sus presupuestos.

No se corrieron tauri:build ni stage:desktop. Los seis comandos completos exigidos en B/C quedan para esas fases; esta entrega de A no afirma haberlos ejecutado. Las limitaciones están en [lo_que_no_pude.md](lo_que_no_pude.md), y las observaciones que no deben corregirse de paso en [observaciones.md](observaciones.md).

Revisar [inventario.json](inventario.json), [glosario.md](glosario.md) y los límites antes de B. Toda entrada sigue pendiente o marcada por su origen externo; **cero arreglos se declaran cerrados**.
`);

write('lo_que_no_pude.md',`# Límites de la Fase A

- Se verificó el export con CSP de producción en Chrome 156, no el instalador, WebView2, los diálogos del sistema ni las notificaciones nativas. La cápsula emula el puente Tauri. Los tres mensajes Rust son referencias estáticas; el EPERM de la cola no demuestra que Rust emita su literal.
- La cápsula ve recursos compartidos preexistentes: pesos ESMFold/Qwen. No se descargó, arrancó ni ejecutó ESMFold/LLM. El guard de la cápsula comprueba existencia de modelos, no sustituye la verificación SHA del instalador. El motor local de MolChat está ausente; no se mide calidad de sus respuestas ni el correo largo de reporte. No se abrió ni envió correo.
- Molecular Nodes no está instalado. Hay una ruta de Blender en la máquina; se recorrieron las tarjetas y configuración, no se afirma haber probado un render real CPU, un vídeo sin GPU ni estados de trabajos completados/fallidos de Blender. El requisito de no descargar impide completar esos caminos. La falta del addon puede tener prioridad sobre el aviso de GPU.
- La voz no está disponible por faltar el reconocedor local. Se capturaron su aviso y control deshabilitado; no se capturó audio ni se instaló nada.
- No se introdujeron claves de API ni se autorizaron destinos remotos. La certificación se abrió sólo hasta la vista inicial/consentimiento. La revisión automática rechazó el primer intento por posible publicación; después se acreditó el manejador de sólo apertura y la separación del consentimiento. No hubo faucet, transacción, wallet ni publicación devnet.
- No se obtuvo un sistema global READY de Preparación. Se inspeccionaron revisión y bloqueo en los tres sistemas, además de los controles técnicos que pasan. Esto no certifica readiness FEP.
- No se construyeron datos falsos para errores de contrato/HTTP, pérdida de sesión, registros legacy o salidas de modelos ausentes. Su condición y consumidor están en cada entrada estática. Los ejemplos de schema.ts fueron revisados, pero la validación nativa del manifiesto ocurre antes y el formulario normal intercepta nombres inválidos: no se cuentan esas frases defensivas TS como fugas demostradas del escritorio.
- Un componente importado no prueba que todas sus ramas se monten. La tabla M5-Zn requiere protocolo M5-Zn; la corrida 1BN1 actual es M4. Se conserva la pista sin sumarla al total. Las fichas CYP3A4, el modal MM-GBSA y fuentes legacy similares tienen el mismo límite explícito.
- No se completó la selección individual de hotspots para comprobar todos los nombres del popup. La escena Web3D y la leyenda sí se renderizan (114); los nombres se trazaron hasta su consumidor. No se afirma haber observado cada aminoácido ni todos los menús de Mol* y Ketcher. Se completó un dibujo 2D por gesto real.
- Fechas: se contrastó app en English con navegador es-MX. Las fechas 102 y 115 sí muestran el formato del sistema. Los números pueden coincidir con en-US en es-MX; las llamadas sin locale tienen evidencia estática, no un supuesto cambio visual.
- Los PNG muestran el viewport con scroll interno; los JSON conservan el DOM de todo el contenedor y atributos. Se añadieron 118/119/120 tras verificar que el literal de interés quedara a la vista. El PNG 84 de informe de lote no se obtuvo por timeout; su DOM y la petición de idioma sí se conservaron.
- El corte independiente se fija de forma conservadora en 01–88. 89 en adelante es comprobación dirigida A2b. El campo visto_por=ambos significa dos tipos de evidencia, no independencia de descubrimiento.
- No se garantiza exhaustividad de cualquier texto futuro ni de un backend con otras versiones/datos. El detector léxico tiene límites declarados; la lista de exclusiones es evidencia revisada de la base, no una lista blanca para una futura regresión.
`);

write('observaciones.md',`# Observaciones — sin corregir producto en A

- Inglés americano: se observaron Quantisation (72), serialised (90) y prioritisation (101), fuera de la lista británica que revisa el guardián actual. El texto es del diccionario/interfaz; no se reescribe el castellano para corregirlo.
- El contexto traduce Pendientes como Earrings y un sufijo plural como It's; se ve «5 advertencias, 2 opcionalIt's». No basta una prueba de paridad de claves para garantizar una traducción útil. Curación aparece como Healing en progreso; el glosario conserva ese uso, sin unificarlo.
- En el lote sigue apareciendo QuickVina 2 deshabilitado como Coming soon. Es una divergencia con la política del menú individual descrita por AGENTS.md, no una propuesta para añadir ni activar ese motor.
- Los textos dicen calibrated/readiness en algunos títulos de preparación del selector; el catálogo no queda calibrado por esa etiqueta. La traducción de B debe conservar el castellano literal y abrir un encargo separado si cambia la afirmación científica.
- Hay lógica que compara texto castellano: localizeReceptorLabel («No definido», cadena/cadenas), localizeCaseStorageLabel, claveDeVeredicto, localizePipelineText y nombres legacy que empiezan por «Ligando ». La fase B no debe añadir más comparaciones. El alcance de un refactor debe separar códigos/identidad de presentación y llevar pruebas; no cambiar nombres del usuario ni formatos persistidos.
- El SDF candidato usa Candidato_Ligando_MolDesign como marcador de identificación y Mol* recibe dataLabel humanos aparte. Traducir el marcador sin separar la identidad puede romper la selección. Sus labels humanos sí están en inventario; el marcador queda como observación técnica.
- Los documentos legales propios de public se muestran tal cual. Una futura variante inglesa requiere preservar las licencias originales de terceros y una revisión del contenido legal; A sólo los identifica, no ofrece asesoría jurídica.
- La identidad del modelo backend incluye «selector oficial de Ruta C». No se debe renombrar a mano una versión científica para ocultar castellano: conservar el identificador y separar la explicación humana mediante contrato estable.
- «No evaluado», «Demo», la abstención y las reservas científicas deben conservar su fuerza. Los errores frontend inventariados no justifican suavizar un bloqueo ni fabricar un resultado.
- La captura SAR 93 se tomó durante LOADING. El resultado posterior 117/118 expuso un contador y un highlight castellanos. Las pruebas futuras deben esperar el estado terminal, no sólo que exista el panel.
`);

const terms=['Evaluación','Batch','Lotes','Preparación','No evaluado','No evaluada','NO EVALUADO','Demostración','Verificados','Tus receptores','En revisión','Requiere revisión','Revisión','Bloqueado','BLOQUEADO','Listo','Abstención','Se abstiene','Curación','Propiedades','Controles superados','Controles fallidos','Pendiente','Pendientes','Pendientes:','Informe','Dossier','Caso','Nuevo caso','Guardar','Guardado','Sin datos','No disponible','No registrado','No definido','Experimental','Afinidad Vina observada','Afinidad observada','Pose','Poses','Ligando','Receptor','Moldex','Molcy','MolChat'];
const termRows=[];
for(const es of terms){for(const d of tool.todos.filter(d=>d.es===es))termRows.push({es,en:d.en,clave:d.key,archivo:'frontend/'+d.archivo});}
assert(termRows.some(r=>r.es==='Batch'&&r.en==='Batch'),'El glosario debe conservar términos iguales en ambos idiomas');
const variants=tool.pares.filter(([es,ds])=>es.length<=45&&new Set(ds.map(d=>d.en)).size>1);
const esc=s=>String(s).replaceAll('|','\\|').replaceAll('\n',' ');
write('glosario.md',`# Glosario vigente — sin unificación

Extraído del diccionario de la base, no propuesto como vocabulario nuevo. Las claves y traducciones completas están en evidencia/diccionario-completo.json; correspondencias-es-en.json conserva los pares con textos distintos. Se conservan mayúsculas, puntuación y variantes por contexto. Un término ausente de esta selección no se inventa.

| Castellano literal | Inglés existente | Clave |
|---|---|---|
${termRows.map(d=>`| ${esc(d.es)} | ${esc(d.en)} | \x60${d.clave}\x60 |`).join('\n')}

## Variantes que ya existen para el mismo literal corto

No se elige una ganadora en A. Algunas diferencias son gramaticales o de contexto; otras requieren revisar el significado antes de B.

| Castellano | Valores en en | Claves |
|---|---|---|
${variants.map(([es,ds])=>`| ${esc(es)} | ${[...new Set(ds.map(d=>d.en))].map(esc).join(' / ')} | ${ds.map(d=>'\x60'+d.key+'\x60').join(', ')} |`).join('\n')}

El nombre de la pestaña Preparation, el sello Demo y el estado Not evaluated se conservan según las claves de su superficie. No sustituir Review por Ready ni No evaluado por Failed. El progreso usa Healing para Curación; el contexto usa Earrings para Pendientes en una clave automática: son usos existentes que A registra, no recomendaciones.
`);

write('RECORRIDO.md',`# Reproducción del recorrido de QA

1. En el worktree base, ejecutar \`node scripts/qa_sandbox/sandbox-up.mjs --agente 1 --reset\` sólo sobre una cápsula de QA propia marcada; abrir localhost:13011. Cambiar English en Opciones, recargar. El reset elimina los datos de esa cápsula; no se usó sobre datos del investigador.
2. Crear I18N QA. Demo → buscar 8HFI → Choose receptor. SMILES \`CC(=O)Oc1ccccc1C(=O)O\`. Parámetros Vina, exhaustividad 8, 9 poses, semilla 42. Abrir ayudas y caja. Ejecutar, desplegar Show detail de preflight, cancelar una vez y repetir hasta terminar. Abrir cada pestaña y detalle de pose/estructura, guardar en Moldex y descargar el dossier.
3. Crear I18N Metal/1BN1 e I18N Copia/6SXC con el mismo SMILES y protocolo. Esperar ambas y guardar en Moldex. En Preparación elegir cada caso y abrir los cinco bloques; global no significa cada requisito.
4. Para subir receptores: fixtures \`backend/tests/data/receptores_propios/8hfi_recortado.pdb\` (A), \`8hfi_protonado.pdb\` (B) y el PDBQT del dossier de referencia bajo docs/verificacion/cierre-1-0-2 (C). Usar nombres I18N Raw A/Prepared B/PDBQT C y caja propia. Un PDB con INVALID PDB FOR I18N QA dio el rechazo. No se modificaron los fixtures.
5. En Moldex pulsar Compare en dos corridas de receptores distintos; el modal se abre solo. Desplazar el contenedor hasta la fila del índice histórico. En Evaluation abrir Previous evaluations; filtrar y abrir la corrida cancelada. En Dossier, recorrer preguntas; para ver la fecha guardar una disposición que declare QA en ese caso sintético.
6. Batch: importar evidencia/entradas/cohorte-ejecutable.csv, nombre I18N CSV, receptor 8HFI, mismo protocolo, Check cohort → Save cohort → Run cohort → Evidence/Report. El CSV tiene 4 filas: 3 elegibles, 2 ligandos únicos, 1 duplicado y 1 inválida. Importar cohorte.sdf para comprobar duplicación; ese SDF no se ejecutó.
7. Volver a SAR sólo después de que existan las dos moléculas de lote y **esperar a que termine la consulta**; entonces aparecen 2 análogos y el highlight. Cambiar al visor Web3D y desplazar la leyenda para los tipos de residuo. Para el dibujo, en el caso sin resultado usar Clear Canvas → Benzene → clic en el SVG de Ketcher.
8. Para controles físicos no evaluados, crear I18N Validator con 8T69 de Verified y el SMILES de 4-67 leído del panel congelado de CAL-D-01-R4-2. Esperar el plazo del validador; no tocar ni escribir en el experimento sellado. La corrida de QA tiene identidad nueva y no confirma una medida científica.
9. Recorrer Options/Manage downloads/Legal/Privacy/Licenses, los documentos locales, las cinco secciones de About, ayuda y tutorial. Abrir Molcy, fotos CPU, presentación/configuración, historial vacío; no descargar. Abrir MolChat, proveedor local/Ollama/API, voz deshabilitada, enviar un turno y leer el error sin instalar un motor ni introducir credenciales.
10. Visitar Historial, Comunidad y Registro; los papers siguen en idioma original por diseño. Abrir sólo la vista inicial de certificación: no consentir destino, no financiar ni firmar. El permiso de abrir el modal no fue permiso para transmitir.
11. Los fallos se registran en 19 (400 de subida), 86 (receptor no seleccionable), 87/88 (cola real fallida/recuperada) y 103–105 (backend parado/restaurado). Se verificó el PID/puerto propio antes de detenerlo. Los atributos originales del único case.json puesto readonly se restauraron; no queda ese cambio.

La captura usa body.innerText y atributos de elementos con getClientRects, incluso dentro de contenedores con scroll. El PNG refleja el viewport. El helper reproducible conserva ambos; no cambia CSS ni traduce el DOM para tomar la imagen. La red omite rutas de autenticación y cabeceras de credenciales.
`);

const reportFile=path.join(AUD,'INFORME_FASE_A.md');fs.appendFileSync(reportFile,'\n\n'+fs.readFileSync(path.join(AUD,'ARCHIVO_EVIDENCIA.md'),'utf8'));
console.log(JSON.stringify(summary,null,2));
module.exports={summary,validate};
