r"""Tamaño y potencia de ENS-PROD-01, calculados; no es una ejecución del ensayo.

Lo que cierra: la auditoría del ensamble dejó ENS-PROD-01 en BORRADOR con cuatro
decisiones pendientes —cohorte, tamaño/potencia, presupuesto y umbral de
relevancia práctica—. Dos de ellas exigen datos y dinero; la de tamaño/potencia
es aritmética y se puede cerrar sin mirar el conjunto final, que es justamente la
condición que el borrador impone.

Lo que NO hace: no ejecuta el ensayo, no elige la cohorte, no fija el umbral de
relevancia práctica y no mira ningún dato nuevo. Lee el artefacto sellado
MF-33-B-RET-R2 en modo lectura y calcula potencia exacta de McNemar.

    python backend/audits/ens_prod_01_potencia.py --output <directorio>

Sin --output imprime el informe y no escribe nada.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ LOS NÚMEROS QUE SALEN DE AQUÍ SON UNA COTA INFERIOR
═══════════════════════════════════════════════════════════════════════════

Dimensionar un ensayo confirmatorio con el efecto observado en la corrida que lo
motivó sesga el resultado a la baja: se escogió mirar precisamente el contraste
que salió grande. El efecto real esperado es MENOR que el observado, así que el n
que sale de aquí es el mínimo bajo un supuesto optimista, no el n suficiente.
R2 declara además, por escrito, que no es confirmación ciega.

Por eso el informe incluye la curva completa de n frente a efecto asumido: la
decisión de qué diferencia merece la pena se toma ANTES y desde fuera, y aquí
sólo se le pone precio en complejos.

Y una segunda razón, independiente: McNemar supone pares independientes. Una
cohorte con varios ligandos de la misma serie o varias estructuras de la misma
diana tiene n efectivo menor que su n nominal. Ninguna cifra de este archivo
corrige esa dependencia; el análisis final tiene que declararla.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
METRICAS = (RAIZ / "scripts" / "artifacts_science" / "MF-33-B-RET-R2"
            / "metrics.json")

#: Dos colas, el nivel del borrador. Un contraste que se anuncia como «mejora»
#: se prueba a dos colas o no se prueba: la hipótesis de que el ensemble EMPEORE
#: el top-1 es tan admisible como la contraria y R2 no la descarta.
ALFA = 0.05

#: Los dos objetivos habituales. Se informan los dos porque la diferencia entre
#: 248 y 324 complejos —lo que sale para el contraste primario— es una decisión
#: de presupuesto, no de estadística.
POTENCIAS = (0.80, 0.90)

#: Efectos asumidos para la curva, en puntos porcentuales de diferencia de
#: acierto pareado. No es una predicción: es el precio en complejos de cada
#: umbral posible, para que el umbral se elija con la cifra delante.
EFECTOS_PP = (5.0, 8.0, 10.0, 15.0, 20.0)


def p_exacta_mcnemar(b: int, c: int) -> float:
    """p exacta de McNemar a dos colas: binomial(b+c, 1/2) sobre los discordantes.

    Es la misma prueba que usó R2 —sus p coinciden con las selladas— y no la
    aproximación de chi-cuadrado, que con diez pares discordantes no es válida.
    """
    n = b + c
    if n == 0:
        return 1.0
    menor = min(b, c)
    cola = sum(math.comb(n, k) for k in range(menor + 1)) / (2 ** n)
    return min(1.0, 2 * cola)


def _k_critico(d: int, alfa: float) -> int:
    """El mayor k con 2·P(Binom(d,½) ≤ k) ≤ alfa, o -1 si ninguno.

    La prueba exacta rechaza exactamente cuando `b ≤ k` o `b ≥ d-k`. Escribirlo
    así es lo que permite calcular la potencia sin recorrer todas las tablas: la
    región de rechazo de McNemar es una cola simétrica sobre los discordantes.
    """
    acumulado = 0.0
    total = 2.0 ** d
    critico = -1
    for k in range(d + 1):
        acumulado += math.comb(d, k) / total
        if 2 * acumulado <= alfa:
            critico = k
        else:
            break
    return critico


class _RechazoCondicional:
    """P(rechazar | D=d) para cada d, memoizado. NO depende de n.

    Es la clave de que esto se pueda calcular de verdad: la prueba exacta de
    McNemar es condicional al número de discordantes, así que su probabilidad de
    rechazo depende sólo de d y de psi. Se tabula por demanda y después cada n es
    una suma. Sin esto, cada cifra del informe tardaba minutos.
    """

    def __init__(self, psi: float, alfa: float):
        self.psi = psi
        self.alfa = alfa
        self._cache: dict[int, float] = {}

    def __getitem__(self, d: int) -> float:
        if d in self._cache:
            return self._cache[d]
        critico = _k_critico(d, self.alfa)
        if critico < 0:
            self._cache[d] = 0.0
            return 0.0
        psi = self.psi
        # pmf de Binomial(d, psi) por recurrencia, sin `math.comb` por término.
        if psi in (0.0, 1.0):
            b_seguro = d if psi == 1.0 else 0
            valor = 1.0 if (b_seguro <= critico or b_seguro >= d - critico) else 0.0
            self._cache[d] = valor
            return valor
        pmf = (1 - psi) ** d
        razon = psi / (1 - psi)
        acumulado = 0.0
        for b in range(d + 1):
            if b:
                pmf *= razon * (d - b + 1) / b
            if b <= critico or b >= d - critico:
                acumulado += pmf
        self._cache[d] = min(1.0, acumulado)
        return self._cache[d]


def potencia_exacta(n: int, p_discordancia: float, psi: float,
                    alfa: float = ALFA,
                    tabla: _RechazoCondicional | None = None) -> float:
    """Potencia EXACTA del McNemar condicional, sumando sobre los discordantes.

    Args:
        n: pares (complejos) de la cohorte.
        p_discordancia: probabilidad de que un par discorde.
        psi: probabilidad de que un par discordante favorezca al ensemble.
        tabla: `_RechazoCondicional` ya construida, si se tiene.

    No se usa la aproximación normal: el número de pares discordantes es
    pequeño, la prueba es discreta y su nivel real salta. Se calcula
    D ~ Binomial(n, p_disc) y, condicionado a D, b ~ Binomial(D, psi), y se suma
    la probabilidad de las tablas que la prueba exacta rechaza de verdad.
    """
    if not 0 < p_discordancia <= 1 or not 0 <= psi <= 1:
        raise ValueError("Proporciones fuera de rango")
    if tabla is None:
        tabla = _RechazoCondicional(psi, alfa)
    potencia = 0.0
    # pmf binomial por recurrencia: con n de varios cientos, `math.comb` en cada
    # término es el coste dominante y aquí no hace falta.
    pmf = (1 - p_discordancia) ** n
    razon = p_discordancia / (1 - p_discordancia)
    for d in range(n + 1):
        if d:
            pmf *= razon * (n - d + 1) / d
        if pmf < 1e-16 and d > n * p_discordancia:
            break
        potencia += pmf * tabla[d]
    return potencia


def n_necesario(p_discordancia: float, psi: float, objetivo: float,
                alfa: float = ALFA, techo: int = 5000) -> int | None:
    """El n más pequeño cuya potencia exacta alcanza el objetivo.

    Se busca el primer n que lo alcanza Y SE COMPRUEBA que no baja después: la
    potencia de una prueba exacta no es monótona en n —su nivel real salta con la
    discreción de la binomial—, así que el primer cruce no siempre se sostiene.
    El barrido es lineal y no binario por el mismo motivo: con una función no
    monótona, una búsqueda binaria puede devolver un n que no es el primero.
    """
    tabla = _RechazoCondicional(psi, alfa)
    for n in range(4, techo + 1):
        if potencia_exacta(n, p_discordancia, psi, alfa, tabla) < objetivo:
            continue
        if all(potencia_exacta(m, p_discordancia, psi, alfa, tabla) >= objetivo
               for m in range(n, min(n + 10, techo) + 1)):
            return n
    return None


def _desde_conteos(b: int, c: int, n: int) -> dict:
    """Estructura de discordancia observada, sin suavizar nada."""
    return {
        "b_gana_ensemble": b,
        "c_gana_single": c,
        "n": n,
        "p_discordancia": (b + c) / n,
        "psi_condicional": (b / (b + c)) if (b + c) else None,
        "delta_pp": 100.0 * (b - c) / n,
        "p_exacta_recalculada": p_exacta_mcnemar(b, c),
    }


def informe() -> dict:
    metricas = json.loads(METRICAS.read_text(encoding="utf-8"))
    resultado: dict = {
        "experimento": "ENS-PROD-01",
        "estado": "BORRADOR: dimensionado cerrado, cohorte y umbral abiertos",
        "fuente": {
            "artefacto": "scripts/artifacts_science/MF-33-B-RET-R2/metrics.json",
            "experiment_id": metricas["experiment_id"],
            "no_es_ciego": metricas["no_es_ciego"],
            "config": metricas["config"],
        },
        "alfa": ALFA,
        "prueba": "McNemar exacta, dos colas, pares independientes",
        "advertencias": [
            "El efecto observado en la corrida que motiva el ensayo sesga el "
            "dimensionado a la baja: estos n son cotas inferiores bajo un "
            "supuesto optimista, no n suficientes.",
            "McNemar supone pares independientes. Una cohorte con series "
            "congenericas o varias estructuras por diana tiene n efectivo "
            "menor; ninguna cifra de aqui lo corrige.",
            "No fija el umbral de relevancia practica ni la cohorte. Esas dos "
            "decisiones siguen abiertas y se toman sin mirar el conjunto final.",
        ],
        "estratos": {},
        "curva_de_precio": [],
    }

    for estrato in ("TODOS", "COLOCACION"):
        datos = metricas[estrato]
        bloque = {}
        for criterio in ("top1", "top5", "oraculo"):
            medida = datos[criterio]
            observado = _desde_conteos(
                medida["b_gana_ensemble"], medida["c_gana_single"], medida["de"]
            )
            # Coherencia con el sellado: si la p recalculada no coincide, algo
            # cambió y no se sigue calculando sobre una base distinta.
            if abs(observado["p_exacta_recalculada"] - medida["mcnemar_p"]) > 1e-6:
                raise SystemExit(
                    f"{estrato}/{criterio}: la p exacta recalculada "
                    f"({observado['p_exacta_recalculada']}) no reproduce la "
                    f"sellada ({medida['mcnemar_p']})"
                )
            observado["potencia_alcanzada_en_r2"] = potencia_exacta(
                medida["de"], observado["p_discordancia"],
                observado["psi_condicional"],
            )
            observado["n_necesario"] = {
                f"{objetivo:.2f}": n_necesario(
                    observado["p_discordancia"], observado["psi_condicional"],
                    objetivo,
                ) for objetivo in POTENCIAS
            }
            bloque[criterio] = observado
        resultado["estratos"][estrato] = bloque

    # El precio de cada umbral posible, con la discordancia observada en el
    # contraste que NO alcanzó significacion: top-1 sobre TODOS. Es el contraste
    # primario propuesto, y el unico cuyo dimensionado decide si el ensayo se
    # puede hacer.
    base = resultado["estratos"]["TODOS"]["top1"]
    p_disc = base["p_discordancia"]
    for efecto in EFECTOS_PP:
        delta = efecto / 100.0
        if delta > p_disc:
            # Un efecto mayor que la discordancia total es imposible con esta
            # estructura: se declara, no se extrapola.
            resultado["curva_de_precio"].append({
                "delta_pp": efecto,
                "n_080": None,
                "n_090": None,
                "nota": ("imposible con la discordancia observada "
                         f"({100 * p_disc:.2f} pp): exigiria mas pares "
                         "discordantes de los que se observan"),
            })
            continue
        psi = (p_disc + delta) / (2 * p_disc)
        resultado["curva_de_precio"].append({
            "delta_pp": efecto,
            "psi_implicado": psi,
            "n_080": n_necesario(p_disc, psi, 0.80),
            "n_090": n_necesario(p_disc, psi, 0.90),
        })
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    argumentos = parser.parse_args()
    datos = informe()
    texto = json.dumps(datos, indent=2, ensure_ascii=False)
    if argumentos.output:
        argumentos.output.mkdir(parents=True, exist_ok=True)
        (argumentos.output / "ens_prod_01_potencia.json").write_text(
            texto + "\n", encoding="utf-8"
        )
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
