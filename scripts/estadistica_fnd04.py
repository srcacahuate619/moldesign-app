#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""estadistica_fnd04.py — FND-04: biblioteca comun de incertidumbre del programa.

La §6 del doc. 49 declara FND-04 como P0: «biblioteca común de bootstrap pareado,
Wilson, McNemar/DeLong y FDR» con «sanity tests perfect/random y uso uniforme». No
tenía artefacto, mientras `RS-14`, `RS-14-R1`, `MF-08`, `REC-03` y el entregable 8
llevaban usando cada uno su propia implementación de los mismos estadísticos.

Ese es el tipo de deuda donde un error no afecta a un experimento: afecta a **todos
los gates a la vez**. Esta biblioteca centraliza las cuatro herramientas, se valida
contra casos de respuesta conocida, y permite **re-verificar de forma independiente**
los intervalos ya sellados.

Solo biblioteca estandar salvo numpy. Sin estado global, sin aleatoriedad implicita:
toda funcion que remuestrea recibe su semilla.
"""

from __future__ import annotations

import math
import random
from typing import Callable, List, Optional, Sequence, Tuple


# ───────────────────────────── Wilson ─────────────────────────────

def wilson(exitos: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """Intervalo de Wilson al 95% para una proporcion.

    Se prefiere a Wald porque no se sale de [0,1] ni colapsa a ancho cero cuando la
    proporcion observada es 0 o 1 — los dos casos en los que Wald enganaria mas.
    """
    if n <= 0:
        raise ValueError("n debe ser positivo")
    p = exitos / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centro - medio), min(1.0, centro + medio))


# ───────────────────────── McNemar exacto ─────────────────────────

def _binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    s = 0.0
    for i in range(k + 1):
        s += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return s


def mcnemar_exacto(b: int, c: int) -> float:
    """p bilateral exacto (binomial) para tablas pareadas 2x2.

    `b` y `c` son las discordancias. Exacto y no aproximado: con los n de este
    programa (17, 33, 92 complejos) la aproximacion chi-cuadrado no es fiable.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * _binom_cdf(k, n))


# ───────────────────── Bootstrap BCa pareado ──────────────────────

def bootstrap_bca_pareado(
    dif: Sequence[float],
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
    estadistico: Optional[Callable[[Sequence[float]], float]] = None,
) -> Tuple[float, float, float]:
    """(punto, low, high) del IC BCa para el estadistico de un vector pareado.

    BCa corrige sesgo (z0) y aceleracion (a, via jackknife). Con distribuciones
    asimetricas —lo habitual al promediar aciertos por complejo— el percentil simple
    desplaza el intervalo; BCa lo corrige.
    """
    x = list(dif)
    n = len(x)
    if n < 2:
        raise ValueError("se necesitan al menos 2 observaciones")
    est = estadistico or (lambda v: sum(v) / len(v))
    theta = est(x)
    rng = random.Random(seed)
    reps: List[float] = []
    for _ in range(n_boot):
        m = [x[rng.randrange(n)] for _ in range(n)]
        reps.append(est(m))
    reps.sort()

    menores = sum(1 for r in reps if r < theta)
    if menores == 0 or menores == len(reps):
        # degenerado: sin variacion, se devuelve el punto
        return theta, theta, theta
    z0 = _ppf(menores / len(reps))

    # jackknife para la aceleracion
    jack = []
    for i in range(n):
        jack.append(est(x[:i] + x[i + 1:]))
    jm = sum(jack) / n
    num = sum((jm - j) ** 3 for j in jack)
    den = 6.0 * (sum((jm - j) ** 2 for j in jack) ** 1.5)
    a = num / den if den != 0 else 0.0

    def ajuste(p: float) -> float:
        zp = _ppf(p)
        return _cdf(z0 + (z0 + zp) / (1 - a * (z0 + zp)))

    lo = ajuste(alpha / 2)
    hi = ajuste(1 - alpha / 2)
    return theta, reps[max(0, min(len(reps) - 1, int(lo * len(reps))))], \
        reps[max(0, min(len(reps) - 1, int(hi * len(reps))))]


def _cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _ppf(p: float) -> float:
    """Inversa de la normal estandar (Acklam), suficiente para BCa."""
    if p <= 0:
        return -8.0
    if p >= 1:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)


# ───────────────────────── FDR (Benjamini-Hochberg) ─────────────────────────

def benjamini_hochberg(pvals: Sequence[float], q: float = 0.05) -> List[bool]:
    """Devuelve, por p-valor y en el orden de entrada, si se rechaza bajo FDR<=q."""
    n = len(pvals)
    if n == 0:
        return []
    orden = sorted(range(n), key=lambda i: pvals[i])
    corte = -1
    for rank, i in enumerate(orden, 1):
        if pvals[i] <= q * rank / n:
            corte = rank
    rechaza = [False] * n
    for rank, i in enumerate(orden, 1):
        if rank <= corte:
            rechaza[i] = True
    return rechaza


# ───────────────── Efecto minimo detectable (potencia prospectiva) ─────────────────

def efecto_minimo_detectable(n: int, discordancia: float, potencia: float = 0.80,
                             alpha: float = 0.05) -> float:
    """Diferencia pareada mas pequena que un diseno de tamano `n` puede detectar.

    Motivacion (doc. 49 §20.9): `RS-14` descubrio DESPUES de ejecutar que con 92
    complejos cubiertos no podia resolver diferencias menores a ~10 puntos. Un ensayo
    clinico calcula esto ANTES de reclutar. Esta funcion existe para que ningun gate
    comparativo se selle sin declarar su efecto minimo detectable.

    Modelo: la diferencia por complejo toma valores en {-1, 0, +1} (el brazo B acierta
    y A no, empate, A acierta y B no). `discordancia` = P(|X| = 1) = tasa de pares
    discordantes. Entonces Var(X) = discordancia - delta^2, y el gate del programa
    -CI95 pareado que excluya el cero- rechaza cuando |media| > z_alpha * SE.

    Resolviendo delta / (sd/sqrt(n)) = z_alpha + z_potencia:

        delta = sqrt( k * d / (n + k) ),  con k = (z_alpha + z_potencia)^2

    Aproximacion normal, no bootstrap. Se justifica porque `FND-04` verifico que el
    BCa del programa reproduce los intervalos sellados; usar la normal aqui evita un
    bootstrap anidado y el error que introduce es de segundo orden frente a la
    incertidumbre sobre `discordancia`.
    """
    if not 0 < discordancia <= 1:
        raise ValueError("discordancia debe estar en (0, 1]")
    if n < 2:
        raise ValueError("n debe ser >= 2")
    k = (_ppf(1 - alpha / 2) + _ppf(potencia)) ** 2
    return math.sqrt(k * discordancia / (n + k))


def n_necesario(delta: float, discordancia: float, potencia: float = 0.80,
                alpha: float = 0.05) -> int:
    """Complejos necesarios para detectar `delta` con la potencia pedida.

    Es la inversa de `efecto_minimo_detectable`, y responde la pregunta operativa:
    «para resolver 5 puntos porcentuales, ¿cuantos complejos hacen falta?»
    """
    if delta <= 0:
        raise ValueError("delta debe ser positivo")
    k = (_ppf(1 - alpha / 2) + _ppf(potencia)) ** 2
    n = k * (discordancia - delta ** 2) / (delta ** 2)
    return max(2, int(math.ceil(n)))
