"""La corrida peptídica registra la caja que ejecutó (auditoría científica 1.0.4, S1-2, 2026-11-13).

Las dos ramas que arman el resultado de un péptido con poses transferidas escribían
`box_center: null` y `box_size: null` en `execution_provenance`, aunque la caja estaba en una
variable del mismo ámbito y el predictor se la entregaba tal cual a Vina. Preparación y el
dossier leen esa procedencia, así que la geometría de búsqueda de la corrida no se podía
recuperar. Las dos ramas pasan ahora por `procedencia_de_la_transferencia`.

`queue_handler` arma el resultado dentro de una función de varios cientos de líneas que no se
puede ejecutar aquí sin el despachador completo; esa rama se vigila con un guardián de código
(con control negativo) y la de `peptide_docking`, de extremo a extremo.
"""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace

import pytest

import services.docking.peptide_docking as peptide_docking
import services.docking.queue_handler as queue_handler
from services.docking.peptide_docking import procedencia_de_la_transferencia

CAJA_CENTRO = [-3.857, 5.196, 14.831]
CAJA_TAMANO = [22.0, 22.0, 22.0]


def test_la_procedencia_lleva_la_caja_como_listas_de_floats():
    prov = procedencia_de_la_transferencia("SDF", (-3.857, 5.196, 14.831), (22, 22, 22))

    assert prov["box_center"] == CAJA_CENTRO
    assert prov["box_size"] == CAJA_TAMANO
    assert all(isinstance(v, float) for v in prov["box_size"])
    assert prov["source"] == "peptide_transfer"
    assert len(prov["poses_sha256"]) == 64


def test_sin_caja_no_la_inventa():
    prov = procedencia_de_la_transferencia("SDF", None, None)

    assert prov["box_center"] is None and prov["box_size"] is None


def test_el_hash_de_las_poses_no_depende_de_la_caja():
    a = procedencia_de_la_transferencia("SDF", CAJA_CENTRO, CAJA_TAMANO)
    b = procedencia_de_la_transferencia("SDF", None, None)

    assert a["poses_sha256"] == b["poses_sha256"]


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
async def test_la_ruta_peptidica_persiste_la_caja_que_le_dieron(monkeypatch):
    """De extremo a extremo por `run_peptide_docking_helper`, con el plegado simulado."""
    import services.esmfold.service as servicio_esmfold
    import services.motores as motores
    import utils.local_storage as local_storage

    pose = SimpleNamespace(rank=1, vina_affinity_kcal_mol=-7.25, rmsd=None)
    visto = {}

    class _Esmfold:
        async def predict(self, _pdb, _smiles, grid_center=None, grid_size=None):
            visto["caja"] = (grid_center, grid_size)
            return SimpleNamespace(
                poses=[pose], best_confidence=0.8, transfer_manifest=None, success=True,
                vina_version="1.2.7", vina_seed=42, vina_exhaustiveness=8,
            )

    async def _existe(_ruta):
        return True

    async def _lee(_ruta):
        return "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"

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
    monkeypatch.setattr(servicio_esmfold, "get_esmfold_service", lambda: _Esmfold())
    monkeypatch.setattr(
        peptide_docking, "poses_acopladas_y_sdf",
        lambda poses, _smiles: (list(poses), "SDF-ACOPLADO", {"sin_afinidad": 0, "solo_plegado": 0, "sin_geometria": 0}),
    )

    resultado = await peptide_docking.run_peptide_docking_helper(
        task_id="task-prueba", smiles="CCO", target_pdb_id="7E2Y",
        peptide_docking_engine="esmfold",
        grid_center=CAJA_CENTRO, grid_size=CAJA_TAMANO,
    )

    assert visto["caja"] == (CAJA_CENTRO, CAJA_TAMANO)
    prov = resultado.execution_provenance
    assert prov["source"] == "peptide_transfer"
    assert prov["box_center"] == CAJA_CENTRO
    assert prov["box_size"] == CAJA_TAMANO


# ── Guardián de la rama de `queue_handler` ────────────────────────────────────────────────────


def _arma_procedencia_de_transferencia_a_mano(codigo: str) -> bool:
    """¿Hay algún diccionario literal con `"source": "peptide_transfer"` en `codigo`?

    Esa forma es la que escribía la caja como `None`. Una rama que la arma a mano puede
    volver a divergir de la otra, así que se exige pasar por `procedencia_de_la_transferencia`.
    """
    for nodo in ast.walk(ast.parse(codigo)):
        if not isinstance(nodo, ast.Dict):
            continue
        for clave, valor in zip(nodo.keys, nodo.values):
            if (
                isinstance(clave, ast.Constant) and clave.value == "source"
                and isinstance(valor, ast.Constant) and valor.value == "peptide_transfer"
            ):
                return True
    return False


def test_el_guardian_ve_la_forma_antigua_y_no_la_nueva():
    antigua = (
        'prov = {"poses_sha256": "x", "box_center": None, "box_size": None, '
        '"source": "peptide_transfer"}'
    )
    nueva = "prov = procedencia_de_la_transferencia(sdf, centro, tamano)"

    assert _arma_procedencia_de_transferencia_a_mano(antigua)
    assert not _arma_procedencia_de_transferencia_a_mano(nueva)


def test_queue_handler_no_arma_la_procedencia_peptidica_a_mano():
    codigo = inspect.getsource(queue_handler)

    assert not _arma_procedencia_de_transferencia_a_mano(codigo)
    assert "procedencia_de_la_transferencia(" in codigo


def test_peptide_docking_solo_la_arma_en_el_ayudante():
    """El único literal con `source: peptide_transfer` es el del ayudante."""
    fuente = inspect.getsource(peptide_docking)
    arbol = ast.parse(fuente)
    ayudante = next(
        n for n in ast.walk(arbol)
        if isinstance(n, ast.FunctionDef) and n.name == "procedencia_de_la_transferencia"
    )
    fuera = ast.unparse(arbol).replace(ast.unparse(ayudante), "")

    assert not _arma_procedencia_de_transferencia_a_mano(fuera)
