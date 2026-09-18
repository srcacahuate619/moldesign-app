import pytest
from openmm import app
from rdkit import Chem

from services.chemistry.mmgbsa_integrity import MMGBSAIntegrityError, validate_ligand_system
from services.chemistry.molchamb_v2 import _register_ligand_template, _override_charges


@pytest.mark.parametrize("smiles", ["CCO", "c1ccccc1"])
def test_legacy_system_cannot_publish_energy_with_missing_parameters(smiles):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    top = app.Topology()
    residue = top.addResidue("LIG",top.addChain())
    atoms = [top.addAtom(f"{a.GetSymbol()}{a.GetIdx()+1}",app.Element.getBySymbol(a.GetSymbol()),residue)
             for a in mol.GetAtoms()]
    for bond in mol.GetBonds():
        top.addBond(atoms[bond.GetBeginAtomIdx()],atoms[bond.GetEndAtomIdx()])
    ff = app.ForceField("amber14-all.xml","implicit/gbn2.xml")
    _register_ligand_template(ff,mol)
    system = ff.createSystem(top,nonbondedMethod=app.NoCutoff,constraints=app.HBonds)
    with pytest.raises(MMGBSAIntegrityError,match="ángulos sin parámetro"):
        validate_ligand_system(system,top,range(mol.GetNumAtoms()))
    _override_charges(system,list(range(mol.GetNumAtoms())),[0.25]*mol.GetNumAtoms())
    with pytest.raises(MMGBSAIntegrityError,match="cargas electrostáticas y GB inconsistentes"):
        validate_ligand_system(system,top,range(mol.GetNumAtoms()))


@pytest.mark.parametrize("name", ["ethanol","benzene","aspirin","chlorobenzene","acetate",
                                 "methylammonium","dimethylphosphate","imidazole"])
def test_complete_reference_system_passes_necessary_integrity_checks(name):
    from pathlib import Path
    path = Path(__file__).resolve().parents[1]/"audits"/"amber_reference"/name/"ligand.prmtop"
    topology = app.AmberPrmtopFile(str(path))
    system = topology.createSystem(nonbondedMethod=app.NoCutoff,constraints=app.HBonds,
                                    implicitSolvent=app.GBn2,sasaMethod=None)
    validate_ligand_system(system,topology.topology,range(system.getNumParticles()))
