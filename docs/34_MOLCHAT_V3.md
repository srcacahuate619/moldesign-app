# 34 — MolChat v3: De la migración a llama-server a las respuestas deterministas

> **Estado:** Implementado y verificado — quality suite 43/43, 0 fallos.
> **Autor:** Sesión de robustecimiento MolChat (agosto 2026).
> **Scope:** Backend (`services/ai/`, `api/routers/ai.py`, `api/routers/history.py`, `services/docking/queue_handler.py`).
> **Continúa:** [`33_MIGRATION_LLAMA_SERVER.md`](33_MIGRATION_LLAMA_SERVER.md) — la base sobre la que se construyó todo esto.

---

## 0. Resumen ejecutivo

MolChat pasó de "un LLM que redacta con guard de seguridad" a **"un sistema híbrido donde el código Python decide lo factual y el modelo solo explica lo conceptual"**.

El cambio de paradigma más importante: **para las consultas químicas factuales (propiedades, rankings, comparaciones, historial), la respuesta final la construye código Python determinista — el LLM no redacta nada, así que no hay nada que pueda alucinar ni invertir.**

Resultado medible (quality suite de 43 casos):

| Métrica | Antes (v2) | Después (v3) |
|---|---|---|
| Propiedades (B01-B09) | 2500-3500ms, flaky | **60-90ms, 0 fallos** |
| Rankings (R01-R03) | 9000-16000ms, flaky | **200-270ms, 0 fallos** |
| Multi-turno (L01) | ~35000ms, fallaba | **570ms, 0 fallos** |
| Historial (H01-H03) | 4000-8000ms | **80-120ms, 0 fallos** |
| Suite completa | 40-42/43 (flakiness) | **43/43, 0 fallos** |

---

## 1. Contexto: de dónde venimos

### 1.1 La base (doc 33 — v2)

La migración a `llama-server.exe` (doc 33) reemplazó `llama-cpp-python` por el binario oficial:
- Subproceso HTTP daemon con protocolo OpenAI-compatible (`/v1/chat/completions`).
- `--jinja` habilita function calling nativo.
- 4 bugs preexistentes corregidos durante la auditoría.

### 1.2 El problema que quedó (motivación de la v3)

Con la v2 funcionando, el stress test de 100 queries + quality suite destaparon **3 problemas de calidad**:

1. **Falsos positivos del guard**: el hallucination guard usaba `tool_results_injected` (solo tools nativas del modelo) e ignoraba al **clasificador determinista** → decía "ninguna herramienta se ejecutó" cuando SÍ se ejecutó.

2. **Alucinaciones multi-molécula**: el modelo Qwen 1.5B **mezclaba valores entre moléculas** del contexto ("paracetamol: 206.3 Da" cuando el real es 151.2) y **invertía relaciones** ("la aspirina es mayor que el ibuprofeno" cuando la tabla decía lo contrario).

3. **El modelo 1.5B es el techo**: con 8 moléculas en contexto, el razonamiento comparativo N>2 lo supera. El guard atrapaba el error, pero el usuario veía el mensaje feo "[Sistema: detecté valores incorrectos...]".

La conclusión de arquitectura fue clara: **no se arregla con más guard — se arregla quitándole la redacción al modelo**.

---

## 2. Arquitectura de MolChat v3

```
Usuario
  └→ Clasificador determinista (regex + keyword, 0 LLM)
       ├→ FACTUAL/COMPARATIVA
       │    └→ Tool (RDKit / molgraph / sesión / historial)
       │         └→ CÓDIGO PYTHON construye la respuesta final
       │              (determinista, 60-270ms, imposible de equivocarse)
       └→ CONCEPTUAL/ABIERTA
            └→ Modelo (Qwen 2.5-1.5B Q4_K_M) redacta
                 └→ Guard de 5 capas (red de seguridad)
```

**Principio rector: "the model proposes, the system disposes".**
El modelo se usa para lo que es bueno (explicar, razonar abiertamente). El código para lo que es infalible (comparar, calcular, ordenar).

---

## 3. Componentes nuevos y modificados

### 3.1 `services/ai/deterministic_responder.py` (NUEVO — el corazón de la v3)

Código Python que construye respuestas finales para consultas factuales. Detecta la pregunta de forma **semántica** (no con ifs sueltos):

**Semántica de métricas** (`_METRICS`):
Cada métrica sabe sus sinónimos, unidad, precisión, orden natural y qué significa "mejor":

| Métrica | Sinónimos detectados | Unidad | "Mejor" = |
|---|---|---|---|
| `molecular_weight` | peso molecular, masa, pesada, liviana, grande, chica, peso | Da | menor |
| `log_p` | lipofil, logp, hidrofil | — | mayor (más lipofílica) |
| `tpsa` | tpsa, superficie polar | A² | menor |
| `affinity_kcal` | afinidad, binding, union, kcal | kcal/mol | **menor** (más negativo) |
| `total_score` | score, puntaje, mejor evaluad | /100 | mayor |
| `hbd`/`hba`/`rotatable_bonds`/`heavy_atoms`/`rings` | donadores, aceptores, anillos... | — | menor |

**Detección de dirección** (`_detect_direction`):
Reconoce formas invertidas y sinónimos: "más pesada" → max, "más liviana" → min, "mejor afinidad" → min (porque más negativo = mejor). Normaliza tildes (`_norm`: "pequeña" → "pequena").

**Responders**:
- `build_rank_response` — ranking de sesión ("cuál es mayor/menor", "más lipofílica")
- `build_compare_response` — comparación par a par ("compará A con B")
- `build_history_response` — historial persistido
- `build_properties_response` — propiedades de una molécula

### 3.2 `services/ai/tools/session_tools.py` (NUEVO)

- **`rank_session_molecules`** — ranking determinista de las moléculas de la conversación actual. Resuelve el bug de comparativas N>2: el código ordena, el modelo no razona.
- **`query_history`** — consulta el historial persistido con filtros (target, sort_by, rangos de score/afinidad/MW). Acepta `user_id` opcional para auth real.

### 3.3 `services/ai/intent_classifier.py` (MODIFICADO)

Nuevos intents + reglas de routing determinista:
- **`rank_session`** → "cuál tiene menor/mayor X" sin 2 nombres (va ANTES del compare)
- **`query_history`** → "qué evalué contra X", "mejores scores"
- **`compare`** → compara 2 nombres (respeta orden de aparición, no longitud — fix: antes invertía A/B)
- **`molgraph`** → "qué moléculas contra 5-HT1A"
- **`recall_anaphoric`** → anáfora pura resuelve SMILES del historial de la conversación

### 3.4 `services/ai/chat_service.py` (MODIFICADO — múltiples fixes)

1. **Hallucination guard 5 capas**:
   - Capa 1: `tool_was_executed` incluye al clasificador determinista (fix falso positivo)
   - Capa 2: `turn_tool_text` — fuente de verdad del tool result del turno actual
   - Capa 3: `history_tool_text` — valores verificados de TODA la conversación (un claim que coincide NO es fabricación)
   - Capa 4: **asignaciones nombre→valor** — "compute_properties (paracetamol): MW: 151.2" permite atrapar "paracetamol: 206.3 Da" (inversión entre moléculas)
   - Capa 5: **`_verify_ranking_logic`** — detecta inversiones de RELACIÓN contra la tabla del ranking ("dijiste que aspirina es mayor que ibuprofeno, pero según la tabla aspirina=180.2 e ibuprofeno=206.3")

2. **Integración de respuestas deterministas**: tras ejecutar la tool, si `build_*_response` devuelve texto → yield directo y `return` (el modelo NO se llama). Log `deterministic_answer` confirma el path.

3. **`_handle_tool_loop` con guard**: las respuestas de rondas recursivas pasan por el guard (antes se servían sin verificar). Flag `_any_tool_round` evita correcciones duplicadas.

4. **`_last_shared_smiles`**: anáfora pura busca el último SMILES del historial de la conversación.

5. **Ventana 40 chars** en asignaciones nombre→valor: evita falso positivo cuando otra molécula está en medio.

### 3.5 `api/routers/history.py` (MODIFICADO — política de persistencia)

**Cambio de política**: TODAS las evaluaciones se registran automáticamente. El botón "guardar" deja de ser el gate del historial (pasa a significar "promover a moldex").

Endpoint `/history/evaluations` ampliado:
- **Sin gate `is_saved`** — muestra todas las evaluaciones del usuario
- **18 filtros combinables**: receptor, rangos de score/afinidad/MW/LogP/TPSA, Lipinski, PAINS, QED, ADME, drug-likeness, nombre, SMILES, estado
- **12 campos de orden**: created_at, total_score, affinity_kcal, affinity_score, molecular_weight, log_p, tpsa, qed, adme_score, druglikeness_score, gnn_score, sa_score

### 3.6 `services/docking/queue_handler.py` (MODIFICADO — política)

**Eliminadas las 3 llamadas a `_schedule_cleanup`**: antes, las moléculas con score < 50 no guardadas se BORRABAN después de 1 hora. Eso destruía el historial. Ahora **nada se borra automáticamente** — el historial es la base del usuario.

### 3.7 `api/routers/ai.py` (MODIFICADO — auth)

El endpoint `/chat` usa `get_current_user_optional` y pasa `user_id` al chat_service → tool `query_history`. Si hay usuario autenticado, consulta SU historial; si no, el usuario demo.

### 3.8 `services/ai/providers/local_llm_provider.py` (MODIFICADO — bug de producción)

**`_pick_first_available_model`**: antes elegía el primer .gguf por orden alfabético → "Bonsai-8B-Q1_0.gguf" < "qwen..." → **el default era Bonsai Q1 (1-bit, el peor modelo) sin que nadie lo eligiera**. Fix: prioriza `_DEFAULT_MODEL_FILE` (Qwen 2.5 Q4_K_M) si existe.

### 3.9 `services/ai/local_llm.py` (MODIFICADO — RAM)

KV cache quantizada a `q8_0` + `--cache-ram 256`: la RAM del server pasó de 5-6GB a **~1.6GB estable** (verificado en stress test de 100 queries). El default del modelo es `qwen2.5-1.5b-instruct-q4_k_m.gguf`.

---

## 4. Modelo de producción

| Atributo | Valor |
|---|---|
| Modelo | `qwen2.5-1.5b-instruct-q4_k_m.gguf` (1.04 GB) |
| Por qué | Llama tools nativas con JSON válido (Bonsai Q1 los rompe), coherencia de texto superior |
| Default | `local_llm.py` línea 54 (`_DEFAULT_MODEL_FILE`) |
| KV cache | q8_0 (2.65GB vs 5.3GB fp16) |
| RAM del server | ~1.6GB estable (stress test 100 queries) |

**Por qué NO Bonsai-8B-Q1_0**: A/B test demostró que Bonsai genera argumentos JSON corruptos en function calling nativo ("solo nombre" → `_raw` con SMILES inválido infinito) y es inferior en coherencia de texto. El mito de "Bonsai es mejor agenticamente" no se sostiene con evidencia.

---

## 5. Quality Suite (regresión)

**`backend/quality_suite.py`** — 43 casos reutilizables que cubren todos los escenarios:

| Categoría | Casos | Validación |
|---|---|---|
| Básicos (propiedades por nombre/SMILES) | B01-B09 | Valores del tool result repetidos |
| Comparaciones (2 moléculas) | C01-C05 | Ambas moléculas presentes, valores correctos |
| Conceptuales | K01-K05 | Sin alucinación de valores |
| Inválidos/bordes | I01-I06 | Sin crash, respuesta honesta |
| Anáforas (con nombre, puras, sin contexto) | A01-A04 | Molécula objetivo resuelta |
| Drug-likeness/ADMET/molgraph | D01-D04, M01-M02 | Sin errores |
| Multi-turno + ranking | L01, R01-R03, V01 | Ranking determinista correcto |
| Historial | H01-H03 | Datos reales de la DB |

**Correr:** `python quality_suite.py` desde `backend/` (requiere el modelo Qwen cargado).

Resultado: **43/43, 0 fallos** — y sin flakiness porque las queries deterministas no dependen del modelo.

---

## 6. Decisiones de arquitectura (ADRs implícitos)

### D1: El código decide lo factual, el modelo explica lo conceptual
**Problema:** el modelo 1.5B invierte relaciones y mezcla valores.
**Decisión:** las respuestas factuales se construyen en Python (deterministic_responder); el modelo queda solo para conceptuales.
**Tradeoff:** respuestas más "formuladas" para las factuales — aceptado porque la corrección vale más que la prosa.

### D2: El historial registra todo automáticamente
**Problema:** las moléculas con score < 50 se borraban tras 1 hora.
**Decisión:** nada se borra automáticamente; `is_saved` pasa a significar "promovido a moldex".
**Tradeoff:** más filas en la DB — aceptado porque habilita el re-docking y el historial completo.

### D3: El clasificador es autoritativo en ambos sentidos
El clasificador determinista decide tool (ejecuta directo) O no-tool (bloquea tools del modelo). El modelo nunca decide si toolear — evita que el 1-bit llame `pubchem_lookup` en "calcula propiedades de KILLMEnow".

### D4: Los filtros del historial cubren todas las combinaciones
18 filtros + 12 órdenes combinables — el objetivo es que cualquier pregunta del usuario sobre el historial tenga una respuesta determinista, no inventada.

### D5: Resolución de nombres por capas (F3 — "propiedades de nicotina" ya funciona)
**Problema:** el clasificador solo conocía ~25 nombres hardcodeados (dict duplicado en 4 módulos). "propiedades de nicotina" caía a `unknown` y el LLM respondía prosa ("necesitamos obtener su SMILES...") en vez de calcular.
**Decisión:** nueva capa `services/ai/name_resolver.py` + fuente única `services/ai/known_molecules.py` (~170 nombres + 159 traducciones es→en). Cadena de resolución: dict unificado → MolGraph FTS5 → PubChem-by-name (SOLO si `allow_web=True`) → fuzzy (difflib cutoff 0.8, captura "dapaglifocina"→dapagliflozina).
**Privacidad:** PubChem jamás se consulta en modo offline — el flag `allow_web` (botón online/offline que ya existía) es la puerta.
**Tradeoff:** el dict es intencionalmente limitado; los nombres fuera caen elegantemente al fallback (PubChem si online, LLM si no hay red).
**Integración:** hook F3 en `chat_service.py` — si el intent es `chemical`/`unknown` sin SMILES y el texto pide datos factuales, intenta resolver antes de delegar al LLM. Los 4 dicts duplicados se unificaron en `known_molecules.py` (el clasificador importa `KNOWN_SMILES` con solo SMILES válidos).

### D6: Resolución de targets por nombre común (F4 — "receptor de serotonina" → 7E2Y)
**Problema:** `_extract_target_pdb` solo reconocía PDB IDs ("7E2Y"). El usuario pide docking contra "receptor β-adrenérgico" y el pipeline devolvía error crudo ("Pipeline de docking no disponible") que el LLM repetía.
**Decisión:** nueva capa `services/ai/target_resolver.py` + datos `backend/data/target_aliases.json` (generado por `scripts/build_target_aliases.py`). Los 387 targets curados tienen PDB local (en `data/targets/` o `data/target_library/{área}/`); 303 tienen aliases comunes (CSV limpio + nombre JSON + COMPND SYNONYM del PDB + aliases es/INN curados). Cadena: PDB ID exacto → alias exacto → token overlap ("receptor de serotonina") → fuzzy ("serotonita"→serotonina).
**Hallazgos de datos:** el CSV catalogaba `3O96` como "ER-alpha LBD Unbound" pero el PDB real es AKT1 (corregido en el generador); los SYNONYM de PDB incluyen tags de constructo de expresión (lysozyme/BRIL chimera) que se filtran.
**Integración:** `_extract_target_pdb` intenta resolver por nombre común PRIMERO, luego regex de PDB. Si intent=docking sin target resuelto, responde determinista con lista de targets disponibles (no ejecuta compute_properties silenciosamente).
**Tradeoff:** los 84 targets sin aliases (solo nombre crudo de PDB) se resuelven por PDB ID o fuzzy; cuantos más aliases es/INN se curen, mejor cobertura.

### D7: Guard de SMILES post-LLM (F5 — "dame un SMILES de un péptido cíclico" ya no alucina)
**Problema:** el system prompt le decía al modelo que usara `validate_smiles`, pero el 1.5B lo ignoró: inventó `C(C)(S)C(C)(S)C(C)(S)C` para "péptido cíclico con puente disulfuro" y de nuevo para "polímero infinito pero molécula pequeña".
**Hallazgo clave:** `C(C)(S)C(C)(S)C(C)(S)C` es VÁLIDO para RDKit (C7H16S3, un tritiol) — la sintaxis no basta. El guard valida DOS niveles: (1) sintaxis RDKit, (2) SEMÁNTICA del pedido: péptido → enlaces amida `C(=O)N`; cíclico → anillos; disulfuro → enlace `S-S`; "polímero infinito + molécula pequeña" → contradicción inherente.
**Decisión:** `_verify_smiles_claims` en `chat_service.py` se ejecuta post-LLM. Si el SMILES es inválido o no cumple el pedido, reemplaza la respuesta con honestidad. Heurística estricta de candidatos: solo tokens con alfabeto SMILES puro (excluye "representa", "SMILES", "es").
**Tradeoff:** el guard no puede juzgar "sentido químico" general — solo verificar características concretas del pedido. Un SMILES válido pero semánticamente incorrecto sin keyword detectable pasa.

### D8: Comparación N-moléculas (F6 — "compárame amlodipino, nifedipino y felodipino")
**Problema:** el clasificador solo soportaba comparación binaria (`smiles`/`smiles_b`). "Compará A, B y C" → tomaba solo A (o A vs B) y el LLM inventaba la tabla.
**Decisión:** `Intent.smiles_list` (lista de SMILES en orden de aparición) + `_find_all_names` (todos los nombres, no solo 2) + bloque F6 en `chat_service` que ejecuta `compute_properties` por CADA molécula (determinista) y `build_multi_compare_response` arma la tabla Markdown con los valores reales.
**Hallazgo:** "biodisponibilidad" NO es computable por RDKit → la tabla honesta solo muestra lo calculable (MW/LogP/TPSA/HBD/HBA/RotBonds/HeavyAtoms/Rings), sin inventar. Además se agregó `felodipino` al dict de moléculas (faltaba — bloqueador de calcio dihidropiridina como amlodipino/nifedipino) y se fijó el regex `_COMPARE_RE` que no matcheaba "Compárame" (á antes de r).
**Tradeoff:** las propiedades no computables (biodisponibilidad, ADME real) quedan fuera de la tabla — es honesto pero el usuario debe saber que se omiten, no que son 0.

### D9: Tool suggest_smiles cruzada con MolGraph (F7 — "dame un smiles interesante")
**Problema:** el usuario pide "dame un SMILES interesante" / "para X receptor" / "variante de X" y el LLM inventa SMILES de memoria (alucina).
**Decisión:** nueva tool `suggest_smiles` (offline) con 3 modos que cruzan con MolGraph:
- `interesting` → SMILES ALEATORIO entre las 2627 evaluadas del grafo con score real ("dame un smiles interesante"). La aleatoriedad es intencional: MolChat NUNCA repite el mismo SMILES (ilusión de variedad sin hardcodear).
- `for_target` → SMILES aleatorio entre las evaluadas contra un target (el chat_service resuelve nombre común → PDB con F4).
- `variant` → primero busca en el grafo si ya existe una derivada (`modified_from`/similar EVALUADA con score); si existe la sugiere con evidencia real; si no, genera BRICS con estrategia aleatoria.
**Robustez:** BRICS tiene guard de tamaño (moléculas <5 átomos pesados se rechazan antes de ejecutar — etanol se colgaba) y `asyncio.wait_for` con timeout (aunque no cancela threads, el guard de tamaño evita el caso lento).
**Integración:** intent `suggest` en el clasificador (detecta "dame un smiles...", "variante de X", "para X receptor") + registro en `_bootstrap_tools` y `quality_suite.py`.
**Tradeoff:** la "variante" prioriza la evidencia del grafo sobre la novedad BRICS — si ya existe una variante evaluada, se sugiere esa (con su score) en vez de generar una nueva.

### D10: Factor X — aleatoriedad en tools de exploración
**Principio:** la aleatoriedad aplica a SELECCIÓN, nunca a VALORES. `compute_properties`, `run_docking`, rankings e historial son hechos exactos → SIEMPRE deterministas (randomizarlos sería mentira y rompería el guard de hallucination). Las tools de exploración muestran un SUBSET de candidatos reales → elegir el subset al azar es legítimo.
**Implementación:** parámetro `randomize` en `query_molgraph`, `molgraph_similar`, `molgraph_neighbors`, `molgraph_scaffolds`. El chat_service lo activa cuando el usuario pidió exploración SIN orden explícito ("dame moléculas contra X", "similares a Y", "muéstrame series") y lo desactiva ante "top 5", "mejores", "ranking", "mayor/menor" (hechos verificables).
**Verificado:** con randomize, 3 llamadas a molgraph_similar dieron 3 subsets distintos; con randomize=false, 2 llamadas idénticas (los hechos no se tocan). 125 tests pasan.
**Resultado:** MolChat nunca repite la misma lista de exploración, pero los datos mostrados son SIEMPRE reales del grafo.

### D11: Guard de alucinación ADME con fuentes (F8 — "Amlodipino LogP 0.83" ya se corrige)
**Problema:** el usuario pidió "para cada valor ADME cita la fuente" y el modelo inventó "LogP: 0.83, TPSA: 103.0" (reales: 2.66, 99.9) con URLs de PubChem falsas. El guard no lo atrapó por 3 bugs encadenados:
1. **Tolerancia 10% demasiado laxa**: "MW 384.3" por real 422.9 (diff 9.1%) pasaba como "coincide". Ahora 1% para propiedades deterministas (MW/LogP/TPSA/HBD/HBA), 10% solo afinidad (ruido docking).
2. **Parser de historial mezclaba moléculas**: `_parse_named_tool_values` con historial concatenado absorbía los valores de TODAS las moléculas bajo la primera — el guard creía que 384.3 (de felodipino) era de amlodipino. Fix: regex con lookahead que detiene el body en el siguiente header `tool (name):`.
3. **Verificación nombre→valor solo corría con tool ejecutada**: ahora corre SIEMPRE (con o sin tools en el turno) — atrapa "cita la fuente" (turno sin tools) donde el modelo inventa con apariencia de precisión.
**Verificado:** 7 casos (inventa LogP, MW invertido, LogP cruzado, TPSA inventado + correctos) — todos pasan con mensajes específicos: "dijiste que amlodipino tiene 'logp ≈ 0.83' pero su valor verificado es 2.66". 125 tests.

### D12: Respuesta "última evaluación" (F9 — "cuál es el score de la última?")
**Problema:** el usuario preguntó por el score de la última evaluación y el sistema respondió con el historial completo ordenado por score, sin identificar la última.
**Decisión:** el chat_service detecta "última/último/más reciente/recién/acabo de" → ordena por `created_at desc` con `limit=1`; `build_history_response` responde "La última evaluación fue: ... score=87.5 | aff=-7.1". Con varias filas, marca la más reciente con "→".

### D13: Tool query_evaluation_details (F10 — el chat consulta evaluaciones reales)
**Problema:** el usuario preguntó "desglosa el Score ADME de la última", "listame las poses con RMSD", "qué comando Vina se usó", "residuos críticos" — y el LLM respondió "no tengo la capacidad" porque NINGUNA tool consultaba la DB. Pero `evaluation_results` tiene TODO: adme_score + subcomponentes (LogS/PPB/BBB/HIA/Lipinski/QED/SA), docking_poses (rank/afinidad/RMSD), vina_version/vina_random_seed, hotspots_hit, evaluated_at.
**Decisión:** nueva tool offline `query_evaluation_details` (which=last/first/target/smiles, limit) que lee la DB real y devuelve los datos formateados. Intent `evaluation` en el clasificador detecta "pose/rmsd/distancia/coordenadas/adme/residuos/vina/comando/timestamp/ultima evaluacion/desglosa". El chat_service ejecuta la tool y sirve la respuesta determinista (el modelo no redacta sobre datos que no tiene).
**Verificado:** "Desglosa el Score ADME" → "ADME: ADME_score=100.0 | druglikeness=55.0 | LogS=-1.62 | PPB=low | BBB=no | HIA=no | Lipinski=OK | QED=0.550 | SA=1.58"; "poses" → "pose 1: aff=-6.145, RMSD_lb=0.0..."; "Vina" → "Vina 1.2.7 | seed=42 | source=pdbqt"; "residuos" → "Hotspots: R:ARG134, R:LYS342...". 125 tests.

### D14: Diseño molecular específico → respuesta honesta (F11) + fix duplicación
**Problema (Bug B):** "Dame el SMILES de un análogo de penicilina CON oxazolidinona fusionada y puente tioéter" disparaba `suggest_smiles variant` (BRICS decía "no pude", mensaje feo). Es un pedido de DISEÑO con requisitos estructurales, no una variante exploratoria.
**Decisión:** intent `design` en el clasificador — si el texto pide SMILES/estructura/análogo + requisitos (fusionado, puente, anillo, tioéter, entre C3/C7, oxazolidinona, betalactámico, residuos) → chat_service responde honesto SIN el LLM: "No puedo diseñar moléculas con requisitos estructurales específicos...". Las variantes simples ("variante de la aspirina") siguen a suggest.
**Fix duplicación (Bug A):** el bloque suggest emitía el resultado DOS veces (el tool result envuelto Y el crudo). Ahora emite UNA vez.

### D15: Fuente verificada con web (F12 — "cita la fuente del LogP" ya no inventa)
**Problema:** el usuario pidió "para cada valor ADME cita la fuente (PubChem/DOI/URL)" y el modelo inventó "LogP: 0.83" con URLs falsas. El guard F8 detecta la invención DESPUÉS, pero la prevención real es consultar la API.
**Decisión:** nueva tool web `query_verified_source` — dado el nombre de una molécula, consulta PubChem (MW/LogP/TPSA/HBD/HBA reales + URL) y ChEMBL (bioactividad real IC50/Ki + URL). Intent `source` en el clasificador (fuente/DOI/URL/cita/de dónde sale) → ejecuta la tool si `allow_web=True`; si offline, responde "activa el modo online".
**Bug de producción corregido:** `_UA = "MolDesign/1.5"` → HTTP 400 en PubChem (nunca funcionó); campos HBD/HBA no existen en PUG REST (son HBondDonorCount/HBondAcceptorCount) → también rompían la petición. Ahora con UA de navegador + campos correctos, PubChem responde 200.
**Verificado:** amlodipino → "PubChem: MW=408.9, LogP=3, TPSA=99.9, HBD=2, HBA=7 + URL" y "ChEMBL: CHEMBL1491 IC50=1.995 nM + URL". Los valores vienen de la API real con su URL — el 1.5B no inventa.

### D16: Sinónimos de recomendación en suggest (F13 — "recomiendame un smiles" ya funciona)
**Problema:** "recomiendame un smiles" → `unknown` (el keyword "recomiend" no estaba en la lista del bloque suggest) → caía al LLM y luego al guard F5 con el mensaje feo.
**Decisión:** agregar "recomiend/recomienda/sugiere/pasame/quiero ver" a los disparadores del intent suggest, y el fallback del bloque ahora devuelve `interesting` por defecto (si no es variante ni target → recomendación aleatoria del grafo). Orden: variant → for_target → interesting.
**Verificado:** "recomiendame un smiles" → "suggest interesting → [MolGraph] c1ccc(O)cc1Cc1cccnc1, score 50.17" (una sola vez, sin guard F5); "variante de aspirina" sigue a variant; "que es un agonista" sigue conceptual. 125 tests.

---

## 7. Limitaciones conocidas

1. **El modelo 1.5B sigue siendo el techo para consultas conceptuales complejas** — explicaciones largas, razonamiento abierto multi-paso. El sistema es sólido; el salto de calidad real vendría de un modelo 3B-7B Q4.
2. **`query_history` con auth real**: el user_id se pasa por el endpoint `/chat`, pero la tool consulta la DB directamente. Para multi-usuario con aislamiento estricto, verificar que `list_user_molecules` siempre filtre por el user_id correcto.
3. **Las respuestas deterministas son templates** — si el usuario pide algo fuera del vocabulario de sinónimos, cae al modelo (fallback correcto, pero más lento).
4. **SMILES del dict `known_molecules.py` sin verificar**: varias entradas nuevas (dapagliflozina, atorvastatina, etc.) llevan `# TODO: verify against PubChem CID ...` — son químicamente plausibles pero NO validadas con PubChem. El pipeline de computación las valida con RDKit en runtime (un SMILES inválido se rechaza honestamente), pero para resultados paper-grade hay que verificar cada CID.
5. **84 targets sin aliases**: los que solo tienen nombre crudo de PDB (>60 chars, sin SYNONYM útil) no se resuelven por nombre común — solo por PDB ID o fuzzy. Curar más aliases es/INN en `TARGET_ALIASES_ES` del generador mejora la cobertura.

---

## 8. Cómo continuar

1. **Upgrade de modelo** (Qwen 2.5-3B/7B Q4): la arquitectura está lista; la suite debería pasar 43/43 sin titubeos con un modelo mayor.
2. **Ampliar el vocabulario de sinónimos** del deterministic_responder si aparecen preguntas nuevas no cubiertas.
3. **Moldex v2**: el botón "guardar" ahora es "promover a moldex" — integrar el flujo completo.
4. **Verificar SMILES TODO** del dict unificado contra PubChem (batch script con CIDs) antes de paper/publicación.
5. **Suite adversarial**: añadir casos de nombres desconocidos/typos (nicotina, dapaglifocina) a `quality_suite.py` para que la regresión F3 quede blindada.
6. **Ampliar aliases de targets**: curar más `TARGET_ALIASES_ES` en `scripts/build_target_aliases.py` (los 84 targets sin alias) y re-generar `target_aliases.json`.
7. **Guard de SMILES post-LLM** (F5): ✅ IMPLEMENTADO — `_verify_smiles_claims` valida sintaxis RDKit + semántica del pedido (amidas/anillos/disulfuro); reemplaza respuestas que no cumplen.
8. **Comparación N-moléculas** (F6): ✅ IMPLEMENTADO — `smiles_list` + `build_multi_compare_response` arma tablas de 3+ moléculas; se agregó felodipino al dict y se fijó el regex "Compárame".
9. **Tool suggest_smiles** (F7): ✅ IMPLEMENTADO — "dame un smiles interesante/para receptor/variante de X" cruza con MolGraph (selección aleatoria, nunca repite); registrada en bootstrap y quality_suite.
10. **Factor X en tools de exploración** (D10): ✅ IMPLEMENTADO — randomize en query_molgraph/molgraph_similar/molgraph_neighbors/molgraph_scaffolds; determinista ante "top/mejor".
11. **Guard ADME con fuentes** (F8): ✅ IMPLEMENTADO — tolerancia 1% propiedades, parser historial separa moléculas, verificación nombre→valor SIEMPRE.
12. **Respuesta "última evaluación"** (F9): ✅ IMPLEMENTADO — created_at desc limit 1 + respuesta directa con score.
13. **Tool query_evaluation_details** (F10): ✅ IMPLEMENTADO — el chat consulta evaluaciones reales (ADME+subcomponentes, poses/RMSD, Vina, hotspots); intent evaluation.
14. **Diseño molecular → honesto** (F11): ✅ IMPLEMENTADO — "SMILES con requisitos estructurales" → intent design (respuesta honesta, no BRICS); fix duplicación en suggest.
15. **Fuente verificada web** (F12): ✅ IMPLEMENTADO — query_verified_source (PubChem real + URL, ChEMBL real + URL); intent source; fix UA PubChem (400→200) y campos HBD/HBA.
16. **Sinónimos recomendación** (F13): ✅ IMPLEMENTADO — "recomiendame un smiles" / "sugiere algo" → suggest interesting; fallback del bloque suggest devuelve interesting.
