---
titulo: "Preparación detecta cortes del sitio; la sensibilidad completa queda abierta"
entradilla: "Un ensayo pareado por la API, con 15 dianas de OpenFF, defectos sembrados y controles independientes. Resultado INCONCLUSIVE: la tabla conserva las detecciones, los límites y una comprobación de origen que no reconoce la receta de receptores ya preparados."
---

**INCONCLUSIVE.** Se completaron 127 intentos confirmatorios:
127 auditados, 0 rechazados antes
de Preparación y 0 fallos de infraestructura.
El piloto de ocho corridas se conserva aparte y no entra en estas cifras.

MolDesign pretende comunicar qué evidencia estructural produjo una corrida
y dónde debe abstenerse. Un control positivo sobre estructuras preparadas
por expertos, como FEP-08, no demuestra que la pestaña Preparación reaccione
a defectos. Este experimento mide esa reacción por requisito, sin ejecutar
energía libre ni cambiar el producto para mejorar su resultado.

## Qué se midió

Producto `f183e0af`, Python embebido 3.11.9, Meeko 0.7.1, camino B
(`respetar`, receta B versión 1, distinta de la receta automática 7), Vina
1.2.7, exhaustividad 8, nueve poses solicitadas, semilla 42, pH 7,4,
un confórmero y modo tautomérico efectivo `entrada`. Se usaron tres cápsulas
aisladas, cuatro núcleos por Vina, con datos y perfiles propios. No se
ejerció el frontend externo ni el instalador.

Benchmark de OpenFF en commit
`fd88824f9114244f95a14b485e6d6c96c1de716d`: 15 dianas con PDB y SDF en
las rutas prescritas, de las 21 entradas en targets.yml. Se excluyeron seis
por archivos ausentes, antes de ver resultados. Se eligió el primer registro
SDF legible por diana; la caja fija de 20 Å por lado se centró en sus átomos
pesados. Los archivos permanecen en el clon externo; aquí se conservan
nombres, hashes, intervenciones y respuestas.

Para cada diana se repitió tres veces una subida y preparación independiente
de la línea base. Cada variante del brazo A cambia una característica: cortes
del esqueleto, cadena o especie ausente, estado químico o protonación local.
Los generadores usan geometría directa y RDKit, sin importar las funciones
del producto. La ruta fue upload → preflight → submit → status → result →
POST preparacion, conservando estados y datos de todos los requisitos.

El [prerregistro](../auditorias/FEP-09-prerregistro.md) se fijó en
`9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638` antes de la primera corrida.
Una alerta ya presente en la base no cuenta como detección. Para categoría
declarada con n≥8 se exige límite inferior del IC exacto bilateral 95 %
de Clopper–Pearson ≥0,5 y falsa alarma de controles inocuos ≤0,10. Las
categorías con n insuficiente quedan INCONCLUSIVE; no se retiran del gate.

**Desviación declarada.** El prerregistro llama «canónico» al modo por
defecto, pero el arnés no especificó ese parámetro y la API de f183e0af
aplicó `entrada`, como muestran preflight y ligand_state. Esa descripción
era incorrecta; no se modificaron las peticiones entre brazos ni se
reintentaron corridas. El texto preregistrado queda intacto. Las métricas
describen la condición efectiva y el cierre queda INCONCLUSIVE; los
proxies no validan minoría tautomérica ni el comportamiento bajo un modo
canónico forzado.

## Qué salió

| Categoría | n | Auditor | Detectado antes | IC 95 % ruta | Decisión / alcance |
|---|---:|---:|---:|---|---|
| agua_puente_retirada | 9 | 0 | 0 | [0,000; 0,336] | límite |
| cadena_del_sitio_ausente | 1 | 0 | 0 | [0,000; 0,975] | límite |
| especie_del_ligando | 0 | 0 | 0 | no estimable | INCONCLUSIVE |
| especie_opuesta_proxy | 7 | 1 | 0 | [0,004; 0,579] | proxy |
| estereo_sin_asignar | 3 | 3 | 0 | [0,292; 1,000] | INCONCLUSIVE |
| hueco_en_el_sitio | 15 | 15 | 0 | [0,782; 1,000] | GO |
| metal_o_cofactor_retirado | 1 | 0 | 0 | [0,000; 0,975] | límite |
| protonacion_del_sitio | 5 | 0 | 0 | [0,000; 0,522] | límite |
| tautomero_alternativo_proxy | 13 | 13 | 0 | [0,753; 1,000] | proxy |
| tautomero_minoritario | 0 | 0 | 0 | no estimable | INCONCLUSIVE |

El gate global exige que todas las categorías declaradas pasen. Estereoquímica
tiene n=3; minoría tautomérica y especie con pKa independiente, n=0.
Aunque una categoría suficiente pase, estas tres quedan INCONCLUSIVE.

«Auditor» cuenta un aumento de riesgo del requisito esperado respecto a su
base, con el mínimo preregistrado; «detectado antes» guarda el rechazo
explícito anterior. Las tasas de los límites y proxies son respuestas al
ensayo, no sensibilidad bajo una cobertura que el producto no declara.
`metrics.json` conserva también saturación, ausencias, casos evaluables y
cambios colaterales, sin excluirlos para favorecer una tasa.

Hay saturación previa en 1
caso de cadena, 5 de especie
proxy y 5 de protonación
del receptor: su aviso base ya alcanza el mínimo, sin incremento atribuible
a la intervención. Esos casos permanecen en el denominador descriptivo.

La falsa alarma de renumeración inocua fue 4/
555 requisitos comparables (0,72 %).
El acuerdo de las bases fue 99,55 %, sobre
1110 comparaciones; cambiaron 5.
Requisitos no reproducibles por estado o riesgo: procedencia.commit (5).
Las tres bases conservan un hash único de receptor por diana:
15/15.

En 5 comparaciones de base y 4 de renumeración
cambió `procedencia.commit` entre REGISTRADO y NO_DISPONIBLE. El producto
declara commit sólo con árbol general limpio
(`vina_service.py::_source_commit`); los scripts y metadatos de este
experimento se editaron y commitearon durante la fase larga, con diff de
producto vacío. Las razones registradas explican esa ausencia por árbol
modificado. Se mantienen estos cambios en el conteo preregistrado y se
declara el factor de confusión: no prueban variación de química o de
preparación, ni son evidencia de no determinismo de protonación.

Los 10 cortes lejanos son un control espacial, con
2 cambios no previstos entre requisitos comparables. El
prerregistro permite revisión de esos extremos nuevos: el producto la
declara aun lejos del sitio. Esa revisión legítima no se presenta como una
falsa alarma ni se confunde con bloquear la cavidad.

## Una comprobación de procedencia que falla

La referencia de distancias quedó sin evaluar por discrepancia de receta
en 127/127 auditorías de este camino B. En la reproducción mínima de cdk2,
el archivo de origen existe y el hash del receptor se verifica; la receta B
recalculada coincide con la registrada. Sin embargo, el comprobador del origen
usa la fórmula de la receta automática y concluye que no coincide.

La auditoría lo declara en `entorno.referencia`: «NO_EVALUADO». Por eso los
otros requisitos usan la caja como referencia y no pueden ofrecer toda la
geometría al ligando que declaran cuando reconocen el origen. El expediente
separa este defecto de las especies borradas **antes** del upload: el auditor
declara el diff que MolDesign produce, no reconstruir un origen que no recibió.
No se aplicó ningún parche durante el experimento.

## Concordancia descriptiva con FEP-08

| Diana | Huecos físicos que declara Preparación | Cadenas del sitio declaradas |
|---|---|---|
| cdk2 | REGISTRADO: Ninguno: el esqueleto de las cadenas del receptor es continuo (C–N ≤ 2 Å entre residuos consecutivos). | A |
| thrombin | REGISTRADO: Ninguno: el esqueleto de las cadenas del receptor es continuo (C–N ≤ 2 Å entre residuos consecutivos). | H |
| tnks2 | REGISTRADO: Ninguno: el esqueleto de las cadenas del receptor es continuo (C–N ≤ 2 Å entre residuos consecutivos). | A |

FEP-08 marcó saltos de numeración en cdk2 y thrombin, y un sitio entre cadenas
en tnks2. Un salto de numeración no prueba un corte físico. Además, aquí se
observa la preparación de MolDesign por API y su referencia efectiva de caja.
Esta comparación no entra al gate ni convierte documentabilidad preliminar
en readiness de un cálculo posterior.

## Lo publicado por terceros

| Diana | Fuente abierta | Qué comunica la fuente | Observación de esta versión |
|---|---|---|---|
| tnks2 | [lig_7](https://github.com/openforcefield/protein-ligand-benchmark/issues/101) | La incidencia comunica un N de amida sin H y carga negativa en lig_7 frente al resto de la serie; se comprueba su representación en el commit fijado, sin adjudicar su población a pH experimental. | lig_7: ligando.especie=REGISTRADO, Microestado más próximo al predicho a pH 7.4, de 2 enumerados; global REVISION |
| eg5 | [lig_CHEMBL1084935](https://github.com/openforcefield/protein-ligand-benchmark/issues/101) | La incidencia pregunta por las dos representaciones de estereoquímica de una amina protonada y nombres repetidos. Es una preocupación publicada, no una demostración de que alguna sea incorrecta. | lig_CHEMBL1084935: ligando.estereoquimica=REVISAR, La entrada declaraba 1 estereocentro(s) y 0 doble(s) E/Z que la especie acoplada no conserva (la normalización cambió esos átomos): lo acoplado no es el estereoisómero escrito.; global REVISION |
| thrombin | [lig_7d](https://github.com/openforcefield/protein-ligand-benchmark/issues/101) | La incidencia pregunta si la medida de lig_7d corresponde a un estereoisómero o una mezcla, ante varias entradas. Se documenta la incertidumbre experimental, sin atribuir un error a los autores. | Sin registro con el nombre indicado en el commit fijado |
| tyk2 | [construcción del receptor](https://github.com/openforcefield/protein-ligand-benchmark/issues/112) | La incidencia propone revisar D1023N respecto al sistema del ensayo. El auditor no declara comparar secuencia y construcción experimental; se mide como límite. La correspondencia de numeración con 4GIH no se ha probado. | lig_ejm_54: sin requisito declarado de identidad del constructo experimental; global REVISION |

Se abrieron las incidencias el 2026-10-11. Son preocupaciones públicas y
preguntas, no demostraciones de que los curadores se equivocaron. El estado
de la versión fijada debe contrastarse por separado: por ejemplo, su
tnks2 lig_7 contiene [nH] neutro en la representación leída, y eg5 aporta
un registro con el nombre buscado. Con cuatro preocupaciones y tres
registros medidos, el brazo C es no concluyente y no tiene tasa.

## Qué no dice

- No mide la fracción de problemas reales de preparación que MolDesign detecta.
- No demuestra transferencia a FEP, compatibilidad con FEP+ ni ejecución de energía libre.
- No valida poblaciones tautoméricas, pKa individuales, protonación del receptor ni identidad experimental.
- No audita interfaz, WebView2, runtime staged o instalador.
- No atribuye errores a los autores de PLB. Los estados químicos proxy están fuera del gate.
- No prueba un protocolo forzado a tautómero canónico: la API usó entrada por defecto, discrepante con la descripción del prerregistro.
- La variación de procedencia.commit está confundida por ediciones y commits del arnés durante la medición; no demuestra no determinismo químico.
- Las tasas de ausencia previa al upload no evalúan el diff que produce la preparación.

No se verificó una población independiente para llamar minoritario a cada
alternativo RDKit ni un pKa individual que cumpla distancia >3 a pH 7,4.
Estas dos categorías estrictas tienen n=0 verificable; los proxies se
publican por separado. Tampoco se validó el carácter catalítico de cada
Asp/Glu intervenido, ni la correspondencia de numeración TYK2–4GIH.

## Consecuencia y reproducción

El resultado conserva qué categorías discriminan y cuáles quedan abiertas.
La comprobación del origen de modo B necesita un encargo de corrección
separado, y la cobertura química necesita una cohorte con estados verificados
independientemente. No se cambia el producto de 1.0.2 ni se publica la rama.

Manifiesto, datos agregados, shards y verificación:
`scripts/artifacts_science/FEP-09-SENSIBILIDAD/`.
Arnés: `scripts/fep09_inputs.py`, `fep09_run.py`, `fep09_analyze.py`,
`fep09_verify.py`, `fep09_reproduce.py`. El analizador incluye autotest
positivo y negativo; sus IC se contrastaron con scipy.stats.beta en 5.150
combinaciones, tolerancia 1e-9. La producción usa biblioteca estándar.

Datos CC BY 4.0 de OpenFF, atribuidos a
[Hahn et al., LiveCoMS 2022](https://doi.org/10.33011/livecoms.4.1.1497),
*Best Practices for Constructing, Preparing, and Evaluating Protein-Ligand
Binding Affinity Benchmarks*. Código del benchmark MIT. El clon externo y
su obtención están declarados en sellos_no_distribuidos.json.
