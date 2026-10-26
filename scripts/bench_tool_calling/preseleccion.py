"""¿Queda la herramienta correcta entre las k que un modelo de embeddings pondría primero?

La hipótesis: pasar al modelo de chat sólo las k herramientas más parecidas a la
petición en vez de las 21 acorta el prompt (el primer turno en CPU tarda 35 s con
Qwen2.5-1.5B y 76 s con Qwen3.5-4B, medido el 2026-10-10) sin perder la correcta.
Si la correcta queda fuera, el modelo ya no puede elegirla: el número que decide
es el recall@k, no la similitud media.

Necesita un llama-server con `--embedding` y el pooling del modelo:
  Qwen3-Embedding:   --pooling last
  multilingual-e5:   --pooling mean

Uso:
  EMB_URL=http://127.0.0.1:8421 EMB=qwen3 SALIDA=r.json [K_PRESEL=5 PRESEL=p.json] python preseleccion.py

Escribe el recall@1/3/5 por idioma y, con PRESEL, el mapa que `run_llama.py` usa
para pasar sólo las k primeras (`PRESELECCION`).
"""
import json
import math
import os
import sys
import time

import httpx

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from corpus import CASOS, DESC_EN  # noqa: E402
from corpus_ampliado import PARAFRASIS  # noqa: E402

URL = os.environ.get("EMB_URL", "http://127.0.0.1:8421")
EMB = os.environ["EMB"]  # "qwen3" | "e5"
SALIDA = os.environ["SALIDA"]
K_PRESEL = int(os.environ.get("K_PRESEL", "5"))
PRESEL = os.environ.get("PRESEL")

SPEC = json.load(open(os.path.join(AQUI, "tools_openai.json"), encoding="utf-8"))
OFFLINE = [s["tool"] for s in SPEC if s["offline"]]

#: Formato de cada modelo, el de sus fichas: e5 exige los prefijos «query:» y
#: «passage:»; Qwen3-Embedding pide una instrucción en la consulta y nada en el
#: documento.
TAREA_QWEN = "Given a user request to a chemistry assistant, retrieve the tool that fulfills it"


def consulta(q: str) -> str:
    return f"Instruct: {TAREA_QWEN}\nQuery:{q}" if EMB == "qwen3" else f"query: {q}"


def documento(nombre: str, desc: str) -> str:
    texto = f"{nombre}: {desc}"
    return texto if EMB == "qwen3" else f"passage: {texto}"


def embeber(cli: httpx.Client, textos: list[str]) -> list[list[float]]:
    r = cli.post(f"{URL}/v1/embeddings", json={"input": textos, "model": EMB})
    r.raise_for_status()
    datos = sorted(r.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in datos]


def coseno(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def main() -> int:
    consultas = []  # (caso, idioma_q, frase, esperado, origen)
    esperado_de = {cid: esp for cid, _, _, esp in CASOS}
    for cid, q_es, q_en, esp in CASOS:
        consultas.append((cid, "es", q_es, esp, "corpus"))
        consultas.append((cid, "en", q_en, esp, "corpus"))
    for cid, idioma, frase in PARAFRASIS:
        consultas.append((cid, idioma, frase, esperado_de[cid], "parafrasis"))

    filas, presel = [], {}
    with httpx.Client(timeout=httpx.Timeout(300.0, connect=2.0)) as cli:
        for idioma_desc in ("es", "en"):
            nombres = [t["function"]["name"] for t in OFFLINE]
            descs = [DESC_EN.get(n, t["function"]["description"]) if idioma_desc == "en" else t["function"]["description"]
                     for n, t in zip(nombres, OFFLINE)]
            v_tools = embeber(cli, [documento(n, d) for n, d in zip(nombres, descs)])
            t0 = time.perf_counter()
            v_q = embeber(cli, [consulta(q) for _, _, q, _, _ in consultas])
            ms_por_consulta = (time.perf_counter() - t0) * 1000 / len(consultas)
            for (cid, idioma_q, q, esp, origen), v in zip(consultas, v_q):
                orden = sorted(zip(nombres, (coseno(v, t) for t in v_tools)), key=lambda x: -x[1])
                ranking = [n for n, _ in orden]
                filas.append({
                    "emb": EMB, "caso": cid, "idioma_q": idioma_q, "idioma_desc": idioma_desc, "origen": origen,
                    "consulta": q, "esperado": esp, "rango": (ranking.index(esp) + 1) if esp else None,
                    "top5": ranking[:5], "sim_top1": round(orden[0][1], 4),
                })
                if origen == "corpus":
                    presel[f"{cid}|{idioma_q}|{idioma_desc}"] = ranking[:K_PRESEL]
            print(f"desc={idioma_desc}: {len(consultas)} consultas, {ms_por_consulta:.0f} ms/consulta (lote)")

    for idioma_desc in ("es", "en"):
        for idioma_q in ("es", "en"):
            sub = [f for f in filas if f["esperado"] and f["idioma_desc"] == idioma_desc and f["idioma_q"] == idioma_q]
            r = {k: sum(1 for f in sub if f["rango"] <= k) for k in (1, 3, 5)}
            print(f"q={idioma_q} desc={idioma_desc} n={len(sub):3d}  recall@1={r[1]:3d} ({100*r[1]/len(sub):5.1f}%)  "
                  f"@3={r[3]:3d} ({100*r[3]/len(sub):5.1f}%)  @5={r[5]:3d} ({100*r[5]/len(sub):5.1f}%)")
    json.dump(filas, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if PRESEL:
        json.dump(presel, open(PRESEL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
