# Gate de release — qué está comprobado y qué falta

**Fecha:** 2026-08-31
**Estado:** 🟡 parcial. Lo automatizable está hecho y verde; lo que falta necesita
máquinas, un certificado y personas, y está nombrado uno por uno.

`scripts/check_release_pipeline.py` ya validaba la **estructura** del pipeline
(stage → runtime gate → frontend → Tauri/NSIS). Lo que faltaba era la sustancia:
qué se distribuye, bajo qué licencia, y si actualizar destruye el trabajo de
alguien. Esas dos se cierran aquí.

## Lo que este corte comprueba

### Actualizar no destruye trabajo

`backend/tests/test_una_base_anterior_sobrevive_a_la_actualizacion.py`
(`10 passed`). Es el criterio que más caro sale si falla: no hay deshacer.

Esta tanda añadió cuatro migraciones sobre datos existentes, y la del grafo es la
única que **borra del origen** —mueve filas de `molgraph.db` a
`molgraph_private.db`—, así que es la que más se ejercita:

| Comprobación | Resultado |
|---|---|
| Conversaciones anteriores a `user_id` | se conservan, sin dueño (D-07) |
| Catálogo `ai_catalog` anterior | se conserva, sin dueño |
| Índice FTS5 (que no admite `ALTER`) | se reconstruye sin perder lo indexado |
| Grafo: lo del seed se queda, lo local se mueve | verificado |
| Nada se pierde en el traslado | los tres SMILES siguen visibles |
| Repetir la actualización | idempotente: no duplica ni reborra |
| Instalación nueva sin datos previos | no falla |
| Corpus corrupto | degrada; lo privado sobrevive en su archivo |

La última importa más de lo que parece: es la razón de haber separado los
archivos. Antes, un `molgraph.db` corrupto se llevaba por delante todo.

### SBOM y licencias

`scripts/generate_sbom.py --write | --check`, salida en `docs/api/sbom.json`.

Alcance deliberadamente estrecho: **el runtime que se distribuye**, no el árbol
del desarrollador. En esta máquina hay 281 distribuciones Python instaladas y
sólo 170 viajan en `python-embed`. Un SBOM que declarara las 281 sería peor que
ninguno: afirmaría algo falso sobre lo que el investigador recibe.

| Componente | Cuenta |
|---|---|
| Paquetes Python en `python-embed` | 170 |
| Paquetes npm de producción | 1353 |
| Binarios de terceros, con SHA-256 | 2 (`vina.exe`, `llama-server.exe`) |

**Un hallazgo que bloqueaba la publicación.** El primer inventario encontró
`ua-parser-js@2.0.10` bajo **AGPL-3.0-or-later** en el árbol de producción,
cinco veces. Llegaba por `@solana/wallet-adapter-wallets` →
`@trezor/connect` → `@trezor/env-utils`. Distribuir un binario propietario que
enlaza AGPL no es una cuestión de estilo.

Lo que lo hace corregible sin discutir alcance: **`@solana/wallet-adapter-wallets`
estaba declarado en `package.json` y no se importaba en ninguna parte**.
`WalletProvider.tsx` pasa `wallets={[]}` y deja que el Wallet Standard detecte
las carteras. Retirada la dependencia:

- la AGPL desaparece del árbol de producción;
- npm de producción baja de **1920 a 1353** paquetes;
- `tsc --noEmit` limpio, frontend `638 passed`, builds web y desktop verdes.

### Revisión LGPL — 2026-08-31

Esta revisión técnica corrige dos premisas del inventario inicial. No sustituye
la aprobación de un abogado para el modelo comercial elegido.

**Meeko 0.7.1 — LGPL-2.1: conservar con cumplimiento.** No se usa solamente por
subproceso: el backend también importa `MoleculePreparation`,
`PDBQTWriterLegacy` y otras APIs de Meeko. La copia distribuida en
`python-embed` conserva el código Python y `meeko-0.7.1.dist-info/licenses/LICENSE`;
los 60 archivos con hash de `RECORD` coinciden, por lo que no hay modificaciones
locales. Al ser una biblioteca Python separada y reemplazable, el riesgo técnico
es bajo, pero el instalador debe dar aviso visible, conservar LGPL-2.1 y ofrecer
el código fuente exacto de Meeko. La EULA no puede prohibir la modificación de
la biblioteca ni la ingeniería inversa necesaria para depurar esa modificación.
Fuente: <https://github.com/forlilab/Meeko/blob/develop/setup.py> y LGPL-2.1
incluida en la distribución.

**Open Babel 3.1.1.23 — GPL-2.0-only: resuelto por la vía técnica.**
Añadido el 2026-09-05 y cerrado el mismo día. Esta revisión no lo incluía, y el
gate tampoco lo delataba: `generate_sbom.py` buscaba la subcadena `GPL`, y el
paquete declara su licencia como `GNU GENERAL PUBLIC LICENSE`, donde esa
subcadena no aparece. El detector ya normaliza el nombre largo.

**La pregunta que quedaba abierta se comprobó, y la respuesta era la mala.** El
paquete distribuye `GPL-2.0-only` —GPL versión 2 *sin* «o posterior»—, que no
permite relicenciar bajo GPL-3/AGPL-3. Y la afirmación de que se invocaba «como
biblioteca Python» era falsa en el único punto de uso vivo (`vina_service` ya lo
llamaba por subproceso) y peor de lo que sugería en todo lo demás: los bindings
viajaban en `site-packages`, dos módulos de `rescoring/` los importaban, y el
binario se resolvía dentro del paquete Python con un respaldo a `"obabel"` a
secas que el `PATH` podía resolver a cualquier cosa.

Ya no. Open Babel **sigue en el instalador**, pero como **programa independiente**
en `tools/openbabel/`, fuera del entorno Python importable, con manifiesto, hash,
licencia y procedencia propios, invocado por un adaptador único que verifica el
hash antes de ejecutar y nunca resuelve por `PATH`. Decisión completa en
[`79_ADR_FRONTERA_OPEN_BABEL.md`](79_ADR_FRONTERA_OPEN_BABEL.md).

Lo que el gate comprueba ahora, y bloquea el build si falla
(`scripts/check_openbabel_boundary.py`, `npm run check:openbabel`):

| | Comprueba |
|---|---|
| G1 | el código de producción no importa `openbabel`, `pybel` ni `_openbabel` |
| G2 | esos bindings no están en el `site-packages` del bundle |
| G3 | producción no resuelve `obabel` por `PATH` |
| G4 | el ejecutable empaquetado está donde dice el manifiesto |
| G5 | los 70 archivos coinciden con sus hashes |
| G6 | `obabel -V` devuelve la versión declarada |
| G7 | una conversión PDBQT→SDF real funciona en el bundle |
| G8 | el SDF convertido es el que se persiste |
| G9 | el SBOM y la pantalla de licencias no lo llaman `GPL-2.0-or-later` |

Cada una lleva autotest positivo y negativo, y las que miran el disco se prueban
rompiendo copias del árbol en
`backend/tests/test_guarda_frontera_open_babel.py`.

**Lo que sigue pendiente y sí exige abogado:** que la frontera CLI —la
interpretación estándar de la distinción entre agregación y obra combinada—
aplique a este caso concreto. La diferencia respecto a la versión anterior de
este párrafo es que ahora esa conversación se tiene sobre hechos comprobables.

**Y un requisito de la GPLv2 §3 sin ejecutar, que SÍ bloquea una publicación
seria:** la oferta de código fuente correspondiente. Un enlace a GitHub no basta
por sí solo; cada publicación debe adjuntar la fuente de la versión exacta
distribuida. `python scripts/verify_release_source_offer.py --check` lo comprueba
y **pasa localmente** porque los dos archivos de oferta de fuente ya están preparados en dist/source-offer/. Todavía no se han publicado ni adjuntado a un release; el gate seguirá siendo obligatorio para cada versión distribuida.

**Doce paquetes sin licencia en su metadata — cerrados el 2026-09-07.**
Once se resolvieron leyendo los archivos de licencia que sí viajaban dentro de
cada paquete. El duodécimo, `jsonalias` 0.1.1, no tenía licencia comprobable y
llegaba exclusivamente por `solders`/`solana-py`.

La integración Solana se rediseñó: firma en el frontend con Web3.js y
preparación/verificación en el backend por JSON-RPC de la biblioteca estándar.
`solana`, `solders` y `jsonalias` ya no están en requisitos, runtime ni SBOM.
El SBOM actual informa cero paquetes Python y cero npm sin licencia declarada.
La decisión y sus límites están en
[`83_ADR_SOLANA_DEVNET_POC.md`](83_ADR_SOLANA_DEVNET_POC.md).

**rpc-websockets 9.3.9 — LGPL-3.0-only: cumplimiento implementado.** Sigue
incorporado por @solana/web3.js@1.98.4. MolDesign se publica actualmente
bajo PolyForm Noncommercial 1.0.0 y el instalador entrega el aviso específico,
el texto LGPL-3.0
completo, el lockfile y las instrucciones de reconstrucción/reemplazo en
`frontend/public/legal/SOURCE_CODE_AND_RELINKING.md`. No bloquea esta
distribución abierta; sí tendría que revisarse de nuevo antes de ofrecer un
binario cerrado bajo otra licencia.
## Lo que falta, y por qué no lo puedo hacer yo

Cada uno dice qué recurso necesita. Los cinco primeros están en el §14 del
[plan de cierre](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md) como decisiones del
propietario.

| Criterio | Qué hace falta |
|---|---|
| **CI remoto sobre checkout limpio** | Un remoto y un push. El clon limpio ya **sí** se probó, localmente y contra el commit real (`git clone` del propio repositorio, no el árbol de trabajo): ahí aparecieron los diez fallos del backend y los tres gates rotos que la tabla de abajo documenta, y ahí están ahora en verde. Lo que falta es ejecutarlo en el runner de GitHub, que exige el repositorio creado. |
| **Instalador sin Node, Rust ni Python externos** | Construir el NSIS y probarlo. La cadena está verificada estructuralmente (`check_release_pipeline.py`), no ejercitada de extremo a extremo. |
| **Windows 10 y 11 limpios** | Dos VMs. |
| **Upgrade desde bases anteriores, backup y rollback** | La parte de **datos** está cubierta arriba. Falta el **backup y rollback del instalador**, que exige el instalador construido. |
| **Desinstalación sin destruir experimentos** | El instalador. Es el criterio hermano del anterior y el que más daño hace si falla. |
| **Vulnerabilidades alcanzables** | Una base de datos actualizada (OSV o GitHub Advisories) y por tanto red y una decisión de servicio. El inventario ya está listo para alimentarla. |
| **Firma Authenticode** | El certificado y su custodia. |
| **Hashes y manifiesto de release** | Los binarios de terceros ya llevan su SHA-256 en el SBOM. El manifiesto del artefacto final necesita ese artefacto. |
| **Piloto observado con investigadores** | Reclutarlos y su consentimiento de datos. |

## Verificación local de la batería de CI

Ejecutado **sobre un clon limpio**, no sólo sobre el árbol de trabajo. Esa
distinción era el agujero: la tabla anterior decía «árbol de trabajo» y con
razón, porque en un clon limpio tres gates fallaban y el backend daba diez
fallos. Todos por lo mismo: artefactos que el repositorio no distribuye y que
en la máquina del mantenedor siempre estaban. Ver el commit `6f81a78` y el
doc. 78.

| Paso de CI | Árbol de trabajo | Clon limpio |
|---|---|---|
| `ruff check api core db services --select E9,F63,F7,F82` | limpio | limpio |
| `pytest backend/tests` | `2082 passed`, 2 omitidas | ``2069 passed`, 15 omitidas` |
| `pytest rescoring/tests` | `307 passed`, 9 omitidas | ``300 passed`, 16 omitidas` |
| `report_test_counts.py --check` | verificado | verificado |
| `generate_openapi_contract.py --check` | verificado | verificado |
| `check_docs_links.py --check` | verificado | verificado |
| `generate_runtime_inventory.py --check` | verificado | verificado |
| `check_stacking_weights_ui.py --check` | verificado | verificado |
| `check_release_pipeline.py` | verificado | verificado |
| `generate_sbom.py --check` | verificado | **no verificable** (1) |
| `generate_model_manifest.py --check` | verificado | **no verificable** (2) |
| `check_vina_importance_gate.py` | verificado | verificado |
| `tsc --noEmit` | limpio | — |
| `vitest run` | `852 passed`, 95 archivos | — |

**(1) y (2): los dos gates que un clon limpio no puede comprobar.** El SBOM
describe `python-embed/`, que no viaja en el repositorio; el manifiesto declara
pesos `.pt` que tampoco. Con `--permitir-runtime-ausente` y
`--permitir-pesos-ausentes` los gates lo **dicen** en vez de imprimir
«verificado» sin haber verificado —que es exactamente la enfermedad que tenía
el detector de licencias— y CI pasa las banderas de forma visible en
`ci.yml`. Se cierra cuando exista un job que descargue runtime y pesos desde
los repositorios de Hugging Face del doc. 78.

Los conteos de esta tabla envejecen. El del backend lo mantiene
`scripts/report_test_counts.py` en `docs/api/test-counts.json`: esa es la
fuente.
