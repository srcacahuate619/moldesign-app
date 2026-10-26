# MolDesign — avisos de software y modelos de terceros

Versión del aviso: 1.0.2 (11 de octubre de 2026). El 11 de octubre se añaden las bibliotecas con copyleft del runtime que este índice no nombraba (MDAnalysis, GridDataFormats, paramiko, gemmi, certifi, tqdm y cinco crates de Rust bajo MPL-2.0), `vina_trace`, PoseBusters, Dimorphite-DL y el código con el que se ejecuta ESMFold; se corrigen versiones de la interfaz y se retiran integraciones que 1.0.2 ya no ofrece. Cambio respecto a 1.0.1: se añade el motor Molcy, un programa propio de MolDesign publicado bajo GPL-3.0-or-later que viaja en el instalador y se ejecuta dentro de Blender, y se describen Blender y Molecular Nodes, que el usuario descarga a petición y que MolDesign no distribuye. Cambio de 1.0.1 respecto a 1.0.0: se corrigió el identificador de licencia de Open Babel, que declaraba una variante «o posterior» que sus autores no concedieron, y se describe como programa independiente invocado por línea de órdenes, con su procedencia y su oferta de código fuente. El identificador correcto es `GPL-2.0-only`.

MolDesign combina código propio con software libre, componentes científicos, datos públicos y modelos descargables. MolDesign no reclama autoría ni propiedad sobre esos componentes. Cada uno conserva sus avisos, autores y licencia original.

Este documento es el índice humano de los avisos. El inventario completo de versiones del runtime se conserva en `docs/api/sbom.json`; los textos íntegros relevantes se instalan en `licenses/` y los metadatos de los paquetes Python permanecen en `python/Lib/site-packages/*dist-info`.

## Código de MolDesign

El código y los artefactos propios identificados de MolDesign se distribuyen para uso no comercial bajo PolyForm Noncommercial 1.0.0. Cualquier uso comercial requiere un acuerdo separado. Ninguna licencia de MolDesign alcanza o relicencia componentes y pesos de terceros. **Excepción:** el motor Molcy (`tools/molcy/`), también obra propia, se distribuye bajo GPL-3.0-or-later; ver su sección más abajo.

## La tipografía DarkGarden que ReportLab empaqueta

ReportLab es BSD-3-Clause, pero distribuye dentro de sí la tipografía
**DarkGarden** (Michal Kosmulski, 1999–2004) bajo **GPL-2.0-or-later con
excepción de fuente**: incrustarla en un documento no somete ese documento a la
GPL. MolDesign **no usa esta tipografía** —no se referencia en ningún punto del
código—, pero la redistribuye por venir dentro del paquete, y eso basta para que
haya que nombrarla.

El cumplimiento está satisfecho dentro del propio paquete: viajan tanto el texto
íntegro de la licencia (`reportlab/fonts/DarkGarden-copying.txt` y
`DarkGarden-copying-gpl.txt`) como el **código fuente de la fuente**
(`DarkGarden.sfd`, el formato de FontForge), de modo que no hace falta oferta
escrita separada.

> **Cómo apareció esto.** No lo vio ninguna persona: lo encontró
> `scripts/check_copyleft_en_runtime.py` la primera vez que se ejecutó. Esa
> puerta existe porque el runtime llevaba `padelpy`, cuya metadata declara MIT
> mientras empaqueta `PaDEL-Descriptor.jar` bajo **AGPL-3.0**. El SBOM lo daba
> por MIT, este documento no lo inventariaba y ningún módulo lo importaba: se
> retiró del runtime el 2026-09-12 en lugar de declararlo, porque 22,5 MB de
> obligación AGPL a cambio de nada no se justifican. La lección es que la
> licencia de un paquete no es la que dice su metadata, sino la de todo lo que
> ese paquete mete dentro.

## Datos de entrenamiento de los artefactos propios

Los modelos ligeros propios (regresor XGBoost, clasificador de pose, CL-GNN) fueron entrenados, en parte, con el **refined set de PDBbind v2020** (Wang et al., J. Med. Chem. 2005), una recopilación curada de complejos proteína–ligando y afinidades de unión medida por sus autores.

- MolDesign **no** redistribuye el dataset PDBbind, sus estructuras de complejos ni sus tablas de afinidades.
- Lo que se distribuye se limita a (a) **pesos de los modelos** y (b) **código de autoría de MolDesign**, bajo PolyForm Noncommercial 1.0.0.
- Los pesos son representaciones entrenadas: MolDesign reclama autoría sobre los pesos y el código que escribió, pero **no reclama derechos sobre el dataset PDBbind ni concede sublicencia alguna** sobre él.
- PDBbind se cita únicamente con fines de atribución científica; no implica respaldo ni afiliación de sus autores.
- Los artefactos que reproducen afinidades derivadas de PDBbind (`benchmark_pdbbind*.json`, `pocket_dataset*.json`, `pdbbind_audit_report.json`) se **excluyen del canal de distribución**: el empaquetado MSIX los retira del layout (ver `scripts/build_msix.py`).

## Componentes incluidos que requieren atención

| Componente | Versión | Función | Licencia / estado | Fuente |
|---|---:|---|---|---|
| AutoDock Vina | 1.2.7 | Docking | Apache-2.0 | https://github.com/ccsb-scripps/AutoDock-Vina |
| `vina_trace` | Vina 1.2.7 modificado | Copia de Vina que registra la búsqueda para la escena «Búsqueda» de Molcy; viaja en `tools/vina/vina_trace.exe` | Apache-2.0; los archivos modificados y el motivo están en `third_party/vina_trace/NOTICE.md` | `third_party/vina_trace/` (commit de origen `8eb40404`) |
| ReportLab | 4.2.0 | Generación de PDF (dossier y certificados) | BSD-3-Clause. **Empaqueta la tipografía DarkGarden bajo GPL-2.0-or-later con excepción de fuente** — ver abajo | https://www.reportlab.com/ |
| Meeko | 0.7.1 | Preparación AutoDock | LGPL-2.1-or-later según distribución upstream | https://github.com/forlilab/Meeko |
| MDAnalysis | 2.10.0 | Lectura de estructuras para el análisis de interacciones (ProLIF) | **LGPL-3.0-or-later** (su `LICENSE`; partes bajo LGPL-2.1-or-later) | https://github.com/MDAnalysis/mdanalysis |
| GridDataFormats | 1.2.0 | Dependencia de MDAnalysis | **LGPL-3.0-or-later** | https://github.com/MDAnalysis/GridDataFormats |
| paramiko | 5.0.0 | Dependencia transitiva de `fsspec`; ningún módulo de MolDesign la importa | **LGPL-2.1** | https://github.com/paramiko/paramiko |
| gemmi | 0.7.5 | Lectura de mmCIF/PDBx de los receptores propios | **MPL-2.0** (copyleft por archivo) | https://github.com/project-gemmi/gemmi |
| certifi | 2026.6.17 | Certificados raíz para las conexiones HTTPS | **MPL-2.0** | https://github.com/certifi/python-certifi |
| tqdm | 4.68.4 | Barras de progreso de dependencias | **MPL-2.0 AND MIT** | https://github.com/tqdm/tqdm |
| PoseBusters | 0.6.5 | Validez física de las poses | BSD-3-Clause | https://github.com/maabuu/posebusters |
| Dimorphite-DL | 2.0.2 | Protonación del ligando al pH elegido | Apache-2.0 | https://github.com/durrantlab/dimorphite_dl |
| Open Babel | 3.1.1.23 | Conversión estructural de respaldo, ejecutada como **programa independiente** | **GPL-2.0-only** (versión 2, sin «o posterior») | https://github.com/openbabel/openbabel |
| Molcy (motor de vídeo) | commit en `tools/molcy/molcy-manifest.json` | Dibuja los vídeos; se ejecuta dentro de Blender como **programa independiente** | **GPL-3.0-or-later** (obra propia de MolDesign) | `tools/molcy/`; código fuente en https://github.com/srcacahuate619/moldesign-molcy |
| Blender | 5.2.2 | Lo descarga el usuario a petición (no viaja en el instalador); ejecuta el motor Molcy | GPL-3.0-or-later (© Blender Foundation) | https://download.blender.org/release/Blender5.2/ |
| Molecular Nodes | instalada por Blender | La instala el usuario a petición desde Blender Extensions (no viaja en el instalador) | GPL-3.0-or-later (© 2022 Brady Johnston) | https://extensions.blender.org/add-ons/molecularnodes/ |
| Microsoft Visual C++ Runtime | 14.50.35719, x64 | Runtime app-local de los binarios nativos | Términos de redistribución de Microsoft Visual Studio; no cubierto por la licencia de MolDesign | https://aka.ms/vs/18/release/14.50.35719/VC_redist.x64.exe |
| xTB | 6.7.1 | Cálculo semiempírico como proceso separado | LGPL-3.0-or-later | https://github.com/grimme-lab/xtb |
| llama.cpp | build b10199, commit b4ca032ae | Inferencia GGUF local | MIT | https://github.com/ggml-org/llama.cpp |
| rpc-websockets | 9.3.9 | Dependencia transitiva de Solana Web3.js | LGPL-3.0-only | https://github.com/elpheria/rpc-websockets |
| TabPFN | 8.0.8 | Predicción tabular | Prior Labs License 1.2; exige atribución de producto | https://github.com/PriorLabs/TabPFN |
| ADMET-AI | 2.0.1 | Predicción ADMET | MIT | https://github.com/swansonk14/admet_ai |
| RTMScore | snapshot integrado | Rescoring GNN proteína–ligando | MIT; Copyright (c) 2023 sc8668 | https://github.com/sc8668/RTMScore |
| RDKit | 2025.9.6 | Quimioinformática | BSD-3-Clause | https://github.com/rdkit/rdkit |
| Tauri | 2.11.5 | Aplicación de escritorio | Apache-2.0 OR MIT | https://github.com/tauri-apps/tauri |
| Next.js / React | 16.3.8 / 19.2.8 | Interfaz | MIT | https://github.com/vercel/next.js |

Cinco crates de Rust que se compilan dentro del ejecutable de la aplicación declaran **MPL-2.0** (copyleft por archivo): `cssparser` 0.36.0, `cssparser-macros` 0.6.1, `dtoa-short` 0.3.5, `option-ext` 0.2.0 y `selectors` 0.36.1. MolDesign no modifica sus archivos; su código fuente está en crates.io.
### Interfaz y visualización

Estos paquetes forman parte del frontend distribuido. Sus avisos íntegros se
conservan en sus metadatos de instalación y no se sustituyen por esta tabla.

| Componente | Versión | Función | Licencia | Fuente |
|---|---:|---|---|---|
| Ketcher React / Standalone | 3.18.0 | Editor químico | Apache-2.0 | http://lifescience.opensource.epam.com/ketcher |
| Mol* | 5.9.0 | Visualización estructural | MIT | https://github.com/molstar/molstar |
| 3Dmol.js | 2.5.4 | Visualización molecular | BSD-3-Clause | http://3dmol.org |
| Three.js | 0.185.0 | Renderizado 3D | MIT | https://threejs.org/ |
| React Three Fiber / Drei | 9.7.0 / 10.7.8 | Escena 3D React | MIT | https://github.com/pmndrs/react-three-fiber |
| Framer Motion | 13.2.0 | Transiciones de interfaz | MIT | https://motion.dev/ |
| Lucide React | 0.474.0 | Iconos | ISC | https://lucide.dev/ |
| react-virtuoso | 4.18.11 | Listas virtualizadas | MIT | https://virtuoso.dev/ |
| Solana Web3.js | 1.98.4 | POC opcional en devnet; firma cliente | MIT | https://solana.com/ |
| Tailwind CSS | 4.2.2 | Estilos | MIT | https://tailwindcss.com/ |

Full license texts for these bundles ship with the static export in
`./3DMOL_LICENSE.txt` and `./MOLSTAR_LICENSE.txt`; the Webpack notice remains at `../3Dmol-min.js.LICENSE.txt`.

**Built with PriorLabs-TabPFN.** MolDesign configura TabPFN para no abrir autenticación web ni enviar telemetría desde la aplicación de escritorio.

## MolTalk — método adaptado, MIT

La elevación 2D → 3D de MolDesign (la miniatura de Moldex que gira la pose
top-1 de su corrida y la vista 3D alternativa al editor Ketcher) se inspiró en
el visor de **MolTalk**, de Dominic Fico (https://github.com/DomFico/moltalk,
versión 1.0.0, commit `44da199`, leído el 24 de octubre de 2026). Queremos
decirlo con exactitud, porque la idea es suya:

- **Lo que adaptamos.** Su método para alinear una geometría 3D con el dibujo
  2D de la misma molécula: una rotación propia por mínimos cuadrados ponderados
  (sin reflexión, para conservar R/S), con más peso en los estereocentros y sus
  vecinos y repesado robusto para las cadenas flexibles. Y la idea de mover cada
  átomo desde su posición en el dibujo hasta su posición en 3D. MolDesign los
  reimplementa en su propio código (`backend/chem/elevacion.py` y
  `frontend/lib/elevacion.ts`).
- **Lo que no tomamos.** Ni su visor, ni su servidor, ni su generador de GIF,
  ni su elección de conformador, ni sus dependencias. MolDesign no distribuye
  código de MolTalk.

Como el método de alineación sigue de cerca su función `_fit`, conservamos su
aviso de licencia:

```text
MIT License

Copyright (c) 2026 Dominic Fico

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Open Babel — programa independiente, GPL-2.0-only

MolDesign distribuye **Open Babel 3.1.1.23** dentro del mismo instalador y lo
ejecuta como un **programa independiente**: lo invoca por subproceso
(`tools/openbabel/bin/obabel.exe`) y se comunica con él mediante archivos
moleculares. **MolDesign no enlaza con Open Babel ni importa sus bindings de
Python**; los bindings se excluyen del entorno Python distribuido y una guarda
del build (`scripts/check_openbabel_boundary.py`) bloquea la publicación si
reaparecen. Viajar en el mismo medio de distribución es agregación, no
combinación en una sola obra.

**Copyright.** Open Babel © The Open Babel Development Team y colaboradores. El
empaquetado del wheel es de Jinzhe Zeng. MolDesign no reclama autoría alguna
sobre este programa.

**Licencia.** GNU General Public License, **versión 2** (junio de 1991), *sin* la
cláusula «o cualquier versión posterior». El texto íntegro se instala en
`licenses/OpenBabel-GPL-2.0.txt` y junto al propio programa en
`tools/openbabel/LICENSE-GPL-2.0.txt`.

**Ausencia de garantía.** Open Babel se distribuye **SIN NINGUNA GARANTÍA**, ni
siquiera la garantía implícita de comerciabilidad o idoneidad para un propósito
determinado. Véanse las secciones 11 y 12 de la GPLv2.

### Procedencia exacta de los bytes distribuidos

| | |
|---|---|
| Paquete de origen | `openbabel-wheel==3.1.1.23` |
| Archivo | `openbabel_wheel-3.1.1.23-cp311-cp311-win_amd64.whl` |
| SHA-256 del wheel | `f0568906e6959fc541518c8e4cea26973e58707bd2434fb7cddfc5f745c32df7` |
| Plataforma | CPython 3.11, Windows x86-64 |
| Repositorio del empaquetador | https://github.com/njzjz/openbabel-wheel |
| Commit del empaquetador | `c6b2731dbd0a559ee56b8084b6d9997df1beb16f` |
| Fuentes Open Babel incorporadas | https://github.com/njzjz/openbabel |
| Commit de las fuentes | `77993b9a3b96fb9bd86249098beb97ab0fcbafc6` |
| Basado en Open Babel oficial | 3.1.1 — https://github.com/openbabel/openbabel |

El ejecutable contesta `Open Babel 3.1.0` a `obabel -V`: la publicación 3.1.1 de
Open Babel corrigió el empaquetado y no actualizó la cadena de versión interna.
La discrepancia viene de origen y está declarada; no es un error de este paquete.

El hash SHA-256 de cada archivo distribuido está en
`tools/openbabel/openbabel-manifest.json`, y el del ejecutable también en
`runtime-manifest.json`. MolDesign comprueba ese hash **antes** de ejecutar el
programa y se abstiene si no coincide.

### Código fuente correspondiente

La GPLv2 §3 exige acompañar el binario del código fuente correspondiente o de
una oferta escrita válida. **Cada publicación de MolDesign adjunta el archivo de
fuentes de la versión exacta distribuida**; un enlace a una web no basta por sí
solo. Las instrucciones para obtenerlo o reconstruirlo están en
`tools/openbabel/README-PROCEDENCIA.md` y en
[`SOURCE_CODE_AND_RELINKING.md`](SOURCE_CODE_AND_RELINKING.md).

No se aplica ninguna medida técnica que impida sustituir este programa por otra
compilación compatible.

> Esta sección describe la ingeniería y la procedencia verificadas. **No es
> asesoría jurídica**; una revisión legal externa sigue siendo recomendable
> antes de vender licencias comerciales.

## Molcy — programa independiente propio, GPL-3.0-or-later

MolDesign distribuye en el instalador el **motor Molcy** (`tools/molcy/`): los scripts que, ejecutados dentro de Blender, dibujan los
vídeos de Molcy. Es obra propia de MolDesign y se publica bajo **GNU General Public License v3.0 o posterior**, porque se ejecuta dentro
de Blender, usa su API de Python (`bpy`) y la extensión Molecular Nodes, ambos GPL-3.0-or-later. El texto íntegro está en
`tools/molcy/LICENSE`, y las razones y la procedencia en `tools/molcy/NOTICE.md` y `tools/molcy/molcy-manifest.json`.

MolDesign lo ejecuta como **programa independiente**: por subproceso (`powershell` → `blender -b --python maestro.py`), con rutas absolutas, y se
comunican por ficheros (`scene.json`, la geometría, el acta y el MP4). **MolDesign no importa ningún módulo del motor ni el motor importa
MolDesign.** Antes de ejecutarlo, el backend comprueba el SHA-256 de cada fichero contra el manifiesto y se abstiene si no coincide.

**Código fuente.** El código fuente completo y correspondiente del motor está en https://github.com/srcacahuate619/moldesign-molcy; el
`molcy-manifest.json` de cada instalador nombra el commit exacto (`fuente.commit`) del que sale la copia incluida. Quien reciba el motor lo
recibe con derecho a usarlo, modificarlo y redistribuirlo, también con fines comerciales, bajo la GPL-3.0-or-later.

**Cierre y vídeos.** El motor añade el cierre de MolDesign al final de todo vídeo que genera. Es una decisión de diseño del producto y no una
condición de la licencia: la GPL permite modificar el motor, también esa parte. Los vídeos que genera el usuario son suyos: la GPL sólo cubre
el resultado de ejecutar un programa si ese resultado es en sí una obra derivada del programa (GPLv3, sección 2), y Blender no restringe el
uso comercial de lo que se crea con él. El nombre y el emblema del cierre siguen siendo marca de MolDesign.

**Blender y Molecular Nodes no se distribuyen con MolDesign.** El usuario los descarga, a petición, de sus fuentes oficiales (Blender Foundation
y Blender Extensions); Blender se instala en la carpeta de datos del usuario y verifica el SHA-256 publicado por la Fundación.

**Marca.** Las licencias GPL conceden derechos sobre el código y los ficheros, no sobre el nombre ni el emblema de MolDesign
(`moldesign/assets/marca/`, que el motor usa en el cierre de los vídeos): una versión modificada debe quitarlos o sustituirlos.

**Ausencia de garantía.** El motor se distribuye **SIN NINGUNA GARANTÍA**; véanse las secciones 15 y 16 de la GPLv3.

> Esta sección describe la ingeniería y la procedencia verificadas. **No es asesoría jurídica**; una revisión legal externa sigue siendo
> recomendable antes de vender licencias comerciales.

## Modelos descargables bajo demanda

Los archivos pesados no se consideran automáticamente modelos propios de MolDesign. El launcher muestra origen, tamaño, SHA-256 y licencia antes de instalarlos.

| Módulo | Origen de descarga | Licencia | Integridad |
|---|---|---|---|
| Qwen2.5-1.5B-Instruct GGUF Q4_K_M | https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | Apache-2.0 | SHA-256 fijado en el manifiesto |
| ESMFold v1 weights | artefacto alojado en el repositorio de modelos de MolDesign; procedencia Meta ESMFold | MIT | SHA-256 fijado en el manifiesto |

ESMFold se ejecuta con el código de Hugging Face Transformers 4.52.0 (Apache-2.0) y PyTorch 2.13.0 (licencia de estilo BSD), que viajan en el runtime; sólo los pesos se descargan.

El alojamiento o espejo de un archivo de tercero no cambia su licencia ni su autoría.

## Catálogo de receptores — datos de RCSB PDB y UniProtKB

El instalador distribuye **380 receptores curados**: 380 identificadores PDB únicos en `curated_targets.json` y un archivo `.pdb.gz` por cada uno.

### Estructuras — RCSB PDB / wwPDB, CC0 1.0

Los 380 archivos proceden **directamente de RCSB PDB**. De ellos, 376 coinciden byte a byte con la descarga actual de RCSB; los cuatro restantes —`2NNJ`, `4EJJ`, `4NY4` y `5TFT`— difieren únicamente en una línea `REVDAT` posterior, y sus registros `ATOM`, `HETATM` y `CONECT` son idénticos.

Además, `data/targets/` trae **65 estructuras fuera del catálogo** —el panel de anti-dianas de Bowes 2012, controles y corridas doradas—, también de RCSB PDB: 59 coinciden byte a byte con su descarga actual y 6 (`8XVK`, `8YUT`, `8ZP2`, `9EQG`, `9GJ1`, `9UWL`), que RCSB sólo ofrece en mmCIF, se convirtieron a PDB con gemmi (medido el 2026-09-28; ver `docs/91_AUDITORIA_PROCEDENCIA_CATALOGO_RECEPTORES.md`).

Los datos del archivo PDB y de las APIs de RCSB se publican bajo **CC0 1.0** (dominio público).

**CC0 no exige atribución**, y este aviso no la reclama como obligación legal. Lo que sí procede, y RCSB lo recomienda, es la **cita científica** de la entrada PDB concreta y de sus autores originales en cualquier trabajo que se apoye en ella.

- Política de uso: https://www.rcsb.org/pages/usage-policy
- Políticas: https://www.rcsb.org/pages/policies
- CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/

### Descripciones funcionales — UniProtKB, CC BY 4.0

Las descripciones funcionales de los receptores se tomaron del comentario **FUNCTION** de UniProtKB y se tradujeron al español. UniProt aplica **CC BY 4.0** a las partes protegibles de sus bases de datos, y esa licencia **sí requiere atribución**:

> Fuente: UniProtKB; traducción/adaptación al español: MolDesign.

- Licencia de UniProt: https://www.uniprot.org/help/license/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

### Qué es curación de MolDesign y qué no

La caja de docking, los *hotspots*, la selección de cadena, la familia estructural y el estado **son curación y cálculo de MolDesign**, no afirmaciones de RCSB ni de UniProt.

**Ni RCSB ni UniProt certifican, avalan ni revisan los resultados de MolDesign.** Aportan, respectivamente, las estructuras y las descripciones de partida; todo lo que MolDesign deriva de ellas es responsabilidad de MolDesign.

Estos receptores **no** son las estructuras preparadas de PDBbind: son descargas de RCSB curadas por MolDesign.

## Integraciones no incluidas

DiffDock, ColabFold, RFdiffusion y ESMFold Pro **no se ofrecen en 1.0.2**: el backend los declara con el motivo por el que esta instalación no los ejecuta y el menú de motores sólo lista Vina y ESMFold. Ni sus runtimes ni sus pesos viajan en el instalador. La transcripción de voz de MolChat (faster-whisper) tampoco viaja en el runtime. Anthropic es una integración opcional. Solana se limita a un POC explícito en devnet, sin validez oficial; transmite únicamente el memo mínimo mostrado antes de firmar.

## RTMScore

El snapshot integrado de RTMScore se distribuye bajo MIT y conserva el texto upstream íntegro en `rescoring/RTMScore/LICENSE`: Copyright (c) 2023 sc8668. Fuente: https://github.com/sc8668/RTMScore/blob/main/LICENSE. La licencia permite uso y redistribución comercial con conservación del aviso de copyright y permiso.


## RDKit: componentes observados dentro de la distribución 2025.9.6

Inspección local del Python embebido 3.11.9, 2026-10-04; sin descargar fuentes ni consultar sitios.
La metadata declara BSD-3-Clause para RDKit, pero `rdkit-2025.9.6.dist-info/LICENSE.md` es
la licencia **MIT de las herramientas de ruedas**, Copyright (c) 2022 Christopher Kuenneth;
no sustituye `rdkit/license.txt`, BSD-3-Clause, © 2006–2015 Rational Discovery LLC,
Greg Landrum, Julie Penzotti y otros. Orígenes declarados en METADATA:
https://github.com/rdkit/rdkit y https://github.com/kuelumbus/rdkit-pypi.

| Componente / archivo observado | Licencia y evidencia | Origen comprobable |
|---|---|---|
| FreeSASA: `rdkit/Chem/rdFreeSASA.pyd` (68096 bytes), `RDKitFreeSASALib-*.dll`, `RDKitfreesasa_clib-*.dll` | **MIT**, la licencia que declara el proyecto FreeSASA; versión, copyright y texto íntegro específicos **no verificados** en esta rueda. No aparecen en sus dos licencias generales. No se presenta ese vacío como cumplimiento completo. | Rueda RDKit citada arriba; fuente exacta del componente no verificada localmente |
| Boost: iostreams, numpy311, python311, serialization; RDKitRDBoost | DLL presentes; licencia/versión exactas **no verificadas** en los textos disponibles | Rueda RDKit; no se presume que BSD de RDKit las cubra |
| Avalon, InChI, coordgen, maeparser, EigenSolvers | DLL con esos nombres presentes; fuentes/versiones/licencias del código integrado **no verificadas** | Rueda RDKit; EigenSolvers no demuestra por sí solo la versión de Eigen |
| Telex-Regular.ttf | SIL OFL-1.1; texto íntegro `Data/Fonts/telex_font_license.txt`, © 2011 The Telex Project Authors | Archivo y aviso incluidos en RDKit |
| ComicNeue-Regular.ttf | SIL OFL-1.1; `Data/Fonts/OFL.txt`, © 2014 The Comic Neue Project Authors | Aviso cita https://github.com/crozynski/comicneue |
| Roboto | Apache-2.0 declarada por `roboto_regular_license.txt`; no se observó Roboto-Regular.ttf en esta carpeta | El aviso lo atribuye a Google; procedencia del binario no verificada |
| Amadeus.ttf | El aviso dice que se encontró sin licencia; **licencia y permiso de redistribución no verificados** | `Data/Fonts/amadeus_font_license.txt`; la opinión del distribuidor no sustituye una licencia |

### Contrib: los 20 directorios incluidos

La evidencia siguiente sólo alcanza los archivos con texto o cabecera de licencia observados;
no extiende esos avisos a todo el directorio, sus datos o sus dependencias. Todo procede de la rueda citada.
Se conservan los avisos originales en sus archivos; SA_Score y NP_Score incluyen BSD-3-Clause de Novartis
(2013 y 2015 respectivamente), y build_sascore_db.py declara © 2023 Glysade LLC.

| Directorio | Archivos Python | Licencia observada / límite |
|---|---:|---|
| AtomAtomSimilarity | 1 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| CalcLigRMSD | 1 | BSD declarada, variante no verificada (`CalcLigRMSD.py`); restantes no verificados |
| ChiralPairs | 1 | BSD-3-Clause, texto en archivo (`ChiralDescriptors.py`); restantes no verificados |
| ConformerParser | 1 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| efgs | 2 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| Fastcluster | 2 | BSD declarada, variante no verificada (`fastcluster.py`); restantes no verificados |
| fraggle | 4 | BSD-3-Clause, texto en archivo (`atomcontrib.py`, `cxn_tversky.py`, `fraggle.py`, `rdkit_tversky.py`); restantes no verificados |
| FreeWilson | 2 | BSD declarada, variante no verificada (`freewilson.py`); restantes no verificados |
| Glare | 1 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| IFG | 1 | BSD declarada, variante no verificada (`ifg.py`); restantes no verificados |
| LEF | 5 | BSD-3-Clause, texto en archivo (`AddLabels.py`, `ClusterFps.py`, `CreateFps.py`, `DistancePlot.py`, `DistancePredict.py`); restantes no verificados |
| M_Kossner | 1 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| mmpa | 7 | BSD-3-Clause, texto en archivo (`cansmirk.py`, `create_mmp_db.py`, `indexing.py`, `mol_transform.py`, `rfrag.py`, `search_mmp_db.py`); restantes no verificados |
| MolVS | 1 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| NIBRSubstructureFilters | 1 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| NP_Score | 1 | BSD-3-Clause, texto en archivo (`npscorer.py`); restantes no verificados |
| PBF | 1 | BSD declarada, variante no verificada (`pbf.py`); restantes no verificados |
| pzc | 1 | no verificado: no se encontró texto suficiente en los archivos Python revisados |
| RxnRoleAssignment | 3 | BSD-3-Clause, texto en archivo (`identifyReactants.py`, `utils.py`); restantes no verificados |
| SA_Score | 3 | BSD-3-Clause, texto en archivo (`build_sascore_db.py`, `sascorer.py`); restantes no verificados |

Se observaron 92 DLL en rdkit.libs. Sus nombres y presencia no bastan para acreditar todas sus
licencias transitivas o las condiciones de sus datos. La inspección se limita a esta rueda instalada,
no al instalador final. El SBOM de paquetes no inventaría automáticamente cada subcomponente.
Antes de distribuir, revisar los textos faltantes de FreeSASA y las fuentes, conservando los avisos
upstream; este documento declara la evidencia disponible y los puntos pendientes.

## Sin sustitución de avisos

Las citas científicas reconocen métodos y autores, pero no sustituyen las licencias de software. Este índice tampoco sustituye los textos de licencia íntegros incluidos con el producto.