> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Intérprete IA + MolChat — Documentación Completa

> **Versión**: v1.4 (Julio 2026)
> **Archivos**: `backend/services/ai/`, `frontend/components/ai/`, `frontend/context/AIContext.tsx`
> **Modelo default**: Qwen2.5-1.5B-Instruct Q4_K_M (~1.04 GB) — Apache 2.0 license

---

## Índice

1. [Arquitectura General](#arquitectura-general)
2. [Sistema de Proveedores (Provider System)](#sistema-de-proveedores)
3. [MolChat — Chatbot Inteligente](#molchat--chatbot-inteligente)
4. [Gestión de Recursos (RAM + VRAM)](#gestión-de-recursos--ram--vram-)
5. [Aceleración GPU](#aceleración-gpu)
6. [Startup Detection (Auto-arranque Inteligente)](#startup-detection)
7. [Contexto "1M Tokens"](#contexto-1m-tokens)
8. [Componentes Frontend](#componentes-frontend)
9. [Referencia de Endpoints](#referencia-de-endpoints)
10. [Testing](#testing)
11. [Limitaciones](#limitaciones)
12. [Próximos Pasos (v1.5+)](#próximos-pasos-v15)

---

## Arquitectura General

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MolDesign App                                   │
│                                                                        │
│  Frontend (Next.js + Tailwind + Framer Motion)                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  ChatPanel (slide-over flotante)                                  │ │
│  │  ├─ ChatMessage     (burbuja con Markdown + streaming cursor)   │ │
│  │  ├─ ChatInput       (Enter/Shift+Enter + botón Stop)            │ │
│  │  ├─ ProviderBadge   (estado GPU/CPU/Cloud en vivo)              │ │
│  │  └─ AISettingsModal (selector de provider + API keys + GPU info)│ │
│  │                                                                   │ │
│  │  OptionsPanel → "Intérprete IA" → Configuración + toggle manual  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                   │ HTTP + SSE                        │
│  Backend (FastAPI + Python 3.11)                                      │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  api/routers/ai.py  — 10 endpoints REST                           │ │
│  │  services/ai/chat_service.py  — Orquestador central               │ │
│  │  services/ai/providers/  — Strategy Pattern (5 providers)         │ │
│  │  services/ai/resource_manager.py  — RAM + VRAM + idle timer       │ │
│  │  services/ai/memory_store.py  — Memoria jerárquica + embeddings   │ │
│  │  services/ai/startup_detection.py  — 3 modos de inicio            │ │
│  │  services/ai/local_llm.py  — Singleton llama-cpp-python           │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Sistema de Proveedores

### Provider Strategy Pattern

Cada proveedor implementa la interfaz abstracta `AIProvider`
(`backend/services/ai/providers/base.py`):

| Método | Propósito |
|--------|-----------|
| `validate_config()` | ¿API key/base_url configurados? |
| `health_check()` | ¿El proveedor FUNCIONA? (llamada real 1-token) |
| `chat(messages, stream)` | Generar respuesta (streaming o completa) |
| `list_models()` | Listar modelos disponibles |
| `get_info()` | Metadata para la UI |

### Proveedores implementados

| ID | Nombre | Archivo | Requiere |
|----|--------|---------|----------|
| `local` | Qwen2.5 1.5B Local (llama-cpp-python) | `local_llm_provider.py` | Nada — offline |
| `ollama` | Ollama (localhost:11434) | `ollama_provider.py` | Ollama instalado |
| `claude` | Claude (Anthropic API) | `claude_provider.py` | `ANTHROPIC_API_KEY` |
| `gemini` | Gemini (Google API) | `gemini_provider.py` | `GEMINI_API_KEY` |
| `openai` | Cloud (OpenAI/Groq) | `openai_provider.py` | `api_key` + `base_url` |

El proveedor `openai` es **compatible con cualquier API de chat**:
OpenAI, Groq (gratis, 500+ tok/s), DeepSeek, Together, vLLM, LocalAI, etc. Solo requiere
configurar `base_url` (ej: `https://api.groq.com/openai/v1`).

### ProviderRegistry

Singleton `get_provider_registry()` que gestiona el ciclo de vida:
- `register(provider)` — registrar un proveedor
- `get_active()` — obtener el que está en uso
- `set_active(id)` — cambiar proveedor activo
- `list_providers()` — listar todos con estado

### Health Check

Cada proveedor cloud implementa `health_check()` con una llamada real
de **1 token** para detectar si la API key tiene saldo:

| Status | Significado |
|--------|-------------|
| `OK` | API key válida y con saldo |
| `NO_API_KEY` | Sin API key configurada |
| `NO_TOKENS` | API key sin saldo/quota |
| `CONNECTION_ERROR` | Error de red o timeout |

El check tarda ~200-500ms por proveedor. Se ejecuta en paralelo via
`asyncio.gather()` en `startup_detection.py`.

---

## MolChat — Chatbot Inteligente

### Panel lateral flotante

Botón 🤖 abajo a la derecha en todas las pantallas. Abre/cierra un
panel slide-over de 420px con animación spring (Framer Motion).

### Funcionalidades

- **Streaming SSE**: tokens aparecen progresivamente como en ChatGPT
- **Markdown**: código, negritas, listas, inline code (renderizado custom)
- **Cursor titilante**: animación CSS `blink` durante generación
- **Botón Stop**: aborta el streaming inmediatamente
- **Auto-reintento**: si el pipeline está ocupado, espera hasta 60s
- **Fallback automático**: si el provider activo falla, cae al Local LLM
- **Banners de advertencia**: amarillos para fallback, azules para info

### Conversaciones

Endpoint `GET/POST/DELETE /ai/conversations`. Cada conversación:
- Persiste en memoria (chat_service dict)
- Muestra preview en sidebar
- Botón "Nuevo chat" resetea el contexto

### Contexto automático de molécula

Si el usuario está viendo una evaluación, `molecule_context` inyecta
los datos de docking como JSON en el system prompt. El LLM recibe
el score, afinidad, hotspots, y puede responder con contexto.

---

## Gestión de Recursos (RAM + VRAM)

### ResourceManager

Singleton `get_resource_manager()` en `backend/services/ai/resource_manager.py`.

**Reglas de oro**:
1. LLM NUNCA se carga al iniciar la app — solo on-demand
2. Pipeline ocupado → LLM descargado (salvo VRAM suficiente)
3. RAM libre < 4 GB → LLM no se carga
4. VRAM libre < 3.5 GB → LLM no se carga en GPU
5. 5 min idle → auto-descarga
6. RAM o VRAM caen por otra app → descarga preventiva en ≤60s
7. `keep_loaded=true` → no descarga en pipeline

### Thresholds

| Constante | Valor | Significado |
|-----------|:-----:|-------------|
| `MIN_RAM_FREE_GB` | 4.0 | Mínimo para cargar LLM (Windows ya come 2-3 GB) |
| `KEEP_LLM_RAM_GB` | 2.5 | Si RAM baja de esto con LLM cargado → descargar YA |
| `COMFORTABLE_RAM_GB` | 6.0 | Si > esto, mantener cargado |
| `MIN_VRAM_FREE_GB` | 2.0 | Mínimo para cargar Qwen2.5-1.5B Q4 (1.0 GB + KV 0.5 + buffer) |
| `LOW_VRAM_FREE_GB` | 1.0 | Si VRAM cae de esto → descargar YA |
| `COMFORTABLE_VRAM_FREE_GB` | 4.0 | Si ≥ esto, no descargar durante pipeline |
| `IDLE_TIMEOUT_S` | 300 | 5 min sin uso → descargar |
| `IDLE_CHECK_INTERVAL_S` | 60 | Intervalo del idle checker |

### Detección de VRAM (prioridad de fuentes)

```
1️⃣ nvidia-smi --query-gpu=memory.free
   └─ La más precisa: VE TODAS las apps (juegos, Chrome, etc.)
   └─ Cache: 10 segundos

2️⃣ torch.cuda.mem_get_info()
   └─ Solo ve memoria de PyTorch (parcial)
   └─ Fallback cuando nvidia-smi no está disponible

3️⃣ detect_hardware().gpu_vram_gb
   └─ VRAM total de la GPU (optimista)
   └─ Fallback final
```

### RAM — psutil

`psutil.virtual_memory().available` devuelve la RAM **realmente libre**
de TODO el sistema (Windows, Chrome, juegos, Docker). Cache: 3 segundos.

### Ciclo de vida del LLM

```
App arranca → LLM NO cargado (0 MB extra)
  ↓
Usuario abre MolChat y manda mensaje
  ↓
resource_manager.can_load():
  ├─ Pipeline ocupado → rechaza con mensaje
  ├─ RAM < 4 GB     → rechaza con mensaje
  ├─ VRAM < 3.5 GB  → rechaza (si GPU)
  └─ OK → llama cpp tiene luz verde

LocalLLM.load():
  ├─ _detect_gpu() → obtiene gpu_name, gpu_vram_gb
  ├─ _calculate_gpu_layers() → -1 (todo) / N (parcial) / 0 (CPU)
  ├─ _load_with_gpu_fallback() → intenta GPU, fallback CPU
  └─ on_llm_loaded() → arranca idle checker

Idle checker (cada 60s):
  should_unload():
    ├─ idle > 300s → descargar
    ├─ RAM < 2.5 GB → descargar (otra app consumió)
    └─ VRAM < 2.0 GB → descargar (juego abierto)

Pipeline arranca:
  on_pipeline_start():
    ├─ keep_loaded → nunca descargar
    ├─ VRAM ≥ 4 GB libre → mantener (cabe LLM + pipeline)
    └─ VRAM < 4 GB → descargar (prioridad pipeline)

Pipeline termina:
  on_pipeline_end():
    └─ state = IDLE → LLM disponible de nuevo
```

---

## Aceleración GPU

### Detección dinámica de capas

En `local_llm.py`, `_calculate_gpu_layers()` decide cuántas capas
del modelo se offloadean a GPU según la **VRAM libre real**:

 | VRAM libre | Comportamiento |
|:---:|--------|
| ≥ 2.0 GB | Offloadear TODAS las capas (`n_gpu_layers = -1`) |
| 1.0–2.0 GB | Offload parcial (ej: 14/28 capas para 1.5 GB) |
| < 1.0 GB | CPU-only (`n_gpu_layers = 0`) |

Nota: Qwen2.5-1.5B tiene ~28 capas a Q4_K_M (~1.04 GB total).

| Configuración | Tokens/segundo |
|:---|:---:|
| CPU (6-8 cores) | 5-10 tok/s |
| GPU CUDA (offload completo) | **60-90 tok/s** |
| Cloud provider (Groq/OpenAI) | Instantáneo |

---

## Startup Detection

### 3 modos de inicio automático

`GET /ai/startup` escanea todos los providers y devuelve:

| Modo | Condición | Comportamiento |
|------|-----------|----------------|
| `auto_start` | Sin API keys cloud configuradas | MolChat se abre solo con Local LLM + mensaje azul de bienvenida |
| `notify_fallback` | API keys configuradas pero sin saldo/quota | MolChat se abre solo con banner amarillo y usa Local LLM |
| `manual_only` | Al menos 1 provider cloud funciona | MolChat NO se abre. Usuario activa desde Opciones |

### Flujo

```
App monta ChatPanel
  ↓
detectStartup() → GET /ai/startup
  ↓
Backend escanea providers en paralelo con health_check()
  ↓
Determina modo según resultados
  ↓
Frontend:
  ├─ auto_start / notify_fallback → SET_PANEL_OPEN true + mensaje
  └─ manual_only → panel cerrado, botón flotante visible
```

### Re-detección

Cuando el usuario guarda configuración en AISettingsModal, se
re-ejecuta `detectStartup()` para actualizar el modo.

---

## Contexto "1M Tokens"

El usuario siente que nunca pierde contexto, aunque el modelo
tenga 4K-16K tokens nativos.

| Técnica | Implementación | Archivo |
|---------|---------------|---------|
| Memoria jerárquica | catalog (~50B/entry) siempre visible, details (~2KB) bajo demanda | `memory_store.py` |
| Context Compression | Solo últimos 10 mensajes, el resto comprimido. Ahorra ~6K tokens | `chat_service.py::get_recent_and_compressed()` |
| Engram Memory (FTS5) | Búsqueda full-text en historial. Resultados precisos, ~600 tokens | `memory_store.py::search_chat_history()` |
| Sliding window | Últimos 8K tokens + resumen del resto | `chat_service.py::_prepare_messages_with_context()` |
| Context-aware molecule | Molécula actual inyectada como párrafo curatorial | `chat_service.py::_build_molecule_prompt()` |
| Deterministic Router | Clasifica intent sin LLM (tool/memory/complex) | `chat_service.py::_route_user_intent()` |
| Limbic System | XP, nivel, mood, preferencias. Personalidad evolutiva | `services/ai/limbic_system.py` |

### MolNeuro v1.4 — Sistema neuronal local

Arquitectura para modelos locales sin dependencias externas:

| Componente | Función | Δ tokens |
|-----------|---------|:---:|
| **Context Compression** | Comprime historial viejo, mantiene últimos 10 mensajes | −6,000 |
| **Engram Memory** | FTS5 reemplaza DENSE genérico por búsqueda precisa | −1,400 |
| **Deterministic Router** | Rutea sin LLM: tool, memory, complex | −30% queries |
| **Limbic System** | XP + mood + preferencias en JSON 2 KB | +100 |
| **Dynamic Prompt** | Prompt adaptativo según intención y etapa | +200 |
| **ReAct Light** | Plan paso a paso + ejecución secuencial de tools | +200 |
| **NETO** | Más calidad, menos contexto | **−6,900 tokens** |

---

## Hallucination Guard (Cerebelo)

Verifica automáticamente que los números en la respuesta del LLM coincidan con los datos reales del `molecule_context`. Si detecta una diferencia >10%, inyecta una corrección como system message antes de que el usuario la lea.

| Número que puede alucinar | Regex de detección |
|--------------------------|-------------------|
| `affinity_kcal` | `afinidad\\s*(?:de\\|:)?\\s*([-\\d.]+)` |
| `total_score` | `score\\s*(?:total\\|general)?\\s*(?:de\\|:)?\\s*(\\d+)` |
| `molecular_weight` | `(\\d+\\.?\\d*)\\s*(?:Da\\|g/mol)` |
| `log_p` | `logp\\s*(?:de\\|:)?\\s*([-\\d.]+)` |

Ejemplo:
```
Usuario: "¿Qué score tiene la aspirina?"
LLM: "La aspirina tiene score 78/100"  ← INCORRECTO (score real = 68)
  ↓
Guard: [Sistema: dijiste 'score ≈78' pero el valor real es 68]
  ↓
LLM: "La aspirina tiene score 68/100" ← CORREGIDO
```

## PubChem + ChEMBL RAG

Cuando el usuario menciona un fármaco conocido (aspirina, ibuprofeno, paracetamol, etc.), MolChat busca datos REALES en PubChem y ChEMBL antes de responder:

| API | Qué aporta | Cache offline |
|-----|-----------|:---:|
| **PubChem** | MW, LogP, TPSA, fórmula, SMILES canónico | ✅ `pubchem_cache.db` |
| **ChEMBL** | Bioactividad (IC50, Ki, targets), ensayos | ✅ `chembl_cache.db` |
| **RCSB PDB** | Estructuras de proteínas, sitios activos | ❌ (requiere internet) |

**Tool Registry** (20 tools registradas — 16 offline + 4 online):

| Módulo | Tools | Offline |
|--------|-------|:------:|
| `rdkit_tools.py` | `compute_properties`, `validate_smiles`, `check_druglikeness`, `compare_molecules` | 4/4 |
| `docking_tools.py` | `run_docking`, `get_rescoring` | 2/2 |
| `admet_tools.py` | `predict_admet` | 1/1 |
| `analog_tools.py` | `generate_analogs`, `explain_fragments` | 2/2 |
| `web_tools.py` | `pubchem_lookup`, `chembl_activity`, `search_pdb`, `search_similar` | 0/4 |
| `molgraph_tool.py` | `query_molgraph`, `molgraph_neighbors`, `molgraph_similar`, `molgraph_impact`, `molgraph_scaffolds`, `molgraph_druglikeness`, `molgraph_admet` | 7/7 |

## Benchmarks Reales (GTX 1660 SUPER, Qwen2.5-1.5B Q4)

### Prueba de estrés — 20 mensajes en 83 segundos

| Msg | Pregunta | Latencia | Tokens | Recall |
|:---:|----------|:---:|:---:|:---:|
| 1 | ¿Qué tal aspirina? | 13.0s | 265 | 40% |
| 2 | ¿Cumple Lipinski? | 7.7s | 182 | 20% |
| 3 | ¿Hotspots? | 6.3s | 82 | 20% |
| 4 | ¿PAINS? | **4.8s** | 22 | 20% |
| 5 | ¿Sintetizar? | 11.4s | 163 | 20% |
| 6-20 | Varios | ~4-8s | 19-837 | 20-60% |

### Evolución completa (Phi-3.5 original → Qwen2.5 optimizado)

| Hito | Msg 1 | Msg 2+ | Contexto usado |
|------|:---:|:---:|:---:|
| **Phi-3.5 original** | 91s | 289s | ~41% en msg 2 |
| Qwen2.5 + carga | 17s | 55s | ~17% |
| + Concisión + max_tokens | 24s | 12s | ~13% |
| + Farmacología prompt | 18s | 12s | ~11% |
| **+ n_ctx=16384 + todos los fixes** | **13s 🚀** | **4.8-7.7s 🚀** | **4% en 20 msgs** |

**Mejora total**: 91s → 13s (7x), 289s → 7.7s (37x). 20 msgs en 1.3 min (vs 2 antes).

## Componentes Frontend

```
frontend/
├── context/
│   └── AIContext.tsx                  ← React Context: state + streaming + polling
├── components/ai/
│   ├── ChatPanel.tsx                  ← Slide-over panel con animación spring
│   ├── ChatMessage.tsx                ← Burbuja con Markdown + cursor titilante
│   ├── ChatInput.tsx                  ← Input auto-resize + Enter/Shift+Enter
│   ├── AISettingsModal.tsx            ← Modal: selector provider + API keys + GPU info
│   ├── ProviderBadge.tsx              ← Badge en vivo: GPU/CPU/Cloud + estado recursos
│   └── MarkdownRenderer.tsx           ← Renderiza code, bold, lists, inline code
├── components/
│   └── OptionsPanel.tsx               ← "Intérprete IA" + toggle Abrir/Cerrar MolChat
└── app/
    └── layout.tsx                     ← AIProvider + ChatPanel wrappeando la app
```

### AIContext — State Management

```typescript
type AIState = {
  startupMode:       "loading" | "auto_start" | "notify_fallback" | "manual_only"
  startupMessage:    string
  warningBanner:     string | null
  isPanelOpen:       boolean
  isSettingsOpen:    boolean
  isStreaming:       boolean
  streamingContent:  string
  messages:          AIMessage[]
  activeProviderId:  string
  providers:         AIProviderInfo[]
  resourceStatus:    ResourceStatus | null
  providerConfigs:   Record<string, AIProviderConfig>
}
```

### ResourceStatus — polling cada 8s

```typescript
type ResourceStatus = {
  pipeline_state:    "idle" | "busy"
  llm_state:         "unloaded" | "loading" | "loaded"
  ram_free_gb:       number
  ram_total_gb:      number
  using_gpu:         boolean
  gpu_name:          string
  gpu_vram_total_gb: number
  vram_free_gb:      number
  keep_loaded:       boolean
}
```

### ProviderBadge — estados

| Estado | Ejemplo |
|--------|---------|
| Cloud provider | `🔵 Claude · Cloud` |
| GPU cargado | `⚡ Qwen2.5 1.5B Local \n GPU · RTX 3080 libre 5.2G/10G` |
| CPU cargado | `🖥️ Qwen2.5 1.5B Local \n CPU · 8.1G libre / 32G` |
| Pipeline ocupado | `🟡 Evaluación · GPU libre 3.1G · RAM 5.2G` |
| Descargado | `🖥️ RAM 12.3G / 32G · descargado` |

---

## Referencia de Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/ai/startup` | GET | Detectar modo de inicio (auto_start/notify_fallback/manual_only) |
| `/ai/providers` | GET | Listar providers con estado (configurado ✓/✗, activo) |
| `/ai/providers/active` | GET/POST | Consultar/cambiar provider activo |
| `/ai/providers/configure` | POST | Configurar API key, base_url, modelo, temperatura |
| `/ai/models` | GET | Listar modelos del provider (con `?provider_id=`) |
| `/ai/chat` | POST | Chat — streaming SSE (`stream=true`) o completo |
| `/ai/conversations` | GET/POST | Listar/crear conversaciones |
| `/ai/conversations/{id}` | DELETE | Eliminar conversación |
| `/ai/status` | GET | Estado completo: providers, RAM, VRAM, pipeline, LLM |
| `/ai/settings` | PATCH | Configurar `keep_loaded` |

### Formato SSE (streaming)

```
data: Hola
data: , 
data: esto
data:  es
data:  streaming
event: warning
data: ⚠️ Claude falló. Usando modo local como respaldo.
data: [DONE]
```

Los eventos `event: warning` se renderizan como banner amarillo en
la UI. Los tokens `data: ...` se concatenan para formar la respuesta.

---

## Testing

### Cargar LLM local

```python
from services.ai.local_llm import get_local_llm, is_local_llm_available

llm = get_local_llm()
llm.load()  # ~2s, devuelve True/False

# GPU info
print(llm.gpu_name)        # "NVIDIA GeForce RTX 3060"
print(llm.gpu_vram_gb)     # 12.0
print(llm.using_gpu)       # True
print(llm.gpu_layers)      # -1 (todas las capas)

# Streaming
for token in llm.generate_stream(prompt="¿Qué es un puente de hidrógeno?"):
    print(token, end="", flush=True)
```

### Chat via API

```bash
# Modo streaming SSE
curl -X POST http://localhost:8000/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"¿Qué es Vina docking?"}],"stream":true}'

# Modo completo
curl -X POST http://localhost:8000/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"¿Qué es Vina docking?"}],"stream":false}'
```

### Startup detection

```bash
curl http://localhost:8000/ai/startup
# {"mode":"auto_start","reason":"No configuraste ninguna API key...",...}
```

---

## Limitaciones

| Limitación | Detalle |
|------------|---------|
| **RAM mínima** | ~1.0 GB adicionales para Qwen2.5-1.5B Q4 |
| **RAM recomendada** | 6 GB total (Windows 2-3 + MolDesign ~1 + LLM 1.0 = ~5 GB) |
| **VRAM mínima** | 1.5 GB libre para offload completo (~2 GB total) |
| **CPU-only speed** | 5-10 tok/s — aceptable para mensajes cortos |
| **GPU (CUDA)** | 60-90 tok/s. Requiere llama-cpp-python compilado con CUDA |
| **Contexto nativo** | 32,768 tokens (nativo, sin RoPE scaling) |
| **Contexto efectivo** | "∞" via Context Compression + Engram FTS5 + Sleep Consolidation |
| **nvidia-smi** | Necesario para VRAM real. Sin él, detección degradada |
| **Precisión científica** | Herramientas (RDKit, PubChem, ChEMBL) dan datos reales |
| **Multi-GPU** | Solo usa GPU 0 (la primera detectada por CUDA) |
| **MTP (Speculative Decoding)** | Bloqueado hasta `llama-cpp-python >= 0.3.35+` para Python 3.14 |

---

## Próximos Pasos (v1.5+)

### ✅ Completado en v1.4
| Feature | Estado |
|---------|:---:|
| Descarga de modelos desde UI (ModelBrowser + HuggingFace) | ✅ |
| Cuantización dinámica según RAM/VRAM | ✅ |
| Historial persistente (SQLite, sobrevive restarts) | ✅ |
| Voice input (local Whisper + Web Speech fallback) | ✅ |
| Plugins / Tools System (9 tools: RDKit, PubChem, ChEMBL, ADMET, Vina) | ✅ |
| PubChem RAG + auto-lookup de 20 fármacos conocidos | ✅ |
| ChEMBL RAG (bioactividad IC50, Ki, targets) | ✅ |
| Anti-hallucination Guard (verificación numérica) | ✅ |
| Tool Cache (resultados RDKit por SMILES en SQLite) | ✅ |
| MolNeuro: Context Compression + Engram FTS5 + Limbic + Router | ✅ |

### Pendiente para v1.5+
| # | Tarea | Prioridad | Bloqueante |
|:-:|-------|:---:|------|
| 1 | MTP / Flash Attention (esperar `llama-cpp-python >= 0.3.35+`) | 🟡 | Paquete pip para Python 3.14 |
| 2 | MolNeuro Agent (Planner → Obrero → Reviewer full loop) | 🟡 | — |
| 3 | Modo "Solo herramientas" (nunca dejar al LLM inventar números) | 🟢 | — |
| 4 | CodeGraph para debugging estructural del código MolDesign | ✅ Instalado | — |
