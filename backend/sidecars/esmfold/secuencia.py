"""
De SMILES de péptido a secuencia, con su quiralidad.

═══════════════════════════════════════════════════════════════════════════
LO QUE HABÍA, Y POR QUÉ NO PODÍA FUNCIONAR NUNCA
═══════════════════════════════════════════════════════════════════════════

`ESMFoldFastPredictor._smiles_to_aa_sequence` es un `@staticmethod` que hacía:

    aa_patterns = {aa: Chem.MolFromSmarts(s) for aa, s in _AA_SMARTS.items()}

`_AA_SMARTS` está definido como ATRIBUTO DE CLASE. Un nombre suelto dentro de
un método estático no resuelve contra el cuerpo de la clase, así que esa línea
levantaba `NameError: name '_AA_SMARTS' is not defined` **en toda llamada, para
todo péptido**. El motor peptídico de ESMFold no ha extraído una secuencia
jamás: fallaba en su primer paso y la corrida caía al respaldo de Vina.

Y arreglar sólo el `NameError` habría sido peor que dejarlo, porque la tabla a
la que apunta tiene TRES residuos de veinte:

    "A": "[CX4]([H])([H])[H]"          metilo
    "R": "[NX3][CX4][CX4][CX4][NX3]"
    "N": "[NX3][CX3](=[OX1])"          ← esto casa con CUALQUIER amida,
                                         empezando por el propio esqueleto

Con eso, un péptido real habría devuelto una secuencia inventada en vez de un
error. Un fallo duro es recuperable; una secuencia falsa que se pliega y se
acopla, no.

Había además un tercer defecto silencioso: los residuos se recorrían en el
orden en que `GetSubstructMatches` devuelve las coincidencias, que sigue los
índices atómicos. Para un SMILES escrito de N a C eso coincide por casualidad;
para uno escrito de otra forma, la secuencia sale permutada — que es otro
péptido.

═══════════════════════════════════════════════════════════════════════════
LA QUIRALIDAD, QUE ES EL PUNTO
═══════════════════════════════════════════════════════════════════════════

Nada de lo anterior miraba el estereocentro del Cα. Un D-péptido y su
enantiómero L producen exactamente la misma cadena lateral en cada posición, y
por tanto la misma secuencia de letras. ESMFold, que sólo conoce L, habría
plegado el L-péptido y el resultado se habría presentado como la molécula del
usuario.

Eso importa precisamente porque un D-péptido se diseña para ser distinto: la
resistencia a proteasas es su razón de ser. Sustituirlo en silencio por su
enantiómero L es cambiarle la molécula a quien la escribió.

Aquí la configuración de cada Cα se lee del código CIP. Para un α-aminoácido:

    L  ->  (S)      salvo cisteína, que es (R) por prioridad del azufre
    D  ->  (R)      salvo cisteína, que es (S)

La glicina no tiene estereocentro y no se clasifica.

═══════════════════════════════════════════════════════════════════════════
CÓMO SE RECONOCE CADA RESIDUO
═══════════════════════════════════════════════════════════════════════════

No con SMARTS escritos a mano —fue lo que produjo la tabla de tres— sino
comparando la cadena lateral contra las de los veinte aminoácidos estándar,
extraídas **con este mismo código** desde sus SMILES canónicos. Comparar
manzanas con manzanas: si la extracción tiene un sesgo, lo tiene en los dos
lados y no produce una falsa coincidencia.

La comparación no depende del estado de ionización ni del tautómero: el
conformador entrega el péptido a pH 7,4 (Lys, Arg, Asp, Glu e His cargadas) y
esos residuos son los mismos que en su forma neutra. Ver `_huella_lateral`.

Lo que este módulo NO resuelve, y declara:

  · aminoácidos no estándar y modificaciones postraduccionales — se marcan
    como `X` y el llamador decide;
  · el segundo estereocentro de Ile y Thr (formas *allo*) — se ignora al
    comparar cadenas laterales;
  · péptidos ramificados o cíclicos cabeza-cola: se detecta y se rechaza en
    vez de devolver una linealización arbitraria.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem

#: Los veinte estándar, en su forma L libre. De aquí salen —por extracción,
#: no a mano— las cadenas laterales de referencia.
AMINOACIDOS_L: dict[str, str] = {
    "A": "C[C@H](N)C(=O)O",
    "R": "N[C@@H](CCCNC(=N)N)C(=O)O",
    "N": "N[C@@H](CC(=O)N)C(=O)O",
    "D": "N[C@@H](CC(=O)O)C(=O)O",
    "C": "N[C@@H](CS)C(=O)O",
    "E": "N[C@@H](CCC(=O)O)C(=O)O",
    "Q": "N[C@@H](CCC(=O)N)C(=O)O",
    "G": "NCC(=O)O",
    "H": "N[C@@H](Cc1c[nH]cn1)C(=O)O",
    "I": "CC[C@H](C)[C@H](N)C(=O)O",
    "L": "CC(C)C[C@H](N)C(=O)O",
    "K": "N[C@@H](CCCCN)C(=O)O",
    "M": "CSCC[C@H](N)C(=O)O",
    "F": "N[C@@H](Cc1ccccc1)C(=O)O",
    "P": "OC(=O)[C@@H]1CCCN1",
    "S": "N[C@@H](CO)C(=O)O",
    "T": "C[C@@H](O)[C@H](N)C(=O)O",
    "W": "N[C@@H](Cc1c[nH]c2ccccc12)C(=O)O",
    "Y": "N[C@@H](Cc1ccc(O)cc1)C(=O)O",
    "V": "CC(C)[C@H](N)C(=O)O",
}

#: Enlace peptídico: N–Cα–C(=O). El Cα es el índice 1 de la coincidencia.
_ESQUELETO = "[N;X3,X4][CX4][CX3](=[OX1])"

#: Cisteína invierte la letra CIP sin cambiar la serie estérica: el azufre pesa
#: más que el carbonilo en las reglas de prioridad.
_CIP_INVERTIDO = {"C"}


@dataclass(frozen=True)
class Residuo:
    """Una posición de la cadena, con lo que se pudo determinar de ella."""

    letra: str
    #: "L", "D" o `None` cuando no hay estereocentro (glicina) o no se declaró.
    serie: str | None
    #: Índice del Cα en la molécula de entrada. Para diagnósticos.
    ca: int


@dataclass(frozen=True)
class SecuenciaPeptidica:
    """El resultado de leer un SMILES de péptido."""

    secuencia: str
    residuos: tuple[Residuo, ...]

    @property
    def tiene_d(self) -> bool:
        return any(r.serie == "D" for r in self.residuos)

    @property
    def tiene_no_estandar(self) -> bool:
        return "X" in self.secuencia

    @property
    def series_sin_declarar(self) -> int:
        """Residuos con Cα estereogénico cuya configuración no viene en el SMILES."""
        return sum(1 for r in self.residuos if r.serie is None and r.letra != "G")


class SecuenciaNoDeterminable(ValueError):
    """No se puede leer una secuencia lineal fiable de este SMILES."""


def _atomos_de_cadena_lateral(mol: Chem.Mol, ca: int, esqueleto: set[int]) -> set[int]:
    """Los átomos colgados del Cα que no son esqueleto.

    En prolina el recorrido llega al N del esqueleto y se detiene ahí, que es lo
    correcto: el anillo se cierra sobre el esqueleto y la cadena lateral es el
    propilo.
    """
    lateral: set[int] = set()
    pila = [
        vecino.GetIdx()
        for vecino in mol.GetAtomWithIdx(ca).GetNeighbors()
        if vecino.GetAtomicNum() > 1 and vecino.GetIdx() not in esqueleto
    ]
    while pila:
        idx = pila.pop()
        if idx in lateral:
            continue
        lateral.add(idx)
        for vecino in mol.GetAtomWithIdx(idx).GetNeighbors():
            v = vecino.GetIdx()
            if vecino.GetAtomicNum() > 1 and v != ca and v not in esqueleto and v not in lateral:
                pila.append(v)
    return lateral


def _huella_lateral(mol: Chem.Mol, ca: int, esqueleto: set[int]) -> str:
    """Huella de la cadena lateral: su grafo de elementos y sus hidrógenos NEUTROS.

    Dos partes, unidas con `|`: `*CC(C)C|H9` es la leucina.

    ═════════════════════════════════════════════════════════════════════
    LA HUELLA NO DEBE DEPENDER DEL ESTADO DE IONIZACIÓN
    ═════════════════════════════════════════════════════════════════════

    Auditoría científica 1.0.4, S1-2. La huella anterior copiaba la carga formal,
    los hidrógenos explícitos y la aromaticidad de cada átomo, y comparaba contra
    los veinte aminoácidos en su forma NEUTRA. El conformador deja el péptido a
    pH 7,4 (`[NH3+]`, `C(=O)[O-]`, guanidinio), así que Lys, Arg, Asp, Glu y
    la His protonada daban `X`: `AKA→AXA`, `GRGD→GXGX`, `KDEL→XXXL`, `EAK→XAX`.
    El predictor rechazaba la secuencia antes de plegar.

    Por eso aquí no cuentan la carga, el orden de enlace ni la aromaticidad
    (un anillo de seis carbonos es el mismo grafo sea fenilo o ciclohexilo, y la
    posición del doble enlace del guanidinio o del imidazol es un tautómero).
    Pero un grafo de elementos solo es demasiado laxo: la ciclohexilalanina
    daría fenilalanina (`AFA`). Lo que lo ata es el número de hidrógenos de la
    especie NEUTRA, que es el de la cadena lateral menos su carga formal: cada
    protonación suma un H y una carga, y cada doble enlace de menos suma dos H.

        Lys   NH3+  3 H, carga +1  ->  2 H     (igual que NH2)
        Asp   COO-  0 H, carga -1  ->  1 H     (igual que COOH)
        Cha   C6H11                 ->  11 H    (Phe: 5 H, distinta)

    Los residuos no estándar siguen dando `X`: la huella agrupa estados de
    ionización y tautómeros del MISMO residuo, no residuos distintos.

    ═════════════════════════════════════════════════════════════════════
    EL ANCLAJE
    ═════════════════════════════════════════════════════════════════════

    EL ANCLAJE HAY QUE MARCARLO, y costó dos intentos verlo:

      1. Con sólo los átomos laterales, leucina e isoleucina dan el mismo
         `CC(C)C`: las dos cuelgan cuatro carbonos y sueltos son el mismo
         isobutano.
      2. Añadiendo el Cα como un carbono más, siguen colisionando en
         `CCC(C)C`: los dos fragmentos son isopentano, y sin saber cuál de los
         cinco carbonos es el Cα, 2-metilbutano y 3-metilbutano son el mismo
         grafo.

    Con el Cα convertido en átomo ficticio (`*`) la posición del anclaje entra
    en el SMILES canónico y los veinte quedan separados:

        leucina      *CC(C)C
        isoleucina   *C(C)CC

    Sin estereoquímica a propósito: la serie L/D se lee del CIP del Cα, y los
    segundos centros de Ile y Thr no distinguen residuo (sólo la forma *allo*,
    que este extractor declara no resolver).
    """
    lateral = _atomos_de_cadena_lateral(mol, ca, esqueleto)
    indices = sorted(lateral | {ca})

    fragmento = Chem.RWMol()
    correspondencia: dict[int, int] = {}
    for idx in indices:
        # Número atómico 0 = átomo ficticio. Es el marcador del anclaje. Sólo
        # cuenta el elemento: sin carga, sin hidrógenos, sin aromaticidad.
        elemento = 0 if idx == ca else mol.GetAtomWithIdx(idx).GetAtomicNum()
        correspondencia[idx] = fragmento.AddAtom(Chem.Atom(elemento))

    for enlace in mol.GetBonds():
        i, j = enlace.GetBeginAtomIdx(), enlace.GetEndAtomIdx()
        if i in correspondencia and j in correspondencia:
            fragmento.AddBond(correspondencia[i], correspondencia[j], Chem.BondType.SINGLE)

    salida = fragmento.GetMol()
    salida.UpdatePropertyCache(strict=False)
    Chem.FastFindRings(salida)
    grafo = Chem.MolToSmiles(salida, canonical=True, isomericSmiles=False)

    # Hidrógenos de la especie neutra: los de cada átomo lateral (implícitos,
    # explícitos y los que vengan como átomos) menos su carga formal. El Cα queda
    # fuera: su hidrógeno es del esqueleto y no distingue residuo.
    hidrogenos_neutros = sum(
        mol.GetAtomWithIdx(i).GetTotalNumHs(includeNeighbors=True)
        - mol.GetAtomWithIdx(i).GetFormalCharge()
        for i in lateral
    )
    return f"{grafo}|H{hidrogenos_neutros}"


def _tabla_de_referencia() -> dict[str, str]:
    """Las cadenas laterales de los veinte, extraídas con este mismo código."""
    tabla: dict[str, str] = {}
    patron = Chem.MolFromSmarts(_ESQUELETO)
    for letra, smiles in AMINOACIDOS_L.items():
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        coincidencias = mol.GetSubstructMatches(patron)
        if not coincidencias:
            continue
        coincidencia = coincidencias[0]
        huella = _huella_lateral(mol, coincidencia[1], set(coincidencia))
        # Una colisión LEVANTA en vez de quedarse con el primero. `setdefault`
        # fue lo que dejó pasar la de Leu/Ile: la tabla salía con 19 entradas y
        # un residuo quedaba fuera sin que nada lo dijera.
        if huella in tabla and tabla[huella] != letra:
            raise RuntimeError(
                f"Colisión en la tabla de residuos: {tabla[huella]} y {letra} "
                f"comparten la huella {huella!r}. La huella no distingue los "
                f"veinte estándar y el extractor devolvería el residuo equivocado."
            )
        tabla[huella] = letra
    if len(tabla) != len(AMINOACIDOS_L):
        raise RuntimeError(
            f"La tabla de referencia tiene {len(tabla)} entradas para "
            f"{len(AMINOACIDOS_L)} aminoácidos."
        )
    return tabla


#: Se calcula una vez. Es determinista y no depende de la entrada.
_POR_HUELLA: dict[str, str] = _tabla_de_referencia()


def _serie_del_alfa(mol: Chem.Mol, ca: int, letra: str) -> str | None:
    """L o D desde el código CIP del Cα. `None` si no hay estereocentro."""
    atomo = mol.GetAtomWithIdx(ca)
    if not atomo.HasProp("_CIPCode"):
        return None
    cip = atomo.GetProp("_CIPCode")
    if cip not in ("R", "S"):
        return None
    es_l = (cip == "S") != (letra in _CIP_INVERTIDO)
    return "L" if es_l else "D"


def _ordenar_residuos(mol: Chem.Mol, coincidencias) -> list[tuple[int, ...]]:
    """Ordena las coincidencias de N a C siguiendo el enlace peptídico.

    LO QUE ARREGLA. El código anterior recorría `GetSubstructMatches` en el
    orden que devuelve RDKit, que sigue los índices atómicos. Con un SMILES
    escrito de N a C coincide por casualidad; con cualquier otro, la secuencia
    sale permutada — y una permutación es otro péptido.
    """
    por_ca = {c[1]: c for c in coincidencias}
    # El carbonilo de un residuo se une al N del siguiente.
    siguiente: dict[int, int] = {}
    anteriores: set[int] = set()
    for c in coincidencias:
        carbonilo = c[2]
        for vecino in mol.GetAtomWithIdx(carbonilo).GetNeighbors():
            if vecino.GetIdx() == c[1] or vecino.GetAtomicNum() != 7:
                continue
            otro = next((o for o in coincidencias if o[0] == vecino.GetIdx()), None)
            if otro is not None and otro is not c:
                if c[1] in siguiente:
                    raise SecuenciaNoDeterminable(
                        "El esqueleto se ramifica: no hay una cadena lineal única."
                    )
                siguiente[c[1]] = otro[1]
                anteriores.add(otro[1])

    inicios = [c[1] for c in coincidencias if c[1] not in anteriores]
    if len(inicios) != 1:
        raise SecuenciaNoDeterminable(
            f"Se esperaba un único extremo N; se encontraron {len(inicios)}. "
            f"Un péptido cíclico o ramificado no tiene una secuencia lineal."
        )

    orden: list[tuple[int, ...]] = []
    visto: set[int] = set()
    actual = inicios[0]
    while actual is not None:
        if actual in visto:
            raise SecuenciaNoDeterminable("El esqueleto se cierra sobre sí mismo.")
        visto.add(actual)
        orden.append(por_ca[actual])
        actual = siguiente.get(actual)
    if len(orden) != len(coincidencias):
        raise SecuenciaNoDeterminable(
            "Hay residuos fuera de la cadena principal: el esqueleto no es lineal."
        )
    return orden


def extraer_secuencia(smiles: str) -> SecuenciaPeptidica:
    """Lee la secuencia y la serie estérica de cada residuo.

    Lanza `SecuenciaNoDeterminable` cuando no hay una lectura lineal fiable.
    Nunca devuelve una secuencia inventada: es la diferencia entre un fallo del
    que se puede informar y un péptido equivocado que se pliega y se acopla.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise SecuenciaNoDeterminable(f"SMILES inválido: {smiles}")

    # El CIP hace falta para la serie L/D y no está asignado por defecto.
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)

    patron = Chem.MolFromSmarts(_ESQUELETO)
    coincidencias = mol.GetSubstructMatches(patron)
    if not coincidencias:
        raise SecuenciaNoDeterminable("No se detectó ningún enlace peptídico.")

    residuos: list[Residuo] = []
    for coincidencia in _ordenar_residuos(mol, coincidencias):
        ca = coincidencia[1]
        huella = _huella_lateral(mol, ca, set(coincidencia))
        letra = _POR_HUELLA.get(huella, "X")
        residuos.append(Residuo(letra=letra, serie=_serie_del_alfa(mol, ca, letra), ca=ca))

    return SecuenciaPeptidica(
        secuencia="".join(r.letra for r in residuos),
        residuos=tuple(residuos),
    )
