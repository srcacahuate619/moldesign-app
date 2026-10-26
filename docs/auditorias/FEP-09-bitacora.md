# FEP-09: bitácora

## Hito 0 — 2026-10-11, reconocimiento

Worktree `D:\moldesign-build\.worktrees\fep09`, rama
`sol/fep-09-sensibilidad`, base `f183e0af`. Clon de OpenFF verificado en
`fd88824f9114244f95a14b485e6d6c96c1de716d`. Python de análisis 3.14.3,
Python embebido 3.11.9; RDKit 2025.09.6 en ambos. Sin medidas del auditor.

Decisiones autónomas: camino B (`respetar`), un ligando por diana (primer
registro legible), 15 dianas con los dos archivos, tres preparaciones
independientes de línea base, corte de tres residuos, caja fija de 20 Å
centrada en los átomos pesados del primer ligando, sin elegir por resultados.
Inventario y defectos se generan por geometría directa y RDKit, sin importar
el producto. El inventario se podrá regenerar antes del prerregistro; después
su hash y el commit fijarán la lista.

Los huecos lejanos tienen revisión legítima declarada: se conservarán como
control espacial con ese cambio esperado. Se añade renumeración de seriales
con conectividad conservada como control inocuo estricto. Proxies químicos
sin pKa o población verificados se publicarán fuera del gate estricto.

Fuentes abiertas: incidencias OpenFF #101, #104 y #112; artículo Hahn et al.
(10.33011/livecoms.4.1.1497). #107 y README remoto del commit no pudieron abrirse
con el navegador; no se usan como evidencia de casos. Se consultará el README
local. Las observaciones de incidencias son preocupaciones publicadas, no
veredictos de que los curadores se equivocaron. Brazo C: cuatro preocupaciones
identificadas en cuatro dianas; menos de cinco, por tanto no concluyente.

No se han modificado archivos de backend, frontend, rescoring o tools, ni
experimentos ajenos. No se ha hecho push, merge, rebase o build.

## Hito 1 — 2026-10-11, prerregistro

Gate y mínimos fijados en FEP-09-prerregistro.md, con inventario de casos y fuentes. 45 bases, 15 controles inocuos, 10 controles espaciales y variantes aplicables. Se hallaron tres registros ejecutables para cuatro preocupaciones públicas: thrombin lig_7d no aparece con ese nombre. El estado de tnks2 lig_7 se contrastará con la representación del commit, sin trasladar la incidencia automáticamente. Sin corridas reales antes de este commit.

Hash del prerregistro: `9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638`.

## Hito 2 — 2026-10-11, arnés y piloto

Piloto completo cdk2: ocho intentos, ocho auditorías, cero fallos. Tres uploads
independientes de base y el control de seriales producen el mismo receptor
`c359de55ebe3a134edcf1d2f75c989f7f86a0564bc48651abbca71ed3f09410c`.
Vina declara 1.2.7, exhaustividad 8, nueve poses, semilla 42; receta
`c6fea531565d2ef11917c2338198f8b982225eb0efd69a502ac59fca007ee644` para la base.
Primer intento 41,756 s; los siete siguientes 25,271–27,614 s. Estimación de
127 casos en tres shards: aproximadamente 20–40 minutos, más arnés, análisis
y verificaciones; no se reduce la población. Los ocho datos del piloto
quedan separados y no entran a las tasas confirmatorias.

No se cambian selección, categorías, mínimos, gate o parameters del protocolo.
Mejoras técnicas del arnés antes de la fase confirmatoria: verificación explícita
de parámetros y modo en result; captura de condiciones QA con sus nombres de
campo reales; integridad de intervenciones comprobada para las 127 entradas;
analizador con autotest positivo y negativo. No hubo reintentos ni eliminación
de resultados. Se añaden atributos -text a los nuevos activos para conservar
bytes al checkout, sin modificar activos sellados ajenos.

El hueco cercano mueve receptor.huecos a ABSTENCION; el lejano a REVISAR.
La descripción se refiere a la caja, no a la pose: se investigará como
observación de contexto sin cambiar el producto. El alternativo tautomérico
queda bloqueado, pero sigue siendo proxy sin población independiente.

Las cápsulas usan un export externo, sin construirlo ni ejercerlo. Su guarda
de puerto del export falla porque mira frontend/out del worktree, que no
existe; se declara esta desviación sin dar por auditada la UI. El backend
sí supera health, login y CORS. Fuente del backend: f183e0af, diff de las
cuatro carpetas prohibidas vacío. Los nuevos scripts hacen que las cápsulas
2–3 declaren árbol general sucio; no se esconde ese estado ni se confunde
con cambios en el producto.

## Nota técnica durante hito 3 — 2026-10-11

La primera comprobación global de sellos detectó tres propiedades extra no
admitidas por manifest.schema.json. Se trasladaron **sin cambiar sus valores**
a registered_conditions.json. El manifiesto mantiene el commit de producto
en protocol; se conservan los hashes originales de prerregistro e inventario
y el commit 9cdd0eab. No se vuelve a init ni se toca la decisión del gate.
Se adapta la lectura del arnés para reanudaciones; los tres procesos ya
iniciados mantienen sus condiciones en memoria. validate pasa y validar_sellos
--check con python-embed pasa: 168 sellados, uno pendiente, cero ausentes o
distintos. No se han editado experimentos ajenos.

Verificación de piloto: ocho respuestas completas y condiciones válidas.
Se reconstruyeron los contratos de hash con stdlib, sin importar el producto:
el raw de cdk2 existe, el receptor congelado tiene el hash declarado y la
receta de modo B recalculada coincide. La receta automática que usa
origen_comprobado es diferente; Preparación lo reporta en entorno.referencia
como NO_EVALUADO. No es un archivo perdido ni un fallo de Vina. Se incorpora
como defecto de producto a documentar, sin reajustar el gate.

Intervalos Clopper–Pearson contrastados contra scipy.stats.beta en 5.150
combinaciones (todos k, n de 1 a 100), tolerancia 1e-9. El cálculo de producción
sigue siendo stdlib; scipy sólo fue contraste independiente. Se amplía el
autotest sintético con falsas alarmas y ruido por requisito, sin resultados
reales usados para seleccionar umbrales.

Al contrastar el ligand_state completo con el texto preregistrado se detectó
una descripción incorrecta: el modo por defecto de f183e0af es **entrada**,
no canónico. El arnés nunca impuso un modo ni cambió esa petición entre
brazos; preflight y result documentan entrada desde el piloto. Se conserva
el prerregistro byte a byte y se publica la desviación sin reintentos ni
ajustes del gate. El cierre será INCONCLUSIVE: además del n insuficiente de
las categorías químicas estrictas, no se ha ejecutado el modo canónico que
el texto asumía. Las respuestas a proxies siguen siendo descriptivas.

Se prepara cierre con prueba de cada activo contra su blob de HEAD antes
de seal y finish; los binarios compartidos se leen fuera del worktree y se
declaran con alcance exclusivo FEP-09. No se copian ni modifican binarios.

## Hito 3 — 2026-10-11, medición completa

Tres shards independientes terminados: shard-0, 44 casos (cdk2, eg5, p38,
ptp1b, thrombin); shard-1, 44 (cdk8, hif2a, pde2, shp2, tnks2); shard-2,
39 (cmet, mcl1, pfkfb3, syk, tyk2). Total 127 intentos confirmatorios,
127 auditorías, cero rechazos anteriores y cero fallos de infraestructura.
Se conservan complete.json, journals y respuestas de cada shard. No hubo
reintentos ni borrado de resultados. Los ocho del piloto siguen aparte.

Se versiona _work a la fuerza. Antes del cierre se comprobaron 1.218 JSON
disponibles entonces: sin claves de credenciales ni contenido PDB/PDBQT/SDF.
Los inputs estructurales están en tmp de cápsulas y se conservan fuera de Git.
Se apagan las cápsulas al terminar, sin limpiar sus datos ni logs.

El conteo preliminar confirma los 15 pares de cortes cercanos, con requisito
receptor.huecos ABSTENCION respecto a base; no se generaliza a problemas
reales. Los controles y repeticiones registran cambios de procedencia.commit
entre REGISTRADO y NO_DISPONIBLE. _source_commit exige árbol general limpio;
las ediciones y commits de scripts/documentos durante la fase larga producen
ese factor de confusión, con producto sin cambios. Se conservan en métricas,
sin exclusión posterior para mejorar falsa alarma ni atribución a química.

## Hito 4 — 2026-10-11, análisis y paper

Unión ordenada por case_id, sin piloto ni duplicados. Dos ejecuciones de
unión y análisis producen los mismos hashes de per_complex, failures y
metrics. Autotest positivo/negativo pasa; IC exactos previamente contrastados
contra scipy. Verificación completa: 127 auditorías, archivos realmente
subidos con sus hashes, fuentes PDB/SDF iguales al inventario, cajas, pH,
una conformación, Vina 8/9/42, CPU=4, Meeko y RDKit válidos. Inventario y
texto preregistrado coinciden con blobs de 9cdd0eab byte a byte.

Decisión INCONCLUSIVE. Huecos cercanos: 15/15, CP95 [0,7819806391; 1], GO
para esa categoría. Estereo sin asignar: 3/3, n insuficiente. Tautómero
minoritario y especie con pKa independiente: n=0. Alternativo proxy: 13/13;
especie proxy: 1/7 con cinco bases saturadas, fuera del gate. Límites:
cadena 0/1, metal 0/1, agua 0/9, protonación B 0/5; sin presentarlos como
defectos de contrato ni problemas atribuidos a los autores de PLB.

Falsa alarma operacional: 4/555 (0,7207207%); ruido: cinco cambios de 1.110
comparaciones, acuerdo 99,54955%. Todos esos cambios son procedencia.commit
y se explica el factor de confusión de árbol general, sin retirarlos del
conteo. Receptor: un único hash entre tres bases, en las 15 dianas. Diez
controles espaciales: dos cambios no previstos; la revisión de huecos
lejanos estaba permitida antes de medir. Brazo C: cuatro preocupaciones,
tres registros, INCONCLUSIVE, sin tasa. Referencia: NO_EVALUADO por receta
en 127/127 auditorías; se demuestra el contrato B en reproducción cdk2.

Paper y expediente se generan desde metrics/verification, con condiciones,
no_demuestra, saturación y concordancia FEP-08. Cinco guardas editoriales
existentes pasan y tres de registro publicado se posponen al candidato
temporal tras finish, sin modificar frontend. Todas las cápsulas están
apagadas; datos/logs e inputs originales permanecen disponibles fuera de Git.

## Hito 6 — 2026-10-11, expediente de defectos

Se cierra antes del hito 5 para incluir los bytes finales del expediente en
el sello. FEP09-P01 (P1 propuesta): origen_comprobado compara la receta
automática con la registrada en modo B. La reproducción mínima cdk2 tiene
origen presente, receptor con hash correcto y receta B coincidente; la
auditoría declara NO_EVALUADO por receta y mide desde la caja. El expediente
conserva entrada, raw normalizado, receptor, ambas recetas, task_id,
solicitudes y respuestas, esperado/observado y comando de cápsula nueva.

L01–L06 separan límites anteriores al upload, protonación B, proxies sin
etiqueta independiente e identidad del constructo. No se propone severidad
de bug para ellos ni se parchea el producto. La segunda reproducción en
cápsula nueva se deja para revisión independiente y está explícitamente
no verificada; el arnés de reproducción escribe fuera del experimento.

## Hito 5 — 2026-10-11, sello

Antes de seal: árbol limpio en 5badbecb4d1edb65bf25922ea817254da3f64e0a,
producto sin diff respecto a f183e0af. Prueba de versionado: 1.387 activos
comparados con blobs de HEAD, mismos bytes; incluye los cuatro directorios
_work de piloto y shards, scripts, preregistro, paper y expediente final.
validate pasa. seal registra 31 archivos de datos externos (15 PDB, 15 SDF,
targets.yml), cuatro binarios reales compartidos y 1.387 activos versionados.
No hay pesos de modelos en el sello: el resultado evalúa Preparación y no
valida las predicciones de rescoring. Binarios/datos externos están
declarados exclusivamente para FEP-09 en sellos_no_distribuidos.json.

Se commitea este sello para volver a árbol limpio antes de finish. README y
manifest son los únicos archivos científicos que finish modificará, conforme
al contrato del gestor de experimentos. La bitácora no es un activo sellado.

### Cierre y verificaciones del hito 5

finish se ejecutó desde árbol limpio en ee4ec6e716da17517508919e5fd3a814e1c65514.
Decisión INCONCLUSIVE, duración confirmatoria 2.154,098978 s de reloj entre
primer inicio y último término de las tres cápsulas paralelas (35,90 min).
No es duración sumada de CPU ni incluye reconocimiento, piloto o análisis.

Con python-embed 3.11.9, validar_sellos.py --check pasa: 169 sellados,
ninguno pendiente, 2.278 ficheros verificados, cero ausentes y cero distintos.
Las declaraciones de activos no distribuidos permanecen explícitas. Ocho
guardas de test_registro_cientifico.py pasan sobre un registro candidato en
tmp/fep09-editorial-registry, comprobando inclusión del experimento y paper
nuevos. El frontend publicado no se regenera porque el encargo prohíbe
modificarlo; no se afirma que el instalado muestre ya este experimento.

Todos los hitos están cerrados en commits locales. Sin push, fusión, rebase,
build, staging de runtime ni smoke de producción; sin cambios en producto,
experimentos ajenos o notas de 1.0.2. Para revisión: manifiesto y paper,
expediente FEP09-P01, límites L01–L06 y desviaciones documentadas. Prerregistro
inalterado: 9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638.

