#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf33ext_moderadores.py — MF-33-EXT-MOD: escenario, replicacion y acierto-vs-dosis.

**Este script se sella ANTES de que `MF-33-EXT` termine.** Su hash queda en
`MF-33-EXT-MOD-PRE`, de modo que las reglas de lectura de abajo son demostrablemente
anteriores a los datos. Sin eso, todo lo que sigue seria post-hoc.

De donde viene
--------------
`MF-33-A3` establecio que la ventaja del ensemble es **diversidad conformacional** y no
conteo de poses, reinicios ni CPU. `MF-33-DOSIS` busco despues un predictor de **cuando**
hace falta el ensemble, sobre los 33 de COLOCACION, y no encontro ninguno: los cinco
prospectivos quedaron en |rho| <= 0.14 y ninguno sobrevivio el FDR. Su MDE declarado era
|rho| >= 0.4711, asi que un efecto moderado quedaba invisible.

`MF-33-EXT` corre el brazo B sobre los **116** de train. Eso da tres cosas que los 33 no
podian dar, y este analisis las usa en bloques separados con reglas distintas.

BLOQUE 1 — ESCENARIO. Un solo conformero contra el ensemble, sobre 116
-----------------------------------------------------------------------
`MF-33-EXT` registra `curva_oraculo`, el oraculo acumulado tras 1..K corridas **en orden de
indice de conformero**. Por construccion, `curva_oraculo[0]` **es** el resultado de un solo
conformero, y el oraculo final es el del ensemble. La comparacion sale sin computo extra y es
pareada por complejo.

    cobertura_single    = fraccion con curva_oraculo[0] <= 2.0 A
    cobertura_ensemble  = fraccion con oraculo final <= 2.0 A
    delta               = ensemble - single, en puntos porcentuales

**TRES LECTURAS ESCRITAS ANTES, con umbrales de 5 y 15 puntos porcentuales:**

  * **ESCENARIO A — EFECTO REAL PERO CONCENTRADO.** `delta` global < 5 pp mientras el delta
    en el estrato dificil es >= 15 pp. El hallazgo de `MF-33` es real y especifico de los
    complejos dificiles. **No justifica regenerar la cohorte universalmente**: el coste se
    pagaria en 116 para cobrar en unas pocas decenas.
  * **ESCENARIO B — EFECTO GENERAL.** `delta` global >= 15 pp. La ventaja no es del estrato
    sino del metodo. **La arquitectura debe cambiar** y la regeneracion queda justificada.
  * **ESCENARIO C — EFECTO GRANDE E IMPREDECIBLE.** `delta` global >= 15 pp **o** un
    subconjunto con delta >= 15 pp, **y** ningun predictor sobrevive los bloques 2 y 3.
    Entonces el ensemble aporta mucho en ciertos sistemas y **no se sabe en cuales antes de
    correr**. Es el escenario que hace atractivo el **muestreo secuencial con criterio de
    parada** en vez de una politica basada en descriptores estaticos.

Cualquier combinacion fuera de esas tres se reporta como **MIXTO** con sus numeros, sin
forzarla a encajar.

BLOQUE 2 — REPLICACION, no descubrimiento
------------------------------------------
Los seis predictores de `MF-33-DOSIS` **ya se miraron** en los 33. Volver a mirarlos en los
116 es **replicacion**, y se declara como tal: no son seis hipotesis virgenes y no se pueden
presentar como si el conjunto fuese nuevo.

Consecuencia practica: se reportan con su `rho`, su p y el FDR, pero **la conclusion se toma
del bloque 3**, no de aqui. Un predictor que aparezca en los 116 y desaparezca en los 68
externos es estructura de la cohorte original filtrandose por los 48 que se solapan.

**Limitacion de cobertura, declarada:** `frac_vuelve` viene de `MF-14`, que solo cubrio 48
complejos. **No tiene version fuera de muestra** y por tanto no puede pasar el bloque 3. Se
reporta en el 2 y se marca; si fuese el unico superviviente, no bastaria.

BLOQUE 3 — FUERA DE MUESTRA. Los 68 que no estaban
---------------------------------------------------
De los 116, **68 no pertenecen a la cohorte de 48** de `MF-33`. Ese subconjunto no se ha
mirado nunca para esta pregunta. Es el unico contraste con valor prospectivo real.

Se aplican los cinco predictores prospectivos, con FDR propio. **La regla de decision del
analisis es esta y no otra**: un predictor solo se declara candidato a politica adaptativa si
sobrevive **aqui**.

BLOQUE 4 — ACIERTO contra DOSIS
--------------------------------
`MF-33-DOSIS` dejo una hipotesis derivada de dos resultados independientes: que el fenomeno no
es de dosis -mas oportunidades, mas espacio conformacional bruto- sino de **acierto**, es
decir, que **basta con que una inicializacion caiga en una region favorable**.

`MF-33-EXT` registra `primer_dock_que_cubre`: el indice de la primera corrida que alcanzo
<= 2.0 A. Eso permite contrastarla directamente, y es la primera vez que se puede.

Si cada conformero acierta de forma **independiente y con la misma probabilidad `p`**, la
cobertura tras `k` corridas sigue `1 - (1 - p)^k` y el primer acierto se distribuye
**geometricamente**. Se estima `p` por maxima verosimilitud sobre los complejos cubiertos y
se compara la curva observada con la predicha.

  * **compatible con ACIERTO (loteria homogenea)** si la curva observada no se separa de la
    geometrica y `primer_dock_que_cubre` no se concentra en 1;
  * **compatible con DOSIS** si la cobertura crece de forma sostenida con `k` por encima de
    lo que predice la geometrica, es decir, si acumular aporta mas que repetir;
  * **HETEROGENEIDAD** si la curva observada se queda **por debajo** de la geometrica: habria
    complejos con `p` cercano a cero que ningun `K` rescata, y la media agregada estaria
    mezclando dos poblaciones.

El tercer caso es interesante por si mismo: seria evidencia de que una parte de los complejos
**no es cuestion de muestreo**, que es justo lo que `MF-33-CRUCES` y `REC-09` sugirieron por
otra via -sistemas mal especificados-.

Limites declarados ANTES de correr
----------------------------------
1. **`curva_oraculo[0]` no es identico al brazo A de `MF-33`.** Aquel uso `conf0.flex.pdbqt`
   con una corrida; aqui es la primera corrida del barrido, mismo conformero y mismos
   parametros. Se espera equivalencia y **se comprueba** en los 48 solapados como control.
2. **El orden de conformeros es por indice, no por calidad.** Es deliberado: elegir el mejor
   seria informacion de oraculo inexistente en produccion. Pero implica que la curva mide
   «cuantas corridas en el orden en que vienen», no «cuantas hacen falta en el mejor orden».
3. Los umbrales de 5 y 15 pp se fijan aqui, antes de ver el resultado, y **no se mueven**.
4. Nada de esto reabre la cantidad primaria de `MF-33-EXT`, que es su cobertura contra el
   liston de 0.90 heredado del G5 de `MF-02D` y esta declarada en `MF-33-EXT-PRE`.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

UMBRAL_A = 2.0
Q_FDR = 0.05
PP_PEQUENO = 5.0     # puntos porcentuales
PP_GRANDE = 15.0

PREDICTORES_PROSPECTIVOS = ["torsdof", "rot_bonds", "n_conformeros", "diversidad", "n_heavy"]
PREDICTOR_NO_PROSPECTIVO = "frac_vuelve"


def _jsonl(p: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _rho_detectable(n: int, alpha: float = 0.05, potencia: float = 0.80) -> Optional[float]:
    if n < 5:
        return None
    from estadistica_fnd04 import _ppf
    return round(math.tanh((_ppf(1 - alpha / 2) + _ppf(potencia)) / math.sqrt(n - 3)), 4)


def _correlar(sub: List[Dict[str, Any]], predictores: List[str], respuesta: str) -> Dict[str, Any]:
    from scipy.stats import spearmanr
    from estadistica_fnd04 import benjamini_hochberg
    res: Dict[str, Any] = {}
    pv, cl = [], []
    for nombre in predictores:
        pares = [(f[nombre], f[respuesta]) for f in sub
                 if f.get(nombre) is not None and f.get(respuesta) is not None]
        if len(pares) < 8 or len({p[0] for p in pares}) < 3:
            res[nombre] = {"n": len(pares), "rho": None, "p": None, "motivo": "n_o_variacion_insuficiente"}
            continue
        rho, p = spearmanr([p[0] for p in pares], [float(p[1]) for p in pares])
        if math.isnan(rho):
            res[nombre] = {"n": len(pares), "rho": None, "p": None, "motivo": "rho_nan"}
            continue
        res[nombre] = {"n": len(pares), "rho": round(float(rho), 4), "p": round(float(p), 6)}
        pv.append(float(p)); cl.append(nombre)
    if pv:
        for k, s in zip(cl, benjamini_hochberg(pv, q=Q_FDR)):
            res[k]["significativo_tras_FDR"] = bool(s)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-33-EXT-MOD: escenario, replicacion, acierto vs dosis")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-EXT-MOD"
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = _jsonl(art / "MF-33-EXT" / "per_complex.jsonl")
    dosis = {r["pid"]: r for r in _jsonl(art / "MF-33-DOSIS" / "per_complex.jsonl")}
    en48 = {r["pid"] for r in _jsonl(art / "MF-33" / "per_complex.jsonl")}

    filas: List[Dict[str, Any]] = []
    for r in ext:
        if r.get("oraculo") is None:
            continue
        curva = r.get("curva_oraculo") or []
        single = curva[0] if curva and curva[0] is not None else None
        f: Dict[str, Any] = {
            "pid": r["pid"], "estrato": r.get("estrato"),
            "en_cohorte_48": r["pid"] in en48,
            "n_conformeros": r.get("n_docks"),
            "oraculo_ensemble": r["oraculo"],
            "oraculo_single": single,
            "cubierto_ensemble": bool(r["oraculo"] <= UMBRAL_A),
            "cubierto_single": bool(single is not None and single <= UMBRAL_A),
            "primer_dock_que_cubre": r.get("primer_dock_que_cubre"),
        }
        f["beneficio_ensemble"] = (round(single - r["oraculo"], 4)
                                   if single is not None else None)
        d = dosis.get(r["pid"], {})
        for k in PREDICTORES_PROSPECTIVOS + [PREDICTOR_NO_PROSPECTIVO]:
            if k == "n_conformeros":
                continue
            f[k] = d.get(k)
        filas.append(f)

    def _cob(sub, campo):
        return (sum(1 for f in sub if f[campo]) / len(sub)) if sub else None

    def _bloque1(sub, etq):
        s, e = _cob(sub, "cubierto_single"), _cob(sub, "cubierto_ensemble")
        return {"etiqueta": etq, "n": len(sub),
                "cobertura_single": round(s, 4) if s is not None else None,
                "cobertura_ensemble": round(e, 4) if e is not None else None,
                "delta_pp": round((e - s) * 100, 2) if (s is not None and e is not None) else None,
                "n_gana_ensemble": sum(1 for f in sub if f["cubierto_ensemble"] and not f["cubierto_single"]),
                "n_gana_single": sum(1 for f in sub if f["cubierto_single"] and not f["cubierto_ensemble"])}

    col = [f for f in filas if f["estrato"] == "COLOCACION"]
    fuera = [f for f in filas if not f["en_cohorte_48"]]
    b1_glob, b1_col = _bloque1(filas, "TODOS"), _bloque1(col, "COLOCACION")

    b2 = _correlar(filas, PREDICTORES_PROSPECTIVOS + [PREDICTOR_NO_PROSPECTIVO], "beneficio_ensemble")
    b3 = _correlar(fuera, PREDICTORES_PROSPECTIVOS, "beneficio_ensemble")
    sobreviven_b3 = sorted(k for k, v in b3.items() if v.get("significativo_tras_FDR"))

    # ── Bloque 4: acierto contra dosis ──
    cub = [f for f in filas if f["cubierto_ensemble"] and f["primer_dock_que_cubre"]]
    Ks = [f["n_conformeros"] for f in filas if f.get("n_conformeros")]
    p_mle = None
    if cub:
        # MLE de la geometrica truncada, aproximada por 1/media del primer acierto
        p_mle = round(len(cub) / sum(f["primer_dock_que_cubre"] for f in cub), 4)
    curva_obs, curva_geo = [], []
    kmax = max(Ks) if Ks else 0
    for k in range(1, kmax + 1):
        n_k = sum(1 for f in filas if (f.get("n_conformeros") or 0) >= k)
        c_k = sum(1 for f in filas if f["primer_dock_que_cubre"] and f["primer_dock_que_cubre"] <= k)
        curva_obs.append({"k": k, "n_con_al_menos_k": n_k, "cubiertos_hasta_k": c_k,
                          "cobertura": round(c_k / len(filas), 4) if filas else None})
        if p_mle:
            curva_geo.append({"k": k, "cobertura_predicha": round(1 - (1 - p_mle) ** k, 4)})
    en_1 = sum(1 for f in cub if f["primer_dock_que_cubre"] == 1)

    escenario = "MIXTO"
    dg, dc = b1_glob["delta_pp"], b1_col["delta_pp"]
    if dg is not None and dc is not None:
        if dg >= PP_GRANDE and not sobreviven_b3:
            escenario = "C_EFECTO_GRANDE_E_IMPREDECIBLE"
        elif dg >= PP_GRANDE:
            escenario = "B_EFECTO_GENERAL"
        elif dg < PP_PEQUENO and dc >= PP_GRANDE:
            escenario = ("C_EFECTO_GRANDE_E_IMPREDECIBLE" if not sobreviven_b3
                         else "A_EFECTO_REAL_PERO_CONCENTRADO")

    salida = {
        "analisis_id": "MF-33-EXT-MOD",
        "tipo": "analisis preregistrado ANTES de que MF-33-EXT cerrara; hash sellado en MF-33-EXT-MOD-PRE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_complejos": len(filas),
        "n_fuera_de_muestra": len(fuera),
        "BLOQUE_1_ESCENARIO": {"global": b1_glob, "colocacion": b1_col,
                               "umbrales_pp": {"pequeno": PP_PEQUENO, "grande": PP_GRANDE},
                               "escenario_leido": escenario},
        "BLOQUE_2_REPLICACION": {
            "advertencia": "REPLICACION, no descubrimiento: estos seis ya se miraron en los 33 de "
                           "MF-33-DOSIS. La conclusion se toma del bloque 3.",
            "mde_rho": _rho_detectable(len(filas)), "resultados": b2},
        "BLOQUE_3_FUERA_DE_MUESTRA": {
            "n": len(fuera),
            "nota": "los 68 que no estan en la cohorte de 48; unico contraste con valor prospectivo",
            "mde_rho": _rho_detectable(len(fuera)),
            "resultados": b3, "sobreviven_FDR": sobreviven_b3,
            "frac_vuelve_excluido": "MF-14 solo cubrio 48 complejos: no tiene version fuera de muestra"},
        "BLOQUE_4_ACIERTO_VS_DOSIS": {
            "n_cubiertos_con_indice": len(cub),
            "p_estimada_por_conformero": p_mle,
            "primer_acierto_en_la_corrida_1": en_1,
            "frac_primer_acierto_en_1": round(en_1 / len(cub), 4) if cub else None,
            "curva_observada": curva_obs[:30],
            "curva_geometrica_predicha": curva_geo[:30],
            "como_leerlo": "si la observada no se separa de la geometrica -> ACIERTO (loteria); "
                           "si crece sostenidamente por encima -> DOSIS; si se queda por debajo -> "
                           "HETEROGENEIDAD, hay complejos con p~0 que ningun K rescata"},
        "limites_declarados": [
            "curva_oraculo[0] no es identico al brazo A de MF-33; se comprueba en los 48 solapados",
            "el orden de conformeros es por indice y no por calidad, a proposito",
            "los umbrales de 5 y 15 pp se fijaron antes de ver el resultado y no se mueven",
            "no reabre la cantidad primaria de MF-33-EXT, declarada en MF-33-EXT-PRE",
        ],
        "per_complex": filas,
    }
    (out_dir / "metrics.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    print(f"[MF-33-EXT-MOD] n={len(filas)} (fuera de muestra {len(fuera)})")
    print(f"  BLOQUE 1  global: single={b1_glob['cobertura_single']} ensemble={b1_glob['cobertura_ensemble']} "
          f"delta={b1_glob['delta_pp']} pp")
    print(f"            COLOCACION: single={b1_col['cobertura_single']} ensemble={b1_col['cobertura_ensemble']} "
          f"delta={b1_col['delta_pp']} pp")
    print(f"            ESCENARIO: {escenario}")
    print(f"  BLOQUE 3  sobreviven FDR fuera de muestra: {sobreviven_b3 or 'NINGUNO'} (MDE rho={_rho_detectable(len(fuera))})")
    print(f"  BLOQUE 4  p por conformero={p_mle}  primer acierto en corrida 1: {en_1}/{len(cub)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
