"""Arm B: Qwen2.5-1.5B-Instruct via llama-server, function calling nativo.

Replica el payload exacto de `local_llm.generate_with_tools`: mismas 21
herramientas offline, mismo `max_tokens=512`, misma `temperature=0.1`, mismo
`/v1/chat/completions`. Mismo corpus y mismo diseño 2x2 que el brazo de Needle.

Una llamada por caso — igual que el producto, e igual que `max_steps=1` en Needle.
"""
import os, json, time, copy, sys
import httpx

from corpus import CASOS, DESC_EN

AQUI = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("LLAMA_URL", "http://127.0.0.1:8099")
MODELO = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

SPEC = json.load(open(os.path.join(AQUI, "tools_openai.json"), encoding="utf-8"))
OFFLINE = [s["tool"] for s in SPEC if s["offline"]]

SISTEMA = ("Sos el asistente de MolDesign. Usá una herramienta cuando la petición "
           "lo requiera. Si ninguna herramienta corresponde, respondé en texto sin "
           "llamar ninguna.")


def tools_para(idioma_desc: str):
    if idioma_desc == "es":
        return OFFLINE
    out = copy.deepcopy(OFFLINE)
    for t in out:
        n = t["function"]["name"]
        if n in DESC_EN:
            t["function"]["description"] = DESC_EN[n]
    return out


def main():
    filas = []
    with httpx.Client(timeout=httpx.Timeout(300.0, connect=2.0)) as cli:
        for idioma_desc in ("es", "en"):
            tools = tools_para(idioma_desc)
            for idioma_q in ("es", "en"):
                for cid, q_es, q_en, esperado in CASOS:
                    q = q_es if idioma_q == "es" else q_en
                    t0 = time.perf_counter()
                    got, args, err = None, {}, None
                    try:
                        r = cli.post(f"{URL}/v1/chat/completions", json={
                            "model": MODELO,
                            "messages": [{"role": "system", "content": SISTEMA},
                                         {"role": "user", "content": q}],
                            "tools": tools,
                            "max_tokens": 512,
                            "temperature": 0.1,
                            "stream": False,
                        })
                        r.raise_for_status()
                        msg = r.json()["choices"][0]["message"]
                        tcs = msg.get("tool_calls") or []
                        if tcs:
                            fn = tcs[0].get("function", {})
                            got = fn.get("name")
                            try:
                                args = json.loads(fn.get("arguments", "{}"))
                            except json.JSONDecodeError:
                                args = {"_raw": fn.get("arguments", "")}
                    except Exception as e:
                        err = f"{type(e).__name__}: {str(e)[:120]}"
                    dt = (time.perf_counter() - t0) * 1000
                    fila = {
                        "arm": "qwen1.5b", "caso": cid, "idioma_q": idioma_q,
                        "idioma_desc": idioma_desc, "prompt": q,
                        "esperado": esperado, "obtenido": got,
                        "acierto_tool": got == esperado,
                        "args": args, "ms": round(dt, 1),
                        "confidence": None, "error": err,
                    }
                    filas.append(fila)
                    marca = "OK " if fila["acierto_tool"] else "XX "
                    print(f"{marca} q={idioma_q} d={idioma_desc} {cid:16s} "
                          f"[{dt:6.0f}ms] {str(esperado):24s} -> {got}", flush=True)

    salida = os.path.join(AQUI, "resultados_qwen.json")
    json.dump(filas, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{len(filas)} filas -> {salida}")


if __name__ == "__main__":
    sys.exit(main())
