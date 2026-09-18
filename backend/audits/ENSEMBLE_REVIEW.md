# Revision acotada del ensamble - 2026-09-17

Alcance: backend, sin build, sin activar MM-GBSA experimental, sin cambiar
pesos, energias, generacion de conformaciones ni seleccion de poses.
Se inspeccionaron implementaciones, contratos y registros experimentales locales;
NO se repitieron los benchmarks cientificos ni se verificaron todos sus hashes.

## Dos mecanismos diferentes

1. Ensemble conformacional: `chem/conformer_ensemble.py` genera conformaciones;
   `services/docking/ensemble.py` ejecuta Vina por conformacion, agrupa las poses
   y entrega las de menor energia observada. Conserva indice de conformacion.
   K=1 delega en el generador habitual. Esto NO es un ensemble de receptores.
2. Stacking M4: `scoring/engine.py`, `rescoring/artifacts/stacking_weights.json`
   y `artifacts/sci_config_registry.json`. El contrato de release declara
   Vina=0.25, XGB=0.75, GNN=0, CL-GNN=0; familias con pesos comunes.
   `services/targets/calibracion.py` declara vacio el conjunto de familias
   calibradas. No se deben presentar los pesos como calibracion por receptor.
   Si falta un componente, el engine renormaliza y declara degradacion/pesos
   efectivos; no se ha medido aqui la utilidad predictiva de esa degradacion.

## Evidencia existente y sus limites

Fuentes originales leidas, sin modificar archivos sellados:

- `scripts/artifacts_science/MF-33-A3/README.md`: en el estrato COLOCACION
  (33 complejos), cobertura del oraculo RMSD <=2 A: ensemble 26/33 frente a
  19/33 con reinicios de un conformero, igualando corridas y poses, CPU
  aproximada (A3/B=1.196). Discordancias 7 contra 0; p=0.0156.
  Es cobertura: el oraculo conoce la estructura experimental. No es un
  porcentaje de recomendaciones correctas ni valida el pipeline actual.
- `scripts/artifacts_science/MF-33-B-RET-R2/metrics.json`: 48 complejos;
  top-1 single 20/48, ensemble 24/48, McNemar p=0.34375; top-5 26/48 frente
  a 35/48, p=0.003906; oraculo 26/48 frente a 41/48. Configuracion:
  exhaustiveness=8, num_modes=9, seed=42, caja=25 A, cpu=1.
  El registro declara expresamente que R2 NO es confirmacion ciega.
  No demostrar mejora top-1 no demuestra equivalencia o ausencia de efecto.
- `scripts/artifacts_science/MF-33-H-COR/README.md`: 8181/8224 poses flexibles
  PB-valid, CONDICIONAL a reconstruccion canonica de hidrogenos conservando
  coordenadas pesadas. No demuestra exactitud de pose, union ni superioridad
  de un brazo. Sustituye cifras historicas contaminadas por reconstruccion.

La evidencia apoya diversidad/cobertura bajo esos protocolos. Queda demostrar
transferencia al generador, preparacion, binarios y parametros actuales, y
ventaja de la seleccion final en un conjunto externo no usado para ajustar.
No se audito exhaustivamente aqui el solapamiento con entrenamiento de XGB/GNN.

## Hallazgos y correccion

| ID | Severidad | Problema | Estado |
|---|---|---|---|
| ENS-01 | ALTO | El agrupador atribuia a todas las poses la procedencia de la primera corrida sin verificar receptor, version, semilla ni protocolo de las restantes. | Corregido: desacuerdos abortan con campo e indice identificados; no se silencian como fallo parcial. |
| ENS-02 | ALTO | Se perdian engine_efectivo, exhaustiveness_efectiva y num_poses_solicitadas al agrupar. El dossier podia recuperar lo pedido y ocultar una diferencia con lo ejecutado. | Corregido: se preservan tras comprobar homogeneidad. |
| ENS-03 | MEDIO | parsing_source queda con el valor de la ultima corrida y no se conserva conversor_estructural en el resultado agrupado. Puede ocultar conversiones mixtas. | Corregido para nuevos ensembles: procedencia por pose, `mixed` declarado, historicos con None. Ver «Continuacion: identidad de registros y conversiones». |
| ENS-04 | MEDIO | El agrupado no tiene SDF colectivo: poses_file_path=None es deliberado para no apuntar a coordenadas de una sola corrida. | Cerrado: recuperacion verificada con seis puertas, ninguna basada en el rank a secas. Ver «ENS-04 cerrado». |
| ENS-05 | ALTO, **confirmado y corregido** | Generacion RDKit adicional dentro de async, almacenamiento por hash/indice y dependencia de metadata sin identidad completa por corrida. | Corregido: el riesgo era real y el mecanismo era PEOR que la hipotesis. Ver seccion «El ensemble acoplaba la misma geometria K veces». |
| ENS-07 | ALTO, corregido | `source_provenance` no cruzaba la persistencia: `Repository.cast_pose` enumeraba campos a mano y no lo incluia. | Corregido: se persiste dentro del JSON existente; sin esto, ENS-03 y ENS-04 eran contratos que no existian fuera del proceso. |

ENS-01 era reproducible inyectando dos DockingResult con receptores o protocolos
distintos. La ruta normal intenta compartir parametros; la guardia protege el
limite del agrupador ante cambios, regresiones o evidencia incompleta. No se
ha demostrado que usuarios hayan sufrido esta mezcla.

La guardia compara receptor_sha256, vina_version, vina_random_seed,
engine_efectivo, exhaustiveness_efectiva y num_poses_solicitadas. Un dato conocido
no puede cubrir el desconocido de otra corrida. Si todas carecen de un campo,
se conserva None por compatibilidad; eso NO certifica su identidad. Distintas
rutas con el mismo hash se admiten. Los errores ordinarios de una conformacion
siguen permitiendo cobertura parcial y la cancelacion se propaga.

## Verificacion

- Antes del cambio: 9 fallos reproducibles y 28 pruebas correctas en la suite
  conformacional ampliada.
- Despues: 113 passed, 1 skipped en ocho archivos (ensemble, protocolo,
  piscina/dossier, stacking, no-fabricacion, calibracion, avisos y dossier).
- Se prueban incompatibilidades, ausencia asimetrica de huella, conservacion
  de parametros, rutas diferentes con mismos bytes y cancelacion. Las pruebas
  existentes conservan energias, ranking estable, K=1 y degradacion parcial.
- Regresion global: 2427 passed, 10 skipped, 1 failed (H15 frontend
  preexistente), 14 warnings, 243.06 s. Log: hardening-ensemble-full.log.
  Ruff F de desarrollo, compileall focalizado y git diff --check correctos.

## Proximo experimento propuesto: ENS-PROD-01

Estado: BORRADOR, no prerregistrado ni ejecutado. Antes de ejecutarlo hay que
cerrar cohorte, tamano/potencia, presupuesto y umbral de relevancia practica.
No mirar el conjunto final para decidir esos valores.

1. Objetivo: comprobar transferencia del beneficio de cobertura al pipeline
   actual y si llega a las poses entregadas. No evaluar actividad biologica
   con etiquetas de RMSD. Priorizar ligandos pequenos no covalentes con
   estructuras experimentales; metales/cofactores como estratos declarados.
2. Datos: cohorte publica independiente de MF-33 y de ajustes previos; documentar
   solapamiento de diana, ligando/serie y entrenamiento de modelos. Hashes,
   licencias, decisiones de preparacion y exclusion registrados antes de correr.
3. Brazos: pipeline actual K=1; K=30; y reinicios desde un conformero con
   presupuesto comparable. Fijar binario, receptor, caja, protonacion, poses
   conservadas y politica de semillas. Registrar CPU y tiempo; no confundir
   beneficio de presupuesto con diversidad.
4. Primario propuesto: acierto top-1 con RMSD pesado corregido por simetria <=2 A
   Y validez fisica bajo reconstruccion de H explicita. Secundarios: top-5,
   cobertura del oraculo, fallos, abstenciones, coste y fraccion evaluable.
   Referencia cristalina accesible SOLO al evaluador, nunca al selector.
5. Analisis: comparaciones pareadas por complejo, intervalos de confianza y
   desglose por diana; contemplar dependencia entre complejos relacionados.
   Todos los casos preincluidos permanecen en el denominador. Predefinir
   tratamiento de fallos y multiplicidad si se prueba mas de una hipotesis.
6. Gate: limite inferior del intervalo para la diferencia primaria superior a
   cero y ganancia practica predefinida, dentro del presupuesto acordado. Si
   solo mejora cobertura, declarar solo cobertura; no promocionar top-1.
7. Stacking se evalua APARTE sobre actividad experimental compatible: Vina,
   XGB ligand-only y combinacion actual, datos separados por serie/diana/fecha,
   precision entre primeros candidatos y cobertura, incluida degradacion.
   No modificar pesos ni entrenar con el conjunto final.
8. Entrega: manifiesto, resultados por complejo, fallos completos y comando
   reproducible offline en entorno limpio. Cambios cientificos posteriores
   requieren decision explicita y nuevo examen independiente.

Orden sugerido de continuacion: resolver procedencia mixta/pose exacta,
congelar ENS-PROD-01 y ejecutar piloto tecnico fuera del holdout; despues ensayo
final. Continuar MM-GBSA en paralelo solo como candidato experimental, con sus
gates de parametrizacion, complejos completos y utilidad aun abiertos.


## Continuacion: identidad de registros y conversiones (2026-09-17)

ENS-03 queda corregido para NUEVOS ensembles: cada pose conserva
`source_provenance` con rank original, ruta SDF de su corrida, parsing_source
y metadata del conversor. La renumeracion de la piscina no altera esos datos.
Un agrupado con distintos parsers declara `mixed`; el conversor global solo
se conserva cuando todas las corridas coinciden. No se recupera metadata de
corridas historicas que nunca la guardaron.

Justificacion del contrato aditivo: `DockingPose.source_provenance` es metadata
opcional, persistida dentro del JSON existente, sin migracion SQL. Los registros
historicos cargan con None. `DockingResult.parsing_source` admite `mixed` para
no atribuir toda la piscina al ultimo parser. No cambian scores, algoritmos,
parametros cientificos ni coordenadas. La UI no se modifico; el backend expone
los nuevos datos para su futura presentacion.

ENS-06 (ALTO, corregido): el parser SDF omitía registros sin afinidad y
renumeraba los siguientes. Vina asocia la lista resultante por posicion con los
bloques PDBQT: un primer registro sin afinidad podia asignar la energia del
segundo a la geometria del primero. La correccion rechaza el conjunto parcial
de scores SDF y permite seguir los respaldos existentes hacia conversion o
PDBQT. Un archivo completo conserva exactamente sus valores y orden. No se
reconstruye una afinidad ausente ni se cambia una formula.

ENS-04 sigue abierto: source_provenance NO certifica por si sola correspondencia
atomica ni integridad de bytes. Todavia no se utiliza para activar MM-GBSA.
Antes de recuperar SDF por rank de origen se exige comprobar hash del artefacto,
identidad quimica y correspondencia geometrica con el bloque PDBQT entregado,
sin conversion desde SMILES ni herencia de la pose de otra conformacion.
No se ha cerrado tampoco la validacion externa ENS-PROD-01: sigue como borrador.

Pruebas: seis fallos reproducidos antes del cambio y una prueba positiva; luego
129 passed, 1 skipped en ocho suites, incluidos SQLite real, contratos de
respuesta/PDF, Open Babel y MM-GBSA. Se cubren huecos de metadata al principio,
en medio y al final, y propiedades truncadas sin valor; parsers mixtos/homogeneos; rank original tras ordenar y
compatibilidad de registros antiguos. Resultado global en HARDENING_1.0.1.md.
Ruff F detecto un F841 preexistente en test_sqlite_roundtrip.py:194, fuera del
cambio (variable mol). No se corrigio ni se oculto en esta revision.

El separador $$$$ se procesa antes de cualquier propiedad pendiente: un valor
ausente no puede absorber el fin del registro ni mezclar metadata entre poses.
Dos pruebas adicionales reprodujeron esa variante antes de corregirla.

Verificacion global de esta continuacion: 2434 passed, 10 skipped, 1 failed
(H15 frontend preexistente), 14 warnings, 239.96 s. Esa corrida comenzo antes
del ultimo ajuste de delimitadores; despues de ese ajuste se verificaron las
129 pruebas focalizadas indicadas arriba. No se afirma una suite global nueva
sobre ese ultimo ajuste. Detalle en HARDENING_1.0.1.md.


## El ensemble acoplaba la misma geometria K veces (2026-09-17, tarde)

ENS-05 estaba anotado como «ALTO, riesgo por verificar» con una hipotesis:
concurrencia, colisiones de hash, metadata sin identidad. Se midio. El riesgo
era real y el mecanismo era otro, peor y deterministico.

`vina_service._prepare_ligand_pdbqt` recibia el hash derivado de cada
conformacion (`<hash>__c07`) y, antes de buscar su `.sdf`, revalidaba el SMILES
y sustituia la ruta por la del conformero del hash canonico si existia. En una
corrida de ensemble ese archivo existe SIEMPRE: es la conformacion 0, que el
generador escribe primero. Las K corridas de Vina recibian la misma geometria.

Lo que esto significa, dicho con cuidado para no afirmar mas de lo medido: **las
K corridas partian de la misma geometria**. La diversidad conformacional que el
ensemble existe para aportar no estaba, y cada pose de la piscina declaraba una
conformacion de origen distinta, asi que **`conformer_index` era falso**. La
lectura que justifica el ensemble entero -distinguir «la misma solucion
encontrada desde puntos de partida distintos» de «dos soluciones distintas»- era
imposible, porque el punto de partida era uno solo. El usuario pagaba K corridas
de Vina y recibia la cobertura geometrica de un unico punto de partida.

Lo que NO se midio: si las K salidas eran identicas entre si. Con la misma
entrada, semilla y caja cabria esperarlo, pero `vina_cpu` vale 0 por defecto
-auto-deteccion de nucleos- y la busqueda paralela de Vina no garantiza
reproducibilidad bit a bit. No se comprobo, y por tanto no se afirma.

Reproducido con un ensemble real de tres conformaciones de benceno y Meeko
instrumentado para anotar que archivo recibia:

    SDF de cada conformacion    d18bd2789cc3  79e5e727d44e  14609fa750c7
    SDF que recibio Meeko       d18bd2789cc3  d18bd2789cc3  d18bd2789cc3

Solo ocurria cuando el hash post-protonacion coincide con el del validador -el
caso de cualquier ligando neutro-, asi que colapsaba el ensemble en silencio
para unas moleculas y no para otras. Las pruebas del agrupador estaban verdes:
probaban la semantica de la piscina, no que las entradas fueran distintas.

Alcance de la correccion, en tres piezas que no sirven por separado:

1. La busqueda por SMILES solo actua si el hash pedido NO tiene geometria, y
   nunca para un hash derivado. Para una conformacion del ensemble, el unico
   SDF que la representa es el suyo; si falta, se aborta. Regenerar desde el
   SMILES daria otra vez la conformacion 0 escrita en la ruta de otra.
2. El `.pdbqt` preparado deja un registro con el objeto y el SHA-256 del
   conformero de origen, el SHA-256 del propio PDBQT y quien lo preparo, y ese
   registro se comprueba antes de reutilizar la cache. Sin esto la correccion no
   habria llegado a ninguna instalacion donde ya exista un `vina_input.pdbqt`
   construido desde la conformacion equivocada: es indistinguible de uno
   correcto, asi que la cache lo habria devuelto igual.
3. La huella del cache de docking incluye la identidad del SDF de entrada. El
   cache vive en memoria con TTL, asi que no hay migracion; lo que evita es que
   dos geometrias bajo el mismo hash compartan resultado dentro de un proceso.

El registro comprueba tambien `prepared_by`. `quantum_ad4_service` escribe ese
mismo objeto con cargas GFN2-xTB en lugar de las de Meeko; hoy no tiene llamante
vivo, y si se recupera no debe heredar esta cache sin declararlo. Queda anotado
como colision latente, no corregida: cambiar rutas de codigo sin llamante ni
cobertura no entra en este alcance.

### El bucle de eventos, medido

La segunda mitad de ENS-05. `generate_conformer` delegaba en un hilo desde el
2026-09-04; el ensemble embebia las K-1 conformaciones restantes DENTRO de la
corrutina. Latidos de una tarea que despierta cada 10 ms, dipeptido, tres
corridas por celda:

    K    duracion    antes        despues
    1      ~78 ms    5 / 7        5 / 7      <- ya estaba bien
    8     ~452 ms    5 / 44-45    29-30 / 45
   16     ~870 ms    4 / 85-86    56-58 / 86-88

Los cuatro o cinco latidos de «antes» son los del conformero 0: anadir siete
conformaciones no anadia un solo punto de suspension. Con K=64 son segundos de
ventana congelada mientras la interfaz sondea el progreso. No recupera los 86
posibles -ETKDG y MMFF sueltan el GIL parte del tiempo, no todo- y la duracion
total no cambia. Lo que cambia es «bucle vivo» frente a «bucle muerto».

### Trazabilidad de entradas

Cada conformacion generada declara ahora el SHA-256 del molblock que se escribio,
y la piscina lo conserva por pose en `source_provenance.ligand_input` junto con
la semilla conformacional. Un indice es una etiqueta; el hash es comprobable. Es
la diferencia que hizo invisible este defecto durante toda su vida.

## ENS-07: la procedencia no cruzaba la persistencia

Encontrado al intentar usar `source_provenance` desde un resultado guardado.
`Repository.cast_pose` enumera a mano los campos de cada pose y
`source_provenance` no estaba en la lista: el dato existia durante la corrida y
se perdia al guardar. La API devolvia None, el snapshot congelado tambien, y
recuperar la pose exacta de una piscina era imposible cinco minutos despues de
calcularla.

Es el mismo patron que ENS-02 -preservar un campo al agrupar y tirarlo en el
salto siguiente- y solo se ve probando el salto completo: agrupar, guardar,
volver a leer. La correccion es aditiva dentro del JSON existente, sin migracion.
Las corridas anteriores siguen cargando con None y no se reconstruyen.

Esto tambien matiza una frase de la seccion anterior de este documento: donde
decia «el backend expone los nuevos datos para su futura presentacion», la
verdad es que no los exponia. Queda corregido aqui en vez de reescrito arriba.

## ENS-04 cerrado: recuperacion verificada, con seis puertas

`services/docking/pose_recovery.py` recupera el registro SDF exacto de una pose
agrupada, o se abstiene diciendo que falta. Las puertas son las que este
documento exigia, mas la integridad de la entrada:

    G1  procedencia completa       sin ruta, rank y hashes no se busca nada
    G2  integridad del artefacto   el SDF de hoy es el SDF de la corrida
    G3  integridad de la entrada   la conformacion acoplada es la declarada
    G4  el registro existe         el rank cae dentro del archivo
    G5  identidad quimica          mismos atomos pesados que la entrada
    G6  correspondencia geometrica cada coordenada entregada esta en el registro

G6 es la que cierra el asunto. El `pdbqt_block` de la pose son las coordenadas
que Vina produjo y que el dossier ya cito; si cada una aparece en el registro
recuperado, el registro ES esa pose, sin depender de que el rank estuviera bien
ni de que nadie hubiera reordenado el archivo. La tolerancia es 0.002 A y es la
precision de los formatos -tres decimales el PDBQT, cuatro el SDF-, no un margen
de ajuste; una prueba fija que 0.05 A se rechaza.

La identidad quimica se comprueba contra la conformacion de entrada, no contra
un SMILES: reconstruir la molecula desde texto es precisamente la conversion que
este documento prohibia. Del PDBQT se leen numeros de las columnas 31-54 y nada
mas; el tipo AutoDock de las columnas 77-78 no se interpreta como elemento, por
el defecto documentado en `pose_physical_validity.py`.

Lo que NO cambia: MM-GBSA sigue EXPERIMENTAL_NOT_ENABLED y su guardia de
integridad sigue rechazando sistemas incompletos. Lo que cambia es que una
corrida de ensemble deja de ser irrecuperable por construccion: el endpoint
recupera la pose cuando las seis puertas pasan y se abstiene con el motivo
exacto cuando no. Las poses anteriores a este contrato no se pueden recuperar y
lo dicen.

Cada puerta se verifico desactivandola: con G6 anulada caen 4 pruebas, con G1
caen 5, con G2 dos, y G3, G4 y G5 una cada una. Una puerta que nunca rechaza no
es una puerta.
