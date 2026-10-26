# Traza de Vina conservada con cada evaluación

La evaluación ejecuta Vina 1.2.7 instrumentado y conserva su búsqueda real
antes de borrar el directorio temporal. No añade controles a Evaluación.
El protocolo de la corrida guarda `execution_provenance.search_trace` y
Moldex congela ese objeto en su snapshot, junto con los hashes de entradas,
poses SDF y archivo ZIP. No se reconstruyen trazas de corridas históricas.

El ZIP bajo `runs/vina-search/<sha256>.zip` contiene las métricas de todos
los pasos de la réplica 0, sus geometrías retenidas muestreadas, las poses
finales PDBQT y los contadores de **todas** las réplicas. Las geometrías
PDBQT tienen precisión de tres decimales; la energía durante la búsqueda
es su objetivo interno, no la afinidad final ni energía libre experimental.
Se comprueban hashes, secuencia de pasos, aceptación, contadores, energías
finitas y correspondencia entre cada geometría y su paso.

La captura deriva de la solución de Molcy original. Se corrigió una
interferencia del observador: al escribir una instantánea se copia el
modelo y se coloca la configuración retenida **en la copia**, conservando
el modelo vivo que utilizará la próxima mutación. No consume números
aleatorios adicionales. La clave de caché incluye el hash del binario;
una entrada sin traza íntegra se vuelve a calcular con el nuevo motor.

Molcy carga hasta doce geometrías muestreadas de ese ZIP y las poses finales
de la corrida, con los mismos receptor, caja y semilla. Cambia entre estados
registrados; no interpola una trayectoria física ni representa dinámica
molecular. La escena se ofrece únicamente con evidencia íntegra y un motor
incluido compatible. La exportación del motor sigue siendo por subproceso
y archivos; el backend no importa sus módulos GPL. El cierre de marca sigue
siendo obligatorio.

El motor incluido procede de la rama `codex/busqueda-interna-vina` de
`moldesign-molcy`. La escena nació en el commit público
[`9e9c48f`](https://github.com/srcacahuate619/moldesign-molcy/commit/9e9c48f44c7758ce7cc289530cfa99638ce3075f)
(publicado con autorización del propietario) y su encuadre y su capa de títulos
se corrigieron en `83c6ad4`; la revisión de Resultado y Receptor, en `3147090` (ambos publicados); las interacciones de Resultado y Búsqueda, en `f836a05` (todos publicados). Se incorpora mediante
`stage_molcy_motor.py`, sin editar la copia vendorizada.

## Compilación y procedencia

`third_party/vina_trace/` conserva las fuentes Apache-2.0 de Vina 1.2.7,
commit `8eb40404f4f45608acb3b01427587ac049f27c1f` (el tag `v1.2.7`), con
cuatro archivos modificados para la instrumentación y uno, `utils.cpp`, para
que lea los ligandos como la referencia (ver «Ligandos con CRLF de 4096 bytes
o más», abajo). `NOTICE.md` declara las dos cosas. Se compila con MSYS2
GCC 16.1.0, Boost 1.91.0, `-O2`, sin opciones fast-math. El programa
instrumentado está junto al Vina original, que se conserva como referencia.

```powershell
python-embed/python.exe scripts/build_vina_trace.py --compiler C:/msys64/mingw64/bin/g++.exe
python-embed/python.exe scripts/build_vina_trace.py --check
```

El manifiesto identifica binarios, fuentes, compilador y licencias. Las
dependencias estáticas incluyen Boost, runtime GCC con GCC-exception-3.1,
winpthreads y CRT MinGW; sus textos viajan en `tools/vina/trace-licenses/`.
El empaquetado verifica la fuente **y** el artefacto staged, y el SBOM
declara el ejecutable instrumentado y esas dependencias. La app no necesita
compilador ni conexión de red para registrar la traza.

## Medidas del 2026-10-05

La comprobación nativa con dos semillas (42 y 7, CPU=1, dos réplicas,
paracetamol de la fixture) produjo los mismos bytes de poses al activar o
desactivar la captura. También se reprodujeron exactamente los bytes del
PDBQT completo de la evaluación real 3F75/aspirina, CPU=1, semilla=42,
exhaustiveness=8, usando las mismas entradas con captura desactivada.
Su traza conservó 128520 pasos agregados y 62 geometrías muestreadas de la
réplica 0. Se recuperaron sus archivos tras reiniciar el backend.

El cambio de compilación **sí** modifica los resultados respecto al binario
anterior, aunque la captura activada/desactivada no los modifica en las
condiciones anteriores. En el caso E2E 3F75, PRO pasó de -5.656 a -5.634
kcal/mol y normal de -4.879 a -4.886. Receptor preparado, ligando de entrada,
caja y semilla se mantuvieron; los hashes de poses cambiaron. El golden E2E
versión 4 identifica la nueva compilación y conserva afinidades y hashes
anteriores. No se debilita la comparación exacta ni se modifican artefactos
científicos sellados. Esto valida captura y persistencia en esos casos;
no constituye una nueva validación científica de Vina en una cohorte.

Blender 5.2.2 con Molecular Nodes construyó el paquete recuperado con nueve
poses y los estados seleccionados. Su QC declaró una alerta de oclusión
parcial del ligando durante la órbita final, sin abortar la construcción.

El runtime staged pasó las dos evaluaciones reales (PRO y ruta por defecto),
la recuperación tras reiniciar y la comparación exacta con los nuevos goldens.
Al guardar ambas corridas en Moldex, `/molcy/fuentes` ofreció `resultado`,
`receptor` y `busqueda` para cada una. El smoke de producción pasó 22/22 y
`verify:desktop-runtime` verificó dependencias y frescura del backend.

Se produjo un MP4 real de Búsqueda con Blender 5.2.2, EEVEE y GTX 1660 SUPER:
90 fotogramas de escena a 30 fps y cierre de 108 fotogramas, duración total
6,6 s. El backend acreditó el cierre, el renderizador y el hash del MP4
`4255508ed5974cdb2aa1174dd74d4d2047dd7d757887c07d593aec76276f467a`.
Se mantuvo la reserva de 1536 MiB de VRAM y un límite nativo de CPU del 41,66%.
Su QC avisó que la aproximación sólo veía el 11% del sitio; no es una validación
de calidad visual para todos los receptores. Una prueba anterior con presupuesto
de 640 MiB se detuvo por la guarda de VRAM; con el máximo permitido se completó.
La prueba de MP4 completo en CPU no se completó: un solo fotograma tardó 145 s
y se canceló el proceso propio. Sí se construyó la escena en CPU.

## Corrección posterior de fuentes y VRAM (2026-10-05)

La API ofrecía las escenas correctas, pero el validador del frontend todavía
admitía sólo `resultado` y `receptor`. Una corrida con `busqueda` rechazaba la
respuesta completa y ocultaba también los receptores. Se añadió ese valor al
contrato, conservando el rechazo de escenas desconocidas. Las pruebas anteriores
de la página simulaban la API; ahora la respuesta poblada atraviesa también el
validador real y el smoke verifica el frontend exportado con esa misma condición.
El smoke anterior de 22/22 usaba una base temporal vacía y no detectaba este fallo.

Por decisión del propietario, los renders nuevos dejan la VRAM a Blender: no hay
selector de presupuesto ni requisito de telemetría NVML para habilitar GPU. El
backend sólo vigila un presupuesto si un cliente anterior lo envía explícitamente.
Los límites CPU se mantienen, también en GPU. La medición de vídeo y presupuesto
descrita arriba corresponde al comportamiento anterior; no demuestra una cuota
de asignación de memoria para Blender.

Verificación de esta corrección: 403 pruebas de backend Molcy y su frontera,
43 pruebas de frontend (contrato, página y CPU), y compilación de escritorio con
TypeScript. El backend staged coincide archivo por archivo con la fuente. El
smoke actualizado pasó 28/28 con el runtime y export reconstruidos; cinco
comprobaciones nuevas ejercitan las fuentes pobladas y GPU sin telemetría en el
frontend real mediante respuestas de prueba, y otra comprueba la política
automática en la respuesta real del backend empaquetado.

## Encuadre de la escena Búsqueda y capa del título (2026-10-05, `83c6ad4`, publicado)

El vídeo de Búsqueda de 1J38 (9:16) salió con la cámara tan cerca que el ligando
cubría el 100 % del ancho a 1,07 unidades del pivote y se cortaba por arriba, sin
sitio activo a la vista, y con los rótulos por detrás de la molécula. Medido sobre
su `.blend`:

- `encuadre.distancia` suma la profundidad de cada punto al pivote; con el ligando
  entre la cámara y el pivote (la caja) la distancia sale corta. Se añadió
  `distancia_visible`, que la resta. La escena `x` planifica un plano por beat con
  la geometría real —sitio, caja, y un plano por estado y por pose con sus vecinos,
  suavizado— y elige el ángulo midiendo si el receptor tapa la esfera del sitio.
  En los 90 fotogramas muestreados de 1J38 ningún punto de los estados ni de las
  poses visibles cae fuera del cuadro. Un ligando de ~6 Å ocupa entre el 11 % (la
  caja entera) y el 58 % del ancho; es una geometría real, no un valor elegido.
- La capa del título sólo apagaba mallas con `hide_render`, animado en el ligando
  (la animación gana al evaluarse) y sin efecto sobre las curvas (caja y silueta
  anterior), así que se dibujaban en esa capa y tapaban el texto. Ahora se apaga
  toda la geometría y se retira su acción durante la pasada.
- La caja entra en el beat `caja`, no en la retirada; la esfera de evidencia sigue
  entrando en la retirada porque su grano tapa el receptor. Las líneas de los
  rótulos de pasos se parten a un máximo de 36 caracteres.

No se renderizó el vídeo completo con el motor corregido: se midieron los 90
fotogramas muestreados (contención) y se renderizaron fotogramas sueltos de los seis
beats. Los rótulos de la escena siguen escritos en español aunque la interfaz esté
en inglés (sólo el cierre sigue el idioma).

## Revisión de Resultado y Receptor (2026-10-05, `3147090`)

Se midieron las dos escenas de `sitio_activo` sobre 4CA8 (9:16), con los defectos del
vídeo de Búsqueda como lista de comprobación:

- **Ligando recortado / sitio fuera de cuadro:** no en Resultado (0 puntos fuera de
  cuadro; ocupa hasta el 43 % del ancho). Pero la causa de fondo estaba también ahí:
  `maestro.medir` calculaba el primer plano con `encuadre.distancia`, que subestima
  cuando el sujeto queda entre la cámara y el pivote; con su margen amplio no
  recortaba (pedía 2,27 y el ligando cabe con 1,74), pero era una trampa latente.
  `distancia_primer_plano` toma el mayor de esa fórmula y de la corregida con un 15 % de
  aire: D_cerca idéntica antes y después en 4CA8 (2,27 y 3,17), y un plano que
  recortaba se abre.
- **Texto detrás de la molécula:** no. El título sólo va en el plano general, cuando el
  ligando no está, y el rótulo «Vina top-1» es 3D por diseño. La capa del título ya
  apaga toda la geometría (`83c6ad4`), así que tampoco puede colarse.
- **Sujeto tapado (mismo síntoma, otra causa):** sí en Resultado. El mejor de los 36 arcos
  de la retirada (giros de 90° a 150°) tenía visibilidad mínima 0,09: en el fotograma 320
  una cinta oscura cubría media molécula. Con giros cortos (30°–60°), que sólo se prueban
  cuando ningún giro grande llega a 0,40, el mínimo es 0,97 y el ligando se ve entero
  durante toda la retirada. Los arcos que ya eran buenos no cambian.
- **Receptor sin sujeto:** la alerta `arco_ocluido` (0,25) era falsa: los rayos iban a
  átomos del propio receptor. Sin sujeto, el arco y la órbita no se miden y el acta lo dice.

**No se cambió** el recorrido estructural de Receptor: la cámara pasa entre cintas del
interior y no marca la caja registrada pese a que su descripción dice «caja registrada».
Es una decisión de producto, no un defecto de las medidas anteriores.

## Interacciones ligando–receptor en Resultado y Búsqueda (2026-10-05, `f836a05`)

La mejor pose de Resultado y cada una de las nueve poses de Búsqueda enseñan sus
interacciones con el bolsillo: una línea punteada (polar) o de trazos (apolar) hasta
el residuo y un rótulo con residuo, clase y distancia medida (p. ej. `TYR507 / POLAR
3.01 Å`). Las clases se distinguen por el color de la línea y del rótulo, pero ningún
texto nombra el color: un nombre de color puede leerse como el de un elemento. La etiqueta
por pose, que antes nombraba los colores, pasa a «POLARES n | APOLARES n».

- **Medida:** por distancia sobre las coordenadas del paquete. Polar = proximidad N/O de
  2,4 a 3,5 Å; apolar = carbono apolar del ligando contra una cadena lateral de 2,8 a
  4,5 Å. Un contacto por residuo y clase, tres como máximo de cada una, y los hotspots
  del catálogo primero si existen. **No es un PLIF:** sin protonar, sin ángulos
  donante–H–aceptor; no son puentes de hidrógeno confirmados ni energías de unión (las
  notas del acta lo dicen y el acta lista cada interacción).
- **Antes:** Búsqueda medía sólo contra los hotspots del catálogo, y 1J38 y 4CA8 no traen
  ninguno, así que las nueve poses salían con «0 polares, 0 apolares». Ahora se mide
  contra todos los residuos del bolsillo (1J38, pose 1: HIS337 2,90 Å, HIS497 3,06 Å,
  TYR507 3,10 Å polares; PHE441 3,39 Å, THR364 3,48 Å, TYR507 3,58 Å apolares).
- **Rotulación:** los rótulos 3D van en la capa del título (se rinden aparte y se
  componen por encima), así que ninguna cinta ni el propio ligando los tapa. Tamaño
  constante entre planos, sin pisar el texto de pantalla ni al ligando. La cámara que
  sigue al ligando en Búsqueda no cambia; en Resultado y Búsqueda el ángulo se recalcula
  porque los residuos de contacto ahora se dibujan y la medida de oclusión los ve.
- **Límites:** en 9:16 y con seis rótulos por pose quedan algunos solapes entre
  rótulos o con líneas, sobre todo en el primer plano; los guiones largos cruzan el
  cuadro. No se renderizó un vídeo completo con las interacciones: se midieron las
  escenas y se renderizaron fotogramas sueltos a resolución completa.

## Ligandos con CRLF de 4096 bytes o más (2026-10-10)

La evaluación de 1HSG con indinavir terminaba en «Vina exit code: 1». La traza
rechazaba un PDBQT que `vina.exe` acoplaba sin problema:

    PDBQT parsing error: Unknown or inappropriate tag found in flex residue or ligand.
     > ENDBRANCH  39  41

**Causa.** No era el parser (es el de upstream y leía las 89 líneas sin error)
ni la profundidad de las ramas. `get_file_contents` (`src/lib/utils.cpp`)
reserva `tellg()` bytes y lee el archivo en modo texto. Meeko escribe el PDBQT
con CRLF en Windows; el modo texto convierte cada CRLF en LF, así que `read()`
devuelve tantos caracteres menos como líneas tiene el archivo. En el `vina.exe`
de referencia ese resto del búfer queda a cero, y el parser ignora una línea de
ceros a propósito (`str[0] == '\0'`, «potential issues on Windows»). En esta
compilación MinGW, desde 4096 bytes de archivo, el resto conservaba bytes viejos
del propio archivo —su final—, y el parser los leía como líneas nuevas detrás de
`TORSDOF`. Medido con un programa mínimo y el mismo compilador: hasta 4095
bytes la cola son ceros; desde 4096, bytes del archivo.

**Arreglo.** Una línea en `utils.cpp`: se pone a cero la parte del búfer que la
lectura no llenó, como hace la referencia. La línea de ceros sigue viajando al
contexto del ligando y a las poses de salida, igual que en `vina.exe` y que
antes en esta compilación para los archivos pequeños.

**Alcance, medido** con ligandos preparados como el producto
(`_construir_conformero` + `mk_prepare_ligand`) y `--score_only --autobox`:

- Muestra aleatoria de 400 ligandos de PDBbind (semilla 20261010): 345 se
  prepararon (49 SDF que RDKit no lee y 6 rechazos del conformador quedan
  fuera). La traza anterior fallaba en **51 (14,8 %)**; la corregida en 0, y
  `vina.exe` en 0. La corregida da la misma energía que `vina.exe` en los 345.
- El criterio «CRLF y ≥ 4096 bytes» separa los fallos sin ninguna excepción. La
  profundidad de ramas no: fallaban ligandos con profundidad 3 a 10 y pasaban
  otros con 8. En átomos del PDBQT el umbral cae hacia 39–40, según la longitud
  de los REMARK.
- Ninguno falló en silencio: con 4096 bytes o más la traza anterior terminaba
  siempre con error (55 «Unknown or inappropriate tag», 2 «Atom number 40 is
  missing in this branch» cuando la cola empezaba por `BRANCH`).
- Casos nombrados: indinavir, Leu-encefalina, ciclo(RGDfV) y los inhibidores de
  proteasa de PDBbind 2BQV, 1HVR y 1OHR fallaban; 3S43, 1HPV y 3NU3 (4073
  bytes), GGG y pentaglicina pasaban. Con la corregida pasan todos.

**Sin cambio donde ya funcionaba.** En los 15 ligandos del panel de Preparación
que la traza anterior acoplaba (docking real, semilla 42, exhaustividad 2,
`--cpu 1`), la corregida produce los mismos bytes de poses, del CSV de pasos y
de los estados retenidos. En los 299 de la muestra que ya pasaban, la misma
energía. El binario nuevo (`0e012590…`) difiere del candidato validado sólo en
la marca de tiempo del PE (4 bytes): con este toolchain cada compilación cambia
el SHA-256 por esa marca, aunque el resto de los bytes coincida.

Prueba: `backend/tests/test_vina_trace_lee_pdbqt_crlf.py`, con el PDBQT que
escribió el pipeline para 1HSG (`af30b5ba…`); falla con el binario anterior.
