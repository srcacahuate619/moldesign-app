"""CAL-D-01 R4: ρ de peor caso contra los scores, y el resto del análisis estadístico del registro previo.

    ρ_peor = mín sobre b ∈ {0,1}^n de Spearman(Q, pKi_i − b_i·log10 F),   F = 1015/703.

Equivale a z_i = Ki_i·F^{b_i} (y = −log10 z). Spearman es Pearson sobre rangos medios.

# Algoritmo exacto (programación dinámica por ventana de F)

Con los padres ordenados por Ki, dos padres i < j sólo pueden cambiar de orden si Ki_j < Ki_i·F
(«interactúan»); cualquier otro par conserva su orden para todo b. El numerador es
N = Σ_p w_p·rY_p, con w = rango de Q centrado, y es suma de términos por pares:

    N(b) = N(0) + Σ_{pares que interactúan} c_i c_j · Δ(b_i, b_j)
    Δ(0,0) = Δ(1,1) = 0,   Δ(1,0) = σ (w_j − w_i),   Δ(0,1) = (1 − σ)(w_i − w_j)

con σ = 1 si Ki_i < Ki_j y σ = 1/2 si son iguales, c = copias, w = rango de Q centrado. La DP sólo
recuerda los bits de los padres «activos» (a menos de un factor F del actual). El denominador depende
de b únicamente por los empates de y: 12·SY = n³ − n − Σ_clases (t³ − t), una clase por (Ki, b), y se
lleva como parte del estado (T, aditivo al cerrar cada grupo de Ki iguales). Para cada T, minimizar ρ
es minimizar N, porque el denominador es positivo y fijo. Un padre con c copias en una réplica de
bootstrap es un solo elemento de peso c: todas sus copias llevan el mismo b y están empatadas.

Supuesto, comprobado en los datos con `Panel.__init__`: ningún par cumple Ki_j = Ki_i·F exacto
(sería un empate cruzado en y que la recurrencia no modela). `ValueError` si ocurre.

`rho_asignacion` y `rho_peor_fuerza_bruta` son la referencia lenta, sin nada de lo anterior: las
pruebas comparan ambas en casos pequeños (empates, copias, valores junto al umbral).
"""
from __future__ import annotations

import itertools
import math
from fractions import Fraction

import numpy as np

F = Fraction(1015, 703)
LOG10_F = math.log10(1015 / 703)
SEMILLA_BOOTSTRAP = 20261021
BOOTSTRAP_N = 10_000


# ── Referencia: Spearman de una asignación concreta, sin DP ──────────────────

def _rangos(vals):
    orden = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(orden):
        j = i + 1
        while j < len(orden) and vals[orden[j]] == vals[orden[i]]:
            j += 1
        for h in range(i, j):
            out[orden[h]] = (i + 1 + j) / 2
        i = j
    return out


def rho_asignacion(ki, q, b, copias=None) -> float:
    """Spearman(Q, y) exacto: z = Ki·F^b en Fraction; y ordena al revés que z."""
    copias = copias or [1] * len(ki)
    z, qq = [], []
    for k, qi, bi, c in zip(ki, q, b, copias):
        zi = Fraction(str(k)) * (F if bi else 1)
        z += [-zi] * c
        qq += [qi] * c
    ra, rb = _rangos(qq), _rangos(z)
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    sa = sum((x - ma) ** 2 for x in ra)
    sb = sum((y - mb) ** 2 for y in rb)
    if sa == 0 or sb == 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / math.sqrt(sa * sb)


def rho_peor_fuerza_bruta(ki, q, copias=None):
    """Enumera las 2^m asignaciones. Sólo para m pequeño: es la referencia de las pruebas."""
    mejor = (math.inf, None)
    for b in itertools.product((0, 1), repeat=len(ki)):
        r = rho_asignacion(ki, q, b, copias)
        if r < mejor[0]:
            mejor = (r, b)
    return mejor


# ── DP exacta ────────────────────────────────────────────────────────────────

def _phi(t):
    return t ** 3 - t


class Panel:
    """Los Ki del panel: orden, grupos de Ki iguales y ventana de interacción, calculados una vez."""

    def __init__(self, ki):
        self.m = len(ki)
        kif = [Fraction(str(k)) for k in ki]
        self.orden = sorted(range(self.m), key=lambda i: kif[i])     # posición ordenada -> índice original
        self.pos = {orig: p for p, orig in enumerate(self.orden)}
        s = [kif[i] for i in self.orden]
        self.ki_ord = s
        m = self.m
        self.inter = np.zeros((m, m), dtype=bool)     # inter[a, j] (a < j): Ki_j < Ki_a·F
        self.igual = np.zeros((m, m), dtype=bool)
        for a in range(m):
            for j in range(a + 1, m):
                if s[j] == s[a] * F:
                    raise ValueError("par con Ki_j = Ki_i·F exacto: la recurrencia no lo modela")
                self.inter[a, j] = s[j] < s[a] * F
                self.igual[a, j] = s[j] == s[a]
        # grupo (Ki iguales) de cada posición y su último miembro
        self.grupo_de = [0] * m                       # posición -> id de grupo (Ki iguales)
        self.grupos: list[list[int]] = []
        i = 0
        while i < m:
            j = i
            while j + 1 < m and s[j + 1] == s[i]:
                j += 1
            for p in range(i, j + 1):
                self.grupo_de[p] = len(self.grupos)
            self.grupos.append(list(range(i, j + 1)))
            i = j + 1


def _rangos_q(q_ord, copias_ord):
    """Rangos medios de Q sobre las posiciones expandidas; devuelve un rango por elemento."""
    expandido = [qv for qv, c in zip(q_ord, copias_ord) for _ in range(c)]
    r = _rangos(expandido)
    out, pos = [], 0
    for c in copias_ord:
        out.append(r[pos] if c else 0.0)
        pos += c
    return out, len(expandido)


def rho_peor(panel: Panel, q, copias=None, fijos=None, devolver_T=False):
    """ρ de peor caso exacto de un panel con scores `q` (en el orden original de los Ki).

    `copias[i]` = veces que el padre i está en la muestra (0 = ausente). `fijos` = {índice original: 0|1}
    restringe la búsqueda; sirve para recuperar una asignación que alcanza el mínimo.
    """
    m = panel.m
    copias = list(copias) if copias is not None else [1] * m
    q_ord = [q[i] for i in panel.orden]
    c_ord = [copias[i] for i in panel.orden]
    rq, n = _rangos_q(q_ord, c_ord)
    media = (n + 1) / 2
    w = [r - media for r in rq]
    sq = sum(c * x * x for c, x in zip(c_ord, w))
    if sq == 0 or n < 3:
        return float("nan")
    fij = {panel.pos[i]: v for i, v in (fijos or {}).items()}
    presentes = [p for p in range(m) if c_ord[p] > 0]

    # N con todos los b = 0
    s = panel.ki_ord
    base = 0.0
    for p in presentes:
        menores = sum(c_ord[r] for r in presentes if s[r] > s[p])
        iguales = sum(c_ord[r] for r in presentes if s[r] == s[p])
        base += c_ord[p] * w[p] * (1 + menores + 0.5 * (iguales - 1))

    ultimo = {panel.grupo_de[p]: p for p in presentes}      # último miembro presente de cada grupo
    activos: list[int] = []
    estados = {0: np.zeros(())}
    for j in presentes:
        for p in [p for p, a in enumerate(activos) if not panel.inter[a, j]][::-1]:
            estados = {T: np.minimum(arr.take(0, axis=p), arr.take(1, axis=p)) for T, arr in estados.items()}
            del activos[p]
        k = len(activos)
        costes = []
        for bj in (0, 1):
            tot = np.zeros((2,) * k)
            for p, a in enumerate(activos):
                sig = 0.5 if panel.igual[a, j] else 1.0
                cc = c_ord[a] * c_ord[j]
                if bj == 0:      # (bi, 0): Δ(0,0) = 0, Δ(1,0) = σ (w_j − w_a)
                    v = np.array([0.0, cc * sig * (w[j] - w[a])])
                else:            # (bi, 1): Δ(0,1) = (1 − σ)(w_a − w_j), Δ(1,1) = 0
                    v = np.array([cc * (1 - sig) * (w[a] - w[j]), 0.0])
                forma = [1] * k
                forma[p] = 2
                tot = tot + v.reshape(forma)
            costes.append(tot)
        nuevo = {}
        for T, arr in estados.items():
            piezas = []
            for bj in (0, 1):
                a_ = arr + costes[bj]
                if j in fij and fij[j] != bj:
                    a_ = np.full(a_.shape, np.inf)
                piezas.append(a_)
            nuevo[T] = np.stack(piezas, axis=-1)
        estados = nuevo
        activos.append(j)
        miembros = [g for g in panel.grupos[panel.grupo_de[j]] if c_ord[g] > 0]
        if ultimo[panel.grupo_de[j]] == j:                  # se cierra un grupo de Ki iguales: suma su término de empates
            if len(miembros) == 1:
                dT = _phi(c_ord[miembros[0]])
                estados = {T + dT: arr for T, arr in estados.items()}
            else:
                ejes = [activos.index(g) for g in miembros]
                acumulado: dict[int, np.ndarray] = {}
                for T, arr in estados.items():
                    for bits in itertools.product((0, 1), repeat=len(miembros)):
                        uno = sum(c_ord[g] for g, b_ in zip(miembros, bits) if b_)
                        cero = sum(c_ord[g] for g in miembros) - uno
                        sel = [slice(None)] * arr.ndim
                        for ax, b_ in zip(ejes, bits):
                            sel[ax] = b_
                        parte = np.full(arr.shape, np.inf)
                        parte[tuple(sel)] = arr[tuple(sel)]
                        clave = T + _phi(uno) + _phi(cero)
                        acumulado[clave] = parte if clave not in acumulado else np.minimum(acumulado[clave], parte)
                estados = acumulado
    mejor = (math.inf, None)
    for T, arr in estados.items():
        nmin = base + float(arr.min())
        sy = (n ** 3 - n - T) / 12.0
        if not math.isfinite(nmin) or sy <= 0:
            continue
        r = nmin / math.sqrt(sq * sy)
        if r < mejor[0]:
            mejor = (r, T)
    return mejor if devolver_T else mejor[0]


def asignacion_peor(panel: Panel, q, copias=None, tol=1e-12):
    """Una asignación b (en el orden original) que alcanza el mínimo, por fijación voraz."""
    objetivo = rho_peor(panel, q, copias)
    fijos: dict[int, int] = {}
    for i in panel.orden:
        if copias is not None and copias[i] == 0:
            continue
        fijos[i] = 0
        if not (rho_peor(panel, q, copias, fijos) <= objetivo + tol):
            fijos[i] = 1
    return [fijos.get(i, 0) for i in range(panel.m)], objetivo


# ── Spearman simple, concordancia de pares (P2) y bootstrap ──────────────────

def spearman(q, y, copias=None):
    from scipy.stats import rankdata
    copias = np.ones(len(q), dtype=int) if copias is None else np.asarray(copias, dtype=int)
    qa = np.repeat(np.asarray(q, dtype=float), copias)
    ya = np.repeat(np.asarray(y, dtype=float), copias)
    if np.unique(qa).size < 2 or np.unique(ya).size < 2:
        return float("nan")
    return float(np.corrcoef(rankdata(qa), rankdata(ya))[0, 1])


def pares_comparables(ki):
    """Matriz de pares (i, j) con Ki_j / Ki_i estrictamente mayor que F: i es el más potente."""
    kif = [Fraction(str(k)) for k in ki]
    m = len(kif)
    comp = np.zeros((m, m), dtype=bool)
    for i in range(m):
        for j in range(m):
            comp[i, j] = kif[j] > kif[i] * F
    return comp


def concordancia(comp, q, copias=None):
    """Fracción de pares comparables en que el más potente tiene el mayor Q (empates cuentan 1/2)."""
    q = np.asarray(q, dtype=float)
    c = np.ones(len(q)) if copias is None else np.asarray(copias, dtype=float)
    mejor = (q[:, None] > q[None, :]).astype(float) + 0.5 * (q[:, None] == q[None, :])
    peso = c[:, None] * c[None, :] * comp
    tot = peso.sum()
    return float((peso * mejor).sum() / tot) if tot else float("nan")


def bootstrap(ki, q, n_rep=BOOTSTRAP_N, semilla=SEMILLA_BOOTSTRAP, con_peor=True, progreso=None):
    """Bootstrap percentil pareado por padre. En cada réplica ρ y ρ_peor usan los mismos copias, y las
    copias de un padre comparten b. Réplicas sin variación en Q o en Ki se descartan y se cuentan."""
    panel = Panel(ki)
    comp = pares_comparables(ki)
    pki = -np.log10(np.asarray([float(Fraction(str(k))) for k in ki]) * 1e-9)
    rng = np.random.default_rng(semilla)
    n = len(ki)
    rho, peor, conc, descartadas = [], [], [], 0
    for r in range(n_rep):
        idx = rng.integers(0, n, n)
        copias = np.bincount(idx, minlength=n)
        pres = copias > 0
        if np.unique(np.asarray(q)[pres]).size < 2 or np.unique(pki[pres]).size < 2:
            descartadas += 1
            continue
        rho.append(spearman(q, pki, copias))
        conc.append(concordancia(comp, q, copias))
        if con_peor:
            peor.append(rho_peor(panel, q, copias))
        if progreso and (r + 1) % 500 == 0:
            progreso(r + 1)
    pct = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]
    return {"n_replicas": n_rep, "descartadas": descartadas, "semilla": semilla,
            "rho": pct(rho), "rho_peor": pct(peor) if con_peor else None, "concordancia": pct(conc)}
