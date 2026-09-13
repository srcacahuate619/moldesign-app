"""
El margen de selectividad, en la magnitud que sí tiene sentido físico.

# El fallo

    selectivity_ratio = round(on_target_affinity / worst_off_affinity, 2)

Las dos cantidades son energías libres de unión en kcal/mol. Dividirlas no
produce una razón de selectividad: produce un número adimensional sin
significado termodinámico. Como ΔG = −RT·ln K_d, ese cociente es
ln K_on / ln K_off, es decir el logaritmo de una constante de disociación en
la base de la otra. No es una cantidad que describa nada.

Lo que se ve en la práctica, con la escala de verdictos que había:

    ΔG_on = −10.0, ΔG_off = −5.0   ->  cociente 2.00   ->  ΔΔG = 5.0 kcal/mol
    ΔG_on =  −6.0, ΔG_off = −3.0   ->  cociente 2.00   ->  ΔΔG = 3.0 kcal/mol

Mismo cociente, mismo veredicto — y márgenes reales que se diferencian por un
factor de treinta. Y al revés: dos moléculas con el MISMO ΔΔG reciben cocientes
distintos según lo fuerte que sea la unión, así que el número ni siquiera
ordena de forma consistente.

Además el cociente se rompe justo en el mejor caso posible: si la molécula no
se une en absoluto a la anti-diana (ΔG_off ≥ 0), no hay división que hacer y el
resultado salía `null` —«sin datos suficientes»— para la situación más segura
que puede darse.

# La magnitud correcta

    ΔΔG = ΔG_off − ΔG_on          [kcal/mol]

Positivo = la diana principal une más fuerte que la anti-diana. Es una
diferencia de energías, se mide en las mismas unidades que sus términos, y es
lo que la literatura de selectividad reporta.

De ahí sale el factor de selectividad, que es lo que un químico médico quiere
leer:

    factor = 10^(ΔΔG / (ln(10)·R·T))   con ln(10)·R·T = 1.3633 kcal/mol a 298 K

# Por qué el factor va como banda y no como número

El score de Vina no es una energía libre medida: es una función empírica de
puntuación con una dispersión de ~2 kcal/mol frente a afinidad experimental.
ΔΔG hereda esa dispersión —parte se cancela al comparar dos acoplamientos del
mismo ligando, pero no toda: son receptores y cajas distintas—, y en escala
exponencial 2 kcal/mol son más de un orden de magnitud.

Dar «4.680×» sería el mismo error de pseudoprecisión que ya se quitó de la
columna de Ki. Se reporta ΔΔG en kcal/mol como cifra principal, y el factor
como intervalo.

# Una sola escala

Los umbrales del veredicto vivían por duplicado y NO COINCIDÍAN:

    backend  (selectivity_verdict)   > 10   > 3    > 1.5  > 1.0
    frontend (ProSelectivityPanel)   > 1.8  > 1.2  > 0.9

Un cociente de 2.0 se guardaba en la base y en el dossier como «MODERADAMENTE
SELECTIVO» mientras la pantalla decía «ALTAMENTE SELECTIVO» para la misma
corrida. Aquí hay una sola escala, en ΔΔG, y el frontend la reimplementa contra
esta tabla con una prueba que compara ambas.
"""

from __future__ import annotations

from dataclasses import dataclass

#: ln(10)·R·T a 298.15 K, en kcal/mol. Convierte ΔΔG en órdenes de magnitud.
KCAL_POR_DECADA: float = 1.3633

#: Dispersión típica del score de Vina frente a afinidad medida (kcal/mol).
#: La misma constante que usa el panel para la banda de concentración.
INCERTIDUMBRE_VINA_KCAL: float = 2.0


@dataclass(frozen=True)
class MargenDeSelectividad:
    """Lo que la corrida sostiene sobre el margen frente a las anti-dianas."""

    #: ΔG_off − ΔG_on, en kcal/mol. Positivo = la diana principal une más fuerte.
    delta_delta_g: float
    #: Anti-diana que define el margen (la que une más fuerte de todas).
    anti_diana: str | None
    #: Factor de selectividad implicado, y su intervalo por la dispersión de Vina.
    factor: float
    factor_min: float
    factor_max: float


def margen_de_selectividad(
    afinidad_on: float | None,
    afinidad_peor_off: float | None,
    anti_diana: str | None = None,
) -> MargenDeSelectividad | None:
    """ΔΔG y el factor que implica. `None` si falta alguna de las dos afinidades.

    A diferencia del cociente anterior, `afinidad_peor_off >= 0` NO es un caso
    degenerado: significa que la molécula no se une a la anti-diana, que es el
    mejor resultado posible, y produce un ΔΔG grande y positivo.
    """
    if afinidad_on is None or afinidad_peor_off is None:
        return None

    ddg = float(afinidad_peor_off) - float(afinidad_on)
    return MargenDeSelectividad(
        delta_delta_g=round(ddg, 2),
        anti_diana=anti_diana,
        factor=factor_de_selectividad(ddg),
        factor_min=factor_de_selectividad(ddg - INCERTIDUMBRE_VINA_KCAL),
        factor_max=factor_de_selectividad(ddg + INCERTIDUMBRE_VINA_KCAL),
    )


def factor_de_selectividad(delta_delta_g: float) -> float:
    """Cuántas veces más fuerte es la unión a la diana principal."""
    return float(10.0 ** (delta_delta_g / KCAL_POR_DECADA))


# ── La escala, en un solo sitio ────────────────────────────────────────────
#
# Los cortes están en órdenes de magnitud redondos, no en números elegidos a
# ojo: 2.73 kcal/mol son 100x, 1.36 son 10x, y 0 es «indistinguible».
#
# Ninguna etiqueta dice «seguro». Un margen in silico de dos órdenes con una
# incertidumbre de ±2 kcal/mol no autoriza esa palabra, y el panel de
# anti-dianas es justo donde no se puede insinuar.

#: (ΔΔG mínimo, veredicto). En orden descendente; el primero que se cumple gana.
ESCALA_DE_MARGEN: tuple[tuple[float, str], ...] = (
    (2.73, "MARGEN AMPLIO — la diana principal une ~100x más fuerte que la peor anti-diana"),
    (1.36, "MARGEN MODERADO — unas 10x a favor de la diana principal"),
    (0.41, "MARGEN ESTRECHO — menos de 10x; el orden puede invertirse dentro del error del método"),
    (0.00, "SIN MARGEN — afinidades indistinguibles entre diana y anti-diana"),
)

VEREDICTO_INVERTIDO = "MARGEN NEGATIVO — la molécula une más fuerte a una anti-diana que a su diana"
VEREDICTO_SIN_DATOS = "Sin datos suficientes"


def veredicto_de_margen(delta_delta_g: float | None) -> str:
    """El texto canónico. Sin API, sin base de datos, sin subprocesos."""
    if delta_delta_g is None:
        return VEREDICTO_SIN_DATOS
    if delta_delta_g < 0:
        return VEREDICTO_INVERTIDO
    for minimo, veredicto in ESCALA_DE_MARGEN:
        if delta_delta_g >= minimo:
            return veredicto
    return VEREDICTO_SIN_DATOS
