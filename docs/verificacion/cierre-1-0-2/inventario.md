# Inventario visible de 1.0.2

Base revisada: `4126c839`. Fuente completa: [registro de cambios](../../versions/1.0.2_cambios.md), incluidos sus apartados históricos y apéndice. Preparado antes de ejecutar la QA. Cada ID es una unidad de comprobación; los resultados y límites se registran en `qa.md`.

| ID | Área | Qué ve o usa el investigador | Commits |
|---|---|---|---|
| I01 | Inicio | Página de presentación con Desde el laboratorio, novedades y acceso a Ciencia. | `6cdace1` |
| I02 | Inicio | Navegación, lanzador y formularios muestran textos en castellano o inglés. | `5d12e25`, `bd70dfd`, `6cdace1` |
| I03 | Inicio | Textos y acciones tienen contraste y foco visibles en ambos temas. | `dd8ee7b` |
| I04 | Inicio | El inicio de sesión de escritorio usa la identidad local y las estadísticas corresponden a la cuenta propia. | `3db6028`, `18f3a03` |
| I05 | Opciones | Acerca de y sus créditos se traducen; el contexto fisiológico se explica sin consultar la red. | `ee622a99` |
| I06 | Evaluación | El campo SMILES se lee y muestra el foco en ambos temas. | `12b0527` |
| I07 | Evaluación | Ejecutar evaluación realiza la comprobación previa y ejecuta sin un botón separado de comprobar. | `e4b7c75b` |
| I08 | Evaluación | Un SMILES inválido se rechaza y no reutiliza silenciosamente la molécula anterior. | `ab762a3` |
| I09 | Evaluación | La cabecera ofrece un único selector Evaluación/Informe. | `59af2ff1` |
| I10 | Evaluación | El resultado abre con un resumen y declara el protocolo y los pesos persistidos. | `217f4bf1`, `91bff58`, `0065dfb` |
| I11 | Evaluación | Vina determina el ranking; XGBoost y CL-GNN conservan su condición exploratoria sin peso. | `47cf6f6`, `18f3a03`, `fef867b` |
| I12 | Evaluación | Los motores que no se ejecutan se deshabilitan con su motivo; ESMFold se puede elegir y existe la plaza de conexión externa. | `34d025c3`, `e44be761`, `18f3a03` |
| I13 | Evaluación | Parámetros de la evaluación reúne muestreo de confórmeros, explicaciones accesibles y etiquetas Experimental. | `1b11e4f7`, `e6d57f2c`, `8a23b35c`, `4cb54c85`, `7c87a2fe` |
| I14 | Evaluación | La estimación reconoce ejecución serial y conserva la semilla y preparación de cada corrida. | `0065dfb`, `164674f` |
| I15 | Evaluación | El panel de selectividad está visible, distingue selección y resultados, y ofrece Todas, Panel por defecto y Ninguna. | `2174e5c`, `ca075925`, `66c4cd4c`, `3e86129e`, `8d92a3ea` |
| I16 | Evaluación | Las anti-dianas se agrupan en demostración y propias, con búsqueda y contador, y el defecto incluye las propias. | `8821ba47`, `563ff6f8` |
| I17 | Evaluación | Guardar selectividad sin una evaluación avisa en el idioma elegido. | `5d12e25` |
| I18 | Evaluación | MolChat reconoce las ocho moléculas corregidas con su estereoquímica declarada. | `18f3a03` |
| I19 | Catálogo de receptores | Los selectores muestran Verificados vacío, Tus receptores y los 381 de Demostración, sin ocultarlos por la sección. | `0341d3a2`, `04a0082a` |
| I20 | Catálogo de receptores | Buscar conserva secciones y familias traducidas, sin repetir la etiqueta en cada tarjeta. | `04a0082a`, `e53e69dd`, `67f7bfc3` |
| I21 | Catálogo de receptores | Dieciséis entradas avisan que las cadenas del sitio podrían ser contactos del cristal. | `0341d3a2`, `04a0082a` |
| I22 | Catálogo de receptores | Intentos publicados muestra CAL-8HFI-01 y su NO_GO, condiciones y cifras, sin promover 8HFI. | `d92a57b0`, `745346f3`, `d17e70b9` |
| I23 | Catálogo de receptores | Un sello verificado exige receta, hash, pose, calibración, protocolo y condiciones; los desconocidos se conservan como códigos. | `6abd7bfe`, `36405e18`, `b149b9a4`, `62b1ebb8` |
| I24 | Catálogo de receptores | Receptores muestran organismo del depósito, disponibilidad y advertencias de la preparación v7. | `20955f1` |
| I25 | Catálogo de receptores | La subida existente admite modo anti-diana y refresca su lista. | `8821ba47` |
| I26 | Historial | Cada corrida muestra fecha y hora y sólo las guardadas reciben la marca Moldex. | `92d79580` |
| I27 | Historial | Se recupera una corrida guardada sin quedar indefinidamente recuperando; conserva su propia atribución. | `ab762a3`, `b296b18c` |
| I28 | Historial | La corrida declara Demostración y su protocolo, sin atribuir el sello de otra corrida. | `c0d60228`, `217f4bf1`, `5abfb6e1` |
| I29 | Moldex | Guardar congela una evaluación propia, permite varias del mismo ligando y habilita Guardar después de otra evaluación. | `92d79580` |
| I30 | Moldex | Ficha, detalle y comparación conservan cifras, pose, PDF e identidad de la corrida guardada. | `92d79580` |
| I31 | Moldex | La CL-GNN se presenta experimental, con dos decimales o ausencia declarada, sin porcentaje de probabilidad. | `bb788f5`, `fef867b` |
| I32 | Moldex | Las barras se superponen al visor sin redimensionarlo; el visor distingue proximidad polar de un puente demostrado. | `d3346a03`, `6cdace1` |
| I33 | Moldex | La ficha dice dónde se guarda y una certificación se refiere a esa corrida, con las limitaciones del POC devnet. | `99b7a8c0`, `92d79580`, `c8401cde` |
| I34 | Moldex | Etiquetas compactas conservan detalles accesibles y el detalle compara receptor y parámetros exactos con el sello. | `3f224b26`, `76139f3f`, `5abfb6e1`, `112a8476` |
| I35 | Lotes | Una cohorte nueva rechaza QuickVina 2; las antiguas con ese nombre siguen siendo legibles. | `1068e8f`, `9dcd479` |
| I36 | Lotes | Importación conserva la etiqueta de duplicados y no publica EF cuando el porcentaje no contiene una molécula. | `c1d3e7c`, `8b2cf31` |
| I37 | Lotes | Crear y ejecutar conserva semilla, receptor y cadenas; los errores del motor se explican sin atribuir todos a conexión. | `e773a0a` |
| I38 | Lotes | Selector, historial, filas y evidencia declaran la sección y el resultado exacto de cada task_id. | `04a0082a`, `c0d60228`, `3f224b26`, `112a8476` |
| I39 | Preparación | La página usa la corrida elegida y conserva sus archivos y relación con el caso. | `74e3220`, `6cdace1`, `010a3215` |
| I40 | Preparación | El informe conserva BLOCKED o REVIEW y no promete transferencia FEP demostrada. | `604b8bb`, `6cdace1` |
| I41 | Preparación | Aguas, metales, cofactores y proteína retirada se enumeran con su distancia al sitio. | `604b8bb`, `ad3d50e` |
| I42 | Preparación | Un cloruro es otro heteroátomo que requiere revisión y no un metal bloqueante. | `a58fe26` |
| I43 | Preparación | Se declaran cadenas laterales truncadas y huecos físicos, con residuos y distancia a la caja. | `ad3d50e`, `d215570` |
| I44 | Preparación | Especie acoplada pide revisión en los motivos químicos de riesgo, incluidas aminas con CF3/CF2 en beta o nitrilo próximo. | `b978495`, `031322b1` |
| I45 | Preparación | El ligando declara tautómero resuelto, multestado requerido o enumeración excedida, sin confundir declarado con resuelto. | `56e8733`, `030c607` |
| I46 | Preparación | Sección del catálogo se traduce y pide revisión para demostración; la identidad prioriza el PDB explícito de la corrida. | `c0d60228`, `108fc7cf`, `a7b98393` |
| I47 | Preparación | El sello se comprueba contra el snapshot de la corrida exacta y distingue diferencia de ausencia de declaración. | `5abfb6e1`, `112a8476` |
| I48 | Dossier y PDF | El expediente declara estructura preparada, especie, decisiones, advertencias y procedencia; desaparecen MM-GBSA, toxicidad y atención GNN ficticias. | `12bd211`, `be1c48d`, `f2cc87a`, `604b8bb`, `18f3a03` |
| I49 | Dossier y PDF | Portada y PDF declaran la sección en los dos idiomas y el alcance del sello de esa corrida. | `d26c5f8a`, `0b72a1b5` |
| I50 | Dossier y PDF | El certificado tiene texto inglés cuando se elige inglés. | `ee622a99` |
| I51 | Molcy | Se elige una corrida guardada exacta o receptor, con tres secciones e intentos publicados. | `d35fddb`, `cc5047e`, `92d79580`, `04a0082a`, `745346f3` |
| I52 | Molcy | La fuente declara demostración, identidad y disponibilidad de receptor, pose, caja y hashes de esa corrida. | `c0d60228`, `cec9fe76`, `112a8476` |
| I53 | Molcy | Resultado, Búsqueda y Ensamble ofrecen sólo evidencia conservada; Búsqueda utiliza traza real de Vina. | `d4e2549b`, `e6513dee`, `9c4240de` |
| I54 | Molcy | Blender y Molecular Nodes se detectan e instalan bajo petición, con motivo cuando faltan. | `7cfb20b`, `0abe491`, `1d54335`, `08af2ed` |
| I55 | Molcy | Formato y generación respetan espacio disponible y la estimación se basa en medidas propias. | `0abe491`, `1d54335`, `010a3215` |
| I56 | Molcy | Panel muestra fotogramas, reproducción, descarga, cancelación, historial, limpieza y procedencia. | `fd516314`, `08af2ed` |
| I57 | Molcy | Se elige carpeta de salida para todos los vídeos o uno. | `99b7a8c0` |
| I58 | Molcy | Resultado y Búsqueda rotulan interacciones; las etiquetas tienen pausas legibles y el final de Resultado da una vuelta completa. | `700ceb58`, `125d94c1`, `a85b2bf2` |
| I59 | Molcy | Fotogramas idénticos se reutilizan y se eliminan destellos al comenzar fundidos. | `8a235d93` |
| I60 | Molcy | Vídeo requiere GPU; Fotos usa Cycles con CPU o GPU, tomas sugeridas, fotograma libre y resoluciones de 720p a 4K. | `8bdc01a6`, `cbaf63c4` |
| I61 | Molcy | Cada foto lleva marca MolDesign y procedencia, y el vídeo conserva el cierre obligatorio. | `8bdc01a6`, `1d54335` |
| I62 | Ciencia | Se consultan experimentos sellados, refutaciones y papers, incluidos siete experimentos que antes carecían de paper. | `afee530`, `c1bb93b`, `6cdace1` |
| I63 | Ciencia | CAL-8HFI-01 aparece como refutación con su paper, condiciones y límites del experimento. | `78d01598` |

## Lectura del registro y límites

- Los estados históricos de catálogo «140/380» y «15 no disponibles» no describen la sección actual: se comprueba I19, manteniendo las advertencias estructurales.
- El vídeo de tres segundos por CPU, sus hilos y estimaciones, y las escenas inicialmente deshabilitadas fueron sustituidos por entradas posteriores: se comprueba la conducta actual de I53 e I60.
- La frase histórica «XGBoost reordena» queda sustituida por su peso cero; I11 comprueba lo persistido.
- Las cifras científicas de FEP/MM-GBSA son resultados de experimentos, no nuevas capacidades ejecutables: sólo se inventaría su acceso mediante Ciencia (I62).
- B-1, B-2, B-3 y B-5 se registraron inicialmente como API que la interfaz todavía no leía; se incluyen sólo sus usos posteriores visibles en I10, I28, I43 e I47.
- El marcador «CPU Molcy, este commit» no identifica por sí solo un commit y describe una conducta sustituida; no se atribuye una función actual a ese marcador.
- Filas sobre hooks, CI, runtime, SBOM, sellado, publicación del código del motor, informes internos y recuentos no especifican cambios visibles en la aplicación y quedan fuera.
- I25 pertenece al frontend base pero su arreglo está reservado a otra sesión: se puede describir un defecto, sin modificar la subida. I33 se inspecciona sin emitir una transacción externa. I54 se inspecciona sin descargar modelos ni Blender.
- Verificados está vacío en la base real; I23, I34 e I47 requieren pruebas de contrato con datos sintéticos claramente separados de la QA real, sin modificar el registro científico.
