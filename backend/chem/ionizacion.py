"""
Estado de ionización a pH 7.4, y el LogD que se deriva de él.

# El fallo que arregla

`_calculate_cns_mpo` estimaba la lipofilia efectiva así:

    # 6. logD (approximated as logP - 0.5 for neutral compounds)
    logd_est = logp - 0.5

Un desplazamiento constante, con el propio comentario reconociendo que sólo
vale «for neutral compounds» — y aplicándolo a todas. En química médica del
sistema nervioso central eso es justo lo contrario del caso típico: la mayoría
de los fármacos que llegan al cerebro llevan una amina alifática básica
(pKa ≈ 9-10), que a pH 7.4 está protonada en más del 95 % y pierde entre 1.5 y
2.5 unidades de lipofilia, no 0.5.

El efecto tiene dos direcciones y las dos importan:

    amina básica (pKa 9.8)   LogD real ≈ LogP − 2.4    estimado LogP − 0.5
                             -> el MPO la premia por lipofílica cuando en
                                sangre está cargada: OPTIMISTA de más

    ácido carboxílico (4.2)  LogD real ≈ LogP − 3.2    estimado LogP − 0.5
                             -> mismo signo del error, y encima el ácido
                                ionizado tampoco cruza

Y el segundo problema: el MPO de Pfizer (Wager et al., ACS Chem. Neurosci.
2010) tiene SEIS términos —MW, cLogP, cLogD, TPSA, HBD y **pKa del centro más
básico**— y esta implementación había puesto el número de aceptores de enlace
de hidrógeno en el lugar del pKa. HBA no es un sustituto de pKa: mide otra cosa.

# Lo que este módulo NO es

No calcula pKa. Calcular un pKa de verdad requiere un modelo dedicado (Epik,
MoKa, o un predictor entrenado), y ninguno viaja en esta instalación.

Lo que hace es **reconocer la clase del centro ionizable por SMARTS y aplicar
el pKa representativo de esa clase**. Es una aproximación, y por eso cada
resultado viene con la lista de centros detectados y el pKa que se les asignó:
quien lea el número puede ver de dónde sale y descartarlo si su molécula no
encaja en la clase.

Los valores representativos son los de manual de química medicinal, no
ajustados a ningún conjunto de este proyecto:

    amina alifática primaria/secundaria/terciaria   pKa ≈ 9.8   base
    amidina / guanidina                             pKa ≈ 12.0  base
    imidazol                                        pKa ≈ 7.0   base
    piridina                                        pKa ≈ 5.2   base
    anilina                                         pKa ≈ 4.6   base
    ácido carboxílico                               pKa ≈ 4.2   ácido
    tetrazol                                        pKa ≈ 4.9   ácido
    sulfonamida (N-arilo)                           pKa ≈ 9.5   ácido
    fenol                                           pKa ≈ 10.0  ácido

# La ecuación

Henderson-Hasselbalch, para el centro dominante de cada signo:

    base   LogD = LogP − log10(1 + 10^(pKa − pH))
    ácido  LogD = LogP − log10(1 + 10^(pH − pKa))

Con centros de los dos signos se restan las dos correcciones: es la
aproximación habitual para un zwitterión y, como todo lo demás aquí, va
declarada.

# Lo que no es un pKa: la carga permanente

Un amonio cuaternario no tiene pKa, tiene carga. Lo mismo un sulfonato o un
fosfonato. No aparecían en ninguna parte de este módulo, así que `carga_neta`
los daba por neutros y el consenso de BBB los dejaba pasar — con
glicopirrolato, un antimuscarínico elegido en clínica **porque** su carga
permanente le impide entrar al cerebro, el veredicto salía «permeable».

Se reconocen aparte, por SMARTS, y se declaran en `cargas_permanentes`. La
distinción con la carga formal del SMILES es deliberada y está anotada sobre
`CARGAS_PERMANENTES`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

PH_FISIOLOGICO: float = 7.4


@dataclass(frozen=True)
class CentroIonizable:
    """Un grupo reconocido, con el pKa representativo de su clase."""

    nombre: str
    smarts: str
    pka: float
    #: "base" protona al bajar el pH; "acido" desprotona al subirlo.
    caracter: str


#: Ordenados por pKa descendente dentro de cada carácter: el centro dominante a
#: pH 7.4 es el de pKa más alto entre las bases y el más bajo entre los ácidos.
CENTROS: tuple[CentroIonizable, ...] = (
    # ── Bases ───────────────────────────────────────────────────────────
    CentroIonizable("guanidina", "[NX3][CX3](=[NX2])[NX3]", 12.0, "base"),
    CentroIonizable("amidina", "[NX3][CX3]=[NX2]", 11.5, "base"),
    # Aminas alifáticas: se excluyen amidas, sulfonamidas, anilinas y nitrilos.
    CentroIonizable(
        "amina_alifatica",
        "[NX3;H2,H1,H0;!$(N[a]);!$(N-[!#6]);!$(N[CX3]=[O,N,S]);!$(NC#N);!$(N=*);!$([N+])]",
        9.8,
        "base",
    ),
    CentroIonizable("imidazol", "c1cnc[nH]1", 7.0, "base"),
    CentroIonizable("piridina", "n1ccccc1", 5.2, "base"),
    # Se excluyen amidas y sulfonamidas: el N de una anilida —el del
    # paracetamol, sin ir más lejos— es H1 y cuelga de un anillo aromático, así
    # que encajaba en el patrón ingenuo `[NX3;H2,H1][a]`. Pero su pKa está en
    # torno a −1, no en 4.6: el carbonilo deslocaliza el par libre y ese
    # nitrógeno no se protona a ningún pH fisiológico.
    CentroIonizable(
        "anilina",
        "[NX3;H2,H1;!$(N[CX3]=[O,S,N]);!$(N[SX4](=O)=O);!$(N[a][a]=O)][a]",
        4.6,
        "base",
    ),
    # ── Ácidos ──────────────────────────────────────────────────────────
    CentroIonizable("acido_carboxilico", "[CX3](=O)[OX2H1]", 4.2, "acido"),
    CentroIonizable("tetrazol", "c1nnn[nH]1", 4.9, "acido"),
    CentroIonizable("sulfonamida_arilo", "[SX4](=O)(=O)[NX3;H1][a]", 9.5, "acido"),
    CentroIonizable("fosfato", "[PX4](=O)([OX2H1])", 2.0, "acido"),
    CentroIonizable("fenol", "[OX2H1][a]", 10.0, "acido"),
)

#: Cargas que NINGUN pH neutraliza, y por eso no son un centro ionizable: no
#: tienen un pKa, tienen una carga.
#:
#: LO QUE ARREGLA. `carga_neta` se calculaba SOLO desde los centros con pKa, asi
#: que un amonio cuaternario salia con carga cero — «neutro»— y el consenso de
#: BBB lo dejaba pasar. Medido con glicopirrolato (un antimuscarinico que se usa
#: precisamente porque su carga permanente le impide entrar al cerebro): el MPO
#: le daba 5.60 sobre 6 y el veredicto era «permeable». Es el peor error posible
#: del panel, porque la molecula es el ejemplo de manual de lo contrario.
#:
#: Se reconocen por SMARTS y no por `GetFormalCharge`, a proposito. Un usuario
#: que pega el SMILES de una amina ya protonada —`[NH2+]`, que es como salen de
#: muchas bases de datos— escribe una carga formal que a pH 7.4 es real pero NO
#: es permanente: esa molecula si difunde por su fraccion neutra. Bloquear por
#: carga formal convertiria la forma en que se escribio el SMILES en un veredicto.
CARGAS_PERMANENTES: tuple[tuple[str, str], ...] = (
    ("amonio_cuaternario", "[NX4+;H0]"),
    ("n_aromatico_cuaternizado", "[nX3+;H0]"),
    ("sulfonato", "[SX4](=O)(=O)[OX1-]"),
    ("fosfonato", "[PX4](=O)([OX1-])"),
)


@dataclass
class EstadoDeIonizacion:
    """Lo que se pudo determinar sobre la ionización a pH 7.4."""

    #: LogD estimado. `None` si no se pudo leer la molécula.
    logd: float | None
    #: Centros reconocidos, como `(nombre, pKa, carácter)`.
    centros: list[tuple[str, float, str]] = field(default_factory=list)
    #: Carga a pH 7.4: la formal del SMILES más la de los centros dominantes.
    carga_neta: int = 0
    #: Fracción ionizada del centro básico dominante (0-1). `None` si no hay.
    fraccion_base_ionizada: float | None = None
    #: Fracción ionizada del centro ácido dominante (0-1). `None` si no hay.
    fraccion_acido_ionizada: float | None = None
    #: pKa del centro más básico. Es el término del MPO de Pfizer.
    pka_mas_basico: float | None = None
    #: Carga formal del SMILES tal como se escribió, antes de aplicar el pH.
    carga_formal: int = 0
    #: Grupos de carga permanente reconocidos, por su nombre.
    cargas_permanentes: list[str] = field(default_factory=list)

    @property
    def tiene_carga_permanente(self) -> bool:
        """Una carga que ningún pH neutraliza: no difunde, y no hay matiz."""
        return bool(self.cargas_permanentes)

    @property
    def especie(self) -> str:
        """Cómo llamar a la especie dominante, para la interfaz."""
        if self.carga_neta > 0 and self.fraccion_acido_ionizada:
            return "zwitterión (neto +)"
        if self.carga_neta < 0 and self.fraccion_base_ionizada:
            return "zwitterión (neto −)"
        if self.carga_neta > 0:
            return f"catión +{self.carga_neta}"
        if self.carga_neta < 0:
            return f"anión {self.carga_neta}"
        if self.fraccion_base_ionizada and self.fraccion_acido_ionizada:
            return "zwitterión neutro"
        return "neutra"


def _fraccion_ionizada(pka: float, caracter: str, ph: float = PH_FISIOLOGICO) -> float:
    """Henderson-Hasselbalch: qué proporción está cargada a este pH."""
    if caracter == "base":
        # BH+ / (BH+ + B)
        return 1.0 / (1.0 + 10 ** (ph - pka))
    # A- / (A- + AH)
    return 1.0 / (1.0 + 10 ** (pka - ph))


def analizar_ionizacion(smiles: str, logp: float | None) -> EstadoDeIonizacion:
    """Reconoce los centros ionizables y deriva LogD a pH 7.4."""
    try:
        from rdkit import Chem
    except ImportError:
        return EstadoDeIonizacion(logd=logp)

    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return EstadoDeIonizacion(logd=logp)

    encontrados: list[tuple[str, float, str]] = []
    for centro in CENTROS:
        patron = Chem.MolFromSmarts(centro.smarts)
        if patron is None:
            continue
        if mol.HasSubstructMatch(patron):
            encontrados.append((centro.nombre, centro.pka, centro.caracter))

    permanentes: list[str] = []
    for nombre, smarts in CARGAS_PERMANENTES:
        patron = Chem.MolFromSmarts(smarts)
        if patron is not None and mol.HasSubstructMatch(patron):
            permanentes.append(nombre)

    bases = [c for c in encontrados if c[2] == "base"]
    acidos = [c for c in encontrados if c[2] == "acido"]

    # El centro dominante a pH 7.4: la base más fuerte y el ácido más fuerte.
    base_dominante = max(bases, key=lambda c: c[1]) if bases else None
    acido_dominante = min(acidos, key=lambda c: c[1]) if acidos else None

    estado = EstadoDeIonizacion(logd=logp, centros=encontrados)
    estado.pka_mas_basico = base_dominante[1] if base_dominante else None
    estado.cargas_permanentes = permanentes

    # La carga con la que llega el SMILES. `carga_neta` parte de aquí y no de
    # cero: una molécula escrita ya como catión o anión —un amonio cuaternario,
    # un sulfonato, una amina que la base de datos exportó protonada— tiene esa
    # carga antes de que el pH añada nada. Antes se ignoraba, y las especies
    # permanentemente cargadas salían con carga neta 0, es decir «neutras».
    estado.carga_formal = Chem.GetFormalCharge(mol)
    estado.carga_neta = estado.carga_formal

    if logp is None:
        return estado

    # ── La fracción neutra, con UN solo denominador ──────────────────────
    #
    # Sólo la especie neutra se reparte al octanol, así que
    #
    #     LogD = LogP + log10(f_neutra)
    #     f_neutra = 1 / (1 + 10^(pKa_base − pH) + 10^(pH − pKa_ácido))
    #
    # Los tres términos van en el MISMO denominador porque son las fracciones
    # de las microespecies, que suman uno. Sumar dos logaritmos por separado
    # —log(1+A) + log(1+B)— multiplica los denominadores en vez de sumarlos, y
    # para un zwitterión, donde A y B son ambos grandes, eso sobreestima la
    # corrección en órdenes de magnitud. Medido con levodopa: la forma
    # multiplicativa daba LogD −5.6 frente al −2.4 experimental; con el
    # denominador único queda en −3.2, dentro de lo que esta aproximación
    # puede sostener.
    denominador = 1.0
    if base_dominante:
        pka = base_dominante[1]
        denominador += 10 ** (pka - PH_FISIOLOGICO)
        estado.fraccion_base_ionizada = round(_fraccion_ionizada(pka, "base"), 3)
        if estado.fraccion_base_ionizada >= 0.5:
            estado.carga_neta += 1
    if acido_dominante:
        pka = acido_dominante[1]
        denominador += 10 ** (PH_FISIOLOGICO - pka)
        estado.fraccion_acido_ionizada = round(_fraccion_ionizada(pka, "acido"), 3)
        if estado.fraccion_acido_ionizada >= 0.5:
            estado.carga_neta -= 1

    estado.logd = round(logp - math.log10(denominador), 2)
    return estado


def desirabilidad_pka(pka_mas_basico: float | None) -> float:
    """El término de pKa del MPO de Pfizer, en [0, 1].

    Wager et al. penalizan las bases fuertes: un pKa alto significa que la
    molécula está cargada en sangre, y una especie cargada no atraviesa
    membranas por difusión pasiva. La rampa (1.0 hasta pKa 8, 0.0 desde 10)
    es la del artículo.

    Sin centro básico el término vale 1.0: no hay nada que penalizar.
    """
    if pka_mas_basico is None:
        return 1.0
    if pka_mas_basico <= 8.0:
        return 1.0
    if pka_mas_basico >= 10.0:
        return 0.0
    return round((10.0 - pka_mas_basico) / 2.0, 3)


# ═════════════════════════════════════════════════════════════════════════
# Cuál de los microestados de dimorphite-dl se acopla
# ═════════════════════════════════════════════════════════════════════════
#
# Auditoría de backend del 2026-09-04, §2.4. `chem/conformer.py` hacía:
#
#     protonated_list = dimorphite_dl.protonate_smiles(canonical, ph 7.4)
#     canonical = protonated_list[0]
#
# La lista no viene ordenada por población. Medido con la versión empaquetada,
# a pH 7.4 exacto:
#
#     propranolol   [0] CC(C)NCC(O)COc1cccc2ccccc12        <- amina NEUTRA
#                   [1] CC(C)[NH2+]CC(O)COc1cccc2ccccc12
#
#     histidina     [0] N[C@@H](Cc1c[n-]cn1)C(=O)[O-]      <- imidazolato Y
#                   ...                                       amina neutra
#                   [3] [NH3+][C@@H](Cc1c[nH]cn1)C(=O)[O-]
#
# El propranolol es una amina secundaria con pKa ≈ 9.5: a pH 7.4 está protonada
# en más del 99 %, y se estaba acoplando la forma neutra. La histidina salía con
# un imidazolato —una especie que a pH 7.4 no existe en cantidad apreciable— y
# la amina sin protonar. Eso no se queda en el panel: el microestado elegido es
# el que va a Meeko y a Vina, y la carga cambia el tipo de átomo y la
# electrostática de la pose.
#
# LO QUE HACE ESTA FUNCIÓN. No calcula pKa —esta instalación no lleva un
# predictor, y eso ya está dicho arriba—: usa la MISMA tabla `CENTROS` del resto
# del módulo, cuenta cuántos centros de cada carácter deberían estar cargados a
# pH 7.4 por Henderson-Hasselbalch, y se queda con el microestado cuyos
# recuentos de carga formal más se parecen. Compara CUÁNTAS cargas hay, no en
# qué átomo están.
#
# LO QUE NO ARREGLA, comprobado antes de escribirla. Con imatinib la tabla da
# 9.8 a los dos nitrógenos de la piperazina y predice el dicatión; el real es
# monocatión (el N-metilo tiene pKa ≈ 7.7 y el bencílico ≈ 3.7, deprimido por el
# nitrógeno vecino). Ahí el resultado es el mismo que daba `[0]`: la clase es
# demasiado gruesa para esa molécula, que es la limitación declarada de toda la
# tabla. No empeora nada; simplemente no lo resuelve.
#
# Cuando no se reconoce ningún centro, o RDKit falla, se conserva `[0]` y se
# dice por qué. Un cambio silencioso de criterio sería peor que el criterio malo.


def _centros_por_instancia(mol) -> list[tuple[str, float, str]]:
    """Los centros de `CENTROS` que casan, contando cada aparición.

    `analizar_ionizacion` usa `HasSubstructMatch` porque sólo necesita saber qué
    clases hay. Aquí hacen falta los recuentos: la lisina tiene DOS aminas
    alifáticas y a pH 7.4 las dos están protonadas.

    Las clases se recorren en el orden de `CENTROS` —bases de pKa descendente,
    luego ácidos— y un átomo ya reclamado por una clase no vuelve a contarse.
    Eso resuelve los solapamientos en la dirección correcta: el nitrógeno de una
    guanidina también casa con `amina_alifatica`, y guanidina va antes.
    """
    from rdkit import Chem

    reclamados: set[int] = set()
    encontrados: list[tuple[str, float, str]] = []

    for centro in CENTROS:
        patron = Chem.MolFromSmarts(centro.smarts)
        if patron is None:
            continue
        for coincidencia in mol.GetSubstructMatches(patron):
            atomos = set(coincidencia)
            if atomos & reclamados:
                continue
            reclamados |= atomos
            encontrados.append((centro.nombre, centro.pka, centro.caracter))

    return encontrados


def cargas_esperadas_a_ph(smiles: str, ph: float = PH_FISIOLOGICO) -> tuple[int, int] | None:
    """(centros catiónicos, centros aniónicos) esperados a ese pH.

    `None` si no se puede leer la molécula o no se reconoce ningún centro: sin
    centros no hay nada que comparar, y devolver (0, 0) afirmaría que la
    molécula es neutra cuando lo que pasa es que no se sabe.

    El pH es un PARÁMETRO desde que el usuario puede elegirlo en las opciones
    avanzadas. Antes estaba escrito a mano en las dos llamadas de abajo, y ése
    es exactamente el acoplamiento que hacía imposible exponerlo: dimorphite
    enumeraba las especies del pH pedido y esta función seguía prediciendo las
    de 7.4, así que el selector elegía la más parecida al pH equivocado.
    """
    try:
        from rdkit import Chem
    except ImportError:
        return None

    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return None

    centros = _centros_por_instancia(mol)
    if not centros:
        return None

    positivos = sum(
        1
        for _, pka, caracter in centros
        if caracter == "base" and _fraccion_ionizada(pka, "base", ph) >= 0.5
    )
    negativos = sum(
        1
        for _, pka, caracter in centros
        if caracter == "acido" and _fraccion_ionizada(pka, "acido", ph) >= 0.5
    )
    return positivos, negativos


def _cargas_formales(smiles: str) -> tuple[int, int] | None:
    """(átomos con carga +, átomos con carga −) de un SMILES ya protonado."""
    try:
        from rdkit import Chem
    except ImportError:
        return None

    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return None

    positivos = sum(1 for a in mol.GetAtoms() if a.GetFormalCharge() > 0)
    negativos = sum(1 for a in mol.GetAtoms() if a.GetFormalCharge() < 0)
    return positivos, negativos


def elegir_microestado(
    smiles_neutro: str,
    microestados: list[str],
    ph: float = PH_FISIOLOGICO,
) -> tuple[str, dict]:
    """Escoge el microestado más cercano al estado predicho a ese pH.

    Devuelve `(smiles_elegido, criterio)`, donde `criterio` es lo que se guarda
    en `estado_del_ligando` para que el dossier pueda decir por qué se acopló
    esa especie y no otra.
    """
    if not microestados:
        return smiles_neutro, {"criterio": "sin_microestados", "indice": None}

    esperadas = cargas_esperadas_a_ph(smiles_neutro, ph)
    if esperadas is None:
        return microestados[0], {
            "criterio": "primero_de_la_lista",
            "indice": 0,
            "motivo": (
                "No se reconoció ningún centro ionizable de la tabla de clases, "
                "así que no hay estado esperado con el que comparar."
            ),
        }

    pos_esperados, neg_esperados = esperadas

    # ── El desempate NO puede heredar el orden de dimorphite ──────────────
    #
    # Medido antes de escribir esto, ejecutando cinco veces el mismo SMILES en
    # procesos separados: `protonate_smiles` devuelve la lista en un orden
    # DISTINTO cada vez. `[0]` dio cuatro microestados diferentes para la
    # lisina y tres para la histidina en cinco corridas.
    #
    # Eso es lo peor del hallazgo original y la auditoría no lo vio: no era sólo
    # que `[0]` fuera arbitrario, es que era arbitrario DE FORMA DISTINTA en
    # cada corrida. El microestado elegido se canoniza y se vuelve a hashear
    # (ver `chem/conformer.py`), así que la misma molécula podía producir dos
    # `smiles_hash`, dos archivos de conformer, dos entradas de caché de
    # acoplamiento y dos afinidades, sin nada en el registro que lo dijera.
    #
    # Por eso el candidato se elige por `(distancia, smiles)` y no por la
    # posición: dos microestados que empatan en distancia se ordenan por su
    # cadena, que es una propiedad de la molécula y no de la corrida. El
    # resultado es reproducible aunque dimorphite baraje.
    candidatos: list[tuple[int, str]] = []
    for candidato in microestados:
        cargas = _cargas_formales(candidato)
        if cargas is None:
            continue
        distancia = abs(cargas[0] - pos_esperados) + abs(cargas[1] - neg_esperados)
        candidatos.append((distancia, candidato))

    if not candidatos:
        return microestados[0], {
            "criterio": "primero_de_la_lista",
            "indice": 0,
            "motivo": "Ningún microestado se pudo leer con RDKit.",
        }

    mejor_distancia, elegido = min(candidatos)

    return elegido, {
        # El nombre del criterio lleva el pH REAL, no el fisiológico escrito a
        # mano: es lo que se guarda en el expediente y lo que alguien va a leer
        # dentro de un año para saber qué especie se acopló.
        "criterio": f"cargas_esperadas_ph_{ph:g}",
        "ph": ph,
        "cationes_esperados": pos_esperados,
        "aniones_esperados": neg_esperados,
        "desajuste": mejor_distancia,
        # Cuántos empataron en distancia. Si es > 1, el desempate lo hizo el
        # orden alfabético y no la química: se declara para que se vea.
        "empatados": sum(1 for d, _ in candidatos if d == mejor_distancia),
        "motivo": (
            "Se comparan los recuentos de carga formal de cada microestado con "
            f"los centros que Henderson-Hasselbalch predice ionizados a pH {ph:g}, "
            "usando los pKa por clase de este módulo. Los empates se rompen por "
            "orden alfabético del SMILES, no por el orden de dimorphite-dl, que "
            "no es reproducible entre corridas."
        ),
    }
