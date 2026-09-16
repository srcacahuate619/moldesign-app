# MolDesign — avisos de software y modelos de terceros

Versión del aviso: 1.0.1 (5 de septiembre de 2026). Cambio respecto a 1.0.0: se corrigió el identificador de licencia de Open Babel, que declaraba una variante «o posterior» que sus autores no concedieron, y se describe como programa independiente invocado por línea de órdenes, con su procedencia y su oferta de código fuente. El identificador correcto es `GPL-2.0-only`.

MolDesign combina código propio con software libre, componentes científicos, datos públicos y modelos descargables. MolDesign no reclama autoría ni propiedad sobre esos componentes. Cada uno conserva sus avisos, autores y licencia original.

Este documento es el índice humano de los avisos. El inventario completo de versiones del runtime se conserva en `docs/api/sbom.json`; los textos íntegros relevantes se instalan en `licenses/` y los metadatos de los paquetes Python permanecen en `python/Lib/site-packages/*dist-info`.

## Código de MolDesign

El código y los artefactos propios identificados de MolDesign se distribuyen para uso no comercial bajo PolyForm Noncommercial 1.0.0. Cualquier uso comercial requiere un acuerdo separado. Ninguna licencia de MolDesign alcanza o relicencia componentes y pesos de terceros.

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
| ReportLab | 4.2.0 | Generación de PDF (dossier y certificados) | BSD-3-Clause. **Empaqueta la tipografía DarkGarden bajo GPL-2.0-or-later con excepción de fuente** — ver abajo | https://www.reportlab.com/ |
| Meeko | 0.7.1 | Preparación AutoDock | LGPL-2.1-or-later según distribución upstream | https://github.com/forlilab/Meeko |
| Open Babel | 3.1.1.23 | Conversión estructural de respaldo, ejecutada como **programa independiente** | **GPL-2.0-only** (versión 2, sin «o posterior») | https://github.com/openbabel/openbabel |
| Microsoft Visual C++ Runtime | 14.50.35719, x64 | Runtime app-local de los binarios nativos | Términos de redistribución de Microsoft Visual Studio; no cubierto por la licencia de MolDesign | https://aka.ms/vs/18/release/14.50.35719/VC_redist.x64.exe |
| xTB | 6.7.1 | Cálculo semiempírico como proceso separado | LGPL-3.0-or-later | https://github.com/grimme-lab/xtb |
| llama.cpp | build b10199, commit b4ca032ae | Inferencia GGUF local | MIT | https://github.com/ggml-org/llama.cpp |
| rpc-websockets | 9.3.9 | Dependencia transitiva de Solana Web3.js | LGPL-3.0-only | https://github.com/elpheria/rpc-websockets |
| TabPFN | 8.0.8 | Predicción tabular | Prior Labs License 1.2; exige atribución de producto | https://github.com/PriorLabs/TabPFN |
| ADMET-AI | 2.0.1 | Predicción ADMET | MIT | https://github.com/swansonk14/admet_ai |
| RTMScore | snapshot integrado | Rescoring GNN proteína–ligando | MIT; Copyright (c) 2023 sc8668 | https://github.com/sc8668/RTMScore |
| RDKit | 2025.9.6 | Quimioinformática | BSD-3-Clause | https://github.com/rdkit/rdkit |
| Tauri | 2.11.3 | Aplicación de escritorio | Apache-2.0 OR MIT | https://github.com/tauri-apps/tauri |
| Next.js / React | 16.3.4 / 19.2.8 | Interfaz | MIT | https://github.com/vercel/next.js |
### Interfaz y visualización

Estos paquetes forman parte del frontend distribuido. Sus avisos íntegros se
conservan en sus metadatos de instalación y no se sustituyen por esta tabla.

| Componente | Versión | Función | Licencia | Fuente |
|---|---:|---|---|---|
| Ketcher React / Standalone | 3.12.0 | Editor químico | Apache-2.0 | http://lifescience.opensource.epam.com/ketcher |
| Mol* | 5.9.0 | Visualización estructural | MIT | https://github.com/molstar/molstar |
| 3Dmol.js | 2.5.4 | Visualización molecular | BSD-3-Clause | http://3dmol.org |
| Three.js | 0.185.0 | Renderizado 3D | MIT | https://threejs.org/ |
| React Three Fiber / Drei | 8.18.0 / 9.122.0 | Escena 3D React | MIT | https://github.com/pmndrs/react-three-fiber |
| Framer Motion | 11.18.2 | Transiciones de interfaz | MIT | https://motion.dev/ |
| Lucide React | 0.474.0 | Iconos | ISC | https://lucide.dev/ |
| react-virtuoso | 4.18.11 | Listas virtualizadas | MIT | https://virtuoso.dev/ |
| Solana Web3.js | 1.98.4 | POC opcional en devnet; firma cliente | MIT | https://solana.com/ |
| Tailwind CSS | 4.2.2 | Estilos | MIT | https://tailwindcss.com/ |

Full license texts for these bundles ship with the static export in
`./3DMOL_LICENSE.txt` and `./MOLSTAR_LICENSE.txt`; the Webpack notice remains at `../3Dmol-min.js.LICENSE.txt`.

**Built with PriorLabs-TabPFN.** MolDesign configura TabPFN para no abrir autenticación web ni enviar telemetría desde la aplicación de escritorio.

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

## Modelos descargables bajo demanda

Los archivos pesados no se consideran automáticamente modelos propios de MolDesign. El launcher muestra origen, tamaño, SHA-256 y licencia antes de instalarlos.

| Módulo | Origen de descarga | Licencia | Integridad |
|---|---|---|---|
| Qwen2.5-1.5B-Instruct GGUF Q4_K_M | https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | Apache-2.0 | SHA-256 fijado en el manifiesto |
| ESMFold v1 weights | artefacto alojado en el repositorio de modelos de MolDesign; procedencia Meta ESMFold | MIT | SHA-256 fijado en el manifiesto |

El alojamiento o espejo de un archivo de tercero no cambia su licencia ni su autoría.

## Catálogo de receptores — datos de RCSB PDB y UniProtKB

El instalador distribuye **380 receptores curados**: 380 identificadores PDB únicos en `curated_targets.json` y un archivo `.pdb.gz` por cada uno.

### Estructuras — RCSB PDB / wwPDB, CC0 1.0

Los 380 archivos proceden **directamente de RCSB PDB**. De ellos, 376 coinciden byte a byte con la descarga actual de RCSB; los cuatro restantes —`2NNJ`, `4EJJ`, `4NY4` y `5TFT`— difieren únicamente en una línea `REVDAT` posterior, y sus registros `ATOM`, `HETATM` y `CONECT` son idénticos.

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

DiffDock, ColabFold y RFdiffusion/ESMFold-Pro se exponen como adaptadores a servicios configurados por el investigador. Sus runtimes y pesos no están incluidos en el instalador base. Anthropic es una integración opcional. Solana se limita a un POC explícito en devnet, sin validez oficial; transmite únicamente el memo mínimo mostrado antes de firmar.

## RTMScore

El snapshot integrado de RTMScore se distribuye bajo MIT y conserva el texto upstream íntegro en `rescoring/RTMScore/LICENSE`: Copyright (c) 2023 sc8668. Fuente: https://github.com/sc8668/RTMScore/blob/main/LICENSE. La licencia permite uso y redistribución comercial con conservación del aviso de copyright y permiso.

## Sin sustitución de avisos

Las citas científicas reconocen métodos y autores, pero no sustituyen las licencias de software. Este índice tampoco sustituye los textos de licencia íntegros incluidos con el producto.