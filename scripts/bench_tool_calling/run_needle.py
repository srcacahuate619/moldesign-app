"""Arm C: Needle 3 sobre las 21 herramientas offline reales de MolDesign.

Diseño 2x2 para aislar el idioma:
    idioma de la PREGUNTA (es/en)  x  idioma de la DESCRIPCION (es/en)

`max_steps=1`: `run()` por defecto itera hasta 8 pasos, lo que compararia 8
pasadas del modelo contra la llamada UNICA que hace `chat_with_tools` de Qwen.
Una pasada contra una pasada.
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

_TIPO = {"string": "str", "integer": "int", "number": "float", "boolean": "bool",
         "array": "list", "object": "dict"}
ELEGIDA: list = []


def construir_tools(idioma_desc: str):
    """Genera funciones decoradas con @needle.tool desde el spec real."""
    ELEGIDA.clear()
    fns = []
    for s in OFFLINE:
        f = s["tool"]["function"]
        nombre = f["name"]
        props = f["parameters"]["properties"]
        desc = DESC_EN.get(nombre, f["description"]) if idioma_desc == "en" else f["description"]
        desc = desc.replace('"', "'").replace("\n", " ")
        args = ", ".join(f"{k}: {_TIPO.get(v.get('type','string'),'str')} = None" for k, v in props.items())
        cuerpo = ", ".join(f"'{k}': {k}" for k in props) or ""
        src = (
            f"def {nombre}({args}):\n"
            f'    "{desc}"\n'
            f"    _rec(('{nombre}', {{{cuerpo}}}))\n"
            f"    return 'ok'\n"
        )
        ns = {"_rec": ELEGIDA.append}
        exec(src, ns)
        fns.append(needle.tool(ns[nombre]))
    return fns


def main():
    filas = []
    # Escritura incremental: una fila por linea, vaciada al disco en el acto.
    # Si esto se mata a media tanda, lo medido hasta ahi sigue siendo medido.
    # Reanudable: lo ya medido no se vuelve a medir.
    ruta_jsonl = os.path.join(AQUI, "resultados_needle.jsonl")
    hechos = set()
    if os.path.exists(ruta_jsonl):
        for linea in open(ruta_jsonl, encoding="utf-8"):
            try:
                d = json.loads(linea)
                hechos.add((d["idioma_q"], d["idioma_desc"], d["caso"]))
                filas.append(d)
            except Exception:
                pass
        print(f"reanudando: {len(hechos)} casos ya medidos")
    jsonl = open(ruta_jsonl, "a", encoding="utf-8")
    for idioma_desc in ("es", "en"):
        tools = construir_tools(idioma_desc)
        agente = needle.Needle(tools=tools)
        for idioma_q in ("es", "en"):
            for cid, q_es, q_en, esperado in CASOS:
                if (idioma_q, idioma_desc, cid) in hechos:
                    continue
                q = q_es if idioma_q == "es" else q_en
                ELEGIDA.clear()
                t0 = time.perf_counter()
                try:
                    r = agente.run(q, max_steps=1)
                except Exception as e:
                    r = {"confidence": None, "peak_ram_mb": None,
                         "prefill_tps": None, "decode_tps": None,
                         "error": f"{type(e).__name__}: {e}"}
                dt = (time.perf_counter() - t0) * 1000
                got = ELEGIDA[0][0] if ELEGIDA else None
                args = ELEGIDA[0][1] if ELEGIDA else {}
                fila = {
                    "arm": "needle", "caso": cid, "idioma_q": idioma_q,
                    "idioma_desc": idioma_desc, "prompt": q,
                    "esperado": esperado, "obtenido": got,
                    "acierto_tool": got == esperado,
                    "args": {k: v for k, v in args.items() if v is not None},
                    "ms": round(dt, 1),
                    "confidence": r.get("confidence"),
                    "peak_ram_mb": r.get("peak_ram_mb"),
                    "prefill_tps": r.get("prefill_tps"),
                    "decode_tps": r.get("decode_tps"),
                    "error": r.get("error"),
                }
                filas.append(fila)
                jsonl.write(json.dumps(fila, ensure_ascii=False) + "\n")
                jsonl.flush()
                marca = "OK " if fila["acierto_tool"] else "XX "
                print(f"{marca} q={idioma_q} d={idioma_desc} {cid:16s} "
                      f"[{dt:6.0f}ms c={fila['confidence'] or -1:.2f}] "
                      f"{str(esperado):24s} -> {got}", flush=True)
        agente.close()

    jsonl.close()
    salida = os.path.join(AQUI, "resultados_needle.json")
    json.dump(filas, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{len(filas)} filas -> {salida}")


if __name__ == "__main__":
    sys.exit(main())
