"""El resultado y el dossier declaran qué residuos de referencia usó la corrida (2026-10-04).

Medido en QA1-007: el panel de resultados pintaba los 15 residuos del CATÁLOGO aunque la corrida usara otra
selección (o ninguna), y el dossier omitía `custom_hotspots` cuando la lista estaba vacía. Un tercero no podía
saber qué se había usado. Decisión del propietario: se declaran, y en el resultado y el dossier.

Las tres procedencias son tres hechos distintos (SOL-08): `catalog` (nadie tocó la selección), `selected` (la
persona eligió) y `none` (decidió no usar residuos). Y una ausencia: las corridas anteriores no lo sellaron.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.docking.protocolo import construir_protocolo, declarar_residuos_de_referencia

RAIZ = Path(__file__).resolve().parents[1]

CATALOGO = [{"name": f"A:RES{i}", "importance": 1.0} for i in range(1, 16)]


def _declarar(elegidos, activos=None):
    if activos is None:
        activos = CATALOGO if elegidos is None else [{"name": n, "importance": 1.0} for n in elegidos]
    return declarar_residuos_de_referencia(
        activos=activos, elegidos=elegidos, catalogo=CATALOGO, fuente_del_catalogo="curated",
    )


# ── Las tres procedencias ────────────────────────────────────────────


def test_sin_tocar_la_seleccion_se_hereda_el_catalogo():
    d = _declarar(None)
    assert d["source"] == "catalog"
    assert d["count"] == 15 and d["catalog_count"] == 15
    assert d["residues"][0] == "A:RES1"
    assert d["catalog_source"] == "curated"


def test_una_seleccion_vacia_es_la_decision_de_no_usar_residuos():
    # `[]` NO es «sin tocar»: es la decisión explícita (SOL-08).
    d = _declarar([])
    assert d["source"] == "none"
    assert d["residues"] == [] and d["count"] == 0
    assert d["catalog_count"] == 15


def test_un_subconjunto_dice_cuantos_de_cuantos():
    d = _declarar(["A:RES2", "A:RES7"])
    assert d["source"] == "selected"
    assert d["residues"] == ["A:RES2", "A:RES7"]
    assert (d["count"], d["catalog_count"]) == (2, 15)


def test_un_residuo_elegido_fuera_del_catalogo_tambien_se_declara():
    d = _declarar(["A:RES2", "B:XYZ99"])
    assert d["residues"] == ["A:RES2", "B:XYZ99"]
    assert d["count"] == 2


def test_se_declaran_los_residuos_que_entraron_no_los_pedidos():
    # Si el pipeline usó otra lista que la pedida, manda la usada.
    d = declarar_residuos_de_referencia(
        activos=[{"name": "A:RES1", "importance": 1.0}], elegidos=["A:RES1", "A:RES2"],
        catalogo=CATALOGO,
    )
    assert d["residues"] == ["A:RES1"]


def test_un_catalogo_vacio_no_rompe():
    d = declarar_residuos_de_referencia(activos=[], elegidos=None, catalogo=[])
    assert d == {"source": "catalog", "residues": [], "count": 0, "catalog_count": 0, "catalog_source": None}


# ── Viaja en el protocolo sellado ────────────────────────────────────


def _docking():
    return SimpleNamespace(
        engine_efectivo="vina", exhaustiveness_efectiva=8, num_poses_solicitadas=9,
        vina_random_seed=42, execution_provenance=None,
    )


def test_el_protocolo_sellado_lleva_los_residuos_usados():
    protocolo = construir_protocolo(docking=_docking(), residuos_de_referencia=_declarar(["A:RES2"]))
    assert protocolo["reference_residues"]["source"] == "selected"
    assert protocolo["contract"] == "docking_protocol/v2"  # aditivo: el contrato no cambia de versión


def test_sin_declarar_no_se_inventa_ninguno():
    # Control: una corrida que no lo declara no lleva la clave, y el dossier lo dirá como ausencia.
    assert "reference_residues" not in construir_protocolo(docking=_docking())


# ── El dossier lo cuenta ─────────────────────────────────────────────


def _campo(protocolo):
    from services.dossier.model import _campo_residuos_de_referencia

    return _campo_residuos_de_referencia(protocolo).as_dict()


def test_el_dossier_dice_que_se_heredo_el_catalogo():
    campo = _campo({"reference_residues": _declarar(None)})
    assert campo["estado"] == "REGISTRADO"
    assert campo["valor"].startswith("15 del catálogo: A:RES1")
    assert "… y 3 más" in campo["valor"]  # abrevia: 12 nombres y el resto contado


def test_el_dossier_dice_cuantos_se_eligieron_de_cuantos():
    campo = _campo({"reference_residues": _declarar(["A:RES2", "A:RES7"])})
    assert campo["valor"] == "2 elegidos de 15 del catálogo: A:RES2, A:RES7"


def test_el_dossier_dice_ninguno_cuando_la_persona_decidio_no_usar():
    campo = _campo({"reference_residues": _declarar([])})
    assert campo["estado"] == "REGISTRADO"
    assert "Ninguno" in campo["valor"]
    assert "no calcula qué residuos del sitio contactan las poses" in campo["razon"]


@pytest.mark.parametrize("protocolo", [None, {}, {"engine": "vina"}, {"reference_residues": None}])
def test_una_corrida_anterior_se_declara_sin_dato_no_se_sustituye(protocolo):
    campo = _campo(protocolo)
    assert campo["estado"] == "NO_EVALUADO"
    assert campo["valor"] is None
    assert "anterior al sellado" in campo["razon"]


# ── Ningún camino de ejecución puede olvidarlo ───────────────────────
#
# `docking_protocol` lo escribía UN solo camino y el otro lo dejaba a NULL sin error (ver
# `services/docking/protocolo.py`). Los dos ejecutores llaman a `construir_protocolo`; los dos tienen que
# pasarle los residuos.


@pytest.mark.parametrize("ruta", ["services/pipeline/runner.py", "services/docking/queue_handler.py"])
def test_cada_ejecutor_sella_los_residuos_de_referencia(ruta):
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    llamadas = [
        n for n in ast.walk(arbol)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "construir_protocolo"
        and any(k.arg == "residuos_de_referencia" for k in n.keywords)
    ]
    assert llamadas, f"{ruta} llama a construir_protocolo sin residuos_de_referencia"
    declaradas = [
        n for n in ast.walk(arbol)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "declarar_residuos_de_referencia"
    ]
    assert declaradas, f"{ruta} no declara los residuos de referencia"
