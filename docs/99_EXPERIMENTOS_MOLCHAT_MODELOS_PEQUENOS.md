# 99 — MolChat: modelos de menos de 1 B parámetros y el enrutado de herramientas

> **Nota de reubicación (2026-10-11).** Los pesos descargados (`descargas/`) se movieron a F: el 2026-10-10. El worktree `molchat-lab` sigue vivo. Índice: [REUBICACIONES_2026-10-11.md](REUBICACIONES_2026-10-11.md).

**Estado:** los experimentos (secciones 1 a 4) son exploración en la rama
`claude/molchat-lab` (worktree `D:\moldesign-worktrees\molchat-lab`, desde
`ff38be1c`) y no cambian la aplicación. Los arreglos de MolChat (secciones 5 y 6)
se integraron en `codex/release-hygiene` en tres commits: `e0fca2dc` (guardián de
SMILES), `e2d05af2` («acoplar») y `4437f282` (comprobación previa). Medido el
2026-10-10.

**Pregunta del propietario:** qué modelos de Hugging Face de menos de 1 B
parámetros podrían mejorar MolChat o el producto, medidos aquí y no leídos en una
ficha; y que MolChat conozca la pestaña Preparación (Molcy queda fuera por ahora,
decisión del propietario). Lo segundo acabó siendo otra cosa, y la sección 5
explica por qué.

## Condiciones

- **Máquina:** la estación del propietario, sólo CPU (la GPU no tiene VRAM libre
  para estos modelos). Los tiempos son de CPU y con otros procesos de la sesión;
  sirven para comparar brazos medidos aquí, no como cifras absolutas.
- **Binarios:** el `llama-server` b10199 que viaja en el instalador
  (`tools/llama/`); whisper.cpp v1.9.4 (build `b5130`, CPU x64); MolScribe en un
  venv aparte (Python 3.11, torch 2.14.1+cpu), nunca en el Python del producto.
- **Arnés de herramientas:** `scripts/bench_tool_calling/` (21 casos, 15 en
  alcance y 6 fuera, diseño 2×2 de idioma de la pregunta y de las descripciones;
  n = 21 por celda, intervalo de unos ±17 puntos). `run_llama.py` envía el mismo
  payload que `local_llm.generate_with_tools` y apaga el pensamiento como el
  producto. Las descripciones «actuales» incluyen la de `run_docking` que
  propone y no lanza (LUNA-05); el 2026-09-20 se midió con la anterior.
- **La condición del producto es pregunta y descripciones en español.** Es la
  columna que decide.

### Procedencia de las descargas

Cada archivo se fijó a un commit y se comprobó contra el SHA-256 que publica la
API de Hugging Face (o el `digest` de GitHub para el ejecutable).

| Repositorio @ commit | Archivo | Bytes | SHA-256 |
|---|---|---:|---|
| `unsloth/Qwen3.5-0.8B-GGUF` @ `6ab461498e` | `Qwen3.5-0.8B-Q4_K_M.gguf` | 532 517 120 | `bd258782e35f7f45…` |
| `ibm-granite/granite-4.0-350m-GGUF` @ `b8208a86a5` | `granite-4.0-350m-Q4_K_M.gguf` | 236 985 760 | `771c588a49607f27…` |
| `Qwen/Qwen3-Embedding-0.6B-GGUF` @ `370f27d755` | `Qwen3-Embedding-0.6B-Q8_0.gguf` | 639 150 592 | `06507c7b42688469…` |
| `cstr/multilingual-e5-small-GGUF` @ `178420da72` | `multilingual-e5-small-q8_0.gguf` | 131 624 960 | `0a34067a40f25d31…` |
| `ggerganov/whisper.cpp` @ `5359861c73` | `ggml-small-q5_1.bin` | 190 085 487 | `ae85e4a935d7a567…` |
| `ggerganov/whisper.cpp` @ `5359861c73` | `ggml-large-v3-turbo-q5_0.bin` | 574 041 195 | `394221709cd5ad1f…` |
| `yujieq/MolScribe` @ `a0189776b7` | `swin_base_char_aux_1m680k.pth` | 1 134 173 494 | `32821fa4ba8d17f9…` |
| `yujieq/MolScribe` @ `a0189776b7` | `real.zip` | 183 667 975 | `c6ebed6c1eec3167…` |
| `ggml-org/whisper.cpp` @ `b5130` | `whisper-bin-x64.zip` | 8 573 270 | `f9ec6c52a2e949b6…` |

Los archivos viven en `D:\moldesign-dev-data\molchat-lab\descargas\` (ahora en F:\Backups\moldesign-evidencia\2026-10-10-limpieza-D\dev-data\molchat-lab) (fuera del
repositorio y fuera de `models/llm`, para que la aplicación no los liste como
modelos de chat); los resultados en `…\molchat-lab\resultados\`.

## 1. Un modelo de chat por defecto más ligero: no

| Modelo (Q4_K_M, sin pensamiento) | ES/ES acierto | En alcance | Abstención | Falsos positivos | Mediana |
|---|---:|---:|---:|---:|---:|
| Qwen2.5-1.5B (el de hoy) | 17/21 | 12/15 | 5/6 | 1 | 2,2 s |
| **Qwen3.5-0.8B** | 12/21 | 6/15 | 6/6 | 0 | 2,2 s |
| **Granite 4.0 350M** | 12/21 | 10/15 | 2/6 | **4** | 1,0 s |
| Qwen3.5-4B (el «Avanzado») | 21/21 | 15/15 | 6/6 | 0 | 6,3 s |

Qwen3.5-0.8B acierta la mitad de las herramientas en alcance y no es más rápido
que Qwen2.5-1.5B en esta CPU. Granite 350M es rápido pero llama a herramientas en
cuatro de seis peticiones que no las piden, que es el peor fallo
(`compute_properties(smiles='Madrid')`). **Ninguno sustituye al actual.** Con las
descripciones actuales, Qwen3.5-4B acierta 84 de 84 en las cuatro celdas.

## 2. Preseleccionar herramientas con embeddings: no como filtro

La idea: pasar al modelo sólo las k herramientas más parecidas a la petición para
acortar el prompt del primer turno.

**Recall de la herramienta correcta** (Qwen3-Embedding-0.6B Q8_0, pooling *last*,
instrucción de consulta de su ficha; 45 consultas en alcance por celda: 15 del
corpus más 30 paráfrasis escritas para la prueba):

| Pregunta / descripciones | @1 | @3 | @5 |
|---|---:|---:|---:|
| es / es | 57,8 % | 73,3 % | **80,0 %** |
| en / es | 60,0 % | 82,2 % | 84,4 % |
| es / en | 55,6 % | 84,4 % | 91,1 % |
| en / en | 66,7 % | 91,1 % | 95,6 % |

Con las descripciones en español, en uno de cada cinco casos la correcta queda
fuera de las cinco primeras. Las que se escapan son las centrales: «acopla … contra
1AJ6» deja `run_docking` en el puesto 16, y también `predict_admet` y
`get_rescoring`. Es el mismo síntoma que la medida de Needle (doc 88): **las
descripciones en español de las herramientas son el punto débil.**

**De punta a punta** con Qwen2.5-1.5B recibiendo sólo esas 5:

| | Acierto ES/ES | Prompt del primer turno | Primer turno en frío (mediana, 5 casos) |
|---|---:|---:|---:|
| Las 21 herramientas | 17/21 | ~2 800 tokens | 31,2 s |
| Las 5 preseleccionadas | 16/21 | ~800 tokens | 6,7 s |

El primer turno baja 4,6 veces y se pierde un acierto. **Alternativa sin pérdida,
no medida todavía:** el prefijo (prompt de sistema más herramientas) es constante,
así que puede precalentarse en la caché de `llama-server` al cargar el modelo; el
primer turno costaría lo que uno con caché (mediana 2,2 s).

`multilingual-e5-small`: la conversión GGUF de `cstr` **no carga** en el b10199
(`bert model needs to define token type count`). Habría que reconvertir el
original; no se hizo porque el modelo más fuerte ya no sirve como filtro.

## 3. Dictado

**El dictado no funciona hoy en la aplicación instalada:** `services/ai/speech_to_text.py`
depende de `faster-whisper`, que no viaja en el runtime, y el modelo previsto es
`tiny`, el peor en español (27,7 % de WER en Common Voice 13 según Whisper-LM,
arXiv 2503.23542, sin ajuste fino).

Medido con whisper.cpp (`whisper-server`, modelo cargado una vez, 8 hilos) sobre
las 20 frases de `scripts/bench_dictado/guion.py`, cada una con un término que
tiene que salir bien escrito (un fármaco, un receptor, un concepto de la app).
**Voz sintética** de Windows (Sabina, es-MX): sin acento, ruido ni titubeos, así
que es una cota optimista. La medida que vale es con voz humana
(`scripts/bench_dictado/grabar.html` graba las 20 en el formato del arnés).

| Modelo | Prompt de vocabulario | Términos clave bien | WER | Latencia por frase (mediana) |
|---|---|---:|---:|---:|
| small q5_1 (190 MB) | no | 15/20 | 5,1 % | 2,2 s |
| small q5_1 | **sí** | **17/20** | 4,4 % | 2,4 s |
| large-v3-turbo q5_0 (574 MB) | no | 14/20 | 5,7 % | 10,4 s |
| large-v3-turbo q5_0 | sí | 17/20 | 2,5 % | 10,7 s |

- **Small con el prompt de vocabulario** acierta los mismos términos clave que
  turbo con un cuarto de la latencia y un tercio del tamaño. El prompt
  (`PROMPT_VOCABULARIO`: nombres de la app, fármacos, «Murcko», «tautómero») es
  gratis y arregla «Murtko» → «Murcko» y «10epam» → «diazepam».
- Fallan en los cuatro brazos «Vina» → «vine» y «paracetamol» (con la voz
  sintética; puede ser la pronunciación de la voz). «haloperidol» sale sin h.
- **Integración posible:** whisper.cpp es un programa aparte (MIT), como
  `llama-server` y Open Babel: no añade dependencias de Python. Hay que convertir
  el audio del navegador (webm/opus) a WAV de 16 kHz antes de enviarlo, porque
  el binario de Windows no trae ffmpeg. La misma build trae `parakeet-cli`, que
  ejecuta Parakeet v3 sin NeMo: candidato para una segunda medida (CC-BY-4.0).

## 4. Figura → SMILES (MolScribe)

La función: pegar la figura de una estructura de un artículo o una patente y que
la aplicación proponga el SMILES para confirmarlo en el editor. MolScribe (MIT,
~88 M parámetros, checkpoint de 1,13 GB), en un venv aparte, sobre las imágenes
reales de su propio benchmark con el SMILES correcto. Acierto exacto = SMILES
canónico igual sin distinguir cis/trans (la métrica `canon_smiles` del artículo,
con su evaluador):

| Conjunto | Imágenes | Exactas | s/imagen (CPU) |
|---|---:|---:|---:|
| **ACS** (figuras de artículos; todas) | 331 | **239 (72,2 %)** | 0,58 |
| CLEF (muestra, semilla 42) | 200 | 176 (88,0 %) | 0,62 |
| USPTO (patentes; muestra, semilla 42) | 200 | 189 (94,5 %) | 0,64 |

El 72,2 % en ACS coincide con lo que publica el artículo (~72 %): en figuras de
artículos, **una de cada cuatro estructuras sale mal**.

**Su confianza sí sirve** (lo que DiffDock no tenía). En ACS:

| Confianza | Imágenes | Exactas |
|---|---:|---:|
| < 0,8 | 29 (9 %) | 21 % |
| 0,8 – 0,9 | 172 (52 %) | 72 % |
| ≥ 0,9 | 130 (39 %) | 88 % |

Sirve para marcar «revisa esta estructura» con fundamento, pero ni la franja alta
permite saltarse la confirmación: la función sólo es honesta como **propuesta
que el investigador confirma en el editor**.

Carga **sin ejecutar código del pickle**: `torch.load` con `weights_only=True`,
permitiendo sólo `argparse.Namespace`. Integrarlo exigiría su código (MIT) y sus
dependencias fijadas (OpenNMT-py 2.2.0, timm 0.4.12, albumentations 1.1.0,
numpy < 2) en el runtime, que es lo más caro de los cuatro.

## 5. MolChat lee la comprobación previa de Evaluación (no la pestaña Preparación)

**Corrección antes de integrar.** La versión del laboratorio (`5b62317a`,
`cc2c773a`) se presentaba como «la pestaña Preparación» y respondía «Según la
pestaña Preparación…». Lo que lee es la **comprobación previa** de Evaluación
(`POST /evaluation/preflight`, el panel «Comprobación previa» que se ve antes de
ejecutar). La pestaña Preparación es otra cosa: audita una corrida ya guardada con
su propio informe (`POST /evaluation/dossier/{id}/preparacion`: tautómero, unión
covalente, membrana, decisiones del investigador). El texto habría mandado al
investigador a buscar el dato donde no está. Integrado en `4437f282` con el nombre
correcto, y la respuesta lo aclara.

- **`check_preparation`** (`services/ai/tools/preparation_tools.py`) devuelve el
  informe REAL de la comprobación previa sin ejecutar docking: qué controles
  bloquean, avisan o no se evaluaron, con su motivo y la huella. Sin ligando pide
  el informe con un ligando de sondeo (fenol) y no devuelve sus controles.
- **El clasificador la enruta** (intención `preparation`: palabras de
  preparación y un PDB en la frase). Va antes de la regla del SMILES explícito.
- **La respuesta la escribe el código** (`respuesta_breve`), no el modelo. La
  primera frase dice si hay bloqueo y desmiente la premisa cuando es falsa. Está
  en castellano también si la pregunta llega en inglés.

**Probado de punta a punta en la cápsula 5**, la primera vez con el laboratorio
y otra vez con la versión integrada (`4437f282`, export de
`codex/release-hygiene` + estos tres commits; datos propios, Qwen2.5-1.5B,
catálogo real):

- «¿por qué está bloqueado el receptor 8HFI?» → `classifier intent=preparation`,
  preflight real (huella `0ab97df4…`, la misma las dos veces): ningún control del
  receptor bloquea, 2 advertencias (especies retiradas, receptor sin calibrar), 4
  sin evaluar. La respuesta: «Según la comprobación previa de Evaluación, 8HFI no
  está bloqueado por el receptor ni por el protocolo…». En un segundo y sin cargar
  el modelo.
- Antes de que la respuesta fuera determinista, con el mismo informe delante,
  Qwen2.5-1.5B escribió «El receptor 8HFI está bloqueado debido a varias
  advertencias»: aceptó la premisa falsa. Eso decidió el cambio.
- «revisa la preparación de CC(=O)Oc1ccccc1C(=O)O contra 1AJ6 antes de lanzar»
  → informe con los controles del ligando (protonación y tautómero sin evaluar
  antes de ejecutar).
- «acopla la aspirina contra 1AJ6» → `intent=docking`, `run_docking` con el
  receptor 1AJ6, propuesta registrada (`docking_propuesto`). La interfaz la
  enseña mal: ver la sección 7.

**En el arnés**, con la herramienta 22 añadida, los 21 casos de siempre no
cambian en la condición del producto (Qwen2.5-1.5B 17/21; Qwen3.5-4B 21/21;
con las preguntas en inglés pierde un caso por celda), y los modelos eligen `check_preparation` en los casos nuevos
(Qwen2.5-1.5B 5/5 en ES/ES; Qwen3.5-4B 20/20 en las cuatro celdas). Condición:
`tools_openai_22.json` lleva la descripción del laboratorio («Lee la pestaña
Preparación…»); la integrada dice «la comprobación previa de Evaluación» y no se
volvió a medir. En el producto esas preguntas no dependen del modelo: las enruta
el clasificador.

## 6. Lo que el enrutado hacía y el arnés no veía

El arnés de herramientas mide qué herramienta elige el modelo **si se le dan las
herramientas**. En el producto, antes del modelo está el clasificador
determinista (`intent_classifier.py`), y de eso el arnés no sabía nada:

1. **El clasificador manda.** Si reconoce la intención, ejecuta él la
   herramienta; si devuelve `conceptual` o `unknown`, `chat_service` **quita las
   herramientas al modelo** («autoritativo en ambos sentidos»). «¿por qué está
   bloqueado 8HFI?» era `conceptual` y las demás preguntas de este tipo
   `unknown`: el modelo nunca habría podido consultar la comprobación previa.
   Los aciertos del arnés describen una franja estrecha del producto, no MolChat
   entero. **Esa regla no se ha cambiado**: es deliberada (evita que el modelo
   llame a herramientas con basura, bug I005). Lo integrado sólo añade la
   intención `preparation` para estas preguntas; cualquier otra pregunta que el
   clasificador no reconozca sigue sin herramientas.
2. **El guardián de SMILES de la ruta nativa** (la del modelo local) exigía
   `smiles` a todas las herramientas. Contado sobre el registro integrado: 13 de
   las 27 herramientas no se ejecutaban nunca por esa ruta (9 de las 21 que el
   modelo ve sin red): 12 que no lo llevan (`query_history`,
   `check_docking_status`, `query_molgraph`, `rank_session_molecules`…) y
   `compare_molecules`, que lo lleva como `smiles_a`/`smiles_b`. Ahora
   `validar_smiles_de_la_llamada` valida y canoniza cada argumento de SMILES y
   exige sólo los obligatorios. La ruta por texto (proveedores en la nube) no
   tenía el defecto. Integrado en `e0fca2dc`.
3. **«acopla X contra 1AJ6» caía en `compute_properties`:** las reglas de
   docking sólo reconocían «afinidad» y «docking», no el verbo «acoplar». Y en
   «la afinidad de la aspirina con 7E2Y» o «docking de CCO en 6LU7» el receptor
   se perdía, porque el extractor exige «contra» o «receptor» delante; ahora un
   PDB suelto sirve de respaldo (un año no). Integrado en `e2d05af2`.

Cada corrección lleva sus pruebas (7 en `test_molchat_guardian_smiles.py`, 7 en
`test_molchat_clasificador_docking.py` y 16 en `test_molchat_comprobacion_previa.py`)
y un control negativo sobre el commit anterior. 224 pruebas de MolChat en verde con
python-embed.

## 7. Defecto previo encontrado en la cápsula: respuestas en blanco

Al repetir la prueba con la versión integrada apareció un defecto que **no viene
de estos cambios**: las preguntas que nombran una molécula conocida salen en
blanco en la interfaz. «calcula las propiedades de la aspirina» y «calcula la
afinidad de la aspirina contra 1AJ6» (la frase de siempre, sin «acoplar») dan un
mensaje de MolChat vacío; la propuesta de docking sólo enseña los botones
«Aprobar y lanzar» y «Cancelar propuesta», sin ligando, receptor, caja ni
advertencias. El backend sí lo envía: la respuesta cruda trae «Propiedades de
aspirina: MW 180.2…» y la propuesta completa.

Causa: cuando el clasificador conoce el nombre, `chat_service` escribe el
resultado como `compute_properties (aspirina): …`, sin la etiqueta
`[clase · fuente]`. `separarEvidencia` (`frontend/components/ai/BloqueDeEvidencia.tsx`)
trata todo lo que sigue a la cabecera `[Sistema: resultados de herramientas
ejecutadas:]` como evidencia, no reconoce esa primera línea y descarta lo demás,
también la respuesta. Existe desde agosto (`493c2a6f`, `af5a60d1`). En la
comprobación previa no se pierde nada porque su resultado lleva la etiqueta, pero
la respuesta breve aparece dentro del bloque de evidencia en vez de como texto.
**Corregido el 2026-10-11** (registro de 1.0.2, fila «MolChat en blanco»): el bloque
con nombre lo escribe `format_tool_results`, con su clase, su fuente y la molécula;
todo bloque que se emite se cierra con `<!--__FIN_DE_EVIDENCIA__-->`, y la interfaz
separa por ese cierre y no descarta ninguna línea. Reproducido antes con el servicio
real: la respuesta determinista llegaba pegada a la línea de la herramienta
(«…Rings: 1Propiedades de aspirina:»).

## Lo que no se midió

- **El dictado con voz humana.** Lo medido es con voz sintética; hace falta
  grabar el guion (`grabar.html`) antes de decidir.
- **Precalentar la caché del prefijo** al cargar el modelo local: es la
  alternativa a la preselección que no pierde aciertos, y no está implementada.
- **multilingual-e5-small**: su conversión GGUF no carga; no se reconvirtió.
- **Parakeet v3 por `parakeet-cli`** (viene en la build de whisper.cpp): no se
  descargó su modelo.
- **MolScribe sobre capturas de pantalla reales** de un PDF hechas por un usuario
  (el benchmark son recortes limpios), ni en el runtime del producto.
- **Ollama y los proveedores en la nube con `check_preparation`.** La pregunta
  la enruta el clasificador, que no depende del proveedor, pero no se probó.
- **La descripción integrada de `check_preparation` en el arnés** (ver sección 5).
- **El bundle instalado.** Todo es el worktree y la cápsula 5.

## Recomendaciones (decide el propietario)

1. **No cambiar el modelo por defecto.** Ninguno de menos de 1 B iguala a
   Qwen2.5-1.5B en la condición del producto.
2. **No preseleccionar herramientas con embeddings.** Precalentar la caché del
   prefijo al cargar (barato, sin pérdida) y, aparte, medir si traducir al inglés
   las `description` de las herramientas mejora el enrutado de verdad (doc 88 y
   el 80 % → 91 % de aquí apuntan a lo mismo).
3. **Dictado: whisper.cpp con small y el prompt de vocabulario**, si la medida con
   voz humana lo confirma. Arregla una función que hoy está rota y cuesta 190 MB
   más un ejecutable de 8,6 MB.
4. **MolScribe: función nueva, la más cara.** Sólo como propuesta que se confirma,
   con la marca «revisa esta» por debajo de 0,8 de confianza.
5. ~~Integrar `check_preparation` y las correcciones del enrutado~~: hecho
   (`e0fca2dc`, `e2d05af2`, `4437f282`), reprobado en la cápsula.
6. ~~**Arreglar las respuestas en blanco** (sección 7) antes del build de 1.0.2~~
   (afectaba a propiedades, comparaciones y propuestas de docking pedidas por
   nombre): hecho el 2026-10-11.
7. Si se quiere que MolChat explique la **pestaña Preparación** de verdad, es otra
   herramienta: leer la auditoría de una corrida guardada
   (`/evaluation/dossier/{id}/preparacion`), que necesita saber de qué corrida se
   habla.
