# 79 — ADR: Open Babel se queda, pero como programa independiente

**Estado:** ✅ Decidido e implementado.
**Fecha:** 2026-09-05.
**Actualización de licencia:** 2026-09-10. La licencia vigente de MolDesign es
PolyForm Noncommercial 1.0.0; las referencias AGPL de la motivación original se
conservan como historia de la decisión.
**Sustituye a:** la pregunta abierta de [`LICENSING.md`](LICENSING.md) §3.1 y la
frase de [`../AGENTS.md`](../AGENTS.md) que decía «Open Babel se invoca como
biblioteca Python, no como subproceso, que es la distinción que decide si la
excepción habitual aplica».
**No es asesoría jurídica.** Es la decisión de ingeniería y el mapa que un
abogado necesita para dar una opinión. Ver §10.

---

## 1. El problema

Cuando se adoptó este ADR, MolDesign se publicaba bajo **AGPL-3.0-only**.
Distribuía, dentro del mismo
instalador, **Open Babel 3.1.1.23**, que declara **GPL versión 2 sin la coletilla
«o cualquier versión posterior»** — es decir, `GPL-2.0-only`.

GPL-2.0-only y la familia GPL-3, **AGPL-3.0 incluida**, son mutuamente
incompatibles: no existe un conjunto de términos bajo el que se pueda distribuir
una obra combinada de ambas. Si MolDesign *importara* Open Babel, el problema no
sería un obstáculo para un cambio futuro de licencia: sería un defecto **hoy**.

Y lo importaba. Tres cosas eran ciertas a la vez antes de esta decisión:

1. `openbabel-wheel==3.1.1.23` viajaba dentro de `python/Lib/site-packages/` del
   instalador, con `openbabel.py`, `pybel.py` y `_openbabel.pyd`. En una
   instalación cualquiera, `from openbabel import openbabel` funcionaba.
2. Dos módulos bajo `rescoring/` lo importaban de verdad
   (`generate_gpu_dataset.py` y `RTMScore/feats/extract_pocket_prody.py`), y
   **viajaban en el instalador** aunque ninguno formara parte del runtime.
3. La documentación del proyecto afirmaba lo contrario de lo que ocurría en el
   único punto de uso vivo: `vina_service` sí lo invocaba por subproceso, pero
   resolviendo el binario **dentro del paquete Python** y, si no lo encontraba,
   cayendo a `"obabel"` a secas — que el `PATH` resuelve a lo que haya en el
   equipo del usuario.

Un cuarto hecho lo agravaba: la pantalla de licencias y `THIRD_PARTY_NOTICES.md`
lo declaraban `GPL-2.0-or-later`. Ese «or-later» concede un permiso que sus
autores no dieron, y —peor para un producto cuya propuesta es saber cuándo no
confiar— **borraba del informe la incompatibilidad misma**. El lector veía dos
licencias que encajan donde hay dos que no encajan.

## 2. La decisión

**Open Babel se queda, en el mismo instalador, y pasa a tratarse como lo que
es: un programa independiente bajo GPL-2.0-only.**

```text
MolDesign / Python (PolyForm Noncommercial 1.0.0)
        │
        │  contrato explícito de subprocess
        │  argumentos fijos · sin shell · con timeout
        ▼
    tools/openbabel/bin/obabel.exe   (GPL-2.0-only)
        │
        │  archivos moleculares de entrada y salida
        ▼
    SDF validado ANTES de aceptarse
```

Cinco reglas, cada una comprobada por una guarda:

1. **Producción no importa** `openbabel`, `pybel` ni `_openbabel`.
2. **Los bindings no viajan.** El `site-packages` del instalador no los
   contiene, así que ni siquiera un error futuro podría importarlos allí.
3. **El programa vive fuera del entorno Python**, en `tools/openbabel/`, junto a
   `tools/vina/` y `tools/xtb/`, con versión, ruta, hash y licencia explícitos.
4. **Nunca se resuelve por `PATH`.** Sólo se ejecuta el ejecutable empaquetado,
   verificado contra su hash.
5. **Su ausencia se declara, no se degrada.** Viaja en el instalador: faltar es
   una instalación dañada.

### 2.1 La licencia de MolDesign cambió después de este ADR

La decisión de separar Open Babel continúa siendo necesaria bajo PolyForm
Noncommercial: los bindings GPL-2.0-only no pueden incorporarse y redistribuirse
como si estuvieran bajo los términos no comerciales de MolDesign. La frontera
de proceso independiente conserva las licencias de ambas obras y permite cumplir
GPL para Open Babel sin atribuirle la licencia de MolDesign.

El texto anterior de esta sección recomendaba conservar AGPL mientras no hubiera
evidencia comercial. Esa decisión fue sustituida el 2026-09-10 por LICENSE y
docs/LICENSING.md. Las copias ya otorgadas bajo AGPL no pierden sus derechos.

También por eso **no se actualiza Open Babel a 3.2.1**. Mezclar una corrección
arquitectónica y legal con un cambio de versión del motor de conversión haría
imposible atribuir una diferencia científica a una de las dos causas. La versión
se congela en 3.1.1.23 y el salto, si se hace, se hace solo y con sus goldens.

## 3. La evidencia histórica de GPL-2.0-only

No es una lectura de la web de Open Babel: es lo que declaran los metadatos del
paquete que se distribuye, y lo que registró el propio gate de este repositorio.

| Hecho | Origen |
|---|---|
| El paquete declara `GNU GENERAL PUBLIC LICENSE`, sin «or later» | metadata de `openbabel_wheel-3.1.1.23.dist-info` |
| El detector de `generate_sbom.py` buscaba la subcadena `GPL` y no la encontraba en ese nombre largo | el gate quedó **verde con un componente GPL dentro** hasta que se normalizó el nombre |
| `AGENTS.md` decía «no hay GPL» y era falso | corregido al descubrirse ese fallo del detector |
| `LICENSING.md` §3.1 planteó la incompatibilidad como *pregunta abierta* el 2026-08-19 | este ADR la cierra por la vía técnica, no por la interpretativa |

Procedencia exacta de los bytes que se distribuyen, verificada:

| | |
|---|---|
| Paquete | `openbabel-wheel==3.1.1.23` |
| Wheel | `openbabel_wheel-3.1.1.23-cp311-cp311-win_amd64.whl` |
| SHA-256 del wheel | `f0568906e6959fc541518c8e4cea26973e58707bd2434fb7cddfc5f745c32df7` |
| Plataforma | CPython 3.11, Windows x86-64 |
| Commit del empaquetador | `c6b2731dbd0a559ee56b8084b6d9997df1beb16f` (github.com/njzjz/openbabel-wheel) |
| Commit de las fuentes incorporadas | `77993b9a3b96fb9bd86249098beb97ab0fcbafc6` (github.com/njzjz/openbabel) |
| Basado en Open Babel oficial | 3.1.1 |
| Licencia efectiva declarada | `GPL-2.0-only` |

**El binario contesta `Open Babel 3.1.0` a `obabel -V`.** La publicación 3.1.1
fue una corrección de empaquetado que no actualizó la cadena de versión interna.
La discrepancia viene de origen; el manifiesto declara el valor **medido**, no
el esperado, y la guarda compara contra ese. Una guarda que comparase contra un
número supuesto sólo comprobaría la imaginación de quien la escribió.

## 4. La frontera CLI, en concreto

Un solo módulo puede nombrar a Open Babel:
[`backend/services/external_tools/open_babel.py`](../backend/services/external_tools/open_babel.py).

- **Localiza** el ejecutable con una regla que vale igual en el árbol de
  desarrollo y en el runtime instalado (`parents[3] / "tools" / "openbabel"`), o
  por `MOLDESIGN_OPENBABEL_DIR`, que el contenedor Tauri define. Ninguna otra.
- **Verifica el hash** contra `tools/openbabel/openbabel-manifest.json` **antes**
  de ejecutar. Un binario que funcione pero no sea el declarado no se ejecuta:
  el informe atribuiría su salida a una versión que no la produjo.
- **Ejecuta** con `create_subprocess_exec` y argumentos fijos, `shell=False`,
  `creationflags=BANDERAS_SIN_VENTANA` y timeout de 30 s.
- **Valida la salida** antes de aceptarla. Medido: con una entrada que no es un
  PDBQT, `obabel` devuelve **código 0** y escribe un archivo de **0 bytes**. Ése
  es el modo de fallo peligroso, y el que el respaldo anterior atravesaba en
  silencio.
- **Devuelve errores tipados** con cinco estados: `AVAILABLE`, `MISSING`,
  `HASH_MISMATCH`, `EXECUTION_FAILED`, `INVALID_OUTPUT`.
- **Publica rutas relativas**, nunca absolutas: la ubicación en el disco de quien
  corre no es evidencia. Ya hubo un manifiesto en este árbol que describía el
  disco de quien lo generó.

## 5. Qué queda prohibido

| Prohibido | Guarda que lo detiene |
|---|---|
| `import openbabel` / `pybel` / `_openbabel` en producción | `check_openbabel_boundary.py` G1 |
| Que los bindings aparezcan en el `site-packages` distribuido | G2 |
| Resolver `obabel` por `PATH`, `shutil.which` o nombre suelto | G3 |
| Que falte el ejecutable empaquetado | G4 + `bundled_layout` en Rust |
| Que su hash —o el de cualquiera de sus 70 archivos— no cuadre | G5 |
| Que `obabel -V` no devuelva la versión declarada | G6 |
| Que una conversión PDBQT→SDF real falle en el bundle | G7 |
| Que el SDF convertido no sea el que se persiste | G8 |
| Que el SBOM o la pantalla de licencias lo llamen `GPL-2.0-or-later` | G9 |

Cada guarda lleva **autotest positivo y negativo**: se ejecuta primero contra
una muestra que debe marcar y otra que no, y aborta si falla cualquiera de las
dos. Las que miran el disco se prueban desde
[`test_guarda_frontera_open_babel.py`](../backend/tests/test_guarda_frontera_open_babel.py),
que rompe **copias** del árbol —nunca el árbol— y exige que se detecte cada
rotura. Es la regla 2 de `AGENTS.md`: un guardián tiene que demostrar que ve.

### 5.1 Lo que sí sigue permitido

Los scripts científicos y los generadores de datasets pueden usar los bindings:
son **dependencias de desarrollo** y no se distribuyen. Hoy son dos, declarados
en su propia cabecera:

- `rescoring/generate_gpu_dataset.py`
- `rescoring/RTMScore/feats/extract_pocket_prody.py` (terceros, MIT)

La autorización **no se cree a ciegas**: la lista que la concede es la misma que
`bundle_helper.py` usa para excluirlos del instalador, y G2 comprueba **sobre el
bundle real** que no viajan. Si alguien autoriza un módulo sin excluirlo, la
guarda lo caza en el artefacto.

## 6. Los dos defectos que esto arregló de paso

Estaban en el respaldo de conversión de `vina_service`. Al arreglarlos apareció
un **tercer hecho**, medido, que explica por qué ninguno de los dos había dado
la cara nunca — y que es más incómodo que los dos juntos. Está en §6.1.

**Defecto 1 — procedencia inválida.** Cuando Meeko exportaba un SDF zombi y Open
Babel rescataba la conversión, el servicio asignaba
`parsing_source = "openbabel"`. `DockingResult.parsing_source` sólo admitía
`"sdf" | "pdbqt" | "vina_stdout"`, así que construir el resultado reventaba con
un `ValidationError` **justo en el caso en que el respaldo había funcionado**.

**Defecto 2 — se persistía el archivo equivocado.** Open Babel escribía un SDF
válido en un temporal, se parseaban sus poses, y a continuación se guardaba
—incondicionalmente— el SDF **original de Meeko**, el inválido; el temporal se
borraba después. El dossier citaba unas poses y adjuntaba un archivo que no las
contenía.

Arreglo:

- procedencia nueva y explícita, `sdf_openbabel_cli` — el nombre dice el formato
  del que se parseó *y* que lo produjo Open Babel invocado como CLI, que es
  precisamente la distinción de licencia de este documento;
- se entrega **el archivo del que salieron las poses**, con una comprobación de
  coherencia en caliente que aborta si la procedencia declarada y el archivo no
  corresponden;
- los caminos `sdf`, `pdbqt` y `vina_stdout` siguen entregando los **bytes**
  exactos del archivo de Meeko con `write_file`, así que su estado persistido no
  cambia;
- los bloques PDBQT originales de cada pose viajan intactos: la trazabilidad
  hacia lo que Vina escribió no depende de la conversión;
- **no se fabrica nada.** Las afinidades salen del mismo parser en los dos
  caminos. Si el respaldo hace falta y Open Babel no está, la corrida deja un
  aviso `CONVERSOR_ESTRUCTURAL_NO_DISPONIBLE` de severidad crítica y no continúa
  como si nada.

### 6.1 El tercer hecho: por qué ninguno de los dos se había visto

**Medido el 2026-09-05**, sobre `data/dmfhard_curve_work/1aaq/curve30_conf0.out.pdbqt`,
una salida real de Vina con seis poses:

| Paso | Resultado |
|---|---|
| Open Babel convierte el PDBQT | ✅ SDF válido, con las seis moléculas |
| ¿Dónde deja los datos de Vina? | en una propiedad `>  <REMARK>` |
| ¿Qué lee `parse_vina_output_sdf`? | sólo `> <meeko>` y `> <minimizedAffinity>` |
| Poses extraídas del SDF convertido | **cero** |

Es decir: **con entrada de Vina, la rama del respaldo nunca llega a producir
poses**, así que `parsing_source = "openbabel"` nunca sobrevivía hasta construir
el `DockingResult` y el `ValidationError` del defecto 1 era **inalcanzable**. Y
el defecto 2 quedaba sin efecto por la misma razón: no había un SDF de Open
Babel del que hubieran salido poses que persistir.

Los dos eran defectos reales del código —el programa se comportaría mal si se
alcanzaran, y cualquier cambio en el parser los habría despertado a la vez— y
ahora son imposibles por construcción. Pero decir que «pasaba en producción»
habría sido falso, y este documento no puede permitírselo.

**Lo que sí pasa hoy, y sigue pasando.** Cuando Meeko exporta un SDF zombi:

1. Open Babel convierte y produce un SDF válido, que se descarta;
2. las afinidades salen del parser de PDBQT, de las **mismas** líneas
   `REMARK VINA RESULT`, así que el número es idéntico y correcto;
3. `parsing_source` queda en `"pdbqt"`, que es honesto;
4. **pero el archivo entregado sigue siendo el SDF de Meeko**, que no contiene
   esas poses.

El punto 4 quedó resuelto el 2026-09-06. parse_vina_output_sdf reconoce la
propiedad REMARK que Open Babel genera y extrae de ella los tres valores
originales de REMARK VINA RESULT. Cuando ese camino se usa, vina_service
declara parsing_source = "sdf_openbabel_cli" y persiste el mismo contenido
SDF convertido del que salieron las poses; no mezcla el informe con el archivo
zombi de Meeko. La regresión
[test_open_babel_sdf_conserva_las_poses_y_sus_metadatos](../backend/tests/test_fallback_open_babel.py)
compara las seis poses del SDF con el PDBQT de Vina.

### 6.2 Y una fuga de ruta que apareció al mirar el SDF convertido

Open Babel usa el nombre del archivo de entrada como **título de la molécula**.
Como la entrada es un temporal, cada pose del SDF convertido salía titulada

```
C:\Users\<usuario>\AppData\Local\Temp\moldesign-obabel-1m9e_hvu\pose.pdbqt
```

Ese archivo se entrega. Habría metido la ruta absoluta del disco de quien
ejecutó —y su nombre de usuario— dentro de la evidencia estructural, y además
habría cambiado en cada ejecución, rompiendo la comparación byte a byte de dos
corridas equivalentes. Se fija con `--title vina_pose`, y una prueba comprueba
que no queda ninguna ruta dentro del contenido convertido.

## 7. Qué pasa si Open Babel falta

Cuatro capas, y ninguna dice «no disponible» y sigue:

| Momento | Comportamiento |
|---|---|
| Arranque del contenedor Tauri | `dev_layout` / `bundled_layout` exigen `tools/openbabel/bin/obabel.exe` y **no arrancan** el motor sin él, nombrando la pieza que falta |
| Preflight de una corrida | control `CONVERSOR_ESTRUCTURAL_DISPONIBLE`, con el estado tipado y la razón. **Advierte, no bloquea**: si Meeko exporta bien, Open Babel no llega a ejecutarse, y bloquear una corrida que iba a funcionar convertiría la comprobación en un estorbo |
| `GET /health` | componente `open_babel` con estado, versión, licencia, hash y ruta. `degraded` si no está sano; **no** es `core`, así que no impide abrir la aplicación |
| Durante la corrida, si el respaldo hace falta | aviso `CONVERSOR_ESTRUCTURAL_NO_DISPONIBLE` con severidad **crítica** y el estado tipado. Sin poses fabricadas, sin renormalización, sin atribuir nada a Open Babel |

## 8. Cómo se verifica

**En un clon limpio.** `tools/openbabel/bin/` no está versionado —los binarios
no lo están, igual que Vina y xTB—, así que:

```bash
python scripts/stage_openbabel_tool.py          # materializa desde el wheel
python scripts/stage_openbabel_tool.py --check  # hashes + conversión real
python scripts/check_openbabel_boundary.py      # G1, G3–G9 sobre el repositorio
```

Sin ese staging, G4–G7 **saltan y lo dicen**; no se anuncian en verde. Saltar no
es aprobar.

**En el instalador.** El build corre las guardas dentro de su cadena
(`tauri.conf.json` → `beforeBuildCommand`):

```
check:openbabel-fuente  →  stage:desktop  →  check:openbabel  →  verify:desktop-runtime
```

`check:openbabel` corre con `--bundle --exigir-binario`, así que mira
`frontend/src-tauri/resources` —lo que de verdad se entrega— y la ausencia es un
fallo, no un salto. `verify:desktop-runtime` añade la comprobación que ninguna
otra hace: que **el adaptador del backend empaquetado**, corriendo bajo el
intérprete empaquetado y con el entorno exacto de producción y
`MOLDESIGN_OPENBABEL_DIR` sin definir, localiza el programa, comprueba su hash y
convierte una molécula. Es la diferencia entre «el archivo está» y «el código
instalado lo encuentra», y aquí ya se pagó: `_obabel_del_bundle()` resolvía a un
lanzador de pip con la ruta del intérprete de la máquina de construcción
incrustada.

### 8.1 De dónde salen los bytes en un clon limpio — corrección del 2026-09-06

Lo de arriba dice «materializa desde el wheel», y eso **deja de ser cierto para
quien clone** en cuanto se publique `runtime-base-v1.1.0.zip`.

El motivo es consecuencia directa de esta misma decisión. El contrato del
runtime redistribuible prohíbe que viajen bindings importables de Open Babel
(`docs/78` §2.2), así que el wheel `openbabel-wheel` **no va dentro del
artefacto**. Y si el wheel no viaja, no hay wheel del que materializar nada.

Así que el binario viaja **directamente** en `tools/openbabel/bin/`, como un
componente declarado del artefacto, con su licencia, su versión, su SHA-256 y su
procedencia dentro de `RUNTIME-MANIFEST.json`.

Los dos papeles quedan repartidos así:

| Quién | Qué hace |
|---|---|
| La máquina que **construye** el artefacto | tiene el wheel en su `python-embed`, corre `stage_openbabel_tool.py` y produce `tools/openbabel/` |
| El clon que lo **consume** | recibe el binario ya materializado; ahí `stage_openbabel_tool.py` no puede regenerar nada, y no le hace falta |

**El manifiesto no viaja en el zip, y eso es deliberado.**
`tools/openbabel/openbabel-manifest.json`, `LICENSE-GPL-2.0.txt` y
`README-PROCEDENCIA.md` siguen versionados en el repositorio. Si el manifiesto
viajara dentro del archivo que sirve para verificarlo, un artefacto manipulado
traería su propio hash y coincidiría consigo mismo. La referencia contra la que
se comprueba tiene que venir de fuera del archivo comprobado — y por eso
`bootstrap_dev_tree.verificar_open_babel` compara el binario extraído contra el
manifiesto **del clon**, no contra nada que viniera en la descarga.

Lo que **no** cambia: subproceso, ruta resuelta desde el manifiesto, hash
verificado antes de ejecutar, nunca `PATH`, nunca `import`. Y el punto 1 de §10
sigue exactamente igual de vivo: esto es ingeniería, no asesoría jurídica, y una
revisión externa sigue siendo recomendable antes de vender licencias
comerciales.

## 9. Viajar junto no es cargar como biblioteca

Merece decirse explícitamente porque es donde se confunde el asunto.

Open Babel se distribuye **en el mismo instalador** que MolDesign. Eso, por sí
solo, no crea una obra combinada: es agregación de dos programas en un medio de
distribución. Lo que crearía una obra combinada sería enlazarlo o importarlo, y
eso es exactamente lo que la frontera de §2 impide —y lo que nueve guardas
comprueban en cada build.

La consecuencia práctica: la obligación que MolDesign asume por distribuirlo es
la de **acompañarlo de su licencia, su copyright, su ausencia de garantía y su
código fuente correspondiente**, no la de relicenciarse.

Sobre la fuente correspondiente: **un enlace a una web no basta por sí solo.**
El enlace apunta a lo que haya hoy en esa rama, no a los bytes compilados. Cada
publicación adjunta los archivos de fuente de la versión exacta distribuida, y
`scripts/verify_release_source_offer.py --check` falla si no están o si sus
hashes no coinciden. **Al 2026-09-06 esos archivos están preparados localmente**: `verify_release_source_offer.py --check` los valida en `dist/source-offer/`, pero `dist/` está ignorado y aún no se han adjuntado a una publicación. Ver §10.

## 10. Lo que sigue abierto

Este documento describe ingeniería verificada. **No es asesoría jurídica.**

1. **Una revisión jurídica externa sigue siendo recomendable antes de vender
   licencias comerciales.** La frontera CLI es la interpretación estándar y la
   práctica común, pero «estándar» no es «dictaminado para este caso». La
   diferencia entre agregación y obra combinada la decide un abogado sobre los
   hechos concretos, y los hechos concretos son ahora comprobables — que es
   justamente lo que esta decisión aporta a esa conversación.
2. **La oferta de código fuente correspondiente está preparada pero no
   ejecutada.** Faltan los dos `.tar.gz` de fuentes junto a la publicación. Es
   un requisito de la GPLv2 §3 y bloquea una distribución seria, no el
   desarrollo.

   Medido el 2026-09-06 en la máquina del mantenedor: los dos artefactos
   **existen** en `dist/source-offer/` —`openbabel-src-77993b9a.tar.gz` (35 MiB)
   y `openbabel-wheel-recipe-c6b2731d.tar.gz`— y
   `verify_release_source_offer.py --check` los da por buenos. Pero `dist/` está
   en `.gitignore`, así que **viven en una máquina, no en el repositorio ni en
   ninguna publicación**. Un clon limpio ejecuta ese mismo comando y obtiene
   código 1, correctamente: para quien clona, la oferta no está preparada. Lo
   que falta no es generarlos otra vez; es adjuntarlos al release.
3. **`smina` sigue en `tools/` y es GPL-2.0.** No viaja en el instalador
   (`bundle_helper` sólo copia `vina`, `xtb`, `llama` y `openbabel`), pero si
   algún día viajara, le aplica este mismo ADR entero.
4. **El SDF del camino de respaldo conserva ya sus poses y metadatos.** `parse_vina_output_sdf` lee las propiedades `REMARK VINA RESULT` que escribe Open Babel y `vina_service` persiste el mismo SDF convertido cuando ese camino se usa. Las afinidades y el orden de poses se conservan; el dossier identifica `parsing_source="sdf_openbabel_cli"`. La regresión está en [`test_fallback_open_babel.py`](../backend/tests/test_fallback_open_babel.py).
5. **`prolif` sigue sin licencia declarada** en su metadata
   ([`LICENSING.md`](LICENSING.md) §5.4). No lo toca esta decisión.

---

## Referencias en el árbol

| Qué | Dónde |
|---|---|
| Adaptador único | `backend/services/external_tools/open_babel.py` |
| Staging de la herramienta | `scripts/stage_openbabel_tool.py` |
| Guarda de la frontera | `scripts/check_openbabel_boundary.py` |
| Oferta de fuente | `scripts/verify_release_source_offer.py` |
| Manifiesto, licencia y procedencia | `tools/openbabel/` |
| Contrato del runtime que lo transporta | `scripts/build_base_archive.py` |
| Verificación del binario al aprovisionar | `scripts/bootstrap_dev_tree.py::verificar_open_babel` |
| Pruebas del adaptador | `backend/tests/test_adaptador_open_babel.py` |
| Pruebas de los dos defectos | `backend/tests/test_fallback_open_babel.py` |
| Pruebas de que la guarda ve | `backend/tests/test_guarda_frontera_open_babel.py` |
| Avisos al usuario | `frontend/public/legal/THIRD_PARTY_NOTICES.md` |
| Oferta y recompilación | `frontend/public/legal/SOURCE_CODE_AND_RELINKING.md` |
| Inventario de licencias | [`LICENSING.md`](LICENSING.md) |
