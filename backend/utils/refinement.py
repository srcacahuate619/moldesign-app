"""
backend/utils/refinement.py

Módulo de refinamiento estructural para complejos receptor-péptido.
Implementa optimización con restricciones usando OpenMM/Amber (si está disponible)
o caída elegante a RDKit UFF.
"""

from __future__ import annotations
import io
from utils.logger import get_logger

log = get_logger(__name__)


def refine_receptor_peptide_complex(
    receptor_pdb_content: str,
    peptide_pdb_content: str,
) -> str:
    """
    Realiza la minimización del complejo receptor-péptido.
    Mantiene el backbone del receptor congelado y optimiza las cadenas laterales y el péptido.
    
    1. Intenta usar OpenMM con AMBER14SB y solvente implícito GB/SA.
    2. Si falla o no está instalado, cae automáticamente a RDKit UFF con restricciones.
    3. Si falla RDKit, retorna el bloque PDB original.
    """
    # 1. Intentar refinamiento con OpenMM/Amber
    try:
        return _refine_openmm(receptor_pdb_content, peptide_pdb_content)
    except ImportError:
        log.info("OpenMM no está instalado en el entorno local. Activando fallback a RDKit UFF.")
    except Exception as exc:
        log.warning("Fallo en refinamiento OpenMM. Activando fallback a RDKit UFF.", error=str(exc))

    # 2. Fallback a RDKit UFF
    try:
        return _refine_rdkit_uff(receptor_pdb_content, peptide_pdb_content)
    except Exception as exc:
        log.warning("Fallo en refinamiento de fallback RDKit UFF. Retornando coordenadas originales.", error=str(exc))

    # 3. Retornar las coordenadas originales del péptido
    return peptide_pdb_content


def _refine_openmm(receptor_pdb_content: str, peptide_pdb_content: str) -> str:
    from openmm.app import PDBFile, ForceField, Simulation, Modeller
    from openmm import LangevinIntegrator
    from openmm.unit import nanometer, picosecond, kelvin, kilocalorie_per_mole, angstrom, md_unit_system
    from openmm import CustomExternalForce

    log.debug("Iniciando refinamiento con OpenMM/AMBER14SB")

    # Parsear estructuras PDB en memoria
    receptor_pdb = PDBFile(io.StringIO(receptor_pdb_content))
    peptide_pdb = PDBFile(io.StringIO(peptide_pdb_content))

    # Combinar receptor y ligando usando Modeller
    modeller = Modeller(receptor_pdb.topology, receptor_pdb.positions)
    modeller.add(peptide_pdb.topology, peptide_pdb.positions)

    # Cargar campo de fuerzas AMBER14-SB y solvente implícito GB/SA (OBC2)
    # BUG-C04: Corregir forcefield de gbc2.xml a obc2.xml
    ff = ForceField('amber14-all.xml', 'amber14/implicit/obc2.xml')

    # Crear el sistema
    system = ff.createSystem(modeller.topology, nonbondedMethod=None, constraints=None)

    # Identificar cadenas del receptor original para congelarlas
    receptor_chain_indices = {c.index for c in receptor_pdb.topology.chains()}

    # Configurar restricciones armónicas para el backbone del receptor (N, CA, C, O)
    restraint = CustomExternalForce('k * ((x-x0)^2 + (y-y0)^2 + (z-z0)^2)')

    # BUG-C05: Convertir la constante de fuerza 'k' al sistema de unidades base (md_unit_system)
    # para evitar mezcla de unidades (kcal/mol·Å² vs base MD units: kJ/mol/nm²)
    k_value = (50.0 * kilocalorie_per_mole / angstrom**2).value_in_unit_system(md_unit_system)
    restraint.addGlobalParameter('k', k_value)
    restraint.addPerParticleParameter('x0')
    restraint.addPerParticleParameter('y0')
    restraint.addPerParticleParameter('z0')

    atoms = list(modeller.topology.atoms())
    positions = modeller.positions

    for atom in atoms:
        # Si el átomo pertenece a alguna cadena del receptor y es del backbone
        if atom.residue.chain.index in receptor_chain_indices:
            if atom.name in ['N', 'CA', 'C', 'O']:
                # BUG-C05: Convertir la posición explícitamente a nanómetros (unidad base unitless)
                pos_val = positions[atom.index].value_in_unit(nanometer)
                restraint.addParticle(atom.index, pos_val)

    system.addForce(restraint)

    # Configurar simulación
    integrator = LangevinIntegrator(300 * kelvin, 1.0 / picosecond, 0.002 * picosecond)
    simulation = Simulation(modeller.topology, system, integrator)
    simulation.context.setPositions(positions)

    # Minimizar energía (límite de 100 iteraciones para mantener la inferencia rápida)
    simulation.minimizeEnergy(maxIterations=100)

    # Extraer nuevas posiciones
    state = simulation.context.getState(getPositions=True)
    optimized_positions = state.getPositions()

    # Re-extraer solo los átomos correspondientes al péptido
    num_receptor_atoms = len(receptor_pdb.positions)

    peptide_topology = peptide_pdb.topology
    peptide_positions = optimized_positions[num_receptor_atoms:]

    output_stream = io.StringIO()
    PDBFile.writeFile(peptide_topology, peptide_positions, output_stream)

    log.info("Refinamiento OpenMM completado con éxito.")
    return output_stream.getvalue()


def _refine_rdkit_uff(receptor_pdb_content: str, peptide_pdb_content: str) -> str:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    log.debug("Iniciando refinamiento con RDKit UFF Fallback")

    # Cargar moléculas
    receptor_mol = Chem.MolFromPDBBlock(receptor_pdb_content, removeHs=False)
    peptide_mol = Chem.MolFromPDBBlock(peptide_pdb_content, removeHs=False)

    if not receptor_mol or not peptide_mol:
        raise ValueError("No se pudo cargar el receptor o el péptido en RDKit para UFF")

    num_receptor_atoms = receptor_mol.GetNumAtoms()
    complex_mol = Chem.CombineMols(receptor_mol, peptide_mol)

    # Sanitize complex molecule for force field calculations
    try:
        Chem.SanitizeMol(complex_mol)
    except Exception as e:
        log.warning("sanitize_complex_failed, FF may be unreliable", error=str(e)[:150])
    ff = AllChem.UFFGetMoleculeForceField(complex_mol)

    if not ff:
        raise RuntimeError("No se pudo inicializar el campo de fuerzas UFF de RDKit")

    # Fijar la posición de los átomos del receptor
    for i in range(num_receptor_atoms):
        ff.AddFixedPoint(i)

    # Ejecutar optimización
    ff.Minimize(maxIts=200)

    # Copiar coordenadas optimizadas de vuelta al péptido original
    conf_complex = complex_mol.GetConformer(0)
    conf_peptide = peptide_mol.GetConformer(0)

    for i in range(peptide_mol.GetNumAtoms()):
        pos = conf_complex.GetAtomPosition(num_receptor_atoms + i)
        conf_peptide.SetAtomPosition(i, pos)

    log.info("Refinamiento RDKit UFF completado con éxito.")
    return Chem.MolToPDBBlock(peptide_mol)

def refine_complex_small_molecule(receptor_pdb_content: str, ligand_sdf_content: str, iterations: int = 100) -> str:
    """
    Refinamiento para ligandos pequeños (SDF).
    Convierte el SDF a PDB, aplica UFF (RDKit) con el receptor fijo,
    y devuelve el SDF actualizado.
    """
    from rdkit import Chem

    log.debug("Iniciando refinamiento de small molecule")

    # Cargar ligando desde SDF
    supplier = Chem.SDMolSupplier()
    supplier.SetData(ligand_sdf_content, sanitize=False, removeHs=False)
    ligand_mol = next(supplier)
    if not ligand_mol:
        raise ValueError("No se pudo cargar el ligando SDF")

    ligand_pdb_content = Chem.MolToPDBBlock(ligand_mol)

    # Intentar refinamiento UFF
    try:
        refined_pdb = _refine_rdkit_uff(receptor_pdb_content, ligand_pdb_content)
        # Activar el PDB refinado como conformador
        refined_mol = Chem.MolFromPDBBlock(refined_pdb, removeHs=False)
        if refined_mol and refined_mol.GetNumAtoms() == ligand_mol.GetNumAtoms():
            # Actualizar coordenadas
            conf = refined_mol.GetConformer()
            lig_conf = ligand_mol.GetConformer()
            for i in range(ligand_mol.GetNumAtoms()):
                lig_conf.SetAtomPosition(i, conf.GetAtomPosition(i))
    except Exception as e:
        log.warning("Fallo en refinamiento de small molecule, retornando original", error=str(e))

    # Volver a SDF
    from chem.conformer import _mol_to_sdf_string
    return _mol_to_sdf_string(ligand_mol, ligand_mol.GetProp("SMILES") if ligand_mol.HasProp("SMILES") else "")
