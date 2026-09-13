"""Los routers dormidos no se publican, y siguen sin pudrirse.

Auditoría de backend del 2026-09-04, §4.1. Tres routers estaban montados en
`api/main.py` describiendo capacidades que esta instalación no tiene:

    /steam/*              verificación de compra vía Steam Web API
    /docking/diffdock/*   proxy HTTP a un servidor de DiffDock
    /docking/colabfold/*  proxy HTTP a ColabFold

La auditoría pedía borrarlos. No se borran: las tres integraciones están en el
plan del producto —Steam como canal de distribución (`docs/37_INTEGRATION_POLICY.md`
la fecha en ~Q4 2026), DiffDock y ColabFold como motores que volverán cuando
exista el motor de inferencia detrás— y borrar el cliente no acerca ninguna.

Lo que sí era un defecto es que la ruta estuviera **publicada**. El inventario de
`GET /evaluation/engines` ya declaraba DiffDock y ColabFold como no disponibles y
el modal los enseñaba apagados, pero `POST /docking/diffdock/predict` contestaba
igual a quien la llamara: en una máquina sin red, un `httpx` con timeout de 300 s
ocupando un hilo del pool. Y `/steam/verify` sin `STEAM_WEB_API_KEY` devuelve
`verified: true` a cualquiera, que es lo contrario de lo que su nombre promete.

Esta prueba fija las dos mitades del trato:

1. Por defecto **no hay ruta**.
2. Con `MONTAR_ROUTERS_DORMIDOS=1` las hay — y los módulos importan, que es lo
   único que impide que el código guardado se pudra en silencio hasta el día que
   se quiera usar.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI

PREFIJOS_DORMIDOS = ("/steam", "/docking/diffdock", "/docking/colabfold")

MODULOS_DORMIDOS = (
    "api.routers.steam",
    "api.routers.diffdock",
    "api.routers.colabfold",
)


def _rutas(app: FastAPI) -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


def _dormidas(app: FastAPI) -> set[str]:
    return {
        ruta
        for ruta in _rutas(app)
        if any(ruta.startswith(prefijo) for prefijo in PREFIJOS_DORMIDOS)
    }


def test_por_defecto_no_se_publica_ninguna_ruta_dormida():
    """La app que arranca en una instalación limpia no expone las tres rutas."""
    from api.main import app

    assert _dormidas(app) == set(), (
        "Un router dormido volvió a montarse por defecto. Si la integración ya "
        "tiene motor detrás, quítala de este test; si no, móntala sólo bajo "
        "MONTAR_ROUTERS_DORMIDOS."
    )


def test_la_app_por_defecto_sigue_sirviendo_lo_demas():
    """Desmontar tres routers no puede llevarse por delante el resto de la API."""
    from api.main import app

    rutas = _rutas(app)
    for imprescindible in ("/evaluation/engines", "/chem/properties", "/rescore"):
        assert imprescindible in rutas, f"{imprescindible} desapareció de la app"


@pytest.mark.parametrize("modulo", MODULOS_DORMIDOS)
def test_el_codigo_dormido_sigue_importando(modulo: str):
    """Guardado no es lo mismo que abandonado: el módulo tiene que cargar.

    Es la contrapartida de no borrarlos. Un router que ya no se monta deja de
    ejecutarse en las pruebas de integración, así que un `import` roto —una
    dependencia retirada, un símbolo renombrado en `utils.logger`— viviría hasta
    el día en que alguien active el flag. Aquí falla el mismo día.
    """
    mod = importlib.import_module(modulo)
    assert getattr(mod, "router", None) is not None, (
        f"{modulo} ya no expone `router`"
    )


def test_el_flag_los_vuelve_a_montar():
    """La puerta de vuelta existe y está probada, no sólo documentada."""
    from fastapi import FastAPI as _FastAPI

    app = _FastAPI()
    for modulo in MODULOS_DORMIDOS:
        app.include_router(importlib.import_module(modulo).router)

    montadas = _dormidas(app)
    assert {"/steam/verify", "/docking/diffdock/predict", "/docking/colabfold/predict"} <= montadas, (
        f"Los routers dormidos ya no publican sus rutas al montarlos: {sorted(montadas)}"
    )


def test_el_ajuste_existe_y_viene_apagado():
    from core.config import Settings

    campo = Settings.model_fields.get("montar_routers_dormidos")
    assert campo is not None, "montar_routers_dormidos desapareció de Settings"
    assert campo.default is False, (
        "montar_routers_dormidos no puede venir encendido por defecto: publicaría "
        "clientes HTTP de servicios que el instalador no trae."
    )
