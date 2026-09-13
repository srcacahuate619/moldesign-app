"""Contratos del servicio peptídico separado del dispatcher (C-09)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import services.docking.peptide_docking as peptide_docking
import services.docking.queue_handler as queue_handler


class _Session:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


class _Repository:
    async def get_target_by_pdb_id(self, _pdb_id):
        return SimpleNamespace(pdb_id="7E2Y", chain="A")

    async def create_or_get_molecule(self, *, smiles, target_pdb_id=None):
        assert smiles == "CCO"
        # EVAL-SCI-001: la molécula se archiva contra el receptor que resolvió
        # esta corrida. Sin el argumento explícito caía al receptor base y la
        # fila persistida contradecía al acoplamiento.
        assert target_pdb_id == "7E2Y"
        return SimpleNamespace(smiles_hash="hash-prueba")


class _Cache:
    def __init__(self):
        self.progress = []

    async def set_job_progress(self, *args):
        self.progress.append(args)


def test_dispatcher_keeps_compatibility_alias_for_peptide_service():
    assert queue_handler.run_peptide_docking_helper is peptide_docking.run_peptide_docking_helper


def _sin_autoencendido(monkeypatch):
    """Aísla el fallback del autoencendido de ENG-002.

    Con el motor fuera del catálogo descargable, `sidecar_de` devuelve `None` y
    la ruta llega hasta donde estas pruebas quieren mirar: qué hace cuando el
    servicio no responde.
    """
    import services.motores as motores

    monkeypatch.setattr(motores, "sidecar_de", lambda _id: None)


@pytest.mark.asyncio
async def test_un_motor_descargable_sin_instalar_dice_que_hay_que_descargarlo(monkeypatch):
    """ENG-002. El primer eslabón que falta es el motor, no la caja.

    Antes de esto, elegir ESMFold sin tenerlo instalado terminaba en una pose de
    Vina con un aviso. Ahora la corrida se detiene en el sitio correcto y el
    mensaje dice qué hacer: descargarlo, y cuánto pesa.
    """
    import utils.local_storage as local_storage

    async def unavailable_local_pdb(_object_name):
        raise OSError("sin PDB local")

    monkeypatch.setattr(peptide_docking, "get_db_session", lambda: _Session())
    monkeypatch.setattr(peptide_docking, "Repository", lambda _db: _Repository())
    monkeypatch.setattr(peptide_docking, "calculate_properties", lambda _smiles: None)
    monkeypatch.setattr(peptide_docking, "cache", _Cache())
    monkeypatch.setattr(local_storage, "exists", unavailable_local_pdb)

    with pytest.raises(RuntimeError) as error:
        await peptide_docking.run_peptide_docking_helper(
            task_id="task-prueba",
            smiles="CCO",
            target_pdb_id="7E2Y",
            peptide_docking_engine="esmfold",
        )

    mensaje = str(error.value)
    assert "instalado" in mensaje and "GB" in mensaje, (
        "el motivo tiene que decir que falta instalarlo y cuánto ocupa"
    )


@pytest.mark.asyncio
async def test_sin_caja_declarada_el_motor_ausente_falla_en_vez_de_inventarla(monkeypatch):
    """ENG-001. El fallback usaba (20, 30, 28) y 30 Å cuando no le pasaban caja.

    Este test ANTES fijaba ese centro como contrato —`captured["target_center"] ==
    (20.0, 30.0, 28.0)`—. Docking en una caja arbitraria del receptor no es un
    resultado degradado: es un resultado de otro sitio, presentado como el del
    caso. El contrato nuevo es que sin caja no hay corrida.
    """
    import services.docking.vina_service as vina_service
    import utils.local_storage as local_storage

    _sin_autoencendido(monkeypatch)

    async def unavailable_local_pdb(_object_name):
        raise OSError("sin PDB local")

    async def fake_vina(**_kwargs):
        raise AssertionError("no debe acoplar sin caja declarada")

    monkeypatch.setattr(peptide_docking, "get_db_session", lambda: _Session())
    monkeypatch.setattr(peptide_docking, "Repository", lambda _db: _Repository())
    monkeypatch.setattr(peptide_docking, "calculate_properties", lambda _smiles: None)
    monkeypatch.setattr(peptide_docking, "cache", _Cache())
    monkeypatch.setattr(local_storage, "exists", unavailable_local_pdb)
    monkeypatch.setattr(vina_service, "run_vina_docking", fake_vina)

    with pytest.raises(RuntimeError) as error:
        await peptide_docking.run_peptide_docking_helper(
            task_id="task-prueba",
            smiles="CCO",
            target_pdb_id="7E2Y",
            peptide_docking_engine="esmfold",
        )

    assert "esmfold" in str(error.value)
    assert "caja" in str(error.value)


@pytest.mark.asyncio
async def test_con_caja_declarada_cae_a_vina_y_dice_que_sustituyo_el_motor(monkeypatch):
    """La sustitución es legítima con caja, pero tiene que decirse en el resultado.

    El aviso anterior hablaba de «fallback rápido de compatibilidad». El
    investigador pidió un modelo de plegamiento y recibe una pose de Vina: eso se
    nombra, o el resultado se lee como si viniera del motor elegido.
    """
    import services.docking.vina_service as vina_service
    import utils.local_storage as local_storage

    _sin_autoencendido(monkeypatch)

    fake_cache = _Cache()
    fake_result = SimpleNamespace(scientific_warnings=[])
    captured = {}

    async def unavailable_local_pdb(_object_name):
        raise OSError("sin PDB local")

    async def fake_vina(**kwargs):
        captured.update(kwargs)
        return fake_result

    monkeypatch.setattr(peptide_docking, "get_db_session", lambda: _Session())
    monkeypatch.setattr(peptide_docking, "Repository", lambda _db: _Repository())
    monkeypatch.setattr(peptide_docking, "calculate_properties", lambda _smiles: None)
    monkeypatch.setattr(peptide_docking, "cache", fake_cache)
    monkeypatch.setattr(local_storage, "exists", unavailable_local_pdb)
    monkeypatch.setattr(vina_service, "run_vina_docking", fake_vina)

    result = await peptide_docking.run_peptide_docking_helper(
        task_id="task-prueba",
        smiles="CCO",
        target_pdb_id="7E2Y",
        peptide_docking_engine="esmfold",
        grid_center=[103.03, 114.79, 108.36],
        grid_size=[25.0, 25.0, 25.0],
    )

    assert result is fake_result
    assert fake_cache.progress == [("task-prueba", 40, "peptide_folding")]
    assert captured["smiles_hash"] == "hash-prueba"
    assert captured["target_pdb_id"] == "7E2Y"
    # La caja es la del caso, no una inventada por el fallback.
    assert captured["target_center"] == (103.03, 114.79, 108.36)
    assert captured["target_size"] == (25.0, 25.0, 25.0)
    assert captured["exhaustiveness"] == 4
    assert captured["num_poses"] == 5
    assert len(fake_result.scientific_warnings) == 1
    emitido = fake_result.scientific_warnings[0]
    # La severidad la DECLARA quien emite el aviso: ya no se deduce del texto.
    # Que el motor que corrio no sea el que se pidio es critico -la pose no es
    # comparable con la del motor pedido- y antes se pintaba del mismo azul de
    # «nota cientifica» que la procedencia del parseo. Ver `services/avisos.py`.
    assert emitido["codigo"] == "MOTOR_SUSTITUIDO"
    assert emitido["severidad"] == "critica"
    assert "MOTOR SUSTITUIDO" in emitido["mensaje"]
    assert "esmfold" in emitido["mensaje"]
