# 86 — Distribución MSIX / Microsoft Store

**Rama:** `claude/msix-store-distribution`
**Base:** `codex/release-hygiene`
**Fecha:** 2026-09-10

> **ACTUALIZACIÓN 2026-09-12 — leer antes que el resto del documento.** Tres
> cosas que este documento da por vigentes ya no lo son:
>
> 1. **§5.0 ya no bloquea.** `check:pesos-stacking` se cerró en `5453bce`. El
>    paquete oficial `1.0.0.0` está construido, firmado y con las dos
>    aceptaciones en **PASS sobre su propio sha256**: ver §5.3.
> 2. **§1.1 ya no aplica.** Las descargas de modelos se redirigen a
>    `%USERPROFILE%\MolDesign\models` bajo identidad de paquete
>    (`downloader.rs::model_root` + `lib.rs::is_packaged_app`). La frontera de
>    contención de `resource_path` sigue en pie: sólo cambió la raíz que
>    contiene. Queda **sin ejercitar por ningún arnés**.
> 3. **Los artefactos ya no viven en `dist/msix`.** Producción es `E:\rel`, en
>    otro disco físico, con una carpeta `v<versión>` por envío. Ver más abajo.

Ruta **separada** de NSIS. El instalador NSIS sigue intacto
(`tauri.conf.json` + `tauri.conf.prod.json` → `npm run tauri:build`); hay un
autotest que lo comprueba en cada cambio.

## 0. Dónde aterrizan los artefactos (2026-09-12)

Producción está **separada del desarrollo por disco**: `E:\rel` es otra unidad
física. Dentro, una carpeta por versión del Store que **nunca se reutiliza**:

```
E:\rel\devcert.pfx                       (compartido, no se commitea)
E:\rel\v1.0.0.0\layout\
E:\rel\v1.0.0.0\amezcua-dev.com.MolDesign_1.0.0.0_x64.msix
E:\rel\v1.0.0.0\build-evidence.json
E:\rel\v1.0.0.0\accept-evidence.json
E:\rel\v1.0.0.0\accept-cases-evidence.json
E:\rel\v1.0.0.0\wack-report.xml          (pendiente: exige consola elevada)
```

Qué cierra esto, en concreto:

| Fallo observado | Qué lo cierra |
|---|---|
| El `.msix` se reempaquetó con el mismo nombre y las tres evidencias quedaron describiendo bytes inexistentes | Carpeta por versión + **sha256 del paquete** en cada evidencia |
| `build-evidence.json` declaraba un commit con 25 ficheros sin commitear | `arbol_limpio` y `ficheros_sin_commitear` en la evidencia |
| Un `--check` de desarrollo corrompió `dist/base-v1.0.0.zip` | Producción fuera del árbol de trabajo |

Se cambia con `--dist` o `MOLDESIGN_DIST_RAIZ`. La raíz debe ser **corta**:
`build_msix.py` mide el path proyectado sobre el runtime real antes de copiar y
aborta si no cabe en los 260 de Windows. Con la raíz antigua
(`D:\moldesign-build\dist\msix\layout`) el fichero más hondo quedaba en 238 y el
margen era de 22 caracteres; con `E:\rel\v1.0.0.0\layout` queda en **225, margen
35**. El fichero que marca el límite es de `torch` y sus `third_party` anidados. Si la unidad de producción no está, el build **aborta**: no se repliega al
disco de desarrollo, porque eso dejaría el paquete en un sitio con la evidencia
diciendo otro.

> **Sin push ni envío a Partner Center.** Nada de este trabajo sale de la
> máquina. No se editó `LICENSE`, `LICENSE-MODELS`, `COMMERCIAL-LICENSE.md`,
> SBOM, textos de licencia ni ningún artefacto científico.

---

## 1. Decisiones que NO tomé, y por qué

Dos cosas que el MSIX exige y que no me corresponden.

### 1.1 BLOQUEANTE — Las descargas de modelos no caben en MSIX

`launcher-manifest.json` declara dos módulos descargables bajo demanda:

| Módulo | Tamaño | Destino declarado | `required` |
|---|---|---|---|
| `esmfold-weights` | 8,44 GB | `esmfold/models/` | `false` |
| `llm-qwen15` | 1,12 GB | `models/llm/` | `false` |

Ambos destinos son **relativos a `resource_dir`**, y `downloader.rs` no los
acepta de otro modo. `resource_path()` (`src-tauri/src/downloader.rs`, ~L67-108)
es una **frontera de seguridad deliberada**: exige que todo destino de descarga
o creación resuelva **dentro** de `resource_dir`, y además canonicaliza el
ancestro existente más cercano para que un symlink plantado en un directorio
padre no permita escapar. El propio código lo dice:

> *«Checking only the final path misses a planted symlink in a parent directory
> when the final file does not exist yet; that would let a download/create
> operation escape the trusted resource tree.»*

En MSIX, `resource_dir` es
`C:\Program Files\WindowsApps\<paquete>\resources\`, que es **de sólo lectura**
para la app. Conclusión: **en la versión Store, ESMFold y el LLM local no se
pueden descargar.**

Las salidas posibles son excluyentes y ninguna es mía:

1. **Redirigir** las descargas a `LocalAppData` y mover o relajar esa frontera
   de seguridad. Cambia un control puesto a propósito y traslada dónde viven
   pesos verificados por hash.
2. **Publicar la versión Store sin modelos descargables**, declarando esas
   funciones como no disponibles en ese canal.

La opción 1 toca seguridad **y** distribución de modelos, que es terreno de
`LICENSE-MODELS` y de los repos de Hugging Face pendientes de revisión
jurídica. Por eso me detuve aquí y **no modifiqué `downloader.rs`**.

**Esto no bloquea el resto**: la evaluación M4 no usa ESMFold ni el LLM. El MSIX
se construye, instala, ejecuta y evalúa con normalidad.

### 1.2 `runFullTrust` necesita una justificación escrita por una persona

El paquete declara:

```xml
<rescap:Capability Name="runFullTrust" />
```
con `EntryPoint="Windows.FullTrustApplication"`.

No es opcional: el backend es un **intérprete Python embebido propio** lanzado
como subproceso que abre un socket en `127.0.0.1`; **AutoDock Vina** se invoca
como proceso externo; **Open Babel** se invoca por CLI como programa
independiente por frontera de licencia GPL-2.0-only. Sin plena confianza no hay
pipeline.

`runFullTrust` es una capacidad **restringida**: Partner Center exige
justificación escrita y la revisa una persona. **Ese texto es decisión del
responsable del producto**, no de un script. Los hechos técnicos que lo
sustentan están en `msix/msix-config.json → nivel_de_confianza`.

### 1.3 El mapeo de versión es política de publicación

`1.0.0-alpha.2` → **`1.0.2.0`**. El mapeo completo está en §3. Es **política de
publicación**, no un hecho técnico, y necesita confirmación antes del primer
envío: una vez publicada una versión, el Store no admite retroceder.

---

## 2. Por qué hay dos pasos y no uno

`tauri build --bundles` admite exactamente `msi` y `nsis` en la CLI 2.11.
**No hay target MSIX.** Verificado sobre la CLI instalada:

```
-b, --bundles [<BUNDLES>...]   [possible values: msi, nsis]
```

La guía oficial para Store con Tauri es la que se sigue aquí: compilar con Tauri
y empaquetar después con el **CLI `winapp` de Microsoft**
(`Microsoft.WinAppCli` 0.6.1, moniker `winapp`), instalado con winget durante
este trabajo. `build_msix.py` cae a `makeappx.exe` del Windows SDK si `winapp`
no está.

Fases: `stage → tauri → assets → manifest → layout → package → sign`.

La fase `tauri` **no** duplica `stage:desktop` ni `build:desktop`: el
`beforeBuildCommand` de `tauri.conf.json` ya encadena las quince puertas del
producto (runtime-árbol, CSP, manifiesto de rescoring, M5, goldens, pesos de
stacking, frontera de Open Babel, staging, verificación del runtime, gate de
evaluación, dossier, build del frontend, API exportada, assets remotos).
Saltárselas produciría un MSIX que no pasó las mismas puertas que el NSIS.

---

## 3. Identidad y versión

```
Package/Identity/Name                      amezcua-dev.com.MolDesign
Package/Identity/Publisher                 CN=6441FBBA-B77A-4619-9CEB-ACEDE74573C0
Package/Properties/PublisherDisplayName    amezcua-dev.com
ProcessorArchitecture                      x64
```

Exacta e inmutable. Cambiar cualquiera de las tres rompe la correspondencia con
la reserva de Partner Center y el paquete deja de ser actualizable para quien ya
lo tenga instalado. Los valores están escritos **a mano** en el autotest, de
modo que editar `msix-config.json` hace fallar la prueba en vez de que ésta se
adapte.

**Versión:** cuatro campos, `Major.Minor.Build.Revision`, con **Revision siempre
0** — el Store reserva ese campo y rechaza un paquete que lo use.

| semver | Build | Versión de Store |
|---|---|---|
| `alpha.N` | `N` | `1.0.N.0` |
| `beta.N` | `10000 + N` | `1.0.1000N.0` |
| `rc.N` | `20000 + N` | `1.0.2000N.0` |
| sin prerelease | `30000 + patch` | `1.0.3000P.0` |

Los tramos separados garantizan `alpha < beta < rc < final` dentro de un mismo
`Major.Minor`, que es lo que el Store exige. Hay un autotest que lo comprueba y
otro que rechaza campos > 65535 y semver irreconocible (aborta en vez de
inventar un número).

---

## 4. Escritura fuera de `WindowsApps`

`C:\Program Files\WindowsApps\...` es de sólo lectura para la app.

| Qué | Dónde | Fuente |
|---|---|---|
| Datos y SQLite | `%USERPROFILE%\MolDesign\data` | `core.config.local_data_dir` |
| Poses y artefactos | `%USERPROFILE%\MolDesign\data` | ídem |
| Logs del backend | `%TEMP%\MolDesign\logs` | `backend.rs::bundled_log_dir` |
| Temporales de Vina | `%TEMP%\vina` | `core.config.vina_temp_dir` |
| Bytecode | no se escribe | `PYTHONDONTWRITEBYTECODE=1` + `.pyc` precompilado en el bundle |
| **Pesos descargables** | **`resources/` → imposible en MSIX** | §1.1 |

`accept_msix_store.py` no da estas rutas por buenas: **se las pregunta al
backend empaquetado** (ejecuta su `get_settings()` con el intérprete que viaja
dentro del paquete instalado) y falla si alguna cae bajo `WindowsApps`. Además
intenta escribir una sonda en el directorio de instalación para confirmar que es
de sólo lectura, y declara el resultado no concluyente si la prueba corre
elevada.

---

## 5. Qué se construyó y qué se validó

### 5.0 BLOQUEANTE PREEXISTENTE — `check:pesos-stacking` falla en la rama

**El `.msix` no llegó a construirse.** La puerta 6 de las quince del
`beforeBuildCommand` falla, y **falla igual en el árbol principal**, sobre el
mismo commit y sin nada mío: bloquea también el instalador NSIS.

```
ERROR: la interfaz declara pesos de stacking que el backend no aplica:
  - default · vina:  la interfaz muestra 0.20 y el backend aplica 0.25
  - default · xgb:   la interfaz muestra 0.60 y el backend aplica 0.75
  - default · clgnn: la interfaz muestra 0.20 y el backend aplica 0.00
  … (las seis familias, idéntico)
```

**Causa raíz**, visible en el log de la propia puerta:

```
stacking_weights_registry_unavailable, using fallback
  error="[Errno 2] No such file or directory: 'artifacts\\sci_config_registry.json'"
```

`sci_config_registry.json` **no existe en ninguna parte del árbol**. El cargador
cae a un fallback que **elimina `clgnn` y renormaliza el resto**, produciendo
exactamente la degradación descrita en `docs/85` §5 — ahora confirmada por una
puerta independiente y sobre el árbol de desarrollo, no sólo sobre el bundle.

La puerta dice qué hace falta decidir, y no es mío:

> *«La fuente que decide el ranking es `rescoring/artifacts/stacking_weights.json`.
> Si el cambio es intencional, cámbialo ahí y actualiza la interfaz; si la
> interfaz quería describir otra cosa, no la llames peso.»*

Las tres salidas —restaurar el registro ausente, cambiar
`stacking_weights.json`, o corregir lo que la interfaz declara— son **decisiones
científicas**. Me detuve aquí, como pide el encargo.

**Tampoco construí el `.msix` saltándome esa puerta.** `build_msix.py` no tiene
forma de omitirla, a propósito: un paquete que no pasó las mismas puertas que el
NSIS no debería existir, y un bypass que se commitea deja de ser temporal.

En consecuencia, en aquel momento **NO se ejecutaron**: instalación, arranque, evaluación
normal/avanzada, persistencia tras reinicio, actualización, desinstalación ni
**WACK**. El arnés que los ejecuta está escrito y listo
(`scripts/accept_msix_store.py`); le falta un paquete.

*(WACK sí está disponible en esta máquina:
`C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe`.)*

### 5.1 Autotests de contrato — 21 pasan

`msix/tests/test_msix_contrato.py`, sin necesidad de paquete construido:
identidad exacta, mapeo de versión y su monotonía, cuarto campo 0, límites de
rango, `runFullTrust` declarado y marcado como restringido, **NSIS intacto**,
CSP del build de Store idéntica a la de producción, y ausencia de claves de
comentario en la config de Tauri.

Esa última prueba existe porque el problema ocurrió: `_nota` y `_csp` tumbaron
el build con *«Additional properties are not allowed»*. La justificación vive
ahora en `msix/README.md`, no dentro del JSON.

### 5.2 Verificado directamente sobre el runtime staged

`npm run stage:desktop` sí corrió (no es una puerta, es el staging):
**35 049 ficheros, 1 801,5 MiB**, con 2 485 `.pyc` precompilados y el runtime de
Visual C++ app-local colocado.

Interrogando al **intérprete que viaja en el bundle** por su configuración
efectiva:

```json
{
  "local_data_dir": "C:\\Users\\<usuario>\\MolDesign\\data",
  "vina_temp_dir":  "C:\\Users\\<usuario>\\AppData\\Local\\Temp\\vina",
  "tempdir":        "C:\\Users\\<usuario>\\AppData\\Local\\Temp"
}
```

**Ninguna cae bajo `WindowsApps`.** Es la comprobación de §4 hecha sobre el
runtime real, aunque todavía no dentro del contenedor MSIX.

### 5.3 Aceptación sobre el paquete instalado — EJECUTADA EN PASS (2026-09-12)

`scripts/accept_msix_store.py` comprueba, en este orden: identidad, versión,
confianza, integridad del runtime, rutas de escritura, instalación, arranque,
**evaluación normal y avanzada**, persistencia tras reiniciar la app,
actualización conservando datos, y desinstalación **sin borrar datos**.

Corrida sobre `1.0.0.0`, sha256 `c17283ff88bc…`, que es **el mismo sha que
declara la evidencia de build**: por primera vez las tres evidencias hablan de
los mismos bytes y no de un nombre de fichero.

| Qué | Resultado |
|---|---|
| Identidad, versión `1.0.0.0`, `runFullTrust` | correctos |
| Runtime en el paquete | 35 130 ficheros; los 8 exigidos presentes |
| `/health` | 200, `version: 1.0.0`, los siete componentes `healthy` |
| Evaluación normal (aspirina) | `-5.665` kcal/mol, 38.0 s, Vina 1.2.7 |
| Evaluación avanzada (paracetamol) | `-4.879` kcal/mol, 9.1 s |
| Persistencia tras reiniciar | ambas afinidades coinciden |
| Desinstalación | paquete ausente, 50 ficheros de usuario conservados |

Las dos afinidades son idénticas a las del paquete anterior: subir la versión,
manifestar PerMonitorV2 y abrir el scope del opener **no movieron el resultado
científico**, que es lo que había que comprobar.

`accept_msix_cases.py` también en PASS: el caso creado reaparece tras cerrar y
abrir, con carpetas en C: y en D:.

**La actualización también está ejercitada** desde el 2026-09-12, tras una
auditoría externa que la señaló. `--store-build 1` genera el paquete `1.0.1.0`
del mismo runtime staged, sin recompilar y sin tocar `msix-config.json`, y el
arnés lo instala encima del `1.0.0.0`:

```
actualizacion: {"de": "1.0.0.0", "a": "1.0.1.0", "datos_conservados": true}
```

Lo único que sigue sin arnés es la **descarga de modelos bajo identidad de
paquete**: el redirect a `%USERPROFILE%\MolDesign\models` está escrito,
compilado y empaquetado, pero ninguna prueba lo ejercita instalado.

### 5.4 Lo que la auditoría del 2026-09-12 cambió en el paquete

| Qué | Antes | Ahora |
|---|---|---|
| `padelpy` + `PaDEL-Descriptor.jar` | 22,5 MB viajando bajo **AGPL-3.0**, declarados MIT en el SBOM y ausentes de los avisos | retirados: ningún módulo los importaba |
| Código fuente de Open Babel | una oferta que enumeraba tarballs ausentes | acompaña al binario, GPL-2.0 §3(a), SHA-256 verificados |
| `README-PROCEDENCIA.md` | afirmaba que MolDesign es **AGPL-3.0-only** | PolyForm Noncommercial 1.0.0, que es lo que la plantilla ya decía |
| Versión en la interfaz | `v1.0.0-alpha.2` en pie, lanzador y menú | sale de `PRODUCT.version`, con gate |
| Procedencia | evidencia citando un commit no publicado | cita `10f4b07`, que es `main` y el tag `v1.0.0` |
| Tamaño | 724,4 MiB | 738,6 MiB (−22,5 AGPL, +36,7 fuente) |

`scripts/check_copyleft_en_runtime.py` es la puerta que habría visto lo primero.
Encontró un segundo caso en su estreno: ReportLab empaqueta una tipografía GPL
que ahora está declarada.

Se valida sobre el paquete **instalado**, no sobre el layout: en
`WindowsApps` el árbol es de sólo lectura y el proceso corre con identidad de
paquete. Un fallo de escritura sólo aparece ahí; validar el layout demostraría
únicamente que los ficheros existen.

Las dos evaluaciones usan moléculas distintas —aspirina y paracetamol— y el
script **comprueba** que no comparten `molecule_id`: si lo hicieran, una
sobrescribiría a la otra y estaríamos probando una sola corrida.

---

## 6. Notas de reproducibilidad

El worktree de esta rama necesitó piezas que `.gitignore` excluye y que un
checkout limpio no trae: `python-embed` (junction al árbol principal), `tools/`
completo (incluido `llama/`, que `bootstrap_dev_tree.py --check` exige),
`esmfold/` (tokenizador, 2,3 KB), `data/molgraph_seed.db` y los tres checkpoints
de los perfiles M5-Zn.

Sobre esos checkpoints: `check:goldens` falló al principio con
`m5_zn_replay.json difiere`. **No regeneré el golden** — el propio mensaje dice
que una diferencia exige explicación. La causa era que faltaba un fichero, y su
ruta no es la que sugiere el nombre: el perfil CA2/3DC3 lo lee de
`data/gnn_v31/checkpoints/benchmark_checkpoint_ca2.json`, no de
`data/benchmark_checkpoint_ca2.json`. Copiado el fichero correcto, las 8
corridas doradas verifican sin tocar nada científico.

Esto confirma lo ya sabido: **un clon limpio no puede construir** hasta que se
publique `runtime-base-v1.1.0.zip`. No es un problema del MSIX.

---

## 7. Pendiente de decisión

| # | Decisión | De quién | Bloquea |
|---|---|---|---|
| ~~**0**~~ | ~~`check:pesos-stacking`~~ | — | **CERRADA** en `5453bce` |
| ~~**1**~~ | ~~Modelos descargables en MSIX~~ | — | **CERRADA**: se redirigen a `%USERPROFILE%\MolDesign\models`. Sin arnés que lo ejercite |
| **2** | Texto de justificación de `runFullTrust` para Partner Center. Borrador en `docs/STORE_RUNFULLTRUST_JUSTIFICATION.md`, pendiente de aprobación humana. | Responsable del producto | El envío |
| **3** | Confirmar el mapeo de versión antes del primer envío. Irreversible: el Store no admite retroceder. | Responsable de release | El envío |
| **4** | Certificado de producción: el paquete de Store lo firma el Store; el `devcert.pfx` de `E:\rel` es sólo para probar y no se distribuye ni se commitea. | Release | El envío |
| **5** | URLs públicas estables de `LICENSE` y `PRIVACY.md`: el remoto `origin` está vacío y la URL que declara `STORE_SUBMISSION_LEGAL.md` hoy es 404. | Release | El envío |

La cadena, con la raíz de producción nueva:

```bash
python scripts/build_msix.py --todo                     # -> E:\rel\v1.0.2.0\
python scripts/accept_msix_store.py --msix E:\rel\v1.0.2.0\amezcua-dev.com.MolDesign_1.0.2.0_x64.msix
python scripts/accept_msix_cases.py  --msix E:\rel\v1.0.2.0\amezcua-dev.com.MolDesign_1.0.2.0_x64.msix
```

Las dos aceptaciones escriben su evidencia **junto al paquete**, con su sha256.
Falta el WACK sobre ese mismo `.msix`, en consola elevada.
