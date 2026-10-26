"""El diagrama de contactos rotula sólo los átomos que forman cada contacto (SCI-A-057).

Antes, un puente de hidrógeno o un puente salino se pintaba sobre TODOS los N, O,
F y S del ligando, con el rótulo de la primera interacción, los formara o no. Y se
dibujaba desde el SMILES, cuyos índices de átomo no son los de la pose de la que
salen las distancias. Ahora cada contacto lleva los índices de los átomos de la pose
(`ligand_atoms`), y el diagrama sólo los localiza cuando dibuja esa misma pose.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import AllChem

from services.blockchain.certificate_figures import (
    generate_2d_interaction_diagram,
    notas_de_contacto,
    primera_pose,
)
from services.blockchain.pdf_generator import compute_residue_interactions


def _pose_sdf() -> str:
    """Etilenglicol con un oxígeno en el origen y el otro lejos de él."""
    mol = Chem.AddHs(Chem.MolFromSmiles("OCCO"))
    AllChem.EmbedMolecule(mol, randomSeed=7)
    conf = mol.GetConformer()
    o1 = conf.GetAtomPosition(0)
    for i in range(mol.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (p.x - o1.x, p.y - o1.y, p.z - o1.z))
    return Chem.MolToMolBlock(mol) + "$$$$\n"


def _receptor_junto_al_primer_oxigeno() -> str:
    """Un nitrógeno de serina a 2,9 Å del oxígeno 0, en dirección opuesta al resto."""
    pose = primera_pose(_pose_sdf())
    conf = pose.GetConformer()
    c = conf.GetAtomPosition(1)
    norma = (c.x ** 2 + c.y ** 2 + c.z ** 2) ** 0.5
    x, y, z = (-2.9 * c.x / norma, -2.9 * c.y / norma, -2.9 * c.z / norma)
    return (f"ATOM      1  N   SER A  42    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           N\n")


def test_el_contacto_nombra_solo_el_oxigeno_que_lo_forma():
    pose = primera_pose(_pose_sdf())
    oxigenos = [a.GetIdx() for a in pose.GetAtoms() if a.GetSymbol() == "O"]
    assert len(oxigenos) == 2

    contactos = compute_residue_interactions(_receptor_junto_al_primer_oxigeno(), _pose_sdf())
    puente = next(c for c in contactos if "H-Bond" in c["type"])
    assert puente["residue"] == "SER42 (A)"
    assert puente["ligand_atoms"] == [0]          # el oxígeno 0, no el otro


def test_el_diagrama_rotula_solo_los_atomos_nombrados():
    contactos = [{"residue": "SER42 (A)", "type": "H-Bond", "distance": "2.90 Å", "ligand_atoms": [0]}]
    assert notas_de_contacto(contactos, 4) == {0: "SER42 (2.90 Å)"}


def test_un_contacto_sin_atomos_no_se_localiza():
    """Lo que hacía el código anterior con cualquier puente: rotular todos los polares."""
    contactos = [{"residue": "ASP186 (A)", "type": "H-Bond", "distance": "2.80 Å"},
                 {"residue": "LYS20 (A)", "type": "Salt Bridge", "distance": "3.10 Å", "ligand_atoms": []}]
    assert notas_de_contacto(contactos, 4) == {}


def test_los_contactos_no_polares_y_los_indices_fuera_de_rango_no_se_rotulan():
    contactos = [{"residue": "LEU8 (A)", "type": "Hydrophobic", "distance": "3.80 Å", "ligand_atoms": [1]},
                 {"residue": "SER42 (A)", "type": "H-Bond", "distance": "2.90 Å", "ligand_atoms": [9, -1]}]
    assert notas_de_contacto(contactos, 4) == {}


def test_un_atomo_con_dos_residuos_lleva_los_dos():
    contactos = [{"residue": "SER42 (A)", "type": "H-Bond", "distance": "2.90 Å", "ligand_atoms": [3]},
                 {"residue": "ARG7 (B)", "type": "Salt Bridge", "distance": "3.40 Å", "ligand_atoms": [3]}]
    assert notas_de_contacto(contactos, 4) == {3: "SER42 (2.90 Å), ARG7 (3.40 Å)"}


def test_el_diagrama_se_dibuja_con_y_sin_pose():
    contactos = compute_residue_interactions(_receptor_junto_al_primer_oxigeno(), _pose_sdf())
    assert generate_2d_interaction_diagram("OCCO", contactos, pose_sdf=_pose_sdf()) is not None
    assert generate_2d_interaction_diagram("OCCO", contactos) is not None
