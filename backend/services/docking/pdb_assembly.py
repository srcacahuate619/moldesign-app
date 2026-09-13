"""Ensamblado local de estructuras para visualización de resultados.

No calcula docking ni modifica coordenadas: convierte la primera pose SDF ya
producida por Vina a registros PDB y la une al receptor para que el visor use
un único modelo molecular.
"""

from __future__ import annotations


def merge_protein_ligand_pdb(protein_pdb: str, ligand_sdf: str) -> str:
    """Fusiona receptor PDB y primera pose SDF en un PDB con ligando ``LIG``.

    El ligando se asigna al residuo ``LIG``, cadena ``L`` y se desplazan los
    seriales de sus átomos/conectividad para que no colisionen con el receptor.
    Devuelve cadena vacía si no hay una pose SDF legible.
    """
    from rdkit import Chem

    supplier = Chem.SDMolSupplier()
    supplier.SetData(ligand_sdf, sanitize=False, removeHs=False)

    mol = next((candidate for candidate in supplier if candidate is not None), None)
    if mol is None:
        return ""

    max_serial = 0
    for line in protein_pdb.splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            try:
                max_serial = max(max_serial, int(line[6:11]))
            except ValueError:
                continue

    for atom in mol.GetAtoms():
        info = Chem.AtomPDBResidueInfo()
        info.SetName(f" {atom.GetSymbol():<3s}")
        info.SetResidueName("LIG")
        info.SetResidueNumber(1)
        info.SetChainId("L")
        info.SetIsHeteroAtom(True)
        atom.SetMonomerInfo(info)

    ligand_pdb_block = Chem.MolToPDBBlock(mol)
    if not ligand_pdb_block:
        return ""

    protein_clean = "\n".join(
        line
        for line in protein_pdb.splitlines()
        if not line.startswith(("END", "MASTER"))
    ).rstrip()

    ligand_lines: list[str] = []
    for line in ligand_pdb_block.splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            try:
                serial = int(line[6:11]) + max_serial
            except ValueError:
                ligand_lines.append(line)
            else:
                ligand_lines.append("HETATM" + f"{serial:>5}" + line[11:])
        elif line.startswith("CONECT"):
            connected = "CONECT"
            for index in range(6, len(line), 5):
                serial = line[index:index + 5].strip()
                if not serial:
                    continue
                try:
                    connected += f"{int(serial) + max_serial:>5}"
                except ValueError:
                    continue
            ligand_lines.append(connected)

    ligand_clean = "\n".join(ligand_lines).rstrip()
    return f"{protein_clean}\n{ligand_clean}\nEND\n"
