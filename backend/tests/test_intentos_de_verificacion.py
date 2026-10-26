"""Los intentos de verificación publicados son los del experimento sellado.

Lo que impiden:

1. Que una cifra publicada no sea la medida: cada intento coincide con el
   `metrics.json` y la decisión de su experimento en `scripts/artifacts_science/`.
2. Que un intento NO_GO promocione el receptor, o que un GO no esté en el registro
   de verificados con las mismas cifras.
3. Que la API lo pierda: viaja en el listado del catálogo sin cambiar la sección.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.targets import seccion_catalogo as sc

RAIZ = Path(__file__).resolve().parents[2]
ARTEFACTOS = RAIZ / "scripts" / "artifacts_science"


def _intentos() -> list[dict]:
    return json.loads(sc.RUTA_INTENTOS.read_text(encoding="utf-8"))["intentos"]


@pytest.fixture(autouse=True)
def limpiar_cache():
    sc._leer.cache_clear()
    yield
    sc._leer.cache_clear()


def test_intentos_publicados():
    assert [(i["pdb_id"], i["experimento"]) for i in _intentos()] == [
        ("8HFI", "CAL-8HFI-01"), ("8T69", "CAL-D-01-R4-VMAT2-8T69"), ("8T69", "CAL-D-01-R4B-VMAT2-8T69"),
        ("8T69", "CAL-D-01-R4-2-VMAT2-8T69")]


def _discrepancias_cal_d01(intento: dict) -> list[str]:
    """CAL-D-01 R4/R4B/R4-2: métricas planas (rho, rho_peor, IC por bootstrap) y puerta de pose propia.

    R4B reanaliza R4 sin acoplar nada, así que su pose y su receptor son los de R4; R4-2 tiene los suyos."""
    exp = ARTEFACTOS / intento["experimento"]
    metrics = json.loads((exp / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((exp / "manifest.json").read_text(encoding="utf-8"))
    r4 = exp if (exp / "puerta_pose.json").exists() else ARTEFACTOS / "CAL-D-01-R4-VMAT2-8T69"
    pose = json.loads((r4 / "puerta_pose.json").read_text(encoding="utf-8"))
    proto = json.loads((r4 / "entrada" / "protocolo.json").read_text(encoding="utf-8"))
    cal, p = intento["calibracion"], intento["pose"]
    r = lambda x: round(x, 4)
    pares = {
        "decision": (intento["decision"], manifest["decision"]),
        "pose.gate": (p["gate"], pose["decision"]),
        "pose.semillas_rmsd_ok": (p["semillas_rmsd_ok"], pose["semillas_rmsd_ok"]),
        "pose.rmsd_top1_A": (p["rmsd_top1_A"], [s["rmsd_A"] for s in pose["semillas"]]),
        "pose.posebusters_valida": (p["posebusters_valida"], pose["posebusters_valida_en_las_que_cumplen"]),
        "calibracion.rho": (cal["rho"], r(metrics["rho_Q_pKi"])),
        "calibracion.ic95": (cal["ic95"], [r(x) for x in metrics["ic95_rho"]]),
        "calibracion.rho_peor": (cal["rho_peor"], r(metrics["rho_peor"])),
        "calibracion.ic95_rho_peor": (cal["ic95_rho_peor"], [r(x) for x in metrics["ic95_rho_peor"]]),
        "calibracion.n": (cal["n"], metrics["n_evaluados"]),
        "receptor_sha256": (intento["receptor_sha256"], proto["receptor"]["receptor_preparado_sha256"]),
    }
    if "fallos_persistentes" in metrics:
        pares["calibracion.fallos"] = (cal["fallos"], metrics["fallos_persistentes"])
    if "criterio_enmendado_cumplido" in metrics:
        pares["no_confirmatorio"] = (metrics["confirmatorio"], False)
    return [campo for campo, (publicado, sellado) in pares.items() if publicado != sellado]


def _discrepancias(intento: dict) -> list[str]:
    """Campos del intento que no coinciden con su experimento sellado."""
    if intento["experimento"].startswith("CAL-D-01-"):
        return _discrepancias_cal_d01(intento)
    exp = ARTEFACTOS / intento["experimento"]
    metrics = json.loads((exp / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((exp / "manifest.json").read_text(encoding="utf-8"))
    protocolo = json.loads((exp / "entrada" / "protocolo.json").read_text(encoding="utf-8"))
    ver, cal = metrics["verificacion"], metrics["calibracion"]
    pares = {
        "decision": (intento["decision"], metrics["decision"]),
        "decision_del_cierre": (intento["decision"] in json.dumps(manifest), True),
        "pose.gate": (intento["pose"]["gate"], ver["gate"]),
        "pose.semillas_rmsd_ok": (intento["pose"]["semillas_rmsd_ok"], ver["semillas_rmsd_ok"]),
        "pose.semillas": (intento["pose"]["semillas"], len(ver["semillas"])),
        "pose.rmsd_top1_A": (intento["pose"]["rmsd_top1_A"], [s["rmsd_A"] for s in ver["semillas"]]),
        "pose.posebusters_valida": (intento["pose"]["posebusters_valida"], ver["posebusters_valida"]),
        "calibracion.gate": (intento["calibracion"]["gate"], cal["gate"]),
        "calibracion.rho": (intento["calibracion"]["rho"], cal["rho_Q_pKi"]),
        "calibracion.ic95": (intento["calibracion"]["ic95"], cal["ic95_bootstrap"]),
        "calibracion.n": (intento["calibracion"]["n"], cal["n"]),
        "calibracion.fallos": (intento["calibracion"]["fallos"], cal["fallos"]),
        "receptor_sha256": ([intento["receptor_sha256"]], metrics["receptor_sha256_distintos"]),
        "condiciones": (intento["condiciones"], protocolo["condiciones_declaradas"]),
    }
    return [campo for campo, (publicado, sellado) in pares.items() if publicado != sellado]


@pytest.mark.parametrize("intento", _intentos(), ids=lambda i: i["experimento"])
def test_cada_intento_coincide_con_su_experimento_sellado(intento):
    assert _discrepancias(intento) == []


@pytest.mark.parametrize("campo, valor", [
    (("calibracion", "rho"), 0.31),
    (("calibracion", "ic95"), [0.01, 0.41]),
    (("pose", "semillas_rmsd_ok"), 4),
    (("decision",), "GO"),
])
@pytest.mark.parametrize("indice", [0, 1, 2, 3])
def test_el_guardian_ve_una_cifra_alterada(campo, valor, indice):
    """Control negativo: mejorar (o, en el GO, empeorar) una cifra a mano tiene que fallar."""
    import copy

    intento = copy.deepcopy(_intentos()[indice])
    if indice == 3 and campo == ("decision",):
        valor = "NO_GO"
    if indice and campo == ("calibracion", "ic95"):
        valor = [0.01, 0.41]
    destino = intento
    for clave in campo[:-1]:
        destino = destino[clave]
    destino[campo[-1]] = valor
    assert _discrepancias(intento) != []


@pytest.mark.parametrize("intento", _intentos(), ids=lambda i: i["experimento"])
def test_un_no_go_no_promociona_y_un_go_esta_en_verificados(intento):
    """Un NO_GO o INCONCLUSIVE no promociona: si el receptor está en Verificados, es por otro intento GO."""
    verificacion = sc.verificacion_del_receptor(intento["pdb_id"])
    if intento["decision"] in {"NO_GO", "INCONCLUSIVE"} and verificacion is not None:
        respaldo = [i for i in _intentos() if i["pdb_id"] == intento["pdb_id"] and i["decision"] == "GO"]
        assert [i["experimento"] for i in respaldo] == [verificacion["experimento"]]
        assert verificacion["experimento"] != intento["experimento"]
    elif intento["decision"] in {"NO_GO", "INCONCLUSIVE"}:
        assert sc.seccion_del_receptor(SimpleNamespace(pdb_id=intento["pdb_id"], is_private=False,
                                                       is_community=False)) == "demostracion"
    else:
        assert verificacion is not None
        assert verificacion["calibracion"]["rho"] == intento["calibracion"]["rho"]
        assert verificacion["experimento"] == intento["experimento"]


def test_lectura_por_receptor():
    assert [i["experimento"] for i in sc.intentos_del_receptor("8hfi")] == ["CAL-8HFI-01"]
    assert [i["experimento"] for i in sc.intentos_del_receptor("8t69")] == [
        "CAL-D-01-R4-VMAT2-8T69", "CAL-D-01-R4B-VMAT2-8T69", "CAL-D-01-R4-2-VMAT2-8T69"]
    assert sc.intentos_del_receptor("1UZJ") == []
    assert sc.intentos_del_receptor(None) == []


@pytest.mark.parametrize("contenido", [None, "{", "[]", '{"intentos": {}}',
                                       '{"intentos": [{"pdb_id": "8HFI", "decision": "QUIZA"}]}'])
def test_archivo_ausente_corrupto_o_decision_invalida(monkeypatch, tmp_path, contenido):
    ruta = tmp_path / "intentos.json"
    if contenido is not None:
        ruta.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(sc, "RUTA_INTENTOS", ruta)
    assert sc.intentos_del_receptor("8HFI") == []


@pytest.mark.asyncio
async def test_el_listado_lo_transporta_sin_cambiar_la_seccion(monkeypatch):
    from api.routers import targets

    receptor = SimpleNamespace(
        id=uuid.uuid4(), pdb_id="8HFI", name="NET", chain="A", description=None, is_prepared=False,
        requires_cns=False, structural_family="transporter", organism=None, resolution=None,
        is_private=False, is_community=False, retired_reason=None, hotspots=None,
    )
    monkeypatch.setattr(targets.Repository, "get_all_targets", AsyncMock(return_value=[receptor]))
    monkeypatch.setattr(targets, "estado_de_calibracion", lambda _: SimpleNamespace(to_dict=lambda: {}))
    monkeypatch.setattr(targets, "motivo_no_disponible", lambda _: None)
    monkeypatch.setattr(targets, "cadenas_truncadas_en_sitio", lambda _: [])
    resultado = (await targets.list_targets(current_user=None, db=None))[0]
    assert resultado.seccion_catalogo == "demostracion"
    assert [i["experimento"] for i in resultado.intentos_verificacion] == ["CAL-8HFI-01"]
