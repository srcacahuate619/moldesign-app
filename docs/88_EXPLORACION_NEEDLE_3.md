# 88 — Needle 3 (Cactus Compute): tecnología en exploración

**Estado: EN EXPLORACIÓN — no integrada, no recomendada para integrar hoy.**
**Fecha de la medida: 2026-09-20.** Arnés y datos en
[`scripts/bench_tool_calling/`](../scripts/bench_tool_calling/).

Este documento no decide nada sobre el producto. Registra qué es Needle 3, qué
se midió contra el motor que MolChat usa hoy, bajo qué condiciones, y qué
quedaría por medir si alguien la reabre. Está aquí porque la tecnología es
interesante y porque la medida contradice varias de sus afirmaciones públicas:
las dos cosas conviene que queden escritas.

---

## 1. Qué es

Modelo de fundación para dispositivos pequeños, de Cactus Compute.
**Apache-2.0** en código y pesos. Hace tres cosas: llamada a herramientas,
extracción estructurada y embeddings.

| | dato | fuente |
|---|---|---|
| Licencia | Apache-2.0 | `pyproject.toml`, tarjeta de HF |
| Tamaño anunciado | 8–29 MB, 29–121M parámetros, 2-bit | cactuscompute.com/needle |
| Tamaño **medido** | paquete 759 KB + `needle3.cact` **35,3 MB** | descarga por defecto |
| Dependencias base | sólo `huggingface_hub` — sin torch, sin numpy | `pyproject.toml` |
| Python | ≥3.9 (el runtime embebido es 3.11.9: compatible) | `pyproject.toml` |
| Telemetría | **activada por defecto** | ver §5 |

## 2. Por qué se miró

MolChat no funciona recién instalado. `services/ai/local_llm.py:812` lo dice: el
instalador empaqueta `llama-server.exe` pero **ningún `.gguf`**; el investigador
instala 504 MiB y el chat le pide descargar **1,12 GB** (Qwen2.5-1.5B) antes de
hacer nada, en un producto que se vende como autónomo sin red.

Un modelo de ~35 MB cabría en el instalador con un +7%. Ésa era la hipótesis.

## 3. Cómo se midió

- **21 herramientas offline reales** del producto, exportadas con
  `ToolDef.to_openai_tool()`. No herramientas de juguete.
- **21 casos**: 15 en alcance, 6 fuera. Cada uno con pareja ES/EN de significado
  idéntico, para aislar el idioma.
- **Diseño 2×2**: idioma de la pregunta × idioma de la descripción de la
  herramienta.
- **Contra**: Qwen2.5-1.5B-Instruct Q4_K_M por `llama-server` (build CUDA), con
  los flags de producción y el payload exacto de `generate_with_tools`.
- **Dos tandas de Needle**: una pasada (`max_steps=1`, sin system prompt) y
  máxima potencia (`max_steps=8`, con el mismo system prompt que recibió Qwen).

**Procedencia del corpus, declarada.** Seis frases salen verbatim de los
comentarios de `services/ai/intent_classifier.py` — casos reales documentados
durante el desarrollo. El resto se escribió para esta prueba a partir de las
`description` y `parameters` reales. **No es tráfico de usuarios**: MolDesign
tiene cero usuarios externos, ese corpus no existe, y fingirlo sería el defecto.

**Límite de resolución.** Con n=21 por celda, el intervalo de confianza ronda los
±17 puntos. Este corpus resuelve diferencias grandes, no pequeñas.

## 4. Resultados

### 4.1 Una pasada por caso (`max_steps=1`)

| pregunta | descripciones | Needle: en alcance | Qwen: en alcance |
|---|---|---:|---:|
| es | es *(el producto hoy)* | **0.0%** | **80.0%** |
| es | en | 26.7% | 93.3% |
| en | es | 20.0% | 86.7% |
| en | en | 6.7% | 93.3% |

No es un problema de idioma: Needle no pasa del 27% en ninguna celda, Qwen no
baja del 80% en ninguna.

### 4.2 Needle a máxima potencia (`max_steps=8` + system prompt)

| | es/es *(producto)* | en/en | Qwen es/es |
|---|---:|---:|---:|
| acierto total | 33.3% | 30.0% | **81.0%** |
| **en alcance** | **1/15** | 4/15 | **12/15** |
| **abstención** | **6/6 (100%)** | 2/5 | 5/6 (83%) |
| falsos positivos | **0/6** | 3/5 | 1/6 |
| ms p50 | **34.276** | 15.386 | **1.237** |
| agotan los 8 pasos | 10/21 | 2/20 | — |

**Dos lecturas, y las dos importan:**

1. **Sabe abstenerse.** Con system prompt, 6/6 y cero falsos positivos — mejor
   que Qwen. Su afirmación de que no alucina fuera de tema **se sostiene**. La
   primera tanda dio 4/6 falsos positivos porque el arnés no le pasaba system
   prompt mientras que a Qwen sí; era un sesgo del arnés, no del modelo.
2. **No sabe enrutar.** 1 de 15. El 33,3% total son seis abstenciones correctas
   más un acierto. Y cuesta 28× la latencia de Qwen, con la mitad de los casos
   agotando el techo de pasos en bucle.

### 4.3 La confianza calibrada

Es la característica que hacía atractivo el motor para MolDesign, y **se
comporta al revés en español**:

| celda | confianza media al **acertar** | al **fallar** |
|---|---:|---:|
| es/es | 0.51 | **0.72** |
| en/en | 0.72 | 0.36 |

En la tanda de una pasada, filtrar por confianza **empeoraba** el acierto en
todos los umbrales: 14.5% sin filtrar → 11.7% con `conf ≥ 0.5`.

Es el mismo patrón por el que [`AGENTS.md`](../AGENTS.md) descarta DiffDock,
cuyo `position_confidence` está anticorrelacionado con la validez física. Un
motor cuya señal de confianza empeora el resultado al usarla no encaja en un
producto cuya propuesta es saber cuándo no confiar.

**La vía de fine-tuning no lo arregla: lo empeora.** El titular del proveedor
(*«fine-tuned 4-layer model passes DeepSeek V4 Flash»*) es sobre modelos
afinados, y la escalera de capas (`needle finetune --layers N`) es una opción de
**entrenamiento**, no de inferencia: no hay parámetro de profundidad en
`Needle(...)` ni en `run(...)`. Y el propio código avisa, `needle/__init__.py:136`:

> *«finetuning does not update the confidence head, so scores are uncalibrated
> for tuned weights; this agent reports confidence as None»*

El base tiene confianza invertida en español; el afinado no tiene confianza. No
hay configuración que dé acierto **y** señal de confianza a la vez.

## 5. Telemetría

Activada por defecto. Se dispara en cada `run()`, `complete()` y `extract()`.

- Destino: `https://vlqqczxwyaodtcdmdmlw.supabase.co/functions/v1/telemetry`
- Carga: evento, id anónimo persistido en `~/.cactus_needle/telemetry_id`,
  versión, motor, SO, arquitectura, versión de Python. **No prompts ni salidas.**
- Hilo demonio, 3 s de timeout, traga excepciones.
- Tres interruptores: `NEEDLE_TELEMETRY=0`, `DO_NOT_TRACK`, `CI`.

**Verificado**: con `NEEDLE_TELEMETRY=0` no se creó `~/.cactus_needle` ni salió
nada.

Si alguna vez se integra, esto sería **un cuarto camino a la red que
`services/ai/consent.py` no ve** — exactamente el defecto que MOLCHAT-NET-006
cerró para el reporte de IA. No bastaría con poner la variable: haría falta una
guarda que lo demuestre, al estilo de las nueve de
`scripts/check_openbabel_boundary.py`. Restricción 2: un guardián tiene que
demostrar que ve.

## 6. Veredicto

**No integrar.** Con 1 de 15 en la condición en que corre el producto, no puede
sustituir ninguna parte de `services/ai/tool_registry.py`.

La hipótesis que motivó la exploración —meter un modelo pequeño en el
instalador— sigue siendo buena. Needle no la cumple: no acierta, y sus 35 MB no
resuelven que el instalador no traiga `.gguf`.

## 7. Lo que quedaría por medir si alguien la reabre

- **Needle como filtro binario de admisión**, no como enrutador. Acertó 6/6
  decidiendo *si* corresponde herramienta, que es una pregunta binaria y no un
  enrutado entre 21 opciones. No se recomienda hoy: 6/6 sobre seis casos no es
  evidencia, 34 s es inviable para un filtro de chat, y Qwen ya da 5/6 gratis
  dentro de la llamada que hará igualmente. El experimento sería 100 casos
  binarios contra la rama `_det_no_tool` del clasificador, con `max_steps=1`.
- **Sus embeddings** para búsqueda semántica sobre las 380 dianas curadas. No se
  midió nada de esto; es capacidad nueva, no reemplazo.
- **Fine-tuning sobre las 21 herramientas.** Requiere las extras `[train]`
  (jax, flax, optax) y datos sintetizados vía OpenRouter — una API de terceros.
  Y renuncia a la confianza. Coste alto, premio dudoso.

## 8. Hallazgo colateral, y NO aplicado

Qwen mejora al traducir al inglés las `description` de las ToolDef, con la
pregunta todavía en español:

| condición | acierto | abstención |
|---|---:|---:|
| pregunta ES, descripciones ES *(hoy)* | 81.0% | 83.3% (1 falso +) |
| pregunta ES, **descripciones EN** | **95.2%** | **100%** (0 falsos +) |

Coste: traducir 21 cadenas. **No aplicado**: con n=21 la diferencia son 3 casos
y el IC es de ±17 puntos. Este corpus no resuelve esa diferencia. Antes de tocar
las descripciones hace falta un corpus mayor — el arnés ya está montado.

## 9. Trampas de método, para la próxima vez

Valen para cualquier motor de tool-calling que se evalúe aquí:

1. **`needle.run()` itera hasta 8 pasos por defecto.** Medir sin fijar
   `max_steps` compara ocho pasadas contra la llamada única de Qwen. Y al revés:
   fijarlo a 1 y llamarlo «máxima potencia» tampoco vale.
2. **El system prompt es parte del trato.** La primera tanda le dio a Qwen un
   system que decía «si ninguna herramienta corresponde, respondé en texto» y a
   Needle no le dio ninguno. Eso convirtió 6/6 abstenciones en 2/6 y produjo un
   resultado falso que llegó a un informe.
3. **La latencia de Needle no es estable**: ~1 s con descripciones en español,
   6–35 s con descripciones en inglés o con el bucle abierto. Un p50 sin decir
   en qué celda se midió no significa nada.

---

## Cómo reproducirlo

```bash
# 1. El brazo de Qwen necesita llama-server con el modelo del producto
tools/llama-cuda/llama-server.exe -m models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --port 8099 -c 8192 -ngl 99 --parallel 1 --no-warmup --no-webui \
    --cont-batching --jinja --cache-type-k q8_0 --cache-type-v q8_0 --cache-ram 256

# 2. Needle va en un venv APARTE. Nunca en el entorno del producto.
python -m venv .venv && .venv/Scripts/pip install cactus-needle
export NEEDLE_TELEMETRY=0 DO_NOT_TRACK=1

# 3. Las tres tandas
python scripts/bench_tool_calling/run_qwen.py
python scripts/bench_tool_calling/run_needle.py      # una pasada, 2x2
python scripts/bench_tool_calling/run_needle_max.py  # max_steps=8 + system
python scripts/bench_tool_calling/analizar.py
```

Los `.json` de `scripts/bench_tool_calling/resultados/` son la medida del
2026-09-20. No son artefactos sellados: rehacerlos es correcto, sobrescribirlos
sin decir con qué versión, no.
