# QA de cierre de 1.0.2

Base: `4126c839`. Código final: `44c3a97e715e7dfd4a6a2dacd9c461bae06120ac`, rama `sol/cierre-qa`. Trabajo realizado el 9 de octubre de 2026 en México, 10 de octubre UTC. Esta QA identifica defectos; no declara preparado el instalador.

La cápsula 3 usa Python embebido 3.11.9, Vina 1.2.7 y el export de Next 16.3.8 con CSP de producción. El navegador es Edge 154.0.4258.62, automatizado mediante Playwright sobre la interfaz real. No se interceptan respuestas ni se inyectan resultados. [Manifiestos por export](capsula-manifiesto-cierre.json), [export de modelos](capsula-manifiesto-modelos.json), [arranque de modelos](capsula-modelos-final.log), [manifiesto sobre 44c3a97e](capsula-manifiesto-contraste.json), [arranque sobre 44c3a97e](capsula-contraste-final.log), [manifiesto sobre 44c3a97e](capsula-manifiesto-contraste.json), [arranque sobre 44c3a97e](capsula-contraste-final.log), [acciones de navegación](qa-flows.cjs), [registro de pantallas](qa-matriz.json).

`arbol_limpio=false` incluye archivos de evidencia sin registrar; las fuentes del frontend estaban commiteadas. Cada captura registra el commit y la huella de fuentes del export servido. La matriz combina comprobaciones sobre 66c682ae, 873d2307, 93b004cf y 33be61be; la regresión de contraste de anti-dianas se repite sobre 44c3a97e. No se atribuyen capturas anteriores al commit final. El backend corre desde el worktree; el runtime staged, Rust, WebView2 y el instalador quedan para Claude. Los E2E de CI usan sus fixtures habituales y se informan separados de esta QA real.

## Datos producidos mediante la aplicación

| Objeto | Identidad y condiciones | Resultado observado |
|---|---|---|
| Caso | `350e8d04-4273-41f5-b818-72ab44f3c95e`, QA cierre 8HFI | Una corrida de Vina guardada en el caso y en MolDex. |
| Corrida individual | `27c62c96-a890-47f6-b0c1-095dc6801edb`; molécula `e5655ee8-fa0b-4c1a-aebe-995548b0281b`; entrada `c1ccccc1CNCC(F)(F)F` | Vina top-1 −6,95 kcal/mol, 9 poses; PoseBusters 9/9 bajo configuración `dock`, 22 controles de la primera pose superados. No demuestra actividad. |
| Sistema | 8HFI, cadena A; caja centro (100,281; 100,843; 101,442) Å, tamaño 30×30×30 Å; exhaustividad 8, 9 poses, semilla 42, pH 7,4, un confórmero | Receptor preparado SHA-256 `30e6695403f7b072cbe436daefa3479f9c8e33ee670590e5f04e01d3a7ff0e60`; pesos M4: Vina 1,0000, XGBoost/GNN legacy/CL-GNN 0,0000. Selectividad desactivada expresamente. |
| Especie | Canónico `FC(F)(F)CNCc1ccccc1`; acoplado `FC(F)(F)C[NH2+]Cc1ccccc1` | REVIEW: amina protonada con CF₃ en β. El informe conserva el motivo y no declara resuelta la población de microestados. |
| Preparación | Misma corrida, misma especie | REVIEW, 0 requisitos imprescindibles sin resolver y 9 para revisar. Sección del catálogo pide revisión y no bloquea. Hueco físico LEU191→TYR202, C–N 21,34 Å, a 11,426 Å de la caja, 10 residuos ausentes; 23 aguas retiradas del entorno de la caja. Estos conteos tienen ese alcance espacial. |
| MolDex | Ficha `MDX-8HFI-3502`, misma pareja molecule_id/task_id | Guarda la evaluación, la insignia Demostración y CL-GNN 0,76 experimental. El índice heredado 64,5 lleva su aviso histórico; no se interpreta como probabilidad. |
| Cohorte | `d87d16f5-2454-45db-8041-b3c437e2fc3b`; huella `a59d8bbbbfdb69d50f0ab0a2fc4736cc8f413abac0214e95be2bd21a00513172` | CSV: `CCCCCO,pentanol,0,negative` y `NCc1ccccc1,bencilamina,1,positive`. 2/2 elegibles, 0 inválidas, 0 duplicadas. CCO/CCN se rechazaron antes correctamente por tener menos de cinco átomos pesados. |
| Lote | `dac3ecc8-fdbf-49e6-8f99-1c3affee9873`; 8HFI, semilla 42 | 2/2 completadas, 0 fallidas, 0 no evaluadas; bencilamina −5,45 y pentanol −4,26 kcal/mol. Los dos son controles excluidos de la población de métricas: no corresponde calcular ROC-AUC/EF con ellos. |
| Intento publicado | CAL-8HFI-01, 8HFI | NO_GO, sin promoción a Verificados: ρ 0,13, IC 95 % [−0,16; 0,41], 57 Ki de CHEMBL853189; pose 3/5 semillas a RMSD ≤2 Å, protocolo por defecto 8/9/42. El paper mantiene sus condiciones y aparece entre refutaciones. |

## Defectos, ordenados por gravedad

Las capturas iniciales se conservan; las pantallas de la matriz final muestran la repetición. `Arreglado` significa corregido y comprobado dentro del alcance indicado, no verificado en un instalador.

| ID / gravedad | Dónde y reproducción | Esperado y observado | Evidencia | Estado / propietario |
|---|---|---|---|---|
| B01 · bloquea 1.0.2 | Abrir dossier/PDF en inglés de la corrida 27c62c96. | Ninguna frase castellana en el PDF inglés. Persisten `cadenas A`, origen `crudo` y el párrafo de familia/modelo universal en castellano. En el PDF castellano aparece `Outputs heredados`. | [PDF EN](dossier-en.pdf), [texto EN](dossier-en.txt), [PDF ES](dossier-es.pdf), [texto ES](dossier-es.txt), [páginas renderizadas EN](pdf-en/page-2.png). | Pendiente backend. Incumple el criterio explícito de 2.2.5; no se modifica el generador ni se oculta el texto. |
| F01 · bloquea 1.0.2 | Con Informe abierto en inglés, elegir castellano en Opciones. Repetir en el informe del lote. | Debe mostrarse el documento de la misma corrida en el idioma elegido. Antes conservaba el mismo blob y no emitía otra petición. | [Caso antes](dossier-cambio-idioma.json), [captura](capturas/defecto-dossier-cambio-idioma-es.png), [lote antes](lote-dossier-cambio-idioma.json), [lote captura](capturas/defecto-lote-informe-idioma-es-1024.png), [caso repetido](dossier-idioma-corregido.json), [lote repetido](lote-idioma-corregido.json). | Arreglado `f5eb7ffd` y `66c682ae`: regeneración, cancelación y descarte de respuesta antigua; pruebas recibida/pendiente. |
| F02 · bloquea 1.0.2 | Reiniciar backend conservando perfil; abrir Lotes con la credencial del arranque anterior. | Debe renovar al mismo propietario y recuperar las cohortes/corrida. Antes la lista decía Ninguna todavía y la referencia local se eliminaba por el 401. | [Repetición real: 401→200](cohortes-recuperadas.json), [pantalla recuperada](capturas/cohortes-recuperadas-tras-reinicio.png). El fallo inicial se conserva en el log del arranque 014635 de la cápsula y en el relato de la QA; no se fabricó una captura anterior. | Arreglado `7740184f`: cliente autenticado compartido, aislamiento por propietario, conservación de errores y multipart; 49 pruebas relacionadas. |
| F03 · bloquea 1.0.2 | Abrir Docking y hotspots y leer qué residuos contactó el ligando. | Cada estado debe tener texto. Antes contacto/sin contacto sólo se distinguían por color. | La captura inicial del resultado no muestra todos los hotspots: no hay una captura anterior específica. Matriz final `hotspots` y prueba que distingue medición ausente/contacto ausente. | Arreglado `99c77889`: contactado, sin contacto o contacto no registrado; ausencia de medición nunca se convierte en ausencia de contacto. |
| F10 · bloquea 1.0.2 | Tema claro → Catálogo 1UZJ y Parámetros. | Título y campos legibles. Antes título/fondo tenían contraste 1,004:1 y campos 1,056:1 por combinar fondo oscuro y reglas de texto claro. | [Catálogo antes](capturas/defecto-contraste-catalogo-1uzj-en-light-1024.png), [Parámetros antes](capturas/defecto-contraste-parametros-en-light-1024.png), [medición antes](contraste-parametros-antes-en-light-1024.json), archivos contraste-*-despues-* y matriz final. | Arreglado 9628aa1c; 67 pruebas existentes y mediciones del export en las ocho combinaciones. |
| F13 · bloquea 1.0.2 | Tema claro → resumen, Detalles y ayudas de Parámetros. | Advertencias científicas legibles; antes texto pálido sobre superficie clara. | [Antes](capturas/defecto-avisos-y-barra-en-light-1024.png), matriz resultado/detalles posterior y mediciones de Parámetros. | Arreglado e87223e5; 19 pruebas existentes, se conservan motivos y gravedad. |
| F14 · bloquea 1.0.2 | Caso abierto a 1024 → barra de Parámetros/anteriores/Ejecutar. | Todas las acciones accesibles dentro de la ventana; Ejecutar quedaba cortado. | [Antes](capturas/defecto-avisos-y-barra-en-light-1024.png), ocho archivos acciones-evaluacion-*.json, matriz resultado. | Arreglado c79e4370; 9 pruebas existentes y medidas de los botones reales. |
| F15 · bloquea 1.0.2 | Lotes con corrida restaurada → elegir cohorte → Ver evidencia antes de terminar la apertura. | Esperar la cohorte elegida y conservar su identidad. Antes pedía la corrida anterior y la respuesta podía desaparecer. Una recuperación tardía también podía sustituir la elección explícita. | Dos pruebas con respuestas retenidas en cohortes.test.tsx; repetición real lote-fila sobre 33be61be con task_id 4fdb58ad. El fallo inicial ocurrió al repetir EN/claro/1440; no se fabricó captura anterior. | Arreglado 93b004cf; 46 pruebas, serialización y testigo de elección. |
| F17 · bloquea 1.0.2 | Tema claro → Parámetros → final del selector de anti-dianas. | Aviso sobre pose cristalográfica y reservas legibles; seguían con el tono pálido del tema oscuro. | [Antes](capturas/defecto-antidianas-contraste-en-light-1024.png), matriz parametros-final y contraste de la regresión. | Arreglado 44c3a97e; 26 pruebas existentes de selector y guardianes, regresión sobre export en las ocho combinaciones. |
| F04 · debería entrar | Inglés → Nuevo caso y Detalles; ver tipos de estudio y validación de nombre. | Presentación en inglés conservando IDs. Los cuatro tipos seguían en castellano. | [Antes](capturas/defecto-tipos-caso-en.png), matriz `nuevo-caso` y `detalles`. | Arreglado `5799b3f7`; 16 pruebas de creación e idiomas. |
| F05 · debería entrar | Inglés → Evaluación, Parámetros y panel de anti-dianas. | Receptor elegido, atribución de corrida, sondeo de motores y familias deben seguir el idioma; Eptides debe ser Peptides. | [Parámetros antes](capturas/defecto-parametros-en.png), [anti-dianas antes](capturas/defecto-antidianas-en.png), matriz `parametros`. | Arreglado `2f8b60c1`; 32 pruebas relacionadas, sin excepciones nuevas. |
| F06 · debería entrar | Molcy, selector montado cinco minutos; buscar 1UZJ. | Conservar el aviso de unidad biológica y los intentos. La caché caducada hacía desaparecer datos al volver a renderizar. | [Antes](capturas/molcy-1uzj-aviso-ausente-en.png), pruebas de caducidad con reloj controlado e invalidación, [repetición real de 332.066 ms](ttl-catalogo-real.json), matriz `molcy-1uzj`. | Arreglado `412f19c1`; 17 pruebas relacionadas. En la misma página montada, sin modificar Date.now, a los 332.066 ms sale otra petición GET /targets/ y vuelven el aviso de 1UZJ y CAL-8HFI-01. |
| F07 · debería entrar | Inglés → Ciencia, registro y paper CAL-8HFI-01. | Etiquetas, categorías, capas, reproducibilidad y fechas en inglés. Había etiquetas castellanas. | [Antes](capturas/defecto-ciencia-capaspoblacion-en.png), matriz `ciencia` / `ciencia-paper`. | Arreglado `ccf0d5e5`; dos pruebas con el experimento y paper reales. La prosa científica original se conserva y se declara en la pantalla. |
| F08 · debería entrar | Inglés → Informe → disposición científica. | Guardar disposición científica. El botón decía Save Layout. | Detectado en la UI, sin captura anterior propia del botón. Matriz `dossier` inglés posterior; la clave previa consta en el diff del commit. | Arreglado `48008803`: Save disposition; 13 pruebas existentes relacionadas. |
| F09 · debería entrar | Informe/PDF incrustado a 1024, también Lotes. | Leer la columna Estado sin recorte. Se solicita view=FitH, pero el visor nativo de Edge automatizado conserva al 100 % algunas aperturas del caso; el visor del lote queda gris en las ocho capturas finales. | [Antes](capturas/defecto-dossier-ancho-1024.png), [sondeo con frame nuevo](capturas/sondeo-pdf-frame-nuevo.png), matriz dossier/lote-dossier y PDF del caso descargables renderizados completos. Los sondeos modifican sólo el DOM de diagnóstico, no la fuente ni los datos. | Parcial 7ac99021/66c682ae: parámetros del iframe y pruebas correctos; ajuste y render uniformes del visor nativo NO confirmados. Pendiente comprobar WebView2 en smoke de Claude. No se atribuye el recorte al PDF generado ni se declara cerrado. |
| F11 · debería entrar | Abrir MolChat a 1024 o 1440: el panel tiene ancho fijo. | Razonamiento y Cerrar dentro del panel. Antes Cerrar excedía la ventana a x=1037 en 1024. | [Antes](capturas/defecto-molchat-fuera-1024.png), ocho archivos molchat-controles-*.json y matriz molchat. | Arreglado 873d2307; 7 pruebas existentes, límites reales de controles y cierre por su botón. |
| F12 · debería entrar | Inglés → Detalles del caso. | Las siete preguntas y ayudas en inglés; seguían en castellano. El texto escrito por el investigador se conserva. | Matriz detalles, incluida [repetición EN](capturas/detalles-en-light-1024.png); prueba CaseContextIdiomas. | Arreglado b2b58703; 8 pruebas relacionadas. |
| F16 · debería entrar | Inglés → Gestionar descargas. | Nombre de pesos de ESMFold y descripciones de modelos en inglés; permanecían en castellano. | Causa identificada en el catálogo recibido de la API y el diff; no se conserva una captura anterior específica. Matriz lanzador repetida sobre 33be61be; DownloadCardIdiomas.test.tsx. | Arreglado 33be61be; dos pruebas de idioma, ID de descarga y manifiesto intacto; 21 relacionadas y 15 de guardianes. |
| B02 · debería entrar | Inglés → resumen de evaluación y evidencia del lote. | Motivos y límites del backend en inglés. El párrafo de familia sin modelo/modelo universal y límites del lote siguen en castellano. La presentación de PoseBusters sí está traducida. | Texto de `resultado-en-*` y `lotes-en-*` en las capturas. | Pendiente backend. Son textos recibidos de la API, no claves nuevas del frontend. |
| B03 · debería entrar | Historial de la corrida 27c62c96 frente a la fecha del caso/Preparación. | Instante y zona coherentes. Historial interpreta un ISO sin zona como hora local y desplaza seis horas el instante observado. | Matriz `historial` y `preparacion-especie`; dossier conserva `2026-10-10T00:52:18.887044`, sin zona. | Pendiente backend: el productor serializa fechas UTC sin offset. No se añade Z por conjetura al cliente. |
| B04 · debería entrar | Evidencia del lote: las dos filas declaran active y control_role. | Motivo: no hay población etiquetada elegible después de excluir controles. Dice que la cohorte no declara etiquetas active. | [Lote completo inicial](capturas/lote-completo-en.json), matriz `lotes`; muestra las dos etiquetas y controles. | Pendiente backend. La abstención de ROC-AUC/EF es correcta; el motivo no describe esta cohorte. |
| B05 · puede esperar | PDF inglés, página 7, continuación de la tabla de límites. | Evitar una línea huérfana aislada al comienzo de la página. | [Página 7](pdf-en/page-7.png). | Pendiente backend/ReportLab. Documento legible, sin datos cortados ni solapados. |

## Límites de entorno y alcance

Blender del host se detecta en `E:\blender.exe`, versión 5.2.2. Molecular Nodes falta (`motivo_codigo=falta_addon`) y `renderer.disponible=false`. Se inspeccionan controles y procedencia; no se instalan Blender/addon, no se producen fotos/vídeos y no se comprueba marca, cierre, trazas animadas, cancelación ni recuperación de renders. Las estimaciones visibles no se convierten en mediciones de un render.

No se modifica ni se prueba como cerrada la subida de receptores propios reservada a otra sesión. Verificados permanece vacío: la correspondencia del sello se verifica con fixtures de contrato claramente sintéticos; no se altera el registro real. No se ejecuta ESMFold ni se descargan pesos. No se emite una transacción Solana. La validación de Tauri del shim comprueba existencia de modelos, no sus hashes; los diálogos nativos y la frontera del instalador no quedan verificados aquí.

Las pantallas altas tienen desplazamiento interno o de página; la tabla del lote conserva desplazamiento horizontal propio. Las capturas originales acompañan texto, idioma, tema, dimensiones, URL, commit y huella del export. Los paneles de revisión reúnen cabecera, centro y final sin modificar los originales; no sustituyen el PDF descargable ni sus nueve páginas renderizadas.

## Resultado por fila del inventario

PASS describe el caso y alcance indicado; PARCIAL y NO VERIFICADO no se convierten en aprobaciones mediante pruebas unitarias. Las treinta superficies se revisan en ES/EN × claro/oscuro × 1024×768/1440×900; esto no ejecuta todas las ramas de cada función. El [registro de revisión visual](revision-visual.json) identifica las capturas realmente vistas.

| ID | Resultado | Evidencia y límite |
|---|---|---|
| I01 | PASS | Inicio y acceso a Ciencia; ocho combinaciones. |
| I02 | PASS con límites | Navegación y modelos traducidos tras F16; motivos recibidos de la API siguen con B02. |
| I03 | PASS parcial | Corregidos F10/F13/F14/F17. No se afirma una auditoría WCAG completa de todo control. |
| I04 | PASS parcial | Identidad local y estadísticas de los tres cálculos propios; aislamiento entre cuentas cubierto en CI, no con dos investigadores reales. |
| I05 | PASS parcial | Acerca de en ocho combinaciones; panel y créditos visibles. No se abrieron todas las ayudas fisiológicas. |
| I06 | PASS | SMILES de la corrida legible y editable en los dos temas. |
| I07 | PASS | Preflight y Vina reales mediante Ejecutar; sin botón separado. |
| I08 | NO VERIFICADO en vivo | Sondeo incompleto en un segundo caso en borrador: se escribió un SMILES malformado, pero no se completó la selección de receptor ni el envío. No se afirma probado el rechazo de evaluación; el rechazo por menos de cinco átomos pesados en importación es otro control. |
| I09 | PASS | Selector único Evaluación/Informe en el caso. |
| I10 | PASS con B02 | Resumen, protocolo 8/9/42 y pesos reales; persisten motivos castellanos enviados por API. |
| I11 | PASS | Pesos de Vina 1 y modelos exploratorios 0 en la corrida, señal CL-GNN experimental. |
| I12 | PARCIAL | Vina ejecutado; ESMFold visible, no ejecutado. API externa sin configurar; ningún motor adicional se habilita. |
| I13 | PASS visual | Parámetros, muestreo y etiquetas Experimental; no se ejecutó una evaluación ADMET. |
| I14 | PARCIAL | Estimación serial visible y semilla/preparación persistidas; no es un benchmark de tiempo. |
| I15 | PASS visual | Todas/por defecto/Ninguna visibles; corrida real ejecutada expresamente sin selectividad. |
| I16 | PARCIAL | Secciones, familias y búsqueda; no hay anti-dianas propias ni corrida contra ellas. |
| I17 | NO VERIFICADO en vivo | No se disparó Guardar selectividad sin evaluación. |
| I18 | NO VERIFICADO | UI MolChat en ocho combinaciones; llama.cpp no detectado, sin descargar LLM ni probar las ocho estructuras con el modelo. |
| I19 | PASS | Verificados vacío, Tus receptores vacío y Demostración 381; Catálogo y Molcy. |
| I20 | PASS | Búsqueda 8HFI/1UZJ conserva secciones y familias. |
| I21 | PASS parcial | Aviso real de 1UZJ inspeccionado; no se recorrieron individualmente los otros quince avisos. |
| I22 | PASS | CAL-8HFI-01, NO_GO, cifras/condiciones y ninguna promoción. |
| I23 | CONTRATO | Registro real vacío; sello sólo con fixtures sintéticos de la suite. |
| I24 | PASS parcial | Organismo, preparación y disponibilidad de 8HFI/1UZJ; no todos los receptores. |
| I25 | FUERA DE ALCANCE | Subida reservada a otra sesión; no modificada ni declarada cerrada. |
| I26 | PASS con B03 | Tres corridas y sólo la guardada marcada Moldex; serialización de fecha sin zona pendiente. |
| I27 | PARCIAL | Caso/corrida recuperados tras recargas y reinicio; no todas las variantes de recuperación histórica. |
| I28 | PASS | Demostración, atribución y protocolo de la corrida exacta. |
| I29 | PARCIAL | Una corrida guardada real; no dos evaluaciones del mismo ligando guardadas. |
| I30 | PARCIAL | Ficha, pose, detalle y PDF; no comparación entre dos fichas reales. |
| I31 | PASS | 0,76 experimental, sin peso ni porcentaje de probabilidad. |
| I32 | PASS visual | Barras y proximidad polar visibles en ocho combinaciones; no medición exhaustiva de cada modo de visor. |
| I33 | PARCIAL | Ubicación y límites del registro visibles; no se emite certificación Solana. |
| I34 | CONTRATO | Detalle accesible observado en Demostración; Verificados vacío, igualdad/diferencia/ausencia sólo en fixtures. |
| I35 | PARCIAL | QuickVina 2 no disponible para una cohorte nueva; no hay una cohorte antigua real de ese motor. |
| I36 | PARCIAL | CSV válido de dos controles; población de métricas vacía y abstención. Sin duplicados ni caso real del umbral EF. |
| I37 | PASS parcial | 2/2 Vina, cadena A y semilla 42; no se indujeron fallos o cancelación del motor. |
| I38 | PASS | Fila real 4fdb58ad, sección y evidencia de la corrida; recuperación F02/F15 repetida. |
| I39 | PASS | Preparación conserva task_id y archivos de la corrida elegida. |
| I40 | PASS | REVIEW, nueve reservas y cero imprescindibles sin resolver; ninguna promesa FEP. |
| I41 | PARCIAL | Aguas retiradas y distancias declaradas; esta estructura no demuestra los casos positivos de metal/cofactor. |
| I42 | NO VERIFICADO positivo | Sin cloruro retenido en esta corrida; no se produjo un caso positivo. |
| I43 | PASS parcial | Hueco físico LEU191→TYR202 con distancia; no caso positivo de cadena lateral truncada. |
| I44 | PASS | Amina con CF3 en beta, especie protonada y motivo de REVIEW. |
| I45 | PARCIAL | Estado enumerado de esta molécula; no corrida real multestado o excediendo 32. |
| I46 | PASS | Demostración REVIEW no bloqueante; 8HFI explícito y consistente. |
| I47 | CONTRATO | Verificados vacío; matriz de sello exacto cubierta con fixtures. |
| I48 | PASS | PDF/ZIP reales con estructura, especie, procedencia y límites; no señales ficticias. |
| I49 | DEFECTO B01/F09 parcial | Portada muestra sección en ES/EN; documentos mezclan frases y ajuste nativo no uniforme. |
| I50 | NO VERIFICADO en vivo | No se emite certificado devnet; pruebas del visor por idioma separadas. |
| I51 | PASS | Selector MolDex/receptor con tres secciones e intento, misma corrida guardada. |
| I52 | PASS | Demostración, fuente y disponibilidad declaradas; no render. |
| I53 | PARCIAL | Controles de escenas según evidencia; no se verifica animación de traza/ensamble. |
| I54 | PASS parcial | Blender 5.2.2 del host detectado; falta addon Molecular Nodes. No instalación. |
| I55 | PARCIAL | Formato/estimación visibles; no contraste con un render producido. |
| I56 | NO VERIFICADO render | Sin jobs reales: reproducción, descarga, cancelación y limpieza de renders pendientes. |
| I57 | NO VERIFICADO nativo | Selector de carpeta no emulado en la cápsula. |
| I58 | NO VERIFICADO render | Rótulos, pausas y vuelta final pendientes por falta de addon. |
| I59 | NO VERIFICADO render | Reutilización de fotogramas/fundidos no medida. |
| I60 | PARCIAL | Modos y límites visibles; no foto CPU/GPU ni vídeo GPU real. |
| I61 | NO VERIFICADO render | No se comprueban marca de foto ni cierre de vídeo sin archivos producidos. |
| I62 | PASS parcial | Registro real: 168 sellados y papers accesibles; no se abrieron los siete papers incorporados. |
| I63 | PASS | CAL-8HFI-01 como refutación, paper con n=57 y condiciones 8/9/42. |
