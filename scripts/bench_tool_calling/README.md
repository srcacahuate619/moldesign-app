# Arnés de comparación de motores de tool-calling

Mide un motor de llamada a herramientas contra el que MolChat usa hoy
(Qwen2.5-1.5B-Instruct Q4_K_M), sobre las **21 herramientas offline reales** de
`backend/services/ai/tool_registry.py`.

La medida del 2026-09-20 —Needle 3 de Cactus Compute— está en
[`docs/88_EXPLORACION_NEEDLE_3.md`](../../docs/88_EXPLORACION_NEEDLE_3.md).
Los `.json` de `resultados/` son esa medida.

```
corpus.py            21 casos (15 en alcance, 6 fuera), pareja ES/EN
tools_openai.json    las 21 ToolDef reales via to_openai_tool()
run_qwen.py          Qwen por llama-server, payload de generate_with_tools
run_needle.py        Needle, una pasada (max_steps=1), 2x2 de idioma
run_needle_max.py    Needle, max_steps=8 + system prompt equivalente
analizar.py          tablas por celda, falsos positivos, calibración
resultados/          la medida del 2026-09-20
```

## Las cuatro métricas, y cuál decide

1. **Acierto en alcance** — de 15 peticiones que sí corresponden a una
   herramienta, ¿cuántas veces elige la correcta?
2. **Abstención** — de 6 peticiones fuera de alcance, ¿cuántas veces NO llama a
   nada? **Ésta es la que decide.** Es la que el clasificador determinista no
   puede dar y la que un motor confiadamente equivocado arruina.
3. **Falsos positivos** — llamar a una herramienta en una petición fuera de
   alcance. El peor fallo: `compute_properties(smiles='Madrid')` manda basura a
   RDKit.
4. **Calibración** — ¿la confianza separa acierto de fallo? Si filtrar por
   confianza alta no mejora el acierto, la señal no sirve, y eso descalifica al
   motor para este producto.

## Reglas para no repetir errores ya cometidos

**Igualdad de trato o el número no vale.** Si un brazo recibe system prompt, el
otro también, con el mismo texto y en el mismo idioma. La primera tanda contra
Needle le dio system prompt a Qwen y no a Needle; eso convirtió 6/6 abstenciones
en 2/6 y produjo un falso resultado que llegó a un informe.

**Declara el presupuesto de pasos.** `needle.run()` itera hasta 8 pasos por
defecto; una llamada de `chat_with_tools` es una. Mide las dos cosas —una pasada
contra una pasada, y máximo contra máximo— y di cuál es cuál.

**El corpus no es tráfico real.** MolDesign tiene cero usuarios externos. Seis
frases salen verbatim de los comentarios de `intent_classifier.py`; el resto se
escribió a partir de las `description` reales. Está declarado en `corpus.py` y
tiene que seguir estándolo.

**n=21 resuelve diferencias grandes, no pequeñas.** El intervalo ronda ±17
puntos. Un 0% contra un 80% es concluyente; un 81% contra un 95% no lo es. Si
hace falta resolver lo segundo, amplía el corpus antes de concluir.

**El motor a evaluar va en un venv aparte.** Nunca en el entorno del producto.
Y si trae telemetría, se apaga **antes** del primer import y se verifica que no
escribió ni envió nada.

## Uso

```bash
# Qwen necesita llama-server levantado con el modelo del producto
tools/llama-cuda/llama-server.exe -m models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --port 8099 -c 8192 -ngl 99 --parallel 1 --no-warmup --no-webui \
    --cont-batching --jinja --cache-type-k q8_0 --cache-type-v q8_0 --cache-ram 256

python scripts/bench_tool_calling/run_qwen.py
python scripts/bench_tool_calling/analizar.py
```

Regenerar `tools_openai.json` cuando cambien las herramientas:

```bash
PYTHONPATH=backend python -c "
import json, importlib
from services.ai.tool_registry import get_tool_registry
r = get_tool_registry()
for m in ['admet_tools','analog_tools','docking_tools','evaluation_tools',
          'molgraph_tool','rdkit_tools','session_tools','suggest_tools','web_tools']:
    mod = importlib.import_module(f'services.ai.tools.{m}')
    fn = next((getattr(mod,n) for n in dir(mod) if n.startswith('register')), None)
    if fn: fn()
json.dump([{'tool': t.to_openai_tool(), 'offline': t.offline, 'category': t.category}
           for t in r.list_all()],
          open('scripts/bench_tool_calling/tools_openai.json','w',encoding='utf-8'),
          ensure_ascii=False, indent=1)
"
```

Los scripts de Needle necesitan `pip install cactus-needle` en su venv y
`NEEDLE_TELEMETRY=0` en el entorno.
