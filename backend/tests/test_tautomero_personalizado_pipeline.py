import asyncio
from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError
from services.docking.protocolo import resolver_parametros_docking
from services.docking.preflight import canonical_input_document
from api.routers.evaluation import PipelineConfigRequest
from services.dossier.model import campos_del_estado_del_ligando, Estado
from services.dossier.localization import traducir_dossier
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito

def config(mode):
    return {"stage_params":{"conformer":{"tautomero":mode}}}

def test_api_acepta_modo_y_cambia_documento_firmado():
    kwargs=dict(smiles_for_hash="Oc1ccccn1",target_pdb_id="1C6X",chain="A",grid_center=(1,2,3),grid_size=(20,20,20),custom_hotspots=[],docking_engine="vina",exhaustiveness=16,num_poses=9,seed=42,source_sha256="a"*64,prepared_sha256=None)
    docs=[canonical_input_document(**kwargs,pipeline_config=PipelineConfigRequest.model_validate(config(m)).model_dump(exclude_none=True)) for m in ("canonico","entrada")]
    assert docs[0] != docs[1]
    assert '"tautomero":"entrada"' in docs[1].replace(" ","")

def test_modo_desconocido_rechazado_en_api_y_resolucion_directa():
    with pytest.raises(ValidationError,match="tautomero"):
        PipelineConfigRequest.model_validate(config("inventado"))
    with pytest.raises(ValueError,match="tautomero"):
        resolver_parametros_docking(pipeline_config=config("inventado"),size=(20,20,20))

@pytest.mark.parametrize("k,fallback",[(1,False),(2,False),(2,True)])
def test_runner_respeta_entrada_incluso_si_falla_ensemble(monkeypatch,k,fallback):
    import services.pipeline.runner as runner
    import chem.conformer_ensemble as ensemble
    single=AsyncMock(return_value={"estado_del_ligando":{"tautomeria":{"modo":"entrada"}}})
    multiple=AsyncMock(side_effect=RuntimeError("no embedding") if fallback else None,return_value={"ok":True})
    monkeypatch.setattr(runner,"generate_conformer",single)
    monkeypatch.setattr(ensemble,"generate_conformer_ensemble",multiple)
    result=asyncio.run(runner._generar_conformaciones("Oc1ccccn1",{"conformer":{"conformers":k,"ph":7.4,"tautomero":"entrada"}}))
    call=single if k==1 or fallback else multiple
    assert call.await_args.kwargs["tautomero"] == "entrada"
    if fallback: assert result["conformer_warnings"]

def test_ensemble_conserva_modo_del_conformero_base(monkeypatch):
    import chem.conformer as conformer
    from chem.conformer_ensemble import generate_conformer_ensemble
    base=AsyncMock(return_value={"smiles_hash":"hash","conformer_path":"path","energia":0})
    monkeypatch.setattr(conformer,"generate_conformer",base)
    asyncio.run(generate_conformer_ensemble("Oc1ccccn1",1,7.4,tautomero="entrada"))
    assert base.await_args.kwargs["tautomero"] == "entrada"

def test_quimica_real_conserva_h_movido_y_canonico_lo_cambia():
    from chem.conformer import _construir_conformero
    from rdkit import Chem
    states=[_construir_conformero("Oc1ccccn1",7.4,mode)["estado_del_ligando"] for mode in ("entrada","canonico")]
    assert states[0]["smiles_acoplado"] == Chem.MolToSmiles(Chem.MolFromSmiles("Oc1ccccn1"))
    assert states[1]["smiles_acoplado"] != states[0]["smiles_acoplado"]
    assert "[nH]" in states[1]["smiles_acoplado"]

@pytest.mark.parametrize("lang",["es","en"])
def test_dossier_y_preparacion_declaran_quien_eligio_sin_resolver_poblaciones(lang):
    from chem.declaracion_tautomeros import declarar_tautomeros
    for mode,phrase in (("entrada","tautómero del usuario" if lang=="es" else "user's tautomer"),("canonico","canónico de RDKit" if lang=="es" else "RDKit canonical")):
        state={"tautomeria":{"modo":mode,"declaracion":declarar_tautomeros("Oc1ccccn1")}}
        field=traducir_dossier(dict(campos_del_estado_del_ligando(state))["tautomero"],lang)
        assert phrase in field.razon
        assert field.estado == Estado.REVISAR
        audit=traducir_dossier(_auditar(_con_procedencia(**state)),lang)
        assert phrase in _requisito(audit,"ligando.tautomero")["razon"]
        if lang=="en": assert "tautómeros" not in _requisito(audit,"ligando.tautomero")["razon"]


# ── 2026-10-10: el tautómero escrito es el valor por defecto ─────────

_HUELLA = dict(target_pdb_id="3F75", chain="A", grid_center=(1, 2, 3), grid_size=(20, 20, 20), custom_hotspots=[],
               docking_engine="vina", exhaustiveness=8, num_poses=9, seed=42, source_sha256="a" * 64,
               prepared_sha256=None)
_VORINOSTAT = "O=C(CCCCCCC(=O)Nc1ccccc1)NO"


def _documento(smiles, pipeline_config=None):
    import json
    return json.loads(canonical_input_document(smiles_for_hash=smiles, pipeline_config=pipeline_config, **_HUELLA))


def test_por_defecto_se_acopla_el_tautomero_escrito():
    from chem.conformer import TAUTOMERO_POR_DEFECTO
    from services.docking.protocolo import resolver_modo_tautomero
    assert TAUTOMERO_POR_DEFECTO == "entrada"
    assert resolver_modo_tautomero(None) == "entrada"
    assert resolver_modo_tautomero({"tautomero": "canonico"}) == "canonico"


def test_si_el_canonico_no_cambia_la_molecula_la_huella_no_cambia():
    """Aspirina: los dos modos acoplan lo mismo, así que los casos guardados siguen correspondiendo."""
    aspirina = "CC(=O)Oc1ccccc1C(=O)O"
    sin_config = _documento(aspirina)
    assert "tautomero" not in sin_config and "pipeline_config" not in sin_config
    assert _documento(aspirina, config("canonico")) == _documento(aspirina, config("entrada"))


def test_si_el_canonico_cambia_la_molecula_la_huella_lo_distingue():
    implicito = _documento(_VORINOSTAT)
    assert implicito["tautomero"] == "entrada"              # el defecto nuevo acopla otra especie que antes
    assert "tautomero" not in _documento(_VORINOSTAT, config("canonico"))
    assert _documento(_VORINOSTAT, {"stage_params": {"conformer": {"conformers": 1}}})[
        "pipeline_config"]["stage_params"]["conformer"]["tautomero"] == "entrada"


def test_la_codificacion_de_antes_se_conserva():
    """Antes: `canonico` sin clave y `entrada` dentro de pipeline_config, tal cual."""
    antes_entrada = config("entrada")
    assert _documento(_VORINOSTAT, antes_entrada)["pipeline_config"] == antes_entrada
    antes_canonico = {"stage_params": {"conformer": {"conformers": 1}}}
    assert _documento("CC(=O)Oc1ccccc1C(=O)O", antes_canonico)["pipeline_config"] == antes_canonico
