"""Aplica los criterios de REGISTRO_PREVIO.md a e1.jsonl, e2.jsonl y e3.jsonl, tal como quedaron escritos.

    python docs/auditorias/elevacion-grandes-2026-10-24/resumen.py
"""
from __future__ import annotations

import json
import pathlib
import statistics as st

AQUI = pathlib.Path(__file__).resolve().parent


def leer(nombre):
    return [json.loads(l) for l in open(AQUI / nombre, encoding="utf-8")]


def legible(d):
    return d["cruces"] == 0 and d["solapes"] == 0


def e1():
    filas = leer("e1.jsonl")
    print("== E1")
    for conj in ("G37", "O167"):
        sub = [f for f in filas if f["conjunto"] == conj]
        for g in ("proxy_de_pose", "elegido"):
            normal_abst = sum(f[g]["razon_normal"] > 1 for f in sub)
            aj_abst = sum(f[g]["razon_ajustado"] > 1 for f in sub)
            print(f"  {conj} {g}: se abstienen normal {normal_abst}/{len(sub)}, ajustado {aj_abst}/{len(sub)}; "
                  f"razón mediana normal {st.median(f[g]['razon_normal'] for f in sub):.2f}, "
                  f"ajustado {st.median(f[g]['razon_ajustado'] for f in sub):.2f}; "
                  f"legibles normal {sum(legible(f['normal']) for f in sub)}, ajustado {sum(legible(f[g]) for f in sub)}")
    g = [f for f in filas if f["conjunto"] == "G37"]
    abst = [f for f in g if f["proxy_de_pose"]["razon_normal"] > 1]
    rescatadas = [f for f in abst if f["proxy_de_pose"]["razon_ajustado"] <= 1]
    leg = [f for f in rescatadas if legible(f["proxy_de_pose"])]
    c1 = len(abst) and len(rescatadas) / len(abst) >= 0.75
    c2 = len(rescatadas) and len(leg) / len(rescatadas) >= 0.75
    print(f"  respaldo: {len(rescatadas)}/{len(abst)} rescatadas ({'≥' if c1 else '<'} 75 %), "
          f"{len(leg)}/{len(rescatadas)} legibles ({'≥' if c2 else '<'} 75 %) -> {'GO' if c1 and c2 else 'NO_GO'}")
    leg_n = sum(legible(f["normal"]) for f in filas)
    leg_a = sum(legible(f["proxy_de_pose"]) for f in filas)
    ab_n = sum(f["proxy_de_pose"]["razon_normal"] > 1 for f in filas)
    ab_a = sum(f["proxy_de_pose"]["razon_ajustado"] > 1 for f in filas)
    defecto = c1 and c2 and leg_a >= 0.9 * leg_n and ab_a <= ab_n
    print(f"  por defecto (G37 ∪ O167): legibles normal {leg_n}, ajustado {leg_a} (≥ 0,9·{leg_n} = {0.9 * leg_n:.0f}?); "
          f"abstienen normal {ab_n}, ajustado {ab_a} -> {'GO' if defecto else 'NO_GO'}")
    cruces = [f["proxy_de_pose"]["cruces"] for f in g]
    solapes = [f["proxy_de_pose"]["solapes"] for f in g]
    print(f"  G37 ajustado (proxy): cruces mediana {st.median(cruces)}, máx {max(cruces)}; solapes mediana {st.median(solapes)}, máx {max(solapes)}")


def e2():
    filas = leer("e2.jsonl")
    m = st.median(f["delta_mmff"] for f in filas)
    a = st.median(f["delta_alpb"] for f in filas)
    g = st.median(f["delta_gas"] for f in filas)
    veredicto = "MMFF exagera" if a <= 0.5 * m else "se sostiene" if a >= 0.8 * m else "parcial"
    print("== E2")
    print(f"  ΔE mediana: MMFF {m:.1f}, xTB-ALPB {a:.1f} ({a / m:.2f}·MMFF), xTB gas {g:.1f} kcal/mol -> {veredicto}")
    print(f"  ρ Spearman MMFF/ALPB mediana {st.median(f['spearman_mmff_alpb'] for f in filas):.2f}; "
          f"ALPB > 5: {sum(f['delta_alpb'] > 5 for f in filas)}/37, > 10: {sum(f['delta_alpb'] > 10 for f in filas)}/37; "
          f"xTB fallidos {sum(f['xtb_fallidos'] for f in filas)}")


def e3():
    filas = leer("e3.jsonl")
    print("== E3")
    restr = [f for f in filas if f["restringida"]]
    fallidas = [f for f in restr if f["razon_e3"] is None]
    print(f"  restringidas {len(restr)}/37; sin ningún embebido {len(fallidas)}; semillas fallidas {sum(f['fallos_e3'] for f in restr)}")
    # Una molécula que E3 no puede embeber se queda como el producto (no se puede usar): cuenta con su razón del producto.
    razon = [f["razon_e3"] if f["razon_e3"] is not None else f["razon_producto"] for f in filas]
    delta3 = [f["delta_e3"] if f["delta_e3"] is not None else f["delta_producto"] for f in filas]
    abst_p = sum(f["razon_producto"] > 1 for f in filas)
    abst_3 = sum(r > 1 for r in razon)
    dp, d3 = st.median(f["delta_producto"] for f in filas), st.median(delta3)
    tp = st.median(f["segundos_producto"] for f in filas)
    t3 = st.median(f["segundos_e3"] for f in filas if f["razon_e3"] is not None)
    go = abst_3 <= 4 and d3 - dp <= 2 and t3 <= 1.5 * tp
    print(f"  abstienen producto {abst_p}/37, E3 {abst_3}/37; ΔE mediana producto {dp:.1f}, E3 {d3:.1f} "
          f"(referencia unida); tiempo mediano producto {tp:.1f} s, E3 {t3:.1f} s -> {'GO' if go else 'NO_GO'}")


if __name__ == "__main__":
    e1()
    e2()
    e3()
