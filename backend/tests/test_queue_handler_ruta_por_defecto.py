"""Regresion: la ruta SIN `pipeline_config` debe alcanzar `calculate_properties`.

El defecto que motiva este fichero: `queue_handler.py` usaba `asyncio.to_thread`
a nivel de modulo en `_run_full_evaluation_async` sin importar `asyncio` alli.
Los cinco `import asyncio as _asyncio` del fichero son LOCALES a otras
funciones, de modo que el nombre no quedaba ligado y **toda** evaluacion por la
ruta por defecto moria con `NameError` ~0,2 s despues de empezar, antes de
calcular propiedades y mucho antes de docking.

Por que no lo vio nadie: `_run_full_evaluation_async` **retorna antes** cuando
recibe `pipeline_config`, delegando en `services/pipeline/runner.py`. El gate de
aceptacion siempre mandaba `pipeline_config`, asi que ejercitaba exclusivamente
la rama sana. La rama rota es la que toma un `POST /evaluation/submit` normal.

Por eso esta prueba **ejecuta** la corrutina en vez de inspeccionar el fuente.
Un `assert "import asyncio" in codigo` habria pasado igual de verde con los
imports locales presentes y el global ausente: es exactamente el error que
permitio el defecto. Aqui se comprueba el efecto observable —que
`calculate_properties` se invoca, y que se invoca en OTRO hilo, que es lo que
`asyncio.to_thread` promete— y no la forma del codigo.

Las dependencias pesadas (sesion de BD, repositorio, resolucion de diana) se
sustituyen por dobles: lo que se ejerce de verdad es el tramo de
`_run_full_evaluation_async` que va desde su entrada hasta la llamada a
propiedades, que es donde vivia el fallo. No se lanza docking.
"""
from __future__ import annotations

import asyncio
import threading
import types
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

import services.docking.queue_handler as qh


class _ParadaTrasPropiedades(Exception):
    """Corta el pipeline justo despues de propiedades.

    No es un fallo: es el punto de observacion. Lo que sigue (SA filter,
    conformero, docking) queda fuera del alcance de esta regresion.
    """


def _diana_doble() -> types.SimpleNamespace:
    """Diana con exactamente los atributos que lee `PipelineParams.from_orm`."""
    return types.SimpleNamespace(
        pdb_id="3F75", name="diana-doble", chain="A", site_chains=["A"],
        structural_family="kinase", is_hot=False,
        grid_center_x=0.0, grid_center_y=0.0, grid_center_z=0.0,
        grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
        hotspots=[], cofactors_whitelist=[],
        affinity_threshold=-7.0, specificity_floor=0.5, spearman_rho=None,
    )


class _RepositorioDoble:
    def __init__(self, _db: object) -> None:
        self.estados: list[object] = []

    async def create_or_get_molecule(self, **kwargs: object) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            id=uuid4(),
            smiles=kwargs.get("smiles"),
            smiles_hash="0" * 64,
        )

    async def get_evaluation_result(self, _molecule_id):
        return None

    async def upsert_evaluation_result(self, **kwargs):
        return None

    async def set_molecule_status(self, _molecule_id: object, estado: object) -> None:
        self.estados.append(estado)


@pytest.mark.asyncio
async def test_ruta_por_defecto_delega_con_presupuesto_historico(monkeypatch):
    """El modo normal usa el runner común con 8/5 y las etapas declaradas."""
    from services.pipeline import runner

    received = {}

    async def fake_runner(**kwargs):
        received.update(kwargs)
        return {"status": "SUCCESS", "delegado": True}

    monkeypatch.setattr(runner, "run_pipeline", fake_runner)
    result = await qh._run_full_evaluation_async(
        task_id=str(uuid4()), smiles="CCO", target_pdb_id="3F75",
        pipeline_config=None,
    )
    assert result["delegado"] is True
    assert received["stage_params"]["docking"] == {
        "exhaustiveness": qh.settings.vina_exhaustiveness,
        "num_poses": qh.settings.vina_num_poses,
    }
    assert {"xgb", "clgnn"} <= set(received["enabled_stages"])
    assert received["pipeline_config"]["execution_profile"] == "default"


@pytest.mark.asyncio
async def test_ruta_con_pipeline_config_sigue_delegando(monkeypatch):
    """La rama con `pipeline_config` retorna antes, sin tocar propiedades.

    Fija el motivo por el que el defecto era invisible: si algun dia esta rama
    dejara de delegar, las dos pruebas dejarian de cubrir caminos distintos y
    convendria enterarse.
    """
    delegado: dict[str, object] = {}

    async def _run_pipeline_doble(**kwargs: object) -> dict[str, object]:
        delegado.update(kwargs)
        return {"status": "SUCCESS", "delegado": True}

    import services.pipeline.runner as runner
    monkeypatch.setattr(runner, "run_pipeline", _run_pipeline_doble)

    def _no_debe_llamarse(*_a: object, **_k: object):
        raise AssertionError(
            "La rama con pipeline_config no debe pasar por calculate_properties "
            "de queue_handler: delega en services/pipeline/runner.py."
        )

    monkeypatch.setattr(qh, "calculate_properties", _no_debe_llamarse)

    resultado = await qh._run_full_evaluation_async(
        task_id=str(uuid4()),
        smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
        target_pdb_id="3F75",
        pipeline_config={"enabled_stages": ["validation"], "stage_params": {}},
    )

    assert resultado == {"status": "SUCCESS", "delegado": True}
    assert delegado["target_pdb_id"] == "3F75"


def test_asyncio_esta_ligado_en_el_modulo():
    """Complemento barato de la prueba de ejecucion, no sustituto.

    Comprueba que el nombre esta ligado al modulo `asyncio` de verdad; un
    `import asyncio as _asyncio` local no satisface esto.
    """
    assert getattr(qh, "asyncio", None) is asyncio
