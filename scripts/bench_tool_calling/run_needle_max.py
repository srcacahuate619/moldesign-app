"""Needle 3 a maxima potencia, y con el MISMO trato que recibio Qwen.

Que cambia respecto de `run_needle.py`, y por que:

  1. `max_steps=8` (su default) en vez de 1. La primera tanda forzo una pasada
     para comparar "una llamada contra una llamada". Esa es la comparacion justa
     de coste; esta es la otra pregunta, la de producto: que da cada motor si le
     dejas gastar lo que quiera. En un escritorio el presupuesto existe.

  2. **System prompt.** La primera tanda le paso a Qwen un system que decia
     explicitamente "si ninguna herramienta corresponde, responde en texto sin
     llamar ninguna", y a Needle NO le paso ninguno. Eso sesgaba la columna de
     abstencion a favor de Qwen. Aqui recibe el mismo texto, en el idioma de la
     celda.

  3. `max_new_tokens=512`, igual que el `max_tokens` de Qwen.

Lo que NO se puede tocar en inferencia, comprobado en el paquete: la profundidad
de la escalera. `needle finetune --layers N` elige el peldano al ENTRENAR un
adaptador LoRA; no hay parametro de capas en `Needle(...)` ni en `run(...)`.
`generation` ya era 3 por defecto (`int(generation or 3)`).
"""
import os, json, time, sys

os.environ["NEEDLE_TELEMETRY"] = "0"
os.environ["DO_NOT_TRACK"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import needle
from corpus import CASOS, DESC_EN

AQUI = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(AQUI, "tools_openai.json"), encoding="utf-8"))
OFFLINE = [s for s in SPEC if s["offline"]]

#: Mismo contrato que recibio Qwen en `run_qwen.py`.
SISTEMA = {
    "es": ("Sos el asistente de MolDesign. Usa una herramienta cuando la peticion "
           "lo requiera. Si ninguna herramienta corresponde, responde en texto sin "
           "llamar ninguna."),
    "en": ("You are the MolDesign assistant. Use a tool when the request requires "
           "it. If no tool applies, answer in text without calling any."),
}

_TIPO = {"string": "str", "integer": "int", "number": "float", "boolean": "bool",
         "array": "list", "object": "dict"}
ELEGIDA: list = []

#: Celdas a medir, en orden de importancia: la del producto primero.
CELDAS = [("es", "es"), ("en", "en")]


def construir_tools(idioma_desc):
    fns = []
    for s in OFFLINE:
        f = s["tool"]["function"]
        nombre = f["name"]
        props = f["parameters"]["properties"]
        desc = DESC_EN.get(nombre, f["description"]) if idioma_desc == "en" else f["description"]
        desc = desc.replace('"', "'").replace("\n", " ")
        args = ", ".join(f"{k}: {_TIPO.get(v.get('type','string'),'str')} = None" for k, v in props.items())
        cuerpo = ", ".join(f"'{k}': {k}" for k in props) or ""
        src = (f"def {nombre}({args}):\n"
               f'    "{desc}"\n'
               f"    _rec(('{nombre}', {{{cuerpo}}}))\n"
               f"    return 'ok'\n")
        ns = {"_rec": ELEGIDA.append}
        exec(src, ns)
        fns.append(needle.tool(ns[nombre]))
    return fns


def main():
    ruta = os.path.join(AQUI, "resultados_needle_max.jsonl")
    hechos = set()
    if os.path.exists(ruta):
        for linea in open(ruta, encoding="utf-8"):
            try:
                d = json.loads(linea)
                hechos.add((d["idioma_q"], d["idioma_desc"], d["caso"]))
            except Exception:
                pass
        print(f"reanudando: {len(hechos)} ya medidos", flush=True)
    out = open(ruta, "a", encoding="utf-8")

    for idioma_q, idioma_desc in CELDAS:
        pend = [c for c in CASOS if (idioma_q, idioma_desc, c[0]) not in hechos]
        if not pend:
            continue
        agente = needle.Needle(tools=construir_tools(idioma_desc),
                               system=SISTEMA[idioma_q])
        for cid, q_es, q_en, esperado in pend:
            q = q_es if idioma_q == "es" else q_en
            ELEGIDA.clear()
            t0 = time.perf_counter()
            try:
                r = agente.run(q, max_steps=8, max_new_tokens=512)
            except Exception as e:
                r = {"confidence": None, "peak_ram_mb": None, "prefill_tps": None,
                     "decode_tps": None, "error": f"{type(e).__name__}: {e}"}
            dt = (time.perf_counter() - t0) * 1000
            got = ELEGIDA[0][0] if ELEGIDA else None
            args = ELEGIDA[0][1] if ELEGIDA else {}
            fila = {
                "arm": "needle_max", "caso": cid, "idioma_q": idioma_q,
                "idioma_desc": idioma_desc, "prompt": q, "esperado": esperado,
                "obtenido": got, "acierto_tool": got == esperado,
                "n_llamadas": len(ELEGIDA),
                "args": {k: v for k, v in args.items() if v is not None},
                "ms": round(dt, 1), "confidence": r.get("confidence"),
                "peak_ram_mb": r.get("peak_ram_mb"),
                "prefill_tps": r.get("prefill_tps"), "decode_tps": r.get("decode_tps"),
                "error": r.get("error"),
            }
            out.write(json.dumps(fila, ensure_ascii=False) + "\n")
            out.flush()
            marca = "OK " if fila["acierto_tool"] else "XX "
            print(f"{marca} q={idioma_q} d={idioma_desc} {cid:16s} "
                  f"[{dt:7.0f}ms c={fila['confidence'] or -1:.2f} n={len(ELEGIDA)}] "
                  f"{str(esperado):24s} -> {got}", flush=True)
        agente.close()
    out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
