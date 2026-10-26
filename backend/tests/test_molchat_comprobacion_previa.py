"""MolChat lee la comprobación previa de Evaluación, y la respuesta la escribe el código.

LOS FALLOS QUE VIGILA (medidos el 2026-10-10 en una cápsula de QA con el
catálogo real y Qwen2.5-1.5B).

1. A «¿por qué está bloqueado el receptor 8HFI?» MolChat contestaba de memoria:
   la pregunta caía en `conceptual` o `unknown`, que le quitan las
   herramientas al modelo. `check_preparation` devuelve el informe REAL de
   `POST /evaluation/preflight`, el del panel «Comprobación previa».
2. Con ese informe delante, el modelo escribió «8HFI está bloqueado debido a
   varias advertencias» cuando ningún control bloqueaba: aceptaba la premisa
   de la pregunta. La respuesta del turno la escribe el código.
3. La primera versión decía «Según la pestaña Preparación», que es otra cosa
   (audita una corrida guardada con su propio informe): habría mandado al
   investigador a buscar el dato donde no está.
"""
from __future__ import annotations

import contextlib

import pytest

from services.ai.intent_classifier import classify
from services.ai.tools import preparation_tools as prep
from services.docking import preflight as pf
from tests.conftest import rdkit_available

pytestmark = pytest.mark.skipif(not rdkit_available(), reason="RDKit no disponible")

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"


# ── El clasificador la enruta ─────────────────────────────────────────

@pytest.mark.parametrize("mensaje, receptor", [
    ("¿por qué está bloqueado el receptor 8HFI?", "8HFI"),
    ("¿está listo 7E2Y para acoplar?", "7E2Y"),
    ("advertencias de la preparación de 6LU7", "6LU7"),
    ("is 7E2Y ready for docking?", "7E2Y"),
])
def test_las_preguntas_de_la_comprobacion_previa_van_a_la_herramienta(mensaje, receptor):
    intencion = classify(mensaje)
    assert intencion.tool == "check_preparation"
    assert intencion.target == receptor
    assert not intencion.smiles


def test_con_ligando_se_comprueba_tambien_el_ligando():
    intencion = classify("revisa la preparación de CC(=O)Oc1ccccc1C(=O)O contra 1AJ6")
    assert intencion.tool == "check_preparation"
    assert intencion.target == "1AJ6" and intencion.smiles == ASPIRINA


def test_sin_un_receptor_no_es_la_comprobacion_previa():
    assert classify("¿qué advertencias tiene el dossier?").tool != "check_preparation"
    assert classify("¿qué se preparó en 2024?").tool != "check_preparation"


def test_la_herramienta_no_exige_un_smiles():
    from api.routers.ai import _bootstrap_tools
    from services.ai.chat_service import validar_smiles_de_la_llamada
    from services.ai.tool_registry import get_tool_registry

    _bootstrap_tools()
    herramienta = get_tool_registry().get("check_preparation")
    assert herramienta is not None and herramienta.offline
    assert validar_smiles_de_la_llamada(herramienta, {"target_pdb": "8HFI"})[1] is None


# ── El informe ────────────────────────────────────────────────────────

def _informe(**cambios) -> dict:
    kwargs = dict(
        smiles=ASPIRINA, target_pdb_id="1ABC", chain="A", target_origin="curado",
        target_reference="ref-1", grid_center=(1.0, 2.0, 3.0), grid_size=(20.0, 20.0, 20.0),
        custom_hotspots=None, catalog_grid_center=None, catalog_grid_size=None,
        catalog_hotspots=None, cofactors_whitelist=None, docking_engine="vina",
    )
    kwargs.update(cambios)
    return pf.build_preflight(**kwargs)


def test_el_resumen_trae_todos_los_controles_que_no_pasan_y_ninguno_mas():
    informe = _informe()
    texto = prep.resumir_informe(informe, con_ligando=True)
    no_pasan = {c["code"] for c in informe["controls"] if c["state"] != "pasa"}
    for codigo in no_pasan:
        assert f"[{codigo}]" in texto, codigo
    pasan = sum(1 for c in informe["controls"] if c["state"] == "pasa")
    assert f"Pasan {pasan} controles." in texto
    assert informe["input_fingerprint"].replace("sha256:", "")[:12] in texto
    assert texto.startswith("Comprobación previa de 1ABC")


def test_sin_ligando_no_describe_el_ligando_de_sondeo():
    informe = _informe(smiles=prep._LIGANDO_DE_SONDEO)
    texto = prep.resumir_informe(informe, con_ligando=False)
    assert "LIGANDO_" not in texto
    assert "sin ligando" in texto


def test_el_ligando_de_sondeo_es_valido():
    """Un sondeo que el validador rechaza bloquea por sí mismo y puede dejar sin evaluar lo demás."""
    informe = _informe(smiles=prep._LIGANDO_DE_SONDEO)
    assert "LIGANDO_SMILES_VALIDO" not in informe["technical_blockers"]


def _con_estados(informe: dict, estados: dict[str, str]) -> dict:
    """El mismo informe con algunos controles forzados a un estado."""
    copia = dict(informe)
    copia["controls"] = [dict(c, state=estados.get(c["code"], c["state"])) for c in informe["controls"]]
    return copia


# ── La respuesta ──────────────────────────────────────────────────────

def test_la_respuesta_desmiente_un_bloqueo_que_no_existe():
    """Lo que pasó en la cápsula: «¿por qué está bloqueado 8HFI?» sin ningún bloqueante del receptor."""
    base = _informe(smiles=prep._LIGANDO_DE_SONDEO)
    sin_bloqueos = _con_estados(base, {c["code"]: "pasa" for c in base["controls"] if c["state"] == "bloquea"})
    # El único bloqueante es del ligando de sondeo, que sin ligando no cuenta.
    sin_bloqueos = _con_estados(sin_bloqueos, {"LIGANDO_SMILES_VALIDO": "bloquea"})
    breve = prep.respuesta_breve(sin_bloqueos, con_ligando=False)
    assert "no está bloqueado por el receptor ni por el protocolo" in breve
    assert "SMILES de un ligando" in breve
    assert not breve.startswith("Sí")


def test_la_respuesta_confirma_un_bloqueo_real_y_lo_nombra():
    base = _informe()
    bloqueado = _con_estados(base, {"RECEPTOR_FUENTE_DISPONIBLE": "bloquea"})
    breve = prep.respuesta_breve(bloqueado, con_ligando=True)
    assert breve.startswith("Sí:")
    titulo = next(c["title"] for c in bloqueado["controls"] if c["code"] == "RECEPTOR_FUENTE_DISPONIBLE")
    assert titulo in breve
    assert "no está bloqueado" not in breve


def test_la_respuesta_dice_de_donde_sale_y_no_lo_confunde_con_la_pestana():
    for con_ligando in (True, False):
        breve = prep.respuesta_breve(_informe(), con_ligando=con_ligando)
        assert "comprobación previa de Evaluación" in breve
        assert "según la pestaña Preparación" not in breve.lower()
        assert "La pestaña Preparación es otra cosa" in breve


@pytest.mark.asyncio
async def test_sin_receptor_valido_pide_el_identificador():
    texto = await prep.check_preparation(target_pdb="el de serotonina")
    assert "identificador del receptor" in texto


@pytest.mark.asyncio
async def test_pide_el_mismo_informe_que_la_comprobacion_previa(monkeypatch):
    """La herramienta llama al endpoint del panel, con el ligando de sondeo si no hay SMILES."""
    from api.routers import evaluation
    import core.database

    pedidos = []

    async def preflight_falso(*, data, db, current_user):
        pedidos.append(data)
        return _informe(smiles=data.smiles, target_pdb_id=data.target_pdb_id)

    class _Db:
        async def get(self, *_a, **_k):
            return None

    @contextlib.asynccontextmanager
    async def sesion():
        yield _Db()

    monkeypatch.setattr(evaluation, "evaluation_preflight", preflight_falso)
    monkeypatch.setattr(core.database, "get_db_session", sesion)

    texto = await prep.check_preparation(target_pdb="8hfi")
    assert pedidos[0].target_pdb_id == "8HFI" and pedidos[0].smiles == prep._LIGANDO_DE_SONDEO
    assert "Comprobación previa de 8HFI" in texto and "sin ligando" in texto

    await prep.check_preparation(target_pdb="7E2Y", smiles=ASPIRINA)
    assert pedidos[1].smiles == ASPIRINA


# ── El turno: responde el código, no el modelo ───────────────────────

class _ModeloEspia:
    id = "local"
    name = "Local (espía)"

    def __init__(self):
        from services.ai.providers.base import ProviderConfig
        self.config = ProviderConfig(model="m", max_tokens=128)
        self.llamadas = 0

    def validate_config(self):
        return True, ""

    async def chat(self, *args, **kwargs):
        self.llamadas += 1
        yield "8HFI está bloqueado debido a varias advertencias."

    async def chat_with_tools(self, *args, **kwargs):
        self.llamadas += 1
        return {"content": "", "tool_calls": []}


@pytest.mark.asyncio
async def test_el_turno_de_la_comprobacion_previa_no_lo_redacta_el_modelo(tmp_path, monkeypatch):
    import uuid

    from services.ai import chat_service as modulo
    from services.ai import memory_store
    from services.ai import provider_config_store as store
    from services.ai.providers.registry import ProviderRegistry

    secreto = tmp_path / "secret_key"
    secreto.write_text("c" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")

    espia = _ModeloEspia()
    registro = ProviderRegistry()
    registro.register(espia)
    monkeypatch.setattr(modulo, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: espia)

    pedidos = []

    async def consultar_falso(target, smiles="", chain="", user_id=""):
        pedidos.append((target, smiles))
        return ("Comprobación previa de 8HFI … Pasan 10 controles.",
                "Según la comprobación previa de Evaluación, 8HFI no está bloqueado por el "
                "receptor ni por el protocolo.")

    monkeypatch.setattr(prep, "consultar_preparacion", consultar_falso)

    servicio = modulo.ChatService()
    tokens = [t async for t in servicio.chat(
        messages=[{"role": "user", "content": "¿por qué está bloqueado el receptor 8HFI?"}],
        user_id=str(uuid.uuid4()),
    )]
    texto = "".join(t for t in tokens if not t.startswith("__WARNING__:"))

    assert pedidos == [("8HFI", "")]
    assert "no está bloqueado" in texto
    assert "debido a varias advertencias" not in texto
    assert espia.llamadas == 0
