"""Contrato HTTP del ADMET post-docking.

ADMET-AI es opt-in y la decisión se toma en Opciones avanzadas ANTES de
ejecutar. Quien no lo marcó se quedaba sin perfil para siempre: la única forma
de obtenerlo era volver a acoplar la molécula entera —minutos de Vina— para
recalcular algo que sólo depende del SMILES.

Lo que estas pruebas fijan, y por qué cada una:

1. **Autorización.** Un perfil ADMET va pegado a una molécula del usuario. La
   ruta es nueva, no exenta.
2. **No declara éxito sobre un perfil vacío.** `predict_admet_ai` devuelve
   `None` a propósito cuando el modelo no está, para que nadie confunda un hueco
   con un valor. Si eso llega aquí, se responde 503 — no un perfil de nulos con
   estado «calculado».
3. **No repite un cálculo caro.** Con perfil ya guardado devuelve el que hay.
4. **No convierte un control en molécula normal.** `upsert_evaluation_result`
   escribe `is_control` SIEMPRE, y su valor por omisión es `False`. Llamarlo sin
   reenviar el valor existente marcaría el control como molécula de trabajo, y
   eso cambia lo que significa la corrida entera. Es el peligro menos visible de
   todo este endpoint.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user_optional
from api.routers import pro_features as router_mod
from core.database import get_db

MOLECULE_ID = uuid.UUID("11111111-2222-4333-8444-666666666666")
USUARIO = SimpleNamespace(id=uuid.UUID("99999999-8888-4777-8666-555555555555"))


def _propiedades(indice):
    """Lo que devolvería `calculate_properties`, en lo que a ADMET respecta."""
    return SimpleNamespace(
        blood_viability_score=indice,
        blood_solubility_logs=-2.8,
        blood_ppb_category="low",
        blood_bbb_permeable=False,
        blood_bbb_motivo="Aniónica a pH 7.4",
        blood_cns_mpo=5.66,
        blood_hia_permeable=True,
        blood_systemic_reactivity=[],
        blood_tabpfn_estado="evaluado",
    )


def _evaluacion(*, indice=None, is_control=False):
    return SimpleNamespace(
        molecule=SimpleNamespace(smiles="CC(C)Cc1ccc(cc1)C(C)C(=O)O"),
        blood_viability_score=indice,
        blood_solubility_logs=None,
        blood_ppb_category=None,
        blood_bbb_permeable=None,
        blood_bbb_motivo=None,
        blood_cns_mpo=None,
        blood_hia_permeable=None,
        blood_systemic_reactivity=None,
        blood_tabpfn_estado=None,
        is_control=is_control,
    )


class _RepositorioFalso:
    def __init__(self, evaluacion, registro):
        self._evaluacion = evaluacion
        self._registro = registro

    async def get_evaluation_result(self, _molecule_id):
        return self._evaluacion

    async def upsert_evaluation_result(self, **kwargs):
        self._registro.append(kwargs)
        return self._evaluacion


@pytest.fixture
def cliente(monkeypatch):
    """Monta el router con sus dependencias sustituidas.

    Comprueba el CONTRATO del endpoint, no el ORM ni el modelo de ADMET.
    """
    registro: list[dict] = []
    estado: dict = {"evaluacion": _evaluacion(), "propiedades": _propiedades(95.5), "dueno": True}

    async def _permitir(**kwargs):
        if not estado["dueno"]:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="No tienes permiso.")
        # `require_owned_molecule` mira la MOLÉCULA. Que no haya evaluación es
        # otra cosa, y la comprueba el endpoint justo después.
        evaluacion = estado["evaluacion"]
        return evaluacion.molecule if evaluacion is not None else SimpleNamespace()

    monkeypatch.setattr(router_mod, "require_owned_molecule", _permitir)
    monkeypatch.setattr(
        router_mod, "Repository", lambda _db: _RepositorioFalso(estado["evaluacion"], registro)
    )

    import chem.properties as props_mod

    monkeypatch.setattr(
        props_mod, "calculate_properties", lambda _s, run_admet_ai=True: estado["propiedades"]
    )

    async def _commit(_db):
        return None

    import core.database as db_mod

    monkeypatch.setattr(db_mod, "commit_with_retry", _commit)

    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[get_current_user_optional] = lambda: USUARIO

    with TestClient(app) as c:
        yield c, estado, registro


def test_calcula_y_persiste(cliente):
    c, _estado, registro = cliente
    r = c.post(f"/pro/admet/{MOLECULE_ID}")

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "calculado"
    assert cuerpo["persistido"] is True
    assert cuerpo["blood_viability_score"] == 95.5
    # Se guarda por el mapeo canónico, no escribiendo columnas a mano: dos
    # copias del mapeo divergen, y eso ya costó doce minutos de build una vez.
    assert len(registro) == 1
    assert registro[0]["properties"] is not None


def test_NO_convierte_un_control_en_molecula_normal(cliente):
    """El peligro menos visible: `is_control` se escribe siempre."""
    c, estado, registro = cliente
    estado["evaluacion"] = _evaluacion(is_control=True)

    r = c.post(f"/pro/admet/{MOLECULE_ID}")
    assert r.status_code == 200, r.text
    assert registro[0]["is_control"] is True, (
        "calcular ADMET sobre un control lo marcó como molécula de trabajo"
    )


def test_no_declara_exito_sobre_un_perfil_vacio(cliente):
    """`predict_admet_ai` devuelve `None` a propósito cuando el modelo no está."""
    c, estado, _registro = cliente
    estado["propiedades"] = _propiedades(None)

    r = c.post(f"/pro/admet/{MOLECULE_ID}")
    assert r.status_code == 503
    assert "no esta disponible" in r.json()["detail"].lower()


def test_no_repite_un_calculo_caro(cliente):
    c, estado, registro = cliente
    estado["evaluacion"] = _evaluacion(indice=82.4)

    r = c.post(f"/pro/admet/{MOLECULE_ID}")
    assert r.status_code == 200
    assert r.json()["estado"] == "ya_calculado"
    assert r.json()["blood_viability_score"] == 82.4
    assert registro == [], "recalculó teniendo el perfil guardado"


def test_recalcular_fuerza_el_calculo(cliente):
    c, estado, registro = cliente
    estado["evaluacion"] = _evaluacion(indice=82.4)

    r = c.post(f"/pro/admet/{MOLECULE_ID}?recalcular=true")
    assert r.status_code == 200
    assert r.json()["estado"] == "calculado"
    assert len(registro) == 1


def test_exige_ser_el_dueno(cliente):
    c, estado, _registro = cliente
    estado["dueno"] = False

    assert c.post(f"/pro/admet/{MOLECULE_ID}").status_code == 403


def test_un_molecule_id_invalido_es_400_y_no_500(cliente):
    c, _estado, _registro = cliente
    assert c.post("/pro/admet/no-es-un-uuid").status_code == 400


def test_sin_evaluacion_es_404(cliente):
    c, estado, _registro = cliente
    estado["evaluacion"] = None
    assert c.post(f"/pro/admet/{MOLECULE_ID}").status_code == 404
