"""Lo que el dossier dice de la generación 3D es lo que la corrida produjo.

- SCI-A-025: «ETKDG + MMFF94» se escribía siempre, aunque el conformador cae a UFF
  y a una geometría sin optimizar, y lo deja dicho en `ligand_state.conformero`.
- SCI-A-024: la piscina del ensemble se contaba como `conformaciones × num_poses`,
  el máximo solicitado, no las poses que el motor devolvió.
- SCI-A-038: si el ensemble fallaba y la corrida seguía con un confórmero, el
  protocolo sellaba «1 pedida, 1 generada» y el dossier, «Confórmero único ·
  REGISTRADO».
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.i18n_plantillas import traducir
from services.dossier.model import _campo_conformaciones
from services.dossier.taxonomy import Estado

BASE = {"contract": "docking_protocol/v1", "engine": "vina", "exhaustiveness": 8,
        "num_poses": 9, "seed": 42}


def _campo(protocolo, conformero=None):
    ligand_state = {"conformero": conformero} if conformero is not None else {}
    return _campo_conformaciones(SimpleNamespace(docking_protocol=protocolo, ligand_state=ligand_state))


def _unico(**extra):
    return {**BASE, "conformers_requested": 1, "conformers_generated": 1, **extra}


def _conf(campo="MMFF94", convergida=True, embebido="ETKDGv3"):
    return {"estrategia_embebido": embebido, "campo_fuerza_final": campo,
            "optimizacion_convergida": convergida}


# ── SCI-A-025 ────────────────────────────────────────────────────────────────

def test_mmff94_convergido_se_registra():
    campo = _campo(_unico(), _conf())
    assert campo.valor == "Confórmero único (ETKDGv3 + MMFF94)"
    assert campo.estado is Estado.REGISTRADO


@pytest.mark.parametrize("conformero, debe_decir", [
    (_conf(campo="UFF"), "UFF (MMFF94 no parametrizó la molécula)"),
    (_conf(campo="sin_optimizacion", convergida=False), "sin optimizar"),
    (_conf(convergida=False), "MMFF94, sin converger"),
    (None, "método no registrado por la corrida"),
])
def test_un_metodo_que_no_es_mmff94_convergido_no_se_llama_mmff94(conformero, debe_decir):
    campo = _campo(_unico(), conformero)
    assert debe_decir in campo.valor
    assert campo.estado is Estado.REVISAR
    if conformero is None or conformero["campo_fuerza_final"] != "MMFF94":
        assert "MMFF94)" not in campo.valor


@pytest.mark.parametrize("conformero", [
    _conf(), _conf(campo="UFF"), _conf(campo="sin_optimizacion", convergida=False),
    _conf(convergida=False), None,
])
def test_el_metodo_sale_en_ingles(conformero):
    campo = _campo(_unico(), conformero)
    assert traducir(campo.valor, "en").startswith("Single conformer (")
    assert traducir(campo.valor, "en") != campo.valor or "MMFF94)" in campo.valor
    if campo.razon:
        assert traducir(campo.razon, "en") != campo.razon


# ── SCI-A-038 ────────────────────────────────────────────────────────────────

def test_un_ensemble_que_cayo_a_un_conformero_lo_dice():
    campo = _campo({**BASE, "conformers_requested": 4, "conformers_generated": 1}, _conf())
    assert campo.estado is Estado.REVISAR
    assert "se pidieron 4 conformaciones" in campo.valor
    assert traducir(campo.valor, "en").endswith("· 4 conformers were requested")
    assert traducir(campo.razon, "en") != campo.razon


@pytest.mark.asyncio
async def test_el_fallback_del_runner_conserva_lo_pedido(monkeypatch):
    from chem import conformer_ensemble
    from services.pipeline import runner

    async def falla(*_a, **_k):
        raise RuntimeError("sin ensemble")

    async def unico(smiles, ph, **_k):
        return {"conformer_path": "x.sdf", "estado_del_ligando": {}}

    monkeypatch.setattr(conformer_ensemble, "generate_conformer_ensemble", falla)
    monkeypatch.setattr(runner, "generate_conformer", unico)
    base = await runner._generar_conformaciones("CCO", {"conformer": {"conformers": 4}})
    assert base["conformers_requested"] == 4
    assert base["conformers_generated"] == 1
    assert base["conformer_warnings"]


# ── SCI-A-024 ────────────────────────────────────────────────────────────────

def test_la_piscina_cuenta_lo_que_el_motor_devolvio():
    protocolo = {**BASE, "conformers_requested": 3, "conformers_generated": 3,
                 "execution_provenance": {"por_conformacion": [
                     {"indice": 0, "num_poses": 9}, {"indice": 1, "num_poses": 4},
                     {"indice": 2, "num_poses": 0}]}}
    campo = _campo(protocolo, _conf())
    assert "pose elegida entre 13 candidatas" in campo.valor
    assert "27" not in campo.valor
    assert traducir(campo.valor, "en") == "Ensemble · 3 of 3 conformers · pose chosen from 13 candidates"


def test_sin_recuento_medido_se_dice_que_es_un_maximo():
    campo = _campo({**BASE, "conformers_requested": 3, "conformers_generated": 3}, _conf())
    assert "hasta 27 candidatas (recuento no registrado)" in campo.valor
    assert "up to 27 candidates (count not recorded)" in traducir(campo.valor, "en")


# ── SCI-A-025: cada conformación del ensemble lleva su minimización hasta Molcy ──

def test_el_conformero_base_declara_lo_que_registro_el_conformador():
    from chem.conformer_ensemble import minimizacion_del_conformero_base
    assert minimizacion_del_conformero_base({"estado_del_ligando": {"conformero": _conf(campo="UFF")}}) == "UFF"
    assert minimizacion_del_conformero_base({"estado_del_ligando": {}}) is None
    assert minimizacion_del_conformero_base({}) is None


@pytest.mark.asyncio
async def test_por_conformacion_lleva_la_minimizacion():
    from services.docking.ensemble import run_ensemble_docking
    from tests.test_ensemble_conserva_procedencia_de_ejecucion import _procedencia, _resultado

    por_hash = {"h__c0": _procedencia(0), "h__c1": _procedencia(1)}

    async def dock(smiles_hash, smiles=None):
        return _resultado(-9.0, por_hash[smiles_hash])

    resultado = await run_ensemble_docking(
        smiles="CCO", num_poses=4, dock_una=dock, conformeros=[
            {"indice": 0, "smiles_hash": "h__c0", "semilla": 42, "energia": None, "minimizacion": "UFF"},
            {"indice": 1, "smiles_hash": "h__c1", "semilla": 43, "energia": None,
             "minimizacion": "sin_minimizar"}])
    filas = resultado.execution_provenance["por_conformacion"]
    assert [f.get("minimizacion") for f in filas] == ["UFF", "sin_minimizar"]
