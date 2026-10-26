"""Cualquier GGUF servido por llama-server, con el payload de `local_llm.generate_with_tools`.

Generaliza `run_qwen.py` (que queda como la medida del 2026-09-20):

  - modelo, brazo y salida por variables de entorno;
  - `chat_template_kwargs = {"enable_thinking": false}`, como el producto desde
    `a095478c` (Qwen3.5 piensa por defecto y se comía el presupuesto de tokens);
  - `PRESELECCION`: un JSON {"<caso>|<idioma_q>|<idioma_desc>": ["tool", ...]} con
    las herramientas que se le pasan en cada caso. Sin él, las 21.
  - `FRIO=1`: `cache_prompt=false`, para medir el primer turno de una sesión (el
    prompt entero se procesa cada vez). Sin él, la caché de prefijo actúa como en
    una sesión ya abierta.

Uso:
  LLAMA_URL=http://127.0.0.1:8411 MODELO=x.gguf ARM=x SALIDA=res.json python run_llama.py
"""
import copy
import json
import os
import sys
import time

import httpx

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import importlib  # noqa: E402

#: `CORPUS=corpus_preparacion` y `SPEC=tools_openai_22.json` para medir con la herramienta 22.
_corpus = importlib.import_module(os.environ.get("CORPUS", "corpus"))
CASOS, DESC_EN = _corpus.CASOS, _corpus.DESC_EN
from run_qwen import SISTEMA  # noqa: E402  mismo system prompt que la medida de referencia

URL = os.environ.get("LLAMA_URL", "http://127.0.0.1:8411")
MODELO = os.environ.get("MODELO", "modelo.gguf")
ARM = os.environ.get("ARM", MODELO)
SALIDA = os.environ["SALIDA"]
FRIO = os.environ.get("FRIO") == "1"
PRESELECCION = json.load(open(os.environ["PRESELECCION"], encoding="utf-8")) if os.environ.get("PRESELECCION") else None
IDIOMAS = [x for x in os.environ.get("IDIOMAS", "es:es,es:en,en:es,en:en").split(",")]
#: Subconjunto de casos (ids separados por comas): el turno en frío con las 21
#: herramientas tarda ~30 s en CPU, y la latencia depende sobre todo del largo del prompt.
SOLO = set(os.environ["SOLO"].split(",")) if os.environ.get("SOLO") else None

SPEC = json.load(open(os.environ.get("SPEC") or os.path.join(AQUI, "tools_openai.json"), encoding="utf-8"))
OFFLINE = [s["tool"] for s in SPEC if s["offline"]]


def tools_para(idioma_desc: str) -> list[dict]:
    if idioma_desc == "es":
        return OFFLINE
    out = copy.deepcopy(OFFLINE)
    for t in out:
        n = t["function"]["name"]
        if n in DESC_EN:
            t["function"]["description"] = DESC_EN[n]
    return out


def main() -> int:
    filas = []
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=2.0)) as cli:
        for par in IDIOMAS:
            idioma_q, idioma_desc = par.split(":")
            todas = tools_para(idioma_desc)
            for cid, q_es, q_en, esperado in CASOS:
                if SOLO is not None and cid not in SOLO:
                    continue
                q = q_es if idioma_q == "es" else q_en
                tools = todas
                if PRESELECCION is not None:
                    nombres = PRESELECCION[f"{cid}|{idioma_q}|{idioma_desc}"]
                    tools = [t for t in todas if t["function"]["name"] in nombres]
                t0 = time.perf_counter()
                got, args, err, tiempos = None, {}, None, {}
                try:
                    r = cli.post(f"{URL}/v1/chat/completions", json={
                        "model": MODELO,
                        "messages": [{"role": "system", "content": SISTEMA},
                                     {"role": "user", "content": q}],
                        "tools": tools,
                        "max_tokens": 512,
                        "temperature": 0.1,
                        "stream": False,
                        "chat_template_kwargs": {"enable_thinking": False},
                        "cache_prompt": not FRIO,
                    })
                    r.raise_for_status()
                    cuerpo = r.json()
                    tiempos = cuerpo.get("timings") or {}
                    msg = cuerpo["choices"][0]["message"]
                    tcs = msg.get("tool_calls") or []
                    if tcs:
                        fn = tcs[0].get("function", {})
                        got = fn.get("name")
                        try:
                            args = json.loads(fn.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {"_raw": fn.get("arguments", "")}
                except Exception as e:  # noqa: BLE001
                    err = f"{type(e).__name__}: {str(e)[:120]}"
                dt = (time.perf_counter() - t0) * 1000
                fila = {
                    "arm": ARM, "caso": cid, "idioma_q": idioma_q, "idioma_desc": idioma_desc,
                    "prompt": q, "esperado": esperado, "obtenido": got,
                    "acierto_tool": got == esperado, "args": args, "ms": round(dt, 1),
                    "n_tools": len(tools), "prompt_n": tiempos.get("prompt_n"),
                    "prompt_ms": tiempos.get("prompt_ms"), "confidence": None, "error": err,
                }
                filas.append(fila)
                marca = "OK " if fila["acierto_tool"] else "XX "
                print(f"{marca} q={idioma_q} d={idioma_desc} {cid:16s} [{dt:7.0f}ms tools={len(tools):2d}] "
                      f"{str(esperado):24s} -> {got}", flush=True)
    json.dump(filas, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{len(filas)} filas -> {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
