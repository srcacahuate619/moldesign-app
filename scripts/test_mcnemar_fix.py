# -*- coding: utf-8 -*-
"""test_mcnemar_fix.py — corrigendum estadistico RS-01A/RS-01B.

Bug formal confirmado por el maintainer: la version previa de mcnemar_hits
(run_rs01a_audit.py / run_rs01b_crossfit.py) multiplicaba por 2 el pvalue de
scipy.stats.binomtest(...), que YA es bilateral.

Este test fija los valores CORREGIDOS:

    (b=4,  c=0)  -> 0.125      (RS-01A a1)
    (b=11, c=7)  -> 0.480682   (RS-01B global)
    (b=7,  c=11) -> 0.480682   (simetrico)
    (b=0,  c=0)  -> 1.0        (sin pares discordantes)

Solo stdlib + scipy. Deterministico.

Uso:
    python scripts/test_mcnemar_fix.py
"""
from __future__ import annotations

from scipy.stats import binomtest


def mcnemar_p(b: int, c: int) -> float:
    """Formula CORREGIDA (sin el factor 2: binomtest ya es bilateral)."""
    n_discordantes = b + c
    if n_discordantes == 0:
        return 1.0
    return float(binomtest(min(b, c), n_discordantes, 0.5).pvalue)


CASOS = [
    ((4, 0), 0.125),
    ((11, 7), 0.480682),
    ((7, 11), 0.480682),
    ((0, 0), 1.0),
]


def main() -> int:
    fallos = 0
    for (b, c), esperado in CASOS:
        obtenido = mcnemar_p(b, c)
        obtenido_r = round(obtenido, 6)
        ok = abs(obtenido - esperado) < 5e-7
        print(f"  mcnemar(b={b}, c={c}) = {obtenido_r} (esperado {esperado}) "
              f"{'OK' if ok else 'FALLO'}", flush=True)
        fallos += 0 if ok else 1
    if fallos:
        print(f"RESULTADO: FALLO ({fallos} caso(s))")
        return 1
    print("RESULTADO: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
