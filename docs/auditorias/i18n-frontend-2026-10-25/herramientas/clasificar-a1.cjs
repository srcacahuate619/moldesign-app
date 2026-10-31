const fs=require('node:fs'),path=require('node:path');
const a=require('./cerrar-fase-a.cjs');
const review=require('./revisar-a1.cjs');
const {rows,entries,tool,ROOT,AUD}=a;
const byLocation=new Map();
for(const e of entries)for(const file of [e.archivo,...e.archivos||[]]){const list=byLocation.get(file)||[];list.push(e);byLocation.set(file,list);}
const aliasFiles=new Map(Object.entries({
 'lib/targetGrouping.ts':'TargetSelectorModal.tsx:411 usa t(family); cada nombre del mapa tiene alias vigente.',
 'components/SupportPanel.tsx':'SupportPanel.tsx:102/120 llama t(item.q/a); alias del módulo paneles.',
 'components/inicio/TutorialMolcy.tsx':'TutorialMolcy usa claves de inicio para etiquetas y el asset en-*.webp para English; no se reescribieron imágenes.',
 'components/interfaces/pro/ProXaiTab.tsx':'Las explicaciones fijas y radar pasan por t(); alias en generadas/remate. Las dos plantillas interpoladas tienen entradas propias.',
 'components/interfaces/pro/ProAlertsTab.tsx':'t(estilo.badge/pie). Los mensajes derivados en bruto se inventarían por separado.',
 'components/interfaces/pro/ProAnalysisTabs.tsx':'PHYSICAL_STATUS.label pasa por t() o presentación de controles. Las claves/códigos del contrato no son texto humano.',
 'components/interfaces/pro/Web3DViewer.tsx':'Las descripciones de AA_INFO pasan por t(selectedInfo.desc). Nombres/tipos/cadena e interacciones sin alias tienen entradas propias.',
 'lib/softwareCatalog.ts':'AboutModal CARD_TRANSLATION_KEYS y LegalModal TEXTOS_DE_LA_FILA sustituyen descripción/rol/versión. Availability/kind se traducen por clave. Crédito Molcy sin override inventariado.',
 'lib/moldex.ts':'constante de alcance del memo se usa con mx_alcance_registro; otros valores son claves de UI, contratos o identidad persistida. Motivos crudos tienen entradas propias.',
 'lib/registro.ts':'RegistroCientifico usa t(estilo.nombre/corto); fechaLegible recibe locale. cargarIndice tiene una entrada de error propia.',
 'lib/preflight.ts':'describeRunBlock recibe t en sus tres consumidores CaseEvaluationRunner:666/1170/1206. localizeReceptorLabel convierte el formato conocido antes de mostrarlo; gridLabel y error HTTP inventariados.',
 'lib/admetEtiquetas.ts':'Casos observados por lectura: todos los rótulos devueltos son entradas del inventario; los case extreme/high/medium/low son códigos.',
 'lib/avisosDeModulos.ts':'Emite titleKey/messageKey; DownloadNotifications traduce al mostrar. Claves y estados de transición no son mensajes.',
 'lib/activityNotifications.ts':'Notificaciones actuales por titleKey/messageKey; cadenas source/outcome/module son identificadores. Texto legacy persistido es dato, no un literal nuevo de este módulo.',
 'lib/molcyJobActivity.ts':'Emite titleKey/messageKey, no frases castellanas; estado en_cola/renderizando/completo pertenece al protocolo.',
 'lib/cases/types.ts':'Estados/tipos/vistas se presentan mediante *_KEYS y t(); preguntas/hints se localizan en CaseContextPanel. Origin labels no tienen consumidor de presentación actual; relaciones de protocolo/inputs son enums.',
 'components/cases/CaseContextPanel.tsx':'SEVERITY_LABEL.warning tiene alias; info no y se inventaría. JSX de ids/radio/contratos no es texto. SaveIndicator y resumen tienen entradas propias.',
 'components/cases/caseContextLabels.ts':'Los tres consumidores CaseDetailsDrawer y CaseWorkspace pasan t; los fallbacks sin traductor no se usan en producto.',
 'lib/selectividadMargen.ts':'ProSelectivityPanel.tsx:768 resuelve por claveDeVeredicto antes de pintar; las frases canónicas/legacy son tabla de correspondencia, no una fuga por sí mismas.',
 'components/science/ProtocoloM5Zn.tsx':'PipelineDeLaCorrida.tsx:24 sólo monta este componente cuando protocoloRegistrado es M5-Zn; 1BN1 real es M4 (116). La tabla española se conserva en pistas, sin estado actual demostrado.',
}));
const bilingualFiles=new Map(Object.entries({
 'lib/sitioDelReceptor.ts':'describirSitio/describirHotspots/avisoDeEvidencia/explicarSitio desvían a rama inglesa. ChipsDelSitio pasa idioma y DetalleDelSitio pasa locale (línea 123); enumerar/calidad españoles sólo se usan desde explicarSitio es.',
 'lib/evaluationEvidence.ts':'deriveEvaluationEvidence termina en localizeEvaluationEvidence; único consumidor EvaluationEvidencePanel:128 pasa t. El antiguo EvaluationReadinessPanel no se monta desde rutas actuales.',
 'lib/resultFieldPresentation.ts':'Filas [clave, grupo, es, en, aliases]; resultFieldPresentation devuelve ambas columnas. ProXai:72 y RunDataExplorer eligen en cuando locale=en; aliases sirven para búsqueda.',
 'app/preparacion/page.tsx':'COPY/GATES/REQUISITOS tienen columnas es/en y se eligen por locale; los valores humanos backend de requisitos se inventarían como backend.',
 'components/science/RespaldoDelReceptor.tsx':'nivelLegible/rhoSinMedir eligen columna idioma. RespaldoDelReceptor usa locale; el detalle calibracion.resumen procede del backend.',
 'app/login/LoginForm.tsx':'La tabla multilingüe elige COPY[locale]. pt/fr/de/it no son idiomas habilitados por MVP_LOCALES. usuario123 es ejemplo de identificador, no una frase para traducir.',
}));
const nonVisibleFiles=new Map(Object.entries({
 'lib/errors.ts':'friendlyError/friendlyStageError no tienen importación ni consumidor en producto (rg sólo encuentra definiciones y llamada interna).',
 'lib/pipelineDefinitions.ts':'ProEvaluation usa localizePipelineText para textos fijos y filtra activeStages. No se pinta la definición completa. Las notas sin datos se ocultan y las presentes se localizan por el mapa revisado.',
 'lib/procedenciaDeSenales.ts':'describirEtapa produce texto intermedio: ProEvaluation localiza el sub de Vina y filtra etapas sin productor/resultado. No se inventaría la plantilla cruda como si estuviese en pantalla.',
 'lib/preparacion.ts':'Tipos/estados/códigos del contrato y clave de requisito, no nuevas frases humanas; valorVisible devuelve datos backend, inventariados por su endpoint.',
 'lib/elevacion.ts':'SVG, atributos data-cambio/data-detector, claves de caché y estados técnicos; las etiquetas son elementos/química. Intl sin locale tiene entrada de formato propia.',
 'lib/seleccionDeResiduos.ts':'Comentarios y estados del contrato de selección, no texto humano nuevo que se imprima.',
 'lib/catalogoDeReceptores.ts':'Cache, identidad y mensajes de documentación; no hay mensajes humanos nuevos fuera de comentarios.',
 'lib/antiDianas.ts':'Identificadores/estados del catálogo; la categoría y los motivos humanos se reciben del endpoint, no se componen aquí.',
 'lib/avisos.ts':'Severidades y códigos de contrato. El mensaje humano conserva el origen del backend; no se traduce una cadena por subcadenas.',
 'lib/seccionCatalogo.ts':'Secciones, campos de sello y condiciones son códigos; componentes usan cat_* para texto humano. Nombres de experimento y decisión son datos.',
 'lib/cases/schema.ts':'Validación defensiva; Rust cases.rs:697/1475 valida el manifiesto entero antes de recordFrom. sanitizeFolderName se captura en CreateCaseDialog y muestra ca_nombre_carpeta_invalido (captura 111). No se demostró una fuga de estos mensajes TS en el camino de escritorio; el navegador legacy es un ámbito distinto.',
 'lib/cases/browserCaseRepository.ts':'crearRepositorioDeCasos usa este repositorio sólo sin Tauri. La cápsula emula Tauri y el instalador usa carpetas. Mensajes sólo de navegador legacy quedan fuera del total de escritorio.',
 'lib/cases/tauriCaseRepository.ts':'storageLabel se localiza mediante uiLabels. Defensas de dueño duplican la autorización Rust, que se ejecuta primero. Los errores IPC reales se inventarían como Rust; no se atribuye su mensaje a este adaptador.',
 'lib/cases/factory.ts':'Identidad vacía contradice la precondición autenticada del proveedor; error de programación, no estado de usuario demostrado.',
 'lib/cases/saveQueue.ts':'No genera frases para mostrar; propaga la causa. El sufijo visible lo añade CaseContext y está inventariado.',
 'lib/desktopAuth.ts':'El texto del secreto ausente se registra en console.error por la inicialización de auth; la pantalla usa su aviso por clave. No se demostró un consumidor que pinte el mensaje crudo.',
 'lib/openExternal.ts':'ExternalLink registra la causa detallada en consola y muestra un mensaje propio, inventariado. Las rutas/esquemas inválidos no son entrada de usuario en esos enlaces fijos.',
 'app/layout.tsx':'Metadata title/description estática castellana. Se conserva en observaciones; el título fijo del contenedor nativo no se midió. No se presenta como una fuga de innerText del escritorio.',
 'app/laboratorio/evaluacion/page.tsx':'Ruta de muestra controlada para pruebas de interfaz; receptor/narrativa son datos de fixture y el aviso se declara como tal. No se contó como evidencia científica ni como fuga de producción por navegación normal.',
}));
const manual=new Map();
function note(file,lines,reason){for(const n of lines)manual.set(file+':'+n,reason);}
note('app/evaluation/batch/page.tsx',[601,844,913,1025],'Id de paso/sección o source_name aportado en la cohorte; los nombres de archivo humanos tienen entrada propia.');
note('app/evaluation/batch/page.tsx',[654],'CSV de ejemplo: nombres de molécula y campos del formato, datos expresamente excluidos del encargo.');
note('app/molcy/page.tsx',[555],'Id html de la pestaña estudio; su rótulo se obtiene mediante clave cy_.');
note('components/ai/BloqueDeEvidencia.tsx',[106,125],'sin clasificar sólo se asigna con verificada=false; el JSX 172 muestra la clave auto_280145ccad5c para esa rama.');
note('components/ai/BloqueDeEvidencia.tsx',[163],'Propiedad CSS borderLeft, no texto.');
note('components/ai/MarkdownRenderer.tsx',[23],'Sustitución técnica de esquemas Markdown bloqueados, no un mensaje de interfaz; la prosa procede del LLM.');
note('components/cases/CaseSidebarShell.tsx',[31,32],'Clave de localStorage del ancho/estado del sidebar.');
note('components/cases/CaseWorkspace.tsx',[610],'Nombre propuesto del caso derivado de carpeta, con fallback sólo si el basename falta; nombres de caso son datos fuera del alcance.');
note('components/CertificationModal.tsx',[271],'flowLabel default no se usa: todas las fases que montan el spinner tienen su case traducido (poc-funding, poc-signing, web3-prepare, web3-signing, verifying).');
note('components/DownloadNotifications.tsx',[28,355,368],'Clave de persistencia o clases CSS de la animación.');
note('components/elevacion/MiniaturaElevable.tsx',[197],'viewBox SVG numérico; lienzo es nombre de variable.');
note('components/elevacion/VisorElevacionEditor.tsx',[85,329,363],'Valor de vista escrita/acoplada que selecciona una clave o viewBox SVG numérico; no es el rótulo humano de la vista.');
note('components/evaluation/CaseEvaluationRunner.tsx',[879,897],'Parámetros de withRecoveryDeadline, parte del mensaje compuesto inventariado en la línea 112; no se cuentan dos veces los fragmentos.');
note('components/evaluation/CaseEvaluationRunner.tsx',[1465,1467,1469,1470],'Enum de origen del receptor; el componente de presentación utiliza la clave de origen.');
note('components/evaluation/CaseEvaluationRunner.tsx',[1576],'Subcadena para clasificar un rechazo de autenticación y sustituirlo por una clave; no se muestra ese literal.');
note('components/interfaces/pro/AdvancedMolstarViewer.tsx',[123,247,248],'Marcador SDF/aliases de identificación de la estructura candidata; no es un rótulo traducible sin separar identidad y presentación. Los dataLabel humanos sí se inventarían.');
note('components/interfaces/pro/EstadoDelLigando.tsx',[80,81,101,104,143,173],'Código de criterio, fórmula química o interpolación de una traducción ya resuelta. Los cuatro rótulos de carga crudos tienen entradas propias.');
note('components/interfaces/pro/OrbeDeEvaluacion.tsx',[20],'Transform CSS del punto del anillo.');
note('components/interfaces/pro/PipelineTimeline.tsx',[18,33],'Etiqueta fija que pasa por t(s.label); alias vigente. English medido en la captura 32 (PROPERTIES, HEALING). Propiedades / ADMET sin alias tiene una entrada aparte.');
note('components/interfaces/pro/ProEvaluation.tsx',[620],'Precondición del modal MM-GBSA, que no se ofrece para ejecutar en la build actual; no se demostró un estado actual de usuario que la alcance.');
note('components/interfaces/pro/ProEvaluation.tsx',[1066],'Identificador de clase/etiqueta, no texto de interfaz.');
note('components/interfaces/pro/ProEvaluation.tsx',[1453,1462],'Campos de DOT fuera del contrato activo: XGB con peso cero se filtra; SMARTS requiere una salida UMS y una definición de familia que la muestre. No se demostró en las corridas actuales; no se afirma que estén traducidos.');
note('components/interfaces/pro/ProParametersTab.tsx',[331],'La ruta de resultados usa ResultPropertiesPanel; la fuente equivalente de ese panel sí está inventariada. Esta copia legacy queda como pista.');
note('components/interfaces/pro/ProSelectivityPanel.tsx',[71,73,74,75],'Ficha CYP3A4 no seleccionable en el panel por defecto actual. Sus textos se conservan como pista; no se inventa un estado observado con esa ficha.');
note('components/interfaces/pro/ProSelectivityPanel.tsx',[241,247,249,356,403],'Estado de persistencia fallido/guardado; el JSX elige una clave pr_sel_ por estado.');
note('components/interfaces/pro/ProSelectivityPanel.tsx',[560,643],'pdb_id del registro on_target legacy, identificador persistido. No se traduce el formato ni se cambia su identidad.');
note('components/interfaces/pro/ReceptorVariantModal.tsx',[36],'Nombre propuesto editable del receptor; los nombres de receptor son datos fuera del alcance.');
note('components/interfaces/pro/RunDataExplorer.tsx',[14,48],'Fallback de basename de archivo y schema del JSON consultable; los campos/enums del formato se conservan. Nombre de descarga inventariado en 51.');
note('components/interfaces/pro/TargetSelectorModal.tsx',[453,455,542],'Puntuación junto a un t() ya traducido, motivo del backend o clases CSS. El motivo conserva el origen backend.');
note('components/molcy/PhotoStudio.tsx',[298],'Duración numérica en min/s, unidades iguales; no es texto castellano.');
note('components/molcy/PresentationControls.tsx',[30,33,36],'Keys del contrato presentacion (residuos, etiquetas, contactos, muestra_anterior, referencia). Rótulos mediante cy_.');
note('components/MoldexCard.tsx',[58],'Comparación con nombre de molécula legacy Ligando; no es un rótulo pintado aquí. Registrar el acoplamiento por texto en observaciones.');
note('components/MolecularComparison.tsx',[75,76],'Identificador MDX y regla para nombres de molécula, datos excluidos; los encabezados comparativos sí tienen entradas.');
note('components/Navigation.tsx',[21,91],'Id inicio del menú que elige una clave para el enlace.');
note('components/PaqueteMolcyCard.tsx',[41],'Id de navegación a descargas, no texto.');
note('components/registro/RegistroCientifico.tsx',[517,676],'Comando reproducible que se muestra literalmente y código de categoría de un experimento; no traducir rutas ni códigos.');
note('components/science/SeccionDelCatalogo.tsx',[19],'Construye la clave cat_*_texto; t() la resuelve después.');
note('lib/api.ts',[116],'resolveTargetName no tiene consumidores de producción (rg sólo encuentra la definición).');
note('lib/api.ts',[687],'Guarda de entorno; TraspasoInvitado se ofrece sólo en escritorio. No hay un estado actual desktop que cumpla !isDesktopRuntime.');
note('lib/api.ts',[998,1001],'Nombres de parámetros URL del contrato (rotables, ligandos).');
note('lib/auth.tsx',[98],'Etiquetas castellanas de campo que forman parte de los mensajes de validación ya inventariados en 99–103.');
note('lib/cohorts.ts',[262],'Valor de sorted_by que la API requiere exactamente: afinidad_vina_observada.');
note('lib/molcy.ts',[199,262,263,337,364,400,420,430,432],'Parámetro URL, cabecera HTTP, propiedad o estado del contrato. El componente traduce por clave cy_ al presentar.');
note('lib/molcy.ts',[261,267],'Error de fotograma capturado y absorbido por app/molcy/page.tsx:323; no se propaga a la ventana. Los errores de abrir una foto sí se inventarían.');
note('lib/reporteDeIA.ts',[66],'Nombre propio MolDesign seguido de versión, igual en inglés. El marcador de recorte es otra entrada.');
note('lib/resultFieldKeys.ts',[66],'Nombre de campo serializado protocolo; no traducir el JSON.');
note('lib/tauri.ts',[123,124,133,140],'Diagnóstico de tauriBridgeSmokeTest; rg no encuentra consumidor de UI ni de producción.');
note('lib/traspaso.ts',[40],'Id persistido de la identidad invitada.');
note('lib/traspaso.ts',[213],'Guarda de capability: browserCaseRepository:184 y tauriCaseRepository:265 implementan adoptCase. No hay una operación normal que alcance este throw con los repositorios actuales.');
note('context/AIContext.tsx',[183],'description del proveedor fallback no tiene consumidor de presentación (rg provider.description/selectedProvider.description sin resultados); no confundir con estado, que sí se muestra.');
note('context/AIContext.tsx',[770,796],'Motivo devuelto al llamador cuando no se envía nada; ChatInput sólo restaura el borrador y no pinta ese motivo.');
note('context/AIContext.tsx',[831],'Error por violar la jerarquía de providers, sólo alcanzable por un fallo de programación.');
note('context/CaseContext.tsx',[225,1077],'Precondición del provider/hook; el layout actual siempre lo monta con sesión. Error de programación, no interacción de usuario.');
note('context/CaseContext.tsx',[747,789,832],'Guarda de capability ausente; el repositorio de carpetas desktop implementa la operación. Sólo navegador legacy/otro repositorio podría alcanzarla.');
note('context/DownloadProvider.tsx',[51,53],'EngineStatusBar devuelve null para idle y ready; el rótulo no se pinta.');
note('context/DownloadProvider.tsx',[149],'Marcador YA_EN_CURSO usado para reconocer la operación nativa; no se imprime.');
note('context/DownloadProvider.tsx',[204,230],'Notas de procedencia del manifiesto sin consumidor de UI (rg revision_nota/.notes en app y components).');
note('context/DownloadProvider.tsx',[209,219,221],'nombreDelModulo/descripcionDelModulo seleccionan las claves por id esmfold-weights/llm-qwen15 antes de pintar.');
note('context/DownloadProvider.tsx',[365,391],'La causa se consume en startDownload y sólo modifica models[id]=error/missing. La campana muestra titleKey/messageKey, sin la frase del throw.');
function classify(r){
 const loc='frontend/'+r.archivo+':'+r.linea;
 const es=(byLocation.get(loc)||[]).filter(e=>{const source=e.texto_fuente||e.texto;return source===r.texto||(e.archivos&&source.includes(r.texto))||e.texto===r.texto;});
 if(es.length)return {decision:'inventariado',ids:es.map(e=>e.id),razon:es.map(e=>e.consumidor).filter(Boolean).join(' | ')};
 const repeated=entries.filter(e=>e.archivo.startsWith('frontend/'+r.archivo+':')&&(e.texto_fuente||e.texto)===r.texto);
 if(repeated.length)return {decision:'inventariado',ids:repeated.map(e=>e.id),razon:'Mismo literal en otra rama del mismo archivo; una entrada por mensaje, sin duplicar el recuento.'};
 const manualReason=manual.get(r.archivo+':'+r.linea);if(manualReason)return {decision:'excluido',razon:manualReason};
 if(!review.reachable.has(r.archivo))return {decision:'excluido',razon:'Sin importación desde las rutas app según el grafo conservado; se comprobaron errors.ts y paneles legacy con rg.'};
 if(r.motivo&&['literal de tipo','identificador o importación','sólo consola','diccionario histórico','comparación o case: contrato/lógica, no salida por sí misma'].includes(r.motivo))return {decision:'excluido',razon:r.motivo};
 if(r.argumento_t===0&&(r.clave_existente!==null||r.dict.some(x=>x.archivo!=='context/LanguageContext.tsx')))return {decision:'excluido',razon:'Clave existente o alias exacto creado por traducciones/index.ts:84; se localiza antes de pintar.'};
 if(tool.claves[r.texto]!==undefined)return {decision:'excluido',razon:'Clave de traducción usada en una tabla/variable y resuelta por el consumidor, no es el rótulo castellano.'};
 if(nonVisibleFiles.has(r.archivo))return {decision:'excluido',razon:nonVisibleFiles.get(r.archivo)};
 if(bilingualFiles.has(r.archivo))return {decision:'excluido',razon:bilingualFiles.get(r.archivo)};
 if(aliasFiles.has(r.archivo)&&r.dict.length)return {decision:'excluido',razon:aliasFiles.get(r.archivo)};
 if(r.archivo==='lib/pipelineStream.ts')return {decision:'excluido',razon:r.linea===143?'El throw de stream sin cuerpo se captura dentro de subscribeToPipelineEvents y sólo se registra en consola.':'Los mensajes del orb sólo se muestran si el consumidor activo los monta; no se demostró ese estado de error/skip en el pipeline Vina actual. Se conserva como pista en el informe.'};
 if(r.contexto?.some(c=>c.tipo==='columna'&&c.idioma.replaceAll('"','').replaceAll("'",'')==='es'))return {decision:'excluido',razon:'Columna es de tabla de presentación; el selector de idioma de la superficie elige en. No basta la tilde de la columna para una fuga.'};
 const text=r.texto;
 if(/(?:cursor-|flex-|font-|text-|divide-|border-|px-|py-|\[var\(|<line|<circle|<rect|<g |<svg|font-family=|stroke=|#[0-9a-fA-F]{3,8})/.test(text))return {decision:'excluido',razon:'CSS/SVG técnico; no es texto humano visible ni atributo accesible.'};
 if(/^(?:auto_|[a-z]{1,5}_(?:[a-z_]|\$\{))/.test(text)||/^(?:[a-z_]+:|[/@]|data-)/.test(text))return {decision:'excluido',razon:'Clave de traducción/contrato, id, ruta o nombre de evento; el componente no lo usa como frase humana.'};
 if(/^[a-z0-9_]+(?:-[a-z0-9_]+)+$/.test(text))return {decision:'excluido',razon:'Identificador técnico de elemento/estado/artefacto; revisar descarga aparte: los nombres propuestos humanos sí tienen entrada cuando corresponden.'};
 if(/^\$\{/.test(text)&&!tool.spanish(text.replace(/\$\{[^}]*\}/g,'')))return {decision:'excluido',razon:'Interpolación de datos ya traducidos/identificadores; la coincidencia léxica procede del nombre de variable.'};
 if(/^(?:radio|motor|entrada|predeterminada|lenta|definir|comprobar|guardar|ejecutar|evidencia|informe|todas|foto|vista|fotos|tomas|resultado|ensamble|biblioteca|sin_datos|verificado|propios|cargando|listo|ninguna|desconocida|cancelar|reanudar|abrir|moviendo|hecho|pendiente|lanzada|cancelada|ya_no_pendiente|en_cola|renderizando|izquierda|neutro|revisar|incompleto|executable|existente|complejo|invitado|sí|no|Descargas|Español|es)$/.test(text))return {decision:'excluido',razon:'Valor de estado/id/contrato o dato; no es el texto que se muestra. El consumidor de la superficie usa su clave correspondiente.'};
 if(aliasFiles.has(r.archivo))return {decision:'excluido',razon:aliasFiles.get(r.archivo)};
 return {decision:'revisar_restante',razon:'Revisión adicional requerida antes de excluir; no se cuenta como hallazgo confirmado.'};
}
const ledger=rows.map(r=>({archivo:'frontend/'+r.archivo,linea:r.linea,texto:r.texto,...classify(r)}));
const remaining=ledger.filter(r=>r.decision==='revisar_restante');
const groups={};for(const r of remaining)groups[r.archivo]=(groups[r.archivo]||0)+1;
if(require.main===module){console.log(JSON.stringify({total:ledger.length,inventariados:ledger.filter(r=>r.decision==='inventariado').length,restantes:remaining.length,archivos:groups},null,2));}
module.exports={...a,ledger,remaining};
