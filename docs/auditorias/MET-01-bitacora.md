# MET-01-ION-DEL-SITIO — bitácora

## Base y alcance — 2026-10-11

Rama `sol/met-01-metales`, worktree `.worktrees/met01`, producto
`f0e6408668fa8ecbecb417cf39621928fdfee886`. El propietario confirmó la
integración P01. No se modifica el producto, catálogo, M5 ni otros experimentos.
No hay push, merge, rebase, build, stage ni smoke.

Runtime montado con la excepción explícita del encargo: junction de
`python-embed` y hardlinks de `tools/vina/vina.exe` y `vina_trace.exe`.
Se retirarán al finalizar, sin borrar el destino de la junction.

## Hito 0 — reconocimiento cerrado (sin docking ni RMSD)

La evidencia geométrica se reprodujo: 41 entradas, 52 iones, 35 entradas con
coordinación directa geométrica. Ningún docking ni RMSD durante reconocimiento.
Se preparan catálogo y variantes SIN/CON en dos procesos independientes;
las variantes usan el endpoint real, heredando cadena y caja.

Se usa una cápsula de API que reutiliza `entornoBackend`, `puertosDe` y
`carpetasDe` de QA. El lanzador general completaría `frontend/node_modules`,
`models` y `data/molgraph_seed.db`, fuera del alcance scripts/docs. Se omite esa
compleción y el frontend; se mantiene el entorno de producción, usuario nuevo,
datos privados, Python embebido, Vina real y cuatro CPU por cápsula.
`PYTHONDONTWRITEBYTECODE=1` evita escribir bytecode fuera del encargo.

El CCD se descarga una sola vez por componente durante la preparación del
prerregistro. Se conservarán definiciones, fuentes, fechas y hashes. Se usa el
SMILES_CANONICAL estereoquímico de OpenEye si está disponible y es legible por
RDKit; fallback determinista a los demás descriptores canónicos. No se toma
conformación del CCD ni del cristal como entrada de docking.

Se ejecuta sin cambios la sonda de microestado de CAL en dos procesos.
Las hipótesis diagnósticas se deciden con SMARTS independientes sobre el grupo
de anclaje; no con las reglas del producto. Se preserva el microestado normal
en los demás centros. La API reprotona muchas hipótesis a pH 7,4. Se prueban,
antes de Vina, pH 7,4, 10 y 12 mediante la opción pública, y sólo se admite una
forma si el grafo completo fijado coincide en ambos procesos. Se publica ese
cambio de parámetro; no es una afirmación sobre el pH de unión.

Se reutiliza `_cristal` de CAL, sin editarlo, suministrando el primer modelo y
altloc vacío/A que define la medida de metales. Se excluyen antes de docking
las referencias que el método no puede casar; no se corrige su grafo buscando
que el resultado pase.

### PoseBusters y los metales

La comprobación del cristal llama a `evaluar_pose_fisica` del producto, con
mapa de Meeko, receptor preparado y microestado normal congelado. No se calcula
RMSD. La inspección de `receptor_como_pdb` y las máscaras reales de PoseBusters
revela un límite: los metales Meeko `ATOM` se excluyen como proteína en la
comprobación inorgánica, y por elemento inorgánico en la de proteína. Ninguno
de los 47 átomos metálicos cargados en la primera inspección participa en
esas dos máscaras. Un PASA no valida los contactos con esos iones.

Los fallos observados del cristal son distancia/solapamiento con proteína,
no fallos intramoleculares; se corrige aquí la descripción preliminar de la
actualización al usuario. El lector también deja una referencia no evaluada.
No se ajusta PoseBusters ni el gate para mejorar una cifra. Las distancias a
los iones se miden aparte, geométricamente.

### Desviación de alcance y corrección

La primera inspección de máscaras omitió redirigir TEMP antes de llamar al
conversor. Creó un archivo propio fuera de scripts/docs:
`C:/Users/Johan Amezcua/AppData/Local/Temp/rec_pb_wrets9bt.pdb` (198405 bytes).
El conversor mantiene abierto el descriptor de `mkstemp`; su borrado falló en
ese proceso de Windows. Tras terminar el proceso se retiró exclusivamente ese
archivo. Se repitió la inspección dentro de TEMP y perfil de la cápsula, fijando
el entorno antes de imports y reiniciando la caché de `tempfile`.
Es una desviación de la cuarta regla nueva, declarada, no un cambio del producto.
No se distribuyen los privados, tokens ni logs con locales de las cápsulas.

## Diseño estadístico anterior al docking

Prueba exacta bilateral de signos, alfa 0,05. El mínimo significativo es 6:0,
p=0,03125; 6/35=17,14 puntos es un límite de significación, no de potencia.
Efecto mínimo declarado: 40 puntos de tasa pareada; probabilidad de discordancia
q=0,5 como supuesto explícito. Potencia exacta 94,758 % con n=35, 82,016 % con
n=25. A 80 %, los efectos detectables son 33,7 y 39,4 puntos, respectivamente.
Se conserva una tabla de sensibilidad a otros q, sin estimar q de las poses.
Se exige n>=25 y no más de 30 % de exclusiones principales.

La propuesta original de exigir seis controles completos no permitiría GO:
5I3T no se prepara sin ion y 8WGR tiene referencia no casable y CON no
representable, todo identificado sin docking. Se propone y fija antes de medir
exigir no pérdida en todos los controles evaluables y al menos cuatro de seis.
El alcance queda limitado a entradas evaluables; no se afirma que los controles
excluidos estén libres de daño. Se mantiene un gate capaz de responder sin
convertir lo no medido en evidencia. El propietario decide sobre cualquier
whitelist; no se aplica en esta rama.

El gate de pose es exactamente el de CAL: al menos tres RMSD <=2 A y todos
los top-1 cuyo RMSD cumple físicamente válidos. No se redondea antes del corte.
Los H se reconstruyen bajo MF-33-H-COR y los PASA del producto se interpretan
con el límite de los metales anterior.

### Cierre del reconocimiento

Dos preparaciones independientes: 39 SIN y 37 CON reproducibles byte a byte.
SIN coincide con catálogo en 38 de las 39 preparables. En 8UBR la variante
conserva 70 átomos adicionales de ATP A1502/A1503; todos los átomos compartidos
con el receptor del catálogo son idénticos. El catálogo declara ATP como
`site_ligand`; la ingesta de la variante USR omite ese parámetro al preparar,
y conserva otras instancias de ATP como cofactores. Se excluye antes de Vina:
SIN ya no es el receptor que se quiere comparar. No se cambia el producto.

Quedan nueve entradas excluidas antes de docking, siete principales y dos
controles: 1VKG, 5E92, 5I3T, 6S1Y, 6S1Z, 6USR, 8UBR, 8WGR y 9GKV. Hay 28
principales y cuatro controles evaluables. Los detalles y motivos acumulados
están en el protocolo; receptor no preparable y referencia no casable son
causas distintas. Los CON de 6USR y 8WGR no se preparan; no se cuentan como
infraestructura. No se sustituyen entradas.

La inspección final de máscaras carga 52 átomos metálicos de los CON
preparables: 46 pertenecen a la población de iones cercanos y seis son
adicionales. La whitelist actúa por código de residuo, no por instancia, y
retiene también esos iones del mismo tipo dentro del margen de la caja.
Ninguno de los 52 participa en las máscaras de proteína o cofactor inorgánico.
`retained_metals.json` conserva su identidad y coordenadas. No se confunden
estos 52 cargados con los 52 iones de la población original.

Se planifican 380 evaluaciones confirmatorias: 32 entradas ×2×5, más seis
entradas diagnósticas ×2×5. El piloto independiente será 1BN1, primera entrada
evaluable por orden PDB. No se ha ejecutado ninguna evaluación todavía.

## Hito 1 — prerregistro

Se inicializa el manifiesto una sola vez desde el reconocimiento commiteado
`1be6e56d`, con hipótesis, gate y referencia al protocolo. El producto bajo
medida sigue siendo f0e64086, distinto del commit que añade la evidencia.
Fuentes, CCD, entradas y preparados se sitúan dentro del experimento, bajo
`-text` ya existente; no se modifica la configuración del repositorio ni
`.gitattributes`. El CCD viaja completo. El runtime ya está declarado por
los prefijos `tools/` y `python-embed/` de `sellos_no_distribuidos.json`.

El protocolo conserva las 41 entradas, nueve exclusiones previas, 28
principales y cuatro controles evaluables, seis hipótesis diagnósticas
representables en ambos brazos, la potencia y sus supuestos. Se fija antes
del piloto y de toda evaluación real. La ausencia de una opción general
de protonación fija queda declarada; no se cambian reglas químicas del producto.

Se aplican límites de hilos a las bibliotecas de scoring para que tres cápsulas
con Vina CPU=4 no reclamen además todos los núcleos por proceso.
Durante la fase confirmatoria se congelarán HEAD y todos los archivos
versionados; sólo se escribirán salidas ignoradas en _work. El analizador,
autotest, verificación desde crudos y generador del informe ya están preparados.

### Corrección del montaje antes del piloto

El prerregistro quedó en `32e552ebe823d8e289582102d52424bce3cd6d4a`.
Dos sesiones nuevas de piloto se detuvieron antes de la primera evaluación:
el endpoint de variantes no encontraba la fuente PDB del padre comprimido.
En el reconocimiento la preparación del catálogo había materializado esa
fuente en los datos propios de la cápsula; faltaba repetir ese paso en el
ejecutor. Se cierran ambas cápsulas, sin resultados de Vina, y se añade la
misma llamada al preparador original, comprobando su hash antes de crear las
variantes. No se cambian microestados, población, gate ni producto.
El autotest del analizador pasa, incluidos denominadores y abstenciones.

El tercer arranque alcanzó Vina, pero ambas tentativas de la primera semilla
fallaron al abrir el PDBQT de salida: la ruta privada superaba MAX_PATH.
El limitador de más de 30 % de infraestructura detuvo y cerró la cápsula.
Se conserva el terminal de infraestructura, los dos errores y el STOP en
`_work/pilot/shard-1-setup-failures`; no se sobrescriben ni se analizan como poses.
Se acorta exclusivamente la ruta del perfil privado a `scripts/met01/tmp/`
dentro del mismo worktree autorizado. Se vuelve a ejecutar el piloto completo
en su directorio original ahora libre. Esta corrección del arnés ocurre antes
de la fase confirmatoria y no modifica el gate ni descarta una pose científica.

La semilla 42 de SIN completó correctamente al acortar la ruta. Después,
el contador detectó también el terminal archivado de la ruta fallida porque
su nombre aún coincidía con `shard-*`; detuvo la cápsula sin iniciar la segunda
semilla. Se preserva ese STOP y se mueve el archivo del montaje a la fase
separada `_work/pilot-setup-failures/`, fuera del glob de terminales del piloto.
El terminal exitoso se conserva y se omite al reanudar. Las variantes nuevas
se registran con el nombre de sesión para tampoco sobrescribir sus metadatos.
No se ha iniciado ninguna cápsula confirmatoria.

## Hito 2 — piloto detenido, no pareado

Con la ruta corta completaron cinco SIN, conservados aparte, y seis tentativas
CON (semillas 42–44, dos por semilla). La variante CON de 1BN1 conservaba Zn
y tenía SHA-256 e23dabe7f14c443a8df26a8ec8aa0ff5d2d3efd90370e4c5d4ee65dd6ff5c08b.
Cada ejecución CON declaró 96e0aa3134454f59a8f8bc3ef365ae8412c3c5bd3e67490988e7e204acb6fed8,
el receptor SIN. Los snapshots utilizados y sus logs de Vina verifican esos
bytes y la ausencia del metal. Preflight y ejecución declararon whitelist vacía.

La causa está en el producto f0e64086: `_coerce_hotspots` retiene únicamente
elementos dict y descarta las cadenas de la whitelist, tanto en preflight
como en el snapshot del pipeline. Se ejecutan sus dos funciones puras
originales por extracción AST, sin alterar el producto: Zn, Mg, Ca y K se
pierden, mientras que un dict de hotspot se conserva. No se manipula la base
de datos para eludirlo. El fallo de receptor, no un fallo de Vina, causó tres
terminales con la etiqueta genérica INFRASTRUCTURE_FAILURE del arnés.
Al ser 3/8 (37,5 %), el limitador cerró la cápsula a las 22:10:34 UTC.

Decisión autónoma: no lanzar las 380 evaluaciones restantes con un brazo
inválido, ni sustituir el camino API por otro después de ver poses. MET-01
se cierra INCONCLUSIVE, conforme a §4.1 y §4.8. Un arreglo y nueva medición
son MET-01-R1, con otro encargo. No se cambian población, potencia ni gate.
El piloto pareado queda incompleto y no se infiere de él una previsión de
tiempo. Potencia condicional del n previsto de 28: 87,240 %, con delta=0,4
y q=0,5; n final válido=0, así que ninguna prueba es aplicable.

El productor ejecutado se conserva byte a byte en `source/executed/`.
`piloto/per_attempt.jsonl` reconstruye los once intentos completados, con
RMSD de todas las poses, especie, receptor esperado/usado, validez, distancias
a la posición del ion del cristal (declarado ausente), logs y hashes. No se
tratan las tentativas repetidas como semillas independientes. Los dos fallos
MAX_PATH, los STOP y las sesiones detenidas originales también se versionan;
los perfiles, tokens, bases privadas y logs con locales no se distribuyen.

## Hitos 3 y 4 — confirmación no iniciada y análisis del cierre

No hubo fase confirmatoria ni intervalo confirmatorio congelado. HEAD se
comprobó antes de cada evaluación del piloto; las correcciones anteriores
se hicieron con sus cápsulas cerradas. Ningún crudo ni terminal se reescribió.
El merge confirmatorio tiene cero filas y excluye todo el piloto. El análisis
determinista retorna INCONCLUSIVE, cero pares y `test_applicable=false`:
el p=1 convencional del algoritmo para cero discordantes no es una prueba.
El autotest demuestra RMSD cero del cristal, exclusión de una traslación de
3 Å, decisiones sintéticas, controles ausentes y denominadores de exclusión.
`verify` reconstruye esa confirmación vacía; la auditoría independiente del
piloto verifica los once crudos y la pérdida real de whitelist.

Se corrige antes del sello la metadata de dependencias del manifiesto:
`init` corrió con Python del sistema 3.14.3, pero la medición usa 3.11.9 y
los paquetes congelados en `entrada/runtime.json`. Se conserva el estado
git real de la creación; producto y prerregistro tienen sus hashes propios.

## Hito 6 — informe de la detención

Paper y auditoría cubren las 41 entradas, sus nueve exclusiones previas y la
abstención por comparación detenida en las demás. Ningún guion equivale a
pose fallida. No se atribuye NO_GO científico al ion ni se propone whitelist.
No se midieron controles, formas diagnósticas ni frecuencia de His en CON.
La ceguera de las máscaras de PoseBusters frente a iones Meeko ATOM queda
declarada, igual que los límites de potencia, de independencia entre familias
y de redocking. La publicación se conserva también bajo el atributo -text
del experimento para sellar sus bytes sin tocar .gitattributes.

## Hito 5 — prueba previa al sello

La prueba comprueba 265 archivos científicos ya versionados: bytes idénticos
al blob de HEAD y atributo text unset existente. Ningún JSON científico
contiene claves de credenciales de sesión. Se guarda el inventario con SHA-256
en `entrada/versionado_antes_del_sello.json`; no sustituye la comprobación
de schema. La prueba excluye su propio archivo, que se añade a continuación
y también se sella. Los privados permanecen ignorados, fuera del inventario.
Se publica el informe antes del sello para incluir sus copias -text en él.
El resto del producto, catálogo, .gitattributes y tabla de no distribuidos
coinciden con f0e64086. No se alteró ningún otro experimento.

El validate formal se ejecuta tras commitear la prueba previa y comprobar el
estado incluyendo archivos nuevos: árbol limpio. El seal se ejecuta una sola
vez desde ese estado y registra 249 datasets, 15 assets y tres binarios,
267 rutas canónicas, ninguna absoluta ni `../`. Se commitea el sello antes
de ejecutar finish para volver a partir de un árbol limpio. La duración
de medición declarada es 626 s, desde el primer arranque de piloto hasta
el cierre final; no es el tiempo invertido en reconocimiento o publicación.

### Comprobación del cierre y del clon limpio

`finish` parte del sello commiteado y de un árbol limpio, fija INCONCLUSIVE
y 626 s; el cierre está en `9e698c1d`. Con el Python embebido 3.11.9,
`experiment_manifest.py validate MET-01-ION-DEL-SITIO` y
`validar_sellos.py --check` pasan en el worktree con sus montajes:
169 experimentos sellados, cero distintos y cero ausentes.

Se crea el clon local limpio de ese cierre en
`D:/moldesign-build/scripts/tmp/met01-clon`, sin hardlinks ni perfiles privados.
Ejecuta el mismo Python embebido aprovisionado fuera del clon. Pasa el
guardián global antes y después de reconstruir: 169 sellos, cero distintos,
cero ausentes; 15 referencias a binarios ausentes se reconocen como RUNTIME
declarado, no como archivos verificados. El autotest pasa. `pilot_stop.py`
reconstruye los once intentos desde archivos versionados, comprueba sus
logs/snapshots y devuelve cinco SIN válidos y seis CON con receptor inválido.
`verify` reconstruye la confirmación vacía de forma determinista. El clon
permanece limpio incluyendo archivos nuevos; no necesitó ninguna cápsula.
Los registros locales de comprobación quedan ignorados en `_work/verification/`.

Las cuatro reglas nuevas se revisan al cierre: potencia calculada antes de
Vina; confirmación no iniciada, por lo que no existió intervalo confirmatorio
que congelar; 267 rutas canónicas y prueba de versionado; una desviación de
alcance, el temporal propio de la primera inspección PB fuera de scripts/docs,
retirado y documentado arriba. Los montajes del runtime se retiran con rmdir
sin recursión y se conservan sus destinos originales. No se toca el producto,
el catálogo, la configuración, otros experimentos ni la rama pública.
