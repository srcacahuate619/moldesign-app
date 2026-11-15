"""Mapa de contactos residuo-ligando del informe de evaluación.

Caza 1 (2026-11-12), B01–B05. Lo que el mapa rotula tiene que ser lo que midió:

* «Salt Bridge» exige cargas de signo contrario. Antes bastaba un ASP/GLU/ARG/LYS junto a cualquier N u O del ligando
  (dos ARG «puente salino» con un ligando dicatión). La carga del ligando es la de la especie acoplada (las cargas formales de
  la pose); la del receptor sale del nombre del residuo y del átomo (ARG NE/NH1/NH2 y LYS NZ, positivas; ASP OD1/OD2 y
  GLU OE1/OE2, negativas).
* El puente salino y el enlace de hidrógeno se evalúan por separado: un mismo residuo puede tener los dos (B02).
* «H-Bond» exige un donante y un aceptor (B03): un N u O con hidrógeno de un lado y un N u O con un par libre del otro. Dos
  aceptores a 2,9 Å no son un enlace de hidrógeno. Sin los hidrógenos del receptor no se sabe cuál de los dos nitrógenos de una
  histidina lleva el protón: se admiten los dos como donante y aceptor.
* La distancia que se rotula es la del par que define el tipo rotulado, medida entre átomos pesados (B04). Antes era el mínimo de
  TODO el residuo, hidrógenos del receptor incluidos (2,02 Å en un receptor con H frente a 3,2 Å sin ellos).
* El apilamiento aromático mide entre centroides de anillo, como decía su comentario (antes bastaba un átomo aromático del
  ligando a menos de 4,5 Å de cualquier carbono de una PHE/TYR/TRP/HIS, el de la cadena principal incluido).

Es una heurística geométrica, no un cálculo de energía: no mira ángulos. El informe lo dice junto a la tabla.
"""
from __future__ import annotations

import logging
import math

from rdkit import Chem

from services.blockchain.certificate_figures import primera_pose

logger = logging.getLogger(__name__)

#: Lo que el informe dice junto a la tabla de contactos (Caza 1, B05). Los umbrales de la frase son los de las constantes de abajo.
NOTA_DE_LOS_CONTACTOS = (
    "Contactos medidos sobre la estructura del receptor del caso, no sobre el PDBQT acoplado. Enlace de hidrógeno: donante y "
    "aceptor a ≤ 3.2 Å entre átomos pesados. Puente salino: cargas opuestas a ≤ 4.0 Å (la del ligando es la de la especie "
    "acoplada; la del receptor, la que corresponde al residuo). Sin ángulos. Distancia: la del par que define el tipo."
)

DIST_MINIMA_FISICA = 0.8     # por debajo, el SDF y el PDB no comparten marco de coordenadas
DIST_CONTACTO = 4.5
DIST_ENLACE_H = 3.2
DIST_PUENTE_SALINO = 4.0
DIST_CENTROIDES = 4.5
DIST_HIDROFOBICO = 4.2
DIST_VAN_DER_WAALS = 4.0

_HIS = frozenset({"HIS", "HID", "HIE", "HIP", "HSD", "HSE", "HSP"})
_AGUA = frozenset({"HOH", "WAT", "H2O", "TIP", "TIP3", "SOL"})
_AMINOACIDOS = frozenset({
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR",
    "TRP", "TYR", "VAL",
})
_HIDROFOBICOS = frozenset({"ALA", "VAL", "LEU", "ILE", "PHE", "TYR", "TRP", "MET", "PRO"})

_DONANTES = frozenset({
    ("ARG", "NE"), ("ARG", "NH1"), ("ARG", "NH2"), ("LYS", "NZ"), ("ASN", "ND2"), ("GLN", "NE2"), ("HIS", "ND1"),
    ("HIS", "NE2"), ("TRP", "NE1"), ("SER", "OG"), ("THR", "OG1"), ("TYR", "OH"),
})
_ACEPTORES = frozenset({
    ("ASP", "OD1"), ("ASP", "OD2"), ("GLU", "OE1"), ("GLU", "OE2"), ("ASN", "OD1"), ("GLN", "OE1"), ("HIS", "ND1"),
    ("HIS", "NE2"), ("SER", "OG"), ("THR", "OG1"), ("TYR", "OH"),
})
_CARGA_DEL_RECEPTOR = {
    ("ARG", "NE"): 1, ("ARG", "NH1"): 1, ("ARG", "NH2"): 1, ("LYS", "NZ"): 1,
    ("HIP", "ND1"): 1, ("HIP", "NE2"): 1,
    ("ASP", "OD1"): -1, ("ASP", "OD2"): -1, ("GLU", "OE1"): -1, ("GLU", "OE2"): -1,
}
_ANILLOS = {
    "PHE": (("CG", "CD1", "CD2", "CE1", "CE2", "CZ"),),
    "TYR": (("CG", "CD1", "CD2", "CE1", "CE2", "CZ"),),
    "TRP": (("CG", "CD1", "NE1", "CE2", "CD2"), ("CD2", "CE2", "CZ2", "CH2", "CZ3", "CE3")),
    "HIS": (("CG", "ND1", "CD2", "CE1", "NE2"),),
}


def _distancia(a: dict, b: dict) -> float:
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def _centroide(puntos: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    n = len(puntos)
    return (sum(p[0] for p in puntos) / n, sum(p[1] for p in puntos) / n, sum(p[2] for p in puntos) / n)


def _elemento_del_receptor(linea: str, nombre: str) -> str:
    elemento = linea[76:78].strip()
    if elemento:
        return elemento.upper()
    letras = nombre.lstrip("0123456789")
    return (letras[:1] or "C").upper()


def _leer_receptor(receptor_pdb: str) -> list[dict]:
    """Átomos pesados del receptor. Los hidrógenos no entran: no son donde está el contacto que se mide."""
    atomos = []
    for linea in receptor_pdb.splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        try:
            nombre = linea[12:16].strip()
            elemento = _elemento_del_receptor(linea, nombre)
            if elemento in ("H", "D"):
                continue
            res = linea[17:20].strip()
            atomos.append({
                "atom_name": nombre, "res_name": res, "chain": linea[21].strip(), "res_num": int(linea[22:26].strip()),
                "x": float(linea[30:38]), "y": float(linea[38:46]), "z": float(linea[46:54]), "element": elemento,
            })
        except (ValueError, IndexError):
            continue
    return atomos


def _papel_polar_del_receptor(a: dict) -> tuple[bool, bool]:
    """(donante, aceptor) de un átomo pesado del receptor, por residuo y nombre de átomo."""
    if a["element"] not in ("N", "O"):
        return False, False
    res = "HIS" if a["res_name"] in _HIS else a["res_name"]
    nombre = a["atom_name"]
    if res in _AGUA:
        return True, True
    if res not in _AMINOACIDOS:
        return True, True            # cofactor, ligando o residuo no estándar: sin tabla, se admiten los dos papeles
    donante = (res, nombre) in _DONANTES or (nombre == "N" and res != "PRO")
    aceptor = (res, nombre) in _ACEPTORES or nombre in ("O", "OXT")
    return donante, aceptor


def _carga_del_receptor(a: dict) -> int:
    return _CARGA_DEL_RECEPTOR.get((a["res_name"], a["atom_name"]), 0)


def _tiene_doble_enlace_a(centro: Chem.Atom, simbolos: tuple[str, ...]) -> bool:
    return any(b.GetBondType() == Chem.BondType.DOUBLE and b.GetOtherAtom(centro).GetSymbol() in simbolos
               for b in centro.GetBonds())


def _carga_del_grupo_del_ligando(mol: Chem.Mol) -> dict[int, int]:
    """Átomo → ±1 para los átomos que llevan la carga de un grupo del ligando acoplado.

    La carga formal de la pose es la de la especie que se acopló. Un carboxilato lleva la carga en los dos oxígenos aunque el
    SDF la ponga en uno; un par de cargas opuestas pegadas (nitro, N-óxido) es un grupo neutro y no cuenta.
    """
    cargas: dict[int, int] = {}
    for a in mol.GetAtoms():
        q = a.GetFormalCharge()
        if q and not any(n.GetFormalCharge() * q < 0 for n in a.GetNeighbors()):
            cargas[a.GetIdx()] = 1 if q > 0 else -1
    anillos = mol.GetRingInfo().AtomRings()
    for idx, signo in list(cargas.items()):
        a = mol.GetAtomWithIdx(idx)
        if signo < 0:
            for centro in a.GetNeighbors():
                if centro.GetSymbol() in ("C", "S", "P") and centro.GetFormalCharge() == 0:
                    for b in centro.GetBonds():
                        o = b.GetOtherAtom(centro)
                        if b.GetBondType() == Chem.BondType.DOUBLE and o.GetSymbol() in ("O", "S") and o.GetFormalCharge() == 0:
                            cargas.setdefault(o.GetIdx(), -1)
            if a.GetIsAromatic():            # tetrazolato y afines: la carga es del anillo
                for anillo in anillos:
                    if idx in anillo:
                        for j in anillo:
                            otro = mol.GetAtomWithIdx(j)
                            if otro.GetSymbol() == "N" and otro.GetIsAromatic() and otro.GetFormalCharge() == 0 \
                                    and otro.GetTotalNumHs() == 0 and otro.GetTotalDegree() == 2:
                                cargas.setdefault(j, -1)
        else:
            for b in a.GetBonds():           # amidinio y guanidinio: C(=[NH2+])N
                if b.GetBondType() == Chem.BondType.DOUBLE and b.GetOtherAtom(a).GetSymbol() == "C":
                    for n in b.GetOtherAtom(a).GetNeighbors():
                        if n.GetSymbol() == "N" and n.GetIdx() != idx and n.GetFormalCharge() == 0 and not _es_tipo_amida(n):
                            cargas.setdefault(n.GetIdx(), 1)
            if a.GetIsAromatic():            # imidazolio: el otro nitrógeno del anillo, junto al mismo carbono
                for c in a.GetNeighbors():
                    if c.GetSymbol() == "C" and c.GetIsAromatic():
                        for n in c.GetNeighbors():
                            if n.GetSymbol() == "N" and n.GetIsAromatic() and n.GetIdx() != idx and n.GetFormalCharge() == 0:
                                cargas.setdefault(n.GetIdx(), 1)
    return cargas


def _es_tipo_amida(n: Chem.Atom) -> bool:
    """N unido a un C, S o P con doble enlace a O o S: su par libre está deslocalizado y no acepta un puente de hidrógeno."""
    return any(c.GetSymbol() in ("C", "S", "P") and _tiene_doble_enlace_a(c, ("O", "S")) for c in n.GetNeighbors())


def _papel_polar_del_ligando(a: Chem.Atom) -> tuple[bool, bool]:
    """(donante, aceptor) de un átomo del ligando acoplado: el donante lleva hidrógeno; el aceptor, un par libre."""
    elemento = a.GetSymbol()
    if elemento not in ("N", "O"):
        return False, False
    donante = a.GetTotalNumHs() >= 1
    if a.GetFormalCharge() > 0:
        return donante, False
    if elemento == "O":
        return donante, True
    if _es_tipo_amida(a):
        return donante, False
    if a.GetIsAromatic():
        return donante, a.GetTotalDegree() == 2      # piridina sí; pirrol y N-sustituido, con el par en el anillo, no
    return donante, True


def _atomos_del_ligando(mol: Chem.Mol) -> list[dict]:
    conf = mol.GetConformer()
    cargas = _carga_del_grupo_del_ligando(mol)
    atomos = []
    for a in mol.GetAtoms():
        if a.GetSymbol() == "H":
            continue
        p = conf.GetAtomPosition(a.GetIdx())
        donante, aceptor = _papel_polar_del_ligando(a)
        atomos.append({
            "idx": a.GetIdx(), "element": a.GetSymbol().upper(), "x": p.x, "y": p.y, "z": p.z,
            "is_aromatic": a.GetIsAromatic(), "donor": donante, "acceptor": aceptor, "charge": cargas.get(a.GetIdx(), 0),
        })
    return atomos


def _centroides_del_ligando(mol: Chem.Mol) -> list[tuple[float, float, float]]:
    conf = mol.GetConformer()
    return [_centroide([tuple(conf.GetAtomPosition(i)) for i in anillo])
            for anillo in mol.GetRingInfo().AtomRings()
            if all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in anillo)]


def _centroides_del_residuo(res_name: str, atomos: list[dict]) -> list[tuple[float, float, float]]:
    familia = "HIS" if res_name in _HIS else res_name
    por_nombre = {a["atom_name"]: (a["x"], a["y"], a["z"]) for a in atomos}
    return [_centroide([por_nombre[n] for n in anillo])
            for anillo in _ANILLOS.get(familia, ()) if all(n in por_nombre for n in anillo)]


def compute_residue_interactions(receptor_pdb: str | None, ligand_sdf: str | None) -> list[dict]:
    """Los diez residuos más cercanos al ligando, cada uno con el tipo de contacto que cumple y la distancia de su par."""
    return residuos_en_contacto(receptor_pdb, ligand_sdf)[:10]


def residuos_en_contacto(receptor_pdb: str | None, ligand_sdf: str | None) -> list[dict]:
    """Todos los residuos que cumplen algún criterio de contacto, del más cercano al más lejano.

    Caza 1, A05: el informe enseña los siete primeros y el diagrama diez; para decir «de cuántos», alguien tiene que contarlos todos.
    """
    if not receptor_pdb or not ligand_sdf:
        return []
    try:
        receptor = _leer_receptor(receptor_pdb)
        pose = primera_pose(ligand_sdf)
        if pose is None:
            return []
        ligando = _atomos_del_ligando(pose)
        anillos_ligando = _centroides_del_ligando(pose)

        por_residuo: dict[tuple, list[dict]] = {}
        for r in receptor:
            por_residuo.setdefault((r["chain"], r["res_name"], r["res_num"]), []).append(r)

        clasificados = []
        for (cadena, res_name, res_num), atomos in por_residuo.items():
            pares = []                                           # (distancia, átomo del ligando, átomo del receptor)
            for r in atomos:
                for l in ligando:
                    d = _distancia(l, r)
                    if DIST_MINIMA_FISICA <= d < DIST_CONTACTO:   # <0,8 Å: marcos de coordenadas distintos
                        pares.append((d, l, r))
            if not pares:
                continue

            pares_h, pares_sal = [], []
            for d, l, r in pares:
                donante_r, aceptor_r = _papel_polar_del_receptor(r)
                if d < DIST_ENLACE_H and ((l["donor"] and aceptor_r) or (l["acceptor"] and donante_r)):
                    pares_h.append((d, l["idx"]))
                carga_r = _carga_del_receptor(r)
                if d < DIST_PUENTE_SALINO and l["charge"] * carga_r < 0 and l["element"] in ("N", "O") \
                        and r["element"] in ("N", "O"):
                    pares_sal.append((d, l["idx"]))

            tipos, distancias = set(), []
            if pares_h:
                tipos.add("H-Bond")
                distancias += [d for d, _ in pares_h]
            if pares_sal:
                tipos.add("Salt Bridge")
                distancias += [d for d, _ in pares_sal]

            if not tipos and anillos_ligando:
                centroides = _centroides_del_residuo(res_name, atomos)
                cercanos = [math.dist(a, b) for a in anillos_ligando for b in centroides]
                cercanos = [d for d in cercanos if d < DIST_CENTROIDES]
                if cercanos:
                    tipos.add("Pi-Stacking")
                    distancias += cercanos

            if not tipos and res_name in _HIDROFOBICOS:
                carbonos = [d for d, l, r in pares if d < DIST_HIDROFOBICO and l["element"] == "C" and r["element"] == "C"]
                if carbonos:
                    tipos.add("Hydrophobic")
                    distancias += carbonos

            minima = min(d for d, _, _ in pares)
            if not tipos and minima < DIST_VAN_DER_WAALS:
                tipos.add("Hydrophobic Contact" if res_name in _HIDROFOBICOS else "Van der Waals")
                distancias.append(minima)

            if tipos:
                distancia = min(distancias)
                clasificados.append({
                    "residue": f"{res_name}{res_num} ({cadena})",
                    "type": "/".join(sorted(tipos)),
                    "distance": f"{distancia:.2f} Å",
                    "min_dist_val": distancia,
                    # SCI-A-057: los átomos de la pose que forman el contacto polar, para que el diagrama rotule sólo ésos.
                    "ligand_atoms": sorted({i for _, i in pares_h} | {i for _, i in pares_sal}),
                })
        clasificados.sort(key=lambda c: c["min_dist_val"])
        return clasificados
    except Exception:
        # Un fallo aquí quita la tabla de contactos del documento: que no pase sin dejar rastro.
        logger.warning("No se pudo calcular el mapa de contactos del informe", exc_info=True)
        return []
