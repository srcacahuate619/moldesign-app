"""Un péptido a pH 7,4 recorre la ruta peptídica entera (auditoría científica 1.0.4, S1-2, 2026-11-14).

El conformador entrega el péptido ionizado (`[NH3+]`, `C(=O)[O-]`, guanidinio). La lectura de la secuencia sólo
conocía los veinte en su forma neutra, así que `AKA` salía `AXA` y el predictor rechazaba la secuencia antes de
plegar; y aunque se leyera, la transferencia de coordenadas comparaba contra la referencia neutra sin ninguna
comprobación química propia. Esta suite mira lo que falta al cierre:

  · un péptido ionizado canónico se lee, se transfiere con sus cargas intactas y llega al resultado con su caja;
  · el mismo grafo con otro residuo (ciclohexilalanina por fenilalanina) NO se acepta;
  · el tautómero del guanidinio no hace que se abstenga.

Las coordenadas son las de un plegado real de ESMFold (`fixtures/esmfold_plegados/GRGDSP.pdb`); el modelo, con sus
8,4 GB, no puede estar en la suite, así que el plegado se sirve desde ese fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from rdkit import Chem

RAIZ = Path(__file__).resolve().parents[1]
SIDECAR = str(RAIZ / "sidecars" / "esmfold")
if SIDECAR not in sys.path:
    sys.path.insert(0, SIDECAR)

import ligand_transfer  # noqa: E402
from ligand_transfer import TransferenciaPeptidicaError, transferir_coordenadas  # noqa: E402

import services.docking.peptide_docking as peptide_docking  # noqa: E402

PLEGADO = (Path(__file__).resolve().parent / "fixtures" / "esmfold_plegados" / "GRGDSP.pdb").read_text()

#: GRGDSP a pH 7,4: amino terminal protonado, guanidinio, Asp y carboxilo terminal desprotonados.
GRGDSP_PH74 = (
    "[NH3+]CC(=O)N[C@@H](CCCNC(=[NH2+])N)C(=O)NCC(=O)N[C@@H](CC(=O)[O-])C(=O)"
    "N[C@@H](CO)C(=O)N1CCC[C@H]1C(=O)[O-]"
)
#: El mismo péptido con el doble enlace del guanidinio en el nitrógeno interno: un tautómero.
GRGDSP_TAUTOMERO = GRGDSP_PH74.replace("CCCNC(=[NH2+])N", "CCC[NH+]=C(N)N")


def _smiles_canonico(mol: Chem.Mol) -> str:
    return Chem.MolToSmiles(mol, isomericSmiles=True)


def test_el_peptido_ionizado_se_transfiere_con_sus_cargas_y_su_grafo():
    resultado = transferir_coordenadas(GRGDSP_PH74, PLEGADO)

    assert resultado.manifest["status"] == "completed"
    assert resultado.manifest["sequence"] == "GRGDSP"
    assert resultado.manifest["atom_match"] == "orden_de_enlace"
    assert resultado.manifest["mapping_version"] == "peptide_atom_map_v2"
    assert _smiles_canonico(resultado.mol) == _smiles_canonico(Chem.MolFromSmiles(GRGDSP_PH74))
    assert resultado.manifest["input_graph_hash"] == resultado.manifest["output_graph_hash"]
    # Las cuatro cargas del SMILES (amino terminal, guanidinio, Asp y carboxilo terminal) siguen en la molécula.
    assert sorted(a.GetFormalCharge() for a in resultado.mol.GetAtoms() if a.GetFormalCharge()) == [-1, -1, 1, 1]


def test_el_tautomero_del_guanidinio_no_obliga_a_abstenerse():
    """Con enlaces de orden exacto este mismo péptido se abstenía (`TERMINAL_MODIFICATION_UNSUPPORTED`)."""
    mol = Chem.MolFromSmiles(GRGDSP_TAUTOMERO)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    referencia = Chem.MolFromFASTA("GRGDSP")
    Chem.AssignStereochemistry(referencia, cleanIt=True, force=True)

    assert not mol.GetSubstructMatch(referencia, useChirality=True), "el control: el criterio estricto no casa"

    resultado = transferir_coordenadas(GRGDSP_TAUTOMERO, PLEGADO)

    assert resultado.manifest["status"] == "completed"
    assert resultado.manifest["atom_match"] == "grafo"
    assert _smiles_canonico(resultado.mol) == _smiles_canonico(mol)


def test_el_emparejamiento_por_grafo_conserva_la_quiralidad():
    """Relajar el orden de enlace no relaja el estereocentro: una D-Ser no casa."""
    d_ser = GRGDSP_TAUTOMERO.replace("N[C@@H](CO)", "N[C@H](CO)")
    mol = Chem.MolFromSmiles(d_ser)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    referencia = Chem.MolFromFASTA("GRGDSP")
    Chem.AssignStereochemistry(referencia, cleanIt=True, force=True)

    mapa, _como = ligand_transfer._emparejar_con_la_referencia(mol, referencia)

    assert not mapa


def test_la_ciclohexilalanina_casa_por_grafo_pero_no_pasa_la_comprobacion_quimica():
    """El grafo de la ciclohexilalanina es el de la fenilalanina: el emparejamiento por sí solo la aceptaría
    (22 átomos pesados, quiralidad activada). Lo que la rechaza es el conteo de hidrógenos neutros."""
    cha = Chem.MolFromSmiles("C[C@H](N)C(=O)N[C@@H](CC1CCCCC1)C(=O)N[C@@H](C)C(=O)O")
    Chem.AssignStereochemistry(cha, cleanIt=True, force=True)
    afa = Chem.MolFromFASTA("AFA")
    Chem.AssignStereochemistry(afa, cleanIt=True, force=True)

    mapa, como = ligand_transfer._emparejar_con_la_referencia(cha, afa)

    assert mapa and como == "grafo", "control: sin la comprobación, esto se aceptaría"
    with pytest.raises(TransferenciaPeptidicaError) as error:
        ligand_transfer._exigir_misma_especie_neutra(cha, afa)
    assert error.value.code == "CHEMICAL_IDENTITY_MISMATCH"


def test_un_peptido_con_un_residuo_modificado_se_abstiene_antes_de_transferir():
    con_cha = GRGDSP_PH74.replace("N[C@@H](CO)C(=O)", "N[C@@H](CC1CCCCC1)C(=O)")  # Ser -> ciclohexilalanina
    with pytest.raises(TransferenciaPeptidicaError) as error:
        transferir_coordenadas(con_cha, PLEGADO)

    assert error.value.code == "NONCANONICAL_RESIDUE_UNSUPPORTED"


def test_el_predictor_lee_la_secuencia_de_un_peptido_ionizado():
    """El primer eslabón que fallaba: `_smiles_to_aa_sequence` rechazaba `GXGX` antes de plegar."""
    import predictor

    secuencia = predictor.ESMFoldFastPredictor._smiles_to_aa_sequence(GRGDSP_PH74)

    assert secuencia == "GRGDSP"


# ── La ruta peptídica entera, con el plegado de ESMFold servido desde el fixture ─────────────────────────────────


class _Session:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_exc):
        return False


class _Repository:
    async def get_target_by_pdb_id(self, _pdb_id):
        return SimpleNamespace(pdb_id="7E2Y", chain="A")

    async def create_or_get_molecule(self, *, smiles, target_pdb_id=None):
        return SimpleNamespace(smiles_hash="hash-prueba")


class _Cache:
    async def set_job_progress(self, *args):
        return None


@pytest.mark.asyncio
async def test_el_peptido_ionizado_recorre_la_ruta_con_su_identidad_y_su_caja(monkeypatch):
    import services.esmfold.service as servicio_esmfold
    import services.motores as motores
    import utils.local_storage as local_storage

    centro, tamano = [12.5, -3.0, 40.25], [20.0, 20.0, 20.0]
    visto: dict = {}

    class _EsmfoldConPlegadoReal:
        async def predict(self, _pdb, smiles, grid_center=None, grid_size=None):
            visto["caja"] = (grid_center, grid_size)
            transferencia = transferir_coordenadas(smiles, PLEGADO)
            pose = SimpleNamespace(
                rank=1, vina_affinity_kcal_mol=-6.2, rmsd=None, origen="vina",
                ligand_sdf=Chem.MolToMolBlock(transferencia.mol),
            )
            return SimpleNamespace(
                poses=[pose], best_confidence=0.7, success=True, transfer_manifest=transferencia.manifest,
                vina_version="1.2.7", vina_seed=42, vina_exhaustiveness=8,
            )

    async def _existe(_ruta):
        return True

    async def _lee(_ruta):
        return PLEGADO

    async def _escribe(_ruta, _contenido):
        return None

    monkeypatch.setattr(motores, "sidecar_de", lambda _id: None)
    monkeypatch.setattr(peptide_docking, "get_db_session", lambda: _Session())
    monkeypatch.setattr(peptide_docking, "Repository", lambda _db: _Repository())
    monkeypatch.setattr(peptide_docking, "calculate_properties", lambda _smiles: None)
    monkeypatch.setattr(peptide_docking, "cache", _Cache())
    monkeypatch.setattr(local_storage, "exists", _existe)
    monkeypatch.setattr(local_storage, "read_text", _lee)
    monkeypatch.setattr(local_storage, "write_text", _escribe)
    monkeypatch.setattr(servicio_esmfold, "get_esmfold_service", lambda: _EsmfoldConPlegadoReal())

    resultado = await peptide_docking.run_peptide_docking_helper(
        task_id="task-prueba", smiles=GRGDSP_PH74, target_pdb_id="7E2Y",
        peptide_docking_engine="esmfold", grid_center=centro, grid_size=tamano,
    )

    # La identidad del ligando: la que se pidió, con sus cargas, no una sustitución por Vina.
    manifiesto = resultado.peptide_transfer_manifest
    assert manifiesto["status"] == "completed" and manifiesto["sequence"] == "GRGDSP"
    assert manifiesto["input_isomeric_smiles"] == manifiesto["output_isomeric_smiles"]
    assert manifiesto["input_isomeric_smiles"] == _smiles_canonico(Chem.MolFromSmiles(GRGDSP_PH74))
    assert resultado.engine_efectivo == "esmfold"
    avisos = [a.get("codigo") if isinstance(a, dict) else getattr(a, "codigo", None) for a in resultado.scientific_warnings]
    assert "MOTOR_SUSTITUIDO" not in avisos

    # La caja efectiva, en la corrida (S1-2, caja).
    assert visto["caja"] == (centro, tamano)
    assert resultado.execution_provenance["box_center"] == centro
    assert resultado.execution_provenance["box_size"] == tamano
