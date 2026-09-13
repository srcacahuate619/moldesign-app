#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf33ord_permutaciones.py — MF-33-ORD: ¿la desviación era el orden?

**Re-análisis puro. Cero cómputo de docking.**

El confusor que resuelve
------------------------
`MF-33-EXT-MOD` midió que la distribución del primer acierto se desvía de una geométrica
homogénea (chi2=11.04, gl=3, p=0.026), y que **la mayor contribución al rechazo es el exceso
en k=1** — 80 observados contra 64.9 esperados.

Eso admite dos explicaciones que aquel análisis **no podía separar**:

  * **HETEROGENEIDAD ENTRE COMPLEJOS**: distinta `p_i` por complejo;
  * **ORDEN NO INTERCAMBIABLE**: `conf0` es el primer confórmero de ETKDG y puede ser
    sistemáticamente mejor que uno al azar, produciendo el exceso en k=1 **sin ninguna
    heterogeneidad**.

Por qué se puede resolver sin recomputar
-----------------------------------------
`MF-33-EXT` guarda el `rmsd_min` de **cada confórmero por separado** en `corridas[]`, para los
116 complejos. Cada confórmero se dockeó **independientemente**, con la misma semilla, así que
su resultado **no depende del orden**. El orden sólo afecta al **mínimo acumulado** y, por
tanto, al índice del primer acierto.

Permutar el orden es entonces una **re-lectura exacta** de los mismos datos, no una simulación
ni una aproximación.

Tres contrastes
---------------
**(1) ¿Es `conf0` especial?** Para cada complejo, el **rango** de `conf0` entre sus K
confórmeros ordenados por `rmsd_min`. Bajo intercambiabilidad ese rango es **uniforme**, y su
valor esperado es `(K+1)/2`. Se contrasta el rango normalizado medio contra 0.5.

**(2) ¿Sobrevive la desviación al randomizar el orden?** Se permuta el orden de los K
confórmeros de cada complejo, se recalcula el primer acierto y se recalcula el mismo chi2
contra la geométrica homogénea. `B` permutaciones dan la **distribución nula del chi2 bajo
orden intercambiable**.

  * si el chi2 observado (11.04) queda **en la cola alta** de esa distribución -> la desviación
    la produce **el orden**, y la heterogeneidad no hace falta para explicarla;
  * si los chi2 permutados son **igual de grandes** -> la desviación **sobrevive** al orden y
    es atribuible a diferencias entre complejos.

**(3) Invariancia de `C11`.** El conjunto de complejos **nunca cubiertos** es invariante bajo
permutación por construcción —un complejo cubierto por algún confórmero lo está en cualquier
orden—. Se comprueba explícitamente, porque convierte una afirmación teórica en un hecho
verificado: `C11` **no depende** de que el modelo de la curva sea correcto.

Lectura preregistrada
---------------------
  * `p_perm < 0.05` para el chi2 observado -> **LA DESVIACION ERA EL ORDEN**. `C12` se
    reformula: la desviación proviene de la posición de `conf0`, no de heterogeneidad
    demostrada.
  * `p_perm >= 0.05` -> **LA DESVIACION SOBREVIVE AL ORDEN**, y la heterogeneidad entre
    complejos pasa a ser la explicación en pie.
  * El contraste (1) se reporta siempre, gane quien gane el (2), porque un `conf0` con ventaja
    medida es un hecho de interés propio para el protocolo.

Límites declarados ANTES de correr
----------------------------------
1. **No toca `C11`.** El conjunto de los nueve es invariante por construcción y el contraste
   (3) sólo lo verifica.
2. **No toca la cantidad primaria de `MF-33-EXT`** —la cobertura, 107/116— que tampoco depende
   del orden.
3. La permutación asume que los K resultados por complejo son **intercambiables bajo la nula**.
   Eso es exactamente la hipótesis que se contrasta; no se asume cierta.
4. **No ajusta modelos de mezcla.** Si la desviación sobrevive al orden, este análisis **no**
   establece un componente refractario: sólo retira una explicación alternativa.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

UMBRAL_A = 2.0
B_PERM = 10000
SEMILLA = 42


def _chi2_contra_geometrica(primeros: List[Optional[int]], Ks: List[int]) -> Optional[float]:
    """chi2 de la distribucion del primer acierto contra una geometrica homogenea.

    Replica exactamente el procedimiento de MF-33-EXT-MOD: p por maxima verosimilitud
    sobre los cubiertos, bins 1..4 y >=5, esperados condicionados a haber sido cubierto.
    """
    from scipy.stats import chisquare
    cub = [(pk, K) for pk, K in zip(primeros, Ks) if pk is not None]
    if len(cub) < 10:
        return None
    p = len(cub) / sum(pk for pk, _K in cub)
    if not (0 < p < 1):
        return None
    obs = [sum(1 for pk, _K in cub if pk == k) for k in (1, 2, 3, 4)]
    obs.append(sum(1 for pk, _K in cub if pk >= 5))
    esp = [sum(((1 - p) ** (k - 1)) * p for _pk, K in cub if K >= k) for k in (1, 2, 3, 4)]
    den = sum(1 - (1 - p) ** K for _pk, K in cub)
    esp.append(max(den - sum(esp), 1e-9))
    esc = sum(obs) / sum(esp)
    esp = [e * esc for e in esp]
    if min(esp) < 1e-6:
        return None
    return float(chisquare(obs, esp)[0])


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-33-ORD: el confusor de orden, por permutacion")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    ap.add_argument("--perms", type=int, default=B_PERM)
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-ORD"
    out_dir.mkdir(parents=True, exist_ok=True)

    filas = [json.loads(l) for l in
             (art / "MF-33-EXT" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    datos = []
    for r in filas:
        corr = r.get("corridas") or []
        vals = [c.get("rmsd_min") for c in corr]
        if not vals or any(v is None for v in vals):
            vals = [v for v in vals if v is not None]
        if len(vals) < 1:
            continue
        datos.append({"pid": r["pid"], "estrato": r.get("estrato"), "rmsds": vals})

    # ── (1) ¿es conf0 especial? rango de conf0 entre sus K conformeros ──
    rangos, rangos_norm = [], []
    for d in datos:
        K = len(d["rmsds"])
        if K < 2:
            continue
        v0 = d["rmsds"][0]
        # rango 1 = el mejor (rmsd mas bajo); empates a la media
        mejores = sum(1 for v in d["rmsds"] if v < v0)
        empates = sum(1 for v in d["rmsds"] if v == v0)
        rango = mejores + (empates + 1) / 2.0
        rangos.append(rango)
        rangos_norm.append((rango - 0.5) / K)      # en [0,1), 0.5 bajo intercambiabilidad
        d["rango_conf0"] = round(rango, 2)
        d["K"] = K
    import statistics as st
    media_norm = st.mean(rangos_norm) if rangos_norm else None
    n_r = len(rangos_norm)
    sd_norm = st.pstdev(rangos_norm) if n_r > 1 else 0.0
    z = ((media_norm - 0.5) / (sd_norm / math.sqrt(n_r))) if (n_r > 1 and sd_norm > 0) else None
    from scipy.stats import norm as _norm
    p_conf0 = float(2 * _norm.sf(abs(z))) if z is not None else None

    # ── (2) permutacion del orden ──
    def primeros_de(orden_fn) -> tuple:
        pr, Ks = [], []
        for d in datos:
            v = orden_fn(d["rmsds"])
            pk = next((i + 1 for i, x in enumerate(v) if x <= UMBRAL_A), None)
            pr.append(pk); Ks.append(len(v))
        return pr, Ks

    pr_obs, Ks = primeros_de(lambda v: v)
    chi2_obs = _chi2_contra_geometrica(pr_obs, Ks)

    rng = random.Random(SEMILLA)
    nulos = []
    for _ in range(args.perms):
        pr, Ks2 = primeros_de(lambda v: rng.sample(v, len(v)))
        c = _chi2_contra_geometrica(pr, Ks2)
        if c is not None:
            nulos.append(c)
    nulos.sort()
    p_perm = (sum(1 for c in nulos if c >= chi2_obs) + 1) / (len(nulos) + 1) if chi2_obs else None

    # ── (3) invariancia de C11 ──
    nunca_obs = sorted(d["pid"] for d in datos if all(v > UMBRAL_A for v in d["rmsds"]))
    inv = True
    for _ in range(200):
        s = sorted(d["pid"] for d in datos
                   if all(v > UMBRAL_A for v in rng.sample(d["rmsds"], len(d["rmsds"]))))
        if s != nunca_obs:
            inv = False
            break

    lectura = None
    if p_perm is not None:
        lectura = "LA_DESVIACION_ERA_EL_ORDEN" if p_perm < 0.05 else "LA_DESVIACION_SOBREVIVE_AL_ORDEN"

    salida = {
        "analisis_id": "MF-33-ORD",
        "tipo": "re-analisis por permutacion, sin computo de docking",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_complejos": len(datos), "permutaciones": len(nulos), "semilla": SEMILLA,
        "CONTRASTE_1_conf0_especial": {
            "pregunta": "el rango de conf0 entre sus K conformeros es uniforme?",
            "n": n_r,
            "rango_normalizado_medio": round(media_norm, 4) if media_norm is not None else None,
            "esperado_bajo_intercambiabilidad": 0.5,
            "z": round(z, 3) if z is not None else None,
            "p": round(p_conf0, 6) if p_conf0 is not None else None,
            "interpretacion": ("<0.5 significa que conf0 tiende a ser MEJOR que un conformero "
                               "al azar del mismo complejo")},
        "CONTRASTE_2_permutacion": {
            "chi2_observado": round(chi2_obs, 4) if chi2_obs else None,
            "chi2_nulo_mediana": round(nulos[len(nulos)//2], 4) if nulos else None,
            "chi2_nulo_p95": round(nulos[int(len(nulos)*0.95)], 4) if nulos else None,
            "p_permutacion": round(p_perm, 5) if p_perm is not None else None,
            "lectura_preregistrada": lectura},
        "CONTRASTE_3_invariancia_C11": {
            "nunca_cubiertos": nunca_obs, "n": len(nunca_obs),
            "invariante_en_200_permutaciones": inv,
            "nota": "invariante por construccion; se verifica explicitamente porque convierte "
                    "una afirmacion teorica en un hecho comprobado"},
        "limites_declarados": [
            "no toca C11: el conjunto de los nueve es invariante y el contraste 3 solo lo verifica",
            "no toca la cobertura de MF-33-EXT, que tampoco depende del orden",
            "no ajusta modelos de mezcla: si la desviacion sobrevive, esto NO establece un "
            "componente refractario, solo retira una explicacion alternativa",
        ],
        "per_complex": [{"pid": d["pid"], "estrato": d["estrato"], "K": d.get("K"),
                         "rango_conf0": d.get("rango_conf0"),
                         "rmsd_conf0": d["rmsds"][0],
                         "mejor_rmsd": min(d["rmsds"])} for d in datos],
    }
    (out_dir / "metrics.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in salida["per_complex"]:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    c1, c2, c3 = (salida["CONTRASTE_1_conf0_especial"], salida["CONTRASTE_2_permutacion"],
                  salida["CONTRASTE_3_invariancia_C11"])
    print(f"[MF-33-ORD] n={len(datos)} | {len(nulos)} permutaciones")
    print(f"  (1) rango normalizado medio de conf0 = {c1['rango_normalizado_medio']} "
          f"(0.5 bajo intercambiabilidad) z={c1['z']} p={c1['p']}")
    print(f"  (2) chi2 obs={c2['chi2_observado']} | nulo mediana={c2['chi2_nulo_mediana']} "
          f"p95={c2['chi2_nulo_p95']} | p_perm={c2['p_permutacion']}")
    print(f"      LECTURA: {c2['lectura_preregistrada']}")
    print(f"  (3) nunca cubiertos: {c3['n']} | invariante: {c3['invariante_en_200_permutaciones']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
