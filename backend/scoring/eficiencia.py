"""Eficiencia de ligando normalizada por tamaño: Reynolds y Nissink.

# Por qué hace falta

`|afinidad| / átomos_pesados` —la eficiencia de ligando de Hopkins, Groom,
Alex, *Drug Discov. Today* 9 (2004) 430— depende del tamaño de forma
sistemática: es una división por el número de átomos, así que un corte fijo
exige una afinidad que crece linealmente con la molécula. Medido sobre este
producto antes de corregirlo:

    átomos    LE > 0.45 exige      LE < 0.25 si
         6      |aff| > 2.7          < 1.5
        13      |aff| > 5.9          < 3.2
        37      |aff| > 16.7         < 9.2
        50      |aff| > 22.5         < 12.5

Vina no baja de unos −12 kcal/mol. Un fragmento superaba el corte alto con
cualquier acoplamiento útil y una molécula de 50 átomos no podía alcanzarlo
nunca. La corrección provisional fue dejar de emitir el veredicto donde el
umbral no discrimina (ver `utils/scientific.py`). Este módulo implementa lo que
la literatura propone en su lugar.

# Fit Quality — Reynolds, Tounge, Bembenek, *J. Med. Chem.* 51 (2008) 2432

Ajustan la eficiencia de ligando MÁXIMA observada en función del tamaño, y
normalizan contra ella (ecuaciones 1-2 del artículo):

    LE_scale(HA) = 0.0715 + 7.5328/HA + 25.7079/HA² − 361.4722/HA³
    FQ = LE / LE_scale(HA)

FQ ≈ 1 significa que la molécula está cerca de la envolvente eficiente del
conjunto de Reynolds **para su tamaño**. No es una probabilidad de unión, ni
una medida de calidad de pose, ni un veredicto.

**Los coeficientes se verificaron contra la tabla 3 del artículo** antes de
escribirlos aquí, y la comprobación vive en
`tests/test_eficiencia_normalizada.py`:

    HA    calculado    tabla 3     delta
    20     0.467226     0.4672    +2.6e-05
    30     0.337770     0.3378    −3.0e-05
    40     0.270239     0.2702    +3.9e-05
    50     0.229547     0.2295    +4.7e-05

Reproduce las cuatro filas dentro del redondeo. El signo negativo del término
cúbico es inequívoco: con el signo cambiado, HA=20 daría 0.5576 en vez de
0.4672.

**El rango de validez del ajuste es 10-50 átomos pesados**, y los autores
recomiendan sujetar la escala fuera de él: `LE_scale(15)` para HA ≤ 15 y
`LE_scale(50)` para HA > 50. Se aplica, y el hecho de que se haya aplicado
viaja en el resultado (`escala_sujetada`) en vez de quedar implícito.

# SILE — Nissink, *J. Chem. Inf. Model.* 49 (2009) 1617

    SILE = Afinidad / HA^0.3

El exponente es exactamente 0.3. Nissink señala que la corrección también sirve
para estimaciones in silico y de acoplamiento, que es el uso de aquí. **No
publica un umbral universal**, así que este módulo no inventa ninguno: devuelve
el número y nada más.

# La parte que NO es de la literatura: usar Vina como proxy de pKi

Reynolds ajustó `LE_scale` contra afinidades experimentales (Ki), no contra
scores de acoplamiento. El artículo sugiere que la escala puede resultar útil
con scores de docking pero no publica una calibración específica para Vina.

Por eso el resultado se llama **`fq_vina_proxy`** y no `fit_quality` a secas.
El nombre carga la advertencia: es la escala de Reynolds evaluada sobre un
proxy, no la métrica que el artículo valida.

La conversión de kcal/mol a unidades de pKi usa 1.37, que es el valor
convencional en química medicinal (RT·ln 10, ~299 K). Medido contra la propia
tabla 3 —dividiendo su columna en kcal entre la columna en pKi— el factor
implícito del artículo es 1.36788, un 0.15 % menor. La diferencia es
irrelevante frente a la incertidumbre de tratar un score de Vina como un pKi,
pero se deja escrita para que nadie la descubra como si fuera un error.

# Lo que estas métricas NO arreglan

Corrigen el sesgo de tamaño de LE mucho mejor que `|Vina|/HA`. No corrigen una
pose equivocada, un receptor equivocado, la incertidumbre de la propia función
de Vina, ni la procedencia. Y existe discusión metodológica posterior sobre si
merecen llamarse «independientes del tamaño».

Encajan como métricas normalizadas y auditables. No como veredictos, y por eso
**ninguna entra en `total_score`**: primero hay que comprobar sobre la cohorte
de Vina de este proyecto si de verdad reducen la dependencia con HA.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# ── Reynolds et al. 2008, ecuaciones 1-2 ─────────────────────────────────
#
# Verificados contra la tabla 3 del artículo. Ver el docstring del módulo y
# `tests/test_eficiencia_normalizada.py`, que falla si alguno cambia.
REYNOLDS_A0 = 0.0715
REYNOLDS_A1 = 7.5328
REYNOLDS_A2 = 25.7079
REYNOLDS_A3 = -361.4722

#: Rango de átomos pesados del ajuste de Reynolds. Fuera de él la escala se
#: sujeta al extremo correspondiente, como recomiendan los autores.
REYNOLDS_HA_MIN = 15
REYNOLDS_HA_MAX = 50

#: Exponente de SILE (Nissink 2009). Exactamente 0.3.
SILE_EXPONENTE = 0.3

#: kcal/mol por unidad logarítmica de afinidad. Convencional en química
#: medicinal; el factor implícito en la tabla 3 de Reynolds es 1.36788.
KCAL_POR_UNIDAD_LOG = 1.37


@dataclass(frozen=True)
class MetricasDeEficiencia:
    """Las tres métricas, con de dónde sale cada una.

    La procedencia viaja con el número a propósito: un FQ suelto en un dossier
    no dice en qué unidades está, con qué escala se normalizó, ni que la
    afinidad de partida es un proxy.
    """

    #: El score de Vina tal cual, sin transformar. Nunca el pKi de XGBoost.
    vina_affinity_kcal: float
    heavy_atoms: int

    #: |Vina| / HA. La métrica clásica, dependiente del tamaño.
    ligand_efficiency_vina: float
    #: |Vina| / HA^0.3 (Nissink 2009). Sin umbral: el artículo no publica uno.
    sile_vina: float
    #: LE / LE_scale (Reynolds 2008), sobre un proxy de pKi. Ver el módulo.
    fq_vina_proxy: float

    #: El valor de LE_scale usado, en unidades de pKi.
    le_scale_pki: float
    #: Si HA cayó fuera del rango 15-50 del ajuste y la escala se sujetó.
    escala_sujetada: bool
    #: Qué HA se usó para la escala (sujetado o no).
    ha_para_la_escala: int

    #: Referencias y fórmulas, para el dossier.
    procedencia: dict[str, str]

    def to_dict(self) -> dict:
        return asdict(self)


def le_scale_pki(heavy_atoms: int) -> tuple[float, bool, int]:
    """La escala de Reynolds, en unidades de pKi por átomo pesado.

    Devuelve `(escala, se_sujeto, ha_usado)`. El ajuste cubre 10-50 átomos y
    los autores recomiendan usar `LE_scale(15)` por debajo de 15 y
    `LE_scale(50)` por encima de 50; extrapolar el polinomio fuera de ahí lo
    dispara —el término en 1/HA³ domina— y produce escalas sin sentido.
    """
    ha = int(heavy_atoms)
    sujetado = False
    if ha < REYNOLDS_HA_MIN:
        ha = REYNOLDS_HA_MIN
        sujetado = True
    elif ha > REYNOLDS_HA_MAX:
        ha = REYNOLDS_HA_MAX
        sujetado = True

    escala = (
        REYNOLDS_A0
        + REYNOLDS_A1 / ha
        + REYNOLDS_A2 / ha**2
        + REYNOLDS_A3 / ha**3
    )
    return escala, sujetado, ha


def calcular(vina_affinity_kcal: float, heavy_atoms: int) -> MetricasDeEficiencia | None:
    """Las tres métricas a partir del score de Vina SIN transformar.

    `vina_affinity_kcal` tiene que ser la afinidad del acoplamiento, negativa.
    NO el equivalente en kcal de la regresión de XGBoost: esa es otra cantidad,
    con otro error y otro dominio, y confundirlas fue un defecto real de este
    producto (ver `db/repository.py`, columna `ml_pki`).

    Devuelve `None` si no hay con qué calcular, en vez de un cero.
    """
    if not heavy_atoms or heavy_atoms <= 0:
        return None
    if vina_affinity_kcal is None:
        return None

    # Vina da energías negativas; las métricas se definen sobre la magnitud.
    magnitud_kcal = abs(float(vina_affinity_kcal))

    le_vina = magnitud_kcal / heavy_atoms
    sile = magnitud_kcal / (heavy_atoms**SILE_EXPONENTE)

    # A unidades de pKi, que es donde vive la escala de Reynolds.
    pki_proxy = magnitud_kcal / KCAL_POR_UNIDAD_LOG
    le_pki = pki_proxy / heavy_atoms
    escala, sujetado, ha_escala = le_scale_pki(heavy_atoms)
    fq = le_pki / escala

    return MetricasDeEficiencia(
        vina_affinity_kcal=float(vina_affinity_kcal),
        heavy_atoms=int(heavy_atoms),
        ligand_efficiency_vina=round(le_vina, 4),
        sile_vina=round(sile, 4),
        fq_vina_proxy=round(fq, 4),
        le_scale_pki=round(escala, 6),
        escala_sujetada=sujetado,
        ha_para_la_escala=ha_escala,
        procedencia={
            "afinidad": (
                "AutoDock Vina, kcal/mol, score sin transformar. No es energía "
                "libre ni se traduce a una concentración."
            ),
            "ligand_efficiency_vina": (
                "|Vina| / átomos pesados. Hopkins, Groom, Alex, Drug Discov. "
                "Today 9 (2004) 430. Depende del tamaño por construcción."
            ),
            "sile_vina": (
                f"|Vina| / HA^{SILE_EXPONENTE}. Nissink, J. Chem. Inf. Model. "
                "49 (2009) 1617. El artículo no publica un umbral universal, "
                "así que aquí no hay ninguno."
            ),
            "fq_vina_proxy": (
                "LE / LE_scale(HA), con LE_scale = 0.0715 + 7.5328/HA + "
                "25.7079/HA² − 361.4722/HA³ (Reynolds, Tounge, Bembenek, "
                "J. Med. Chem. 51 (2008) 2432, ec. 1-2). PROXY: Reynolds ajustó "
                "la escala contra Ki experimental, no contra scores de "
                f"acoplamiento; aquí se convierte Vina a pKi con "
                f"{KCAL_POR_UNIDAD_LOG} kcal/mol por unidad log. FQ ≈ 1 es "
                "proximidad a la envolvente eficiente del conjunto de Reynolds "
                "para ese tamaño, no probabilidad de unión ni calidad de pose."
            ),
            "rango_del_ajuste": (
                f"El ajuste de Reynolds cubre {REYNOLDS_HA_MIN}-{REYNOLDS_HA_MAX} "
                "átomos pesados; fuera de ese rango la escala se sujeta al "
                "extremo, como recomiendan los autores. `escala_sujetada` dice "
                "si ocurrió."
            ),
        },
    )
