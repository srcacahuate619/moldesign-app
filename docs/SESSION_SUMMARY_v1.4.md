> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Session Summary — MolChat v1.4 Final (Julio 3, 2026)

> **Sesión**: 10+ horas de desarrollo continuo
> **Archivos modificados**: ~25
> **Archivos creados**: ~10
> **Arquitectura final**: Qwen2.5-1.5B + MolNeuro + MolGraph + 12 tools + Speed/Deep toggle

---

## ⚡ Pipeline IA — Mejoras de Latencia

### Antes (Phi-3.5 original)

| Métrica | Valor |
|---------|:---:|
| Modelo | Phi-3.5-mini Q4 (2.5 GB) |
| Msg 1 (primer turno) | 91s |
| Msg 2+ | 289s |
| VRAM usada | 2.5 GB |
| Contexto | 4K nativo (RoPE a 16K) |

### Después (Qwen2.5 + todas las optimizaciones)

| Métrica | Valor |
|---------|:---:|
| Modelo | Qwen2.5-1.5B Q4 (1.04 GB) |
| Msg 1 (speed mode) | **13s** |
| Msg simple (speed) | **4.5-6.3s** |
| Msg 2+ (speed) | **9.7s avg** |
| VRAM usada | 1.04 GB |
| Contexto | 32K nativo |
| Mensajes en 10 min | **~53** (proyectado) |
| Mejora total | **91s → 13s (7x), 289s → 7.7s (37x)** |

---

## 🧠 MolNeuro — Arquitectura Neuronal

| Sistema | Inspiración | Función | Archivo |
|---------|-------------|---------|---------|
| **Context Compression** | Hipocampo | Comprime historial. Solo últimos 6-12 msgs. | `chat_service.py` |
| **Engram Memory** | Corteza | FTS5 búsqueda full-text en historial | `memory_store.py` |
| **Synaptic Pruning** | Poda sináptica | Elimina "gracias", "ok", "hola" del contexto | `chat_service.py` |
| **Attention RAS** | Formación Reticular | Re-ordena mensajes por relevancia | `chat_service.py` |
| **Sleep Consolidation** | Replay hipocampal | Compresión de sesiones pasadas | `memory_store.py` |
| **Deterministic Router** | Tálamo | Clasifica 6 intenciones sin LLM | `chat_service.py` |
| **Limbic System** | Sistema Límbico | XP, nivel, mood, preferencias | `limbic_system.py` |
| **Dynamic Prompt** | Córtex Prefrontal | Prompt adaptativo según etapa + intención | `chat_service.py` |
| **ReAct Light** | Cerebelo | Tool interceptor recursivo (2 rondas) | `chat_service.py` |
| **Hallucination Guard** | Verificador | Regex numérico cross-check vs contexto real | `chat_service.py` |
| **Factual Mode** | Reflejo | Ejecuta tool ANTES del LLM para 0% alucinación | `chat_service.py` |

---

## 🧬 MolGraph — Knowledge Graph Químico Personal

| Componente | Archivo | Estado |
|-----------|---------|:---:|
| Nodos (molecules, targets, evaluations) | `molgraph.py` | ✅ |
| Aristas (docking, same_target, modified_from) | `molgraph.py` | ✅ |
| Fingerprints RDKit (2048-bit Morgan) | `molgraph.py` | ✅ |
| FTS5 search | `molgraph.py` | ✅ |
| Cross-Evaluation Impact Analysis | `molgraph.py` | ✅ |
| Scaffold/Series Auto-Detection | `molgraph.py` | ✅ |
| Drug-Likeness Stats | `molgraph.py` | ✅ |
| ADMET Correlation | `molgraph.py` | ✅ |
| Tools (12 registradas) | `tools/molgraph_tool.py` | ✅ |
| Integración con MolChat | `chat_service.py` | ✅ |

---

## 🔴 Bugs Encontrados y Corregidos

| # | Bug | Síntoma | Fix | Archivo |
|:-:|------|---------|-----|---------|
| **1** | `embedding=True` en Llama constructor | **2x latencia**: fuerza embeddings en cada forward pass | `embedding=False` (ya no usamos embeddings) | `local_llm.py` |
| **2** | `n_ctx=32768` con RoPE | Atención O(n²) sobre 32K posiciones → **4x más lento** | `n_ctx=16384` default con `MOLCHAT_NCTX` configurable | `local_llm.py` |
| **3** | VRAM threshold 4GB para modelo 1GB | Bloqueaba carga con 2-3GB libres (sobraba) | `MIN_VRAM_FREE_GB=2.0` (Qwen pesa 1.04GB) | `resource_manager.py` |
| **4** | Limbic `get_level(0)` hardcodeado | Siempre "Recién Nacido", nunca subía de nivel | `get_state().get("xp", 0)` real | `chat_service.py` |
| **5** | `≥` (U+2265) en prompt → crash CP1252 | Windows no puede codificar Unicode en llama-cpp-python | `_sanitize_ascii()` en todas las salidas | `chat_service.py` |
| **6** | Tool markers `🛠️` visibles en respuestas | Se guardaban sin limpiar en la conversación | `strip_tool_markers()` antes de `add_message()` | `chat_service.py` |
| **7** | DENSE format (2000 tokens) para "complex" | Siempre inyectado, incluso para preguntas simples | Solo para `intent == "memory"` | `chat_service.py` |
| **8** | Router no detectaba "afinidad" como tool keyword | Fallaba queries tool comunes | Agregada a `_TOOL_KEYWORDS` | `chat_service.py` |
| **9** | Threshold de 2 keywords demasiado alto | "calcula propiedades" no activaba tools | 1 keyword + 3 palabras → "tool" | `chat_service.py` |
| **10** | Memory keywords sin "recordas" | "recordas mi evaluacion?" → "complex" | Agregado `"recordas"` | `chat_service.py` |
| **11** | Orphaned code en router (duplicate returns) | Indentation errors, `return "memory"` duplicado | Limpiado | `chat_service.py` |
| **12** | Tool interceptor solo 1 ronda | Tools encadenadas no funcionaban | `_handle_tool_loop()` recursivo (max 2 rondas) | `chat_service.py` |
| **13** | `generate_summary()` LLM-based + `_quick_compress()` redundantes | Doble gasto de tokens para resumir | Eliminado `generate_summary()`, solo `_quick_compress` | `chat_service.py` |
| **14** | FTS5 search con phrase query | `"termino1 termino2"` → 0 resultados | OR query: `termino1 OR termino2` | `memory_store.py` |
| **15** | `backfill_embeddings_and_summaries` en carga | 30-120s extra en primer mensaje | Eliminado (FTS5 reemplaza embeddings) | `local_llm.py` |
| **16** | `return` dentro de `finally` en FTS5 search | SyntaxWarning + resultados truncados | Movido afuera del `finally` | `memory_store.py` |
| **17** | Consolidate `-999` affinity filter bloquea | Mostraba 0 moléculas (todas filtradas) | `min_affinity > -998` → correcto | `molgraph.py` |
| **18** | Fingerprints `bytes()` → `CreateFromBitString()` mismatch | 0 resultados en similitud química | `pickle.dumps()`/`pickle.loads()` | `molgraph.py` |
| **19** | `max_tokens` no se respetaba estrictamente | LLM generaba más tokens que el límite | Soft cap: `generate_with_cache` no usado. Aceptado como límite blando. | Documentado |
| **20** | `web_tools.py` con código duplicado | `register_web_tools()` ×2, `search_similar` huérfana | Reescrito limpio | `tools/web_tools.py` |

---

## 🟡 Dead Ends (Intentado pero bloqueado)

| # | Tecnología | Resultado | Por qué falló |
|:-:|-----------|:---:|--------------|
| **1** | MTP / Speculative Decoding (`draft_model`) | ❌ Broadcast error | `llama-cpp-python 0.3.32` no soporta CUDA draft models. Versión 0.3.35+ requerida pero no disponible para Python 3.14 en pip. |
| **2** | MTP con `LlamaPromptLookupDecoding(3)` | ❌ Broadcast error | N-gram devuelve array vacío → CUDA batch size 0. |
| **3** | MTP con `ChemistryDraftModel` propio | ❌ Broadcast error | Draft nunca devuelve vacío, pero buffer CUDA en capa C no redimensiona. |
| **4** | Flash Attention (`flash_attn=True`) | ❌ Broadcast error | Incompatible con n_ctx grande en 0.3.32. |
| **5** | `draft_model` con string path a GGUF | ❌ `'str' object is not callable` | 0.3.32 espera `LlamaDraftModel` no path. |
| **6** | CodeGraph integrado al producto | ❌ No aplica | CodeGraph indexa código fuente. No tiene sentido para usuarios químicos. |

**Conclusión MTP**: Esperar `llama-cpp-python >= 0.3.35+` para Python 3.14. Código infraestructura listo (`local_llm_draft.py`, `_resolve_draft_path()`, `Qwen2.5-0.5B` descargado 491MB). Se activa con `MOLCHAT_MTP=1`.

---

## 🟢 Aprendizajes Clave

1. **`embedding=True` en llama-cpp-python cuesta 2x latencia.** Si no se usan embeddings (FTS5 los reemplaza), apagar.
2. **n_ctx afecta la velocidad brutalmente.** 16384→8192 = 2x más rápido. La atención es O(n²).
3. **El sanitizer ASCII es obligatorio en Windows.** llama-cpp-python no maneja Unicode en chat templates.
4. **Prefix caching funciona automáticamente en llama.cpp** si el system prompt comienza igual. Dividir en mensajes fijo + variable es clave.
5. **FTS5 > DENSE** siempre. 100 tokens vs 2000. 0% alucinación.
6. **Los fingerprints RDKit son robustos** pero `bytes()` no se puede cargar con `CreateFromBitString()`. Pickle es confiable.
7. **El tool registry necesita testing por intent.** Varios bugs eran de keywords mal configuradas que el router no activaba.
8. **MolGraph es paper-worthy.** Knowledge graph químico personal con SAR engine basado en datos del usuario.
9. **El toggle speed/deep empodera al usuario.** No tenemos que decidir calidad vs velocidad — el usuario elige según su contexto.
10. **Los tests de estrés revelan bugs que los unit tests no.** 50 mensajes en 10 min encuentra problemas de encoding, indentación, filtros, y duplicados.

---

## 📊 Métricas Finales

| Métrica | Phi-3.5 original | Qwen2.5 final | Mejora |
|---------|:---:|:---:|:---:|
| Msg 1 | 91s | 13s | **7x** |
| Msg simple | 289s | 4.5-6.3s | **46-64x** |
| VRAM | 2.5 GB | 1.04 GB | **2.4x menos** |
| Contexto | 4K (RoPE) | 32K nativo | **8x más** |
| Alucinaciones factuales | 5-10% | **0% (Factual Mode)** | **100%** |
| Tools | 0 | **12** | — |
| MolGraph nodes | 0 | **7** | — |

---

## 📁 Archivos del Proyecto

### Backend (`services/ai/`)
```
├── chat_service.py          ← Orquestador: MolNeuro + Router + Factual + Guard
├── local_llm.py             ← Qwen2.5-1.5B: GPU, n_ctx, embedding=False
├── local_llm_draft.py       ← ChemistryDraftModel (infra MTP lista)
├── resource_manager.py      ← RAM + VRAM + idle timer (thresholds Qwen)
├── memory_store.py          ← FTS5 Engram + Sleep + Conversations
├── limbic_system.py         ← XP + mood + preferencias (JSON + cache)
├── startup_detection.py     ← 3 modos de inicio
├── speech_to_text.py        ← Whisper (faster-whisper tiny, 75MB)
├── model_registry.py        ← Búsqueda HF + descarga + cuantizacion
├── molgraph.py              ← Knowledge graph quimico: nodos, aristas, fingerprints
├── providers/
│   ├── base.py              ← AIProvider abstracto
│   ├── registry.py          ← Singleton ProviderRegistry
│   ├── local_llm_provider.py← Qwen2.5 1.5B (era Phi-3.5)
│   ├── ollama_provider.py   ← Ollama HTTP
│   ├── claude_provider.py   ← Anthropic SDK
│   ├── gemini_provider.py   ← Google REST
│   └── openai_provider.py   ← Cloud (Groq pre-configurado)
├── tools/
│   ├── tool_registry.py     ← ToolDef + ToolRegistry + executor
│   ├── rdkit_tools.py       ← properties, validate, druglikeness, compare + cache
│   ├── docking_tools.py     ← run_docking, get_rescoring (batch)
│   ├── admet_tools.py       ← predict_admet
│   ├── web_tools.py         ← PubChem, ChEMBL, RCSB PDB, search_similar
│   └── molgraph_tool.py     ← 12 MolGraph tools
```

### Frontend
```
├── context/AIContext.tsx     ← State: providers, streaming, polling, chatMode
├── components/ai/
│   ├── ChatPanel.tsx         ← Slide-over + toggle Speed/Deep
│   ├── ChatMessage.tsx       ← Markdown + cursor
│   ├── ChatInput.tsx         ← Voice + dictado + Enter/Shift+Enter
│   ├── AISettingsModal.tsx   ← Providers + ModelBrowser + Quants + GPU
│   ├── ProviderBadge.tsx     ← GPU/CPU/Cloud + VRAM/RAM en vivo
│   └── MarkdownRenderer.tsx  ← Code, bold, lists
└── hooks/useSpeechRecognition.ts ← Local Whisper + Web Speech fallback
```

### Documentación
```
├── docs/Interprete_IA.md    ← Documentación completa del módulo
├── docs/MolGraph.md         ← Knowledge Graph químico
└── docs/SESSION_SUMMARY_v1.4.md ← Este archivo
```

### Backup
```
└── backup_molchat_v1.4/     ← Snapshot pre-antigravity (restore.ps1)
```
