"""Transferencia quimica de una estructura ESMFold al ligando de entrada.

ESMFold produce una estructura geometrica sin conectividad quimica completa.
Este modulo mantiene el grafo del SMILES como autoridad, copia las
coordenadas inequívocas del PDB del modelo y completa unicamente los atomos
que faltan mediante un conformero restringido de RDKit.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from rdkit import Chem
from rdkit.Chem import AllChem


PROTOCOL_VERSION = "PEPTIDE_ESMFOLD_VINA_V1"
MAPPING_VERSION = "peptide_atom_map_v1"


class TransferenciaPeptidicaError(ValueError):
    """Fallo que obliga a abstenerse antes de Meeko/Vina."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TransferenciaPeptidica:
    mol: Chem.Mol
    manifest: dict[str, Any]
    pdb_complete: str


# Orden que usa RDKit para MolFromFASTA: N, CA, C, O, cadena lateral y el OXT
# del extremo C. Se valida contra el simbolo del atomo para que una futura
# modificacion de RDKit no pueda producir un mapa silenciosamente incorrecto.
_NOMBRES_LATERALES: dict[str, tuple[str, ...]] = {
    "A": ("CB",),
    "R": ("CB", "CG", "CD", "NE", "CZ", "NH1", "NH2"),
    "N": ("CB", "CG", "OD1", "ND2"),
    "D": ("CB", "CG", "OD1", "OD2"),
    "C": ("CB", "SG"),
    "Q": ("CB", "CG", "CD", "OE1", "NE2"),
    "E": ("CB", "CG", "CD", "OE1", "OE2"),
    "G": (),
    "H": ("CB", "CG", "ND1", "CD2", "CE1", "NE2"),
    "I": ("CB", "CG1", "CG2", "CD1"),
    "L": ("CB", "CG", "CD1", "CD2"),
    "K": ("CB", "CG", "CD", "CE", "NZ"),
    "M": ("CB", "CG", "SD", "CE"),
    "F": ("CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ"),
    "P": ("CB", "CG", "CD"),
    "S": ("CB", "OG"),
    "T": ("CB", "OG1", "CG2"),
    "W": ("CB", "CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"),
    "Y": ("CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ", "OH"),
    "V": ("CB", "CG1", "CG2"),
}


def _atom_names(sequence: str) -> list[str]:
    names: list[str] = []
    for residue in sequence:
        if residue not in _NOMBRES_LATERALES:
            raise TransferenciaPeptidicaError(
                "NONCANONICAL_RESIDUE_UNSUPPORTED",
                f"Residuo no estandar: {residue}",
            )
        names.extend(("N", "CA", "C", "O"))
        names.extend(_NOMBRES_LATERALES[residue])
    names.append("OXT")
    return names


def _parse_pdb_coordinates(pdb_text: str) -> dict[tuple[int, str], tuple[float, float, float]]:
    """Lee coordenadas por residuo/nombre, prefiriendo altloc vacio o A."""
    coords: dict[tuple[int, str], tuple[float, float, float]] = {}
    for line in pdb_text.splitlines():
        if not line.startswith(("ATOM", "HETATM")) or len(line) < 54:
            continue
        altloc = line[16:17].strip()
        if altloc not in ("", "A"):
            continue
        try:
            residue = int(line[22:26])
            atom_name = line[12:16].strip()
            xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except (ValueError, IndexError):
            continue
        if all(abs(v) < 1.0e6 for v in xyz):
            coords.setdefault((residue, atom_name), xyz)
    return coords


def _complete_geometry(mol: Chem.Mol, transferred: dict[int, tuple[float, float, float]]) -> None:
    """Crea un conformero completo y restringe los atomos copiados."""
    work = Chem.Mol(mol)
    if AllChem.EmbedMolecule(work, randomSeed=42, useRandomCoords=True) < 0:
        raise TransferenciaPeptidicaError(
            "LIGAND_GEOMETRY_COMPLETION_FAILED",
            "RDKit no pudo generar un conformero inicial para el peptido.",
        )
    source_conf = work.GetConformer()
    for idx, xyz in transferred.items():
        source_conf.SetAtomPosition(idx, xyz)

    props = AllChem.MMFFGetMoleculeProperties(work, mmffVariant="MMFF94s")
    force = (
        AllChem.MMFFGetMoleculeForceField(work, props)
        if props is not None
        else AllChem.UFFGetMoleculeForceField(work)
    )
    if force is None:
        raise TransferenciaPeptidicaError(
            "LIGAND_GEOMETRY_COMPLETION_FAILED",
            "RDKit no pudo crear un campo de fuerzas para completar el peptido.",
        )
    # ═════════════════════════════════════════════════════════════════════
    # EL ANCHO DE LA RESTRICCION TIENE QUE SER MENOR QUE EL UMBRAL QUE JUZGA
    # ═════════════════════════════════════════════════════════════════════
    #
    # Decia 0.25 A, y treinta lineas mas abajo se rechaza la transferencia si
    # algun atomo restringido se desvio mas de 0.26 A. `MMFFAddPositionConstraint`
    # deja moverse ESE ancho SIN COSTE, asi que entre lo que el campo de fuerzas
    # permite gratis y lo que la comprobacion admite quedaban 0.01 A: cualquier
    # tension real de la geometria se salia.
    #
    # Medido sobre coordenadas reales de ESMFold, siete peptidos de 2 a 12
    # residuos, barriendo el ancho:
    #
    #     ancho   0.25   0.10   0.05   0.01
    #     pasan    2/7    5/7    6/7    6/7
    #
    # Con 0.05 los desvios quedan entre 0.02 y 0.24 A y el umbral de 0.26 mide
    # lo que dice medir -si la geometria transferida sobrevivio- en vez de medir
    # el ancho de su propia holgura.
    #
    # El unico que sigue fallando es el dipeptido GG, con 4.19 A a cualquier
    # ancho: nueve atomos pesados y el OXT libre no dejan geometria que
    # satisfacer. Ese caso DEBE abstenerse.
    ANCHO_RESTRICCION_A = 0.05
    for idx in transferred:
        if props is not None:
            force.MMFFAddPositionConstraint(idx, ANCHO_RESTRICCION_A, 10000.0)
        else:
            force.UFFAddPositionConstraint(idx, ANCHO_RESTRICCION_A, 10000.0)
    force.Initialize()

    # `Minimize` devuelve 1 cuando AGOTA las iteraciones, no cuando falla. Con
    # `!= 0` como fallo duro, dos de los siete peptidos se rechazaban con la
    # geometria ya correcta -0.253 y 0.250 A, por debajo del umbral-: sobraba
    # una segunda tanda de iteraciones. Lo que decide es el desvio de abajo,
    # que es el criterio fisico; agotar iteraciones es un detalle del
    # minimizador.
    RONDAS_MAX = 20
    convergio = False
    for _ in range(RONDAS_MAX):
        if force.Minimize(maxIts=500) == 0:
            convergio = True
            break
    if not convergio:
        raise TransferenciaPeptidicaError(
            "LIGAND_GEOMETRY_COMPLETION_FAILED",
            f"La optimizacion restringida no convergio en {RONDAS_MAX * 500} iteraciones.",
        )

    # Copiar el conformero completo de vuelta al grafo quimico del input.
    conf = mol.GetConformer()
    for idx in range(mol.GetNumAtoms()):
        conf.SetAtomPosition(idx, source_conf.GetAtomPosition(idx))
    # El umbral que decide, y que ahora SIGNIFICA algo.
    #
    # Mientras la restriccion tenia 0.25 A de holgura, este 0.26 era su ancho
    # mas un pelo: no medía si la geometria transferida habia sobrevivido, medía
    # que el campo de fuerzas hubiera usado su holgura. Con la restriccion en
    # 0.05 son dos parametros independientes y este es el que declara la
    # promesa del traspaso: **las coordenadas que se entregan son las de
    # ESMFold, dentro de 0.26 A**.
    #
    # No se afloja para que pasen mas peptidos. Con 0.05 de restriccion, de diez
    # peptidos de 2 a 12 residuos siete quedan entre 0.02 y 0.24 A y tres se
    # abstienen entre 0.265 y 1.025. Subir el umbral convertiria esas tres
    # abstenciones en poses cuya geometria ya no es la que se plego.
    TOLERANCIA_TRASPASO_A = 0.26
    for idx in transferred:
        a = conf.GetAtomPosition(idx)
        b = transferred[idx]
        delta = ((a.x - b[0]) ** 2 + (a.y - b[1]) ** 2 + (a.z - b[2]) ** 2) ** 0.5
        if delta > TOLERANCIA_TRASPASO_A:
            raise TransferenciaPeptidicaError(
                "LIGAND_GEOMETRY_COMPLETION_FAILED",
                f"La restriccion del atomo {idx} se desvio {delta:.3f} A.",
            )


def transferir_coordenadas(peptide_smiles: str, folded_pdb: str) -> TransferenciaPeptidica:
    """Devuelve el grafo del SMILES con el conformero de ESMFold transferido."""
    mol = Chem.MolFromSmiles(peptide_smiles)
    if mol is None:
        raise TransferenciaPeptidicaError("CHEMICAL_IDENTITY_MISMATCH", "SMILES invalido.")
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)

    from secuencia import SecuenciaNoDeterminable, extraer_secuencia

    try:
        lectura = extraer_secuencia(peptide_smiles)
    except SecuenciaNoDeterminable as exc:
        raise TransferenciaPeptidicaError("CYCLIC_OR_BRANCHED_PEPTIDE_UNSUPPORTED", str(exc)) from exc
    if lectura.tiene_d:
        raise TransferenciaPeptidicaError(
            "D_PEPTIDE_UNSUPPORTED", "ESMFold V1 solo admite aminoacidos L."
        )
    if lectura.tiene_no_estandar:
        raise TransferenciaPeptidicaError(
            "NONCANONICAL_RESIDUE_UNSUPPORTED", "El SMILES contiene residuos no estandar."
        )
    if lectura.series_sin_declarar:
        raise TransferenciaPeptidicaError(
            "AMBIGUOUS_STEREOCHEMISTRY", "La estereoquimica de uno o mas residuos no esta declarada."
        )

    sequence = lectura.secuencia
    reference = Chem.MolFromFASTA(sequence)
    if reference is None:
        raise TransferenciaPeptidicaError("CHEMICAL_IDENTITY_MISMATCH", "No se pudo construir el grafo de referencia.")
    Chem.AssignStereochemistry(reference, cleanIt=True, force=True)
    mapping = mol.GetSubstructMatch(reference, useChirality=True)
    if not mapping or len(mapping) != reference.GetNumAtoms() or mol.GetNumAtoms() != reference.GetNumAtoms():
        raise TransferenciaPeptidicaError(
            "TERMINAL_MODIFICATION_UNSUPPORTED",
            "El grafo del SMILES no coincide con el constructor V1 de terminales estandar.",
        )

    names = _atom_names(sequence)
    if len(names) != reference.GetNumAtoms():
        raise TransferenciaPeptidicaError("CHEMICAL_IDENTITY_MISMATCH", "El mapa de nombres no coincide con RDKit.")
    for idx, name in enumerate(names):
        element = name.lstrip("0123456789")[0]
        if reference.GetAtomWithIdx(idx).GetSymbol() != element:
            raise TransferenciaPeptidicaError("CHEMICAL_IDENTITY_MISMATCH", f"Orden de atomos inesperado para {name}.")

    pdb_coords = _parse_pdb_coordinates(folded_pdb)
    transferred: dict[int, tuple[float, float, float]] = {}
    missing: list[str] = []
    required_backbone = {"N", "CA", "C", "O"}
    for ref_idx, name in enumerate(names):
        residue_idx = 1 + next(i for i, offset in enumerate(_residue_offsets(sequence)) if ref_idx < offset)
        xyz = pdb_coords.get((residue_idx, name))
        if xyz is None:
            missing.append(name if name == "OXT" else f"{residue_idx}:{name}")
            continue
        transferred[mapping[ref_idx]] = xyz

    for residue_idx in range(1, len(sequence) + 1):
        if any((residue_idx, name) not in pdb_coords for name in required_backbone):
            raise TransferenciaPeptidicaError(
                "ATOM_MAPPING_INCOMPLETE",
                f"Faltan atomos backbone de la posicion {residue_idx} en el PDB de ESMFold.",
            )

    if not transferred:
        raise TransferenciaPeptidicaError("ATOM_MAPPING_INCOMPLETE", "El PDB de ESMFold no contiene coordenadas transferibles.")

    out = Chem.Mol(mol)
    out.RemoveAllConformers()
    out.AddConformer(Chem.Conformer(out.GetNumAtoms()), assignId=True)
    _complete_geometry(out, transferred)
    Chem.SanitizeMol(out)
    if len(Chem.GetMolFrags(out)) != 1:
        raise TransferenciaPeptidicaError("CHEMICAL_IDENTITY_MISMATCH", "El ligando transferido no es una sola molecula conectada.")
    if out.GetNumHeavyAtoms() != mol.GetNumHeavyAtoms():
        raise TransferenciaPeptidicaError("CHEMICAL_IDENTITY_MISMATCH", "Cambio el numero de atomos pesados.")

    output_smiles = Chem.MolToSmiles(out, isomericSmiles=True)
    input_smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
    if output_smiles != input_smiles:
        raise TransferenciaPeptidicaError("CHEMICAL_IDENTITY_MISMATCH", "El SMILES isomerico cambio durante la transferencia.")

    # Serializacion PDB solo para inspeccion; Meeko recibira el Mol con enlaces.
    pdb_complete = Chem.MolToPDBBlock(out)
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "completed",
        "mapping_version": MAPPING_VERSION,
        "chemical_graph_source": "smiles",
        "coordinate_source": "esmfold",
        "coordinates_transferred": len(transferred),
        "coordinates_completed": out.GetNumHeavyAtoms() - len(transferred),
        "completed_atom_names": missing,
        "completion_method": "rdkit_constrained_v1",
        "input_isomeric_smiles": input_smiles,
        "output_isomeric_smiles": output_smiles,
        "input_graph_hash": hashlib.sha256(input_smiles.encode("utf-8")).hexdigest(),
        "output_graph_hash": hashlib.sha256(output_smiles.encode("utf-8")).hexdigest(),
        "heavy_atoms": out.GetNumHeavyAtoms(),
        "sequence": sequence,
    }
    return TransferenciaPeptidica(mol=out, manifest=manifest, pdb_complete=pdb_complete)


def _residue_offsets(sequence: str) -> list[int]:
    offsets: list[int] = []
    total = 0
    for residue in sequence:
        total += 4 + len(_NOMBRES_LATERALES[residue])
        offsets.append(total)
    # El OXT pertenece al ultimo residuo y ocupa el ultimo indice.
    if offsets:
        offsets[-1] += 1
    return offsets
