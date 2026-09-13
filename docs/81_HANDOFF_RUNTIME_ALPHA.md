# 81 — Traspaso: el runtime reproducible del alpha

> **Documento histórico (2026-09-06).** Este handoff conserva decisiones y tareas de la rama de distribución alpha; varias quedaron resueltas después de su corte. No sustituye el contrato vigente de `AGENTS.md`, `BUILD_GUIDE.md` y `launcher-manifest.json`.


Rama: `claude/runtime-distribution-alpha`, sobre `6a5cabe`.
Fecha del corte: **2026-09-06**.

Este documento existe porque el trabajo se hizo con una lista de propiedad
cerrada. Todo lo que sigue es **necesario y no está implementado aquí**: son
cambios en archivos de otro equipo. No se han tocado ni se deben deducir; están
escritos con su posición exacta y su código de salida para que la integración
no tenga que reinventarlos.

---

## 0. Qué cambió, en una frase

`base-v1.0.0.zip` no puede usarse como bootstrap —contiene código versionado,
pesos propios y bindings GPL, y espera `python/` donde el árbol quiere
`python-embed/`—, así que se define **`runtime-base-v1.1.0.zip`**, un formato
distinto con un nombre distinto, y el bootstrap deja de poder escribir fuera de
siete destinos declarados.

El archivo publicado **no se ha tocado**. Sigue en Hugging Face y sigue siendo
lo que `launcher-manifest.json` describe hoy.

---

## 1. Lo que hay que integrar

### 1.1 `.gitignore` — nada que hacer, pero hay que no perderlo

**Archivo:** `.gitignore` (reservado al otro equipo).

Medido el 2026-09-06, archivo a archivo, sobre el árbol aprovisionado:

| Destino | ¿Deja archivos no rastreados tras aprovisionar? |
|---|---|
| `tools/openbabel/bin/` | **No** — el árbol principal ya tiene `tools/openbabel/bin/` en la línea 119 de su `.gitignore` sin commitear |
| `tools/llama/` | **No** — sus 51 archivos son `.dll` y `.exe`, cubiertos por `tools/**/*.exe` y `tools/**/*.dll`. Los tres únicos que no lo están (`.gitkeep`, `README.md`, `SHA256SUM.txt`) están **versionados**, y el empaquetador los omite por definición |
| Los otros cinco | **No** — ignorados por directorio |

**Así que no hay ninguna línea que añadir.** Lo único que hay que hacer es
**asegurarse de que la línea 119 sobrevive al merge**: es de otro equipo, está
sin commitear, y sobre `6a5cabe` no existe. En esta rama, aislada, aprovisionar
sí deja `?? tools/openbabel/bin/`.

Esto corrige una versión anterior de este mismo documento, que pedía tres líneas
por haber leído la sonda del comprobador en vez de medir los archivos. La sonda
de `_verificar_destinos_ignorados` usa un nombre inventado y sin extensión, así
que marca `tools/llama/` como «no cubierto» aunque todo lo que de verdad cae ahí
sí lo esté. Mide si el destino está ignorado **por directorio**, no si va a
haber ruido.

**Cómo se vigila:** `scripts/tests/test_runtime_base.py::
test_los_destinos_sin_ignorar_son_los_ya_declarados` fija la lista de destinos
no cubiertos por directorio. Si alguien añade un destino nuevo sin su línea, esa
prueba falla; que un destino conocido esté en la lista no significa que haya
ruido.

### 1.2 `frontend/package.json` — dos scripts npm

**Archivo:** `frontend/package.json` (reservado).
**Dónde:** en `"scripts"`, junto a `check:openbabel-fuente`.

```json
"check:runtime-arbol": "python ..\\scripts\\bootstrap_dev_tree.py --check",
"check:runtime-base": "python ..\\scripts\\build_base_archive.py --check",
```

**Ojo con el intérprete.** Los demás gates usan `..\python-embed\python.exe`.
Estos dos usan `python` del sistema **a propósito**: `check:runtime-arbol`
comprueba, entre otras cosas, si `python-embed/` existe. Invocarlo con el
intérprete que quizá no está produce un error de npm sobre un ejecutable
ausente en vez del informe que explica qué falta y de dónde sale. El precio es
que hace falta un Python 3.9+ en el `PATH` del que construye; el beneficio es
que el único gate que sabe diagnosticar un árbol incompleto puede correr sobre
un árbol incompleto.

### 1.3 `frontend/src-tauri/tauri.conf.json` — una puerta más, la primera

**Archivo:** `frontend/src-tauri/tauri.conf.json` (reservado).
**Campo:** `build.beforeBuildCommand`.
**Posición exacta:** **al principio**, antes de `npm run check:csp`.

Cadena resultante (partiendo de la que hay hoy sin commitear en el árbol
principal, con las catorce puertas):

```
npm run check:runtime-arbol && npm run check:csp && npm run check:rescoring-manifest && ...
```

| Dato | Valor |
|---|---|
| Comando | `npm run check:runtime-arbol` |
| Código de salida esperado | `0` |
| Consume | `python-embed/`, `tools/vina/`, `tools/openbabel/`, `tools/xtb/`, `tools/llama/`, `esmfold/models/`, `data/molgraph_seed.db`, `python-embed/.runtime-base.json` |
| Produce | nada. **No escribe** |
| Duración medida | < 1 s sin `--hashes` |

**Por qué tiene que bloquear el build, y por qué la primera.** Las catorce
puertas actuales comprueban el contenido del árbol dando por hecho que el árbol
está. Si `python-embed/` está a medias —una descarga interrumpida, un
`--fetch` que murió—, la puerta 1 fallará con un error sobre CSP y la 6 con uno
sobre Open Babel, y ninguno de los dos dirá la verdad, que es que el runtime
está incompleto. Esta puerta distingue `AUSENTE`, `AJENO`, `INCOMPLETO`,
`CORRUPTO` y `COMPLETO`, y devuelve 1 en los cuatro primeros.

**`check:runtime-base` NO va en `beforeBuildCommand`.** Empaqueta 2,2 GB: son
minutos en cada build. Es una puerta de **publicación**, no de compilación.
Su sitio es el flujo de release —`docs/69_GATE_DE_RELEASE.md`— y sólo cuando se
va a publicar un runtime nuevo.

### 1.4 `.github/workflows/ci.yml` — un paso

**Archivo:** `.github/workflows/ci.yml` (reservado).
**Dónde:** en el job `backend`, después de `Run backend contracts`.

```yaml
      # El contrato del runtime redistribuible: 24 pruebas que construyen su
      # propio árbol en un temporal. No tocan el árbol de trabajo ni la red.
      - name: Verify runtime base contract
        working-directory: .
        run: python -m pytest scripts/tests --maxfail=1 -ra -p no:cacheprovider
```

**Ojo con `working-directory`.** El job `backend` corre con
`defaults.run.working-directory: backend`, y estas pruebas necesitan la raíz
del repositorio: el `conftest.py` resuelve `scripts/` desde su propia ubicación,
pero el `git clone` de la prueba del clon limpio clona `RAIZ`.

**Duración medida:** 11 s en esta máquina, de los cuales ~8 son el `git clone`
de la prueba del clon limpio.

**Qué se salta en CI, y hay que saberlo:**
`test_open_babel_convierte_por_cli_y_coincide_con_su_hash` se **salta** si
`tools/openbabel/bin/obabel.exe` no está, y en un `actions/checkout` no está.
El paso saldrá verde con una prueba menos. Saltar no es aprobar: la conversión
real la comprueba `npm run check:openbabel-fuente` (puerta 6) en la máquina que
construye, donde el binario sí existe.

### 1.5 `docs/api/test-counts.json` — ya está hecho

**Archivo:** `docs/api/test-counts.json` (reservado).

Ese archivo enumera `backend/tests/` archivo a archivo. Comprobado sobre
`codex/release-hygiene` en `b072e8f`, las tres pruebas de la frontera ya están
declaradas:

```
tests/test_adaptador_open_babel.py       27
tests/test_fallback_open_babel.py        10
tests/test_guarda_frontera_open_babel.py 23
```

con `"total": 2144`. **Nada que hacer.**

Sigue siendo la razón por la que las pruebas del runtime viven en
`scripts/tests/` y no en `backend/tests/`: añadir allí habría vuelto a
descuadrar ese recuento, y ese archivo no es mío.

### 1.6 `launcher-manifest.json` — un módulo nuevo, al publicar

**Archivo:** `launcher-manifest.json` (fuera de mi lista).

Hoy declara `base` → `base-v1.0.0.zip`. **No se toca todavía**: mientras la
aplicación instalada siga descargando ese archivo, quitarlo rompería el
arranque de quien ya lo tiene.

Cuando se publique el artefacto nuevo, se **añade** —no se sustituye— un módulo:

```json
{
  "id": "runtime-base",
  "filename": "runtime-base-v1.1.0.zip",
  "version": "1.1.0",
  "urls": [
    "https://huggingface.co/srcacahuate/moldesign-models/resolve/<REVISION>/v1.1.0/runtime-base-v1.1.0.zip"
  ],
  "sha256": "<el que imprime build_base_archive.py>",
  "size_bytes": 0,
  "gated": false
}
```

`<REVISION>` es el commit inmutable de Hugging Face, no una rama: una rama no
fija bytes. Después hay que copiar `sha256` y `size_bytes` a
`scripts/build_base_archive.py::RUNTIME_BASE` — mientras estén en `None`,
`--fetch` **se niega a descargar**, que es el comportamiento correcto y también
la razón por la que hoy un clon limpio todavía no puede aprovisionarse solo.

Y `frontend/lib/downloadManifest.ts` tiene una copia tipada que
`downloadManifest.test.ts` compara: hay que actualizarla en el mismo cambio.

### 1.7 `docs/INDEX.md` — una fila

**Archivo:** `docs/INDEX.md` (fuera de mi lista).
**Dónde:** en la tabla, encima de la fila de `80`.

```markdown
| 81 | [81_HANDOFF_RUNTIME_ALPHA.md](81_HANDOFF_RUNTIME_ALPHA.md) | 🟡 | Traspaso del runtime reproducible: contrato de `runtime-base-v1.1.0.zip`, las tres murallas del bootstrap y los cambios pendientes en archivos de otro equipo. |
```

`scripts/check_docs_links.py --check` pasa sin esto (comprueba enlaces, no
cobertura del índice), así que nada bloquea. Es que si no está en el índice,
dentro de tres meses nadie lo encuentra.

---

## 2. El contrato del artefacto nuevo

`runtime-base-v1.1.0.zip`. Formato 1. Definido en
`scripts/build_base_archive.py`, que es también quien lo construye y quien lo
verifica.

### 2.1 Estructura

```
RUNTIME-MANIFEST.json      inventario: SHA-256 y bytes de CADA archivo
python-embed/…             CPython 3.11 + entorno científico, SIN el wheel de Open Babel
tools/vina/…               AutoDock Vina 1.2.7            Apache-2.0
tools/openbabel/bin/…      Open Babel 3.1.1.23            GPL-2.0-only
tools/xtb/…                xTB 6.7.1                      LGPL-3.0-or-later
tools/llama/…              llama.cpp                      MIT
esmfold/models/…           sólo el tokenizer              MIT
data/molgraph_seed.db      base sembrada                  CC0-1.0
```

**Siete destinos, y ninguno contiene código del producto.** Ésa es la garantía
estructural: el artefacto no puede pisar `backend/`, `frontend/`, `rescoring/`
ni `scripts/` porque no existe ninguna ruta por la que llegar ahí.

### 2.1b Medido, no estimado — 2026-09-06

`python scripts/build_base_archive.py --check --raiz D:\moldesign-build`, sobre
el árbol de desarrollo real:

```
31 824 archivos, 1.63 GiB sin comprimir
bytes:  620 219 383
sha256: 84fdece03f5daf67165880a75583e95cc6befd8ce647c09a8c433afca617abc1
```

| Componente | Archivos | Tamaño | Licencia |
|---|---:|---:|---|
| `python-embed/` | 31 391 | 1.37 GiB | PSF-2.0 + las de cada dependencia |
| `tools/xtb/` | 300 | 179.14 MiB | LGPL-3.0-or-later |
| `tools/llama/` | 51 | 44.76 MiB | MIT |
| `data/molgraph_seed.db` | 1 | 18.29 MiB | CC0-1.0 |
| `tools/openbabel/bin/` | 68 | 10.21 MiB | GPL-2.0-only |
| `tools/vina/` | 7 | 6.68 MiB | Apache-2.0 |
| `esmfold/models/` | 6 | 4.36 KiB | MIT |

**Ese SHA-256 no es publicable todavía.** Sale de un árbol con cambios sin
commitear de dos agentes a la vez. Es la medida de que el empaquetador funciona
de punta a punta sobre contenido real, no el hash del artefacto que se publique.

Comparación con el anterior: 620 MiB frente a los 872 MiB declarados para
`base-v1.0.0.zip`. La diferencia son los pesos propios, el código de julio y los
bindings del wheel, que ya no viajan.

Y lo que hacía falta comprobar de esa ejecución: `dist/base-v1.0.0.zip` seguía
teniendo **los mismos 672 592 712 bytes y el mismo SHA-256** antes y después, y
el directorio temporal quedó vacío. `--check` sólo borró lo suyo.

### 2.2 Lo que NO contiene, y por qué

| No contiene | Por qué |
|---|---|
| Código versionado | El artefacto aporta lo que el clon no tiene. Si el repositorio ya lo trae, incluirlo no añade nada y sí puede sobrescribir trabajo. Se comprueba contra `git ls-files`, no contra una lista escrita a mano |
| Pesos propios de MolDesign | Otra licencia (`LICENSE-MODELS`) y otro origen. Ver §3 |
| Bindings de Open Babel | GPL-2.0-only y AGPL-3.0 son incompatibles: un import convertiría las dos obras en una sola |
| Pesos de LLM y ESMFold | Descargas propias, bajo demanda, con su hash en `launcher-manifest.json` |

Lo que **sí** contiene y conviene no confundir: los checkpoints que vendorizan
las propias dependencias —`admet_ai` trae los suyos en `resources/models/`—.
Son de esos paquetes, con su licencia, y sin ellos la capa ADMET no arranca. El
manifiesto los cuenta por paquete para que una revisión de licencias los vea
sin abrir el zip.

### 2.3 Open Babel: de dónde salen ahora los bytes

**Esto cambia respecto de `docs/79`, y es la decisión de diseño más
consecuente de esta rama.**

Antes: el wheel `openbabel-wheel` viajaba dentro de `python-embed/` y
`stage_openbabel_tool.py` extraía de ahí el binario a `tools/openbabel/`.

Ahora: el wheel **no viaja** en el runtime base —es un binding importable, y el
contrato lo prohíbe— así que el binario viaja **directamente** en
`tools/openbabel/bin/`.

Consecuencia que hay que aceptar a conciencia: **en un clon limpio aprovisionado
desde el artefacto, `stage_openbabel_tool.py` ya no puede regenerar nada**,
porque no hay wheel del que sacarlo. Ese script pasa a ser una herramienta de la
máquina que CONSTRUYE el artefacto, no del que lo consume.

Qué NO cambia:

- El manifiesto, la licencia y la procedencia (`tools/openbabel/*.json`,
  `LICENSE-GPL-2.0.txt`, `README-PROCEDENCIA.md`) siguen **versionados en el
  repositorio** y NO viajan en el zip. Es deliberado: si el manifiesto viajara
  dentro del archivo que verifica, un artefacto manipulado traería su propio
  hash y coincidiría consigo mismo. La referencia tiene que venir de fuera.
- La frontera sigue siendo la de `docs/79`: subproceso, ruta del manifiesto,
  hash verificado, nunca `PATH`, nunca `import`.
- **La recomendación de revisión jurídica externa sigue en pie.** Nada de esta
  rama la sustituye, y nada de lo hecho aquí permite concluir que la
  arquitectura sea jurídicamente suficiente.

---

## 3. Pesos propios: contrato declarado, no implementado

`scripts/build_base_archive.py::PESOS_PROPIOS`:

| Campo | Valor |
|---|---|
| `id` | `rescoring-weights` |
| `licencia` | `LICENSE-MODELS v1.1` |
| `gated` | `True` |
| `urls` | **vacío** |
| `sha256` | **`None`** |

Origen previsto: `hf.co/srcacahuate/moldesign-rescoring`, con acceso controlado
y aceptación de licencia.

**Que `urls` esté vacío no es un descuido: es el estado real.** Ese repositorio
no existe. Un contrato que apunta a una URL inventada es peor que uno que dice
«falta esto», porque el primero produce un error de red que parece un problema
del usuario.

Lo que hay que decidir —**y es del propietario, no del empaquetador**—:

1. ¿Se crea el repositorio con acceso controlado, o los pesos siguen viajando
   en el árbol de desarrollo hasta el primer usuario externo?
2. Si se crea: ¿la aceptación es automática o manual? El error por falta de
   credencial tiene que ser explícito («este repositorio exige aceptar
   `LICENSE-MODELS`; ve a tal sitio») y **distinguirse de la corrupción**. Sin
   pesos, CL-GNN y el preentrenado contrastivo no están disponibles y la corrida
   lo declara: la ausencia es legítima. Un archivo presente cuyo hash no cuadra
   no lo es.

No se ha descargado ningún peso restringido ni se ha metido ninguno en el
runtime base.

---

## 4. Decisiones abiertas que necesitan al propietario

1. **¿Open Babel dentro del runtime base o como módulo aparte?** Aquí va
   dentro, en `tools/openbabel/bin/`, con su licencia declarada componente a
   componente en el manifiesto. La alternativa —un
   `openbabel-tool-v3.1.1.zip` separado— etiquetaría el GPL en su propio
   archivo y sería más limpio de leer para un tercero, a cambio de una descarga
   más y un módulo más que mantener. **Recomendación: dejarlo como está hasta
   que haya revisión jurídica externa**, y que sea ella quien diga si la
   etiqueta por componente basta.

2. **¿Se retira `base-v1.0.0.zip` de Hugging Face?** No desde aquí. Mientras
   haya instalaciones que lo descarguen, retirarlo las rompe. Pero es un
   archivo que contiene código de julio y pesos propios bajo una etiqueta de
   licencia que no los cubre, y eso es un problema con fecha.

3. **`dist/base-v1.0.0.zip` local está corrupto.** 672 592 712 bytes frente a
   los 872 210 118 que declara `launcher-manifest.json`. Lo dejó así la versión
   anterior de `--check`. No se ha tocado, no se ha reparado y no debe usarse
   como fuente. Bórralo cuando quieras; el manifiesto sigue describiendo el
   archivo bueno, que está en Hugging Face.

---

## 5. Lo que esta rama NO demuestra

Dicho aquí y no sólo en un informe, porque es donde se va a leer dentro de seis
meses.

- **El setup completo no está validado.** No se ha construido ningún
  instalador, no se ha ejecutado `tauri:build` y no se ha publicado nada.
- **Ningún clon limpio se ha aprovisionado de verdad desde la red**, porque el
  artefacto no está publicado y `--fetch` se niega a descargar sin SHA-256
  declarado. Lo comprobado es el camino local (`--desde ARCHIVO --sha256 HEX`),
  con artefactos construidos en el momento.
- **Vina, `/health` y la conversión con el intérprete embebido no se
  comprobaron en estas pruebas.** Usan un `python-embed` de mentira de cuatro
  archivos, porque el real pesa 2,2 GB. Eso lo comprueba
  `npm run verify:desktop-runtime` sobre el bundle staged, que necesita el
  runtime de verdad y no corrió en esta rama. La conversión PDBQT→SDF de Open
  Babel **sí** se ejecutó de verdad, con el binario del manifiesto.
- **`check_openbabel_boundary.py` devuelve 1 sobre esta rama**, en G8 y G9. No
  es una regresión de este trabajo: las correcciones que esas dos guardas
  esperan viven en `backend/services/docking/vina_service.py`,
  `backend/core/models.py`, `frontend/lib/softwareCatalog.ts` y
  `frontend/public/legal/THIRD_PARTY_NOTICES.md`, que están fuera de mi lista
  de propiedad y ya existen sin commitear en el árbol principal. Medido el
  2026-09-06: sobre el árbol principal, el mismo gate pasa sus **diez**
  comprobaciones. Al fusionar, G8 y G9 vuelven a verde solos.

- **Y por la misma razón, 15 de las 60 pruebas de Open Babel del backend fallan
  aquí.** `test_adaptador_open_babel.py`, `test_fallback_open_babel.py` y
  `test_guarda_frontera_open_babel.py` son de mi propiedad y se importaron tal
  cual, pero comprueban código de `backend/api/main.py`,
  `backend/core/models.py`, `backend/services/docking/preflight.py` y
  `vina_service.py` que sólo existe sin commitear en el árbol principal.
  Medido el mismo día: **60/60 pasan en el árbol principal, 44/60 en esta
  rama**. No hay nada que arreglar en las pruebas; hay que fusionar.

  Consecuencia práctica: **no fusiones esta rama sola a `main` esperando verde.**
  Va después de —o junto con— el trabajo de frontera del otro equipo.

---

## 5.1 Cómo fusionar esto — comprobado el 2026-09-06

Mientras se escribía esta rama, el otro equipo comprometió su trabajo:
`codex/release-hygiene`, en `b072e8f chore: coordination checkpoint before alpha
release work`, que **contiene** `6a5cabe`, la base de esta rama.

**Habrá siete conflictos, y los siete son mecánicos.** No es una conjetura: se
midió con `git merge-tree --write-tree`, que calcula la fusión sin tocar ninguna
referencia ni ningún árbol de trabajo.

```
CONFLICT (add/add): docs/79_ADR_FRONTERA_OPEN_BABEL.md
CONFLICT (add/add): scripts/bootstrap_dev_tree.py
CONFLICT (add/add): scripts/build_base_archive.py
CONFLICT (add/add): scripts/check_openbabel_boundary.py
CONFLICT (add/add): scripts/lock_embedded_runtime.py
CONFLICT (add/add): scripts/stage_openbabel_tool.py
CONFLICT (add/add): scripts/verify_release_source_offer.py
```

**Por qué `add/add`.** Los dos lados AÑADEN esos archivos, porque en la base
común (`6a5cabe`) no existían: vivían sin versionar en el árbol de trabajo. Git
no tiene versión antigua con la que hacer una fusión a tres, así que cualquier
diferencia entre los dos lados es un conflicto, por pequeña que sea.

**Y la resolución es «quédate con la mía», en los siete.** Comprobado hash a
hash contra el tip de `codex/release-hygiene`: la versión de esos siete archivos
en su rama es **byte a byte idéntica** a mi commit de importación `aa4cbe0`. O
sea que mi versión es exactamente la suya más mis cambios; no hay trabajo ajeno
que perder.

```bash
git merge claude/runtime-distribution-alpha        # dará los 7 conflictos
git checkout --theirs -- \
  docs/79_ADR_FRONTERA_OPEN_BABEL.md \
  scripts/bootstrap_dev_tree.py \
  scripts/build_base_archive.py \
  scripts/check_openbabel_boundary.py \
  scripts/lock_embedded_runtime.py \
  scripts/stage_openbabel_tool.py \
  scripts/verify_release_source_offer.py
git add -- docs/79_ADR_FRONTERA_OPEN_BABEL.md scripts/*.py
```

(`--theirs` porque, desde `codex/release-hygiene`, la rama que se fusiona es la
mía. Antes de dar por buena la resolución:
`git diff aa4cbe0 -- <archivo>` no debería mostrar nada que no reconozcas.)

La alternativa más limpia, si el integrador la prefiere, es **rebasar esta rama
sobre `codex/release-hygiene` descartando `aa4cbe0`**: su contenido ya está allí,
así que sin ese commit no hay `add/add` en absoluto y no queda ningún conflicto.
No lo he hecho yo porque reescribir historia estaba fuera de mi encargo; es
decisión de quien integre.

**`docs/78` NO conflictúa.** Existía en la base, así que git hace fusión a tres
de verdad. Verificado sobre el árbol resultante: quedan las dos secciones, en
orden —`### 2.1 Corrección medida` (suya, línea 30) y `### 2.2 El runtime base,
definido` (mía, línea 70)—, y ninguna pisa a la otra. §2.1 dice dónde viven los
pesos; §2.2, qué contiene el runtime que no los lleva.

Y lo dicho arriba: esta rama sola no da verde. Va después de la suya, o junto
con ella.

## 6. Dependencia cruzada: `scripts/salida_consola.py`

Ese ayudante lo está añadiendo el otro equipo y no está en esta rama. Seis de
sus siete consumidores son archivos míos.

**Lo hecho:** los cuatro gates de mi propiedad que lo importaban ahora lo hacen
dentro de un `try/except ImportError` con una implementación equivalente de
respaldo. Un script de aprovisionamiento que no arranca porque falta una
comodidad de consola deja a quien clona sin la única herramienta que tenía para
desbloquearse.

**Al fusionar:** nada obligatorio. `salida_consola.py` ya está comprometido en
`b072e8f`, así que el `import` lo encontrará y el respaldo quedará como código
muerto e inofensivo. Si se prefiere limpiarlo, es un borrado de diez líneas por
archivo — pero conviene pensarlo dos veces: el respaldo es lo que hace que cada
script funcione suelto, y `bootstrap_dev_tree.py` es justamente el que tiene que
funcionar cuando el árbol está incompleto.

---

## 7. Referencias

- `scripts/build_base_archive.py` — el contrato, el constructor y el verificador
- `scripts/bootstrap_dev_tree.py` — las tres murallas y los cinco estados
- `scripts/tests/test_runtime_base.py` — 24 pruebas
- `docs/78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md` — dónde vive cada cosa
- `docs/79_ADR_FRONTERA_OPEN_BABEL.md` — la frontera GPL
- `docs/69_GATE_DE_RELEASE.md` — el gate de publicación (de otro equipo)
