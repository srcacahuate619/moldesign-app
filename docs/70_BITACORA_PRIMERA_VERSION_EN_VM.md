# 70 — Bitácora: de un instalador verde a uno que funciona en una máquina limpia

**Fecha:** 2026-09-02
**Rango:** `f273fba` → `d5be1d8` (12 commits)
**Estado:** la evaluación de extremo a extremo se completa en una VM con Windows
limpio. Quedan 19 defectos abiertos (ver doc 71).

---

## Para qué sirve este documento

Dos usos, y conviene decirlos por separado porque llevan a leerlo distinto:

1. **Reproducir.** Qué se cambió y en qué orden para llegar aquí.
2. **Bisecar.** Si mañana algo se rompe, encontrar rápido qué lo rompió. Por eso
   cada entrada dice **qué síntoma produce si se revierte** — que es la pregunta
   que uno se hace cuando algo deja de funcionar, no «qué hacía este commit».

---

## El patrón, antes que la lista

Los ocho fallos que impidieron que el instalador funcionara en una VM son **el
mismo error repetido**:

> Código que funciona en la máquina donde se construye porque esa máquina tiene
> algo que la del usuario no.

| Qué tenía la máquina de desarrollo | Qué faltaba en la VM |
|---|---|
| Visual Studio → DLLs de MSVC en `System32` | el runtime de VC++ |
| `D:\moldesign-build\python-embed\python.exe` | la ruta que los lanzadores de pip llevan dentro |
| `~/MolDesign/data/` lleno tras meses de uso | las estructuras de los receptores |
| GPU con WebGL | aceleración 3D |
| `tauri dev` sirviendo desde `devUrl` | la CSP reescrita del empaquetado |

**Y las 1996 pruebas estaban verdes durante todo eso**, porque todas corren
sobre el *código* y estos fallos viven en el *artefacto*, en el entorno donde se
entrega. La lección operativa está en las guardias que se añadieron: cada una
mira lo que se entrega, no lo que se escribió.

---

## Cronología

### 1. `15fe55c` — cierre del MVP: motores honestos, encoding, runtime embebido

- **ENG-004**: los cinco motores que esta build no ejecuta pasan de «NO
  INSTALADO / SERVICIO APARTE» a **«Próximamente»**. La decisión se deriva de
  `requiere`, que declara el backend, no de una lista escrita en la interfaz.
  `descarga_bajo_demanda` queda fuera a propósito: ESMFold se puede instalar, y
  llamarlo futuro escondería una capacidad que existe.
- Reparada doble codificación (UTF-8 leído como cp1252) en `Navigation.tsx`,
  `OptionsMenu.tsx` y `softwareCatalog.ts`. «EVALUACIÓN» se leía «EVALUACIÃ“N».
- `verify_desktop_bundle.py`: el probe de imports pasa de 120 s a 600 s.

> **Si se revierte:** el menú vuelve a ofrecer motores inexistentes como si
> fueran fallos de instalación; reaparecen los acentos rotos; el empaquetado
> falla por timeout en un disco frío.

### 2. `c3691a0` — cinco fallos que sólo existían en el empaquetado

El más instructivo de la sesión. Los cinco convivían mientras las 688 pruebas de
frontend estaban verdes.

| Fallo | Causa | Síntoma |
|---|---|---|
| Estilos en línea descartados | Tauri reescribe la CSP e **inyecta nonces**; por especificación un nonce anula `'unsafe-inline'` | Botón de MolChat sin `position:fixed` ni fondo, abajo a la izquierda, sólo visible con scroll. Ketcher sin estilos |
| Visores 3D muertos | El overlay de producción quitaba `'unsafe-eval'`, que `molstar.js` (4 usos) y `3Dmol-min.js` (1) necesitan | «Evaluating a string as JavaScript violates…» |
| Registro científico inalcanzable | `connect-src` no incluía `'self'` ni `http://tauri.localhost` (sólo la variante `https://`) | «No se pudo cargar el registro científico. Failed to fetch» |
| Puerto del backend horneado | `.env.local` mete `NEXT_PUBLIC_API_URL=…:8000` en el export estático | Receptores cargando para siempre. En esta máquina el 8000 lo ocupaba `legaldesk-server.exe`, que contesta 200 con HTML |
| Tipografía pedida a Google | `@import` dentro de `@solana/wallet-adapter-react-ui/styles.css` | Petición de red en cada arranque, bloqueada por la CSP |

**Reproducción del nonce**, que es la que más cuesta creer sin verla:

```
con nonce en style-src : x=0    y=4516  bg=rgba(0,0,0,0)
sin nonce              : x=1204 y=644   bg=rgb(140,122,153)
```

En `tauri dev` no ocurre: Tauri sirve desde `devUrl` y sólo reescribe la CSP de
los assets empaquetados. Corregido con
`dangerousDisableAssetCspModification: ["style-src"]` — sólo esa directiva; el
endurecimiento de `script-src` sí funciona y se conserva.

> **Si se revierte:** cualquiera de los cinco vuelve. El del nonce es el más
> difícil de diagnosticar porque no produce ningún error en consola: los estilos
> simplemente no se aplican.

**Guardias que nacieron aquí:**
- `check-exported-api-url.js` — ninguna dirección de backend horneada en `out/`
- `check-no-remote-assets.js` — ningún `@import`/`<link>` remoto
- `check-prod-csp.js` reescrito: ahora exige lo que la app **necesita**, y falla
  si `style-src` depende de `'unsafe-inline'` sin la protección del nonce

**Las dos veces que un guardián mintió**, documentadas porque la lección vale
más que el código:

1. Un carácter de retroceso (`0x08`) quedó dentro de una expresión regular. El
   detector recorrió 167 archivos y anunció «limpio» sobre un export sucio.
2. Corregido eso, empezó a bloquear el build por `DEFAULT_API_URL`, una
   constante legítima. Un guardián con falsos positivos acaba desactivado.

Desde entonces **todo guardián lleva autotest**: muestras que debe detectar y
muestras que no debe marcar, comprobadas antes de dar un veredicto.

### 3. `fd709c9` — arranque de ~57 s a ~6 s

Medido con `python -X importtime` sobre el runtime **empaquetado**.

| | Antes | Después |
|---|---|---|
| Imports | 51,7 s / 5.876 módulos | **3,6 s / 1.221** |
| `lifespan` hasta servir | 5,03 s | **0,32 s** |

**Causa 1 — un import fantasma de 28 s.** `chem/blood_viability.py` tenía a
nivel de módulo un `try: from admet_ai import ADMETModel` cuyo nombre **no se
usaba en ningún sitio**: cuando el modelo hace falta se vuelve a importar dentro
de `get_admet_model()`. Servía sólo para decidir si emitir un aviso, y arrastraba
torch (12,45 s), chemprop→lightning→torchmetrics→transformers (~6 s),
astartes→aimsim→matplotlib (2,05 s) y descriptastorus→xarray (1,11 s).
Sustituido por `importlib.util.find_spec`, que responde lo mismo sin ejecutar el
paquete.

**Causa 2 — un precalentamiento que bloqueaba la ventana 4,45 s.** El
`lifespan` cargaba el `ModelManager` de rescoring antes de dejar servir. Esos
modelos sólo hacen falta al rescorear, al final de un docking que dura minutos, y
`/rescore` **ya tenía** su carga perezosa de respaldo. Pasa a segundo plano con
`asyncio.to_thread`.

**Causa 3 — bytecode.** `backend.rs` fija `PYTHONDONTWRITEBYTECODE=1` (correcto:
los recursos instalados son inmutables), así que los módulos sin `.pyc` se
recompilaban **en cada arranque, siempre**. Se precompilan sólo los 78 paquetes
que el arranque importa:

```
todo site-packages : 2210 MiB, 5,6 s, SIN instalador (makensis muere a los 2 GiB)
solo el arranque   : 1945 MiB, 5,8 s, instalador correcto
```

Dos décimas de diferencia por 265 MB menos. Precompilarlo todo no daba un
instalador grande: no daba **ninguno**.

> **Si se revierte:** el arranque vuelve a ~57 s. Si se revierte sólo la
> precompilación acotada y se compila todo, el build muere en NSIS.

**Además:** `compute_quantum_features.py` vive en `<repo>/scripts/` pero se
importa como módulo de primer nivel. El instalador empaqueta `backend/`, no
`scripts/`, así que las features cuánticas se caían **en silencio** en
producción (`quantum_features_failed_skipped`).

### 4. `a062cd4` — `AGENTS.md`

Convención que leen los agentes de código. Declara los dos motores reales, por
qué DiffDock y ColabFold no están (con la medida propia: 21% de validez física y
confianza anticorrelacionada), qué significa «FEP+ ready» (**no** que MolDesign
corra FEP), que el ejecutable no está firmado, y siete restricciones que no se
deben romper.

### 5. `753de69` + `b35b474` — el runtime de Visual C++

**El síntoma:** en una VM limpia el backend no arrancaba. `_greenlet.pyd` no
cargaba, SQLAlchemy asíncrono moría con él, uvicorn se apagaba antes de contestar
`/health`, y Rust sólo reportaba «el backend no llegó a estar sano».

**Faltaban tres DLLs, en tres directorios.** Medido leyendo la tabla de
importación de los 770 binarios del runtime:

```
python/                      msvcp140, msvcp140_atomic_wait, vcomp140
tools/llama/                 3 DLLs   <- 52 binarios las piden: MolChat local
tools/xtb/                   libiomp5md + 1
tools/xtb/xtb-6.7.1/bin/     1
```

`vcruntime140.dll` y `vcruntime140_1.dll` **ya viajaban** con el Python
embeddable. El diagnóstico inicial nombraba esas dos y `msvcp140`; quedarse ahí
habría arrancado el backend y dejado **MolChat** (`vcomp140`, OpenMP) y
**ESMFold** (`msvcp140_atomic_wait`, torch) rotos en la siguiente vuelta.

Se copian del **redist de Visual Studio**, que es lo que Microsoft licencia para
redistribuir, no de `System32`. Coste: +2,3 MiB.

**El orden de las pasadas importa**: primero las DLLs propias de cada
herramienta, después el runtime de MSVC, porque una DLL recién copiada puede
necesitarlo a su vez (`libiomp5md.dll` pide `vcruntime140.dll`).

**La guardia que lo cierra** (`validate_native_dependencies`) es **estática**:
lee las tablas de importación y no ejecuta nada, así que da el mismo resultado se
corra donde se corra. El probe de imports anterior daba verde en la máquina de
construcción porque ahí las DLLs están en `System32`. *Una comprobación que
depende del entorno donde se ejecuta no puede detectar una dependencia del
entorno.*

Se equivocó dos veces antes de servir:

1. **Demasiado laxa**: daba por resuelta una DLL si existía en *cualquier*
   carpeta del bundle. Al apartar `msvcp140.dll` de `python/` no falló — quedaba
   otra copia en `openbabel_wheel.libs/`, un directorio privado que ningún otro
   módulo tiene en su ruta de búsqueda. **Es literalmente el bug original.**
2. **Demasiado estricta**: al modelar el orden real empezó a marcar los
   directorios de biblioteca de OpenMM y torch, que sí son resolubles porque las
   ruedas los registran con `os.add_dll_directory()`.

El modelo final distingue nombre con hash de `delvewheel` (basta que exista en
alguna `.libs`) de nombre de sistema (orden de búsqueda real de Windows).

> **Si se revierte:** el backend no arranca en ninguna máquina sin Visual
> Studio. Si se revierte sólo la guardia, el fallo vuelve a ser invisible hasta
> que alguien instale en una VM.

**`scripts/pe_imports.py`** nació aquí: un lector de tablas de importación de PE
sin dependencias. Existe porque el primer barrido buscaba cadenas por el binario
y daba falsos positivos absurdos — 96 binarios de RDKit parecían depender de
`rdkitrdgeneral.dll`, que no existe: `delvewheel` renombra las DLLs con un hash y
deja los nombres viejos como texto suelto.

### 6. `b51ed8c` + `c25a99c` — las estructuras de los receptores

**El síntoma:** en la VM, **todo** receptor bloqueaba la comprobación previa con
«El PDB de 1FH0 todavía no está en disco».

```
el instalador empaqueta en : <recursos>/data/targets/1HSG.pdb
el preflight busca en      : ~/MolDesign/data/targets/1HSG/raw.pdb
```

Distinta ubicación (un directorio **por usuario**, vacío tras instalar) y
distinta forma. Y un `grep` sobre el backend confirma lo peor: **nadie leía
`resources/data/targets`**. Esos 67 MB viajaban sin que ninguna línea de código
los abriera.

`services/semilla_estructuras.py` las copia donde el preflight las busca, al
arrancar y en segundo plano. Nunca sobreescribe: un archivo que el investigador
importó manda sobre el del instalador.

**Después se completó el catálogo**: el repositorio tenía 87 de los 387
objetivos. `scripts/descargar_estructuras_catalogo.py` trae del RCSB las que
falten — a mano, nunca en el build, que no puede depender de la red.

Viajan **en gzip**, y no es una optimización sino un requisito:

```
387 sin comprimir : ~183 MB -> runtime ~2065 MiB -> makensis MUERE
387 comprimidas   :   85 MB -> runtime ~1963 MiB -> correcto
```

> **Si se revierte la siembra:** vuelve el bloqueo con todo receptor.
> **Si se revierte la compresión:** el build muere en NSIS.

**El validador del descargador era el bug**, y por poco tira diez receptores
buenos: miraba sólo las 2000 primeras líneas buscando coordenadas, y en
complejos grandes (`1IRU`, el proteasoma 20S, con 47.757 líneas ATOM) la
cabecera es más larga que eso.

**WebGL:** `AvisoSinWebGL` va **encima** del visor, no dentro. El mensaje de
Mol* no se oculta —es técnicamente correcto— y ninguno tapa al otro. El nuestro
dice lo que aquél no puede saber: que el docking, el rescoring y el dossier se
calculan en el procesador y no dependen del visor.

### 7. `d798094` — PoseBusters a medias, y Propiedades reventando

**PoseBusters sólo hacía la mitad de su trabajo.** El veredicto decía «12 pasan,
1 fallan, 9 sin evaluar» y los 9 eran **los intermoleculares**: distancia mínima
al receptor, solapamiento de volumen. La interfaz mostraba «12 pasan» sobre poses
de las que nadie había comprobado si chocan con la proteína.

`receptor_como_pdb` truncaba el PDBQT a 66 columnas y dejaba el archivo **sin
símbolo químico**. Con un receptor de OpenBabel cuela; con uno de **meeko** —el
que produce el pipeline— RDKit no puede cargarlo **ni sin sanear**:

```
sin columna de elemento : sanitize=True None | sanitize=False None
con columna de elemento : sanitize=True OK   | sanitize=False OK
```

De punta a punta: `mol_cond_loaded` de `False` a `True`, de 13/22 booleanos a
**22/22**, de 9 sin evaluar a **0**.

> Una primera hipótesis apuntaba a `proximityBonding` de RDKit y **era falsa**.
> Lo que resolvió el caso fue reproducirlo con el receptor que usa producción,
> no con uno parecido.

**`Cannot read properties of null (reading 'toFixed')`.** La guarda parecía
correcta:

```ts
result.molecular_weight !== undefined ? result.molecular_weight.toFixed(1) : "—"
```

**`null !== undefined` es `true`.** El backend devuelve `null` en JSON, así que
pasaba la guarda y explotaba, tumbando la pestaña entera. En el mismo archivo,
cuatro líneas más abajo, convivía la forma correcta (`?.toFixed(2)`).
`lib/formatoNumerico.ts` deja una sola manera.

### 8. `7894be2` — los lanzadores de pip

**El síntoma:** en la VM, toda evaluación moría con
`Docking falló … contra target '7E2Y' (Vina exit code: 1)`. El usuario había
elegido **1TW7**.

**Dos mentiras antes de llegar a la causa:**

1. `_prepare_ligand_pdbqt` no recibía el target y ponía
   `settings.default_target_pdb_id` — la constante `"7E2Y"`.
2. El proceso que devolvió 1 era **meeko**, no Vina, que ni había arrancado.

**La causa real:** los `.exe` que pip genera en Windows llevan incrustado el
intérprete con el que se instalaron:

```
#!D:\moldesign-build\python-embed\python.exe
```

En el equipo del usuario esa ruta no existe. Un barrido de los 16.139 archivos
del runtime encuentra **55 así**. Cuatro estaban en el camino crítico:
`mk_prepare_ligand` (ninguna evaluación completaba), `mk_export`, `obabel`, y
`mk_prepare_receptor` — que **ya estaba bien**, porque `preparer.py` usa
`sys.executable -m …` con el comentario *«usar exactamente el intérprete del
backend instalado por el launcher»*. Esa lección no había llegado a las otras
tres rutas.

> **Si se revierte:** ninguna evaluación se completa en ninguna máquina que no
> sea la de construcción.

---

## La cadena del build, tal como quedó

`npm run tauri:build` encadena nueve puertas. Todas bloquean:

| # | Paso | Qué impide |
|---|---|---|
| 1 | `check:csp` | que `style-src` dependa de `'unsafe-inline'` sin la protección del nonce; que falte el origen propio en `connect-src` |
| 2 | `check:rescoring-manifest` | modelos desalineados |
| 3 | `stage:desktop` | — copia el runtime, coloca las DLLs (dos pasadas, en orden), precompila el bytecode del arranque |
| 4 | `verify:desktop-runtime` | dependencias nativas sin resolver, secretos, backend desactualizado, imports/Vina/`/health` rotos |
| 5 | `build:desktop` | — export estático con `NEXT_PUBLIC_API_URL` vacía |
| 6 | `check:exported-api-url` | un puerto de backend horneado |
| 7 | `check:no-remote-assets` | un recurso remoto |
| 8 | `cargo` + NSIS | — |
| 9 | `seal:installer` | un artefacto sin SHA-256, o con versión que no coincide |

Y aparte, **`npm run smoke:prod`**: levanta el backend con el Python empaquetado
y el entorno exacto de `backend.rs`, sirve el `out/` real con la CSP de
producción, e inyecta un `window.__TAURI__`. 12 comprobaciones sobre los cinco
fallos que se escaparon.

**Ejecutarlo antes de dar por buena cualquier corrección que toque empaquetado,
CSP o estilos.**

---

## Estado verificado

| | |
|---|---|
| Backend | **1313** pruebas |
| Frontend | **705** pruebas (80 archivos) |
| `tsc --noEmit` | limpio |
| Smoke de producción | **12/12** |
| Dependencias nativas | 770 binarios, 6938 importaciones, **0 sin resolver** |
| Arranque del backend | **~3-6 s** (era ~57 s) |
| Instalador | 572,9 MiB · `arbol_limpio: true` |

---

## Cómo bisecar si algo se rompe

1. **`npm run smoke:prod`** primero. Si falla ahí, es empaquetado/CSP/estilos y
   la tabla de arriba dice qué commit lo introdujo.
2. **`python scripts/verify_desktop_bundle.py .`** si el backend no arranca:
   distingue una dependencia nativa que falta de un problema de código.
3. **`python -X importtime`** sobre el runtime empaquetado si el arranque se
   alarga: un import de sondeo nuevo aparece de inmediato en el desglose.
4. **El `release-manifest.json`** del instalador dice el commit exacto y si el
   árbol estaba limpio. Si dice `arbol_limpio: false`, ese binario **no** es
   reproducible y no hay que asumir que corresponde al código que se está
   leyendo.

---

## Lo que este documento NO afirma

- Que la aplicación esté validada científicamente. Ver doc 71: **149 de 387
  objetivos acoplan contra una cavidad incompleta**.
- Que la instalación esté probada del todo. La desinstalación no la ha
  ejercitado nadie, y es la que más daño hace si falla.
- Que el instalador sea seguro de distribuir sin más: no lleva firma
  Authenticode, y el runtime de MSVC redistribuido todavía no está declarado en
  `THIRD_PARTY_NOTICES.md`.
