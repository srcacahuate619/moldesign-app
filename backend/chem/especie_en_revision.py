"""
Clases químicas cuya especie a pH fisiológico la tabla de pKa por clases no resuelve.

# Qué hace y qué NO hace

NO cambia qué se acopla: `chem/ionizacion.py` sigue eligiendo el microestado con
su tabla de pKa por clase, y cambiar esa tabla exige un experimento sellado. Lo
que hace es DECLARAR: si el ligando pertenece a una de estas clases, la
«Especie acoplada» del expediente y de Preparación pasa a REVISAR con el motivo,
en vez de aparecer como REGISTRADA.

# Por qué estas tres clases (evidencia, 2026-09-27/28)

- **Dos centros básicos a ≤ 3 enlaces** (piperazinas y diaminas). La tabla da a
  cada N alifático el pKa de su clase (9,8) por separado, pero protonar uno baja
  varias unidades el del otro. Cetirizina (pKa 2,12 / 2,90 / 7,98; Tam y Quéré
  2001, DOI 10.2116/analsci.17.1203) es zwitterión neutro a pH 7,4 y el producto
  la acoplaba como catión +1. Indinavir, dicatión en QA-002.
- **N-sulfonil-piperazina con el N distal básico.** El sulfonilo baja el pKa del
  N distal muy por debajo de 9,8: sildenafilo 6,78 (Gobry et al. 2000, DOI
  10.1002/1522-2675(20000705)83:7<1465::AID-HLCA1465>3.0.CO;2-#), neutro
  dominante a pH 7,4, acoplado como catión. Vardenafilo igual (QA-002).
- **Ácidos enólicos vinílogos (oxicams y 4-hidroxicumarinas).** La tabla no tiene
  la clase: el piroxicam (pKa ácido 5,30, Baek et al. 2018; ~5,3-5,7 por
  HPLC/UV, DOI 10.4274/tjps.82335) salía «química resuelta» y neutro, con una
  tabla de la misma fuente que lo da >99 % neutro: la especie está en disputa y
  el producto no puede afirmar ninguna.

- **Amina protonada con un grupo atractor a uno o dos enlaces del N** (CF3 o CHF2 en
  β, nitrilo en α o β; añadida el 2026-10-09). La tabla le da el pKa de la clase
  (9,8) y la protona, pero el grupo lo baja varias unidades: 2,2,2-trifluoroetilamina
  pKa ≈ 5,7, aminoacetonitrilo ≈ 5,3 y 3-aminopropionitrilo ≈ 7,8 (CRC Handbook,
  constantes de disociación de bases orgánicas; tendencia de los sustituyentes en β
  en Morgenthaler et al., «Predicting and Tuning Physicochemical Properties in Lead
  Optimization: Amine Basicities», ChemMedChem 2007, 2, 1100). Se vio en la
  calibración de 8HFI (`CAL-8HFI-01`): tres padres de CHEMBL853189 se acoplaron con
  esa amina protonada. Sólo se marca si la especie ACOPLADA la protonó: si el
  producto ya la dejó neutra, no hay nada que revisar.

Medido contra el panel de 45 moléculas de la auditoría de GPT 6 Sol
(`D:\\moldesign-audits\\qa-sol\\repro\\t3_microstates.jsonl`): ver
`tests/test_especie_en_revision.py`, que fija los aciertos y las falsas alarmas.

# Coste

RDKit ya está cargado cuando se construye un expediente; este módulo se importa
de forma perezosa desde el dossier, fuera del arranque (restricción 7 de
AGENTS.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize

from chem.ionizacion import CENTROS, PH_FISIOLOGICO

#: Distancia topológica máxima, en enlaces, entre dos centros básicos para que la
#: protonación de uno cambie la del otro de forma que la tabla no ve. 3 = N-C-C-N.
MAX_ENLACES_ENTRE_BASES = 3


@dataclass(frozen=True)
class MotivoDeRevision:
    codigo: str
    texto: str

    def as_dict(self) -> dict[str, str]:
        return {"codigo": self.codigo, "texto": self.texto}


_BASES_PROXIMAS = MotivoDeRevision(
    "bases_proximas",
    "En revisión por dos centros básicos a 3 enlaces o menos (piperazina o diamina): la tabla da a "
    "cada uno el pKa de su clase por separado, pero protonar uno baja el del otro "
    "(cetirizina, pKa 7,98, es zwitterión neutro y se acoplaba como catión).",
)
_SULFONIL_PIPERAZINA = MotivoDeRevision(
    "sulfonil_piperazina",
    "En revisión por N-sulfonil-piperazina: el sulfonilo baja el pKa del N distal muy por debajo del "
    "9,8 de una amina alifática (sildenafilo 6,78: neutro a pH 7,4, se acoplaba como "
    "catión).",
)
_ACIDO_ENOLICO = MotivoDeRevision(
    "acido_enolico",
    "En revisión por ácido enólico vinílogo (oxicam o 4-hidroxicumarina): la tabla de pKa no tiene "
    "esta clase y la especie a pH 7,4 no está establecida (piroxicam, pKa ácido "
    "≈5,3, con fuentes que discrepan).",
)

_AMINA_CON_ATRACTOR = MotivoDeRevision(
    "amina_con_atractor",
    "En revisión por amina protonada con un grupo atractor a uno o dos enlaces del N (CF3 o CHF2 en β, "
    "nitrilo en α o β): el grupo baja varias unidades el pKa que la tabla da a la clase "
    "(9,8); la 2,2,2-trifluoroetilamina tiene pKa ≈5,7 y el 3-aminopropionitrilo ≈7,8, "
    "así que la carga a pH 7,4 es una decisión abierta.",
)

#: Sobre la especie ACOPLADA (con cargas): N protonado con H, sp3, no anilinio.
_SMARTS_AMINA_CON_ATRACTOR = (
    "[NX4+;!H0;!$(N[a])]-[CX4]-[CX4](F)(F)",       # CF3 / CHF2 en β
    "[NX4+;!H0;!$(N[a])]-[CX4]-C#N",               # nitrilo en α
    "[NX4+;!H0;!$(N[a])]-[CX4]-[CX4]-C#N",         # nitrilo en β
)

#: Bases cuyo pKa de clase supera el pH fisiológico: las que la tabla protona.
_BASES = tuple(c for c in CENTROS if c.caracter == "base" and c.pka > PH_FISIOLOGICO)

_SMARTS_SULFONIL_PIPERAZINA = (
    "[SX4](=O)(=O)[NX3;R]1[CH2][CH2]"
    "[NX3;!$(N[a]);!$(N[CX3]=[O,N,S]);!$(N-[!#6])][CH2][CH2]1"
)
#: Los dos tautómeros de cada núcleo: el producto acopla por defecto el canónico
#: de RDKit (ceto en el piroxicam), así que la clase se reconoce en cualquiera.
_SMARTS_ACIDO_ENOLICO = (
    # Oxicam (1,2-benzotiazina / tienotiazina 3-carboxamida 1,1-dióxido), enol y ceto.
    "O=S1(=O)[#7][#6](C(=O)[#7])=[#6]([OX2H1,OX1-])[#6]~[#6]1",
    "O=S1(=O)[#7][#6](C(=O)[#7])[#6](=O)[#6]~[#6]1",
    # 4-hidroxicumarina (warfarina, acenocumarol), enol y ceto (2,4-diona). Por
    # número atómico y con enlaces genéricos: RDKit aromatiza la pirona de la
    # cumarina, y un patrón con `C`/`O` alifáticos no la ve (así falló la primera
    # versión con la warfarina).
    "[OX2H1,OX1-][#6]1~[#6]~[#6](=[OX1])~[#8]~[#6]~[#6]1",
    "[OX1]=[#6]1[CX4][#6](=[OX1])[#8][#6]~[#6]1",
)


@lru_cache(maxsize=1)
def _patrones():
    bases = [(c.nombre, Chem.MolFromSmarts(c.smarts)) for c in _BASES]
    sulfonil = Chem.MolFromSmarts(_SMARTS_SULFONIL_PIPERAZINA)
    enolicos = [Chem.MolFromSmarts(s) for s in _SMARTS_ACIDO_ENOLICO]
    return bases, sulfonil, enolicos


@lru_cache(maxsize=1)
def _patrones_de_atractor():
    return [Chem.MolFromSmarts(s) for s in _SMARTS_AMINA_CON_ATRACTOR]


def _molecula_neutra(smiles: str):
    """La especie acoplada puede venir protonada: los patrones de base de la tabla
    excluyen `[N+]`, así que se mira el padre neutro (los cuaternarios se quedan)."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return _padre_neutro(mol)


def _padre_neutro(mol):
    """`Uncharger` cambia cargas e hidrógenos, no el orden de los átomos."""
    try:
        return rdMolStandardize.Uncharger().uncharge(mol)
    except Exception:  # noqa: BLE001 — sin padre neutro, se mira tal cual
        return mol


def _centros_basicos(mol) -> list[frozenset[int]]:
    """Centros básicos disjuntos, en el orden de la tabla (el primero reclama sus átomos)."""
    bases, _, _ = _patrones()
    reclamados: set[int] = set()
    centros: list[frozenset[int]] = []
    for _, patron in bases:
        for coincidencia in mol.GetSubstructMatches(patron):
            atomos = frozenset(coincidencia)
            if atomos & reclamados:
                continue
            reclamados |= atomos
            centros.append(atomos)
    return centros


def motivos_de_revision(smiles: str | None) -> list[MotivoDeRevision]:
    """Por qué la especie de este ligando no puede declararse resuelta. Vacío si no aplica."""
    if not smiles:
        return []
    acoplada = Chem.MolFromSmiles(smiles)
    if acoplada is None:
        return []
    return [motivo for motivo, _ in revisiones_en_mol(acoplada)]


def revisiones_en_mol(acoplada) -> list[tuple[MotivoDeRevision, list[int]]]:
    """Los motivos de `motivos_de_revision`, en el mismo orden, con los átomos de
    `acoplada` que los provocan (la especie tal como se acopló o se escribió)."""
    mol = _padre_neutro(acoplada)
    _, sulfonil, enolicos = _patrones()
    motivos: list[tuple[MotivoDeRevision, list[int]]] = []

    centros = _centros_basicos(mol)
    if len(centros) >= 2:
        distancias = Chem.GetDistanceMatrix(mol)
        proximos: set[int] = set()
        for a, b in combinations(centros, 2):
            if min(distancias[i][j] for i in a for j in b) <= MAX_ENLACES_ENTRE_BASES:
                proximos |= a | b
        if proximos:
            motivos.append((_BASES_PROXIMAS, sorted(proximos)))
    if mol.HasSubstructMatch(sulfonil):
        motivos.append((_SULFONIL_PIPERAZINA, sorted({i for m in mol.GetSubstructMatches(sulfonil) for i in m})))
    enolicos_hallados = {i for p in enolicos for m in mol.GetSubstructMatches(p) for i in m}
    if enolicos_hallados:
        motivos.append((_ACIDO_ENOLICO, sorted(enolicos_hallados)))
    # Sobre la especie tal como se acopló: importa que ESTA amina esté protonada.
    atractor = {i for p in _patrones_de_atractor() for m in acoplada.GetSubstructMatches(p) for i in m}
    if atractor:
        motivos.append((_AMINA_CON_ATRACTOR, sorted(atractor)))
    return motivos
