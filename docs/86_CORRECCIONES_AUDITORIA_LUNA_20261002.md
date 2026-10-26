# Correcciones de la auditoría LUNA (legalidad, MolChat y opciones) — 2026-10-02

**Estado:** **cerrado el 2026-10-03** (cada hallazgo con su commit en el índice; lo que no se
hizo, declarado en su sección y en el cierre).
**Objeto:** registrar cada corrección aplicada a partir del informe de auditoría
legal, epistémica y de opciones, con diagnóstico, decisión, contratos afectados y
pruebas de verificación.

**Fuente de auditoría:**

- `D:\moldesign-audits\AUDIT_luna_legalidad_molchat_20261002\INFORME_LEGAL_MOLCHAT.md`
  (hecha sobre `12abc22`, **antes** del bloque Sol). El informe no numera sus
  hallazgos: los IDs `LUNA-01…06` son de este documento y siguen el orden en que
  se atendieron las prioridades del informe.

> **Esto es análisis técnico, no opinión jurídica.** `AGENTS.md` y
> `docs/79_ADR_FRONTERA_OPEN_BABEL.md` ya recomiendan una revisión jurídica
> externa antes de vender licencias comerciales; nada de lo que sigue la
> sustituye ni cambia una licencia.

## Jerarquía de principios y reglas

Las mismas que `docs/85_CORRECCIONES_AUDITORIA_SOL_20261001.md`:

> **CIENCIA > CALIDAD > EFICIENCIA** — honestidad epistemológica: si algo no se
> puede demostrar, se declara. Dos motores y sólo dos (Vina 1.2.7 y ESMFold).
> Prohibido tocar `scripts/artifacts_science/`. Frontera GPL de Open Babel:
> programa independiente, invocado por CLI, nunca por PATH.

## Metodología por hallazgo

1. Reproducir con evidencia propia en el HEAD actual (la auditoría es anterior al
   bloque Sol: lo que ya no se reproduce se dice con su medida, no se «arregla»).
2. Escribir primero la prueba que falla y comprobar que falla contra el código
   anterior.
3. Cambio mínimo y robusto.
4. Suites completas, conteos de pruebas y AGENTS.md al día.
5. Actualizar este documento y commit por bloque. **Nada se empuja**: esta rama
   no va al repositorio público (`scripts/check_push_publico.py` lo bloquea a
   propósito).

## Re-verificación contra el HEAD (`315eb95`)

| ID | Hallazgo | Veredicto | Medida |
|---|---|---|---|
| LUNA-01 | P1 imports de Open Babel en `rescoring/` | **Reproduce** | El mismo recorrido AST da 7 imports en 4 archivos, idénticos al informe. Matiz: 2 de los 4 están declarados «dev-only» a propósito y los otros 2 cuelgan de `rescoring/scripts/`, que `bundle_helper` excluye; ninguno viaja. |
| LUNA-02 | P1 SBOM desactualizado | **Reproduce, con causa más honda** | `--check` sale 1; sólo difiere `binarios` (2 vs 4). Ver LUNA-02. |
| LUNA-03 | P1 575 crates sin licencia | **Reproduce** | `cargo metadata --offline` falla y cae a `Cargo.lock`. Con filtro de plataforma resuelve las 353 crates de Windows, con 0 sin licencia. Ver LUNA-03. |
| LUNA-04 | P2 `docking_engine` raíz ignorado en submit | **Reproduce por código** | `EvaluationSubmitRequest` no tiene `extra="forbid"` ni campo raíz `docking_engine`. |
| LUNA-05 | P2 MolChat encola sin confirmación | **Reproduce por código** | `run_docking` construye la petición y llama a `registrar_corrida` en el mismo turno. |
| LUNA-06 | P2 AGENTS.md describe `sin_licencia_declarada` | **Reproduce** | Esa sección está vacía; los paquetes están en `licencias_resueltas_por_evidencia`. |

### Un incidente de procedimiento, declarado

Para reproducir LUNA-01 se ejecutó `scan_openbabel_ast.py` **tal cual** desde la
carpeta de evidencia sellada. El script escribe su salida
(`openbabel_ast_imports.json`) en esa misma carpeta, y la sobrescribió. El
contenido es byte a byte el mismo —sha256 `902d4200…8950`, 1084 B, igual al
registrado en `EVIDENCE_SHA256.json`—, de modo que el sello sigue validando; lo
único que cambió fue el mtime. Es la misma familia de fallo que ya está en la
memoria del proyecto («un `--check` que escribe sobre lo que verifica»): leer un
script antes de ejecutarlo habría bastado. Desde entonces no se ejecuta nada de
esa carpeta; las sondas se escriben en el scratchpad.

## Índice de hallazgos

| ID | Severidad | Resumen | Estado |
|---|---|---|---|
| LUNA-01 | P1 | 7 imports prohibidos de Open Babel en `rescoring/` que la guarda G1 no ve; G2 sin comprobar | **Corregido (commit 0745047)**: excepción explícita y auditada, G1 sobre todo el árbol, G2 aprobado sobre el artefacto |
| LUNA-02 | P1 | `generate_sbom.py --check` sale 1: el SBOM guardado omite binarios que sí viajan | **Corregido (commit 4da1ad8)** |
| LUNA-03 | P1 | 575 crates Rust con licencia vacía y sin aparecer como «sin licencia declarada» | **Corregido junto con LUNA-02 (commit 4da1ad8)** |
| LUNA-04 | P2 | `docking_engine` en la raíz de `/evaluation/submit` se descarta en silencio (202) | **Corregido (commit db0c532)** |
| LUNA-05 | P2 | MolChat registra y encola docking sin confirmación humana separada | **Corregido (commit 075817b)**: propuesta + aprobación autenticada, gate runtime real en verde |
| LUNA-06 | P2 | AGENTS.md describe una clasificación del SBOM que ya no existe | **Corregido junto con LUNA-02 (commit 4da1ad8)** |
| (extra) | P1 | Al verificar el artefacto: el golden E2E de Vina estaba desactualizado desde el bloque Sol (`prepared_chains`) y la puerta 11 de `tauri:build` fallaba | **Corregido (commit c1c83f6)**; ver «Compuerta final» |

---

## LUNA-01 — Siete imports de Open Babel en `rescoring/` que la guarda G1 no veía

**Severidad:** P1 (regla escrita ≠ regla comprobada). **Decisión del propietario
(2026-10-03):** excepción explícita y auditada.

### Diagnóstico

Reproduce idéntico al informe: el mismo recorrido AST (corrido de nuevo contra
`315eb95`, en el Python embebido 3.11) da **7 imports en 4 archivos** de
`rescoring/`, ninguno en `backend/`:

| Archivo | Líneas | Qué es |
|---|---|---|
| `rescoring/generate_gpu_dataset.py` | 151, 170 | genera los datasets de entrenamiento |
| `rescoring/RTMScore/feats/extract_pocket_prody.py` | 20 | ayudante de bolsillos de RTMScore (terceros, MIT) |
| `rescoring/scripts/redock_pdbbind.py` | 100, 152, 227 | preparación del redocking de PDBbind |
| `rescoring/scripts/test_crystal_vs_docked.py` | 113 | experimento «cristal vs acoplado» |

**La causa no es sólo que haya imports; es que la regla escrita y la regla
comprobada habían dejado de ser la misma.** `AGENTS.md` prohibía importar los
bindings «desde `backend/` o `rescoring/`» sin excepción. La guarda G1, en cambio,
filtraba por nombre de directorio (`tests`, `scripts`, `data`, `artifacts`...) y
por una lista de módulos «de desarrollo» leída de `bundle_helper`: «limpio» era
verdad del subconjunto que miraba. Y el ADR 79 decía que las excepciones eran
**dos**; eran cuatro. Ninguno de los siete imports viaja en el instalador: dos de
los archivos se excluyen por nombre y los otros dos cuelgan de `rescoring/scripts`,
que se excluye por directorio. Lo que fallaba era el control, no —hasta donde se ha
medido— el contenido del instalador: G2 sobre el artefacto lo comprueba más abajo.

Hechos medidos que condicionan la decisión:

- `redock_pdbbind.py` **no es un script cualquiera**: **1414** registros de
  procedencia repartidos en cinco artefactos sellados (FND-06, D-MF-HARD-CURVE,
  D-MF-HARD-CURVE-VAL, D-MF-HARD-EXH4, D-MF-HARD-EXH4-VAL) declaran el receptor
  «`openbabel_pdb2pdbqt_rigido`», y en FND-06 **470** registros citan
  `rescoring/scripts/redock_pdbbind.py` como el código de preparación. Además lo
  importan por ruta `scripts/molflex.py`, `molflex_exp_v1.py`, `calibrate_redock.py`,
  `retest_timeouts.py` y `fase_b_expand_dataset.py`. Reescribir cómo prepara el
  receptor cambiaría lo que se midió.
- **Una corrección a lo dicho al preguntar la decisión:** se enunció que «470
  registros dicen `openbabel_pdb2pdbqt_rigido`». Lo exacto: 470 es el número de
  registros de FND-06 que **citan el script**; los que declaran la herramienta son 560
  en FND-06 y 1414 en los cinco artefactos. La conclusión se refuerza, pero la cifra
  citada era la del nombre del archivo, no la de la herramienta.
- Los docstrings de `generate_gpu_dataset.py` y de `extract_pocket_prody.py` aún
  dicen que MolDesign «se publica bajo AGPL-3.0-only»; la licencia vigente es
  PolyForm Noncommercial 1.0.0 (ADR 79 §2.1 ya lo reconoce). Es texto legal en
  archivos que la decisión dejó intactos: **no se tocó**; queda anotado.

### Decisión tomada y el PORQUÉ

Opción 1 del propietario: **no se tocan los cuatro archivos y la excepción se hace
explícita, comprobable y cerrada**, en vez de ocultarse tras un filtro de
directorios.

1. **G1 pasa a AST sobre TODO `backend/` y `rescoring/`** —`tests/`, `scripts/`,
   `data/`, `artifacts/`, `deprecated/` incluidos—, 643 módulos hoy frente a los 309
   «de producción» de antes. Detecta `import`, `from ... import` y los imports
   dinámicos con nombre constante (`__import__("openbabel")`,
   `importlib.import_module("pybel")`); un `from .openbabel import x` relativo, que
   nombra un módulo local, **ya no** es un falso positivo.
2. **Un archivo que no se puede analizar es un fallo.** El detector contestaba `[]`
   ante un `SyntaxError` (y la auditoría que originó esto escaneó con
   `except: continue`): «limpio» sobre algo que no miró. Ahora
   `analizar_imports` devuelve el error aparte y G1 falla nombrando el archivo.
3. **La excepción es una lista nombrada, con motivo escrito**:
   `EXCEPCIONES_DEV_ONLY` en `scripts/check_openbabel_boundary.py`, cuatro entradas.
   Se lista en el informe de la guarda en cada ejecución. **Ampliarla es decisión
   del propietario, no un parche.**
4. **Tres candados, no uno.** (a) **G1b**: cada entrada existe, tiene motivo y
   `bundle_helper` la excluye (por nombre —`RESCORING_FUERA_DEL_RUNTIME_FILES`— o por
   directorio —la nueva constante `RESCORING_DIRS_FUERA_DEL_RUNTIME`, que es la misma
   que usa el empaquetado—). (b) **G2** comprueba que **ninguna de las cuatro** esté
   en el bundle (antes sólo miraba las dos excluidas por nombre). (c) **G1 sobre el
   bundle** corre **sin ninguna exención**, ni siquiera la declarada.
5. **El adaptador ya no está exento de G1**, sólo de G3: invoca el programa, no importa
   los bindings.
6. **G3 conserva su alcance** (producción, filtrado por directorio): es una búsqueda
   por expresión regular sobre el texto, y en `tests/` abundan las muestras que
   contienen justo lo buscado. G1 y G3 dejan de compartir recorrido.
7. **La regla escrita se alinea con la comprobada**: `AGENTS.md` (la regla de Open
   Babel, con las cuatro rutas nombradas y por qué `redock_pdbbind.py` no se
   reescribe) y `docs/79_ADR_FRONTERA_OPEN_BABEL.md` §5.1 (que decía «dos»).

**Por qué no las otras dos opciones.** Reescribir los imports (opción 2) cambia cómo
se prepara el receptor en el script que respalda la procedencia sellada de cinco
experimentos, y exigiría revalidarlos. Mover los archivos (opción 3) rompe los
`import redock_pdbbind` por ruta de cinco scripts y las rutas que quedaron registradas
en la procedencia. Ambas se descartan por riesgo científico, no por comodidad.

### Contratos y archivos modificados

- `scripts/check_openbabel_boundary.py`: `EXCEPCIONES_DEV_ONLY`,
  `DIRECTORIOS_IGNORADOS`, `analizar_imports`, `importa_prohibido` (envoltorio),
  `imports_prohibidos_en`, `g1_g3_codigo(..., excepciones=)`,
  `g1b_excepciones_coherentes`, `_excluido_del_empaquetado`,
  `autotest_recorrido`, G2 ampliado; se elimina `_dev_only_declarados`.
- `scripts/bundle_helper.py`: `RESCORING_DIRS_FUERA_DEL_RUNTIME` (una sola fuente para
  el empaquetado y la guarda).
- `AGENTS.md` (regla de Open Babel; se añade xTB al párrafo de copyleft por decisión
  del propietario), `docs/79_ADR_FRONTERA_OPEN_BABEL.md` §5.
- `backend/tests/test_guarda_frontera_open_babel.py`: la prueba que codificaba la
  exención de `tests/` cambia de sentido (`…_pero_si_las_pruebas`).

### Pruebas de verificación

`test_guarda_frontera_open_babel.py` pasa de 28 a 49 pruebas; con la guarda anterior
fallaban 21. Cubren: los cinco directorios que antes se saltaba (parametrizado), la
cita de `archivo:línea`, los imports dinámicos y anidados, los vecinos que no deben
marcarse (relativos, nombres no constantes, comentarios, cadenas), el archivo
ilegible, la excepción declarada admitida **y listada**, el bundle sin ninguna
exención, G2 sobre las cuatro rutas, y la coherencia de la lista (huérfana, que
viajaría, sin motivo, nombrada en AGENTS.md). Y la prueba de fondo: lo que el AST
encuentra en el árbol real, sin exenciones, es **exactamente** `EXCEPCIONES_DEV_ONLY`
(ni una violación nueva ni una excepción obsoleta). La guarda lleva además un
`autotest_recorrido` propio que fabrica un árbol y aborta si el recorrido no ve lo que
debe, que es la restricción 2 de AGENTS.md aplicada al recorrido y no sólo al
detector.

**G2 sobre el artefacto (la auditoría lo dejó sin comprobar por no haber bundle):**
`npm run stage:desktop` (35 225 archivos, 1826 MiB) y después
`check_openbabel_boundary.py --bundle --exigir-binario`: **17 comprobaciones, frontera
intacta**. G2 aprobado sobre el artefacto —ningún binding en `site-packages`, ninguna
de las cuatro excepciones en `resources/`—; G1 sobre el bundle, **sin ninguna
exención**, recorre 323 módulos sin un solo import prohibido; G4–G7 con el
`obabel.exe` empaquetado (hash, versión y conversión PDBQT→SDF reales). El bundle se
volverá a construir al final del bloque 4 para la compuerta final.

---

## LUNA-02 — El SBOM guardado omite binarios que viajan en el instalador

**Severidad:** P1 (gate de release). **Comprobación:**
`python-embed\python.exe scripts\generate_sbom.py --check` → código 1.

### Diagnóstico

Comparado sección por sección contra lo generado en este HEAD, **sólo `binarios`
difiere**: guardado, `vina.exe` y `obabel.exe`; generado, esos dos más `xtb.exe` y
`llama-server.exe`. (Con la consola en cp1252 parecen diferir más secciones: es un
artefacto de decodificar la salida del script; `--check` compara en proceso y
no lo sufre.)

La causa no es que «el runtime cambió». `_binarios()` recorría una lista de
candidatos con `if not existe: continue`: lo que no estuviera en el árbol donde se
generaba el SBOM desaparecía sin decirlo. El archivo se escribió el 2026-09-25
(`3db6028`) en un árbol sin `tools/xtb` ni `tools/llama` (los directorios actuales
tienen fecha del 2026-09-27); `bundle_helper` **sí** los empaqueta cuando existen.
Dos copias de la misma decisión —qué viaja— que se habían separado, y un SBOM cuyo
contenido dependía de la máquina que lo generó. Además:

- `smina.exe` figuraba entre los candidatos y nunca se empaquetó.
- `xtb`, `llama` y `vina` no llevaban licencia ni procedencia, a diferencia de
  `obabel.exe`; sólo uno de los cuatro binarios tenía su licencia en el inventario.
- `docs/69_GATE_DE_RELEASE.md` decía «2 (`vina.exe`, `llama-server.exe`)» — otro
  par distinto del guardado, prueba de que la tabla envejeció por su cuenta.

### Decisión tomada y el PORQUÉ

1. **Una sola fuente de «qué viaja».** `bundle_helper.HERRAMIENTAS_EMPAQUETADAS`
   y `HERRAMIENTAS_CRITICAS` (nuevas constantes; el bucle del paso [4/7] ya las
   usa) son lo que recorre `generate_sbom._binarios()`. Una prueba exige que las
   claves de `BINARIOS` sean exactamente esa tupla. *Porque* con dos copias gana la
   que se queda vieja, y aquí fue justo la que declaraba.
2. **La ausencia se declara, no se calla.** Herramienta crítica ausente (Vina,
   Open Babel) → aborta, igual que aborta el empaquetado. Opcional ausente (xtb,
   llama) → entra en `binarios_ausentes` con su consecuencia. *Porque* un SBOM
   puede describir legítimamente un instalador sin xtb, pero no puede dejar que
   «no viaja» y «no estaba aquí» se confundan.
3. **Licencia con su origen.** `vina`, `xtb` y `llama` toman su licencia de la
   tabla de `frontend/public/legal/THIRD_PARTY_NOTICES.md` —la declaración que el
   producto ya publica— y el SBOM lo dice (`licencia_origen`): no es la lectura de
   un archivo de licencia dentro de `tools/<x>/`, que no existe. Open Babel sigue
   leyendo su manifiesto. *Porque* escribir una segunda copia de la licencia en el
   script es una segunda copia que se puede quedar vieja, y porque declarar una
   licencia nueva en un inventario legal no es una decisión técnica.
4. **Lo que sigue sin inventariarse se declara en `no_cubre`**: los directorios de
   `tools/` viajan enteros (DLL de ggml, `AutoDock-Vina-GPU-2-1.exe`, utilidades de
   llama.cpp, DLL de xTB) y sólo se hashea el ejecutable principal;
   `llama-server.exe` es un lanzador de 9 KB y el código está en
   `llama-server-impl.dll`. Ya lo admitía `docs/80_INVENTARIO_TECNOLOGICO_INTEGRAL.md`
   §4; ahora lo dice el propio SBOM.
5. **`--check` falla por una segunda razón**: cobertura de licencias incompleta
   (ver LUNA-03). Un archivo idéntico y con huecos sigue teniendo huecos.

Se regeneró `docs/api/sbom.json` por el flujo normal (`--write`) y se revisó el
diff: `python_embed` y `npm_produccion` salen **idénticos**; cambian `binarios`
(+`xtb.exe`, +`llama-server.exe`, con licencia y origen), `binarios_ausentes`
(vacío), `rust_produccion` (LUNA-03), `no_cubre`, `cobertura_de_licencias` y
`licencias_resueltas_por_evidencia`. Sobre esta última: `busboy` y `streamsearch`
seguían en el diccionario y en el informe aunque **ya no están en el lockfile**
(el informe «resolvía» paquetes que no se distribuyen); ahora sólo se listan los
aplicados a un paquete del inventario, y se retiraron esas dos lecturas viejas.

### Contratos y archivos modificados

- `scripts/generate_sbom.py`: `BINARIOS`, `_binarios(raiz)` → `(presentes,
  ausentes)`, `_licencias_de_los_avisos`, `_hash_de_archivo` (por bloques; xtb pesa
  58 MB), `_resueltas_por_evidencia`, `_cobertura`, `main()`.
- `scripts/bundle_helper.py`: `HERRAMIENTAS_EMPAQUETADAS`, `HERRAMIENTAS_CRITICAS`.
- `docs/api/sbom.json` regenerado; `docs/69_GATE_DE_RELEASE.md` (tabla de cuentas).

### Pruebas de verificación

`backend/tests/test_sbom_inventario.py` (22 pruebas; contra el código anterior
fallaron 20 —las otras dos son guardas nuevas sobre lo que ya existía—, incluida
`test_el_check_del_sbom_pasa_sobre_este_arbol`, que reproduce la salida 1 de la
auditoría). Verdes tras el cambio. `generate_sbom.py --check` → 0:
«168 paquetes Python, 1267 npm, 331 Rust, 4 binarios; cobertura de licencias
completa». `check_openbabel_boundary.py` (G9 lee `sbom.json`) y
`check_release_pipeline.py` siguen en verde.

---

## LUNA-03 — 575 crates Rust sin licencia verificable

**Severidad:** P1 (afirmación legal no demostrada).

### Diagnóstico

Reproduce: las 575 entradas Rust del SBOM guardado tenían `licencia: ""`. La
causa tiene tres capas:

1. `cargo metadata --offline` falla con `failed to download android_log-sys`: el
   `Cargo.lock` lista **222** crates que sólo se compilan para otras plataformas
   (Android, Linux, macOS) y que no están en la caché, aunque el instalador de
   Windows no las lleva.
2. Al fallar, el código caía a `Cargo.lock`, que fija nombre y versión pero no
   trae licencias, **sin marcar el resultado como degradado**.
3. `sin_licencia_declarada` sólo se construía para Python y npm: ni siquiera tenía
   una lista Rust, de modo que «rust: 0» se leía como «sin riesgo» cuando era
   «sin mirar». Es la misma familia de fallo que dejó el gate verde con Open Babel
   dentro: un detector que informa de lo que él sabe leer.

Con `cargo metadata --locked --offline --filter-platform x86_64-pc-windows-msvc`
(medido el 2026-10-03): 353 crates en el grafo de Windows —331 enlazadas por
dependencias normales, 21 sólo de construcción, más el propio producto—; **las 353
declaran licencia**. Expresiones SPDX, sin GPL/AGPL/SSPL; 5 crates MPL-2.0
(`cssparser`, `cssparser-macros`, `dtoa-short`, `option-ext`, `selectors`:
copyleft débil por archivo, y `MPL` no está en `LICENCIAS_A_REVISAR`, que es una
política del propietario; se registra aquí como hecho).

### Medición adicional, puntual y declarada como tal

El campo `license` de un `Cargo.toml` es lo que la crate **declara**; la lección
de `padelpy` es que declarar no es contener. Se aplicó a las 331 crates enlazadas
el método de `scripts/check_copyleft_en_runtime.py` (cabecera literal de los
textos de licencia que traen sus fuentes en `~/.cargo/registry`), el 2026-10-03:

| Medida | Resultado |
|---|---|
| Crates con directorio de fuente | 331 / 331 |
| Archivos de licencia leídos | 591 |
| Crates sin ningún archivo de licencia en su fuente | 12 (`alloc-stdlib`, `crc-catalog`, `defmt-parser`, `selectors`, 5 `unic-*`, 3 `webview2-com*`): declaran sólo por `Cargo.toml` |
| Cabecera **AGPL** | **0** |
| Cabecera GPL | 5 crates, ninguna imputable a una obligación en el binario (abajo) |

Las 5 de GPL: cuatro (`cssparser`, `cssparser-macros`, `dtoa-short`,
`option-ext`) son falsos positivos del método —el texto de la MPL-2.0 define
«Secondary License» nombrando a la GPL, la LGPL y la AGPL—; la quinta,
**`lzma-sys` 0.1.20** (declarada «MIT/Apache-2.0», llega por `zip` → `xz2`),
trae vendorizado el árbol de xz 5.2 con sus `COPYING.GPLv2` y `COPYING.GPLv3`.
Su `build.rs` compila únicamente `xz-5.2/src/liblzma/*`, que según el propio
`COPYING` de xz «is in the public domain», y ese `COPYING` dice que los archivos
del sistema de construcción bajo GPL «none of these files end up in the binaries».
**Observación para la revisión jurídica, no decisión:** el SBOM declara MIT/Apache
para una crate cuyo código fuente distribuido lleva textos GPL que no se compilan.

Esta medición **no está automatizada** y depende de la caché de Cargo de esta
máquina; el gate no la repite. Extender `check_copyleft_en_runtime.py` a Rust y a
npm queda como mejora abierta, no hecha aquí.

### Decisión tomada y el PORQUÉ

1. **Pedir a Cargo lo que el instalador compila**: `--filter-platform
   x86_64-pc-windows-msvc` (`PLATAFORMA_RUST`). *Porque* es lo que se entrega;
   el resto del lockfile no viaja y no se lista, pero se cuenta
   (`otras_plataformas_en_lockfile: 222`) para que nadie crea que se perdió.
2. **Clausura por tipo de dependencia** (`_clasificar_crates`): *enlazadas* =
   dependencias normales desde la raíz, sin el propio producto; *sólo de
   construcción* = alcanzadas únicamente por `build-dependencies`, listadas en
   `dependencias_de_construccion.rust`; las de desarrollo no entran. El producto
   no es dependencia de sí mismo (antes salía como «PolyForm Noncommercial» entre
   las crates de terceros, y el normalizador lo habría marcado a revisar).
3. **El respaldo se declara degradado.** Si Cargo no puede resolver —o ni siquiera
   existe— el resultado trae `licencias_verificadas: False`, `plataforma: "sin
   filtrar (Cargo.lock)"` y la causa en `fuente`. Sus crates quedan con licencia
   vacía y aparecen en `sin_licencia_declarada.rust`. *Porque* un vacío en ese
   estado no distingue «sin licencia» de «no se miró».
4. **El gate bloquea la afirmación global.** Nuevo `cobertura_de_licencias` por
   ecosistema, con `completa = rust_verificado and nada sin licencia`. `--check`
   y `--write` devuelven 1 si no es completa, aunque el archivo coincida. Cada
   ecosistema tiene su lista en `sin_licencia_declarada` (Rust y binarios no la
   tenían). *Porque* «no hay AGPL de terceros» sólo es una afirmación si ninguna
   parte del inventario quedó sin mirar.
5. **No se amplía `LICENCIAS_A_REVISAR`** (añadir `MPL`, por ejemplo): decide el
   propietario.

### Contratos y archivos modificados

- `scripts/generate_sbom.py`: `PLATAFORMA_RUST`, `_clasificar_crates`,
  `_crates_del_lockfile`, `_paquetes_rust()` (ahora devuelve un `dict` con
  `plataforma`, `fuente`, `licencias_verificadas`, `enlazadas`,
  `solo_de_construccion`, `otras_plataformas_en_lockfile`), `_con_nota`,
  `_cobertura`, `_informar_cobertura`.
- `docs/api/sbom.json`: `rust_produccion` pasa de 575 a **331** crates con licencia
  (`licencias_verificadas: true`); `dependencias_de_construccion.rust` (21);
  `sin_licencia_declarada.{rust,binarios}`; `cobertura_de_licencias`.

### Pruebas de verificación

En `test_sbom_inventario.py`: clausura normal sin la raíz; construcción separada y
desarrollo excluido; crate sin licencia visible; `cargo metadata` pedido con
`--filter-platform`; respaldo y cargo ausente → `licencias_verificadas: False`;
cobertura completa sólo sin huecos y con Rust verificado; `--check` falla con
huecos **aunque el archivo coincida** y pasa con cobertura completa. Sobre el SBOM
guardado: cobertura completa, ninguna sección sin licencia, todas las crates con
licencia. Y `test_ningun_componente_inventariado_declara_agpl_ni_sspl`, que
convierte la frase de AGENTS.md en algo que falla, acompañada de una prueba de que
el normalizador **ve** AGPL/SSPL en sus nombres largos y no marca LGPL/GPL/MPL.

---

## LUNA-06 — AGENTS.md describe una clasificación que ya no existe

**Severidad:** P2.

### Diagnóstico

AGENTS.md decía «cinco paquetes Python y siete npm … el SBOM los lista ahora en
`sin_licencia_declarada`». Esa sección está vacía; los paquetes viven en
`licencias_resueltas_por_evidencia`. Y ni siquiera los números del informe de
auditoría («11 nombres: cuatro Python y siete npm») cuadraban con el inventario:
medido, son **4 Python y 5 npm** aplicados (más `busboy` y `streamsearch`, que ya no
están en el lockfile; ver LUNA-02). El mismo párrafo contenía además «No hay AGPL de
terceros ni SSPL», que para Rust no estaba demostrado (LUNA-03).

### Decisión tomada y el PORQUÉ

Describir la clasificación vigente con su recuento **y atarlo a una prueba**:
«**4 paquetes Python y 5 npm**», con `test_agents_md_cuenta_lo_que_el_sbom_tiene`
comparándolo contra el SBOM (el párrafo envejeció tres veces porque nada lo
comparaba). La frase sobre AGPL/SSPL se acota a lo medido: ningún componente
inventariado **declara** AGPL ni SSPL; «declara no es contiene»; la medición de
textos en Rust se cita con su fecha y su condición (regla 6 de AGENTS.md: un número
sin su condición es un número falso). Sin cifras volátiles en la prosa salvo las
dos que la prueba vigila.

### Contratos y archivos modificados

`AGENTS.md` (párrafo de licencias de dependencias, dos frases),
`docs/69_GATE_DE_RELEASE.md` (tabla de cuentas con fecha y la fuente señalada).

### Pruebas de verificación

`test_agents_md_cuenta_lo_que_el_sbom_tiene`: comprueba el par (4, 5) y que todo lo
«resuelto por evidencia» pertenece al inventario distribuido.

---

## LUNA-04 — Un campo desconocido en la petición de una corrida se aceptaba y se descartaba

**Severidad:** P2 (procedencia por omisión).

### Diagnóstico

Reproduce por código (y por prueba: sin el cambio, 20 de las 23 pruebas nuevas
fallan). `POST /evaluation/submit` con `docking_engine: "diffdock"` en la raíz del
cuerpo pasaba la validación: `EvaluationSubmitRequest` no declara ese campo (el
motor vive en `pipeline_config`) y Pydantic descarta por defecto lo que no conoce.
La corrida salía con Vina por defecto y el sello usa el motor efectivo, de modo que
**no** se etiquetó como DiffDock; el defecto es que el cliente creyó haber pedido un
motor deshabilitado y nada se lo desmintió. No era sólo el motor: cualquier campo con
el nombre equivocado se descartaba igual (`exhaustiveness` suelto en la raíz o dentro
de `pipeline_config`, un `target_id` donde el campo es `target_pdb_id`).

Hallazgo colateral que el propio cambio dejó al descubierto:
`test_api_phase5_security.py` pasaba `target_id=` a `EvaluationSubmitRequest` creyendo
ejercitar el receptor. El modelo lo ignoraba y la prueba seguía verde. Con el modelo
cerrado habría seguido verde **por la razón equivocada** (el 422 de «campo
desconocido» en vez del de la caja), así que se corrigió a `target_pdb_id` y ahora
comprueba que el error nombra `grid_size` / `custom_hotspots`.

El informe también menciona el preflight. Medido: `docking_engine: "diffdock"` en la
raíz del preflight da 200 con un bloqueante (`RUTA_PREFLIGHT_SOPORTADA`), y eso es
correcto —el campo es parte de su contrato y el informe que explica por qué no se
puede es más útil que un 422 sin informe—. Lo que sí se ignoraba era un campo que el
preflight no tiene (`peptide_docking_engine` en la raíz): el informe mostraba Vina sin
bloqueantes.

### Decisión tomada y el PORQUÉ

Modelos de petición **cerrados** (`ConfigDict(extra="forbid")`) en
`EvaluationGeometry` (lo heredan `EvaluationSubmitRequest`, y con él
`/evaluation/evaluate`, y `PreflightRequest`) y en `PipelineConfigRequest`. *Porque*
un campo desconocido en la petición de una corrida nunca es inocuo: cambia, o intenta
cambiar, lo que se ejecuta; el error lo nombra. Se eligió el cierre general en vez de
un 422 específico para `docking_engine`: la misma errata con otro nombre habría
seguido pasando.

Verificado antes de cerrar que no rompe a quien existe: el cuerpo que envía el
cliente de escritorio (`lib/api.ts`, `lib/preflight.ts`, el `pipeline_config` de
`ProEvaluation.tsx`) usa sólo campos modelados, y también los cuatro scripts de
aceptación en runtime (`accept_evaluation_runtime`, `accept_moldex_runtime`,
`accept_msix_store`, `accept_batch_runtime`). Una prueba lo fija con el cuerpo real
como control positivo.

### Contratos y archivos modificados

- `backend/api/routers/evaluation.py`: `model_config` en `EvaluationGeometry` y
  `PipelineConfigRequest`.
- `docs/api/openapi-current.json` y `docs/45_API_CONTRACT_CURRENT.md` regenerados:
  `additionalProperties: false` en los tres esquemas. **El snapshot ya estaba
  desactualizado antes de este cambio** (`generate_openapi_contract.py --check` no
  pasaba en `315eb95`): arrastraba los parámetros `task_id` y `cohort_task_ids` de
  `GET /sar/{molecule_id}` que añadió CAS-02 sin regenerar. Ambas diferencias entran juntas.
- `backend/tests/test_api_phase5_security.py`: `target_pdb_id` en vez de `target_id`.
- Es un endurecimiento del contrato HTTP: un cuerpo con campos de más que antes daba
  202 ahora da 422. No se anotó en `docs/api/CHANGELOG.md`, que se reserva a lo que
  el generador rechaza sin `--allow-breaking`.

### Pruebas de verificación

`backend/tests/test_campos_desconocidos_no_se_ignoran.py` (23): cinco campos
desconocidos en la raíz (el del informe, `docking_engine: "vina"`, `exhaustiveness`,
`num_poses`, `target_id`) rechazados por modelo y por HTTP en `/submit` y `/evaluate`
(422 que **nombra el campo** y sin llegar a `registrar_corrida`); campo desconocido
dentro de `pipeline_config`; el cuerpo real del cliente sigue siendo válido; el motor
inexistente anidado sigue rechazándose; el preflight conserva `docking_engine` en la
raíz y rechaza `peptide_docking_engine`, `seed` y `target_id`. 177 pruebas vecinas
(evaluación, preflight, motores, MolChat) verdes.

---

## LUNA-05 — MolChat registraba y encolaba docking sin confirmación humana separada

**Severidad:** P2 (consumo de recursos y procedencia sin aceptación humana).
**Decisión del propietario (2026-10-03):** propuesta + botón a un endpoint autenticado.

### Diagnóstico

Reproduce por código en el HEAD: `run_docking` (`backend/services/ai/tools/docking_tools.py`)
construía la petición y llamaba a `registrar_corrida(..., exigir_preflight=True)` en el
**mismo turno** en que se interpretó el texto; `check_docking_status`, el clasificador
determinista y las llamadas nativas del modelo entraban todos por ahí. El preflight del
servidor valida bloqueantes pero no es una aceptación humana, y el contrato de la
auditoría pide receptor, motor, política efectiva y coste a la vista antes, y una
confirmación autenticada atada a esa propuesta.

Había además un **precedente que no se podía reutilizar tal cual**: el permiso web del chat
usa un marcador oculto y un «sí» tecleado. Para un permiso de red (que un SMILES salga o
no) puede bastar; para encolar una corrida de Vina, el «sí» es un mensaje de texto más y
la aprobación tiene que ser un acto distinto de lo que se escribió.

### Decisión tomada y el PORQUÉ

1. **`run_docking` propone, no lanza.** Corre el preflight REAL —el mismo informe de la
   pestaña Evaluación, extraído de `_enforce_submission_gates` a `comprobar_preparacion`
   para que lo que se muestra y lo que la puerta recalcula sea un solo cálculo— y, si no
   hay bloqueantes, guarda una propuesta y la presenta: ligando, receptor y cadena,
   origen, motor, protocolo efectivo (exhaustividad, poses, K, semilla), caja, política
   de heteroátomos, advertencias y «no evaluado» del preflight, y **coste aproximado** del
   estimador del producto (`services.estimacion`: rango, con su apoyo declarado —«modelo
   medido en otra máquina» o «calibrado con N acoplamientos de este equipo»—; sin
   estimación, se dice, no se inventa). Si el preflight bloquea, no hay propuesta que
   aprobar: se devuelve el motivo.
2. **Sólo `POST /ai/proposals/{id}/approve` lanza**, con la sesión de la cuenta
   (`get_current_user`, no el opcional). *Porque* «autenticada» tiene que significar algo
   más que «llegó por el mismo chat»: el botón llama a un endpoint propio; el «sí»
   tecleado no aprueba (y MolChat lo dice, ver 5).
3. **La petición que se ejecuta sale del servidor, nunca del cliente.** El cuerpo de la
   aprobación es cerrado (`extra="forbid"`, LUNA-04) y lleva sólo la huella que el
   investigador vio. La propuesta guarda la petición completa más la huella del preflight
   mostrado.
4. **Atada a esa propuesta, de cuatro maneras.** (a) Huella sha256 de cuenta + ligando +
   receptor + cadena + protocolo + huella del preflight. (b) Se aprueba **una sola vez**:
   reclamo atómico en el almacén (`cache.delete` devuelve True a una sola llamada; con 5
   aprobaciones simultáneas, 1 lanza y 4 reciben 410). (c) Sólo la aprueba **su cuenta**
   (otra recibe el mismo 404 que si no existiera) y expira a los 15 min. (d) La puerta
   común (`registrar_corrida`, `exigir_preflight=True`) **recalcula el preflight y lo
   compara con la huella mostrada**: si la preparación cambió entre la propuesta y la
   aprobación, 409 y no se lanza.
5. **Un «sí» escrito no aprueba.** `respuesta_a_un_si_escrito` lo intercepta antes de que
   llegue al clasificador y contesta dónde se aprueba. *Esto lo encontró el gate runtime
   real, no una prueba:* por el camino del clasificador determinista el asistente guarda
   un marcador de posición y la propuesta —con su marcador— queda en el mensaje del
   **sistema**; la primera versión de la guarda sólo miraba mensajes del asistente y un
   «sí» **generó una segunda propuesta** en vez del aviso (no lanzó nada, pero no era lo
   dicho). La guarda recorre ahora hacia atrás hasta el último mensaje del investigador,
   en ambos roles.
6. **Constancia en la conversación.** `conversacion_del_turno` (una `ContextVar`) publica
   la conversación del turno para que la propuesta sepa dónde nació sin tocar los cuatro
   sitios de `chat_service` que llaman a `run_docking`; al aprobar, el endpoint anota el
   lanzamiento (con su `task_id`) en esa conversación, de forma «best effort»: la corrida
   ya está lanzada y un historial que falla no la deshace.
7. **Frontend**: `PropuestaDeDocking.tsx` —tarjeta con «Aprobar y lanzar» /
   «Cancelar propuesta», estados explícitos (enviando, lanzada con su `task_id`,
   cancelada, «ya no está pendiente», error con el motivo del servidor) y una nota de
   que escribir «sí» no lanza nada—. `ChatMessage` extrae el marcador y sólo muestra la
   tarjeta cuando el mensaje terminó de llegar. Una tarjeta vieja de un historial
   recargado se marca como no pendiente al montarse. Textos en el catálogo es/en.

**Límites declarados.** La propuesta vive en el almacén efímero local (como las tareas en
curso): caduca a los 15 min y no sobrevive a un reinicio del motor; una propuesta caducada
se vuelve a pedir, que es preferible a una aprobación vieja sobre un receptor que quizá
cambió. Una aprobación que la puerta común rechaza **consume** la propuesta: una que
pudiera aprobarse dos veces es peor que una que hay que repetir. La anotación en la
conversación depende de que el turno la haya publicado; sin ella, la tarjeta igualmente
muestra el `task_id`. Y el texto de la propuesta, cuando llega por el clasificador, viaja
dentro del bloque de evidencia («dato persistido · propuesta pendiente de aprobación»):
el modelo puede reformularlo después, como ya podía con cualquier resultado de herramienta
(no se tocó).

### Contratos y archivos modificados

- `backend/services/ai/propuestas_de_docking.py` (nuevo): `proponer`, `consultar`,
  `rechazar`, `aprobar`, `mensaje_de_lanzamiento`, `respuesta_a_un_si_escrito`,
  `huella_de_propuesta`, `TTL_PROPUESTA_S = 900`, `MARCADOR`.
- `backend/services/ai/contexto_de_turno.py` (nuevo): `conversacion_del_turno`.
- `backend/services/ai/tools/docking_tools.py`: `run_docking` propone; descripción de la
  herramienta que ve el modelo («PROPONE… NO la lanza ni la encola»).
- `backend/services/ai/chat_service.py`: publica la conversación del turno e intercepta el
  «sí» escrito.
- `backend/api/routers/evaluation.py`: `comprobar_preparacion` extraído.
- `backend/api/routers/ai.py`: `GET /ai/proposals/{id}`, `POST …/approve`, `POST …/reject`.
- `docs/api/openapi-current.json`, `docs/45_API_CONTRACT_CURRENT.md`: contrato regenerado
  (tres rutas nuevas).
- `frontend/components/ai/PropuestaDeDocking.tsx` (nuevo), `ChatMessage.tsx`,
  `frontend/lib/api.ts`, `frontend/context/traducciones/ia.ts`.
- `scripts/accept_molchat_runtime.py`: el gate ahora comprueba el flujo de aprobación.
- Pruebas que codificaban «el chat encola» y cambiaron de sentido:
  `test_docking_desde_el_chat.py` (2) y `test_la_advertencia_de_calibracion_no_se_pierde.py`
  (el aviso de calibración ahora lo lleva el mensaje de lanzamiento y la propuesta).

### Pruebas de verificación

`backend/tests/test_propuesta_de_docking_molchat.py` (31): propone sin encolar y muestra lo
que la auditoría pide ver (receptor, cadena, motor, protocolo, caja, heteroátomos, coste,
advertencias); un preflight bloqueante no produce propuesta; aprobar entra por
`registrar_corrida` con `exigir_preflight=True` y la huella mostrada; una sola vez (también
con 5 aprobaciones concurrentes); huella distinta → 409 sin consumirla; otra cuenta → 404;
caducada → 410; rechazar la retira; una aprobación rechazada por la puerta común consume la
propuesta; HTTP: 200 con constancia en la conversación, 422 si el cliente intenta inyectar
la petición o manda una huella mal formada, 401/403 sin sesión, 404/410 para ajena y
desaparecida; el «sí» (y sus variantes) no aprueba y no se confunde con otra cosa, también
por el camino del clasificador; y una **garantía estructural por AST**: la única función de
`services/ai` y del router de IA que invoca `registrar_corrida` es
`propuestas_de_docking.aprobar`. Frontend: `PropuestaDeDocking.test.tsx` (20): aprobar con
id + huella sin escribir «sí» en el chat, cancelar, 410/404/409/red, y el marcador en
`ChatMessage` (se extrae, no aparece mientras se escribe, no genera tarjeta en un mensaje del
usuario). `tsc --noEmit` limpio.

**Gate runtime real (modelo local Qwen2.5-1.5B + Vina real), `accept_molchat_runtime.py`:**
**PASS**, con el modelo local y Vina reales. El turno trae una propuesta y ningún
`task_id`; un «sí» escrito recibe el aviso de que la aprobación es el botón y no lanza nada; la
aprobación de **otra cuenta da 404**; la de la cuenta dueña lanza la corrida (afinidad Vina
−5,885 kcal/mol, procedencia completa: receptor sellado, protocolo y versión); una **segunda
aprobación da 410** y no encola otra; tras reiniciar el motor la corrida citada es la misma y
la segunda cuenta no la ve (403). Se ejecutó **dos veces**: la primera pasó pero mostró el fallo
de la guarda del «sí» descrito en 5 (la respuesta a ese «sí» era una segunda propuesta, no
el aviso); tras corregirla, el «sí» recibe «Escribir «sí» no lanza el docking…». El gate ahora
exige ese aviso, para que el fallo no vuelva a pasar desapercibido.

---

## Observaciones que NO se tocaron (decisión del propietario) y lo ya resuelto

- **`xtb.exe` y el párrafo de copyleft de AGENTS.md — resuelto en el bloque 2 por
  decisión del propietario.** El párrafo omitía un binario **LGPL-3.0-or-later** que
  viaja en `tools/xtb/` y que `THIRD_PARTY_NOTICES.md` y `softwareCatalog.ts` ya
  declaraban; el SBOM lo lista ahora en `licencias_a_revisar.binarios`. Se añadió con
  la misma redacción factual de los avisos; no cambia ninguna licencia.
- **Docstrings con licencia vieja.** `rescoring/generate_gpu_dataset.py` y
  `rescoring/RTMScore/feats/extract_pocket_prody.py` dicen que MolDesign «se publica
  bajo AGPL-3.0-only»; la licencia vigente es PolyForm Noncommercial 1.0.0 (el ADR 79
  §2.1 ya reconoce el cambio). Es texto legal en archivos que la decisión de LUNA-01
  dejó intactos: sin tocar.
- **`npm_produccion` se construye del lockfile, no del bundle.** Incluye, p. ej., los
  `@img/sharp-libvips-*` (LGPL-3.0-or-later) de plataformas que un export estático para
  Windows no lleva. Es sobreinclusivo, lo cual es conservador para la afirmación sobre
  AGPL, pero no describe con exactitud lo que viaja.
- **`lzma-sys`**: ver LUNA-03 (GPL vendorizada que no se compila; observación para la
  revisión jurídica).
- **MPL-2.0** (5 crates) no está en `LICENCIAS_A_REVISAR`: política del propietario.
- **Sin automatizar:** la medición de textos de licencia en Rust y npm. Extender
  `check_copyleft_en_runtime.py` a esos ecosistemas queda como mejora abierta.

---

## Compuerta final y lo que apareció al verificar el artefacto

Todo se midió sobre el estado final (`075817b` más el golden `c1c83f6`):

| Comprobación | Resultado |
|---|---|
| `npm run stage:desktop` (bundle final) | 35 229 archivos, 1826,1 MiB |
| `check_openbabel_boundary.py --bundle --exigir-binario` | **17 comprobaciones, frontera intacta** (G2 aprobado; G1 sobre el bundle sin exenciones: 323 módulos) |
| `npm run build:desktop` | exit 0 (incluye `check:solana-boundary`) |
| `npm run smoke:prod` | **16/16** |
| Backend, Python embebido 3.11.9 | **3155 passed, 17 skipped** |
| Backend, Python de desarrollo 3.14.3 | **3216 passed, 4 skipped** (corre además lo que necesita `pypdf`) |
| Frontend `vitest run` | **1257 passed** en 134 archivos; `tsc --noEmit` limpio |
| `generate_sbom.py --check` · `generate_openapi_contract.py --check` · `generate_goldens.py --check` | verdes (SBOM: 168 Python, 1267 npm, 331 Rust, 4 binarios) |
| `accept_molchat_runtime.py` (Qwen local + Vina real) | **PASS**, dos veces (ver LUNA-05) |
| `accept_evaluation_runtime.py` (Vina real, reinicio, dossier) | **PASS** tras actualizar el golden (abajo): 2 contratos |

### Dos gates de aceptación que fallaban ANTES de este bloque

Verificar el artefacto, no sólo el código, destapó dos fallos que no son de Luna y que el
cierre de Sol no vio porque su compuerta fue `build:desktop` + `smoke:prod`, que no los
ejecutan.

1. **`accept_evaluation_runtime.py` — «Golden E2E pro: execution difiere»**
   (puerta 11 de `tauri:build`). SOL-05/SOL-07 (`83372c9`, `21d48bb`) añadieron
   `prepared_chains` a `execution_provenance.receptor_prep` y el golden E2E, sellado el
   2026-09-27, no se regeneró. Se midió: la diferencia es **una clave**,
   `prepared_chains = ["A", "P"]`, en los dos perfiles; afinidad (−5,885), caja, semilla,
   versiones, hashes de receptor, entradas y poses, idénticos; y `backend/services/docking`
   no cambió desde `315eb95`, así que no es de este bloque. El README de goldens exige
   explicar una diferencia antes de sellarla: esta es un campo de procedencia añadido a
   propósito. Se añadió a mano (8 líneas, commit `c1c83f6`) y la puerta pasa. Es la
   verificación de punta a punta de LUNA-04: sus cuerpos de preflight y submit, con los
   modelos ya cerrados, entran sin rechazo.
2. **`accept_moldex_runtime.py` — NO se tocó.** Falla en `POST /blockchain/certify`: el
   backend contesta **409** («La firma institucional fue retirada. Usa el registro
   experimental de Solana devnet…», `docs/83_ADR_SOLANA_DEVNET_POC.md`) y el script espera
   `{200, 400, 401, 403, 404, 422, 500, 503}`. Es un desfase del script con el POC de
   Solana, anterior a Luna y fuera de su alcance; los pasos de preflight y submit que sí
   tocan LUNA-04 van antes y pasan. Queda abierto. No se ejecutaron
   `accept_batch_runtime.py` ni `accept_msix_store.py` (los cuerpos que envían se leyeron:
   sólo campos modelados).

## Qué quedó abierto a propósito, y por qué

- **Revisión jurídica externa** (AGENTS.md y ADR 79 ya la recomiendan antes de vender
  licencias comerciales): nada de este documento la sustituye. Observaciones para ella:
  `lzma-sys` (GPL vendorizada que no se compila, LUNA-03), las 5 crates MPL-2.0 y los
  docstrings con «AGPL» de dos scripts de desarrollo.
- **La excepción de Open Babel es cerrada.** Una quinta entrada en `EXCEPCIONES_DEV_ONLY`
  es decisión del propietario. G1b sólo sabe comprobar el empaquetado de rutas bajo
  `rescoring/`; una excepción en `backend/` fallaría hasta que se le enseñe, a propósito.
- **Sin automatizar:** la lectura de textos de licencia en Rust y npm (sólo se midió una
  vez para Rust) y la reconciliación de los archivos auxiliares de `tools/*` en el SBOM.
  El SBOM de npm sale del lockfile y no del bundle (sobreinclusivo).
- **`LICENCIAS_A_REVISAR` no incluye MPL**: política del propietario.
- **MolChat:** la propuesta es efímera (15 min, no sobrevive a un reinicio), una aprobación
  rechazada por la puerta común la consume, y el texto de la propuesta puede ser
  reformulado por el modelo cuando llega por el clasificador, como cualquier resultado de
  herramienta; no se tocó. Una tarjeta de un historial recargado se marca al montarse, pero
  la constancia del lanzamiento en la conversación depende de que el turno la publicara.
- **El clasificador de seguridad:** no denegó ninguna acción en este bloque.
- **Un incidente de procedimiento, ya declarado arriba:** se ejecutó un script de la
  carpeta de evidencia sellada que reescribió su propio JSON (mismo sha256).
