# 73 — Lo que rompe en un Windows limpio

**Fecha:** 2026-09-02
**Origen:** el defecto D2 del doc 71. Al buscar su causa apareció que el generador
de PDF pedía su fuente en `/usr/share/fonts/truetype/dejavu/…` — una ruta de
**Linux**. En Windows nunca existe, caía a Courier, y de ahí las viñetas
extraídas como `U+007F`.
**Estado:** siete hallazgos corregidos y verificados, tres riesgos descartados
con evidencia.

---

## 0. La firma que se persiguió

> Código escrito o probado en otro sistema —o en **esta** máquina— que en un
> Windows limpio **degrada en silencio**.

Silencio es la parte importante. Un `ImportError` se ve; una ruta que no existe
dentro de un `try/except` no, y el producto sigue funcionando peor sin que nadie
lo sepa. Los siete hallazgos son de ese tipo: ninguno tumba la aplicación, y por
eso ninguno se había visto.

**Una advertencia sobre el método.** El fallo se manifiesta en una máquina que no
es ésta, así que no se puede reproducir desde dentro. Donde se pudo medir de
verdad —el intérprete que se instala, las fuentes del sistema, el modelo de CPU—
está el número; donde no, se vigila la causa y se dice que es una predicción.

---

## 1. La codificación por defecto — **el más grave**

`python-embed` es Python **3.11.9** y arranca con la página de códigos del
sistema. Medido sobre ese intérprete, no supuesto:

| | sin `PYTHONUTF8` | con `PYTHONUTF8=1` |
|---|---|---|
| leer un UTF-8 sin `encoding=` | **contenido corrompido, sin excepción** | correcto |
| escribir una cadena con `→` | **`UnicodeEncodeError`** | correcto |
| `sys.stdout.encoding` | `cp1252` | `utf-8` |

El backend tiene **87 llamadas de texto** sin `encoding=` explícito. La lectura
silenciosa es la peor de las tres: un PDB o un JSON con un acento vuelve mal y
nadie se entera. Y como el `stdout` del backend va al archivo de log, un solo
`print` con una flecha tumbaba la línea.

**Corregido en un sitio**, no en 87: `spawn_backend` es donde se define el
entorno del proceso, y los subprocesos —Vina, los sidecars, MM-GBSA— lo heredan.

> Durante esta misma auditoría el fallo se reprodujo solo: un `print` de
> diagnóstico con `→` levantó `UnicodeEncodeError` en la consola. La
> demostración vino gratis.

---

## 2. MM-GBSA no podía funcionar en ninguna máquina

```python
sys.path.insert(0, r"D:\moldesign-build\backend")
```

En `mmgbsa_subprocess.py`, que corre como **proceso aparte** y necesita el
backend en `sys.path`. En cualquier instalación real ese directorio no existe, el
import de `services.chemistry.molchamb_v2` fallaba, y el `except` lo devolvía
como `{"error": "No module named 'services'"}`.

Es decir: **MM-GBSA sólo funcionaba en la máquina de construcción**, y fallaba
con un mensaje que no apunta a la causa. Ahora la raíz se deduce de la posición
del propio archivo.

---

## 3. `wmic` ya no existe

Comprobado **en esta misma máquina** (Windows 11 build 26200): `where wmic` no lo
encuentra y `subprocess.run` levanta `FileNotFoundError`. Microsoft lo retiró.

Como la llamada vivía dentro de un `except Exception`, el fallo era invisible: el
modelo de CPU caía al respaldo `«6C/12T CPU»` y eso acababa en la sección de
entorno del dossier.

```
antes:   cpu_model -> '6C/12T CPU'
después: cpu_model -> 'AMD Ryzen 5 5500'
```

Se lee del registro, que no lanza procesos y no depende de una herramienta que
Microsoft pueda volver a quitar.

---

## 4. Una corrida terminada que se pierde al limpiar

En Windows no se puede borrar un archivo que alguien tenga abierto. Dentro de
esos directorios temporales corren procesos hijos —Meeko, Vina, Open Babel— y el
antivirus escanea lo recién escrito.

Sin `ignore_cleanup_errors`, la limpieza levanta `PermissionError` **después de
que el trabajo haya terminado bien**: se pierde una corrida completa por no poder
borrar un temporal. Ocho sitios, cuatro de ellos en el camino caliente del
docking. Dejar un archivo suelto es mucho mejor que perder el resultado.

---

## 5. La fuente del PDF, ahora sí

Medido extrayendo el texto del PDF generado:

```
Courier / Helvetica (Type1)    «•» → U+007F     «·» → «·»
Consolas / Courier New (TTF)   «•» → «•»        «·» → «·»
```

Era la fuente incorporada la que perdía el glifo. Se arreglan **las dos cosas por
separado**: la viñeta pasa a ser el punto medio, que sobrevive en todos los
casos, y la fuente se busca donde puede estar (`consola.ttf` y `cour.ttf` existen
en todo Windows desde Vista). Depender de que un glifo exista es una fragilidad
que no hace falta correr.

**Licencia comprobada, no supuesta:** ambas fuentes tienen `fsType = 0x0008`
—*editable embedding allowed*—, así que incrustar un subconjunto en el PDF está
permitido.

---

## 6. Un nombre de usuario que viajaba en el producto

```python
DEFAULT_DB = Path(r"C:\Users\Johan Amezcua\MolDesign\data\moldesign_local.db")
```

En `backend/scripts/reclassify_targets.py`. El empaquetador copia `backend/`
**entero**, `scripts/` incluido, así que ese nombre se instalaba en cada máquina
y la ruta no existía en ninguna que no fuera aquélla. Ahora se deriva de
`LOCALAPPDATA`.

---

## 7. Rutas muertas de un repositorio anterior

`services/xtb/service.py` buscaba xTB en `D:\moldesign-app\…`, un directorio de
una versión anterior del repositorio. En otra máquina apunta a la nada —o peor, a
lo que esa persona tenga en su disco D—. Las candidatas relativas de arriba son
las que de verdad resuelven una instalación.

---

## 8. Lo que se comprobó y **no** es un riesgo

Vale la pena dejarlo escrito: son las hipótesis que más asustaban.

| hipótesis | veredicto |
|---|---|
| **Falta el runtime de C++** | **Descartado.** `MSVCP140.DLL` la piden 194 binarios y **sí viaja** en el paquete, junto a `VCRUNTIME140`, `VCRUNTIME140_1`, `VCOMP140` y `LIBIOMP5MD`. Se inspeccionaron 611 binarios nativos leyendo su tabla de importaciones |
| **Rutas de más de 260 caracteres** | **Descartado.** El camino más largo que la aplicación construye —un hash de 64 caracteres bajo `LOCALAPPDATA`— llega a **141**. Ni con un nombre de usuario largo se acerca al límite |
| **Módulos sólo-Unix** (`fcntl`, `pwd`, `resource`) | **Ninguno.** Tampoco `SIGKILL` ni `os.fork`; los `.kill()` que hay son de `subprocess`, que en Windows funciona |
| **Las estructuras no se empaquetan** | **Descartado.** `bundle_helper` copia `data/targets` y los dos catálogos |
| **`multiprocessing` con `fork`** | **No se usa** en el backend |

Y dos que **degradan sin romper**, anotados sin exagerar:

- `GET /anti-targets` cae al panel por defecto si la base no responde. Ahora al
  menos **lo registra**.
- El nombre de archivo de una cohorte no filtra los nombres reservados de Windows
  (`CON`, `PRN`, `NUL`…). Sólo se usa como columna y como ruta **dentro de un
  ZIP**, así que la molestia aparecería al extraerlo, no en la aplicación. El
  saneador del frontend sí los filtra.

---

## 9. Dos pruebas que escribí mal, y por qué se quedan escritas

**La primera** prohibía el patrón `except Exception: pass` en un módulo entero.
Dio cinco falsos positivos —limpiezas de directorios temporales y lecturas de
archivo con alternativa, donde tragar el fallo *es* lo correcto— y me habría
llevado a ensuciar código sano para callar la prueba.

**La segunda** buscaba rutas de Linux por texto y marcó `chem/properties.py`, que
tiene tres candidatas **incluida la de Windows**. Se reescribió con AST: una ruta
POSIX dentro de una lista de dos o más elementos es una candidata legítima; lo
que no puede estar es una ruta de Linux **sola**. Con ese criterio la prueba
encontró la de `pdf_generator.py`, que era la de verdad.

En los dos casos el error fue el mismo: **prohibir una forma sintáctica en vez de
exigir una propiedad.**

---

## 10. Lo que queda, y lo que no cubre esto

Esta auditoría mira el **código**. No cubre:

- que el instalador esté **firmado** (SmartScreen bloqueará un ejecutable sin
  firma en la primera ejecución);
- los pendientes del doc 70 que siguen abiertos: los lanzadores de pip con la
  ruta del constructor incrustada, `AutoDock-Vina-GPU` muerto en el instalador,
  el runtime de MSVC sin declarar en `THIRD_PARTY_NOTICES.md`;
- una ejecución real en una VM limpia, que es lo único que confirma de verdad
  todo lo anterior.

`backend/tests/test_windows_maquina_limpia.py` vigila las causas para que no
vuelvan. Es estático a propósito, y lo dice en su docstring.

backend 1391 pruebas, frontend 725, `cargo check` limpio.

---

# Segunda parte — la instalación limpia, simulada de verdad

**Fecha:** 2026-09-03
**Origen:** el §10 dejaba abierto lo único que confirma todo lo anterior —«una
ejecución real en una VM limpia»—. Esto es esa ejecución, con el matiz de que se
simula: almacenamiento del usuario vacío, estructuras sembradas desde las
`.pdb.gz` que viajan en el instalador y el backend servido desde el runtime
staged, que es literalmente lo que se instala.

**Encontró tres defectos que ninguna de las 1387 pruebas veía**, los tres en el
mismo camino: la preparación del receptor.

## 11. `prepare_target` moría con un `NameError`

En la última rama de la función, justo antes de guardar el `.pdbqt`:

```python
log.info("receptor PDBQT validado", pdb_id=pdb_id, chain=etiqueta_cadena, ...)
```

`etiqueta_cadena` es una variable local de `_filter_pdb_content`. Llegó en
`2d76046` —el receptor multicadena— y **cada preparación de receptor terminaba
en `NameError`** desde entonces. La línea siguiente, la que guarda el archivo,
nunca se ejecutaba.

**Por qué no se veía.** Ninguna prueba ejecutaba `prepare_target` de punta a
punta: entraban por `_filter_pdb_content`, por `preparer_multichain` o por un
`AsyncMock`. Y en esta máquina tampoco se nota, porque `~/MolDesign` lleva meses
de uso: el `.pdbqt` ya está en disco y la función vuelve por la caché antes de
llegar a esa línea.

> En una instalación nueva no hay caché. **Todo acoplamiento moría en el primero.**

## 12. La unidad biológica se generaba desde una copia ya filtrada

`prepare_target` escribe una copia del receptor filtrada por cadena para el
rescoring, y **acto seguido volvía a leerla como origen**:

```python
if shared_pdb_path.exists():
    raw_content = shared_pdb_path.read_text(...)   # <- la que acaba de escribir
```

Esa copia sale de `_filter_pdb_content`, que sólo emite `ATOM`/`HETATM`: **no
conserva los `REMARK`**, y sin `REMARK 350` no hay matrices `BIOMT` que aplicar.
El trabajo del §24 del doc 72 —generar la unidad biológica— quedaba anulado en
el producto para los quince objetivos cuyo sitio se forma con una cadena que
**sólo existe en el ensamblaje**.

Medido sobre 5VA1, con almacenamiento vacío:

```
                        antes            ahora
origen                  4407 átomos      8814 (ensamblaje)
recorte al sitio        cadena A sola    A + B
receptor preparado      1884 átomos      2685
```

**Por qué no se veía aquí.** `data/target_library` —material de esta máquina,
que `bundle_helper` **no empaqueta**— adelanta una estructura completa para
catorce de los quince. 5VA1 es el único sin copia ahí, y por eso es el que
recorre en esta máquina el mismo camino que recorrería instalado. Es el patrón
del §0 otra vez: *el entorno donde se construye tiene algo que el del usuario
no*.

Dos correcciones más en el mismo sitio:

- **El origen es siempre el crudo depositado** cuando existe. Es lo que siembra
  el instalador y lo que escribe la ingesta de un receptor subido, así que la
  regla vale igual para el catálogo y para lo que traiga el investigador.
- **La copia para el rescoring se escribe desde el ensamblaje**, y sólo en el
  almacenamiento del usuario. `get_target_pdb_path` puede resolver al directorio
  del programa, que instalado es de sólo lectura —y con privilegios sería peor,
  porque mutaría un recurso instalado—. Escribiendo allí, durante esta misma
  auditoría, se sobreescribió un archivo de `data/target_library` de esta
  máquina; se restauró desde el `.pdb.gz` empaquetado y la regla quedó escrita.

## 13. «No hubo nada que recortar», leído como «no hay nada cerca»

`trim_to_pocket` termina así:

```python
return (out, n_kept > 0 and n_kept < n_total)
```

Ese booleano vale `False` en **dos situaciones opuestas**: cuando ningún residuo
cae dentro del radio —un defecto real, la caja no corresponde a la estructura— y
cuando **todo el receptor cabe dentro del radio**, que no tiene nada de malo.
`_recortar_al_sitio` interpretaba las dos como la primera y abortaba.

La víctima es el receptor pequeño de interfaz. 1C6X —proteasa del VIH-1, 1514
átomos— tiene **1510 de ellos a menos de 30 Å del centro**, y el centro está
exactamente sobre el centroide de su ligando co-cristalizado, con la cadena más
cercana a 3,98 Å. Su preparación moría con un mensaje que acusaba a su propia
caja:

> «El centro (39.324, 28.658, 18.489) no tiene ningún residuo de las cadenas A+B
> a 30.0 Å. O el centro del sitio está mal, o no corresponde a esta estructura.»

Ahora el criterio se **mide** —cuántos átomos hay dentro del radio— en vez de
deducirse de un booleano que responde a otra pregunta. El mensaje de error sigue
existiendo, para cuando de verdad no haya nada.

## 14. Y una cuarta cosa, que no es un defecto sino una ausencia

Si falta una cadena del sitio tras el recorte, **no pasaba nada**: quedaba una
línea de log —`cadenas_conservadas=['A']` frente a `cadenas_pedidas=['A','B']`—
y la preparación seguía. Vina acopla contra media cavidad y devuelve una
afinidad con la misma cara que una buena. Ahora se detiene con
`step="site_chains_missing"`.

## 15. La siembra de estructuras llega tarde a su propio arranque

Con los cuatro anteriores corregidos, el gate de Evaluación sobre el runtime
staged seguía fallando, y con un mensaje conocido —el mismo que
`services/semilla_estructuras.py` existe para eliminar—:

> **BLOQUEA — Fuente del receptor.** El PDB de 7E2Y todavía no está en disco y no
> se pudo sellar su contenido.

La siembra sí corre, pero como **tarea de fondo**: copia las 407 estructuras
—unos 400 MB descomprimidos— mientras el backend ya atiende peticiones. En el
directorio de datos del gate, cuando llegó la primera:

```
sembradas cuando se pidió el receptor    57 de 407   (hasta 1VL4, alfabéticamente)
7E2Y                                     todavía no
```

El comentario en `api/main.py` dice que la siembra «tiene que estar hecha antes
de que nadie pulse *Comprobar preparación*». No hay nada que lo garantice: es una
esperanza sobre una carrera, y **el usuario recién instalado es precisamente el
que llega dentro de la ventana**.

Lo que veía: un control que le pedía importar o preparar un receptor **que ya
venía en el instalador**. Y peor por debajo: `prepare_target` no encontraba el
crudo y caía a `download_pdb_from_rcsb`, o sea a la **red**, en un producto que
se vende como offline.

**`sembrar_una(pdb_id)`** materializa esa estructura y sólo esa, en el acto.
La usan los dos caminos —la comprobación previa antes de rendirse, y la
preparación antes de considerar el RCSB—, así que ambos siguen resolviendo el
mismo artefacto. Copiar un archivo del bundle no es descargar nada, de modo que
la regla del preflight —no toca la red— queda intacta.

## 16. Los gates, ahora, corren sobre el runtime staged

Los cinco defectos anteriores tienen algo en común: **ninguno era visible desde
el árbol de desarrollo**. Los gates de aceptación arrancaban el backend desde el
repositorio, donde hay `data/target_library` y PDB sin comprimir que el
instalador no lleva. Corriendo así, un receptor podía prepararse bien por un
archivo que el usuario nunca tendrá.

`MOLDESIGN_GATE_BUNDLE=1` cambia el árbol desde el que se sirve el backend a
`frontend/src-tauri/resources` —el runtime staged, que es literalmente lo que se
instala— y como los cuatro gates importan `BACKEND`, `PYTHON` y el entorno de
`accept_evaluation_runtime`, basta ponerlo una vez:

```
npm run stage:desktop           # o python scripts/bundle_helper.py .
MOLDESIGN_GATE_BUNDLE=1 python-embed/python.exe scripts/accept_evaluation_runtime.py
```

El entorno de los cuatro se unificó en `entorno_runtime()` y **añade
`PYTHONUTF8=1` y `PYTHONDONTWRITEBYTECODE=1`**, que son los que pone
`spawn_backend` en producción (§1). Sin ellos, los gates medían un entorno que
ningún usuario tiene. Lo mismo se añadió a `verify_desktop_bundle.py`, que
arranca el backend staged para comprobar `/health`.

Y `verify_desktop_bundle.py` comprueba ahora algo que no comprobaba nadie:
**que cada objetivo del catálogo viaje con su estructura**. Hoy son 380 de 380;
el día que uno no lo haga, el usuario descubriría que necesita red para acoplar
contra un receptor del catálogo.

### El resultado, sobre el bundle y con el almacenamiento vacío

| Gate | Resultado | Evidencia |
|---|---|---|
| Evaluación (Vina 1.2.7, reinicio, dos cuentas) | **PASS** | `tmp/evaluation-runtime-20260903T195936Z` |
| Batch / cohortes | **PASS** | `tmp/batch-runtime-20260903T200027Z` |
| Moldex | **PASS** | `tmp/moldex-runtime-20260903T200051Z` |
| MolChat (modelo local + herramientas) | **PASS** | `tmp/molchat-runtime-20260903T200139Z` |

La corrida de Evaluación acopló de verdad: afinidad −5,31 kcal/mol, receptor
sellado por SHA-256, seis denegaciones de autorización comprobadas, y en su log
está la línea `estructura_sembrada_a_peticion` —el §15 funcionando donde antes
se bloqueaba—.

`scripts/check_release_pipeline.py` y `scripts/verify_desktop_bundle.py`, verdes:
35 334 archivos, 1963 MiB, 770 binarios y 6938 importaciones nativas sin una sola
sin resolver.

## 17. Y ya puestos: los 380, preparados uno por uno

Con los gates en verde quedaba la pregunta grande. Los gates acoplan contra
**7E2Y**; el catálogo entrega **380**. `scripts/barrido_preparacion_instalacion_limpia.py`
los prepara todos por el camino real —`prepare_target` con Meeko de verdad—
sobre un almacenamiento vacío sembrado desde el bundle.

```
380 objetivos · 31 min
OK        359
ERROR      21
CADENAS     0     <- ninguno preparó cadenas distintas de las que declara
```

Los **359** contienen **exactamente** las cadenas que el catálogo anota como
formadoras del sitio. Es la primera vez que esa afirmación se mide sobre el
receptor que el usuario recibiría, y no sobre las coordenadas depositadas.

### Los 21 que no se pueden preparar

Los 21 fallan **dentro de Meeko**, en `mk_prepare_receptor` (10) o en su
reintento para glicanos (11):

```
1FEM  1UZJ  1VKG  1XWD  2OYE  2OYU  2VE3  3HH2  3KK6  3N8W  3N8X
3N8Y  3N8Z  4EJJ  5I3T  5U6X  5WBE  6NTW  6S1Z  7D42  8WTW
```

Las causas son del material, no del código: residuos incompletos
—`1FEM` tiene una LYS a la que le faltan ocho átomos pesados—, plantillas que
Meeko no sabe construir —`2OYE` con su HEM—, y glicanos.

**Y no los causa nada de esta tanda.** Se comprobó de la única forma que vale:
generando el archivo que recibe Meeko con el código anterior y con el nuevo, y
comparándolos. En 19 de los 21 son **idénticos**; en `2OYE` y `2OYU` difieren en
**una línea** —un `END` duplicado que añade el generador del ensamblaje— y Meeko
falla igual con los dos, con el mismo mensaje.

> Quedan como deuda declarada, no corregida: repararlos es una decisión
> científica —reconstruir residuos que faltan, o retirar el objetivo—, del mismo
> tipo que las del doc 72, y no de las que se toman de paso. Lo que sí está es
> que **el producto falla en voz alta** para ellos: `ProteinPreparationError`
> con el paso y el motivo, no un receptor a medias.

`docs/auditorias/preparacion_en_instalacion_limpia.json` guarda la fila de cada
uno de los 380: cadenas esperadas, cadenas obtenidas, átomos y error si lo hubo.

## 18. Lo que sigue sin cubrir esto

Las mismas de siempre —firma del instalador, Authenticode, el piloto— más dos
que esta tanda deja nombradas:

- **Los 21 receptores que Meeko no prepara.** Medidos, no arreglados.
- **Una VM de verdad.** Esto simula la instalación con precisión —el runtime
  staged, el almacenamiento vacío, las estructuras del bundle— pero corre sobre
  la máquina de desarrollo. Lo que no puede ver: el instalador NSIS, los
  permisos de `Program Files`, SmartScreen y el antivirus.

backend 1382 pruebas y 8 saltadas, frontend 725, `tsc` y `cargo check` limpios.
