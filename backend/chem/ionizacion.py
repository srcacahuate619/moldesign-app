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

Los valores representativos combinan clases de manual y medidas publicadas
para esqueletos estrechos. Ninguno se ajustó a datos de este proyecto. Los
nuevos grupos con medida llevan DOI junto a su SMARTS; los reconocidos sin
constante verificable se declaran aparte:

    amina alifática primaria/secundaria/terciaria   pKa ≈ 9.8   base
    amidina / guanidina                             pKa ≈ 12.0  base
    imidazol                                        pKa ≈ 7.0   base
    piridina                                        pKa ≈ 5.2   base
    anilina                                         pKa ≈ 4.6   base
    ácido carboxílico                               pKa ≈ 4.2   ácido
    tetrazol                                        pKa ≈ 4.9   ácido
    sulfonamida (N-arilo)                           pKa ≈ 9.5   ácido
    ArSO2NH2 (celecoxib)                            pKa = 9.525 ácido
    ArSO2NHCONH (glimepirida)                       pKa = 5.32  ácido
    monoéster fosfato                               pKa = 1.1/6.36 ácido
    biguanida                                       pKa = 10.57 base, REVISIÓN
    N-cianoguanidina, imida N-H                     sin pKa verificado
    fenol                                           pKa ≈ 10.0  ácido

# La ecuación

Henderson-Hasselbalch, para el centro dominante de cada signo:

    base   LogD = LogP − log10(1 + 10^(pKa − pH))
    ácido  LogD = LogP − log10(1 + 10^(pH − pKa))

Con centros de ambos signos se usa un denominador compartido para las
microespecies. Para monoésteres de fosfato se añade el segundo término de
acidez. Sigue siendo una aproximación de clase, no un LogD medido.

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
    # Biguanida: un solo grupo conjugado, no una guanidina + amidina.
    # Abdelrahman et al. (2021), DOI 10.3390/molecules26164730, midieron
    # pKa 10.57 y 8.00 a 25 C, I=0.1 M. Langmaier et al. (2016) respaldan
    # el monocatión en un rango amplio. Como discrepan en la segunda carga,
    # el selector marca REVIEW para esta clase.
    CentroIonizable(
        "biguanida", "[N;!a]~[C;X3](~[N;!a])~[N;!a]~[C;X3](~[N;!a])~[N;!a]",
        10.57, "base",
    ),
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
    # Dos tautómeros prototrópicos del tetrazol; un mismo anillo se reclama
    # una sola vez en _explorar_centros aunque encajen ambas representaciones.
    CentroIonizable("tetrazol", "c1nnn[nH]1", 4.9, "acido"),
    CentroIonizable("tetrazol", "c1nn[nH]n1", 4.9, "acido"),
    # Caine et al. (2019), DOI 10.1039/c9sc01818b: celecoxib 9.525,
    # glimepirida 5.32. Sólo se aplican a los esqueletos estudiados.
    CentroIonizable("sulfonilurea_arilo", "[c][SX4](=O)(=O)[NX3;H1][CX3](=O)[NX3]", 5.32, "acido"),
    CentroIonizable("sulfonamida_primaria_arilo", "[c][SX4](=O)(=O)[NX3;H2]", 9.525, "acido"),
    CentroIonizable("sulfonamida_arilo", "[SX4](=O)(=O)[NX3;H1][a]", 9.5, "acido"),
    # Methyl phosphate: 1.1 +/- 0.2 y 6.36 +/- 0.01 a 25 C, I=0.1 M
    # (Saha et al., 1996, DOI 10.1007/s007750050048; dato tabulado
    # por Sigel et al., 2022, DOI 10.3390/molecules27092625).
    # El segundo protón se registra sobre el MISMO fósforo de forma explícita.
    CentroIonizable("fosfato_monoester", "[PX4](=O)([O;H1,-1])([O;H1,-1])[OX2][#6]", 1.1, "acido"),
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
# Durant et al. (1977), DOI 10.1021/jm00217a007, observan que el
# sustituyente ciano reduce la basicidad de la guanidina. Su abstract no
# determina un pKa acuoso; se suprime el falso positivo guanidina y se declara
# que esta clase carece de constante cuantitativa verificada.
CLASES_SIN_PKA: tuple[tuple[str, str], ...] = (
    ("n_cianoguanidina", "[NX3][CX3](=[NX2])[NX3]C#N"),
    ("imida_no_calibrada", "[CX3](=O)[NX3;H1][CX3]=O"),
)

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
    #: False si la enumeración de tautómeros falló o alcanzó el tope.
    centros_completos: bool = True
    clases_sin_pka: list[str] = field(default_factory=list)
    quimica_resuelta: bool = True

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

    centros_por_grupo, barrido_completo = _explorar_centros(mol)
    clases_sin_pka = _clases_sin_pka(mol)
    # El panel muestra clases, no el número de instancias de cada clase.
    encontrados = list(dict.fromkeys(centros_por_grupo)) if barrido_completo else []

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

    estado = EstadoDeIonizacion(logd=logp if barrido_completo else None,
                                centros=encontrados)
    estado.centros_completos = barrido_completo
    estado.clases_sin_pka = clases_sin_pka
    estado.quimica_resuelta = barrido_completo and not clases_sin_pka and not any(
        centro[0] == "biguanida" for centro in encontrados
    )
    estado.pka_mas_basico = base_dominante[1] if base_dominante else None
    estado.cargas_permanentes = permanentes

    # La carga con la que llega el SMILES. `carga_neta` parte de aquí y no de
    # cero: una molécula escrita ya como catión o anión —un amonio cuaternario,
    # un sulfonato, una amina que la base de datos exportó protonada— tiene esa
    # carga antes de que el pH añada nada. Antes se ignoraba, y las especies
    # permanentemente cargadas salían con carga neta 0, es decir «neutras».
    estado.carga_formal = Chem.GetFormalCharge(mol)
    estado.carga_neta = estado.carga_formal
    # El grupo bifásico puede llegar ya como monoanión o dianión. Su carga
    # formal se quita de la base antes de aplicar la población a pH 7.4;
    # de otro modo la entrada dianión terminaba falsamente en −4.
    patron_fosfato = Chem.MolFromSmarts(
        "[PX4](=O)([O;H1,-1])([O;H1,-1])[OX2][#6]"
    )
    indices_fosfato = {
        indice
        for coincidencia in mol.GetSubstructMatches(patron_fosfato)
        for indice in coincidencia[2:4]
        if mol.GetAtomWithIdx(indice).GetFormalCharge() < 0
    }
    estado.carga_neta += len(indices_fosfato)

    if not barrido_completo or logp is None:
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
        if any(c[0] == "fosfato_monoester_segunda" for c in acidos):
            segundo = 6.36
            denominador += 10 ** (2 * PH_FISIOLOGICO - pka - segundo)
            if _fraccion_ionizada(segundo, "acido") >= 0.5:
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
# Si no hay centro reconocido, el fallback es el menor SMILES canónico, no
# la posición de Dimorphite. Si se reconoce un grupo sin pKa, se minimiza la
# carga formal y se declara REVIEW. Ningún orden alfabético estima poblaciones.


def _clases_sin_pka(mol) -> list[str]:
    """Grupos reconocidos cualitativamente sin constante acuosa fiable."""
    from rdkit import Chem
    return [
        nombre for nombre, smarts in CLASES_SIN_PKA
        if mol.HasSubstructMatch(Chem.MolFromSmarts(smarts))
    ]


def _explorar_centros(mol) -> tuple[list[tuple[str, float, str]], bool]:
    """Centros sobre la entrada y los tautómeros del tetrazol, sin doble conteo.

    RDKit conserva los índices de los átomos pesados al tautomerizar. Sólo se
    aplican patrones sobre esos tautómeros cuando la clase es químicamente
    invariante bajo el cambio; el tetrazol 1H/2H es el caso medido aquí.
    """
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    from chem.declaracion_tautomeros import MAX_TAUTOMEROS

    # Buscar en todos los tautómeros sólo está validado para el tetrazol.
    # Un barrido indiscriminado produce un falso positivo: el tautómero imídico
    # del paracetamol presenta su N amídico como si fuera una amina básica.
    # Para las demás clases se conserva el grafo de entrada hasta contar con
    # reglas de equivalencia química por grupo, no sólo coincidencia SMARTS.
    hay_tetrazol = any(
        len(anillo) == 5 and sorted(mol.GetAtomWithIdx(i).GetAtomicNum() for i in anillo)
        == [6, 7, 7, 7, 7]
        for anillo in mol.GetRingInfo().AtomRings()
    )
    formas = [mol]
    completo = True
    if hay_tetrazol:
        parametros = rdMolStandardize.CleanupParameters()
        parametros.tautomerRemoveSp3Stereo = False
        parametros.maxTautomers = MAX_TAUTOMEROS
        try:
            resultado = rdMolStandardize.TautomerEnumerator(parametros).Enumerate(mol)
            completo = resultado.status == rdMolStandardize.TautomerEnumeratorStatus.Completed
            formas.extend(resultado.tautomers)
        except Exception:
            completo = False

    reclamados: set[int] = set()
    for _, smarts in CLASES_SIN_PKA:
        for coincidencia in mol.GetSubstructMatches(Chem.MolFromSmarts(smarts)):
            reclamados.update(coincidencia)
    encontrados: list[tuple[str, float, str]] = []
    for centro in CENTROS:
        patron = Chem.MolFromSmarts(centro.smarts)
        if patron is None:
            continue
        coincidencias = sorted({
            tuple(sorted(coincidencia))
            for forma in (formas if centro.nombre == "tetrazol" else [mol])
            for coincidencia in forma.GetSubstructMatches(patron)
        })
        for coincidencia in coincidencias:
            atomos = set(coincidencia)
            if atomos & reclamados:
                continue
            reclamados.update(atomos)
            encontrados.append((centro.nombre, centro.pka, centro.caracter))
            if centro.nombre == "fosfato_monoester":
                encontrados.append(("fosfato_monoester_segunda", 6.36, "acido"))
    return encontrados, completo


def _centros_por_instancia(mol) -> list[tuple[str, float, str]]:
    """Centros por grupo; una enumeración incompleta no permite predecirlos."""
    encontrados, completo = _explorar_centros(mol)
    return encontrados if completo else []


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

    centros, barrido_completo = _explorar_centros(mol)
    if not barrido_completo or not centros:
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

    # Dimorphite puede variar el orden y la grafía de los SMILES entre procesos.
    # La identidad de cada candidato se fija con RDKit ANTES de elegir, también
    # cuando la tabla de pKa no reconoce ningún centro.
    try:
        from rdkit import Chem
    except ImportError:
        Chem = None
    canonicos = sorted({
        Chem.MolToSmiles(mol, isomericSmiles=True)
        for estado in microestados
        if Chem is not None and (mol := Chem.MolFromSmiles(estado)) is not None
    })
    entrada = Chem.MolFromSmiles(smiles_neutro) if Chem is not None else None
    clases_sin_pka = _clases_sin_pka(entrada) if entrada is not None else []
    if clases_sin_pka and entrada is not None:
        # Dimorphite puede no ofrecer la forma neutra de N-cianoguanidina.
        # La entrada del investigador sí es un candidato auditable.
        canonicos = sorted(set(canonicos) | {Chem.MolToSmiles(entrada, isomericSmiles=True)})
    if not canonicos:
        return smiles_neutro, {
            "criterio": "sin_microestados_validos",
            "indice": None,
            "alternativas_recibidas": len(microestados),
            "motivo": "Ninguna alternativa pudo validarse con RDKit; se conserva la entrada.",
        }

    biguanida_en_revision = bool(
        entrada is not None and any(c[0] == "biguanida" for c in _centros_por_instancia(entrada))
    )
    esperadas = cargas_esperadas_a_ph(smiles_neutro, ph)
    if esperadas is None:
        # Una imida/cianoguanidina reconocida sin pKa no se trata como
        # "sin centro" ordinario: se minimiza la carga formal y se avisa.
        candidato = min(canonicos, key=lambda smi: (sum(_cargas_formales(smi)), smi)) if clases_sin_pka else canonicos[0]
        return candidato, {
            "criterio": "grupo_reconocido_sin_pka" if clases_sin_pka else "primer_smiles_alfabetico_sin_centros",
            "clases_sin_pka": clases_sin_pka,
            "indice": None,
            "ph": ph,
            "empatados": len(canonicos),
            "quimica_resuelta": False,
            "motivo": (
                "Hay un grupo reconocido sin pKa verificable; se minimizó la carga formal "
                "entre alternativas y entrada, con resultado en revisión."
                if clases_sin_pka else
                "No se reconoció ningún centro ionizable de la tabla de clases. "
                "Se eligió el menor SMILES canónico para reproducibilidad; "
                "el orden alfabético no estima la población química."
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
    for candidato in canonicos:
        cargas = _cargas_formales(candidato)
        if cargas is None:
            continue
        distancia = abs(cargas[0] - pos_esperados) + abs(cargas[1] - neg_esperados)
        candidatos.append((distancia, candidato))

    if not candidatos:
        return smiles_neutro, {
            "criterio": "sin_microestados_validos",
            "indice": None,
            "alternativas_recibidas": len(microestados),
            "motivo": "Ninguna alternativa pudo evaluarse con RDKit; se conserva la entrada.",
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
        "clases_sin_pka": clases_sin_pka,
        "quimica_resuelta": not clases_sin_pka and not biguanida_en_revision and mejor_distancia == 0 and sum(1 for d, _ in candidatos if d == mejor_distancia) == 1,
        "revision_biguanida": biguanida_en_revision,
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
